"""TikTok initial consent: durable intent, then atomic verified account creation."""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from webapp import db

from .connections import _connection, connection_metadata
from .contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    canonical_hash,
    canonical_json,
    positive_integer,
)
from .oauth import (
    OAuthConfig,
    VerificationClient,
    VerifiedAccount,
    _evidence_reason,
    _hash,
    _seal,
    authorization_url,
)
from .policies import lock_tenant, require_owner


class OnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    platform: Literal["tiktok"]
    api_mode: Literal["oauth2"]
    project_ids: list[StrictInt] = Field(min_length=1, max_length=100)
    redirect_uri: StrictStr


def _projects(con: db.DualConnection, tenant_id: int, project_ids: list[int]) -> None:
    # Keep project authorization stable until the final transaction commits.
    suffix = " FOR SHARE" if con.dialect == "postgres" else ""
    for pid in project_ids:
        positive_integer(pid, "invalid_project")
        if not con.execute(
            "SELECT id FROM projects WHERE tenant_id=? AND id=? AND archived=0" + suffix,
            (tenant_id, pid),
        ).fetchone():
            raise Forbidden()


def start_onboarding(
    db_url: str | Path | None,
    tenant_id: int,
    owner_id: int,
    platform: str,
    redirect_uri: str,
    now: int,
    *,
    project_ids: list[int],
    session_binding: str | None = None,
    config: OAuthConfig | None = None,
    key: bytes | None = None,
    key_id: str | None = None,
) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        if config is None:
            raise Conflict("oauth_not_configured")
        try:
            payload = OnboardingInput.model_validate(
                {
                    "platform": platform,
                    "api_mode": config.api_mode,
                    "project_ids": project_ids,
                    "redirect_uri": redirect_uri,
                }
            )
        except ValidationError as exc:
            raise InvalidInput("invalid_oauth_start") from exc
        public = config.public()
        if config.platform != "tiktok" or redirect_uri not in config.redirect_uris:
            raise InvalidInput("invalid_redirect_uri")
        session_hash = _hash(session_binding)
        positive_integer(now, "invalid_time", allow_zero=True)
        projects = sorted(set(payload.project_ids))
        _projects(con, tenant_id, projects)
        state = secrets.token_urlsafe(32)
        flow = {**public, "redirect_uri": redirect_uri, "project_ids": projects}
        con.execute(
            "INSERT INTO publication_oauth_onboarding_states(tenant_id,owner_id,state_hash,session_hash,config_hash,flow_json,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                owner_id,
                _hash(state),
                session_hash,
                canonical_hash(public),
                canonical_json(flow),
                now,
                now + 600,
            ),
        )
    return {
        "state": state,
        "authorization_url": authorization_url(config, redirect_uri, state, None),
        "expires_at": now + 600,
    }


def _principal(session_owner: dict) -> tuple[int, int, str]:
    if session_owner.get("auth_method") != "session":
        raise Forbidden()
    try:
        return (
            positive_integer(session_owner.get("tenant_id"), "invalid_tenant"),
            positive_integer(session_owner.get("user_id"), "invalid_owner"),
            _hash(session_owner.get("session_binding")),
        )
    except InvalidInput as exc:
        raise Forbidden() from exc


def finish_onboarding(
    db_url: str | Path | None,
    session_owner: dict,
    state: str,
    code: str,
    now: int,
    client: VerificationClient,
    *,
    key: bytes | None = None,
    key_id: str | None = None,
    provider_error: bool = False,
    config_getter: Callable[[], OAuthConfig] | None = None,
) -> dict:
    tenant_id, owner_id, session_hash = _principal(session_owner)
    state_hash = _hash(state)
    positive_integer(now, "invalid_time", allow_zero=True)
    if not provider_error and (
        not isinstance(code, str) or not code or len(code) > 4096 or not code.isascii()
    ):
        raise InvalidInput("invalid_oauth_code")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        intent = con.execute(
            "SELECT * FROM publication_oauth_onboarding_states WHERE tenant_id=? AND owner_id=? AND state_hash=? AND session_hash=?",
            (tenant_id, owner_id, state_hash, session_hash),
        ).fetchone()
        if intent is None:
            raise Forbidden()
        changed = con.execute(
            "UPDATE publication_oauth_onboarding_states SET consumed_at=? WHERE tenant_id=? AND owner_id=? AND state_hash=? AND session_hash=? AND consumed_at IS NULL AND expires_at>?",
            (now, tenant_id, owner_id, state_hash, session_hash, now),
        )
        if changed.rowcount != 1:
            raise Conflict("oauth_state_unavailable")
    # Commit consumption before provider calls, including cancellation/failure.
    if provider_error:
        raise Conflict("provider_consent_denied")
    flow = json.loads(intent["flow_json"])

    def check_config() -> None:
        config = config_getter() if config_getter else getattr(client, "config", None)
        if (
            not isinstance(config, OAuthConfig)
            or canonical_hash(config.public()) != intent["config_hash"]
        ):
            raise Conflict("oauth_not_configured")

    check_config()
    try:
        credential = client.exchange(flow, code, None)
        # Anchor lifetime conservatively to callback entry, not after slow I/O.
        account = client.verify(flow, credential, now)
    except Conflict as exc:
        raise Conflict(
            "oauth_not_configured"
            if exc.code == "oauth_not_configured"
            else "provider_verification_failed"
        ) from None
    except Exception:
        raise Conflict("provider_verification_failed") from None
    return _commit_account(
        db_url, session_owner, intent, flow, account, now, key, key_id, check_config
    )


