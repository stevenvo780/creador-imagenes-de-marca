"""Persistencia de proyectos con scope de empresa explícito."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from webapp import db
from webapp.services.eikon_runner import validate_slug


def create_project(
    db_url: str | Path | None, tenant_id: int, slug: str, name: str, description: str = ""
) -> dict[str, Any]:
    """Crea un proyecto; la unicidad del slug se aplica dentro de la empresa."""
    slug = validate_slug(slug)
    if not name.strip():
        raise ValueError("nombre vacío")
    with db.connect(db_url) as con:
        con.execute(
            "INSERT INTO projects(tenant_id, slug, name, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant_id, slug, name, description, int(time.time())),
        )
        project_id = db.get_last_insert_id(db_url, con, "projects")
        row = con.execute(
            "SELECT * FROM projects WHERE tenant_id = ? AND id = ?", (tenant_id, project_id)
        ).fetchone()
    assert row is not None
    return row


def get_project(
    db_url: str | Path | None, tenant_id: int, project_id: int
) -> dict[str, Any] | None:
    """Lee un proyecto propio, incluyendo los archivados."""
    with db.connect(db_url) as con:
        return con.execute(
            "SELECT * FROM projects WHERE tenant_id = ? AND id = ?", (tenant_id, project_id)
        ).fetchone()


def list_projects(
    db_url: str | Path | None,
    tenant_id: int,
    limit: int = 50,
    cursor: int | None = None,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Paginación por ID estable, sin mezclar empresas ni archivados por defecto."""
    if not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100")
    if cursor is not None and not 0 <= cursor <= 2**63 - 1:
        raise ValueError("cursor fuera de rango")
    sql = "SELECT * FROM projects WHERE tenant_id = ? AND id > ?"
    if not include_archived:
        sql += " AND archived = 0"
    sql += " ORDER BY id LIMIT ?"
    with db.connect(db_url) as con:
        return con.execute(sql, (tenant_id, cursor or 0, limit)).fetchall()


def update_project(
    db_url: str | Path | None, tenant_id: int, project_id: int, changes: dict[str, Any]
) -> dict[str, Any] | None:
    """Actualiza sólo columnas permitidas; archivo lógico conserva las referencias."""
    allowed = {"slug", "name", "description", "archived"}
    if not changes or not changes.keys() <= allowed:
        raise ValueError("campos de proyecto inválidos")
    if any(value is None for value in changes.values()):
        raise ValueError("campos de proyecto no pueden ser null")
    if "slug" in changes:
        validate_slug(changes["slug"])
    if "name" in changes and not changes["name"].strip():
        raise ValueError("nombre vacío")
    if "archived" in changes and changes["archived"] not in (0, 1):
        raise ValueError("archivo debe ser 0 o 1")
    # Los identificadores provienen exclusivamente de la whitelist anterior.
    assignments = ", ".join(f"{key} = ?" for key in changes)
    with db.connect(db_url) as con:
        con.execute(
            f"UPDATE projects SET {assignments} WHERE tenant_id = ? AND id = ?",
            (*changes.values(), tenant_id, project_id),
        )
        return con.execute(
            "SELECT * FROM projects WHERE tenant_id = ? AND id = ?", (tenant_id, project_id)
        ).fetchone()
