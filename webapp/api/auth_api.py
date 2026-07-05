"""Router para gestionar API keys de agentes sin navegador."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from webapp.storage import create_api_key, list_api_keys, revoke_api_key

from .deps import current_user, get_settings

auth_api_router = APIRouter(prefix="/api/v1/auth", tags=["auth-api"])


@auth_api_router.post("/api-keys", status_code=201)
async def create_api_key_endpoint(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Crea una API key nueva para el tenant autenticado."""
    settings = get_settings(request)
    key, row = create_api_key(settings.db_url, int(user["tenant_id"]))
    return {
        "id": row["id"],
        "key": key,
        "created_at": row["created_at"],
    }


@auth_api_router.get("/api-keys")
async def list_api_keys_endpoint(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Lista API keys del tenant sin revelar el secret."""
    settings = get_settings(request)
    rows = list_api_keys(settings.db_url, int(user["tenant_id"]))
    return {
        "keys": [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "revoked": row["revoked_at"] is not None,
            }
            for row in rows
        ]
    }


@auth_api_router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key_endpoint(
    key_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Revoca una API key del tenant autenticado."""
    settings = get_settings(request)
    if not revoke_api_key(settings.db_url, int(user["tenant_id"]), key_id):
        raise HTTPException(status_code=404, detail="key not found")
    return Response(status_code=204)
