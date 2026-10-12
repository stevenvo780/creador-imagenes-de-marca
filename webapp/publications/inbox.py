"""Proyección diaria planner: solo metadatos locales, sin autorizar ni despachar."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from webapp import db

from .campaigns import require_planner
from .connections import REQUIRED_SCOPES, connection_metadata
from .contracts import InvalidInput, positive_integer
from .decisions import publication_eligibility_in_transaction
from .deliveries import _destination_usage, _reasons, _worker_hold_event
from .ledger import _canonical_destination, history_ready_in_transaction
from .policies import lock_tenant


class CandidateStatus(TypedDict):
    revision_id: int
    contract_hash: str
    reasons: list[str]
    decision_id: int | None
    eligible: bool


class StockItem(TypedDict):
    delivery_id: int
    revision_id: int
    contract_hash: str
    media_sha256: str
    state: str


class HistoryPage(TypedDict):
    media_sha256: list[str]
    next_cursor: str | None
    complete: bool
    history_ready: bool


class AccountInbox(TypedDict):
    connection: dict[str, Any]
    destination: str
    remaining_daily_capacity: int
    authorized_stock: int
    deficit: int
    stock: list[StockItem]
    pending_candidates: list[CandidateStatus]
    held_deliveries: list[CandidateStatus]
    hold_reasons: list[str]
    history: HistoryPage


def _history_page(
    con: db.DualConnection, tenant: int, destination: str, cursor: str, ready: bool
) -> HistoryPage:
    # Misma resolución de alias que seen_media; SQL pagina sólo destinos autorizados.
    destinations = con.execute(
        "SELECT DISTINCT normalized_destination FROM publication_media_guards WHERE tenant_id=? AND normalized_destination LIKE ?",
        (tenant, destination.split(":", 1)[0] + ":%"),
    ).fetchall()
    permitted = [
        r["normalized_destination"]
        for r in destinations
        if _canonical_destination(con, tenant, r["normalized_destination"]) == destination
    ]
    hashes = []
    if permitted:
        slots = ",".join("?" for _ in permitted)
        rows = con.execute(
            f"SELECT DISTINCT image_sha256 FROM publication_media_guards WHERE tenant_id=? AND normalized_destination IN ({slots}) AND image_sha256>? ORDER BY image_sha256 LIMIT 101",
            (tenant, *permitted, cursor),
        ).fetchall()
        hashes = [r["image_sha256"] for r in rows]
    next_cursor = hashes[99] if len(hashes) > 100 else None
    return {
        "media_sha256": hashes[:100],
        "next_cursor": next_cursor,
        "complete": ready and next_cursor is None,
        "history_ready": ready,
    }


def _connection_reasons(account: dict, now: int) -> list[str]:
    reasons: list[str] = []
    if (
        account["status"] != "active"
        or account["verified_at"] is None
        or account["scope_evidence"] == "unverified"
        or account["expiry_state"] == "unknown"
        or (account["expires_at"] is not None and account["expires_at"] <= now)
        or not REQUIRED_SCOPES[(account["platform"], account["api_mode"])].issubset(
            account["scopes"]
        )
    ):
        reasons.append("connection_unavailable")
    if account["hold_reason"]:
        reasons.append(account["hold_reason"])
    if account["platform"] == "x":
        reasons.append("blocked_budget")
    return reasons


def _stock_projection(
    con: db.DualConnection,
    tenant: int,
    revisions: list[dict],
    now: int,
    connection_reasons: list[str],
) -> tuple[list[CandidateStatus], list[CandidateStatus], list[StockItem]]:
    pending: list[CandidateStatus] = []
    held: list[CandidateStatus] = []
    stock: list[StockItem] = []
    seen: set[tuple[str, str]] = set()
    for revision in revisions:
        eligibility = publication_eligibility_in_transaction(con, tenant, revision["id"], now)
        status: CandidateStatus = {
            "revision_id": revision["id"],
            "contract_hash": revision["contract_hash"],
            "reasons": list(eligibility["reasons"]),
            "decision_id": eligibility["decision_id"],
            "eligible": eligibility["eligible"],
        }
        delivery = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND revision_id=?",
            (tenant, revision["id"]),
        ).fetchone()
        if delivery is None:
            pending.append(status)
            continue
        checks, _ = _reasons(con, delivery, now)
        checks.extend(connection_reasons)
        if delivery["contract_hash"] != revision["contract_hash"]:
            checks.append("contract_changed")
        if delivery["expires_at"] <= now:
            checks.append("revision_expired")
        if _worker_hold_event(con, delivery) is not None:
            checks.extend(json.loads(delivery["hold_reasons_json"]))
        if delivery["state"] == "reserved" and (delivery["lease_until"] or 0) <= now:
            checks.append("reservation_expired")
        if delivery["started_at"] is not None or delivery["state"] not in (
            "scheduled",
            "reserved",
        ):
            checks.append("delivery_not_stock")
        if checks:
            held.append(status | {"reasons": list(dict.fromkeys(checks)), "eligible": False})
            continue
        key = (
            _canonical_destination(con, tenant, delivery["normalized_destination"]),
            delivery["media_sha256"],
        )
        if key in seen:
            continue
        seen.add(key)
        stock.append(
            {
                "delivery_id": delivery["id"],
                "revision_id": revision["id"],
                "contract_hash": revision["contract_hash"],
                "media_sha256": key[1],
                "state": delivery["state"],
            }
        )
    return pending, held, stock


def daily_inbox(
    db_url: str | Path | None,
    principal: dict,
    stock_target: int = 1,
    cursor: int = 0,
    limit: int = 50,
    history_cursor: str = "",
) -> dict:
    for value, code, zero in (
        (stock_target, "invalid_stock_target", False),
        (cursor, "invalid_cursor", True),
        (limit, "invalid_limit", False),
    ):
        positive_integer(value, code, allow_zero=zero)
    if stock_target > 100 or limit > 100:
        raise InvalidInput("invalid_limit")
    if not isinstance(history_cursor, str) or (
        history_cursor and not re.fullmatch("[a-f0-9]{64}", history_cursor)
    ):
        raise InvalidInput("invalid_history_cursor")
    tenant = positive_integer(principal.get("tenant_id"), "invalid_tenant")
    now = int(time.time())
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        policy = require_planner(con, principal)
        rules = json.loads(policy["payload_json"])
        zone = ZoneInfo(rules["timezone"])
        local = datetime.fromtimestamp(now, UTC).astimezone(zone)
        day = local.date().isoformat()
        start = datetime.combine(local.date(), datetime.min.time(), zone)
        end = start + timedelta(days=1)
        projects = ",".join("?" for _ in rules["project_ids"])
        products = ",".join("?" for _ in rules["product_ids"])
        scoped = (tenant, *rules["project_ids"], *rules["product_ids"])
        campaign_scope = f"tenant_id=? AND project_id IN ({projects}) AND brand_id IN ({products})"
        rows = con.execute(
            f"SELECT id,project_id,brand_id,objective FROM publication_campaigns WHERE {campaign_scope} AND archived=0 AND id>? ORDER BY id LIMIT ?",
            (*scoped, cursor, limit + 1),
        ).fetchall()
        accounts: list[AccountInbox] = []
        for cid in rules["connection_ids"]:
            row = con.execute(
                "SELECT * FROM publication_connections WHERE tenant_id=? AND id=?", (tenant, cid)
            ).fetchone()
            if row is None:
                continue
            account = connection_metadata(con, row)
            account["project_ids"] = [
                p for p in account["project_ids"] if p in rules["project_ids"]
            ]
            if not account["project_ids"]:
                continue
            destination = _canonical_destination(
                con, tenant, f"{account['platform']}:{account['remote_id']}"
            )
            count, _, reasons = _destination_usage(
                con, tenant, destination, rules["timezone"], day, now
            )
            remaining = max(0, rules["max_daily_per_destination"] - count)
            history_ready = history_ready_in_transaction(con, tenant, destination)
            if not history_ready:
                reasons.append("history_not_ready")
            connection_reasons = _connection_reasons(account, now)
            reasons.extend(connection_reasons)
            revisions = con.execute(
                f"SELECT r.id,r.contract_hash FROM publication_revisions r JOIN publication_campaigns c ON c.tenant_id=r.tenant_id AND c.id=r.campaign_id WHERE r.tenant_id=? AND c.project_id IN ({projects}) AND c.brand_id IN ({products}) AND r.connection_id=? AND r.policy_version=? AND r.scheduled_at_utc>=? AND r.scheduled_at_utc<? ORDER BY r.id",
                (*scoped, cid, policy["version"], int(start.timestamp()), int(end.timestamp())),
            ).fetchall()
            pending, held, stock = _stock_projection(
                con, tenant, revisions, now, connection_reasons
            )
            accounts.append(
                {
                    "connection": account,
                    "destination": destination,
                    "remaining_daily_capacity": remaining,
                    "authorized_stock": len(stock),
                    "deficit": max(0, min(stock_target, remaining) - len(stock)),
                    "stock": stock,
                    "pending_candidates": pending,
                    "held_deliveries": held,
                    "hold_reasons": list(dict.fromkeys(reasons)),
                    "history": _history_page(
                        con, tenant, destination, history_cursor, history_ready
                    ),
                }
            )
        return {
            "tenant_id": tenant,
            "policy": rules
            | {"version": policy["version"], "payload_hash": policy["payload_hash"]},
            "day": day,
            "timezone": rules["timezone"],
            "as_of": now,
            "stock_target": stock_target,
            "campaigns": {
                "items": [dict(r) for r in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            },
            "accounts": accounts,
        }
