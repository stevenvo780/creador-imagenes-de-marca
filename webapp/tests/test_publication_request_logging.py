"""Marcadores sintéticos y HTTP real local; no certificado de logs managed."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
    rendered = record.getMessage()
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
    before = record.getMessage()
    PublicationAccessFilter().filter(record)
    assert record.getMessage() == before


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
