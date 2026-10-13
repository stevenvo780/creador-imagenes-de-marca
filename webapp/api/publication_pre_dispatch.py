"""Original worker attestation and owner-only closure, with private responses."""

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from webapp.api.deps import get_settings
from webapp.api.publications import publication_owner
from webapp.publications.auth import publication_worker
from webapp.publications.contracts import PublicationError
from webapp.publications.pre_dispatch import attest_before_dispatch, close_before_dispatch

router = APIRouter(prefix="/api/v1/publications", tags=["publication-pre-dispatch"])


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value: dict = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = child
    return value


def _invalid_constant(value: str) -> None:
    raise ValueError("invalid_json_constant")


async def _body(request: Request) -> dict:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 16384:
            raise HTTPException(422, detail="pre_dispatch_body_too_large")
    try:
        value = json.loads(
            content, object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(422, detail="invalid_pre_dispatch_json") from None


def _https(request: Request) -> None:
    if request.url.scheme != "https":
        raise HTTPException(403, detail="https_required")


@router.post(
    "/worker/attempts/{attempt_id}/pre-dispatch-attestations",
    status_code=201,
    dependencies=[Depends(_https)],
)
async def attest(
    attempt_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return attest_before_dispatch(
            get_settings(request).db_url,
            principal,
            attempt_id,
            await _body(request),
            int(time.time()),
        )
    except PublicationError as error:
        raise HTTPException(error.status_code, detail=error.code) from error


@router.post("/attempts/{attempt_id}/close-before-dispatch")
async def close(
    attempt_id: str, request: Request, response: Response, owner: dict = Depends(publication_owner)
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return close_before_dispatch(
            get_settings(request).db_url,
            owner["tenant_id"],
            owner["user_id"],
            attempt_id,
            await _body(request),
            int(time.time()),
        )
    except PublicationError as error:
        raise HTTPException(error.status_code, detail=error.code) from error
