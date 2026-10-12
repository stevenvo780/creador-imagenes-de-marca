"""Campañas propias y contratos inmutables de candidatos, sin permisos remotos."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

from webapp import brand_briefs, db
from webapp.media_storage import _current_public

from .connections import connection_metadata
from .contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    MediaKind,
    NotFound,
    canonical_hash,
    canonical_json,
    normalize_schedule,
    positive_integer,
)
from .policies import (
    _normalize_source,
    latest_policy,
    lock_tenant,
    require_active_policy,
    require_owner,
)


class ChannelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    publication_format: Literal["feed", "reel"] = "feed"
    links: list[StrictStr] = Field(default_factory=list, max_length=20)
    sources: list[StrictStr] = Field(default_factory=list, max_length=20)
    context: StrictStr = Field(default="", max_length=12000)
    rights: StrictStr = Field(default="", max_length=2000)
    privacy: StrictStr | None = Field(default=None, max_length=80)
    commercial_content: StrictBool | None = None
    branded_content: StrictBool | None = None
    platform_consent_receipt: StrictStr | None = Field(default=None, max_length=2000)


def require_planner(con: db.DualConnection, principal: dict) -> dict:
    """Revalida principal resuelto, grant revocado y política antes de cada operación."""
    if not isinstance(principal, dict) or principal.get("role") != "planner":
        raise Forbidden()
    tenant = positive_integer(principal.get("tenant_id"), "invalid_tenant")
    grant = positive_integer(principal.get("grant_id"), "invalid_grant")
    row = con.execute(
        "SELECT * FROM publication_grants WHERE tenant_id=? AND id=?", (tenant, grant)
    ).fetchone()
    now = int(time.time())
    if (
        row is None
        or row["role"] != "planner"
        or row["subject"] != principal.get("subject")
        or row["policy_version"] != principal.get("policy_version")
        or row["revoked_at"] is not None
        or not row["created_at"] <= now < row["expires_at"]
    ):
        raise Forbidden()
    return require_active_policy(con, tenant, row["policy_version"], now)


def _actor(
    con: db.DualConnection, tenant_id: int, actor: int | dict, project_id: int, brand_id: int
) -> str:
    if isinstance(actor, dict):
        if actor.get("tenant_id") != tenant_id:
            raise Forbidden()
        policy = json.loads(require_planner(con, actor)["payload_json"])
        if project_id not in policy["project_ids"] or brand_id not in policy["product_ids"]:
            raise Forbidden()
        return f"planner:{actor['grant_id']}"
    require_owner(con, tenant_id, positive_integer(actor, "invalid_actor"))
    return f"owner:{actor}"


def create_campaign(
    db_url: str | Path | None,
    tenant_id: int,
    actor: int | dict,
    project_id: int,
    brand_id: int,
    objective: str,
) -> dict:
    for value in (project_id, brand_id):
        positive_integer(value, "invalid_catalog_id")
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 12000:
        raise InvalidInput("invalid_objective")
    canonical_json({"objective": objective})
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        who = _actor(con, tenant_id, actor, project_id, brand_id)
        try:
            identity = brand_briefs._snapshot(con, tenant_id, brand_id)
        except KeyError as exc:
            raise NotFound() from exc
        if identity["project"]["id"] != project_id:
            raise NotFound()
        if identity["project"]["archived"]:
            raise Conflict("project_archived")
        con.execute(
            "INSERT INTO publication_campaigns(tenant_id,project_id,brand_id,objective,actor,created_at) VALUES (?,?,?,?,?,?)",
            (tenant_id, project_id, brand_id, objective, who, int(time.time())),
        )
        cid = db.get_last_insert_id(db_url, con, "publication_campaigns")
        return _campaign(con, tenant_id, cid)


def _campaign(con: db.DualConnection, tenant: int, cid: int) -> dict:
    positive_integer(cid, "invalid_campaign")
    row = con.execute(
        "SELECT * FROM publication_campaigns WHERE tenant_id=? AND id=?", (tenant, cid)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def archive_campaign(
    db_url: str | Path | None, tenant_id: int, owner_id: int, campaign_id: int
) -> dict:
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        require_owner(con, tenant_id, owner_id)
        _campaign(con, tenant_id, campaign_id)
        con.execute(
            "UPDATE publication_campaigns SET archived=1 WHERE tenant_id=? AND id=?",
            (tenant_id, campaign_id),
        )
        return _campaign(con, tenant_id, campaign_id)


def _media(con: db.DualConnection, tenant: int, kind: str, mid: int) -> dict:
    positive_integer(mid, "invalid_media")
    if kind not in ("gallery_image", "publication_video"):
        raise InvalidInput("invalid_media_kind")
    table = "media_assets" if kind == "gallery_image" else "publication_video_media"
    row = con.execute(f"SELECT * FROM {table} WHERE tenant_id=? AND id=?", (tenant, mid)).fetchone()
    if row is None:
        raise NotFound()
    return row


def _metadata(value: dict) -> dict:
    try:
        result = ChannelMetadata.model_validate(value).model_dump()
    except ValidationError as exc:
        raise InvalidInput("invalid_channel_metadata") from exc
    canonical_json(result)
    for link in result["links"]:
        _normalize_source(link)  # valida seguridad sin reescribir el enlace exacto
    result["sources"] = [_normalize_source(source) for source in result["sources"]]
    if len(canonical_json(result).encode()) > 32768:
        raise InvalidInput("metadata_too_large")
    return result


def _authorize_revision(
    con: db.DualConnection,
    tenant_id: int,
    actor: int | dict | None,
    campaign: dict,
    connection_id: int,
    policy_version: int,
) -> None:
    if actor is None:
        return
    _actor(con, tenant_id, actor, campaign["project_id"], campaign["brand_id"])
    if isinstance(actor, dict):
        rules = json.loads(require_planner(con, actor)["payload_json"])
        if (
            policy_version != actor["policy_version"]
            or connection_id not in rules["connection_ids"]
        ):
            raise Forbidden()


def freeze_revision(
    db_url: str | Path | None,
    tenant_id: int,
    campaign_id: int,
    media_id: int,
    caption: str,
    connection_id: int,
    scheduled_at: str,
    policy_version: int,
    channel_metadata: dict,
    *,
    media_kind: MediaKind = "gallery_image",
    actor: int | dict | None = None,
) -> dict:
    """Operación interna tenant autenticado; routers resuelven owner/planner primero."""
    if (
        not isinstance(caption, str)
        or not caption.strip()
        or len(caption) > 12000
        or "\x00" in caption
    ):
        raise InvalidInput("invalid_caption")
    canonical_json({"caption": caption})
    metadata = _metadata(channel_metadata)
    scheduled = normalize_schedule(scheduled_at)
    positive_integer(connection_id, "invalid_connection")
    positive_integer(policy_version, "invalid_version")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        campaign = _campaign(con, tenant_id, campaign_id)
        _authorize_revision(con, tenant_id, actor, campaign, connection_id, policy_version)
        if campaign["archived"]:
            raise Conflict("campaign_archived")
        media = _media(con, tenant_id, media_kind, media_id)
        if media["status"] not in ("pending_review", "approved"):
            raise Conflict("media_unavailable")
        if (media["project_id"], media["brand_id"]) != (
            campaign["project_id"],
            campaign["brand_id"],
        ):
            raise Conflict("media_campaign_mismatch")
        current = brand_briefs._snapshot(con, tenant_id, campaign["brand_id"])
        if current["project"]["archived"]:
            raise Conflict("project_archived")
        connection = con.execute(
            "SELECT * FROM publication_connections WHERE tenant_id=? AND id=?",
            (tenant_id, connection_id),
        ).fetchone()
        if connection is None:
            raise NotFound()
        account = connection_metadata(con, connection)
        if campaign["project_id"] not in account["project_ids"]:
            raise Forbidden()
        policy = con.execute(
            "SELECT * FROM publication_policies WHERE tenant_id=? AND version=?",
            (tenant_id, policy_version),
        ).fetchone()
        if policy is None:
            raise Conflict("policy_required")
        rules = json.loads(policy["payload_json"])
        brief = con.execute(
            "SELECT * FROM generation_briefs WHERE tenant_id=? AND id=?",
            (tenant_id, media["brief_id"]),
        ).fetchone()
        if brief is None:
            raise NotFound()
        snapshot = {
            "contract_version": 1,
            "tenant_id": tenant_id,
            "project_id": campaign["project_id"],
            "brand_id": campaign["brand_id"],
            "campaign_id": campaign_id,
            "campaign_objective": campaign["objective"],
            "brand_version": media["brand_version"],
            "identity": json.loads(brief["snapshot_json"]),
            "identity_hash": media["snapshot_hash"],
            "brief": {
                k: brief[k]
                for k in (
                    "id",
                    "prompt",
                    "width",
                    "height",
                    "snapshot_hash",
                    "created_at",
                    "expires_at",
                )
            },
            "media": {
                "kind": media_kind,
                **{
                    k: media[k]
                    for k in (
                        "id",
                        "sha256",
                        "mime",
                        "width",
                        "height",
                        "byte_size",
                        "source",
                        "status",
                    )
                },
                "provenance": json.loads(media["provenance_json"]),
            },
            "visual_review": {"approval_current": False, "reviews": []},
            "caption": caption,
            "channel_metadata": metadata,
            "connection": account,
            "destination": f"{account['platform']}:{account['remote_id']}",
            "scheduled_at_utc": scheduled,
            "policy_version": policy_version,
            "policy_hash": policy["payload_hash"],
            "policy_timezone": rules["timezone"],
            "scheduled_local_date": datetime.fromtimestamp(scheduled, UTC)
            .astimezone(ZoneInfo(rules["timezone"]))
            .date()
            .isoformat(),
            "expires_at_utc": scheduled + rules["window_minutes"] * 60,
        }
        if media_kind == "gallery_image":
            visual = _current_public(con, media)
            snapshot["visual_review"] = {k: visual[k] for k in ("approval_current", "reviews")}
        else:
            snapshot["media"].update(
                {k: media[k] for k in ("codec", "audio_codec", "duration_seconds", "fps", "rights")}
            )
        raw = canonical_json(snapshot)
        con.execute(
            "INSERT INTO publication_revisions(tenant_id,campaign_id,media_kind,gallery_image_id,video_media_id,connection_id,policy_version,scheduled_at_utc,contract_hash,frozen_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                campaign_id,
                media_kind,
                media_id if media_kind == "gallery_image" else None,
                media_id if media_kind == "publication_video" else None,
                connection_id,
                policy_version,
                scheduled,
                canonical_hash(snapshot),
                raw,
                int(time.time()),
            ),
        )
        rid = db.get_last_insert_id(db_url, con, "publication_revisions")
        return _revision(con, tenant_id, rid)


def _eligibility(con: db.DualConnection, snapshot: dict, now: int | None = None) -> list[str]:
    now = int(time.time()) if now is None else now
    tenant = snapshot["tenant_id"]
    reasons = []
    campaign = _campaign(con, tenant, snapshot["campaign_id"])
    if campaign["archived"]:
        reasons.append("campaign_archived")
    try:
        current = brand_briefs._snapshot(con, tenant, snapshot["brand_id"])
        if current["project"]["archived"]:
            reasons.append("project_archived")
        if canonical_hash(current) != snapshot["identity_hash"]:
            reasons.append("identity_changed")
    except KeyError:
        reasons.append("identity_unavailable")
    media = _media(con, tenant, snapshot["media"]["kind"], snapshot["media"]["id"])
    if media["status"] not in ("approved", "pending_review"):
        reasons.append("media_unavailable")
    if media["sha256"] != snapshot["media"]["sha256"]:
        reasons.append("media_changed")
    row = con.execute(
        "SELECT * FROM publication_connections WHERE tenant_id=? AND id=?",
        (tenant, snapshot["connection"]["id"]),
    ).fetchone()
    account = connection_metadata(con, row) if row else None
    if account is None or any(
        account[k] != snapshot["connection"][k] for k in ("version", "platform", "remote_id")
    ):
        reasons.append("connection_changed")
    if (
        account is None
        or account["status"] != "active"
        or account["verified_at"] is None
        or account["scope_evidence"] == "unverified"
        or account["expiry_state"] == "unknown"
        or (account["expires_at"] is not None and account["expires_at"] <= now)
    ):
        reasons.append("connection_unavailable")
    if account and snapshot["project_id"] not in account["project_ids"]:
        reasons.append("connection_project_unavailable")
    reasons.extend(_policy_reasons(con, snapshot, now=now))
    platform = snapshot["connection"]["platform"]
    if platform == "x":
        reasons.append("blocked_budget")
    if platform == "tiktok":
        # El texto del planner no acredita consentimiento ni auditoría externa.
        reasons.extend(("needs_platform_consent", "needs_platform_audit"))
    return list(dict.fromkeys(reasons))


def _policy_reasons(con: db.DualConnection, snapshot: dict, now: int | None = None) -> list[str]:
    now = int(time.time()) if now is None else now
    tenant = snapshot["tenant_id"]
    reasons = []
    policy = latest_policy(con, tenant)
    if (
        policy is None
        or policy["version"] != snapshot["policy_version"]
        or policy["payload_hash"] != snapshot["policy_hash"]
    ):
        reasons.append("policy_changed")
    if policy:
        rules = json.loads(policy["payload_json"])
        try:
            require_active_policy(con, tenant, policy["version"], now)
        except (Conflict, Forbidden):
            reasons.append("policy_unavailable")
        if (
            snapshot["project_id"] not in rules["project_ids"]
            or snapshot["brand_id"] not in rules["product_ids"]
            or snapshot["connection"]["id"] not in rules["connection_ids"]
        ):
            reasons.append("outside_policy_scope")
        if not snapshot["channel_metadata"]["sources"] or any(
            s not in rules["allowed_sources"] for s in snapshot["channel_metadata"]["sources"]
        ):
            reasons.append("sources_not_authorized")
        if not snapshot["channel_metadata"]["rights"] and not snapshot["media"].get("rights"):
            reasons.append("rights_evidence_required")
    return reasons


def _revision(con: db.DualConnection, tenant: int, rid: int, now: int | None = None) -> dict:
    row = con.execute(
        "SELECT * FROM publication_revisions WHERE tenant_id=? AND id=?", (tenant, rid)
    ).fetchone()
    if row is None:
        raise NotFound()
    snapshot = json.loads(row["frozen_json"])
    return {
        "id": row["id"],
        "tenant_id": tenant,
        "campaign_id": row["campaign_id"],
        "created_at": row["created_at"],
        "contract_hash": row["contract_hash"],
        "frozen_json": row["frozen_json"],
        "snapshot": snapshot,
        "eligibility_reasons": _eligibility(con, snapshot, now=now),
    }


def get_revision(db_url: str | Path | None, tenant_id: int, revision_id: int) -> dict:
    positive_integer(revision_id, "invalid_revision")
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        return _revision(con, tenant_id, revision_id)


def list_candidates(
    db_url: str | Path | None, principal: dict, cursor: int = 0, limit: int = 50
) -> dict:
    positive_integer(cursor, "invalid_cursor", allow_zero=True)
    positive_integer(limit, "invalid_limit")
    if limit > 100:
        raise InvalidInput("invalid_limit")
    with db.connect(db_url) as con:
        tenant = positive_integer(principal.get("tenant_id"), "invalid_tenant")
        lock_tenant(con, tenant)
        policy = json.loads(require_planner(con, principal)["payload_json"])
        # SQL scope previo a paginar: los proyectos fuera del grant no filtran resultados.
        placeholders = ",".join("?" for _ in policy["project_ids"])
        products = ",".join("?" for _ in policy["product_ids"])
        rows = con.execute(
            f"SELECT r.id FROM publication_revisions r JOIN publication_campaigns c ON c.tenant_id=r.tenant_id AND c.id=r.campaign_id WHERE r.tenant_id=? AND r.id>? AND c.project_id IN ({placeholders}) AND c.brand_id IN ({products}) ORDER BY r.id LIMIT ?",
            (tenant, cursor, *policy["project_ids"], *policy["product_ids"], limit + 1),
        ).fetchall()
        return {
            "items": [_revision(con, tenant, r["id"]) for r in rows[:limit]],
            "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
        }
