"""Grants por rol, sin herencia de API keys ni cookies owner."""

from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

from fastapi import HTTPException, Request

from webapp import db

from .contracts import (
    Conflict,
    Forbidden,
    GrantRole,
    InvalidInput,
    NotFound,
    Principal,
    PublicationError,
    canonical_json,
    positive_integer,
)
from .policies import lock_tenant, require_active_policy, require_owner

_PREFIXES = {role: f"eikon_pub_{role}_" for role in ("planner", "reviewer", "worker")}
_METADATA_COLUMNS = (
    "id,tenant_id,owner_id,role,subject,policy_version,created_at,expires_at,revoked_at"
)


def issue_grant(
    db_url: str | Path | None,
    tenant_id: int,
    owner_id: int,
    role: GrantRole,
    subject: str,
    policy_version: int,
    expires_at: int,
) -> tuple[str, dict]:
    """Devuelve secreto solo aquí; BD y listados guardan únicamente su hash."""
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        now = int(time.time())
        # La ausencia/deshabilitación de política nunca concede autoridad.
        require_active_policy(con, tenant_id, policy_version, now)
        positive_integer(policy_version, "invalid_version")
        positive_integer(expires_at, "invalid_expiration")
        if not isinstance(role, str) or role not in _PREFIXES:
            raise InvalidInput("invalid_grant_role")
        if (
            not isinstance(subject, str)
            or not subject.strip()
            or len(subject) > 200
            or any(ord(c) < 32 for c in subject)
        ):
            raise InvalidInput("invalid_subject")
        canonical_json({"subject": subject})
        if expires_at <= now:
            raise InvalidInput("invalid_expiration")
        token = _PREFIXES[role] + secrets.token_urlsafe(32)
        con.execute(
            "INSERT INTO publication_grants(tenant_id,owner_id,policy_version,role,subject,secret_hash,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                owner_id,
                policy_version,
                role,
                subject.strip(),
                hashlib.sha256(token.encode()).hexdigest(),
                now,
                expires_at,
            ),
        )
        grant_id = db.get_last_insert_id(db_url, con, "publication_grants")
        row = con.execute(
            f"SELECT {_METADATA_COLUMNS} FROM publication_grants WHERE tenant_id=? AND id=?",
            (tenant_id, grant_id),
        ).fetchone()
        assert row is not None
    return token, row


def resolve_grant(
    db_url: str | Path | None, token: str, expected_role: GrantRole, now: int
) -> Principal:
    """Prefijo y tabla dedicada: el prefijo solo no otorga ningún permiso."""
    if (
        not isinstance(expected_role, str)
        or expected_role not in _PREFIXES
        or not isinstance(token, str)
        or not token.startswith(_PREFIXES[expected_role])
        or not token.isascii()
        or any(c.isspace() for c in token)
    ):
        raise Forbidden()
    positive_integer(now, "invalid_time", allow_zero=True)
    with db.connect(db_url) as con:
        # Única lectura global: la credencial aleatoria resuelve su tenant.
        row = con.execute(
            f"SELECT {_METADATA_COLUMNS} FROM publication_grants WHERE secret_hash=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        ).fetchone()
        if (
            row is None
            or row["role"] != expected_role
            or row["revoked_at"] is not None
            or now >= row["expires_at"]
            or now < row["created_at"]
        ):
            raise Forbidden()
        require_owner(con, row["tenant_id"], row["owner_id"])
        try:
            require_active_policy(con, row["tenant_id"], row["policy_version"], now)
        except Conflict as exc:
            raise Forbidden() from exc
        return {
            "tenant_id": row["tenant_id"],
            "grant_id": row["id"],
            "role": cast(GrantRole, row["role"]),
            "policy_version": row["policy_version"],
            "subject": row["subject"],
        }


def list_grants(db_url: str | Path | None, tenant_id: int, owner_id: int) -> list[dict]:
    with db.connect(db_url) as con:
        require_owner(con, tenant_id, owner_id)
        return con.execute(
            f"SELECT {_METADATA_COLUMNS} FROM publication_grants WHERE tenant_id=? ORDER BY id",
            (tenant_id,),
        ).fetchall()


def revoke_grant(db_url: str | Path | None, tenant_id: int, owner_id: int, grant_id: int) -> None:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = con.execute(
            "SELECT id FROM publication_grants WHERE tenant_id=? AND id=?", (tenant_id, grant_id)
        ).fetchone()
        if row is None:
            raise NotFound()
        con.execute(
            "UPDATE publication_grants SET revoked_at=? WHERE tenant_id=? AND id=? AND revoked_at IS NULL",
            (int(time.time()), tenant_id, grant_id),
        )


def grant_dependency(role: GrantRole) -> Callable[[Request], Principal]:
    """Dependencia exclusiva para futuros routers planner/reviewer/worker."""
    if role not in _PREFIXES:
        raise InvalidInput("invalid_grant_role")

    def dependency(request: Request) -> Principal:
        settings = request.app.state.settings
        header = request.headers.get("Authorization")
        if header is not None and settings.cookie_name in request.cookies:
            raise HTTPException(403, detail="ambiguous_authentication")
        if header is None or not header.lower().startswith("bearer "):
            raise HTTPException(403, detail="publication_grant_required")
        token = header[7:]
        if not token or token != token.strip() or any(c.isspace() for c in token):
            raise HTTPException(403, detail="publication_grant_required")
        try:
            return resolve_grant(settings.db_url, token, role, int(time.time()))
        except PublicationError as exc:
            raise HTTPException(exc.status_code, detail=exc.code) from exc

    return dependency


publication_planner = grant_dependency("planner")
publication_reviewer = grant_dependency("reviewer")
publication_worker = grant_dependency("worker")
