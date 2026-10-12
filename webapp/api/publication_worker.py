"""Worker separado: claims acotados y capacidades exactas, sin cookies owner."""

import logging
import os
import time
from collections.abc import Callable, Iterator
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from webapp.api.deps import get_settings, get_storage
from webapp.api.publications import _body, publication_owner
from webapp.publications import deliveries, media_delivery
from webapp.publications.auth import publication_worker
from webapp.publications.contracts import Conflict, ProviderResult, PublicationError
from webapp.publications.vault import service_key


def _https(request: Request) -> None:
    if request.url.scheme != "https":
        raise HTTPException(403, detail="https_required")


router = APIRouter(
    prefix="/api/v1/publications/worker",
    tags=["publication-worker"],
    dependencies=[Depends(_https)],
)
calendar_router = APIRouter(prefix="/api/v1/publications/calendar", tags=["publication-calendar"])
media_router = APIRouter(
    prefix="/api/v1/publications/delivery-media", tags=["publication-delivery-media"]
)
_Id = Annotated[int, Path(ge=1, le=2**63 - 1)]


class CapabilityAccessFilter(logging.Filter):
    """Redacción de access log local. No certifica logs administrados/proxy."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                "[publication-media-redacted]"
                if isinstance(arg, str) and "/publications/delivery-media/" in arg
                else arg
                for arg in record.args
            )
        if isinstance(record.msg, str) and "/publications/delivery-media/" in record.msg:
            record.msg = "[publication-media-redacted]"
            record.args = ()
        return True


def install_capability_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, CapabilityAccessFilter) for item in logger.filters):
        logger.addFilter(CapabilityAccessFilter())


def _call[T](fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    try:
        return fn(*args, **kwargs)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartInput(EmptyInput):
    contract_hash: StrictStr


class HoldInput(StartInput):
    reason: Literal[
        "unknown",
        "requires_auth",
        "requires_provider_review",
        "requires_post_consent",
        "blocked_by_budget",
        "unsupported_media",
        "rate_limited",
    ]


class ReportInput(EmptyInput):
    event_key: StrictStr
    result: dict
    confirmation: dict | None = None


class TicketInput(EmptyInput):
    ttl_seconds: StrictInt = 3900


class ReconcileInput(ReportInput):
    confirmation: dict


async def _input(request: Request, schema: type[BaseModel]) -> dict:
    try:
        return schema.model_validate(await _body(request)).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_publication_request") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.post("/claims")
async def claim(
    request: Request, response: Response, principal: dict = Depends(publication_worker)
) -> dict | None:
    await _input(request, EmptyInput)
    _private(response)
    result = _call(deliveries.claim_due, get_settings(request).db_url, principal, int(time.time()))
    return dict(result) if result is not None else None


@router.get("/claims/{claim_id}")
def status(
    claim_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    _private(response)
    return _call(
        deliveries.get_claim, get_settings(request).db_url, principal, claim_id, int(time.time())
    )


@router.post("/claims/{claim_id}/start")
async def start(
    claim_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    body = await _input(request, StartInput)
    _private(response)
    return _call(
        deliveries.start_attempt,
        get_settings(request).db_url,
        principal,
        claim_id,
        body["contract_hash"],
        int(time.time()),
    )


@router.post("/claims/{claim_id}/hold")
async def hold(
    claim_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    body = await _input(request, HoldInput)
    _private(response)
    return _call(
        deliveries.hold_claim,
        get_settings(request).db_url,
        principal,
        claim_id,
        body["contract_hash"],
        body["reason"],
        int(time.time()),
    )


def _binary(content: bytes, mime: str) -> StreamingResponse:
    def chunks() -> Iterator[bytes]:
        for pos in range(0, len(content), 65536):
            yield content[pos : pos + 65536]

    return StreamingResponse(
        chunks(),
        media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(content)),
        },
    )


@router.get("/claims/{claim_id}/original")
def original(
    claim_id: str, request: Request, principal: dict = Depends(publication_worker)
) -> StreamingResponse:
    content, mime = _call(
        deliveries.claim_original,
        get_settings(request).db_url,
        get_storage(request),
        principal,
        claim_id,
        int(time.time()),
    )
    return _binary(content, mime)


@router.post("/claims/{claim_id}/credential")
async def credential(
    claim_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    await _input(request, EmptyInput)
    _private(response)
    if request.url.scheme != "https":
        raise HTTPException(403, detail="https_required")
    key = _call(service_key, get_settings(request).publication_vault_key)
    return _call(
        deliveries.claim_credential,
        get_settings(request).db_url,
        principal,
        claim_id,
        int(time.time()),
        key=key,
    )


@router.post("/attempts/{attempt_id}/reconciliation-credential")
async def reconciliation_credential(
    attempt_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    await _input(request, EmptyInput)
    _private(response)
    key = _call(service_key, get_settings(request).publication_vault_key)
    return _call(
        deliveries.reconciliation_credential,
        get_settings(request).db_url,
        principal,
        attempt_id,
        int(time.time()),
        key=key,
    )


@router.post("/attempts/{attempt_id}/reports")
async def report(
    attempt_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    body = await _input(request, ReportInput)
    _private(response)
    return _call(
        deliveries.report_attempt,
        get_settings(request).db_url,
        principal,
        attempt_id,
        body["event_key"],
        cast(ProviderResult, body["result"]),
        int(time.time()),
        confirmation=body["confirmation"],
    )


def _media_origin() -> str:
    # Activar sólo tras el gate de logging/HTTPS administrado de Task10.
    if os.environ.get("EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED") != "1":
        raise Conflict("media_delivery_release_gate")
    raw = os.environ.get("EIKON_PUBLICATION_MEDIA_ORIGIN", "")
    try:
        origin = urlsplit(raw)
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path not in ("", "/")
            or origin.port not in (None, 443)
        ):
            raise ValueError
    except ValueError as exc:
        raise Conflict("media_delivery_origin_required") from exc
    return raw.rstrip("/")


@router.post("/attempts/{attempt_id}/media-ticket")
async def issue_ticket(
    attempt_id: str,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_worker),
) -> dict:
    body = await _input(request, TicketInput)
    _private(response)
    origin = _call(_media_origin)
    if request.url.scheme != "https":
        raise HTTPException(403, detail="https_required")
    ticket = _call(
        media_delivery.issue_media_ticket,
        get_settings(request).db_url,
        principal,
        attempt_id,
        int(time.time()),
        ttl_seconds=body["ttl_seconds"],
    )
    token = ticket.pop("ticket")
    return ticket | {"url": origin + "/api/v1/publications/delivery-media/" + token}


@router.delete("/attempts/{attempt_id}/media-tickets/{ticket_id}", status_code=204)
def revoke_ticket(
    attempt_id: str, ticket_id: _Id, request: Request, principal: dict = Depends(publication_worker)
) -> Response:
    _call(
        media_delivery.revoke_media_ticket,
        get_settings(request).db_url,
        principal,
        attempt_id,
        ticket_id,
        int(time.time()),
    )
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@media_router.get("/{ticket}")
def serve_ticket(ticket: str, request: Request) -> StreamingResponse:
    _call(_media_origin)
    if request.url.scheme != "https":
        raise HTTPException(403, detail="https_required")
    if request.headers.get("range"):
        raise HTTPException(416, detail="range_not_supported")
    content, mime = _call(
        media_delivery.fetch_media_ticket,
        get_settings(request).db_url,
        get_storage(request),
        ticket,
        int(time.time()),
    )
    return _binary(content, mime)


@calendar_router.get("")
def calendar(
    request: Request,
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    user: dict = Depends(publication_owner),
) -> dict:
    _private(response)
    return _call(
        deliveries.list_calendar,
        get_settings(request).db_url,
        user["tenant_id"],
        user["user_id"],
        limit=limit,
        cursor=cursor,
    )


@calendar_router.post("/revisions/{revision_id}/schedule")
async def schedule(
    revision_id: _Id, request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    await _input(request, EmptyInput)
    _private(response)
    return _call(
        deliveries.schedule_revision,
        get_settings(request).db_url,
        user["tenant_id"],
        revision_id,
        int(time.time()),
    )


@calendar_router.post("/deliveries/{delivery_id}/cancel")
async def cancel(
    delivery_id: _Id, request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    await _input(request, EmptyInput)
    _private(response)
    return _call(
        deliveries.cancel_delivery,
        get_settings(request).db_url,
        user["tenant_id"],
        user["user_id"],
        delivery_id,
        int(time.time()),
    )


@calendar_router.post("/attempts/{attempt_id}/reconcile")
async def reconcile(
    attempt_id: str, request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    body = await _input(request, ReconcileInput)
    _private(response)
    return _call(
        deliveries.reconcile_attempt,
        get_settings(request).db_url,
        user["tenant_id"],
        user["user_id"],
        attempt_id,
        body["event_key"],
        cast(ProviderResult, body["result"]),
        body["confirmation"],
        int(time.time()),
    )


@calendar_router.post("/attempts/{attempt_id}/withdrawal")
async def withdrawal(
    attempt_id: str, request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    body = await _input(request, ReconcileInput)
    _private(response)
    return _call(
        deliveries.reconcile_attempt,
        get_settings(request).db_url,
        user["tenant_id"],
        user["user_id"],
        attempt_id,
        body["event_key"],
        cast(ProviderResult, body["result"]),
        body["confirmation"],
        int(time.time()),
        withdrawn=True,
    )
