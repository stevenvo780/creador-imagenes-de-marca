"""Migraciones de proyectos privadas, idempotentes y transaccionales."""

from __future__ import annotations

import time
from pathlib import Path

from webapp import db

PROJECTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 slug TEXT NOT NULL,
 name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
 created_at INTEGER NOT NULL,
 UNIQUE(tenant_id, slug)
)
"""

_PROJECTS_VERSION = "projects_v1"


def _brand_columns(con: db.DualConnection) -> set[str]:
    """Introspección de una tabla fija; ningún identificador viene del cliente."""
    if con.dialect == "sqlite":
        return {row["name"] for row in con.execute("PRAGMA table_info(brands)").fetchall()}
    return {
        row["column_name"]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?",
            ("brands",),
        ).fetchall()
    }


def migrate_projects(db_url: str | Path | None) -> None:
    """Añade proyectos y vincula marcas heredadas al General de su empresa.

    El bloqueo serializa procesos de startup antes de la introspección/DDL.
    SQLite ejecuta cada sentencia dentro de BEGIN IMMEDIATE; executescript()
    no sirve aquí porque confirma implícitamente la transacción. Postgres usa
    un advisory lock transaccional. El marcador sólo se escribe al finalizar.
    Las marcas creadas después por rutas heredadas se vinculan en otro startup;
    nunca se reemplaza un project_id ya asignado, incluso si está archivado.
    """
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
        con.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at BIGINT NOT NULL)"
        )
        con.execute(
            db._schema_for_postgres(PROJECTS_SCHEMA)
            if con.dialect == "postgres"
            else PROJECTS_SCHEMA
        )
        if "project_id" not in _brand_columns(con):
            con.execute("ALTER TABLE brands ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_projects_tenant_id ON projects(tenant_id, id)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_brands_tenant_project ON brands(tenant_id, project_id)"
        )

        # La enumeración global es exclusiva de esta migración administrativa.
        # Cada lectura/escritura de datos de la empresa lleva scope explícito.
        tenants = con.execute("SELECT id FROM tenants ORDER BY id").fetchall()
        for tenant in tenants:
            tenant_id = tenant["id"]
            unassigned = con.execute(
                "SELECT id FROM brands WHERE tenant_id = ? AND project_id IS NULL LIMIT 1",
                (tenant_id,),
            ).fetchone()
            if unassigned is None:
                continue
            con.execute(
                "INSERT INTO projects(tenant_id, slug, name, description, created_at) "
                "VALUES (?, 'general', 'General', '', ?) "
                "ON CONFLICT(tenant_id, slug) DO NOTHING",
                (tenant_id, int(time.time())),
            )
            general = con.execute(
                "SELECT id FROM projects WHERE tenant_id = ? AND slug = ?",
                (tenant_id, "general"),
            ).fetchone()
            assert general is not None
            con.execute(
                "UPDATE brands SET project_id = ? WHERE tenant_id = ? AND project_id IS NULL",
                (general["id"], tenant_id),
            )
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            (_PROJECTS_VERSION, int(time.time())),
        )
