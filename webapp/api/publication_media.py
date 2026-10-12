"""Ingreso vídeo privado owner/planner, sin ampliar los scopes de galería."""

import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Request,
    Response,
)
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser, parse_options_header

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


MAX_MULTIPART_OVERHEAD = 64 * 1024
MAX_MULTIPART_HEADERS = 8 * 1024


class _VideoUploadLimit(MultiPartException):
    """Error local que el parser cierra antes de escribir el bloque excesivo."""


class _VideoMultipartParser(MultiPartParser):
    def __init__(self, request: Request) -> None:
        super().__init__(
            request.headers,
            _bounded_stream(request),
            max_files=1,
            max_fields=4,
        )
        self.file_bytes = 0
        self.header_bytes = 0
        self.finished = False

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > MAX_VIDEO_BYTES:
                raise _VideoUploadLimit("video_size_limit")
        elif len(self._current_part.data) + end - start > 16384:
            raise MultiPartException("invalid_video_field_size")
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self.finished = True
        super().on_end()

    async def parse(self) -> FormData:
        try:
            form = await super().parse()
            if not self.finished:
                raise MultiPartException("invalid_video_multipart")
            return form
        except BaseException:
            # Incluye partes incompletas que todavía no aparecen en FormData.
            for file in self._files_to_close_on_error:
                file.close()
            raise

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._count_headers(end - start)
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._count_headers(end - start)
        super().on_header_value(data, start, end)

    def _count_headers(self, size: int) -> None:
        self.header_bytes += size
        if self.header_bytes > MAX_MULTIPART_HEADERS:
            raise _VideoUploadLimit("video_request_size_limit")


async def _bounded_stream(request: Request) -> AsyncGenerator[bytes, None]:
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_VIDEO_BYTES + MAX_MULTIPART_OVERHEAD:
            raise _VideoUploadLimit("video_request_size_limit")
        # Un único ASGI event grande no causa una cola de escrituras sin límite.
        for offset in range(0, len(chunk), 64 * 1024):
            yield chunk[offset : offset + 64 * 1024]


class _VideoFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_id: int = Field(ge=1, le=2**63 - 1)
    source: StrictStr = Field(max_length=32)
    provenance: StrictStr = Field(max_length=16384)
    rights: StrictStr = Field(min_length=1, max_length=2000)


_VIDEO_UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        **_VideoFields.model_json_schema()["properties"],
                        "file": {"type": "string", "format": "binary"},
                    },
                    "required": [*_VideoFields.model_fields, "file"],
                    "additionalProperties": False,
                }
            }
        },
    }
}


async def _receive_video(
    request: Request, response: Response, principal: dict, idempotency_key: str, *, planner: bool
) -> dict:
    """No hay body fields FastAPI: las dependencias resuelven auth antes del stream."""
    content_type, parameters = parse_options_header(request.headers.get("content-type", ""))
    boundary = parameters.get(b"boundary", b"")
    if content_type != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
        raise HTTPException(422, detail="invalid_video_multipart")
    try:
        form = await _VideoMultipartParser(request).parse()
    except _VideoUploadLimit as exc:
        raise HTTPException(413, detail=exc.message) from exc
    except MultiPartException as exc:
        raise HTTPException(422, detail="invalid_video_multipart") from exc
    try:
        items = list(form.multi_items())
        if len({name for name, _ in items}) != len(items):
            raise HTTPException(422, detail="invalid_video_request")
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(422, detail="invalid_video_request")
        try:
            fields = _VideoFields.model_validate(
                {name: value for name, value in items if name != "file"}
            )
        except ValidationError as exc:
            raise HTTPException(422, detail="invalid_video_request") from exc
        return await _ingest(
            request,
            response,
            principal,
            file,
            **fields.model_dump(),
            idempotency_key=idempotency_key,
            planner=planner,
        )
    finally:
        await form.close()


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


@router.post("/media/videos", status_code=201, openapi_extra=_VIDEO_UPLOAD_OPENAPI)
async def upload_video(
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
) -> dict:
    return await _receive_video(request, response, user, idempotency_key, planner=False)


@router.post("/planner/media/videos", status_code=201, openapi_extra=_VIDEO_UPLOAD_OPENAPI)
async def planner_upload_video(
    request: Request,
    response: Response,
    principal: dict = Depends(publication_planner),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
) -> dict:
    return await _receive_video(request, response, principal, idempotency_key, planner=True)


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
