"""Encargos Codex y referencias originales autenticadas de identidad."""

from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from webapp import brand_briefs
from webapp.api.deps import current_user, get_settings, get_storage
from webapp.api.permissions import require_owner_session, require_scope
from webapp.api.schemas import _SQLITE_INT_MAX

router = APIRouter(prefix="/api/v1", tags=["generation-briefs"])
_Id = Annotated[int, Path(ge=1, le=_SQLITE_INT_MAX)]


class BriefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand_id: int = Field(ge=1, le=_SQLITE_INT_MAX)
    prompt: str = Field(min_length=1, max_length=12000)
    width: int = Field(ge=256, le=8192)
    height: int = Field(ge=256, le=8192)
    expires_in_hours: int = Field(default=24, ge=1, le=168)

    @model_validator(mode="after")
    def valid(self) -> BriefCreate:
        if not self.prompt.strip() or self.width * self.height > 40_000_000:
            raise ValueError("prompt o dimensiones inválidos")
        return self


@router.get("/brands/{brand_id}/brief")
def brand_brief(
    brand_id: _Id, request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    require_scope(user, "brands:read")
    try:
        return brand_briefs.snapshot_brand(
            get_settings(request).db_url, user["tenant_id"], brand_id
        )
    except KeyError as error:
        raise HTTPException(404, "marca no encontrada") from error


@router.post("/generation-briefs", status_code=201)
def create_brief(
    payload: BriefCreate, request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    require_scope(user, "briefs:write")
    try:
        return brand_briefs.create_generation_brief(
            get_settings(request).db_url,
            user["tenant_id"],
            payload.brand_id,
            payload.prompt,
            payload.width,
            payload.height,
            int(time.time()) + payload.expires_in_hours * 3600,
        )
    except KeyError as error:
        raise HTTPException(404, "marca no encontrada") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/generation-briefs")
def list_briefs(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: int = Query(0, ge=0, le=_SQLITE_INT_MAX),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_scope(user, "brands:read")
    rows = brand_briefs.list_generation_briefs(
        get_settings(request).db_url, user["tenant_id"], limit + 1, cursor
    )
    return {
        "items": rows[:limit],
        "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
    }


@router.get("/generation-briefs/{brief_id}")
def get_brief(
    brief_id: _Id, request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    require_scope(user, "brands:read")
    result = brand_briefs.get_generation_brief(
        get_settings(request).db_url, user["tenant_id"], brief_id
    )
    if result is None:
        raise HTTPException(404, "encargo no encontrado")
    return result


@router.post("/brands/{brand_id}/reference-logo", status_code=201)
async def upload_logo(
    brand_id: _Id,
    request: Request,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    require_owner_session(user)
    content = await file.read(brand_briefs.LOGO_MAX_BYTES + 1)
    if len(content) > brand_briefs.LOGO_MAX_BYTES:
        raise HTTPException(413, "logo excede 5 MiB")
    try:
        return brand_briefs.save_reference_logo(
            get_settings(request).db_url, user["tenant_id"], brand_id, content, get_storage(request)
        )
    except KeyError as error:
        raise HTTPException(404, "marca no encontrada") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/brands/{brand_id}/reference-logo")
def read_logo(
    brand_id: _Id,
    request: Request,
    sha256: str | None = Query(None, pattern=r"^[a-f0-9]{64}$"),
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    require_scope(user, "brands:read")
    row = brand_briefs.get_reference_logo(
        get_settings(request).db_url, user["tenant_id"], brand_id, sha256
    )
    if row is None:
        raise HTTPException(404, "logo no encontrado")
    try:
        content = get_storage(request).open(user["tenant_id"], row["storage_key"])
    except FileNotFoundError as error:
        raise HTTPException(404, "logo no encontrado") from error
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'; script-src 'none'; style-src 'unsafe-inline'",
        "Content-Disposition": 'inline; filename="reference-logo"',
    }
    return Response(content, media_type=row["content_type"], headers=headers)
