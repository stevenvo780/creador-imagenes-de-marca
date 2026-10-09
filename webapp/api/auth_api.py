"""Administración humana de claves limitadas para agentes."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from webapp.storage import create_scoped_api_key, list_api_keys, revoke_api_key

from .deps import current_user, get_settings
from .permissions import require_owner_session, validate_scopes

auth_api_router = APIRouter(prefix="/api/v1/auth", tags=["auth-api"])


class ApiKeyCreate(BaseModel):
    """El tenant siempre procede de la sesión, nunca del cuerpo."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="codex", min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: StrictInt = Field(default=30, ge=1, le=365)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre de clave vacío")
        return value.strip()

    @field_validator("scopes")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        return sorted(validate_scopes(value))


def key_owner(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Las claves API nunca administran otras claves."""
    require_owner_session(user)
    return user


@auth_api_router.post("/api-keys", status_code=201)
async def create_api_key_endpoint(
    request: Request,
    payload: ApiKeyCreate | None = Body(default=None),
    user: dict[str, Any] = Depends(key_owner),
) -> dict[str, Any]:
    """Crea una clave con TTL30 y scopes vacíos cuando el cuerpo está ausente."""
    payload = payload or ApiKeyCreate()
    key, row = create_scoped_api_key(
        get_settings(request).db_url,
        int(user["tenant_id"]),
        payload.name,
        payload.scopes,
        int(time.time()) + payload.expires_in_days * 86400,
    )
    return {
        **{field: row[field] for field in ("id", "name", "scopes", "created_at", "expires_at")},
        "key": key,
    }


@auth_api_router.get("/api-keys")
async def list_api_keys_endpoint(
    request: Request,
    user: dict[str, Any] = Depends(key_owner),
) -> dict[str, Any]:
    """Lista metadata por empresa sin revelar secretos."""
    rows = list_api_keys(get_settings(request).db_url, int(user["tenant_id"]))
    return {
        "keys": [
            {
                **{
                    field: row[field]
                    for field in ("id", "name", "scopes", "created_at", "expires_at")
                },
                "revoked": row["revoked_at"] is not None,
            }
            for row in rows
        ]
    }


@auth_api_router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key_endpoint(
    key_id: int,
    request: Request,
    user: dict[str, Any] = Depends(key_owner),
) -> Response:
    """Revoca una API key de la empresa del propietario."""
    if not revoke_api_key(get_settings(request).db_url, int(user["tenant_id"]), key_id):
        raise HTTPException(status_code=404, detail="API key no encontrada")
    return Response(status_code=204)
