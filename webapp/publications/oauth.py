"""OAuth ligado a owner/tenant/navegador con reserva durable antes del proveedor."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlencode, urlsplit

from webapp import db

from .connections import MODES, REQUIRED_SCOPES, _connection, connection_metadata, hold_connection
from .contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    canonical_hash,
    canonical_json,
    positive_integer,
)
from .policies import lock_tenant, require_owner
from .vault import seal, unseal


@dataclass(frozen=True)
class OAuthConfig:
    platform: str
    api_mode: str
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uris: tuple[str, ...]
    graph_version: str | None = None
    # La exclusión de gasto de X sigue vigente; Task2 nunca habilita este flag.
    spend_allowed: bool = False

    def public(self) -> dict:
        if self.platform not in MODES or self.api_mode not in MODES[self.platform]:
            raise InvalidInput("invalid_oauth_mode")
        if not self.client_id or not self.client_secret:
            raise Conflict("oauth_not_configured")
        if self.platform in ("facebook", "instagram") and not re.fullmatch(
            r"v[1-9]\d*\.\d+", self.graph_version or ""
        ):
            raise Conflict("oauth_not_configured")
        for uri in self.redirect_uris:
            p = urlsplit(uri)
            if (
                p.scheme != "https"
                or not p.hostname
                or p.username
                or p.password
                or p.fragment
                or "*" in uri
                or any(c.isspace() for c in uri)
            ):
                raise InvalidInput("invalid_redirect_uri")
        return {
            "platform": self.platform,
            "api_mode": self.api_mode,
            "client_id": self.client_id,
            "redirect_uris": list(self.redirect_uris),
            "graph_version": self.graph_version,
        }


@dataclass(frozen=True)
class VerifiedAccount:
    """Resultado privado de lecturas remotas; jamás se acepta desde JSON owner."""

    remote_id: str
    name: str
    scopes: tuple[str, ...]
    expires_at: int | None
    expiry_state: Literal["known", "non_expiring", "unknown"]
    evidence_hosts: tuple[str, ...]
    credential: dict = field(repr=False)
    scope_evidence: Literal["remote_introspection", "token_exchange", "capability_probe"] = (
        "remote_introspection"
    )
    # Solo memoria privada: incluye tokens intermedios y secretos del transporte.
    sensitive_material: tuple[str, ...] = field(default=(), repr=False)


class VerificationClient(Protocol):
    def exchange(self, flow: dict, code: str, verifier: str | None) -> dict: ...
    def verify(self, flow: dict, credential: dict, now: int) -> VerifiedAccount: ...


def _hash(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or not value.isascii():
        raise InvalidInput("invalid_oauth_binding")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def authorization_url(
    config: OAuthConfig, redirect_uri: str, state: str, challenge: str | None
) -> str:
    scopes = sorted(REQUIRED_SCOPES[(config.platform, config.api_mode)])
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": ",".join(scopes),
    }
    if config.platform == "facebook" or config.api_mode == "facebook_login":
        endpoint = f"https://www.facebook.com/{config.graph_version}/dialog/oauth"
    elif config.platform == "instagram":
        endpoint = "https://www.instagram.com/oauth/authorize"
        params["enable_fb_login"] = "0"
        params["force_authentication"] = "1"
    elif config.platform == "tiktok":
        endpoint = "https://www.tiktok.com/v2/auth/authorize/"
        params["client_key"] = params.pop("client_id")
    else:
        endpoint = "https://x.com/i/oauth2/authorize"
        params["scope"] = " ".join([*scopes, "offline.access"])
    if challenge:
        params.update(code_challenge=challenge, code_challenge_method="S256")
    return endpoint + "?" + urlencode(params)


def start_oauth(
    db_url: str | Path | None,
    tenant_id: int,
    owner_id: int,
    platform: str,
    redirect_uri: str,
    now: int,
    *,
    session_binding: str | None = None,
    connection_id: int | None = None,
    config: OAuthConfig | None = None,
    api_mode: str | None = None,
    key: bytes | None = None,
    key_id: str | None = None,
) -> dict:
    """La cookie nonce se crea en la ruta; no se deriva del JWT deslizante."""
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        if config is None:
            raise Conflict("oauth_not_configured")
        public = config.public()
        if platform != config.platform or (api_mode is not None and api_mode != config.api_mode):
            raise InvalidInput("invalid_oauth_mode")
        if redirect_uri not in config.redirect_uris:
            raise InvalidInput("invalid_redirect_uri")
        session_hash = _hash(session_binding)
        positive_integer(now, "invalid_time", allow_zero=True)
        row = _connection(con, tenant_id, connection_id)
        if row["platform"] != config.platform or row["api_mode"] != config.api_mode:
            raise InvalidInput("invalid_oauth_mode")
        verifier = None
        verifier_envelope = None
        if platform == "x":
            verifier = secrets.token_urlsafe(48)
            verifier_envelope = seal(key, key_id, tenant_id, row["id"], verifier.encode())
        state = secrets.token_urlsafe(32)
        flow = {
            **public,
            "connection_id": row["id"],
            "expected_remote_id": row["remote_id"],
            "redirect_uri": redirect_uri,
        }
        # Reconectar retiene e invalida contratos antes de cualquier exchange.
        held = hold_connection(con, tenant_id, owner_id, row["id"], "authorization_pending")
        con.execute(
            "INSERT INTO publication_oauth_states(tenant_id,owner_id,connection_id,connection_version,state_hash,session_hash,config_hash,flow_json,verifier_envelope_json,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                owner_id,
                row["id"],
                held["version"],
                _hash(state),
                session_hash,
                canonical_hash(public),
                canonical_json(flow),
                canonical_json(verifier_envelope) if verifier_envelope else None,
                now,
                now + 600,
            ),
        )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if verifier
        else None
    )
    return {
        "state": state,
        "authorization_url": authorization_url(config, redirect_uri, state, challenge),
        "expires_at": now + 600,
    }


def _evidence_reason(row: dict, account: VerifiedAccount, now: int) -> str | None:
    if not isinstance(account, VerifiedAccount) or not _public_evidence_safe(account):
        return "provider_verification_failed"
    official = {
        "facebook": {"graph.facebook.com"},
        "instagram": {"graph.instagram.com"}
        if row["api_mode"] == "instagram_login"
        else {"graph.facebook.com"},
        "tiktok": {"open.tiktokapis.com"},
        "x": {"api.x.com"},
    }
    if not account.evidence_hosts or set(account.evidence_hosts) != official[row["platform"]]:
        return "provider_verification_failed"
    if account.remote_id != row["remote_id"]:
        return "remote_identity_mismatch"
    if not isinstance(account.name, str) or not account.name.strip() or len(account.name) > 256:
        return "provider_verification_failed"
    if not isinstance(account.scopes, tuple) or any(not isinstance(s, str) for s in account.scopes):
        return "provider_verification_failed"
    if not REQUIRED_SCOPES[(row["platform"], row["api_mode"])].issubset(account.scopes):
        return "insufficient_scopes"
    expiry_reason = _expiry_reason(account, now)
    if expiry_reason:
        return expiry_reason
    if (
        not isinstance(account.credential, dict)
        or not isinstance(account.credential.get("access_token"), str)
        or not account.credential["access_token"]
    ):
        return "provider_verification_failed"
    return None


def _public_evidence_safe(account: VerifiedAccount) -> bool:
    if (
        not isinstance(account.credential, dict)
        or not isinstance(account.scopes, tuple)
        or not isinstance(account.evidence_hosts, tuple)
        or any(not isinstance(h, str) for h in account.evidence_hosts)
        or not isinstance(account.sensitive_material, tuple)
        or any(not isinstance(s, str) for s in account.sensitive_material)
    ):
        return False
    fields = (account.remote_id, account.name, *account.scopes)
    if any(not isinstance(v, str) or any(ord(c) < 32 for c in v) for v in fields):
        return False
    if any(not re.fullmatch(r"[a-z][a-z0-9_.:]{0,100}", scope) for scope in account.scopes):
        return False
    private = [v for v in account.credential.values() if isinstance(v, str) and v]
    private.extend(secret for secret in account.sensitive_material if secret)
    if any(secret in value for secret in private for value in fields):
        return False
    try:
        canonical_json({"name": account.name, "scopes": account.scopes})
    except InvalidInput:
        return False
    return account.scope_evidence in ("remote_introspection", "token_exchange", "capability_probe")


def _expiry_reason(account: VerifiedAccount, now: int) -> str | None:
    if account.expiry_state == "unknown":
        return "token_expiry_unknown"
    if account.expiry_state == "known" and (
        type(account.expires_at) is not int or not 0 < account.expires_at <= 2**63 - 1
    ):
        return "token_expiry_unknown"
    if account.expiry_state == "known" and account.expires_at <= now:
        return "token_expired"
    if account.expiry_state == "non_expiring" and account.expires_at is not None:
        return "token_expiry_unknown"
    if account.expiry_state not in ("known", "non_expiring"):
        return "token_expiry_unknown"
    return None


def _store_verified(
    db_url: str | Path | None,
    tenant_id: int,
    owner_id: int,
    cid: int,
    expected_version: int,
    account: VerifiedAccount | None,
    reason: str | None,
    now: int,
    key: bytes | None,
    key_id: str | None,
) -> dict:
    """Único camino de activación; revalida autoridad y versión tras la red."""
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = _connection(con, tenant_id, cid)
        if row["version"] != expected_version:
            raise Conflict("connection_version_conflict")
        reason = reason or _evidence_reason(row, account, now)
        envelope = None
        if reason is None:
            try:
                envelope = seal(
                    key, key_id, tenant_id, cid, canonical_json(account.credential).encode()
                )
            except (Conflict, InvalidInput):
                reason = "vault_key_unavailable"
        if reason:
            return hold_connection(con, tenant_id, owner_id, cid, reason)
        scopes = sorted(set(account.scopes))
        capabilities = {"publish": True, "image": row["platform"] != "tiktok", "video": True}
        con.execute(
            "INSERT INTO publication_connection_vault(tenant_id,connection_id,envelope_json) VALUES (?,?,?) ON CONFLICT(tenant_id,connection_id) DO UPDATE SET envelope_json=excluded.envelope_json",
            (tenant_id, cid, canonical_json(envelope)),
        )
        con.execute(
            "UPDATE publication_connections SET status='active',version=version+1,expires_at=?,capabilities_json=? WHERE tenant_id=? AND id=?",
            (account.expires_at, canonical_json(capabilities), tenant_id, cid),
        )
        con.execute(
            "INSERT INTO publication_connection_details(tenant_id,connection_id,owner_id,remote_name,scopes_json,scope_evidence,verified_at,expiry_state,hold_reason) VALUES (?,?,?,?,?,?,?,?,NULL) ON CONFLICT(tenant_id,connection_id) DO UPDATE SET owner_id=excluded.owner_id,remote_name=excluded.remote_name,scopes_json=excluded.scopes_json,scope_evidence=excluded.scope_evidence,verified_at=excluded.verified_at,expiry_state=excluded.expiry_state,hold_reason=NULL",
            (
                tenant_id,
                cid,
                owner_id,
                account.name,
                json.dumps(scopes, separators=(",", ":")),
                account.scope_evidence,
                now,
                account.expiry_state,
            ),
        )
        return connection_metadata(con, _connection(con, tenant_id, cid))


def finish_oauth(
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
) -> dict:
    tenant_id, owner_id = session_owner.get("tenant_id"), session_owner.get("user_id")
    if session_owner.get("auth_method") != "session":
        raise Forbidden()
    try:
        state_hash = _hash(state)
        session_hash = _hash(session_owner.get("session_binding"))
    except InvalidInput as exc:
        raise Forbidden() from exc
    positive_integer(now, "invalid_time", allow_zero=True)
    if not provider_error and (
        not isinstance(code, str) or not code or len(code) > 4096 or not code.isascii()
    ):
        raise InvalidInput("invalid_oauth_code")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        row = con.execute(
            "SELECT * FROM publication_oauth_states WHERE tenant_id=? AND owner_id=? AND state_hash=? AND session_hash=?",
            (tenant_id, owner_id, state_hash, session_hash),
        ).fetchone()
        if row is None:
            raise Forbidden()
        current = _connection(con, tenant_id, row["connection_id"])
        changed = con.execute(
            "UPDATE publication_oauth_states SET consumed_at=?,verifier_envelope_json=NULL WHERE tenant_id=? AND owner_id=? AND state_hash=? AND session_hash=? AND consumed_at IS NULL AND expires_at>?",
            (now, tenant_id, owner_id, state_hash, session_hash, now),
        )
        if changed.rowcount != 1:
            raise Conflict("oauth_state_unavailable")
    if current["version"] != row["connection_version"]:
        raise Conflict("connection_version_conflict")
    if provider_error:
        return _store_verified(
            db_url,
            tenant_id,
            owner_id,
            row["connection_id"],
            row["connection_version"],
            None,
            "provider_consent_denied",
            now,
            key,
            key_id,
        )
    # Commit anterior a exchange: ni concurrencia ni error remoto reusan state.
    reason = None
    account = None
    try:
        verifier = (
            unseal(
                key, tenant_id, row["connection_id"], json.loads(row["verifier_envelope_json"])
            ).decode()
            if row["verifier_envelope_json"]
            else None
        )
        flow = json.loads(row["flow_json"])
        credential = client.exchange(flow, code, verifier)
        account = client.verify(flow, credential, now)
    except Conflict as exc:
        reason = (
            exc.code
            if exc.code in ("blocked_budget", "vault_key_unavailable", "oauth_not_configured")
            else "provider_verification_failed"
        )
    except Exception:
        # No registrar excepción/cuerpo remoto, URL, códigos OAuth ni tokens.
        reason = "provider_verification_failed"
    return _store_verified(
        db_url,
        tenant_id,
        owner_id,
        row["connection_id"],
        row["connection_version"],
        account,
        reason,
        now,
        key,
        key_id,
    )


def import_credential(
    db_url: str | Path | None,
    tenant_id: int,
    owner_id: int,
    connection_id: int,
    credential: dict,
    now: int,
    client: VerificationClient,
    *,
    key: bytes | None,
    key_id: str | None,
    dry_run: bool = True,
) -> dict:
    """Import privado: sin exchange, exige lectura real de identidad/scopes."""
    with db.connect(db_url) as con:
        require_owner(con, tenant_id, owner_id)
        row = _connection(con, tenant_id, connection_id)
    flow = {
        "platform": row["platform"],
        "api_mode": row["api_mode"],
        "expected_remote_id": row["remote_id"],
    }
    account = None
    reason = None
    try:
        account = client.verify(flow, credential, now)
    except Conflict as exc:
        reason = (
            exc.code
            if exc.code in ("blocked_budget", "oauth_not_configured")
            else "provider_verification_failed"
        )
    except Exception:
        reason = "provider_verification_failed"
    reason = reason or _evidence_reason(row, account, now)
    if reason is None:
        try:
            seal(key, key_id, tenant_id, connection_id, canonical_json(account.credential).encode())
        except (Conflict, InvalidInput):
            reason = "vault_key_unavailable"
    if dry_run:
        return {
            "dry_run": True,
            "connection_id": connection_id,
            "eligible": reason is None,
            "hold_reason": reason,
        }
    return _store_verified(
        db_url,
        tenant_id,
        owner_id,
        connection_id,
        row["version"],
        account,
        reason,
        now,
        key,
        key_id,
    )
