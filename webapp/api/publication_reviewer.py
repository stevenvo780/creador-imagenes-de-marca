"""Bandeja exclusiva de reviewer, sin identidad owner ni claves heredadas."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from webapp.api.deps import get_settings, get_storage
from webapp.api.publications import _body
from webapp.publications.auth import publication_reviewer
from webapp.publications.contracts import PublicationError
from webapp.publications.decisions import (
    deliver_candidate,
    list_reviewer_candidates,
    publication_eligibility,
    submit_evaluation,
)

router = APIRouter(prefix="/api/v1/publications/reviewer", tags=["publication-reviewer"])
_Id = Annotated[int, Path(ge=1, le=2**63 - 1)]


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_contract_hash: StrictStr
    policy_version: StrictInt
    material_hashes: dict
    model_receipt: dict
    response: dict


@router.get("/candidates")
def candidates(
    request: Request,
    response: Response,
    cursor: int = Query(0, ge=0, le=2**63 - 1),
    limit: int = Query(50, ge=1, le=100),
    principal: dict = Depends(publication_reviewer),
) -> dict:
    try:
        response.headers["Cache-Control"] = "private, no-store"
        return list_reviewer_candidates(get_settings(request).db_url, principal, cursor, limit)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.get("/candidates/{revision_id}")
def candidate(
    revision_id: _Id,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_reviewer),
) -> dict:
    try:
        response.headers["Cache-Control"] = "private, no-store"
        data = deliver_candidate(
            get_settings(request).db_url, get_storage(request), principal, revision_id
        )
        data["eligibility"] = publication_eligibility(
            get_settings(request).db_url, principal["tenant_id"], revision_id, int(time.time())
        )
        return data
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/candidates/{revision_id}/evaluations", status_code=201)
async def evaluate(
    revision_id: _Id,
    request: Request,
    response: Response,
    principal: dict = Depends(publication_reviewer),
) -> dict:
    try:
        payload = EvaluationInput.model_validate(await _body(request)).model_dump()
        response.headers["Cache-Control"] = "private, no-store"
        return submit_evaluation(get_settings(request).db_url, principal, revision_id, **payload)
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_evaluation") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
