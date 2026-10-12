"""Marcadores sintéticos y HTTP real local; no certificado de logs managed."""

import json
import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from uvicorn.logging import AccessFormatter


@pytest.fixture(autouse=True)
def isolated_request_logging(caplog):
    """Captura local y restaura configuración para no alterar otras pruebas."""
    loggers = [
        logging.getLogger(name)
        for name in ("eikon.publication_requests", "uvicorn.access", "uvicorn.error", "httpx")
    ]
    states = [
        (logger.level, logger.propagate, logger.handlers[:], logger.filters[:])
        for logger in loggers
    ]
    loggers[0].addHandler(caplog.handler)
    try:
        yield
    finally:
        for logger, (level, propagate, handlers, filters) in zip(loggers, states, strict=True):
            logger.setLevel(level)
            logger.propagate = propagate
            logger.handlers = handlers
            logger.filters = filters


@pytest.mark.parametrize("configured_handler", ["none", "root", "dedicated"])
def test_default_uvicorn_runtime_emits_allowlisted_diagnostics_once(configured_handler):
    """Sin caplog: detecta INFO perdido, handler ausente y emisiones duplicadas."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import asyncio
                import json
                import logging
                import logging.config
                import sys

                from uvicorn.config import LOGGING_CONFIG
                from webapp.publications.request_logging import (
                    PublicationRequestMiddleware,
                    install_request_log_filters,
                )

                logging.config.dictConfig(LOGGING_CONFIG)
                root = logging.getLogger()
                logger = logging.getLogger("eikon.publication_requests")
                other = logging.getLogger("eikon.unrelated")
                other.setLevel(logging.ERROR)
                existing = logging.StreamHandler(sys.stderr)
                existing.setFormatter(logging.Formatter("%(message)s"))
                if sys.argv[1] == "root":
                    root.addHandler(existing)
                elif sys.argv[1] == "dedicated":
                    logger.addHandler(existing)
                before = (root.level, tuple(root.handlers), other.level)
                access = logging.getLogger("uvicorn.access")
                error = logging.getLogger("uvicorn.error")
                uvicorn_handlers = (tuple(access.handlers), tuple(error.handlers))
                install_request_log_filters()
                installed = tuple(logger.handlers)
                install_request_log_filters()

                async def receive():
                    return {"type": "http.request", "body": b"NOBODY"}

                async def send(message):
                    pass

                async def run():
                    for path, headers, status, fail in (
                        ("/api/v1/publications/oauth/callback", [], 201, False),
                        ("/api/v1/publications/delivery-media/NOTICKET", [], 404, False),
                        ("/health", [(b"referer", b"https://host/api/v1/publications/oauth/callback?code=NOCODE")], 202, False),
                        ("/api/v1/publications/oauth/callback", [], 500, True),
                    ):
                        async def app(scope, receive, send):
                            if fail:
                                raise ValueError("NOCODE NOSTATE NOTICKET NOBODY")
                            await send({"type": "http.response.start", "status": status, "headers": []})
                            await send({"type": "http.response.body", "body": b"NOBODY"})

                        await PublicationRequestMiddleware(app)(
                            {"type": "http", "path": path, "method": "GET",
                             "headers": headers + [(b"authorization", b"NOTOKEN")],
                             "query_string": b"code=NOCODE&state=NOSTATE"},
                            receive, send,
                        )
                        access.info('%s - "%s %s HTTP/%s" %d',
                                    "127.0.0.1", "GET", path + "?code=NOCODE", "1.1", status,
                                    extra={"referer": "https://host/api/v1/publications/oauth/callback?state=NOSTATE"})

                asyncio.run(run())
                other.info("unrelated-info")
                print(json.dumps({"runtime": {
                    "root_unchanged": before == (root.level, tuple(root.handlers), other.level),
                    "uvicorn_handlers_unchanged": uvicorn_handlers == (tuple(access.handlers), tuple(error.handlers)),
                    "installer_idempotent": installed == tuple(logger.handlers),
                    "existing_handler_preserved": sys.argv[1] != "dedicated" or existing in logger.handlers,
                    "effective_level": logger.getEffectiveLevel(),
                }}))
                """
            ),
            configured_handler,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    for marker in ("NOCODE", "NOSTATE", "NOTICKET", "NOBODY", "NOTOKEN", "Traceback"):
        assert marker not in output
    assert "unrelated-info" not in output
    payloads = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    events = [payload for payload in payloads if "request_id" in payload]
    assert len(events) == 4
    assert [(event["route_class"], event["status"], event["error_class"]) for event in events] == [
        ("oauth_callback", 201, "none"),
        ("delivery_media", 404, "none"),
        ("sensitive_referer", 202, "none"),
        ("oauth_callback", 500, "internal_error"),
    ]
    for event in events:
        assert set(event) == {
            "request_id",
            "route_class",
            "method",
            "status",
            "duration_ms",
            "error_class",
        }
        assert event["method"] == "GET" and event["duration_ms"] >= 0
        assert len(event["request_id"]) == 32
    assert len({event["request_id"] for event in events}) == 4
    runtime = next(payload["runtime"] for payload in payloads if "runtime" in payload)
    assert runtime == {
        "root_unchanged": True,
        "uvicorn_handlers_unchanged": True,
        "installer_idempotent": True,
        "existing_handler_preserved": True,
        "effective_level": logging.INFO,
    }
    access_lines = [line for line in result.stdout.splitlines() if '"GET ' in line]
    assert len(access_lines) == 4
    assert all("/publication/" in line for line in access_lines)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/publications/oauth/callback?code=NOCODE&state=NOSTATE",
        "/api/v1/publications/oauth/callback/malformed?code=NOCODE",
        "/api/v1/publications/delivery-media/NOTICKET",
        "/api/v1/publications%2Fdelivery-media%2FNOTICKET",
        "/api/v1/publications%252Fdelivery-media%252FNOTICKET",
    ],
)
def test_source_access_log_preserves_status_without_raw_path(path):
    from webapp.publications.request_logging import PublicationAccessFilter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.WARNING,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", path, "1.1", 404),
        None,
    )
    assert PublicationAccessFilter().filter(record)
    rendered = AccessFormatter(
        fmt='%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False
    ).format(record)
    assert "404" in rendered and "GET" in rendered
    assert "NOCODE" not in rendered and "NOSTATE" not in rendered and "NOTICKET" not in rendered


