"""Calendario durable. Una respuesta start confirma un único POST, nunca un retry."""

from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidTag

from webapp import db
from webapp.storage_backend.base import StorageBackend

from .campaigns import _media
from .connections import REQUIRED_SCOPES, _connection, connection_metadata
from .contracts import (
    Claim,
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    ProviderResult,
    canonical_hash,
    canonical_json,
    normalize_schedule,
    positive_integer,
)
from .decisions import publication_eligibility_in_transaction
from .ledger import (
    _effective_destination,
    append_event_in_transaction,
    history_ready_in_transaction,
    seen_media_in_transaction,
)
from .policies import lock_tenant, require_active_policy, require_owner
from .vault import unseal

DBUrl = str | Path | None
LEASE_SECONDS = 300
_PRESTART = ("scheduled", "held", "reserved")
_TERMINAL = ("published", "failed", "withdrawn")
PRESTART_HOLD_REASONS = frozenset(
    {
        "unknown",
        "requires_auth",
        "requires_provider_review",
        "requires_post_consent",
        "blocked_by_budget",
        "unsupported_media",
        "rate_limited",
    }
)


def _worker_hold_event(con: db.DualConnection, row: dict) -> dict | None:
    return con.execute(
        "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key='worker:prestart_hold' AND kind='held'",
        (row["tenant_id"], row["attempt_id"]),
    ).fetchone()


def hold_claim(
    db_url: DBUrl, principal: dict, claim_id: str, contract_hash: str, reason: str, now: int
) -> dict:
    """Retención durable antes de POST; nunca convierte un claim en autorización."""
    if not isinstance(reason, str) or reason not in PRESTART_HOLD_REASONS:
        raise InvalidInput("invalid_prestart_reason")
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row = bound_claim(con, principal, claim_id, now, active=False)
        if row["contract_hash"] != contract_hash or row["started_at"] is not None:
            raise Conflict("prestart_hold_conflict")
        old = _worker_hold_event(con, row)
        if old is not None:
            if json.loads(old["payload_json"])["reasons"] != [reason]:
                raise Conflict("event_idempotency_conflict")
            return _public(row)
        bound_claim(con, principal, claim_id, now, active=True)
        changed = con.execute(
            "UPDATE publication_deliveries SET state='held',lease_until=NULL,hold_reasons_json=? WHERE tenant_id=? AND id=? AND claim_id=? AND worker_grant_id=? AND contract_hash=? AND state='reserved' AND started_at IS NULL AND lease_until>? AND expires_at>?",
            (
                json.dumps([reason]),
                row["tenant_id"],
                row["id"],
                claim_id,
                principal["grant_id"],
                contract_hash,
                now,
                now,
            ),
        ).rowcount
        if changed != 1:
            raise Conflict("prestart_hold_conflict")
        _event(
            con,
            row,
            row["attempt_id"],
            "worker:prestart_hold",
            "held",
            now,
            worker_grant_id=principal["grant_id"],
            reasons=[reason],
        )
        return _public(_delivery(con, row["tenant_id"], row["id"]))


def _tenant(principal: dict) -> int:
    if not isinstance(principal, dict) or principal.get("role") != "worker":
        raise Forbidden()
    return positive_integer(principal.get("tenant_id"), "invalid_tenant")


def require_worker(con: db.DualConnection, principal: dict, now: int) -> dict:
    tenant = _tenant(principal)
    positive_integer(now, "invalid_time", allow_zero=True)
    row = con.execute(
        "SELECT * FROM publication_grants WHERE tenant_id=? AND id=?",
        (tenant, principal.get("grant_id")),
    ).fetchone()
    if (
        not row
        or row["role"] != "worker"
        or row["revoked_at"] is not None
        or row["subject"] != principal.get("subject")
        or row["policy_version"] != principal.get("policy_version")
        or not row["created_at"] <= now < row["expires_at"]
    ):
        raise Forbidden()
    require_owner(con, tenant, row["owner_id"])
    return require_active_policy(con, tenant, row["policy_version"], now)


