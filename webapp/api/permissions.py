"""Autorización explícita para medios privados y operaciones humanas."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException

API_KEY_SCOPES = frozenset(
    {"projects:read", "projects:write", "brands:read", "briefs:write", "media:read", "media:write"}
)


def validate_scopes(scopes: Iterable[str]) -> frozenset[str]:
    """Valida una concesión explícita; no amplía claves heredadas."""
    if isinstance(scopes, (str, bytes)):
        raise ValueError("scopes debe ser una lista de permisos")
    values = list(scopes)
    if any(not isinstance(scope, str) or scope not in API_KEY_SCOPES for scope in values):
        raise ValueError("scope desconocido")
    return frozenset(values)


def require_owner_session(user: dict[str, Any]) -> None:
    """La administración y revisión requieren el rol actual de una sesión."""
    if user.get("auth_method") != "session" or user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Se requiere sesión de propietario")


def require_scope(user: dict[str, Any], scope: str) -> None:
    """Autoriza owner humano o una clave con el permiso exacto conocido."""
    if scope not in API_KEY_SCOPES:
        raise HTTPException(status_code=403, detail="Permiso desconocido")
    if user.get("auth_method") == "session":
        require_owner_session(user)
        return
    if user.get("auth_method") != "api_key" or scope not in user.get("scopes", frozenset()):
        raise HTTPException(status_code=403, detail="Permiso insuficiente")


# Templates exactos registrados por FastAPI, nunca prefijos de URL del cliente.
_LEGACY_READ_SCOPES = {
    ("GET", "/api/v1/brands"): "brands:read",
    ("GET", "/api/v1/brands/{brand_id}"): "brands:read",
    ("GET", "/api/v1/brands/{brand_id}/logo-options"): "brands:read",
    ("GET", "/api/v1/wizard/brands"): "brands:read",
    ("GET", "/api/v1/gallery"): "media:read",
    ("GET", "/api/v1/gallery/{brand_id}"): "media:read",
    ("GET", "/api/v1/batches/{batch_id}"): "media:read",
    ("GET", "/api/v1/batches/{batch_id}/variations"): "media:read",
    ("GET", "/api/v1/batches/{batch_id}/events"): "media:read",
    ("GET", "/api/v1/batches/{batch_id}/plan"): "media:read",
    ("GET", "/api/v1/variations/{variation_id}/file"): "media:read",
    ("POST", "/api/v1/downloads/batch/{batch_id}"): "media:read",
    ("POST", "/api/v1/downloads/zip"): "media:read",
}
_SCOPED_ROUTE_SCOPES = {
    ("POST", "/api/v1/media"): "media:write",
    ("GET", "/api/v1/media"): "media:read",
    ("GET", "/api/v1/media/{media_id}"): "media:read",
    ("GET", "/api/v1/brands/{brand_id}/brief"): "brands:read",
    ("GET", "/api/v1/brands/{brand_id}/reference-logo"): "brands:read",
    ("POST", "/api/v1/brands/{brand_id}/reference-logo"): "media:write",
    ("POST", "/api/v1/generation-briefs"): "briefs:write",
    ("GET", "/api/v1/generation-briefs"): "brands:read",
    ("GET", "/api/v1/generation-briefs/{brief_id}"): "brands:read",
    ("GET", "/api/v1/projects"): "projects:read",
    ("GET", "/api/v1/projects/{project_id}"): "projects:read",
    ("POST", "/api/v1/projects"): "projects:write",
    ("PATCH", "/api/v1/projects/{project_id}"): "projects:write",
    ("POST", "/api/v1/projects/{project_id}/archive"): "projects:write",
    ("POST", "/api/v1/generate"): "media:write",
    ("POST", "/api/v1/batches"): "media:write",
    ("POST", "/api/v1/batches/{batch_id}/variations/upload"): "media:write",
    **_LEGACY_READ_SCOPES,
}

_LEGACY_OWNER_ROUTES = frozenset(
    {
        ("POST", "/api/v1/brands"),
        ("PUT", "/api/v1/brands/{brand_id}"),
        ("DELETE", "/api/v1/brands/{brand_id}"),
        ("POST", "/api/v1/brands/{brand_id}/set-identity"),
        ("DELETE", "/api/v1/variations/{variation_id}"),
        ("POST", "/api/v1/variations/delete"),
        ("POST", "/api/v1/gallery/select"),
    }
)


_KEY_ADMIN_ROUTES = frozenset(
    {
        ("POST", "/api/v1/auth/api-keys"),
        ("GET", "/api/v1/auth/api-keys"),
        ("DELETE", "/api/v1/auth/api-keys/{key_id}"),
    }
)

_AUTHENTICATED_CATALOG_ROUTES = frozenset(
    {
        ("GET", "/auth/me"),
        ("GET", "/api/v1/asset-types"),
        ("GET", "/api/v1/wizard/axes"),
        ("GET", "/api/v1/wizard/asset-types"),
        ("GET", "/api/v1/templates/{name}"),
    }
)


_LEGACY_ROUTES = (
    frozenset(_LEGACY_READ_SCOPES)
    | _LEGACY_OWNER_ROUTES
    | _AUTHENTICATED_CATALOG_ROUTES
    | frozenset(
        {
            ("POST", "/api/v1/generate"),
            ("POST", "/api/v1/batches"),
            ("POST", "/api/v1/batches/{batch_id}/variations/upload"),
        }
    )
)


def require_legacy_route_scope(user: dict[str, Any], method: str, route: str) -> None:
    """Impide usar rutas anteriores para eludir las concesiones nuevas.

    Sólo las claves anteriores (NULL persistido) conservan permisos heredados.
    Toda ruta nueva para claves debe registrarse explícitamente en la matriz
    además de usar su helper. Rutas desconocidas fallan cerradas. Los catálogos
    sin datos de empresa y /auth/me únicamente requieren autenticación.
    """
    if user.get("auth_method") == "session":
        # Una degradación de rol conserva las lecturas heredadas, pero revoca
        # las mutaciones. El principal ya trae el rol vigente de la BD.
        if (method, route) not in _LEGACY_READ_SCOPES and (
            method,
            route,
        ) not in _AUTHENTICATED_CATALOG_ROUTES:
            require_owner_session(user)
        return
    if user.get("legacy_api_key") and (method, route) in _LEGACY_ROUTES:
        return
    scope = _SCOPED_ROUTE_SCOPES.get((method, route))
    if scope is not None:
        require_scope(user, scope)
    elif (method, route) in _LEGACY_OWNER_ROUTES | _KEY_ADMIN_ROUTES:
        require_owner_session(user)
    elif (method, route) not in _AUTHENTICATED_CATALOG_ROUTES:
        raise HTTPException(status_code=403, detail="Ruta no autorizada para esta API key")
