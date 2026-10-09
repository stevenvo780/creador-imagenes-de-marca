"""Revisión humana, promoción legacy y descarga privada por tenant."""

from __future__ import annotations

import hashlib
import io
import json
import time
import warnings
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import Path as ApiPath
from PIL import Image

from webapp import brand_briefs, db, media_storage
from webapp.api.deps import current_user, get_settings, get_storage
from webapp.api.permissions import require_owner_session, require_scope
from webapp.api.schemas import _SQLITE_INT_MAX, MediaPromotionRequest, MediaReviewRequest
from webapp.media_validation import validate_image
from webapp.storage_backend.base import StorageBackend

router = APIRouter(prefix="/api/v1/media", tags=["media"])
_Id = Annotated[int, ApiPath(ge=1, le=_SQLITE_INT_MAX)]
_PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def review_media(
    db_url: str | Path | None,
    tenant_id: int,
    media_id: int,
    user_id: int,
    decision: str,
    expected_sha256: str,
    expected_brand_version: int,
    reason: str,
) -> dict[str, Any]:
    """Append-only: bloquea identidad/media/rol antes de confirmar una decisión."""
    if decision not in {"approved", "rejected"} or len(reason) > 4000:
        raise ValueError("Revisión inválida")
    if decision == "rejected" and not reason.strip():
        raise ValueError("El rechazo requiere motivo")
    with db.connect(db_url) as con:
        media_storage._begin(con)
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?", (tenant_id, media_id)
        ).fetchone()
        if not row or row["status"] not in media_storage.PUBLIC_MEDIA_STATUSES:
            raise KeyError("pieza no encontrada")
        # Orden de ingest: brief SHARE -> brand SHARE -> project SHARE -> media UPDATE.
        suffix = " FOR SHARE" if con.dialect == "postgres" else ""
        brief = con.execute(
            "SELECT * FROM generation_briefs WHERE tenant_id = ? AND id = ?" + suffix,
            (tenant_id, row["brief_id"]),
        ).fetchone()
        if brief is None:
            raise media_storage.MediaConflict("identity_changed")
        try:
            snapshot = brand_briefs._snapshot(con, tenant_id, row["brand_id"])
        except KeyError as error:
            raise media_storage.MediaConflict("identity_changed") from error
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?"
            + (" FOR UPDATE" if con.dialect == "postgres" else ""),
            (tenant_id, media_id),
        ).fetchone()
        if not row or row["status"] not in media_storage.PUBLIC_MEDIA_STATUSES:
            raise KeyError("pieza no encontrada")
        owner = con.execute(
            "SELECT role FROM users WHERE tenant_id = ? AND id = ?" + suffix, (tenant_id, user_id)
        ).fetchone()
        if not owner or owner["role"] != "owner":
            raise PermissionError("Se requiere propietario vigente")
        if row["status"] == "archived":
            raise media_storage.MediaConflict("asset_archived")
        if snapshot["project"]["archived"]:
            raise media_storage.MediaConflict("project_archived")
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if (
            hashlib.sha256(canonical.encode()).hexdigest() != row["snapshot_hash"]
            or brief["snapshot_hash"] != row["snapshot_hash"]
            or snapshot["brand_version"] != row["brand_version"]
        ):
            raise media_storage.MediaConflict("identity_changed")
        if expected_sha256 != row["sha256"] or expected_brand_version != row["brand_version"]:
            raise media_storage.MediaConflict("version_mismatch")
        now = int(time.time())
        con.execute(
            "INSERT INTO asset_reviews(tenant_id, media_id, sha256, brand_version, decision, "
            "reason, reviewer_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                media_id,
                row["sha256"],
                row["brand_version"],
                decision,
                reason,
                user_id,
                now,
            ),
        )
        review_id = db.get_last_insert_id(db_url, con, "asset_reviews")
        con.execute(
            "UPDATE media_assets SET status = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
            (decision, now, tenant_id, media_id),
        )
        return {
            "id": review_id,
            "sha256": row["sha256"],
            "brand_version": row["brand_version"],
            "decision": decision,
            "reason": reason,
            "reviewer_id": user_id,
            "created_at": now,
        }


