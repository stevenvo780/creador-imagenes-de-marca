"""Proyectos privados de la empresa autenticada por sesión."""

from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as FPath
from psycopg.errors import UniqueViolation

from webapp.project_storage import create_project, get_project, list_projects, update_project

from .deps import current_user, get_settings
from .permissions import require_scope
from .schemas import _SQLITE_INT_MAX, ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
_ProjectId = Annotated[int, FPath(ge=1, le=_SQLITE_INT_MAX)]


def project_reader(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """La lectura exige concesión explícita o sesión owner."""
    require_scope(user, "projects:read")
    return user


def project_writer(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Las mutaciones exigen concesión explícita o sesión owner."""
    require_scope(user, "projects:write")
    return user


@router.post("", status_code=201)
def create_project_endpoint(
    payload: ProjectCreate, request: Request, user: dict[str, Any] = Depends(project_writer)
) -> dict[str, Any]:
    try:
        return create_project(
            get_settings(request).db_url,
            user["tenant_id"],
            payload.slug,
            payload.name,
            payload.description,
        )
    except (sqlite3.IntegrityError, UniqueViolation) as exc:
        raise HTTPException(status_code=409, detail="slug ya existe en esta empresa") from exc


@router.get("")
def list_projects_endpoint(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[int | None, Query(ge=0, le=_SQLITE_INT_MAX)] = None,
    include_archived: bool = False,
    user: dict[str, Any] = Depends(project_reader),
) -> dict[str, Any]:
    db_url = get_settings(request).db_url
    rows = list_projects(
        db_url, user["tenant_id"], limit, cursor, include_archived=include_archived
    )
    # Consultar la siguiente fila conserva el límite público de 100.
    more = rows and list_projects(
        db_url, user["tenant_id"], 1, rows[-1]["id"], include_archived=include_archived
    )
    return {"items": rows, "next_cursor": rows[-1]["id"] if more else None}


@router.get("/{project_id}")
def get_project_endpoint(
    project_id: _ProjectId, request: Request, user: dict[str, Any] = Depends(project_reader)
) -> dict[str, Any]:
    row = get_project(get_settings(request).db_url, user["tenant_id"], project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="proyecto no encontrado")
    return row


@router.patch("/{project_id}")
def update_project_endpoint(
    project_id: _ProjectId,
    payload: ProjectUpdate,
    request: Request,
    user: dict[str, Any] = Depends(project_writer),
) -> dict[str, Any]:
    try:
        row = update_project(
            get_settings(request).db_url,
            user["tenant_id"],
            project_id,
            payload.model_dump(exclude_unset=True),
        )
    except (sqlite3.IntegrityError, UniqueViolation) as exc:
        raise HTTPException(status_code=409, detail="slug ya existe en esta empresa") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="proyecto no encontrado")
    return row


@router.post("/{project_id}/archive")
def archive_project_endpoint(
    project_id: _ProjectId, request: Request, user: dict[str, Any] = Depends(project_writer)
) -> dict[str, Any]:
    row = update_project(
        get_settings(request).db_url, user["tenant_id"], project_id, {"archived": 1}
    )
    if row is None:
        raise HTTPException(status_code=404, detail="proyecto no encontrado")
    return row