def _delivery(con: db.DualConnection, tenant: int, delivery_id: int) -> dict:
    row = con.execute(
        "SELECT * FROM publication_deliveries WHERE tenant_id=? AND id=?", (tenant, delivery_id)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def _snapshot(con: db.DualConnection, row: dict) -> dict:
    revision = con.execute(
        "SELECT frozen_json,contract_hash FROM publication_revisions WHERE tenant_id=? AND id=?",
        (row["tenant_id"], row["revision_id"]),
    ).fetchone()
    if revision is None:
        raise NotFound()
    snapshot: dict = json.loads(revision["frozen_json"])
    if (
        canonical_hash(snapshot) != row["contract_hash"]
        or revision["contract_hash"] != row["contract_hash"]
    ):
        raise Conflict("contract_changed")
    return snapshot


def _public(row: dict) -> dict:
    return {
        k: row[k]
        for k in (
            "id",
            "revision_id",
            "contract_hash",
            "normalized_destination",
            "media_sha256",
            "due_at",
            "expires_at",
            "state",
            "started_at",
            "attempt_id",
            "lease_until",
        )
    } | {
        "hold_reasons": json.loads(row["hold_reasons_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
    }


def _event(
    con: db.DualConnection, row: dict, attempt: str, key: str, kind: str, now: int, **extra: Any
) -> dict:
    return append_event_in_transaction(
        con,
        row["tenant_id"],
        attempt,
        key,
        kind,
        {
            "delivery_id": row["id"],
            "revision_id": row["revision_id"],
            "normalized_destination": row["normalized_destination"],
            "image_sha256": row["media_sha256"],
            "contract_hash": row["contract_hash"],
            "occurred_at": now,
            **extra,
        },
    )


def _date(now: int, zone: str) -> str:
    return datetime.fromtimestamp(now, UTC).astimezone(ZoneInfo(zone)).date().isoformat()


def _historical_time(item: dict) -> int | None:
    # Campos explícitos del importador revisado. Nunca created_at (incorporación).
    candidates = [item, item.get("original", {}), item.get("receipt", {})]
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        for key in ("remote_created_at", "published_at", "completed_at"):
            value = obj.get(key)
            if value is not None:
                try:
                    return normalize_schedule(value)
                except InvalidInput:
                    return None
    return None


def _verified_history_time(
    con: db.DualConnection, tenant: int, row: dict, destination: str
) -> int | None:
    """Última prueba del importador confiable. No es una ruta para roles públicos."""
    event = con.execute(
        "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='reconciled' ORDER BY id DESC LIMIT 1",
        (tenant, row["attempt_id"]),
    ).fetchone()
    source = con.execute(
        "SELECT source_sha256 FROM publication_history_sources WHERE tenant_id=? AND source_id=?",
        (tenant, row["source_id"]),
    ).fetchone()
    if event is None or source is None:
        return None
    payload = json.loads(event["payload_json"])
    receipt = payload.get("receipt")
    if (
        payload.get("confirmed") is not True
        or payload.get("state") not in ("published", "withdrawn")
        or not isinstance(receipt, dict)
    ):
        return None
    binding = {
        "source_id": row["source_id"],
        "source_delivery_id": row["source_delivery_id"],
        "item_hash": row["item_hash"],
        "source_sha256": source["source_sha256"],
        "normalized_destination": destination,
        "published_at_source": "provider",
    }
    if any(receipt.get(k) != v for k, v in binding.items()) or not re.fullmatch(
        r"[0-9a-f]{64}", str(receipt.get("receipt_sha256", ""))
    ):
        return None
    original = json.loads(row["item_json"]).get("receipt", {})
    ids = {
        str(original[key])
        for key in (
            "remote_id",
            "post_id",
            "photo_id",
            "media_id",
            "remote_post_id",
            "remote_photo_id",
            "remote_media_id",
        )
        if original.get(key) is not None
    }
    if not isinstance(receipt.get("remote_id"), str) or receipt["remote_id"] not in ids:
        return None
    published_at = receipt.get("published_at")
    if not isinstance(published_at, str):
        return None
    try:
        return normalize_schedule(published_at)
    except InvalidInput:
        return None


def _history_limits(
    con: db.DualConnection, tenant: int, destination: str, zone: str, day: str
) -> tuple[int, list[int], list[str]]:
    count, times, reasons = 0, [], []
    historical = con.execute(
        "SELECT * FROM publication_history WHERE tenant_id=?", (tenant,)
    ).fetchall()
    for old in historical:
        if _effective_destination(con, tenant, old) != destination or old["state"] in (
            "held",
            "cancelled",
        ):
            continue
        stamp = _historical_time(json.loads(old["item_json"]))
        if stamp is None:
            stamp = _verified_history_time(con, tenant, old, destination)
        if stamp is None:
            reasons.append("history_time_unknown")
        else:
            count += _date(stamp, zone) == day
            times.append(stamp)
    return count, times, reasons


def _attempt_times(row: dict, zone: str) -> tuple[list[int], bool]:
    stamps = [row["started_at"]]
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    remote = result.get("published_at_utc")
    if remote is not None:
        stamps.append(remote)
    first_report = result.get("first_published_report_at")
    ambiguous = (
        remote is None
        and first_report is not None
        and _date(first_report, zone) != _date(row["started_at"], zone)
    )
    return stamps, ambiguous


def _destination_usage(
    con: db.DualConnection,
    tenant: int,
    destination: str,
    zone: str,
    day: str,
    now: int,
    exclude_delivery_id: int = -1,
) -> tuple[int, list[int], list[str]]:
    """Lectura común del consumo real; el llamador conserva el lock tenant."""
    count, times, reasons = _history_limits(con, tenant, destination, zone, day)
    others = con.execute(
        "SELECT * FROM publication_deliveries WHERE tenant_id=? AND normalized_destination=? AND id<>?",
        (tenant, destination, exclude_delivery_id),
    ).fetchall()
    for other in others:
        if other["state"] in ("attempt_started", "uncertain"):
            reasons.append("destination_attempt_unresolved")
        if other["started_at"] is not None:
            stamps, unverified = _attempt_times(other, zone)
            count += any(_date(stamp, zone) == day for stamp in stamps)
            times.extend(stamps)
            if unverified:
                reasons.append("publication_day_unverified")
        elif other["state"] == "reserved" and other["lease_until"] > now:
            # Una reserva viva consume capacidad del día efectivo de inicio, incluso tras medianoche.
            count += 1
            claim = con.execute(
                "SELECT claimed_at FROM publication_claims WHERE tenant_id=? AND claim_id=?",
                (tenant, other["claim_id"]),
            ).fetchone()
            if claim is None:
                raise Conflict("claim_missing")
            times.append(claim["claimed_at"])
    return count, times, reasons


def _limits(con: db.DualConnection, row: dict, snapshot: dict, now: int) -> list[str]:
    tenant, destination = row["tenant_id"], row["normalized_destination"]
    policy = con.execute(
        "SELECT payload_json FROM publication_policies WHERE tenant_id=? AND version=?",
        (tenant, snapshot["policy_version"]),
    ).fetchone()
    if policy is None:
        raise Conflict("policy_required")
    rules = json.loads(policy["payload_json"])
    zone, day = rules["timezone"], _date(now, rules["timezone"])
    count, times, reasons = _destination_usage(
        con, tenant, destination, zone, day, now, row.get("id", -1)
    )
    if count >= rules["max_daily_per_destination"]:
        reasons.append("daily_quota_reached")
    if any(now - stamp < rules["frequency_minutes"] * 60 for stamp in times):
        reasons.append("frequency_limit")
    return reasons


def _reasons(con: db.DualConnection, row: dict, now: int) -> tuple[list[str], dict]:
    eligibility = publication_eligibility_in_transaction(
        con, row["tenant_id"], row["revision_id"], now
    )
    s = _snapshot(con, row)
    reasons = list(eligibility["reasons"])
    if not history_ready_in_transaction(con, row["tenant_id"], row["normalized_destination"]):
        reasons.append("history_not_ready")
    if seen_media_in_transaction(
        con, row["tenant_id"], row["normalized_destination"], row["media_sha256"]
    ):
        reasons.append("media_already_attempted")
    pending_same = con.execute(
        "SELECT id FROM publication_deliveries WHERE tenant_id=? AND normalized_destination=? AND media_sha256=? AND id<>? AND (started_at IS NOT NULL OR (state='reserved' AND lease_until>?)) LIMIT 1",
        (
            row["tenant_id"],
            row["normalized_destination"],
            row["media_sha256"],
            row.get("id", -1),
            now,
        ),
    ).fetchone()
    if pending_same:
        reasons.append("media_already_reserved")
    reasons.extend(_limits(con, row, s, now))
    return list(dict.fromkeys(reasons)), eligibility


def _retain(con: db.DualConnection, row: dict, now: int, reasons: list[str]) -> None:
    state = "expired" if now >= row["expires_at"] else "held" if reasons else "scheduled"
    raw = json.dumps(reasons)
    if row["state"] == state and row["hold_reasons_json"] == raw:
        return
    con.execute(
        "UPDATE publication_deliveries SET state=?,hold_reasons_json=? WHERE tenant_id=? AND id=? AND started_at IS NULL",
        (state, raw, row["tenant_id"], row["id"]),
    )
    _event(con, row, f"delivery:{row['id']}", secrets.token_hex(16), state, now, reasons=reasons)


def schedule_revision(db_url: DBUrl, tenant_id: int, revision_id: int, now: int) -> dict:
    positive_integer(now, "invalid_time", allow_zero=True)
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        revision = con.execute(
            "SELECT * FROM publication_revisions WHERE tenant_id=? AND id=?",
            (tenant_id, revision_id),
        ).fetchone()
        if revision is None:
            raise NotFound()
        s = json.loads(revision["frozen_json"])
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND revision_id=?",
            (tenant_id, revision_id),
        ).fetchone()
        if row is not None and (row["state"] not in _PRESTART or row["state"] == "reserved"):
            return _public(row)
        if row is not None and _worker_hold_event(con, row) is not None:
            return _public(row)
        if row is None:
            # No crea autorización: estado inicial held hasta revalidación dentro del mismo lock.
            con.execute(
                "INSERT INTO publication_deliveries(tenant_id,revision_id,contract_hash,normalized_destination,media_sha256,due_at,expires_at,state,created_at) VALUES (?,?,?,?,?,?,?,'held',?)",
                (
                    tenant_id,
                    revision_id,
                    revision["contract_hash"],
                    s["destination"],
                    s["media"]["sha256"],
                    s["scheduled_at_utc"],
                    s["expires_at_utc"],
                    now,
                ),
            )
            row = _delivery(
                con, tenant_id, db.get_last_insert_id(db_url, con, "publication_deliveries")
            )
        reasons, eligibility = _reasons(con, row, now)
        con.execute(
            "UPDATE publication_deliveries SET decision_id=? WHERE tenant_id=? AND id=?",
            (eligibility["decision_id"], tenant_id, row["id"]),
        )
        _retain(con, row, now, reasons)
        return _public(_delivery(con, tenant_id, row["id"]))


def claim_due(db_url: DBUrl, principal: dict, now: int) -> Claim | None:
    with db.connect(db_url) as con:
        tenant = _tenant(principal)
        lock_tenant(con, tenant)
        require_worker(con, principal, now)
        rows = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND state IN ('scheduled','held','reserved') AND due_at<=? AND started_at IS NULL ORDER BY due_at,id",
            (tenant, now),
        ).fetchall()
        for row in rows:
            if _worker_hold_event(con, row) is not None:
                continue
            if row["state"] == "reserved" and row["lease_until"] > now and now < row["expires_at"]:
                continue
            reasons, eligibility = _reasons(con, row, now)
            if now >= row["expires_at"] or reasons:
                _retain(con, row, now, reasons)
                continue
            claim, attempt = secrets.token_urlsafe(32), "attempt:" + secrets.token_hex(24)
            lease = min(now + LEASE_SECONDS, row["expires_at"])
            changed = con.execute(
                "UPDATE publication_deliveries SET state='reserved',claim_id=?,worker_grant_id=?,attempt_id=?,lease_until=?,hold_reasons_json='[]',decision_id=? WHERE tenant_id=? AND id=? AND started_at IS NULL AND state IN ('scheduled','held','reserved') AND (state<>'reserved' OR lease_until<=?)",
                (
                    claim,
                    principal["grant_id"],
                    attempt,
                    lease,
                    eligibility["decision_id"],
                    tenant,
                    row["id"],
                    now,
                ),
            ).rowcount
            if changed != 1:
                continue
            con.execute(
                "INSERT INTO publication_claims(tenant_id,claim_id,delivery_id,attempt_id,worker_grant_id,contract_hash,claimed_at,lease_until) VALUES (?,?,?,?,?,?,?,?)",
                (
                    tenant,
                    claim,
                    row["id"],
                    attempt,
                    principal["grant_id"],
                    row["contract_hash"],
                    now,
                    lease,
                ),
            )
            _event(
                con,
                row,
                attempt,
                "reserved",
                "reserved",
                now,
                worker_grant_id=principal["grant_id"],
            )
            return Claim(
                delivery_id=row["id"],
                attempt_id=attempt,
                claim_id=claim,
                contract_hash=row["contract_hash"],
                lease_until=lease,
            )
    return None


def bound_claim(
    con: db.DualConnection, principal: dict, claim_id: str, now: int, *, active: bool
) -> dict:
    require_worker(con, principal, now)
    claim = con.execute(
        "SELECT * FROM publication_claims WHERE tenant_id=? AND claim_id=? AND worker_grant_id=?",
        (principal["tenant_id"], claim_id, principal["grant_id"]),
    ).fetchone()
    if claim is None:
        raise NotFound()
    row = _delivery(con, principal["tenant_id"], claim["delivery_id"])
    if row["claim_id"] != claim_id or row["worker_grant_id"] != principal["grant_id"]:
        raise Conflict("claim_replaced")
    if active and (
        row["state"] not in ("reserved", "attempt_started")
        or now >= row["lease_until"]
        or now >= row["expires_at"]
    ):
        raise Conflict("claim_not_active")
    return row


def get_claim(db_url: DBUrl, principal: dict, claim_id: str, now: int) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row = bound_claim(con, principal, claim_id, now, active=False)
        return _public(row) | {
            "attempt_id": row["attempt_id"],
            "post_permitted": False,
            "snapshot": _snapshot(con, row),
        }


def start_attempt(
    db_url: DBUrl, principal: dict, claim_id: str, contract_hash: str, now: int
) -> dict:
    error = None
    result = None
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row = bound_claim(con, principal, claim_id, now, active=False)
        if row["started_at"] is not None:
            raise Conflict("attempt_already_started")
        if row["contract_hash"] != contract_hash:
            raise Conflict("contract_changed")
        if now >= row["expires_at"]:
            _retain(con, row, now, ["revision_expired"])
            error = "revision_expired"
        else:
            bound_claim(con, principal, claim_id, now, active=True)
            reasons, eligibility = _reasons(con, row, now)
            if row["normalized_destination"].startswith("tiktok:"):
                from .consent import claim_authority

                try:
                    consent = claim_authority(con, row, now)
                    if any(
                        consent[k] != row[k]
                        for k in ("contract_hash", "normalized_destination", "media_sha256")
                    ):
                        reasons.append("consent_binding_mismatch")
                except (Conflict, Forbidden, NotFound, InvalidInput):
                    reasons.append("needs_platform_consent")
            material = con.execute(
                "SELECT media_sha256 FROM publication_claim_materials WHERE tenant_id=? AND claim_id=?",
                (row["tenant_id"], claim_id),
            ).fetchone()
            if not material or material["media_sha256"] != row["media_sha256"]:
                reasons.append("original_verification_required")
            if reasons:
                _retain(con, row, now, reasons)
                error = "delivery_not_eligible"
            else:
                changed = con.execute(
                    "UPDATE publication_deliveries SET state='attempt_started',started_at=?,decision_id=? WHERE tenant_id=? AND id=? AND state='reserved' AND claim_id=? AND worker_grant_id=? AND contract_hash=? AND lease_until>? AND started_at IS NULL",
                    (
                        now,
                        eligibility["decision_id"],
                        row["tenant_id"],
                        row["id"],
                        claim_id,
                        principal["grant_id"],
                        contract_hash,
                        now,
                    ),
                ).rowcount
                if changed != 1:
                    raise Conflict("start_not_granted")
                _event(
                    con,
                    row,
                    row["attempt_id"],
                    "start",
                    "attempt_started",
                    now,
                    worker_grant_id=principal["grant_id"],
                )
                result = {
                    "attempt_id": row["attempt_id"],
                    "delivery_id": row["id"],
                    "state": "attempt_started",
                    "post_permitted": True,
                }
    if error:
        raise Conflict(error)
    assert result is not None
    return result


def _active_material(
    con: db.DualConnection, principal: dict, claim_id: str, now: int
) -> tuple[dict, dict]:
    row = bound_claim(con, principal, claim_id, now, active=True)
    eligibility = publication_eligibility_in_transaction(
        con, row["tenant_id"], row["revision_id"], now
    )
    if not eligibility["eligible"]:
        raise Conflict("delivery_not_eligible")
    return row, _snapshot(con, row)


def claim_original(
    db_url: DBUrl, storage: StorageBackend, principal: dict, claim_id: str, now: int
) -> tuple[bytes, str]:
    from .media_delivery import read_original

    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row, snapshot = _active_material(con, principal, claim_id, now)
        media = _media(con, row["tenant_id"], snapshot["media"]["kind"], snapshot["media"]["id"])
    content = read_original(storage, row["tenant_id"], snapshot["media"], media)
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        _active_material(con, principal, claim_id, now)
        con.execute(
            "INSERT INTO publication_claim_materials(tenant_id,claim_id,media_sha256,verified_at) VALUES (?,?,?,?) ON CONFLICT(tenant_id,claim_id) DO NOTHING",
            (row["tenant_id"], claim_id, row["media_sha256"], now),
        )
    return content, media["mime"]


def claim_credential(
    db_url: DBUrl, principal: dict, claim_id: str, now: int, *, key: bytes
) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row, snapshot = _active_material(con, principal, claim_id, now)
        return _credential(con, row["tenant_id"], snapshot["connection"]["id"], key)


def _credential(con: db.DualConnection, tenant: int, cid: int, key: bytes) -> dict:
    vault = con.execute(
        "SELECT envelope_json FROM publication_connection_vault WHERE tenant_id=? AND connection_id=?",
        (tenant, cid),
    ).fetchone()
    if vault is None:
        raise Conflict("vault_unavailable")
    try:
        credential: dict = json.loads(unseal(key, tenant, cid, json.loads(vault["envelope_json"])))
    except (InvalidTag, ValueError, TypeError) as exc:
        raise Conflict("vault_unavailable") from exc
    if not isinstance(credential, dict):
        raise Conflict("vault_unavailable")
    return credential


def _reconciliation_account(con: db.DualConnection, snapshot: dict, now: int) -> dict:
    frozen = snapshot["connection"]
    if frozen["platform"] == "x":
        raise Conflict("blocked_budget")
    account = connection_metadata(con, _connection(con, snapshot["tenant_id"], frozen["id"]))
    if any(account[k] != frozen[k] for k in ("platform", "api_mode", "remote_id")):
        raise Conflict("connection_changed")
    expiry_valid = (
        account["expiry_state"] == "non_expiring" and account["expires_at"] is None
    ) or (
        account["expiry_state"] == "known"
        and account["expires_at"] is not None
        and account["expires_at"] > now
    )
    required = REQUIRED_SCOPES.get((account["platform"], account["api_mode"]))
    if (
        account["status"] != "active"
        or account["verified_at"] is None
        or account["verified_at"] > now
        or account["scope_evidence"]
        not in ("remote_introspection", "token_exchange", "capability_probe")
        or not expiry_valid
        or required is None
        or not required.issubset(account["scopes"])
        or snapshot["project_id"] not in account["project_ids"]
    ):
        raise Conflict("connection_unavailable")
    return account


def reconciliation_credential(
    db_url: DBUrl, principal: dict, attempt_id: str, now: int, *, key: bytes
) -> dict:
    """Credencial privada para conciliar un efecto iniciado; no autoriza otro POST.

    El token del proveedor puede conservar scopes de escritura. El worker de
    confianza debe usarlo únicamente en adapter.reconcile, nunca en su outbox.
    """
    tenant = _tenant(principal)
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        policy = json.loads(require_worker(con, principal, now)["payload_json"])
        claim = con.execute(
            "SELECT claim_id FROM publication_claims WHERE tenant_id=? AND attempt_id=? AND worker_grant_id=?",
            (tenant, attempt_id, principal["grant_id"]),
        ).fetchone()
        if claim is None:
            raise NotFound()
        row = bound_claim(con, principal, claim["claim_id"], now, active=False)
        if row["state"] not in ("attempt_started", "uncertain") or row["started_at"] is None:
            raise Conflict("reconciliation_requires_started_attempt")
        snapshot = _snapshot(con, row)
        if (
            snapshot["project_id"] not in policy["project_ids"]
            or snapshot["brand_id"] not in policy["product_ids"]
            or snapshot["connection"]["id"] not in policy["connection_ids"]
        ):
            raise Forbidden()
        account = _reconciliation_account(con, snapshot, now)
        credential = _credential(con, tenant, account["id"], key)
        _event(
            con,
            row,
            attempt_id,
            secrets.token_hex(16),
            "reconciliation_credentials_resolved",
            now,
            worker_grant_id=principal["grant_id"],
            connection_id=account["id"],
            connection_version=account["version"],
            purpose="reconcile_only",
        )
        return {"purpose": "reconcile_only", "post_permitted": False, "credential": credential}


_EVIDENCE_ERRORS = (
    "network_timeout",
    "connection_error",
    "rate_limited",
    "authorization_failed",
    "provider_rejected",
    "processing_failed",
    "processing_pending",
    "status_unavailable",
)


def _safe_evidence(value: object, platform: str) -> dict:
    """Sólo comprobantes tipados: jamás texto de excepciones, URLs o JSON remoto."""
    allowed = {
        "receipt_sha256",
        "published_at",
        "published_at_source",
        "processing_kind",
        "processing_id",
        "http_status",
        "error_code",
    }
    if not isinstance(value, dict) or set(value) - allowed:
        raise InvalidInput("invalid_evidence")
    receipt = value.get("receipt_sha256")
    if "receipt_sha256" in value and (
        not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt)
    ):
        raise InvalidInput("invalid_evidence")
    if "error_code" in value and value["error_code"] not in _EVIDENCE_ERRORS:
        raise InvalidInput("invalid_evidence")
    if "http_status" in value and (
        type(value["http_status"]) is not int or not 100 <= value["http_status"] <= 599
    ):
        raise InvalidInput("invalid_evidence")
    _evidence_time(value)
    _evidence_processing(value, platform)
    return dict(value)


