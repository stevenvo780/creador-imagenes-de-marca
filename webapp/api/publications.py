"""Administración owner de políticas y grants independientes."""

import json
import os
import secrets
import time
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from webapp import db
from webapp.publications.auth import issue_grant, list_grants, publication_planner, revoke_grant
from webapp.publications.connections import list_connections, put_connection
from webapp.publications.contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    PublicationError,
    positive_integer,
)
from webapp.publications.oauth import OAuthConfig, finish_oauth, start_oauth
from webapp.publications.oauth_providers import OfficialOAuthClient, load_provider_configs
from webapp.publications.policies import get_policy, set_policy
from webapp.publications.vault import service_key

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
def get_policy_endpoint(
    request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
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


@router.get("/connections")
def list_connections_endpoint(
    request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return {
            "items": list_connections(
                get_settings(request).db_url, user["tenant_id"], user["user_id"]
            )
        }
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/connections", status_code=201)
async def put_connection_endpoint(
    request: Request, user: dict = Depends(publication_owner)
) -> dict:
    try:
        return put_connection(
            get_settings(request).db_url, user["tenant_id"], user["user_id"], await _body(request)
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


def _oauth_cookie(request: Request) -> tuple[str, bool]:
    # __Host- sin Domain y Path=/; el callback HTTPS requiere cookie Secure.
    secure = (
        request.url.scheme == "https"
        or get_settings(request).cookie_secure
        or os.environ.get("EIKON_ENV", os.environ.get("ENVIRONMENT", "")).lower()
        in ("prod", "production")
    )
    return ("__Host-eikon_publication_oauth" if secure else "eikon_publication_oauth_dev"), secure


def _oauth_runtime(
    request: Request, platform: str, mode: str
) -> tuple[OAuthConfig, OfficialOAuthClient]:
    configs = getattr(request.app.state, "publication_oauth_configs", None)
    if configs is None:
        configs = load_provider_configs(get_settings(request).publication_oauth_config_file)
    config = configs.get((platform, mode))
    if config is None:
        raise Conflict("oauth_not_configured")
    client = getattr(request.app.state, "publication_oauth_clients", {}).get((platform, mode))
    return config, client or OfficialOAuthClient(config)


class OAuthStartInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    platform: StrictStr
    connection_id: StrictInt
    redirect_uri: StrictStr


@router.post("/oauth/start")
async def start_oauth_endpoint(
    request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    client = None
    try:
        payload = OAuthStartInput.model_validate(await _body(request))
        settings = get_settings(request)
        # Sin configuración, ni catálogo inválido ni cuerpo sensible cambian el error.
        configs = getattr(request.app.state, "publication_oauth_configs", None)
        if configs is None:
            configs = load_provider_configs(settings.publication_oauth_config_file)
        with db.connect(settings.db_url) as con:
            row = con.execute(
                "SELECT api_mode FROM publication_connections WHERE tenant_id=? AND id=?",
                (user["tenant_id"], payload.connection_id),
            ).fetchone()
        if row is None:
            raise NotFound()
        config, client = _oauth_runtime(request, payload.platform, row["api_mode"])
        binding = secrets.token_urlsafe(32)
        try:
            key = service_key(settings.publication_vault_key)
        except Conflict:
            key = None
        result = start_oauth(
            settings.db_url,
            user["tenant_id"],
            user["user_id"],
            payload.platform,
            payload.redirect_uri,
            int(time.time()),
            session_binding=binding,
            connection_id=payload.connection_id,
            config=config,
            key=key,
            key_id=settings.publication_vault_key_id,
        )
        name, secure = _oauth_cookie(request)
        response.set_cookie(
            name, binding, httponly=True, secure=secure, samesite="lax", path="/", max_age=600
        )
        return result
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_oauth_start") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
    finally:
        if isinstance(client, OfficialOAuthClient):
            client.close()


@router.get("/oauth/callback")
def finish_oauth_endpoint(
    request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    client = None
    try:
        from webapp.publications.oauth import _hash

        settings = get_settings(request)
        state = request.query_params.get("state", "")
        name, secure = _oauth_cookie(request)
        binding = request.cookies.get(name)
        if not binding:
            raise Forbidden()
        with db.connect(settings.db_url) as con:
            row = con.execute(
                "SELECT flow_json FROM publication_oauth_states WHERE tenant_id=? AND owner_id=? AND state_hash=?",
                (user["tenant_id"], user["user_id"], _hash(state)),
            ).fetchone()
        if row is None:
            raise Forbidden()
        flow = json.loads(row["flow_json"])
        _, client = _oauth_runtime(request, flow["platform"], flow["api_mode"])
        try:
            key = service_key(settings.publication_vault_key)
        except Conflict:
            key = None
        result = finish_oauth(
            settings.db_url,
            {**user, "session_binding": binding},
            state,
            request.query_params.get("code", ""),
            int(time.time()),
            client,
            key=key,
            key_id=settings.publication_vault_key_id,
            provider_error="error" in request.query_params,
        )
        response.delete_cookie(name, path="/", secure=secure, httponly=True, samesite="lax")
        return result
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
    finally:
        if isinstance(client, OfficialOAuthClient):
            client.close()


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project_id: StrictInt
    brand_id: StrictInt
    objective: StrictStr


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    media_id: StrictInt
    media_kind: StrictStr = "gallery_image"
    caption: StrictStr
    connection_id: StrictInt
    scheduled_at: StrictStr
    policy_version: StrictInt
    channel_metadata: dict


async def _create_campaign(request: Request, tenant_id: int, actor: int | dict) -> dict:
    from webapp.publications.campaigns import create_campaign

    try:
        payload = CampaignInput.model_validate(await _body(request))
        return create_campaign(
            get_settings(request).db_url, tenant_id, actor, **payload.model_dump()
        )
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_campaign") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/campaigns", status_code=201)
async def create_campaign_endpoint(
    request: Request, user: dict = Depends(publication_owner)
) -> dict:
    return await _create_campaign(request, user["tenant_id"], user["user_id"])


@router.post("/planner/campaigns", status_code=201)
async def planner_create_campaign_endpoint(
    request: Request, principal: dict = Depends(publication_planner)
) -> dict:
    return await _create_campaign(request, principal["tenant_id"], principal)


@router.post("/campaigns/{campaign_id}/archive")
def archive_campaign_endpoint(
    campaign_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    request: Request,
    user: dict = Depends(publication_owner),
) -> dict:
    from webapp.publications.campaigns import archive_campaign

    try:
        return archive_campaign(
            get_settings(request).db_url, user["tenant_id"], user["user_id"], campaign_id
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


async def _freeze(request: Request, campaign_id: int, tenant: int, *, actor: int | dict) -> dict:
    from webapp.publications.campaigns import freeze_revision

    try:
        payload = RevisionInput.model_validate(await _body(request))
        return freeze_revision(
            get_settings(request).db_url, tenant, campaign_id, **payload.model_dump(), actor=actor
        )
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_revision") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.post("/campaigns/{campaign_id}/revisions", status_code=201)
async def freeze_revision_endpoint(
    campaign_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    request: Request,
    user: dict = Depends(publication_owner),
) -> dict:
    return await _freeze(request, campaign_id, user["tenant_id"], actor=user["user_id"])


@router.post("/planner/campaigns/{campaign_id}/revisions", status_code=201)
async def planner_freeze_revision_endpoint(
    campaign_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    request: Request,
    principal: dict = Depends(publication_planner),
) -> dict:
    return await _freeze(request, campaign_id, principal["tenant_id"], actor=principal)


@router.get("/revisions/{revision_id}")
def get_revision_endpoint(
    revision_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
) -> dict:
    from webapp.publications.campaigns import get_revision

    try:
        response.headers["Cache-Control"] = "private, no-store"
        return get_revision(get_settings(request).db_url, user["tenant_id"], revision_id)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.get("/planner/candidates")
def list_candidates_endpoint(
    request: Request,
    response: Response,
    cursor: int = 0,
    limit: int = 50,
    principal: dict = Depends(publication_planner),
) -> dict:
    from webapp.publications.campaigns import list_candidates

    try:
        response.headers["Cache-Control"] = "private, no-store"
        return list_candidates(get_settings(request).db_url, principal, cursor, limit)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


def _view(request: Request, response: Response, user: dict, name: str, *args: Any) -> dict:
    from webapp.publications import views

    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    try:
        return cast(
            dict,
            getattr(views, name)(
                get_settings(request).db_url, user["tenant_id"], user["user_id"], *args
            ),
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.get("/overview")
def overview_endpoint(
    request: Request, response: Response, user: dict = Depends(publication_owner)
) -> dict:
    return _view(request, response, user, "overview")


@router.get("/campaigns")
def campaigns_endpoint(
    request: Request,
    response: Response,
    cursor: int = 0,
    limit: int = 50,
    user: dict = Depends(publication_owner),
) -> dict:
    return _view(request, response, user, "campaigns", cursor, limit)


@router.get("/deliveries/{delivery_id}")
def delivery_endpoint(
    delivery_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
) -> dict:
    return _view(request, response, user, "delivery", delivery_id)


@router.get("/revisions/{revision_id}/preview")
def preview_endpoint(
    revision_id: Annotated[int, Path(ge=1)],
    contract_hash: str,
    request: Request,
    user: dict = Depends(publication_owner),
) -> Response:
    from webapp.api.deps import get_storage
    from webapp.publications.views import original

    try:
        content, mime = original(
            get_settings(request).db_url,
            get_storage(request),
            user["tenant_id"],
            user["user_id"],
            revision_id,
            contract_hash,
        )
        return Response(
            content,
            media_type=mime,
            headers={
                "Cache-Control": "private, no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.get("/revisions/{revision_id}/consent")
def consent_status_endpoint(
    revision_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
) -> dict:
    from webapp.publications.consent import status

    response.headers["Cache-Control"] = "private, no-store"
    try:
        return status(get_settings(request).db_url, user["tenant_id"], user["user_id"], revision_id)
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


class CreatorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract_hash: StrictStr


@router.post("/revisions/{revision_id}/creator-info")
async def creator_info_endpoint(
    revision_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
) -> dict:
    from starlette.concurrency import run_in_threadpool

    from webapp.publications.consent import creator_preflight

    response.headers["Cache-Control"] = "private, no-store"
    client = None
    try:
        body = CreatorInput.model_validate(await _body(request))
        _, client = _oauth_runtime(request, "tiktok", "oauth2")
        return await run_in_threadpool(
            creator_preflight,
            get_settings(request).db_url,
            user["tenant_id"],
            user["user_id"],
            revision_id,
            body.contract_hash,
            client,
            service_key(get_settings(request).publication_vault_key),
        )
    except ValidationError as exc:
        raise HTTPException(422, detail="invalid_creator_request") from exc
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
    finally:
        if isinstance(client, OfficialOAuthClient):
            client.close()


@router.post("/revisions/{revision_id}/consent", status_code=201)
async def consent_endpoint(
    revision_id: Annotated[int, Path(ge=1)],
    request: Request,
    response: Response,
    user: dict = Depends(publication_owner),
) -> dict:
    from webapp.publications.consent import record_consent

    response.headers["Cache-Control"] = "private, no-store"
    try:
        return record_consent(
            get_settings(request).db_url,
            user["tenant_id"],
            user["user_id"],
            revision_id,
            await _body(request),
        )
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@router.delete("/consents/{receipt_id}", status_code=204)
def revoke_consent_endpoint(
    receipt_id: Annotated[int, Path(ge=1)],
    request: Request,
    user: dict = Depends(publication_owner),
) -> Response:
    from webapp.publications.consent import revoke

    try:
        revoke(
            get_settings(request).db_url, user["tenant_id"], user["user_id"], "consent", receipt_id
        )
        return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
    except PublicationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc
