"""Narrow Instagram/JPEG closure qualified by original worker and current owner.

Digests preserve integrity of the operator's evidence; they do not prove that
an outbox or process exclusion was inspected. No ticket, credential, provider
request, synthetic confirmation, or publication timestamp is produced here.
"""

from __future__ import annotations

import json
import re

from webapp import db

from .contracts import (
    Conflict,
    InvalidInput,
    NotFound,
    canonical_hash,
    canonical_json,
    positive_integer,
)
from .deliveries import DBUrl, _snapshot, bound_claim, require_worker
from .ledger import append_event_in_transaction
from .policies import lock_tenant, require_owner

MANIFEST_FIELDS = {
    "schema_version",
    "tenant_id",
    "attempt_id",
    "claim_id",
    "delivery_id",
    "contract_hash",
    "media_sha256",
    "claim_sha256",
    "platform",
    "media_mime",
    "local_stage",
    "phase_count",
    "local_ticket_count",
    "started_confirmed",
    "done",
}
REMOTE_EVIDENCE = {
    "remote_id",
    "permalink",
    "receipt_sha256",
    "receipt",
    "confirmation",
    "published_at",
    "published_at_utc",
    "published_at_source",
    "first_published_report_at",
    "processing_kind",
    "processing_id",
    "http_status",
}
FAILED_RESULT = {
    "state": "failed",
    "remote_id": None,
    "permalink": None,
    "evidence": {"error_code": "failed_before_dispatch"},
}


def _sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise InvalidInput("invalid_pre_dispatch_sha256")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch("[A-Za-z0-9_.:-]{1,120}", value) is None:
        raise InvalidInput("invalid_pre_dispatch_event_key")
    return value


def validate_manifest(value: dict, digest: str) -> dict:
    if not isinstance(value, dict) or set(value) != MANIFEST_FIELDS:
        raise InvalidInput("invalid_pre_dispatch_manifest")
    expected = {
        "schema_version": 1,
        "platform": "instagram",
        "media_mime": "image/jpeg",
        "local_stage": "quarantined_before_dispatch",
        "phase_count": 0,
        "local_ticket_count": 0,
        "started_confirmed": True,
        "done": False,
    }
    if any(type(value.get(k)) is not type(v) or value[k] != v for k, v in expected.items()):
        raise InvalidInput("invalid_pre_dispatch_manifest")
    for name in ("tenant_id", "delivery_id"):
        positive_integer(value[name], "invalid_pre_dispatch_binding")
    for name in ("attempt_id", "claim_id"):
        _key(value[name])
    for name in ("contract_hash", "media_sha256", "claim_sha256"):
        _sha(value[name])
    if canonical_hash(value) != _sha(digest):
        raise Conflict("pre_dispatch_manifest_digest_mismatch")
    return dict(value)


def validate_qualification(value: dict) -> dict:
    fields = {
        "kind",
        "schema_version",
        "code_sha256",
        "outbox_sha256",
        "historical_config_sha256",
        "process_exclusion_sha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("kind") != "operator_verified_original_worker"
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
    ):
        raise InvalidInput("invalid_pre_dispatch_qualification")
    for name in fields - {"kind", "schema_version"}:
        _sha(value[name])
    return dict(value)


def _binding(
    con: db.DualConnection, principal: dict, attempt_id: str, now: int
) -> tuple[dict, dict, dict]:
    require_worker(con, principal, now)
    claim = con.execute(
        "SELECT * FROM publication_claims WHERE tenant_id=? AND attempt_id=? AND worker_grant_id=?",
        (principal["tenant_id"], attempt_id, principal["grant_id"]),
    ).fetchone()
    if claim is None:
        raise NotFound()
    row = bound_claim(con, principal, claim["claim_id"], now, active=False)
    if any(
        claim[name] != row[target]
        for name, target in {
            "claim_id": "claim_id",
            "delivery_id": "id",
            "attempt_id": "attempt_id",
            "worker_grant_id": "worker_grant_id",
            "contract_hash": "contract_hash",
        }.items()
    ):
        raise Conflict("pre_dispatch_original_binding_mismatch")
    snapshot = _snapshot(con, row)
    if (
        row["started_at"] is None
        or snapshot["tenant_id"] != row["tenant_id"]
        or snapshot["connection"]["tenant_id"] != row["tenant_id"]
        or snapshot["connection"]["platform"] != "instagram"
        or snapshot["media"]["kind"] != "gallery_image"
        or snapshot["media"]["mime"] != "image/jpeg"
        or snapshot["media"]["sha256"] != row["media_sha256"]
        or snapshot["destination"] != row["normalized_destination"]
    ):
        raise Conflict("pre_dispatch_instagram_jpeg_required")
    return row, dict(claim), snapshot


