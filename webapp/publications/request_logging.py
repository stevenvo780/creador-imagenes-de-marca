"""Diagnóstico allowlist local; no controla request logs gestionados o proxy."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_STANDARD = frozenset(logging.makeLogRecord({}).__dict__)


def route_class(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    for _ in range(4):
        folded = value.casefold().replace("\\", "/")
        if "/publications/oauth/callback" in folded:
            return "oauth_callback"
        if "/publications/delivery-media" in folded:
            return "delivery_media"
        value = unquote(value)
    return None


def _sensitive(value: object) -> str | None:
    values: Iterable[object]
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (tuple, list)):
        values = value
    else:
        return route_class(value)
    for item in values:
        result = _sensitive(item)
        if result:
            return result
    return None


class PublicationAccessFilter(logging.Filter):
    """Conserva método/status Uvicorn, suprime URL/headers/trace sensibles."""

    def filter(self, record: logging.LogRecord) -> bool:
        category = _sensitive(record.__dict__)
        if not category and record.exc_info and record.exc_info[1]:
            category = route_class(str(record.exc_info[1]))
        if not category:
            return True
        args = record.args
        method, status = "UNKNOWN", 0
        if isinstance(args, tuple) and len(args) == 5:
            method = args[1] if isinstance(args[1], str) and args[1] in _METHODS else "UNKNOWN"
            status = args[4] if type(args[4]) is int and 100 <= args[4] <= 599 else 0
        if record.name == "uvicorn.access":
            # AccessFormatter consume siempre cinco valores, también tras redacción.
            record.msg = '%s - "%s %s HTTP/%s" %d'
            record.args = ("[redacted]", method, "/publication/" + category, "1.1", status)
        else:
            record.msg = "publication_request route=%s method=%s status=%s"
            record.args = (category, method, status)
        record.exc_info, record.exc_text, record.stack_info = None, None, None
        for key in set(record.__dict__) - _STANDARD:
            record.__dict__[key] = "[publication-sensitive-redacted]"
        return True


def install_request_log_filters() -> None:
    diagnostics = logging.getLogger("eikon.publication_requests")
    diagnostics.setLevel(logging.INFO)
    if not diagnostics.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        diagnostics.addHandler(handler)
    # Salida local única, sin depender del WARNING de root ni duplicar por propagación.
    diagnostics.propagate = False
    for name in ("uvicorn.access", "uvicorn.error", "httpx"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, PublicationAccessFilter) for item in logger.filters):
            logger.addFilter(PublicationAccessFilter())


class PublicationRequestMiddleware:
    """Cubre 404/422 y fallos antes/después de iniciar respuesta, sin cambiar guards."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        category = route_class(scope.get("path")) or route_class(
            scope.get("raw_path", b"").decode("latin1")
        )
        sensitive_route = category is not None
        for name, value in scope.get("headers", []):
            if name.lower() == b"referer" and route_class(value.decode("latin1")):
                category = category or "sensitive_referer"
        if category is None:
            await self.app(scope, receive, send)
            return
        await self._sensitive_request(
            scope, receive, send, category, sanitize_errors=sensitive_route
        )

    async def _sensitive_request(
        self, scope: Scope, receive: Receive, send: Send, category: str, *, sanitize_errors: bool
    ) -> None:
        started, status, error = False, 0, "none"
        began = time.monotonic()
        request_id = uuid.uuid4().hex

        async def safe_send(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started, status = True, message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in {b"cache-control", b"referrer-policy"}
                ]
                message = {
                    **message,
                    "headers": [
                        *headers,
                        (b"cache-control", b"private, no-store"),
                        (b"referrer-policy", b"no-referrer"),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, safe_send)
        except Exception:
            error = "response_interrupted" if started else "internal_error"
            if not sanitize_errors:
                raise
            if started:
                raise RuntimeError("publication_request_failed") from None
            await safe_send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await safe_send({"type": "http.response.body", "body": b"Internal Server Error"})
        finally:
            if not started and error == "none":
                error = "response_not_started"
            event: dict[str, Any] = dict(
                request_id=request_id,
                route_class=category,
                method=scope.get("method") if scope.get("method") in _METHODS else "UNKNOWN",
                status=status,
                duration_ms=max(0, round((time.monotonic() - began) * 1000)),
                error_class=error,
            )
            logging.getLogger("eikon.publication_requests").log(
                logging.ERROR if error != "none" else logging.INFO,
                json.dumps(event, separators=(",", ":")),
            )