def promote_variation(
    db_url: str | Path | None,
    storage: StorageBackend,
    tenant_id: int,
    variation_id: int,
) -> dict[str, Any]:
    """Copia validada; selected/score no participan en la revisión humana."""
    with db.connect(db_url) as con:
        variation = con.execute(
            "SELECT * FROM variations WHERE tenant_id = ? AND id = ?", (tenant_id, variation_id)
        ).fetchone()
    if not variation or not variation["output_path"]:
        raise KeyError("variación no encontrada")
    try:
        content = storage.open(tenant_id, storage.relative_key(tenant_id, variation["output_path"]))
    except FileNotFoundError as error:
        raise KeyError("archivo no encontrado") from error
    except ValueError as error:
        raise ValueError("Origen legacy fuera de scope") from error
    except Exception as error:
        raise media_storage.MediaStorageError("No se pudo leer el original") from error
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as header:
                width, height = header.size
        validate_image(content, width, height)
    except (OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise ValueError("Imagen legacy dañada o insegura") from error
    with db.connect(db_url) as con:
        media_storage._begin(con)
        if con.dialect == "postgres":
            lock_key = int.from_bytes(
                hashlib.sha256(f"{tenant_id}:{variation_id}".encode()).digest()[:8],
                "big",
                signed=True,
            )
            con.execute("SELECT pg_advisory_xact_lock(?)", (lock_key,))
        origin = con.execute(
            "SELECT brief_id FROM media_variation_origins WHERE tenant_id = ? AND variation_id = ?",
            (tenant_id, variation_id),
        ).fetchone()
        if origin:
            brief_id = origin["brief_id"]
        else:
            snapshot = brand_briefs._snapshot(con, tenant_id, variation["brand_id"])
            if snapshot["project"]["archived"]:
                raise media_storage.MediaConflict("project_archived")
            canonical = json.dumps(
                snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            now = int(time.time())
            con.execute(
                "INSERT INTO generation_briefs(tenant_id, brand_id, project_id, brand_version, "
                "prompt, width, height, snapshot_json, snapshot_hash, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    variation["brand_id"],
                    snapshot["project"]["id"],
                    snapshot["brand_version"],
                    "Promoción de variación legacy para revisión humana",
                    width,
                    height,
                    canonical,
                    hashlib.sha256(canonical.encode()).hexdigest(),
                    now,
                    now + 168 * 3600,
                ),
            )
            brief_id = db.get_last_insert_id(db_url, con, "generation_briefs")
            con.execute(
                "INSERT INTO media_variation_origins(tenant_id, variation_id, brief_id) "
                "VALUES (?, ?, ?)",
                (tenant_id, variation_id, brief_id),
            )
    return media_storage._import_media(
        db_url,
        storage,
        tenant_id,
        brief_id,
        f"legacy:{variation_id}",
        content,
        "legacy",
        {"variation_id": variation_id, "origin": "legacy_variation"},
        legacy=True,
    )


def _raise_media_error(error: Exception) -> None:
    if isinstance(error, media_storage.MediaConflict):
        raise HTTPException(409, {"code": error.code, "retryable": error.retryable}) from error
    if isinstance(error, PermissionError):
        raise HTTPException(403, "Se requiere propietario vigente") from error
    if isinstance(error, KeyError):
        raise HTTPException(404, "pieza u origen no encontrado") from error
    if isinstance(error, ValueError):
        raise HTTPException(422, str(error)) from error
    raise HTTPException(503, "Almacenamiento temporalmente no disponible") from error


@router.post("/from-variation", status_code=201)
def promote_endpoint(
    payload: MediaPromotionRequest,
    request: Request,
    response: Response,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_scope(user, "media:write")
    try:
        result = promote_variation(
            get_settings(request).db_url,
            get_storage(request),
            user["tenant_id"],
            payload.variation_id,
        )
    except (KeyError, ValueError, media_storage.MediaStorageError) as error:
        _raise_media_error(error)
        raise  # unreachable
    response.status_code = 200 if result.pop("_replayed") else 201
    response.headers.update(_PRIVATE_HEADERS)
    return result


@router.post("/{media_id}/reviews", status_code=201)
def review_endpoint(
    media_id: _Id,
    payload: MediaReviewRequest,
    request: Request,
    response: Response,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_owner_session(user)
    try:
        result = review_media(
            get_settings(request).db_url,
            user["tenant_id"],
            media_id,
            user["user_id"],
            payload.decision,
            payload.expected_sha256,
            payload.expected_brand_version,
            payload.reason,
        )
    except (KeyError, ValueError, PermissionError) as error:
        _raise_media_error(error)
        raise
    response.headers.update(_PRIVATE_HEADERS)
    return result


def _download(request: Request, user: dict[str, Any], media_id: int, thumbnail: bool) -> Response:
    require_scope(user, "media:read")
    with db.connect(get_settings(request).db_url) as con:
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ? "
            "AND status IN ('pending_review', 'approved', 'rejected', 'archived')",
            (user["tenant_id"], media_id),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "pieza no encontrada")
    try:
        content = get_storage(request).open(
            user["tenant_id"], row["thumbnail_key"] if thumbnail else row["original_key"]
        )
    except FileNotFoundError as error:
        raise HTTPException(404, "archivo no encontrado") from error
    except Exception as error:
        raise HTTPException(503, "Almacenamiento temporalmente no disponible") from error
    headers = dict(_PRIVATE_HEADERS)
    if not thumbnail:
        extension = "png" if row["mime"] == "image/png" else "jpg"
        headers["Content-Disposition"] = f'attachment; filename="media-{media_id}.{extension}"'
    return Response(content, media_type="image/png" if thumbnail else row["mime"], headers=headers)


@router.get("/{media_id}/download")
def download_endpoint(
    media_id: _Id, request: Request, user: dict[str, Any] = Depends(current_user)
) -> Response:
    return _download(request, user, media_id, False)


@router.get("/{media_id}/thumbnail")
def thumbnail_endpoint(
    media_id: _Id, request: Request, user: dict[str, Any] = Depends(current_user)
) -> Response:
    return _download(request, user, media_id, True)
