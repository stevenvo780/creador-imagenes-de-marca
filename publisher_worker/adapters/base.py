"""Contrato común y transporte sin reintentos, redirecciones ni errores secretos."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import time
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from publisher_worker.outbox import PhaseJournal
from webapp.publications.connections import REQUIRED_SCOPES
from webapp.publications.contracts import ProviderResult

CAPABILITY_STATES = frozenset(
    {
        "unknown",
        "verified",
        "requires_auth",
        "requires_provider_review",
        "requires_post_consent",
        "blocked_by_budget",
        "unsupported_media",
        "rate_limited",
    }
)


def outcome(
    state="uncertain", remote_id=None, *, digest=None, code=None, status=None
) -> ProviderResult:
    evidence = {}
    if digest:
        evidence["receipt_sha256"] = digest
    if code:
        evidence["error_code"] = code
    if status:
        evidence["http_status"] = status
    return {"state": state, "remote_id": remote_id, "permalink": None, "evidence": evidence}


def numeric(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,31}", value) is not None


class ProviderAdapter(Protocol):
    def preflight(self, connection: dict, variant: dict, now: int) -> dict: ...
    def publish(self, connection: dict, variant: dict, attempt_id: str) -> ProviderResult: ...
    def reconcile(self, connection: dict, result: ProviderResult) -> ProviderResult: ...


class ProviderFailure(Exception):
    def __init__(self, result: ProviderResult):
        self.result = result
        super().__init__("provider_unconfirmed")


class HTTPTransport:
    """Conexiones directas, respuesta acotada, sin hooks ni retry automático."""

    def __init__(self):
        logging.getLogger("httpx").addFilter(_TransportLogFilter())
        self.client = httpx.Client(
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=httpx.HTTPTransport(retries=0),
        )

    def request(self, method, url, **kwargs):
        with self.client.stream(method, url, **kwargs) as response:
            chunks = bytearray()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 1024 * 1024:
                    raise ValueError("provider_response_too_large")
            return httpx.Response(response.status_code, content=bytes(chunks))

    def close(self):
        self.client.close()


class _TransportLogFilter(logging.Filter):
    def filter(self, record):
        # HTTPX registra URLs al nivel INFO; un upload_url puede contener tokens.
        record.msg, record.args = "provider_http_request", ()
        return True


class Adapter:
    platform = ""
    needs_delivery = False
    minimum_delivery_seconds = 0

    def __init__(self, transport, *, clock=time.time, sleep=time.sleep, poll_attempts=10):
        self.transport, self.clock, self.sleep = transport, clock, sleep
        self.poll_attempts = poll_attempts
        self._journal: PhaseJournal | None = None
        self.proof = None
        self.processing_complete = False

    def bind(self, journal):
        bound = copy.copy(self)
        bound._journal, bound.proof = journal, None
        bound.processing_complete = False
        return bound

    @property
    def journal(self) -> PhaseJournal:
        if self._journal is None:
            raise ProviderFailure(outcome("held", code="authorization_failed"))
        return self._journal

    def preflight(self, connection, variant, now):
        from publisher_worker.media_delivery import qualify_media

        required = REQUIRED_SCOPES.get((self.platform, connection.get("api_mode")))
        if (
            connection.get("platform") != self.platform
            or connection.get("tenant_id") != variant.get("tenant_id")
            or connection.get("status") != "active"
            or not connection.get("verified_at")
            or connection.get("scope_evidence")
            not in {"remote_introspection", "token_exchange", "capability_probe"}
            or not required
            or not required.issubset(connection.get("scopes", []))
            or connection.get("expiry_state") not in {"known", "non_expiring"}
            or (connection.get("expires_at") is not None and connection["expires_at"] <= now)
        ):
            return {"state": "requires_auth"}
        media = variant["media"]
        kind = "video" if media["kind"] == "publication_video" else "image"
        if (
            variant.get("channel_metadata", {}).get("publication_format") == "reel"
            and kind != "video"
        ):
            return {"state": "unsupported_media"}
        if not connection.get("capabilities", {}).get("publish") or not connection[
            "capabilities"
        ].get(kind):
            return {"state": "unsupported_media"}
        quality = qualify_media(variant, self.platform)
        if quality != "verified":
            return {"state": quality}
        return {"state": "verified"}

    def guard(self, connection):
        return None

    def attempt_guard(self, connection, attempt_id):
        if (
            self.journal is None
            or self.journal.attempt != attempt_id
            or self.journal.box.tenant_id != connection.get("tenant_id")
        ):
            raise ProviderFailure(outcome("held", code="authorization_failed"))

    def request(self, connection, method, url, *, phase=None, **kwargs):
        self.guard(connection)
        if phase and (self.journal is None or not self.journal.begin(phase)):
            raise ProviderFailure(outcome(code="status_unavailable"))
        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", "Bearer " + connection["credential"]["access_token"])
        try:
            response = self.transport.request(method, url, headers=headers, **kwargs)
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderFailure(outcome(code="network_timeout")) from None
        except Exception:
            raise ProviderFailure(outcome(code="connection_error")) from None
        digest = hashlib.sha256(response.content).hexdigest()
        status = response.status_code
        if type(status) is not int or not 200 <= status < 300:
            safe_status = status if type(status) is int and 100 <= status <= 599 else None
            code = "rate_limited" if status == 429 else "provider_rejected"
            if status in (401, 403):
                code = "authorization_failed"
            # Incluso 4xx no permite reconstruir la autoridad de otro intento.
            raise ProviderFailure(outcome(digest=digest, code=code, status=safe_status))
        try:
            body = json.loads(response.content)
            if not isinstance(body, dict) or body.get("errors"):
                raise ValueError
            error = body.get("error")
            if error and (
                self.platform != "tiktok"
                or not isinstance(error, dict)
                or error.get("code") != "ok"
            ):
                raise ValueError
            if self.platform == "tiktok" and (
                not isinstance(error, dict) or error.get("code") != "ok"
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise ProviderFailure(
                outcome(digest=digest, code="provider_rejected", status=status)
            ) from None
        return body, digest

    def receipt(self, phase, digest, **fields):
        self.journal.complete(phase, {"receipt_sha256": digest, **fields})

    def canonical(self, remote_id, digest, *, reconciled=False):
        if not isinstance(remote_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", remote_id):
            return outcome(digest=digest, code="status_unavailable")
        if reconciled:
            self.proof = {"remote_id": remote_id, "sha256": digest, "operation": "remote_lookup"}
        return outcome("published", remote_id, digest=digest)

    def reconcile(self, connection, result):
        return outcome(remote_id=result.get("remote_id"), code="status_unavailable")


def require_upload_url(url, hostname):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ProviderFailure(outcome(code="provider_rejected")) from None
    return url
