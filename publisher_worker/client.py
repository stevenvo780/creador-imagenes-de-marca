"""Cliente HTTPS worker y barrido recuperable; el status nunca concede POST."""

from __future__ import annotations

import hashlib
from contextlib import suppress
from urllib.parse import quote, urlsplit

import httpx

from webapp.publications.contracts import canonical_hash

from .adapters.base import outcome
from .adapters.tiktok import PostConsent
from .media_delivery import MediaDelivery


class WorkerAPIError(Exception):
    def __init__(self, status=None):
        self.status = status
        super().__init__("worker_api_unavailable")


class WorkerClient:
    def __init__(self, origin, token, *, tenant_id, http=None):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("worker_https_origin_required")
        self.root, self.tenant_id = origin.rstrip("/") + "/api/v1/publications/worker", tenant_id
        self.http = http or httpx.Client(
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=5),
            transport=httpx.HTTPTransport(retries=0),
        )
        self.headers = {"Authorization": "Bearer " + token}

    def _request(self, method, path, *, binary=False, **kwargs):
        try:
            response = self.http.request(
                method, self.root + path, headers=self.headers, follow_redirects=False, **kwargs
            )
            if not 200 <= response.status_code < 300:
                raise WorkerAPIError(response.status_code)
            if binary:
                if len(response.content) > 32 * 1024 * 1024:
                    raise WorkerAPIError()
                return response.content
            return response.json() if response.status_code != 204 else None
        except WorkerAPIError:
            raise
        except Exception:
            raise WorkerAPIError() from None

    def claim_due(self):
        return self._request("POST", "/claims", json={})

    def _claim_path(self, claim):
        return "/claims/" + quote(claim["claim_id"], safe="")

    def _attempt_path(self, claim):
        return "/attempts/" + quote(claim["attempt_id"], safe="")

    def get_claim(self, claim):
        return self._request("GET", self._claim_path(claim))

    def original(self, claim):
        return self._request("GET", self._claim_path(claim) + "/original", binary=True)

    def credential(self, claim):
        return self._request("POST", self._claim_path(claim) + "/credential", json={})

    def start_attempt(self, claim):
        response = self._request(
            "POST",
            self._claim_path(claim) + "/start",
            json={"contract_hash": claim["contract_hash"]},
        )
        return response | {
            "confirmed": response.get("post_permitted") is True
            and response.get("state") == "attempt_started"
            and response.get("attempt_id") == claim["attempt_id"]
        }

    def hold_claim(self, claim, reason):
        return self._request(
            "POST",
            self._claim_path(claim) + "/hold",
            json={"contract_hash": claim["contract_hash"], "reason": reason},
        )

    def report_attempt(self, claim, result, event_key, confirmation=None):
        body = {"event_key": event_key, "result": result}
        if confirmation is not None:
            body["confirmation"] = confirmation
        return self._request("POST", self._attempt_path(claim) + "/reports", json=body)

    def reconciliation_credential(self, claim):
        return self._request(
            "POST", self._attempt_path(claim) + "/reconciliation-credential", json={}
        )

    def issue_ticket(self, claim):
        return self._request(
            "POST", self._attempt_path(claim) + "/media-ticket", json={"ttl_seconds": 3900}
        )

    def revoke_ticket(self, attempt, ticket):
        return self._request(
            "DELETE", "/attempts/" + quote(attempt, safe="") + "/media-tickets/" + str(ticket)
        )

    def post_consent(self, claim):
        try:
            return self._request("GET", self._claim_path(claim) + "/post-consent")
        except WorkerAPIError as exc:
            if exc.status == 404:
                return None
            raise

    def close(self):
        self.http.close()


def _send_pending(client, outbox, claim, pending):
    response = client.report_attempt(claim, **pending)
    terminal = response.get("state") in {"published", "failed", "withdrawn"}
    outbox.reported(claim["attempt_id"], terminal)
    if terminal:
        MediaDelivery(client, outbox).revoke(claim["attempt_id"])
    return terminal


def _save_report(client, outbox, claim, result, *, platform, confirmation=None):
    from webapp.publications.deliveries import _provider_result

    try:
        result = _provider_result(result, platform)
    except Exception:
        result, confirmation = outcome(code="status_unavailable"), None
    pending = outbox.queue_report(claim["attempt_id"], result, confirmation)
    _send_pending(client, outbox, claim, pending)
    return result


def _recover(client, outbox, adapters, entry):
    claim, snapshot = entry["claim"], entry["snapshot"]
    if entry["pending"] and _send_pending(client, outbox, claim, entry["pending"]):
        return {"state": "reported"}
    status = client.get_claim(claim)
    if status["state"] in {"published", "failed", "withdrawn", "cancelled", "expired"}:
        outbox.finish_local(claim["attempt_id"])
        MediaDelivery(client, outbox).revoke(claim["attempt_id"])
        return {"state": status["state"]}
    if status["state"] not in {"attempt_started", "uncertain"}:
        # Claim reservado sin ACK local: no hay autorización de POST recuperable.
        outbox.finish_local(claim["attempt_id"])
        return {"state": "held", "reason": "start_not_confirmed"}
    platform = snapshot["connection"]["platform"]
    adapter = adapters[platform].bind(outbox.journal(claim["attempt_id"]))
    envelope = client.reconciliation_credential(claim)
    if envelope.get("purpose") != "reconcile_only" or envelope.get("post_permitted") is not False:
        return {"state": "held", "reason": "recovery_credential_invalid"}
    connection = snapshot["connection"] | {"credential": envelope["credential"]}
    prior = status.get("result") or entry["result"] or outcome()
    result = adapter.reconcile(connection, prior)
    confirmation = None
    proof = getattr(adapter, "proof", None)
    if result["state"] in {"published", "failed"}:
        if not proof or proof.get("remote_id") != result.get("remote_id"):
            result = outcome(remote_id=prior.get("remote_id"), code="status_unavailable")
        else:
            confirmation = {
                "confirmed": True,
                "attempt_id": claim["attempt_id"],
                "normalized_destination": status["normalized_destination"],
                "remote_id": proof["remote_id"],
                "receipt": {"sha256": proof["sha256"], "operation": proof["operation"]},
            }
    saved = _save_report(
        client, outbox, claim, result, platform=platform, confirmation=confirmation
    )
    if getattr(adapter, "processing_complete", False):
        MediaDelivery(client, outbox).revoke(claim["attempt_id"])
    return saved


