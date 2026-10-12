"""Política owner inmutable, versionada y acotada al catálogo propio."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError

from webapp import db

from .contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    canonical_hash,
    canonical_json,
    normalize_schedule,
    positive_integer,
)


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: StrictBool
    project_ids: list[StrictInt] = Field(default_factory=list)
    product_ids: list[StrictInt] = Field(default_factory=list)
    connection_ids: list[StrictInt] = Field(default_factory=list)
    allowed_sources: list[StrictStr] = Field(default_factory=list)
    timezone: StrictStr = "UTC"
    frequency_minutes: StrictInt = Field(default=60, gt=0, le=2**31 - 1)
    max_daily_per_destination: StrictInt = Field(default=1, gt=0, le=2**31 - 1)
    window_minutes: StrictInt = Field(default=60, gt=0, le=2**31 - 1)
    valid_from: StrictStr | None = None
    expires_at: StrictStr | None = None
    spend_allowed: StrictBool = False


def lock_tenant(con: db.DualConnection, tenant_id: int) -> None:
    """Serializa CAS/issue/revoke dentro de una empresa."""
    if con.dialect == "sqlite":
        con.execute("BEGIN IMMEDIATE")
    else:
        con.execute("SELECT id FROM tenants WHERE id=? FOR UPDATE", (tenant_id,))


def require_owner(con: db.DualConnection, tenant_id: int, owner_id: int) -> None:
    suffix = " FOR SHARE" if con.dialect == "postgres" else ""
    row = con.execute(
        "SELECT role FROM users WHERE tenant_id=? AND id=?" + suffix, (tenant_id, owner_id)
    ).fetchone()
    if row is None or row["role"] != "owner":
        raise Forbidden()


def latest_policy(con: db.DualConnection, tenant_id: int) -> dict | None:
    return con.execute(
        "SELECT * FROM publication_policies WHERE tenant_id=? ORDER BY version DESC LIMIT 1",
        (tenant_id,),
    ).fetchone()


def policy_metadata(row: dict) -> dict:
    return {
        **json.loads(row["payload_json"]),
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "owner_id": row["owner_id"],
        "version": row["version"],
        "created_at": row["created_at"],
        "payload_hash": row["payload_hash"],
    }


def get_policy(db_url: str | Path | None, tenant_id: int, owner_id: int) -> dict:
    with db.connect(db_url) as con:
        require_owner(con, tenant_id, owner_id)
        row = latest_policy(con, tenant_id)
    return policy_metadata(row) if row else {"version": 0, "enabled": False}


def _normalize_source(value: str) -> str:
    """Fuentes HTTPS concretas; evita credenciales y autorización por wildcard."""
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or any(c.isspace() or ord(c) < 32 for c in value)
            or "*" in value
        ):
            raise ValueError
        host = parts.hostname.encode("idna").decode("ascii").lower()
        if ":" in host:
            host = f"[{host}]"
        port = parts.port
        netloc = host if port in (None, 443) else f"{host}:{port}"
        return urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError) as exc:
        raise InvalidInput("invalid_source") from exc


def _validate_payload(con: db.DualConnection, tenant_id: int, payload: dict, now: int) -> dict:
    try:
        value = PolicyInput.model_validate(payload).model_dump()
        ZoneInfo(value["timezone"])
    except (ValidationError, ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        raise InvalidInput("invalid_policy") from exc
    if value["spend_allowed"]:
        raise InvalidInput("spend_not_authorized")
    for field in ("project_ids", "product_ids", "connection_ids"):
        for item in value[field]:
            positive_integer(item, "invalid_catalog_id")
        value[field] = sorted(set(value[field]))
    value["allowed_sources"] = sorted({_normalize_source(s) for s in value["allowed_sources"]})
    for field in ("valid_from", "expires_at"):
        if value[field] is not None:
            value[field] = normalize_schedule(value[field])
    start, end = value["valid_from"], value["expires_at"]
    if (start is None) != (end is None) or (start is not None and start >= end):
        raise InvalidInput("invalid_validity")
    if value["enabled"] and (
        start is None
        or end <= now
        or any(
            not value[field]
            for field in ("project_ids", "product_ids", "connection_ids", "allowed_sources")
        )
    ):
        raise InvalidInput("incomplete_active_policy")
    _validate_catalog(con, tenant_id, value, now)
    return value


def _validate_catalog(con: db.DualConnection, tenant_id: int, value: dict, now: int) -> None:
    for pid in value["project_ids"]:
        if not con.execute(
            "SELECT id FROM projects WHERE tenant_id=? AND id=? AND archived=0", (tenant_id, pid)
        ).fetchone():
            raise Forbidden()
    for bid in value["product_ids"]:
        product = con.execute(
            "SELECT project_id FROM brands WHERE tenant_id=? AND id=?", (tenant_id, bid)
        ).fetchone()
        if product is None or product["project_id"] not in value["project_ids"]:
            raise Forbidden()
    for cid in value["connection_ids"]:
        connection = con.execute(
            "SELECT status,expires_at,remote_id FROM publication_connections WHERE tenant_id=? AND id=?",
            (tenant_id, cid),
        ).fetchone()
        if connection is None:
            raise Forbidden()
        if value["enabled"] and (
            connection["status"] != "active"
            or not connection["remote_id"].strip()
            or (connection["expires_at"] is not None and connection["expires_at"] <= now)
        ):
            raise Forbidden()


def set_policy(
    db_url: str | Path | None, tenant_id: int, owner_id: int, expected_version: int, payload: dict
) -> dict:
    """Inserta nueva versión; jamás modifica ni habilita versiones anteriores."""
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        positive_integer(expected_version, "invalid_version", allow_zero=True)
        row = latest_policy(con, tenant_id)
        version = row["version"] if row else 0
        if version != expected_version:
            raise Conflict("policy_version_conflict")
        now = int(time.time())
        value = _validate_payload(con, tenant_id, payload, now)
        con.execute(
            "INSERT INTO publication_policies(tenant_id,owner_id,version,enabled,payload_json,payload_hash,valid_from,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                owner_id,
                version + 1,
                int(value["enabled"]),
                canonical_json(value),
                canonical_hash(value),
                value["valid_from"],
                value["expires_at"],
                now,
            ),
        )
        result = latest_policy(con, tenant_id)
        assert result is not None
        return policy_metadata(result)


def require_active_policy(
    con: db.DualConnection, tenant_id: int, policy_version: int, now: int
) -> dict:
    """Vigencia de versión y owner autorizante, comprobada en cada uso."""
    policy = latest_policy(con, tenant_id)
    if policy is None or not policy["enabled"]:
        raise Forbidden()
    if policy["version"] != policy_version:
        raise Conflict("policy_version_conflict")
    require_owner(con, tenant_id, policy["owner_id"])
    if (
        policy["valid_from"] is None
        or policy["expires_at"] is None
        or not policy["valid_from"] <= now < policy["expires_at"]
    ):
        raise Forbidden()
    return policy
