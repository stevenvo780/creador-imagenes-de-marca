"""Administración owner de políticas y grants independientes."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from webapp.publications.auth import issue_grant, list_grants, revoke_grant
from webapp.publications.contracts import InvalidInput, PublicationError, positive_integer
from webapp.publications.policies import get_policy, set_policy

from .deps import current_user, get_settings
from .permissions import require_owner_session

router = APIRouter(prefix="/api/v1/publications", tags=["publications"])


def publication_owner(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_owner_session(user)
    return user


async def _body(request: Request) -> dict:
    """Se valida después de resolver owner; errores JSON nunca son traceback."""
    try:
        value = await request.json()
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidInput("invalid_json") from exc


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: StrictStr
    subject: StrictStr
    policy_version: StrictInt
    expires_at: StrictInt


@router.get("/policy")
def get_policy_endpoint(request: Request, user: dict = Depends(publication_owner)) -> dict:
    try:
        return get_policy(get_settings(request).db_url, user["tenant_id"], user["user_id"])
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/policy", status_code=201)
async def set_policy_endpoint(request: Request, user: dict = Depends(publication_owner)) -> dict:
    try:
        payload = await _body(request)
        expected = positive_integer(
            payload.pop("expected_version", None), "invalid_version", allow_zero=True
        )
        return set_policy(
            get_settings(request).db_url, user["tenant_id"], user["user_id"], expected, payload
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.get("/grants")
def list_grants_endpoint(request: Request, user: dict = Depends(publication_owner)) -> dict:
    try:
        return {
            "items": list_grants(get_settings(request).db_url, user["tenant_id"], user["user_id"])
        }
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/grants", status_code=201)
async def issue_grant_endpoint(request: Request, user: dict = Depends(publication_owner)) -> dict:
    try:
        payload = GrantInput.model_validate(await _body(request))
        token, metadata = issue_grant(
            get_settings(request).db_url, user["tenant_id"], user["user_id"], **payload.model_dump()
        )
        return {**metadata, "token": token}
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_grant") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.delete("/grants/{grant_id}", status_code=204)
def revoke_grant_endpoint(
    grant_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    request: Request,
    user: dict = Depends(publication_owner),
) -> Response:
    try:
        revoke_grant(get_settings(request).db_url, user["tenant_id"], user["user_id"], grant_id)
        return Response(status_code=204)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
