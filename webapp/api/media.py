"""Ingreso multipart acotado y catálogo privado; no genera enlaces públicos."""

from __future__ import annotations

import io
import json
import warnings
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from PIL import Image
from starlette.concurrency import run_in_threadpool

from webapp import media_storage
from webapp.api.deps import current_user, get_settings, get_storage
from webapp.api.permissions import require_scope
from webapp.api.schemas import _SQLITE_INT_MAX
from webapp.media_validation import MAX_IMAGE_BYTES, MAX_PROVENANCE_BYTES

router = APIRouter(prefix="/api/v1/media", tags=["media"])
_Id = Annotated[int, Path(ge=1, le=_SQLITE_INT_MAX)]


@router.post("", status_code=201)
async def upload_media(
    request: Request,
    response: Response,
    brief_id: int = Form(..., ge=1, le=_SQLITE_INT_MAX),
    source: str = Form(..., max_length=32),
    provenance: str = Form(..., max_length=MAX_PROVENANCE_BYTES),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_scope(user, "media:write")
    try:
        if len(provenance.encode()) > MAX_PROVENANCE_BYTES:
            raise ValueError("Procedencia excede 16 KiB")
        metadata = json.loads(provenance)
        if not isinstance(metadata, dict):
            raise ValueError("Procedencia debe ser un objeto JSON")
    except (ValueError, RecursionError) as error:
        raise HTTPException(422, "Procedencia inválida") from error
    chunks, byte_size = [], 0
    try:
        while chunk := await file.read(64 * 1024):
            byte_size += len(chunk)
            if byte_size > MAX_IMAGE_BYTES:
                raise HTTPException(413, "Imagen excede 20 MiB")
            chunks.append(chunk)
        content = b"".join(chunks)
        chunks.clear()
        # MIME real se verifica sin confiar en el nombre ni content_type multipart.
        # Sólo cabecera aquí; import_media aplica verify/load y todos los límites.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as header:
                    real_mime = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(header.format or "")
        except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise ValueError("Imagen dañada o insegura") from error
        if real_mime is None or file.content_type != real_mime:
            raise ValueError("MIME declarado diferente del contenido")
        result = await run_in_threadpool(
            media_storage.import_media,
            get_settings(request).db_url,
            get_storage(request),
            user["tenant_id"],
            brief_id,
            idempotency_key,
            content,
            source,
            metadata,
        )
        response.status_code = 200 if result.pop("_replayed") else 201
        response.headers["Cache-Control"] = "private, no-store"
        return result
    except media_storage.MediaConflict as error:
        raise HTTPException(409, {"code": error.code, "retryable": error.retryable}) from error
    except KeyError as error:
        raise HTTPException(404, "encargo no encontrado") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except media_storage.MediaStorageError as error:
        raise HTTPException(
            503, "Importación fallida; puede reintentar la misma solicitud"
        ) from error
    finally:
        await file.close()


@router.get("")
def read_media_list(
    request: Request,
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    cursor: int = Query(0, ge=0, le=_SQLITE_INT_MAX),
    brand_id: int | None = Query(None, ge=1, le=_SQLITE_INT_MAX),
    project_id: int | None = Query(None, ge=1, le=_SQLITE_INT_MAX),
    brief_id: int | None = Query(None, ge=1, le=_SQLITE_INT_MAX),
    source: str | None = Query(None, pattern="^(codex|legacy)$"),
    status: str | None = Query(None, pattern="^(pending_review|approved|rejected|archived)$"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_scope(user, "media:read")
    filters = {
        key: value
        for key, value in {
            "brand_id": brand_id,
            "project_id": project_id,
            "brief_id": brief_id,
            "source": source,
            "status": status,
        }.items()
        if value is not None
    }
    rows = media_storage.list_media(
        get_settings(request).db_url, user["tenant_id"], filters, limit + 1, cursor
    )
    response.headers["Cache-Control"] = "private, no-store"
    return {
        "items": rows[:limit],
        "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
    }


@router.get("/{media_id}")
def read_media(
    media_id: _Id,
    request: Request,
    response: Response,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_scope(user, "media:read")
    result = media_storage.get_media(get_settings(request).db_url, user["tenant_id"], media_id)
    if result is None:
        raise HTTPException(404, "pieza no encontrada")
    response.headers["Cache-Control"] = "private, no-store"
    return result