def _evidence_time(value: dict) -> None:
    if not {"published_at", "published_at_source"}.intersection(value):
        return
    if (
        value.get("published_at_source") != "provider"
        or not value.get("receipt_sha256")
        or not isinstance(value.get("published_at"), str)
    ):
        raise InvalidInput("invalid_evidence")
    normalize_schedule(value["published_at"])


def _evidence_processing(value: dict, platform: str) -> None:
    if not {"processing_kind", "processing_id"}.intersection(value):
        return
    kinds = {"facebook": "facebook_upload", "instagram": "instagram_container", "x": "x_upload"}
    identifier = value.get("processing_id")
    if (
        platform not in kinds
        or value.get("processing_kind") != kinds[platform]
        or not isinstance(identifier, str)
        or not re.fullmatch(r"[1-9][0-9]{0,31}", identifier)
    ):
        # IDs opacos de otros contratos necesitan una gramática revisada explícita.
        raise InvalidInput("invalid_evidence")


def _provider_result(value: ProviderResult, platform: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"state", "remote_id", "permalink", "evidence"}:
        raise InvalidInput("invalid_provider_result")
    state = value["state"]
    if not isinstance(state, str) or state not in ("published", "failed", "uncertain", "held"):
        raise InvalidInput("invalid_provider_result")
    evidence = _safe_evidence(value["evidence"], platform)
    rid = value["remote_id"]
    if rid is not None and (
        not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", rid)
    ):
        raise InvalidInput("invalid_remote_id")
    if state == "published" and (not rid or not evidence.get("receipt_sha256")):
        raise InvalidInput("publication_receipt_required")
    link = value["permalink"]
    if link is not None:
        if not isinstance(link, str) or len(link) > 2048 or any(ord(c) < 33 for c in link):
            raise InvalidInput("invalid_permalink")
        try:
            url = urlsplit(link)
            hosts = {
                "facebook": {"facebook.com", "www.facebook.com"},
                "instagram": {"instagram.com", "www.instagram.com"},
                "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
                "tiktok": {"tiktok.com", "www.tiktok.com"},
            }
            if (
                url.scheme != "https"
                or url.hostname not in hosts[platform]
                or url.username
                or url.password
                or url.port not in (None, 443)
                or url.fragment
            ):
                raise ValueError
            if any(word in url.query.lower() for word in ("token", "secret", "code=", "ticket")):
                raise ValueError
        except ValueError as exc:
            raise InvalidInput("invalid_permalink") from exc
    return dict(value) | {"evidence": evidence}


