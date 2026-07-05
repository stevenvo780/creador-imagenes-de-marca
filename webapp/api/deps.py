"""Dependencias compartidas de la API: settings, usuario actual, paths.

La configuración por aplicación (settings, output_root, axes_config) se guarda
en request.app.state durante create_app(), de modo que los tests puedan inyectar
una BD temporal sin tocar el módulo global.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException, Request, Response

from eikon_core.combinatorial import AxesConfig
from webapp.config import Settings
from webapp.security import create_jwt, decode_jwt
from webapp.storage import get_user
from webapp.storage_backend import StorageBackend


def get_settings(request: Request) -> Settings:
    """Devuelve los Settings de la app (fijados en create_app)."""
    return cast(Settings, request.app.state.settings)


def get_output_root(request: Request) -> Path:
    """Raíz del árbol de salida donde el worker escribe los PNG renderizados."""
    return cast(Path, request.app.state.output_root)


def get_storage(request: Request) -> StorageBackend:
    """Seam de almacenamiento multi-tenant (lectura/empaquetado de assets)."""
    return cast(StorageBackend, request.app.state.storage)


def get_axes_config(request: Request) -> AxesConfig:
    """Catálogo de ejes combinatorios cargado en memoria."""
    return cast(AxesConfig, request.app.state.axes_config)


async def current_user(request: Request, response: Response) -> dict[str, Any]:
    """Resuelve el usuario autenticado desde la cookie JWT httpOnly.

    Lanza 401 si no hay cookie, el token es inválido/expirado, o el usuario
    ya no existe. El dict devuelto incluye tenant_id para el scoping multi-tenant.
    """
    settings = get_settings(request)
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        payload = decode_jwt(token, settings.jwt_secret)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    user = get_user(settings.db_url, int(payload.get("sub", 0)))
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    refreshed_token = create_jwt(
        {"sub": user["user_id"], "tenant_id": user["tenant_id"]},
        settings.jwt_secret,
        settings.jwt_ttl_seconds,
    )
    response.set_cookie(
        settings.cookie_name,
        refreshed_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_ttl_seconds,
    )
    return user
