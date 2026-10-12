"""Catálogo propio y permisos obtenidos exclusivamente por transporte privado."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from webapp import db

from .contracts import Conflict, Forbidden, InvalidInput, NotFound, canonical_json, positive_integer
from .policies import lock_tenant, require_owner

MODES = {
    "facebook": ("page", "facebook_login"),
    "instagram": ("instagram_login", "facebook_login"),
    "x": ("oauth2",),
    "tiktok": ("oauth2",),
}
REQUIRED_SCOPES = {
    ("facebook", "page"): frozenset(
        ("pages_manage_posts", "pages_read_engagement", "pages_show_list")
    ),
    ("facebook", "facebook_login"): frozenset(
        ("pages_manage_posts", "pages_read_engagement", "pages_show_list")
    ),
    ("instagram", "facebook_login"): frozenset(
        ("instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement")
    ),
    ("instagram", "instagram_login"): frozenset(
        ("instagram_business_basic", "instagram_business_content_publish")
    ),
    ("x", "oauth2"): frozenset(("tweet.read", "tweet.write", "users.read", "media.write")),
    ("tiktok", "oauth2"): frozenset(("user.info.basic", "video.publish")),
}


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: StrictInt | None = None
    expected_version: StrictInt | None = None
    platform: Literal["facebook", "instagram", "x", "tiktok"]
    api_mode: StrictStr
    remote_id: StrictStr
    project_ids: list[StrictInt] = Field(min_length=1, max_length=100)
    capabilities: dict = Field(default_factory=dict)


def _connection(con: db.DualConnection, tenant_id: int, connection_id: int) -> dict:
    positive_integer(connection_id, "invalid_connection")
    row = con.execute(
        "SELECT * FROM publication_connections WHERE tenant_id=? AND id=?",
        (tenant_id, connection_id),
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def connection_metadata(con: db.DualConnection, row: dict) -> dict:
    tenant_id, cid = row["tenant_id"], row["id"]
    detail = con.execute(
        "SELECT remote_name,scopes_json,scope_evidence,verified_at,expiry_state,hold_reason FROM publication_connection_details WHERE tenant_id=? AND connection_id=?",
        (tenant_id, cid),
    ).fetchone()
    projects = con.execute(
        "SELECT project_id FROM publication_project_connections WHERE tenant_id=? AND connection_id=? ORDER BY project_id",
        (tenant_id, cid),
    ).fetchall()
    return {
        "id": cid,
        "tenant_id": tenant_id,
        "platform": row["platform"],
        "api_mode": row["api_mode"],
        "remote_id": row["remote_id"],
        "status": row["status"],
        "version": row["version"],
        "expires_at": row["expires_at"],
        "capabilities": json.loads(row["capabilities_json"]),
        "project_ids": [p["project_id"] for p in projects],
        "remote_name": detail["remote_name"] if detail else None,
        "scopes": json.loads(detail["scopes_json"]) if detail else [],
        "verified_at": detail["verified_at"] if detail else None,
        "scope_evidence": detail["scope_evidence"] if detail else "unverified",
        "expiry_state": detail["expiry_state"] if detail else "unknown",
        "hold_reason": detail["hold_reason"] if detail else "authorization_required",
    }


def list_connections(db_url: str | Path | None, tenant_id: int, owner_id: int) -> list[dict]:
    with db.connect(db_url) as con:
        require_owner(con, tenant_id, owner_id)
        return [
            connection_metadata(con, row)
            for row in con.execute(
                "SELECT * FROM publication_connections WHERE tenant_id=? ORDER BY id", (tenant_id,)
            ).fetchall()
        ]


def put_connection(db_url: str | Path | None, tenant_id: int, owner_id: int, payload: dict) -> dict:
    """Metadatos del owner nunca constituyen evidencia ni activan la cuenta."""
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        try:
            value = ConnectionInput.model_validate(payload).model_dump()
        except (ValidationError, TypeError) as exc:
            raise InvalidInput("invalid_connection") from exc
        platform, mode, remote = value["platform"], value["api_mode"], value["remote_id"]
        if mode not in MODES[platform] or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", remote):
            raise InvalidInput("invalid_destination")
        if set(value["capabilities"]) - {"publish", "image", "video"} or any(
            type(v) is not bool for v in value["capabilities"].values()
        ):
            raise InvalidInput("invalid_capabilities")
        canonical_json(value["capabilities"])
        for pid in value["project_ids"]:
            positive_integer(pid, "invalid_project")
            if not con.execute(
                "SELECT id FROM projects WHERE tenant_id=? AND id=? AND archived=0",
                (tenant_id, pid),
            ).fetchone():
                raise Forbidden()
        cid = value["id"]
        if cid is None:
            if value["expected_version"] is not None:
                raise InvalidInput("invalid_version")
            con.execute(
                "INSERT INTO publication_connections(tenant_id,platform,api_mode,remote_id,status,version,capabilities_json,created_at) VALUES (?,?,?,?,'held',1,'{}',?)",
                (tenant_id, platform, mode, remote, int(time.time())),
            )
            cid = db.get_last_insert_id(db_url, con, "publication_connections")
        else:
            row = _connection(con, tenant_id, cid)
            if (
                positive_integer(value["expected_version"], "invalid_version", allow_zero=True)
                != row["version"]
            ):
                raise Conflict("connection_version_conflict")
            con.execute(
                "UPDATE publication_connections SET platform=?,api_mode=?,remote_id=?,status='held',version=version+1,expires_at=NULL,capabilities_json='{}' WHERE tenant_id=? AND id=?",
                (platform, mode, remote, tenant_id, cid),
            )
        con.execute(
            "DELETE FROM publication_connection_vault WHERE tenant_id=? AND connection_id=?",
            (tenant_id, cid),
        )
        con.execute(
            "DELETE FROM publication_project_connections WHERE tenant_id=? AND connection_id=?",
            (tenant_id, cid),
        )
        for pid in sorted(set(value["project_ids"])):
            con.execute(
                "INSERT INTO publication_project_connections(tenant_id,project_id,connection_id) VALUES (?,?,?)",
                (tenant_id, pid, cid),
            )
        con.execute(
            "INSERT INTO publication_connection_details(tenant_id,connection_id,owner_id,hold_reason,requested_capabilities_json) VALUES (?,?,?,'authorization_required',?) ON CONFLICT(tenant_id,connection_id) DO UPDATE SET owner_id=excluded.owner_id,remote_name=NULL,scopes_json='[]',scope_evidence='unverified',verified_at=NULL,expiry_state='unknown',hold_reason='authorization_required',requested_capabilities_json=excluded.requested_capabilities_json",
            (tenant_id, cid, owner_id, canonical_json(value["capabilities"])),
        )
        return connection_metadata(con, _connection(con, tenant_id, cid))


def hold_connection(con: db.DualConnection, tenant_id: int, cid: int, reason: str) -> dict:
    con.execute(
        "UPDATE publication_connections SET status='held',version=version+1,expires_at=NULL,capabilities_json='{}' WHERE tenant_id=? AND id=?",
        (tenant_id, cid),
    )
    con.execute(
        "DELETE FROM publication_connection_vault WHERE tenant_id=? AND connection_id=?",
        (tenant_id, cid),
    )
    con.execute(
        "UPDATE publication_connection_details SET remote_name=NULL,scopes_json='[]',scope_evidence='unverified',verified_at=NULL,expiry_state='unknown',hold_reason=? WHERE tenant_id=? AND connection_id=?",
        (reason, tenant_id, cid),
    )
    return connection_metadata(con, _connection(con, tenant_id, cid))