def _validate_confirmation(
    row: dict, attempt_id: str, value: dict, confirmed: dict, withdrawn: bool
) -> None:
    expected = {
        "attempt_id": attempt_id,
        "normalized_destination": row["normalized_destination"],
        "remote_id": value["remote_id"],
    }
    if (
        not isinstance(confirmed, dict)
        or set(confirmed)
        != {"confirmed", "attempt_id", "normalized_destination", "remote_id", "receipt"}
        or not value["remote_id"]
        or confirmed.get("confirmed") is not True
        or any(confirmed.get(k) != v for k, v in expected.items())
        or not isinstance(confirmed.get("receipt"), dict)
        or set(confirmed["receipt"]) != {"sha256", "operation"}
        or not re.fullmatch(r"[0-9a-f]{64}", str(confirmed["receipt"].get("sha256", "")))
        or not isinstance(confirmed["receipt"].get("operation"), str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", confirmed["receipt"]["operation"])
    ):
        raise InvalidInput("confirmed_receipt_required")
    previous = json.loads(row["result_json"]) if row["result_json"] else {}
    if previous.get("remote_id") and previous["remote_id"] != value["remote_id"]:
        raise Conflict("remote_receipt_mismatch")
    if withdrawn and not previous.get("remote_id"):
        raise Conflict("withdrawal_receipt_mismatch")


def _publication_time(value: dict, row: dict, now: int) -> int | None:
    evidence = value["evidence"]
    if "published_at" not in evidence:
        return None
    if (
        value["state"] != "published"
        or evidence.get("published_at_source") != "provider"
        or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("receipt_sha256", "")))
    ):
        raise InvalidInput("remote_publication_time_required")
    stamp = normalize_schedule(evidence["published_at"])
    if not row["started_at"] <= stamp <= now:
        raise InvalidInput("remote_publication_time_outside_attempt")
    return stamp