def test_source_filter_redacts_sensitive_referer_and_exception():
    from webapp.publications.request_logging import PublicationAccessFilter

    try:
        raise ValueError("https://host/api/v1/publications/delivery-media/NOTICKET")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "uvicorn.error", logging.ERROR, __file__, 1, "failure", (), sys.exc_info()
        )
    record.referer = "/api/v1/publications/oauth/callback?code=NOCODE"
    assert PublicationAccessFilter().filter(record)
    assert record.exc_info is None
    assert "NOTICKET" not in record.getMessage() and "NOCODE" not in str(record.__dict__)


def test_safe_access_log_is_preserved_byte_for_byte():
    from webapp.publications.request_logging import PublicationAccessFilter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/health", "1.1", 200),
        None,
    )
    formatter = AccessFormatter(
        fmt='%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False
    )
    before = formatter.format(record)
    original_args = record.args
    PublicationAccessFilter().filter(record)
    assert formatter.format(record) == before
    assert record.args == original_args


@pytest.mark.parametrize("status", [200, 404, 422, 500])
def test_sensitive_http_diagnostics_and_headers_preserve_outcome(caplog, status):
    from starlette.responses import JSONResponse

    from webapp.publications.request_logging import PublicationRequestMiddleware

    app = FastAPI()
    app.add_middleware(PublicationRequestMiddleware)

    @app.get("/api/v1/publications/oauth/callback")
    def callback():
        if status == 500:
            raise ValueError("NOCODE")
        return JSONResponse({"detail": "fixture"}, status_code=status)

    with (
        caplog.at_level(logging.INFO, logger="eikon.publication_requests"),
        TestClient(app) as client,
    ):
        response = client.get("/api/v1/publications/oauth/callback?code=NOCODE&state=NOSTATE")
    assert response.status_code == status
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "NOCODE" not in caplog.text and "NOSTATE" not in caplog.text
    events = [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "eikon.publication_requests"
    ]
    assert events[-1]["status"] == status and events[-1]["route_class"] == "oauth_callback"
    assert events[-1]["method"] == "GET" and events[-1]["duration_ms"] >= 0
    assert len(events[-1]["request_id"]) == 32