def _commit_account(
    db_url: str | Path | None,
    session_owner: dict,
    intent: dict,
    flow: dict,
    account: VerifiedAccount,
    now: int,
    key: bytes | None,
    key_id: str | None,
    check_config: Callable[[], None],
) -> dict:
    tenant_id, owner_id, session_hash = (
        intent["tenant_id"],
        intent["owner_id"],
        intent["session_hash"],
    )
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        if _principal(session_owner) != (tenant_id, owner_id, session_hash):
            raise Forbidden()
        check_config()
        _projects(con, tenant_id, flow["project_ids"])
        final_now = max(now, int(time.time()))
        session_expiry = session_owner.get("session_expires_at")
        if session_expiry is not None and (
            type(session_expiry) is not int or final_now >= session_expiry
        ):
            raise Forbidden()
        if final_now >= intent["expires_at"]:
            raise Conflict("oauth_state_unavailable")
        if (
            not isinstance(account, VerifiedAccount)
            or not isinstance(account.remote_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", account.remote_id)
        ):
            raise Conflict("provider_verification_failed")
        reason = _evidence_reason(
            {"platform": "tiktok", "api_mode": "oauth2", "remote_id": account.remote_id},
            account,
            final_now,
        )
        if reason:
            raise Conflict(reason)
        if con.execute(
            "SELECT id FROM publication_connections WHERE tenant_id=? AND platform='tiktok' AND api_mode='oauth2' AND remote_id=?",
            (tenant_id, account.remote_id),
        ).fetchone():
            raise Conflict("connection_already_exists")
        capabilities = canonical_json({"publish": True, "image": True, "video": True})
        con.execute(
            "INSERT INTO publication_connections(tenant_id,platform,api_mode,remote_id,status,version,expires_at,capabilities_json,created_at) VALUES (?,'tiktok','oauth2',?,'active',1,?,?,?)",
            (tenant_id, account.remote_id, account.expires_at, capabilities, final_now),
        )
        cid = db.get_last_insert_id(db_url, con, "publication_connections")
        try:
            envelope = _seal(
                key, key_id, tenant_id, cid, canonical_json(account.credential).encode()
            )
        except (Conflict, InvalidInput):
            # Roll back the new connection too; the consumed intent stays durable.
            raise Conflict("vault_key_unavailable") from None
        con.execute(
            "INSERT INTO publication_connection_vault(tenant_id,connection_id,envelope_json) VALUES (?,?,?)",
            (tenant_id, cid, canonical_json(envelope)),
        )
        con.execute(
            "INSERT INTO publication_connection_details(tenant_id,connection_id,owner_id,remote_name,scopes_json,scope_evidence,verified_at,expiry_state,hold_reason) VALUES (?,?,?,?,?,?,?,?,NULL)",
            (
                tenant_id,
                cid,
                owner_id,
                account.name,
                json.dumps(sorted(set(account.scopes)), separators=(",", ":")),
                account.scope_evidence,
                final_now,
                account.expiry_state,
            ),
        )
        for pid in flow["project_ids"]:
            con.execute(
                "INSERT INTO publication_project_connections(tenant_id,project_id,connection_id) VALUES (?,?,?)",
                (tenant_id, pid, cid),
            )
        return connection_metadata(con, _connection(con, tenant_id, cid))