def _report_target(
    row: dict, value: dict, confirmed: dict | None, withdrawn: bool, remote_time: int | None
) -> str:
    target = (
        "withdrawn" if withdrawn else "uncertain" if value["state"] == "held" else value["state"]
    )
    previous = json.loads(row["result_json"]) if row["result_json"] else {}
    enrichment = (
        confirmed is not None
        and not withdrawn
        and row["state"] in ("published", "withdrawn")
        and value["state"] == "published"
        and value["remote_id"] == previous.get("remote_id")
        and previous.get("published_at_utc") is None
        and remote_time is not None
    )
    if enrichment:
        return str(row["state"])
    if row["state"] in _TERMINAL and not (withdrawn and row["state"] == "published"):
        raise Conflict("terminal_result_conflict")
    if row["state"] == "uncertain" and target in _TERMINAL and confirmed is None:
        raise Conflict("reconciliation_required")
    if withdrawn and (confirmed is None or row["state"] != "published"):
        raise Conflict("withdrawal_requires_publication")
    return str(target)


def _report(
    con: db.DualConnection,
    row: dict,
    attempt_id: str,
    event_key: str,
    result: ProviderResult,
    now: int,
    actor: str,
    *,
    confirmed: dict | None = None,
    withdrawn: bool = False,
) -> dict:
    value = _provider_result(result, row["normalized_destination"].split(":", 1)[0])
    if not isinstance(event_key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", event_key):
        raise InvalidInput("invalid_event_key")
    key = "report:" + event_key
    semantic = {"result": value, "actor": actor, "confirmation": confirmed, "withdrawn": withdrawn}
    digest = canonical_hash(semantic)
    old = con.execute(
        "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key=?",
        (row["tenant_id"], attempt_id, key),
    ).fetchone()
    if old:
        payload = json.loads(old["payload_json"])
        if payload.get("report_hash") != digest:
            raise Conflict("event_idempotency_conflict")
        answer: dict = payload["report_response"]
        return answer
    if row["started_at"] is None or row["attempt_id"] != attempt_id:
        raise Conflict("attempt_not_started")
    previous = json.loads(row["result_json"]) if row["result_json"] else {}
    if (
        previous.get("remote_id")
        and value["remote_id"]
        and value["remote_id"] != previous["remote_id"]
    ):
        raise Conflict("remote_receipt_mismatch")
    remote_time = _publication_time(value, row, now)
    target = _report_target(row, value, confirmed, withdrawn, remote_time)
    if confirmed is not None:
        _validate_confirmation(row, attempt_id, value, confirmed, withdrawn)
    answer = {"delivery_id": row["id"], "attempt_id": attempt_id, "state": target}
    _event(
        con,
        row,
        attempt_id,
        key,
        "withdrawn" if withdrawn else "reconciled" if confirmed else target,
        now,
        actor=actor,
        report_hash=digest,
        report_response=answer,
        result=value,
        confirmation=confirmed,
    )
    stored = value | {
        "remote_id": value["remote_id"] or previous.get("remote_id"),
        "recorded_at": now,
        "first_published_report_at": previous.get("first_published_report_at")
        or (now if value["state"] == "published" else None),
        "published_at_utc": remote_time
        if remote_time is not None
        else previous.get("published_at_utc"),
    }
    con.execute(
        "UPDATE publication_deliveries SET state=?,result_json=? WHERE tenant_id=? AND id=? AND attempt_id=? AND started_at IS NOT NULL",
        (target, canonical_json(stored), row["tenant_id"], row["id"], attempt_id),
    )
    if target in _TERMINAL:
        con.execute(
            "UPDATE publication_media_tickets SET revoked_at=? WHERE tenant_id=? AND attempt_id=? AND revoked_at IS NULL",
            (now, row["tenant_id"], attempt_id),
        )
    return answer


def report_attempt(
    db_url: DBUrl,
    principal: dict,
    attempt_id: str,
    event_key: str,
    result: ProviderResult,
    now: int,
    *,
    confirmation: dict | None = None,
) -> dict:
    with db.connect(db_url) as con:
        tenant = _tenant(principal)
        lock_tenant(con, tenant)
        require_worker(con, principal, now)
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=? AND worker_grant_id=?",
            (tenant, attempt_id, principal["grant_id"]),
        ).fetchone()
        if row is None:
            raise NotFound()
        return _report(
            con,
            row,
            attempt_id,
            event_key,
            result,
            now,
            f"worker:{principal['grant_id']}",
            confirmed=confirmation,
        )