def _manifest_binding(manifest: dict, row: dict, claim: dict) -> None:
    original = {
        name: claim[name]
        for name in ("delivery_id", "attempt_id", "claim_id", "contract_hash", "lease_until")
    }
    expected = {
        "tenant_id": row["tenant_id"],
        "attempt_id": row["attempt_id"],
        "claim_id": row["claim_id"],
        "delivery_id": row["id"],
        "contract_hash": row["contract_hash"],
        "media_sha256": row["media_sha256"],
        "claim_sha256": canonical_hash(original),
    }
    if any(manifest[k] != v for k, v in expected.items()):
        raise Conflict("pre_dispatch_original_binding_mismatch")


def _remote_evidenced(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (
                key in REMOTE_EVIDENCE
                and child is not None
                and child != ""
                and child != {}
                and child != []
            )
            or _remote_evidenced(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_remote_evidenced(child) for child in value)
    return False


def _no_dispatch_history(con: db.DualConnection, row: dict) -> None:
    if row["state"] != "uncertain":
        raise Conflict("pre_dispatch_uncertain_required")
    tickets = con.execute(
        "SELECT COUNT(*) AS count FROM publication_media_tickets WHERE tenant_id=? AND attempt_id=?",
        (row["tenant_id"], row["attempt_id"]),
    ).fetchone()
    if tickets is None or tickets["count"]:
        raise Conflict("pre_dispatch_historical_ticket_exists")
    values = [json.loads(row["result_json"])] if row["result_json"] else []
    values.extend(
        json.loads(event["payload_json"])
        for event in con.execute(
            "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? ORDER BY id",
            (row["tenant_id"], row["attempt_id"]),
        ).fetchall()
    )
    if any(_remote_evidenced(value) for value in values):
        raise Conflict("pre_dispatch_remote_evidence_exists")


def _prior(
    con: db.DualConnection, tenant: int, attempt: str, key: str, digest: str, kind: str
) -> dict | None:
    row = con.execute(
        "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key=?",
        (tenant, attempt, key),
    ).fetchone()
    if row is not None:
        payload = json.loads(row["payload_json"])
        if row["kind"] != kind or payload.get("request_hash") != digest:
            raise Conflict("event_idempotency_conflict")
        return dict(row)
    return None


def _event(con: db.DualConnection, row: dict, key: str, kind: str, payload: dict, now: int) -> dict:
    return append_event_in_transaction(
        con,
        row["tenant_id"],
        row["attempt_id"],
        key,
        kind,
        {
            "delivery_id": row["id"],
            "revision_id": row["revision_id"],
            "normalized_destination": row["normalized_destination"],
            "image_sha256": row["media_sha256"],
            "contract_hash": row["contract_hash"],
            "occurred_at": now,
            **payload,
        },
    )


def _attestation_receipt(event: dict) -> dict:
    payload = json.loads(event["payload_json"])
    return {
        "attestation_id": event["id"],
        "attempt_id": event["attempt_id"],
        "tenant_id": event["tenant_id"],
        "manifest_sha256": payload["manifest_sha256"],
        "worker_grant_id": payload["worker_grant_id"],
        "post_permitted": False,
        "state": "attested_before_dispatch",
        "attested_at": payload["occurred_at"],
    }


def attest_before_dispatch(
    db_url: DBUrl, principal: dict, attempt_id: str, body: dict, now: int
) -> dict:
    if not isinstance(body, dict) or set(body) != {"event_key", "manifest", "manifest_sha256"}:
        raise InvalidInput("invalid_pre_dispatch_attestation")
    positive_integer(now, "invalid_time", allow_zero=True)
    manifest = validate_manifest(body["manifest"], body["manifest_sha256"])
    key = "pre_dispatch:attest:" + _key(body["event_key"])
    semantic = body | {"worker_grant_id": principal.get("grant_id")}
    digest = canonical_hash(semantic)
    with db.connect(db_url) as con:
        lock_tenant(con, principal["tenant_id"])
        row, claim, _ = _binding(con, principal, attempt_id, now)
        _manifest_binding(manifest, row, claim)
        old = _prior(con, row["tenant_id"], attempt_id, key, digest, "pre_dispatch_attested")
        if old:
            return _attestation_receipt(old)
        _no_dispatch_history(con, row)
        event = _event(
            con,
            row,
            key,
            "pre_dispatch_attested",
            {
                "request_hash": digest,
                "worker_grant_id": principal["grant_id"],
                "manifest": manifest,
                "manifest_sha256": body["manifest_sha256"],
            },
            now,
        )
        return _attestation_receipt(event)


def _owner_principal(con: db.DualConnection, row: dict) -> dict:
    grant = con.execute(
        "SELECT * FROM publication_grants WHERE tenant_id=? AND id=?",
        (row["tenant_id"], row["worker_grant_id"]),
    ).fetchone()
    if grant is None:
        raise NotFound()
    return {
        "tenant_id": row["tenant_id"],
        "grant_id": grant["id"],
        "role": grant["role"],
        "subject": grant["subject"],
        "policy_version": grant["policy_version"],
    }


def _closure_attestation(con: db.DualConnection, row: dict, body: dict, claim: dict) -> dict:
    attestation = con.execute(
        "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id=? AND id=? AND kind='pre_dispatch_attested'",
        (row["tenant_id"], row["attempt_id"], body["attestation_id"]),
    ).fetchone()
    if attestation is None:
        raise NotFound("pre_dispatch_attestation_not_found")
    payload = json.loads(attestation["payload_json"])
    if (
        payload["worker_grant_id"] != row["worker_grant_id"]
        or payload["manifest_sha256"] != body["manifest_sha256"]
    ):
        raise Conflict("pre_dispatch_attestation_mismatch")
    manifest = validate_manifest(payload["manifest"], body["manifest_sha256"])
    _manifest_binding(manifest, row, claim)
    return dict(attestation)


def close_before_dispatch(
    db_url: DBUrl, tenant_id: int, owner_id: int, attempt_id: str, body: dict, now: int
) -> dict:
    if not isinstance(body, dict) or set(body) != {
        "event_key",
        "attestation_id",
        "manifest_sha256",
        "qualification",
        "expected_result_hash",
    }:
        raise InvalidInput("invalid_pre_dispatch_closure")
    positive_integer(body["attestation_id"], "invalid_pre_dispatch_attestation_id")
    positive_integer(now, "invalid_time", allow_zero=True)
    validate_qualification(body["qualification"])
    _sha(body["manifest_sha256"])
    _sha(body["expected_result_hash"])
    key = "pre_dispatch:close:" + _key(body["event_key"])
    digest = canonical_hash(body | {"owner_id": owner_id})
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=?",
            (tenant_id, attempt_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        row, claim, _ = _binding(con, _owner_principal(con, row), attempt_id, now)
        _closure_attestation(con, row, body, claim)
        old = _prior(con, tenant_id, attempt_id, key, digest, "failed_before_dispatch")
        if old:
            persisted: dict = json.loads(old["payload_json"])["closure_response"]
            return persisted
        _no_dispatch_history(con, row)
        current = json.loads(row["result_json"]) if row["result_json"] else {}
        if canonical_hash(current) != body["expected_result_hash"]:
            raise Conflict("pre_dispatch_result_changed")
        answer = {
            "attempt_id": attempt_id,
            "delivery_id": row["id"],
            "state": "failed",
            "reason": "failed_before_dispatch",
            "remote_id": None,
            "permalink": None,
            "post_permitted": False,
            "attestation_id": body["attestation_id"],
            "manifest_sha256": body["manifest_sha256"],
            "closed_at": now,
            "result_hash": canonical_hash(FAILED_RESULT),
        }
        if (
            con.execute(
                "UPDATE publication_deliveries SET state='failed',result_json=? WHERE tenant_id=? AND id=? AND attempt_id=? AND claim_id=? AND worker_grant_id=? AND contract_hash=? AND state='uncertain'",
                (
                    canonical_json(FAILED_RESULT),
                    tenant_id,
                    row["id"],
                    attempt_id,
                    row["claim_id"],
                    row["worker_grant_id"],
                    row["contract_hash"],
                ),
            ).rowcount
            != 1
        ):
            raise Conflict("pre_dispatch_close_cas_failed")
        _event(
            con,
            row,
            key,
            "failed_before_dispatch",
            {
                "request_hash": digest,
                "owner_id": owner_id,
                "worker_grant_id": row["worker_grant_id"],
                "attestation_id": body["attestation_id"],
                "manifest_sha256": body["manifest_sha256"],
                "qualification": body["qualification"],
                "previous_result_hash": body["expected_result_hash"],
                "reason": "failed_before_dispatch",
                "result": FAILED_RESULT,
                "closure_response": answer,
            },
            now,
        )
        return answer
