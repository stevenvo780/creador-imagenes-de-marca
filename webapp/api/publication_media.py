"""Ingreso vídeo privado owner/planner, sin ampliar los scopes de galería."""

import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool

from webapp import db
from webapp.api.deps import get_settings, get_storage
from webapp.api.publications import publication_owner
from webapp.publications.auth import publication_planner
from webapp.publications.campaigns import require_planner
from webapp.publications.contracts import PublicationError
from webapp.publications.media import MAX_VIDEO_BYTES, import_video, resolve_video
from webapp.publications.policies import require_owner

router = APIRouter(prefix="/api/v1/publications", tags=["publication-media"])
_Id = Annotated[int, Path(ge=1, le=2**63 - 1)]


async def _ingest(
    request: Request,
    response: Response,
    principal: dict,
    file: UploadFile,
    brief_id: int,
    source: str,
    provenance: str,
    rights: str,
    idempotency_key: str,
    *,
    planner: bool,
) -> dict:
    try:
        settings = get_settings(request)
        tenant = principal["tenant_id"]
        with db.connect(settings.db_url) as con:
            if planner:
                rules = json.loads(require_planner(con, principal)["payload_json"])
                job = con.execute(
                    "SELECT project_id,brand_id FROM generation_briefs WHERE tenant_id=? AND id=?",
                    (tenant, brief_id),
                ).fetchone()
                if job is None:
                    raise HTTPException(404, detail="not_found")
                if (
                    job["project_id"] not in rules["project_ids"]
                    or job["brand_id"] not in rules["product_ids"]
                ):
                    raise HTTPException(403, detail="forbidden")
            else:
                require_owner(con, tenant, principal["user_id"])
        if len(provenance.encode()) > 16384:
            raise HTTPException(422, detail="invalid_video_provenance")
        try:
            metadata = json.loads(provenance)
        except (ValueError, RecursionError) as exc:
            raise HTTPException(422, detail="invalid_video_provenance") from exc
        chunks, size = [], 0
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_BYTES:
                raise HTTPException(413, detail="video_size_limit")
            chunks.append(chunk)
        content = b"".join(chunks)
        result = await run_in_threadpool(
            import_video,
            settings.db_url,
            get_storage(request),
            tenant,
            brief_id,
            idempotency_key,
            content,
            file.content_type or "",
            source,
            metadata,
            rights,
            actor=principal if planner else principal["user_id"],
        )
        response.status_code = 200 if result.pop("_replayed") else 201
        response.headers["Cache-Control"] = "private, no-store"
        return result
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
    finally:
        await file.close()


@router.post("/media/videos", status_code=201)
async def upload_video(
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
    brief_id: int = Form(..., ge=1, le=2**63 - 1),
    source: str = Form(..., max_length=32),
    provenance: str = Form(..., max_length=16384),
    rights: str = Form(..., min_length=1, max_length=2000),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    file: UploadFile = File(...),
) -> dict:
    return await _ingest(
        request,
        response,
        user,
        file,
        brief_id,
        source,
        provenance,
        rights,
        idempotency_key,
        planner=False,
    )


@router.post("/planner/media/videos", status_code=201)
async def planner_upload_video(
    request: Request,
    response: Response,
    principal: dict = Depends(publication_planner),
    brief_id: int = Form(..., ge=1, le=2**63 - 1),
    source: str = Form(..., max_length=32),
    provenance: str = Form(..., max_length=16384),
    rights: str = Form(..., min_length=1, max_length=2000),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    file: UploadFile = File(...),
) -> dict:
    return await _ingest(
        request,
        response,
        principal,
        file,
        brief_id,
        source,
        provenance,
        rights,
        idempotency_key,
        planner=True,
    )


@router.get("/media/videos/{media_id}/download")
def download_video(
    media_id: _Id, request: Request, user: dict = Depends(publication_owner)
) -> Response:
    try:
        content = resolve_video(
            get_settings(request).db_url, get_storage(request), user["tenant_id"], media_id
        )
        return Response(
            content,
            media_type="video/mp4",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