def _prepare(client, claim, now):
    status = client.get_claim(claim)
    snapshot = status["snapshot"]
    if (
        snapshot["tenant_id"] != client.tenant_id
        or snapshot["connection"]["tenant_id"] != client.tenant_id
    ):
        raise ValueError("tenant_mismatch")
    if (
        status["state"] != "reserved"
        or canonical_hash(snapshot) != claim["contract_hash"]
        or status["contract_hash"] != claim["contract_hash"]
    ):
        raise ValueError("claim_changed")
    if min(claim["lease_until"], snapshot["expires_at_utc"]) <= now:
        raise ValueError("claim_expired")
    raw = client.original(claim)
    if (
        len(raw) != snapshot["media"]["byte_size"]
        or hashlib.sha256(raw).hexdigest() != snapshot["media"]["sha256"]
    ):
        raise ValueError("original_mismatch")
    variant = snapshot | {"content": raw}
    if snapshot["connection"]["platform"] == "tiktok":
        variant["post_consent"] = PostConsent.from_server(
            client.post_consent(claim),
            tenant_id=client.tenant_id,
            revision_id=status["revision_id"],
            contract_hash=claim["contract_hash"],
            destination=status["normalized_destination"],
            media_sha256=snapshot["media"]["sha256"],
            now=now,
        )
    return snapshot, variant


def _dispatch(client, outbox, adapters, claim, clock):
    snapshot, variant = _prepare(client, claim, clock())
    if not outbox.reserve(claim, snapshot):
        return {"state": "held", "reason": "already_recorded"}
    attempt, platform = claim["attempt_id"], snapshot["connection"]["platform"]
    adapter = adapters[platform].bind(outbox.journal(attempt))
    connection = snapshot["connection"] | {"credential": client.credential(claim)}
    checked = adapter.preflight(connection, variant, clock())
    if checked["state"] != "verified":
        client.hold_claim(claim, checked["state"])
        outbox.finish_local(attempt)
        return {"state": "held", "reason": checked["state"]}
    if not outbox.stage(attempt, "reserved", "start_requested"):
        return {"state": "held", "reason": "start_not_confirmed"}
    started = client.start_attempt(claim)
    if (
        started.get("confirmed") is not True
        or started.get("post_permitted") is not True
        or started.get("attempt_id") != attempt
    ):
        return {"state": "held", "reason": "start_not_confirmed"}
    if not outbox.stage(attempt, "start_requested", "start_confirmed"):
        return {"state": "held", "reason": "outbox_conflict"}
    try:
        if adapter.needs_delivery:
            ticket = MediaDelivery(client, outbox).issue(
                claim,
                snapshot["media"]["sha256"],
                now=clock,
                minimum_seconds=adapter.minimum_delivery_seconds,
            )
            variant["delivery_url"] = ticket["url"]
        if not outbox.stage(attempt, "start_confirmed", "dispatching"):
            return {"state": "held", "reason": "outbox_conflict"}
        result = adapter.publish(connection, variant, attempt)
    except Exception:
        result = outcome(code="network_timeout")
    saved = _save_report(client, outbox, claim, result, platform=platform)
    if getattr(adapter, "processing_complete", False):
        MediaDelivery(client, outbox).revoke(attempt)
    return saved


def run_once(client, outbox, adapters, now) -> dict:
    """Un barrido acotado; recuperar primero y aislar cada destino fallido."""
    if client.tenant_id != outbox.tenant_id:
        raise ValueError("outbox_tenant_mismatch")
    clock = now if callable(now) else lambda: now
    results = []
    with outbox.exclusive() as acquired:
        if not acquired:
            return {"state": "busy", "results": []}
        MediaDelivery(client, outbox).expire(clock())
        for entry in outbox.active():
            try:
                results.append(_recover(client, outbox, adapters, entry))
            except Exception:
                results.append({"state": "held", "reason": "recovery_unavailable"})
        for _ in range(100):
            try:
                claim = client.claim_due()
            except Exception:
                results.append({"state": "held", "reason": "authority_unavailable"})
                break
            if claim is None:
                break
            try:
                results.append(_dispatch(client, outbox, adapters, claim, clock))
            except Exception:
                with suppress(Exception):
                    client.hold_claim(claim, "unknown")
                results.append({"state": "held", "reason": "authority_unavailable"})
    return {"state": "idle" if not results else "completed_sweep", "results": results}
