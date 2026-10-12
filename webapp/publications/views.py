"""Proyecciones owner acotadas; nunca serializa filas de credenciales/evaluaciones."""

import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from webapp import db
from webapp.storage_backend.base import StorageBackend

from .campaigns import _media, _revision
from .connections import connection_metadata
from .contracts import Conflict, InvalidInput, NotFound, positive_integer
from .deliveries import _public, list_calendar
from .policies import latest_policy, lock_tenant, policy_metadata, require_owner

DBUrl = str | Path | None


def safe_link(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
        if p.scheme == "https" and p.hostname and not p.username and not p.password:
            return value
    except ValueError:
        pass
    return None


def revision_view(con: db.DualConnection, tenant: int, rid: int) -> dict:
    revision = _revision(con, tenant, rid)
    s = revision["snapshot"]
    decision = con.execute(
        "SELECT d.id,d.outcome,d.reason,d.created_at,d.contract_hash,e.model_receipt_json FROM publication_ai_decisions d JOIN publication_evaluations e ON e.tenant_id=d.tenant_id AND e.id=d.evaluation_receipt_id WHERE d.tenant_id=? AND d.revision_id=? ORDER BY d.id DESC LIMIT 1",
        (tenant, rid),
    ).fetchone()
    if decision:
        receipt = json.loads(decision.pop("model_receipt_json"))
        decision.update({k: receipt.get(k) for k in ("provider", "model")})
    return {
        "id": rid,
        "campaign_id": s["campaign_id"],
        "contract_hash": revision["contract_hash"],
        "caption": s["caption"],
        "policy_version": s["policy_version"],
        "scheduled_at_utc": s["scheduled_at_utc"],
        "expires_at_utc": s["expires_at_utc"],
        "timezone": s["policy_timezone"],
        "channel_metadata": s["channel_metadata"],
        "media": {k: s["media"][k] for k in ("id", "kind", "sha256", "mime", "width", "height")},
        "connection": {
            k: s["connection"][k] for k in ("id", "platform", "remote_id", "remote_name")
        },
        "visual_review": {"approval_current": s["visual_review"]["approval_current"]},
        "decision": dict(decision) if decision else None,
        "eligibility_reasons": revision["eligibility_reasons"],
    }


def _campaigns(con: db.DualConnection, tenant: int, cursor: int, limit: int) -> dict:
    positive_integer(cursor, "invalid_cursor", allow_zero=True)
    positive_integer(limit, "invalid_limit")
    if limit > 100:
        raise InvalidInput("invalid_limit")
    rows = con.execute(
        "SELECT c.id,c.project_id,c.brand_id,c.objective,c.archived,p.name project_name,b.name product_name FROM publication_campaigns c JOIN projects p ON p.tenant_id=c.tenant_id AND p.id=c.project_id JOIN brands b ON b.tenant_id=c.tenant_id AND b.id=c.brand_id WHERE c.tenant_id=? AND c.id>? ORDER BY c.id LIMIT ?",
        (tenant, cursor, limit + 1),
    ).fetchall()
    items = []
    for row in rows[:limit]:
        revisions = con.execute(
            "SELECT id FROM publication_revisions WHERE tenant_id=? AND campaign_id=? ORDER BY id DESC",
            (tenant, row["id"]),
        ).fetchall()
        items.append(
            dict(row) | {"revisions": [revision_view(con, tenant, r["id"]) for r in revisions]}
        )
    return {"items": items, "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}


def campaigns(db_url: DBUrl, tenant: int, owner: int, cursor: int = 0, limit: int = 50) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        return _campaigns(con, tenant, cursor, limit)


def _delivery_view(row: dict) -> dict:
    value = _public(row)
    if value["state"] in ("scheduled", "held") and value["expires_at"] <= int(time.time()):
        value["state"] = "expired"
    raw = value["result"]
    value["result"] = (
        None
        if not raw
        else {
            "state": raw.get("state"),
            "remote_id": raw.get("remote_id"),
            "permalink": safe_link(raw.get("permalink"))
            if value["state"] == "published" and raw.get("state") == "published"
            else None,
        }
    )
    return value


def delivery(db_url: DBUrl, tenant: int, owner: int, did: int) -> dict:
    with db.connect(db_url) as con:
        require_owner(con, tenant, owner)
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND id=?", (tenant, did)
        ).fetchone()
        if not row:
            raise NotFound()
        result = _delivery_view(row)
        result["visibility"] = _visibility(con, tenant, row["revision_id"])
        events = con.execute(
            "SELECT id,kind,created_at FROM publication_events WHERE tenant_id=? AND attempt_id=? ORDER BY id",
            (tenant, row["attempt_id"]),
        ).fetchall()
        result["events"] = [dict(e) for e in events]
        return result


def overview(db_url: DBUrl, tenant: int, owner: int) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        policy = latest_policy(con, tenant)
        tenant_row = con.execute(
            "SELECT id,slug,name FROM tenants WHERE id=?", (tenant,)
        ).fetchone()
        if tenant_row is None:
            raise NotFound()
        return {
            "tenant": dict(tenant_row),
            "policy": policy_metadata(policy) if policy else {"version": 0, "enabled": False},
            "campaigns": _campaigns(con, tenant, 0, 50),
            "connections": [
                connection_metadata(con, r)
                for r in con.execute(
                    "SELECT * FROM publication_connections WHERE tenant_id=? ORDER BY id", (tenant,)
                ).fetchall()
            ],
        }


def original(
    db_url: DBUrl, storage: StorageBackend, tenant: int, owner: int, rid: int, expected_hash: str
) -> tuple[bytes, str]:
    from .media_delivery import read_original

    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        row = con.execute(
            "SELECT contract_hash,frozen_json FROM publication_revisions WHERE tenant_id=? AND id=?",
            (tenant, rid),
        ).fetchone()
        if not row:
            raise NotFound()
        if row["contract_hash"] != expected_hash:
            raise Conflict("contract_changed")
        media = json.loads(row["frozen_json"])["media"]
        stored = _media(con, tenant, media["kind"], media["id"])
    content = read_original(storage, tenant, media, stored)
    return content, media["mime"]


def _visibility(con: db.DualConnection, tenant: int, rid: int) -> str:
    row = con.execute(
        "SELECT frozen_json FROM publication_revisions WHERE tenant_id=? AND id=?", (tenant, rid)
    ).fetchone()
    if row is None:
        return "unknown"
    s = json.loads(row["frozen_json"])
    if s["connection"]["platform"] != "tiktok":
        return "platform"
    return "private" if s["channel_metadata"].get("privacy") == "SELF_ONLY" else "platform"


def calendar(db_url: DBUrl, tenant: int, owner: int, *, cursor: int = 0, limit: int = 50) -> dict:
    page = list_calendar(db_url, tenant, owner, cursor=cursor, limit=limit)
    with db.connect(db_url) as con:
        require_owner(con, tenant, owner)
        for row in page["items"]:
            row["visibility"] = _visibility(con, tenant, row["revision_id"])
            result = row["result"]
            if result:
                row["result"] = {
                    "state": result.get("state"),
                    "remote_id": result.get("remote_id"),
                    "permalink": safe_link(result.get("permalink"))
                    if row["state"] == "published" and result.get("state") == "published"
                    else None,
                }
    return page
