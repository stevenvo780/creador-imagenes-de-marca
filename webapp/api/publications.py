"""Administración owner de políticas y grants independientes."""

import json
import os
import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from webapp import db
from webapp.publications.auth import issue_grant, list_grants, revoke_grant
from webapp.publications.connections import list_connections, put_connection
from webapp.publications.contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    PublicationError,
    positive_integer,
)
from webapp.publications.oauth import finish_oauth, start_oauth
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


@router.get("/connections")
def list_connections_endpoint(request: Request, user: dict = Depends(publication_owner)) -> dict:
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


def _oauth_runtime(request: Request, platform: str, mode: str):
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
