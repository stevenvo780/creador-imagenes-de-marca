"""Consentimiento exacto TikTok; sólo el importador privado aporta pruebas externas.

El importador es una frontera de confianza operativa, no atestación criptográfica.
No se expone por HTTP. El controlador comprueba evidencias reales en Task10.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError

from webapp import db

from .contracts import Conflict, Forbidden, InvalidInput, NotFound, canonical_hash, canonical_json
from .policies import lock_tenant, require_active_policy, require_owner

DBUrl = str | Path | None


class CreatorClient(Protocol):
    def _request(self, method: str, url: str, *, token: str) -> dict: ...


Privacy = Literal["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]
_REF = r"^[A-Za-z0-9_.:-]{1,128}$"
_SHA = r"^[a-f0-9]{64}$"


class ProviderProof(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    proof_key: StrictStr = Field(pattern=_REF)
    contract_hash: StrictStr = Field(pattern=_SHA)
    media_sha256: StrictStr = Field(pattern=_SHA)
    normalized_destination: StrictStr
    connection_version: StrictInt
    expires_at: StrictInt
    verified_domain_prefix: StrictStr
    domain_proof_ref: StrictStr = Field(pattern=_REF)
    domain_proof_sha256: StrictStr = Field(pattern=_SHA)
    provider_review_ref: StrictStr = Field(pattern=_REF)
    provider_review_sha256: StrictStr = Field(pattern=_SHA)
    content_eligibility_ref: StrictStr = Field(pattern=_REF)
    content_eligibility_sha256: StrictStr = Field(pattern=_SHA)
    public_audit_ref: StrictStr | None = Field(default=None, pattern=_REF)
    public_audit_sha256: StrictStr | None = Field(default=None, pattern=_SHA)
    provenance_ref: StrictStr = Field(pattern=_REF)


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract_hash: StrictStr = Field(pattern=_SHA)
    creator_id: StrictInt = Field(gt=0)
    privacy_level: Privacy
    disable_comment: StrictBool
    disable_duet: StrictBool
    disable_stitch: StrictBool
    brand_content_toggle: StrictBool
    brand_organic_toggle: StrictBool
    is_aigc: StrictBool
    music_acknowledged: StrictBool
    consent_confirmed: StrictBool


def _parse(schema: type[BaseModel], payload: dict) -> dict:
    try:
        return schema.model_validate(payload).model_dump()
    except ValidationError as exc:
        raise InvalidInput("invalid_post_consent") from exc


def _revision(con: db.DualConnection, tenant: int, rid: int, now: int) -> tuple[dict, dict]:
    row = con.execute(
        "SELECT * FROM publication_revisions WHERE tenant_id=? AND id=?", (tenant, rid)
    ).fetchone()
    if not row:
        raise NotFound()
    s = json.loads(row["frozen_json"])
    if s["connection"]["platform"] != "tiktok":
        raise Conflict("tiktok_revision_required")
    if canonical_hash(s) != row["contract_hash"]:
        raise Conflict("contract_changed")
    connection = con.execute(
        "SELECT * FROM publication_connections WHERE tenant_id=? AND id=?",
        (tenant, row["connection_id"]),
    ).fetchone()
    if (
        not connection
        or connection["status"] != "active"
        or any(connection[k] != s["connection"][k] for k in ("version", "platform", "remote_id"))
        or (connection["expires_at"] is not None and now >= connection["expires_at"])
    ):
        raise Conflict("connection_changed")
    table = "media_assets" if row["media_kind"] == "gallery_image" else "publication_video_media"
    media = con.execute(
        f"SELECT sha256,status FROM {table} WHERE tenant_id=? AND id=?", (tenant, s["media"]["id"])
    ).fetchone()
    if (
        not media
        or media["sha256"] != s["media"]["sha256"]
        or media["status"] not in ("pending_review", "approved")
    ):
        raise Conflict("media_changed")
    newer = con.execute(
        "SELECT id FROM publication_revisions WHERE tenant_id=? AND campaign_id=? AND connection_id=? AND media_kind=? AND id>? AND (gallery_image_id=? OR video_media_id=?) LIMIT 1",
        (
            tenant,
            row["campaign_id"],
            row["connection_id"],
            row["media_kind"],
            rid,
            row["gallery_image_id"],
            row["video_media_id"],
        ),
    ).fetchone()
    if newer or now >= s["expires_at_utc"]:
        raise Conflict("consent_revision_stale")
    return row, s


def _binding(row: dict, snapshot: dict) -> dict:
    return {
        "contract_hash": row["contract_hash"],
        "media_sha256": snapshot["media"]["sha256"],
        "normalized_destination": snapshot["destination"],
        "connection_version": snapshot["connection"]["version"],
    }


def _valid_record(
    con: db.DualConnection,
    tenant: int,
    record: dict,
    kind: str | None,
    binding: dict,
    now: int,
    *,
    check_expiry: bool = True,
) -> dict:
    require_owner(con, tenant, record["owner_id"])
    if (
        kind
        and con.execute(
            "SELECT record_id FROM publication_consent_revocations WHERE tenant_id=? AND kind=? AND record_id=?",
            (tenant, kind, record["id"]),
        ).fetchone()
    ):
        raise Conflict("consent_revoked")
    value = json.loads(record["payload_json"])
    if any(value.get(k) != v for k, v in binding.items()) or (
        check_expiry and value["expires_at"] <= now
    ):
        raise Conflict("consent_stale")
    return dict(value)


def import_provider_proof(
    db_url: DBUrl, tenant: int, owner: int, revision_id: int, payload: dict, now: int | None = None
) -> int:
    """Sólo controlador privado: verifica refs/hashes reales antes de invocar."""
    now = int(time.time()) if now is None else now
    value = _parse(ProviderProof, payload)
    try:
        p = urlsplit(value["verified_domain_prefix"])
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username
            or p.password
            or p.query
            or p.fragment
            or p.port not in (None, 443)
            or p.path != "/api/v1/publications/delivery-media/"
        ):
            raise ValueError
    except ValueError as exc:
        raise InvalidInput("invalid_domain_proof") from exc
    if bool(value["public_audit_ref"]) != bool(value["public_audit_sha256"]):
        raise InvalidInput("invalid_public_audit")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        row, s = _revision(con, tenant, revision_id, now)
        if (
            any(value[k] != v for k, v in _binding(row, s).items())
            or not now < value["expires_at"] <= s["expires_at_utc"]
        ):
            raise Conflict("proof_binding_mismatch")
        existing = con.execute(
            "SELECT * FROM publication_provider_proofs WHERE tenant_id=? AND proof_key=?",
            (tenant, value["proof_key"]),
        ).fetchone()
        if existing:
            _valid_record(con, tenant, existing, "proof", _binding(row, s), now)
            if (
                existing["revision_id"] != revision_id
                or existing["owner_id"] != owner
                or existing["payload_hash"] != canonical_hash(value)
            ):
                raise Conflict("proof_key_conflict")
            return int(existing["id"])
        con.execute(
            "INSERT INTO publication_provider_proofs(tenant_id,revision_id,owner_id,proof_key,payload_json,payload_hash,created_at) VALUES (?,?,?,?,?,?,?)",
            (
                tenant,
                revision_id,
                owner,
                value["proof_key"],
                canonical_json(value),
                canonical_hash(value),
                now,
            ),
        )
        return db.get_last_insert_id(db_url, con, "publication_provider_proofs")


def revoke(db_url: DBUrl, tenant: int, owner: int, kind: str, record_id: int) -> None:
    table = {"proof": "publication_provider_proofs", "consent": "publication_post_consents"}.get(
        kind
    )
    if table is None:
        raise InvalidInput("invalid_revocation")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        if not con.execute(
            f"SELECT id FROM {table} WHERE tenant_id=? AND id=?", (tenant, record_id)
        ).fetchone():
            raise NotFound()
        con.execute(
            "INSERT INTO publication_consent_revocations(tenant_id,kind,record_id,created_at) VALUES (?,?,?,?) ON CONFLICT(tenant_id,kind,record_id) DO NOTHING",
            (tenant, kind, record_id, int(time.time())),
        )


def fetch_creator_info(client: CreatorClient, credential: dict) -> dict:
    # Transporte oficial acotado ya usado por OAuth; jamás recibe URL del navegador.
    return client._request(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        token=credential["access_token"],
    )


def creator_preflight(
    db_url: DBUrl,
    tenant: int,
    owner: int,
    rid: int,
    expected_hash: str,
    client: CreatorClient,
    key: bytes,
) -> dict:
    from .deliveries import _credential

    now = int(time.time())
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        row, s = _revision(con, tenant, rid, now)
        if row["contract_hash"] != expected_hash:
            raise Conflict("contract_changed")
        binding = _binding(row, s)
        credential = _credential(con, tenant, row["connection_id"], key)
    # Sin red lenta dentro del lock. No persistir el cuerpo remoto.
    raw = fetch_creator_info(client, credential)
    try:
        data = raw["data"]
        options = data["privacy_level_options"]
        allowed = {
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "FOLLOWER_OF_CREATOR",
            "SELF_ONLY",
        }
        if (
            not isinstance(options, list)
            or not options
            or any(not isinstance(x, str) or x not in allowed for x in options)
        ):
            raise ValueError
        restrictions = {
            k: data[k] for k in ("comment_disabled", "duet_disabled", "stitch_disabled")
        }
        if any(type(v) is not bool for v in restrictions.values()):
            raise ValueError
        value = binding | {
            "privacy_level_options": options,
            **restrictions,
            "creator_receipt_sha256": canonical_hash(raw),
            "expires_at": min(now + 300, s["expires_at_utc"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise Conflict("creator_info_unavailable") from exc
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        current, snapshot = _revision(con, tenant, rid, int(time.time()))
        if _binding(current, snapshot) != binding:
            raise Conflict("connection_changed")
        con.execute(
            "INSERT INTO publication_creator_receipts(tenant_id,revision_id,owner_id,payload_json,created_at) VALUES (?,?,?,?,?)",
            (tenant, rid, owner, canonical_json(value), now),
        )
        cid = db.get_last_insert_id(db_url, con, "publication_creator_receipts")
    return {"creator_id": cid, **value}


def authority(con: db.DualConnection, tenant: int, rid: int, now: int) -> dict:
    """Autoridad actual bajo el lock del llamador; no red ni transacciones anidadas."""
    row, s = _revision(con, tenant, rid, now)
    require_active_policy(con, tenant, s["policy_version"], now)
    receipt = con.execute(
        "SELECT * FROM publication_post_consents WHERE tenant_id=? AND revision_id=? ORDER BY id DESC LIMIT 1",
        (tenant, rid),
    ).fetchone()
    if not receipt:
        raise Conflict("needs_platform_consent")
    binding = _binding(row, s)
    value = _valid_record(con, tenant, receipt, "consent", binding, now)
    proof = con.execute(
        "SELECT * FROM publication_provider_proofs WHERE tenant_id=? AND id=? AND revision_id=?",
        (tenant, receipt["proof_id"], rid),
    ).fetchone()
    creator = con.execute(
        "SELECT * FROM publication_creator_receipts WHERE tenant_id=? AND id=? AND revision_id=?",
        (tenant, receipt["creator_id"], rid),
    ).fetchone()
    if not proof or not creator:
        raise Conflict("needs_platform_audit")
    p = _valid_record(con, tenant, proof, "proof", binding, now)
    # La frescura de creator_info limita la confirmación, no el horario consentido.
    # El worker reconsulta opciones actuales antes del inicio fuera de este lock.
    c = _valid_record(con, tenant, creator, None, binding, now, check_expiry=False)
    _choices(s, value, c, p)
    return {
        k: value[k]
        for k in (
            "confirmed",
            "tenant_id",
            "revision_id",
            "contract_hash",
            "normalized_destination",
            "media_sha256",
            "consent_id",
            "expires_at",
            "privacy_level",
            "privacy_level_options",
            "disable_comment",
            "disable_duet",
            "disable_stitch",
            "brand_content_toggle",
            "brand_organic_toggle",
            "is_aigc",
            "music_acknowledged",
            "creator_receipt_sha256",
            "verified_domain_prefix",
            "domain_proof_ref",
            "provider_review_ref",
            "content_eligibility_ref",
            "public_audit_ref",
        )
    }


def _choices(s: dict, value: dict, creator: dict, proof: dict) -> None:
    m = s["channel_metadata"]
    for flag in ("disable_comment", "disable_duet", "disable_stitch", "is_aigc"):
        if type(m.get(flag)) is not bool or m[flag] != value[flag]:
            raise Conflict("new_revision_required")
    provenance = s["media"].get("provenance", {})
    # Declaración explícita persistida durante ingest; no inferimos por nombre/logo.
    if (
        provenance.get("tool") == "image_gen" or provenance.get("ai_generated") is True
    ) and not value["is_aigc"]:
        raise Conflict("aigc_disclosure_required")
    if (
        m["privacy"] != value["privacy_level"]
        or type(m["commercial_content"]) is not bool
        or type(m["branded_content"]) is not bool
        or m["commercial_content"] != value["brand_organic_toggle"]
        or m["branded_content"] != value["brand_content_toggle"]
    ):
        raise Conflict("new_revision_required")
    if value["privacy_level"] not in creator["privacy_level_options"] or (
        value["brand_content_toggle"] and value["privacy_level"] == "SELF_ONLY"
    ):
        raise InvalidInput("invalid_privacy")
    for a, b in (
        ("disable_comment", "comment_disabled"),
        ("disable_duet", "duet_disabled"),
        ("disable_stitch", "stitch_disabled"),
    ):
        if creator[b] and not value[a]:
            raise InvalidInput("interaction_not_available")
    if value["privacy_level"] != "SELF_ONLY" and not proof["public_audit_ref"]:
        raise Conflict("needs_platform_audit")


def record_consent(db_url: DBUrl, tenant: int, owner: int, rid: int, payload: dict) -> dict:
    value = _parse(ConsentInput, payload)
    if not value["music_acknowledged"] or not value["consent_confirmed"]:
        raise InvalidInput("consent_required")
    now = int(time.time())
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        row, s = _revision(con, tenant, rid, now)
        if row["contract_hash"] != value["contract_hash"]:
            raise Conflict("contract_changed")
        binding = _binding(row, s)
        creator = con.execute(
            "SELECT * FROM publication_creator_receipts WHERE tenant_id=? AND id=? AND revision_id=? AND owner_id=?",
            (tenant, value["creator_id"], rid, owner),
        ).fetchone()
        proof = con.execute(
            "SELECT * FROM publication_provider_proofs WHERE tenant_id=? AND revision_id=? ORDER BY id DESC LIMIT 1",
            (tenant, rid),
        ).fetchone()
        if not creator:
            raise Conflict("creator_info_required")
        if not proof:
            raise Conflict("needs_platform_audit")
        c = _valid_record(con, tenant, creator, None, binding, now)
        p = _valid_record(con, tenant, proof, "proof", binding, now)
        _choices(s, value, c, p)
        policy = require_active_policy(con, tenant, s["policy_version"], now)
        deadlines = [p["expires_at"], s["expires_at_utc"], policy["expires_at"]]
        if s["connection"]["expires_at"] is not None:
            deadlines.append(s["connection"]["expires_at"])
        stored = (
            binding
            | value
            | {
                k: p[k]
                for k in (
                    "verified_domain_prefix",
                    "domain_proof_ref",
                    "provider_review_ref",
                    "content_eligibility_ref",
                    "public_audit_ref",
                )
            }
            | {
                "tenant_id": tenant,
                "revision_id": rid,
                "confirmed": True,
                "privacy_level_options": c["privacy_level_options"],
                "creator_receipt_sha256": c["creator_receipt_sha256"],
                "expires_at": min(deadlines),
            }
        )
        # Identificador estable antes de insertar; no deriva de texto del owner.
        import secrets

        stored["consent_id"] = "consent:" + secrets.token_hex(16)
        con.execute(
            "INSERT INTO publication_post_consents(tenant_id,revision_id,owner_id,creator_id,proof_id,payload_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (tenant, rid, owner, creator["id"], proof["id"], canonical_json(stored), now),
        )
        receipt_id = db.get_last_insert_id(db_url, con, "publication_post_consents")
        return {"receipt_id": receipt_id, "consent": authority(con, tenant, rid, now)}


def status(db_url: DBUrl, tenant: int, owner: int, rid: int) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant)
        require_owner(con, tenant, owner)
        _revision(con, tenant, rid, int(time.time()))
        try:
            result = authority(con, tenant, rid, int(time.time()))
            row = con.execute(
                "SELECT id FROM publication_post_consents WHERE tenant_id=? AND revision_id=? ORDER BY id DESC LIMIT 1",
                (tenant, rid),
            ).fetchone()
            return {"consent": result, "receipt_id": row["id"] if row else None, "reasons": []}
        except (Conflict, Forbidden) as exc:
            return {"consent": None, "reasons": [exc.code]}


def eligibility_reasons(con: db.DualConnection, snapshot: dict, now: int) -> list[str]:
    row = con.execute(
        "SELECT id FROM publication_revisions WHERE tenant_id=? AND contract_hash=? ORDER BY id DESC LIMIT 1",
        (snapshot["tenant_id"], canonical_hash(snapshot)),
    ).fetchone()
    if not row:
        return ["needs_platform_consent", "needs_platform_audit"]
    try:
        authority(con, snapshot["tenant_id"], row["id"], now)
        return []
    except (Conflict, Forbidden, NotFound, InvalidInput):
        return ["needs_platform_consent", "needs_platform_audit"]


def claim_authority(con: db.DualConnection, row: dict, now: int, *, bind: bool = False) -> dict:
    """El primer GET fija el recibo; start jamás cambia ese binding."""
    if row["state"] != "reserved" or row["started_at"] is not None:
        raise Conflict("claim_not_reserved")
    result = authority(con, row["tenant_id"], row["revision_id"], now)
    if any(
        result[k] != row[k] for k in ("contract_hash", "normalized_destination", "media_sha256")
    ):
        raise Conflict("consent_binding_mismatch")
    receipt = con.execute(
        "SELECT id FROM publication_post_consents WHERE tenant_id=? AND revision_id=? ORDER BY id DESC LIMIT 1",
        (row["tenant_id"], row["revision_id"]),
    ).fetchone()
    assert receipt is not None
    pinned = con.execute(
        "SELECT receipt_id FROM publication_claim_consents WHERE tenant_id=? AND claim_id=?",
        (row["tenant_id"], row["claim_id"]),
    ).fetchone()
    if pinned is None and bind:
        con.execute(
            "INSERT INTO publication_claim_consents(tenant_id,claim_id,receipt_id,created_at) VALUES (?,?,?,?)",
            (row["tenant_id"], row["claim_id"], receipt["id"], now),
        )
    elif pinned is None or pinned["receipt_id"] != receipt["id"]:
        raise Conflict("consent_receipt_changed")
    return result


def claim_consent(db_url: DBUrl, principal: dict, claim_id: str, now: int) -> dict | None:
    from .deliveries import bound_claim

    with db.connect(db_url) as con:
        lock_tenant(con, principal["tenant_id"])
        row = bound_claim(con, principal, claim_id, now, active=True)
        try:
            return claim_authority(con, row, now, bind=True)
        except (Conflict, Forbidden, NotFound, InvalidInput):
            return None