def reconcile_attempt(
    db_url: DBUrl,
    tenant_id: int,
    owner_id: int,
    attempt_id: str,
    event_key: str,
    result: ProviderResult,
    confirmation: dict,
    now: int,
    *,
    withdrawn: bool = False,
) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=?",
            (tenant_id, attempt_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        if not confirmation:
            raise InvalidInput("confirmed_receipt_required")
        return _report(
            con,
            row,
            attempt_id,
            event_key,
            result,
            now,
            f"owner:{owner_id}",
            confirmed=confirmation,
            withdrawn=withdrawn,
        )


def cancel_delivery(
    db_url: DBUrl, tenant_id: int, owner_id: int, delivery_id: int, now: int
) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = _delivery(con, tenant_id, delivery_id)
        if row["started_at"] is not None:
            raise Conflict("attempt_already_started")
        if row["state"] == "cancelled":
            return _public(row)
        con.execute(
            "UPDATE publication_deliveries SET state='cancelled' WHERE tenant_id=? AND id=? AND started_at IS NULL",
            (tenant_id, delivery_id),
        )
        _event(
            con,
            row,
            f"delivery:{delivery_id}",
            "cancel",
            "cancelled",
            now,
            actor=f"owner:{owner_id}",
        )
        return _public(_delivery(con, tenant_id, delivery_id))


def list_calendar(
    db_url: DBUrl, tenant_id: int, owner_id: int, *, limit: int = 50, cursor: int = 0
) -> dict:
    positive_integer(limit, "invalid_limit")
    positive_integer(cursor, "invalid_cursor", allow_zero=True)
    if limit > 100:
        raise InvalidInput("invalid_limit")
    with db.connect(db_url) as con:
        require_owner(con, tenant_id, owner_id)
        rows = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND id>? ORDER BY id LIMIT ?",
            (tenant_id, cursor, limit + 1),
        ).fetchall()
        return {
            "items": [_public(r) for r in rows[:limit]],
            "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
        }