def test_real_app_hook_handles_encoded_missing_media_without_secret_echo(media_clients, caplog):
    with caplog.at_level(logging.INFO):
        response = media_clients.a.get(
            "/api/v1/publications%2Fdelivery-media%2FNOTICKET?unused=NOCODE"
        )
    assert response.status_code in (404, 409, 422)
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in response.headers["cache-control"]
    app_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith(("eikon.", "uvicorn."))
    )
    assert "NOTICKET" not in app_logs and "NOCODE" not in app_logs


from webapp.tests.media_helpers import media_clients as _media_clients


@pytest.mark.asyncio
async def test_partial_response_error_aborts_once_without_raw_trace(caplog):
    from webapp.publications.request_logging import PublicationRequestMiddleware

    async def partial(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"part", "more_body": True})
        raise ValueError("NOCODE")

    messages = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    middleware = PublicationRequestMiddleware(partial)
    with pytest.raises(RuntimeError, match="publication_request_failed") as caught:
        await middleware(
            {
                "type": "http",
                "path": "/api/v1/publications/oauth/callback",
                "method": "GET",
                "headers": [],
            },
            receive,
            send,
        )
    assert caught.value.__suppress_context__ is True
    assert [m["type"] for m in messages] == ["http.response.start", "http.response.body"]
    assert messages[0]["status"] == 200
    assert "NOCODE" not in caplog.text


@pytest.mark.asyncio
async def test_normal_route_exception_and_cancellation_are_preserved():
    import asyncio

    from webapp.publications.request_logging import PublicationRequestMiddleware

    failure = ValueError("normal-error")

    async def raises(scope, receive, send):
        raise failure

    async def ignored(*args):
        pass

    with pytest.raises(ValueError) as caught:
        await PublicationRequestMiddleware(raises)(
            {"type": "http", "path": "/health", "headers": []}, ignored, ignored
        )
    assert caught.value is failure

    async def cancel(scope, receive, send):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await PublicationRequestMiddleware(cancel)(
            {"type": "http", "path": "/api/v1/publications/oauth/callback", "headers": []},
            ignored,
            ignored,
        )


media_clients = _media_clients


@pytest.mark.asyncio
@pytest.mark.parametrize("started", [False, True])
async def test_normal_route_with_sensitive_referer_preserves_original_exception(started, caplog):
    from webapp.publications.request_logging import (
        PublicationAccessFilter,
        PublicationRequestMiddleware,
    )

    failure = ValueError("normal-route-error")
    messages = []

    async def normal(scope, receive, send):
        if started:
            await send({"type": "http.response.start", "status": 202, "headers": []})
            await send({"type": "http.response.body", "body": b"part", "more_body": True})
        raise failure

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    referer = b"https://host/api/v1/publications/oauth/callback?code=NOCODE"
    with (
        caplog.at_level(logging.INFO, logger="eikon.publication_requests"),
        pytest.raises(ValueError) as caught,
    ):
        await PublicationRequestMiddleware(normal)(
            {
                "type": "http",
                "path": "/health",
                "method": "GET",
                "headers": [(b"referer", referer)],
            },
            receive,
            send,
        )
    assert caught.value is failure
    assert [m["type"] for m in messages] == (
        ["http.response.start", "http.response.body"] if started else []
    )
    if started:
        assert messages[0]["status"] == 202
        assert (b"cache-control", b"private, no-store") in messages[0]["headers"]
        assert (b"referrer-policy", b"no-referrer") in messages[0]["headers"]
    events = [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "eikon.publication_requests"
    ]
    assert events[-1]["route_class"] == "sensitive_referer"
    assert events[-1]["status"] == (202 if started else 0)
    assert events[-1]["error_class"] == ("response_interrupted" if started else "internal_error")
    assert "NOCODE" not in caplog.text

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/health", "1.1", 202 if started else 500),
        None,
    )
    record.referer = referer.decode()
    PublicationAccessFilter().filter(record)
    rendered = AccessFormatter(fmt="%(request_line)s %(status_code)s", use_colors=False).format(
        record
    )
    assert "GET" in rendered and str(202 if started else 500) in rendered
    assert "NOCODE" not in rendered and "NOCODE" not in str(record.__dict__)
