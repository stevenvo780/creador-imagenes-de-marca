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


def migrate_api_key_scopes(db_url: str | Path | None) -> None:
    """Añade metadata de claves sin otorgar scopes ni caducar las heredadas."""
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in con.execute("PRAGMA table_info(api_keys)").fetchall()}
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
            columns = {
                row["column_name"]
                for row in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = ?",
                    ("api_keys",),
                ).fetchall()
            }
        for name, definition in (
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("scopes_json", "TEXT"),
            ("expires_at", "BIGINT"),
        ):
            if name not in columns:
                con.execute(f"ALTER TABLE api_keys ADD COLUMN {name} {definition}")
        con.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at BIGINT NOT NULL)"
        )
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            ("api_key_scopes_v1", int(time.time())),
        )


def migrate_brand_briefs(db_url: str | Path | None) -> None:
    """Identidad monotónica y originales/referencias inmutables por empresa."""
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
        columns = _brand_columns(con)
        for name, definition in (
            ("brand_version", "INTEGER NOT NULL DEFAULT 1"),
            ("reference_logo_sha256", "TEXT"),
        ):
            if name not in columns:
                con.execute(f"ALTER TABLE brands ADD COLUMN {name} {definition}")
        schema = """
CREATE TABLE IF NOT EXISTS brand_logo_versions (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 brand_id INTEGER NOT NULL,
 sha256 TEXT NOT NULL,
 storage_key TEXT NOT NULL,
 content_type TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id, brand_id, sha256)
);
CREATE TABLE IF NOT EXISTS generation_briefs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 brand_id INTEGER NOT NULL,
 project_id INTEGER NOT NULL,
 brand_version INTEGER NOT NULL,
 prompt TEXT NOT NULL,
 width INTEGER NOT NULL,
 height INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_briefs_tenant_id ON generation_briefs(tenant_id, id);
"""
        if con.dialect == "postgres":
            schema = db._schema_for_postgres(schema)
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            ("brand_briefs_v1", int(time.time())),
        )


def migrate_media(db_url: str | Path | None) -> None:
    """Reserva única de importación y originales privados inmutables."""
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
        schema = """
CREATE TABLE IF NOT EXISTS media_assets (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 brief_id INTEGER NOT NULL,
 project_id INTEGER NOT NULL,
 brand_id INTEGER NOT NULL,
 brand_version INTEGER NOT NULL,
 snapshot_hash TEXT NOT NULL,
 idempotency_key TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 mime TEXT NOT NULL,
 width INTEGER NOT NULL,
 height INTEGER NOT NULL,
 byte_size INTEGER NOT NULL,
 source TEXT NOT NULL,
 provenance_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ingesting', 'pending_review', 'approved', 'rejected', 'archived', 'failed')),
 original_key TEXT NOT NULL DEFAULT '',
 thumbnail_key TEXT NOT NULL DEFAULT '',
 cleanup_keys_json TEXT NOT NULL DEFAULT '[]',
 attempt_token TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 failure_code TEXT,
 UNIQUE(tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_media_tenant_id ON media_assets(tenant_id, id);
CREATE TABLE IF NOT EXISTS media_cleanup_attempts (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 media_id INTEGER NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
 attempt_token TEXT NOT NULL,
 keys_json TEXT NOT NULL,
 cleanup_token TEXT NOT NULL,
 PRIMARY KEY(tenant_id, media_id, attempt_token)
);
"""
        if con.dialect == "postgres":
            schema = db._schema_for_postgres(schema)
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            ("media_v1", int(time.time())),
        )
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            ("media_cleanup_attempts_v1", int(time.time())),
        )


def migrate_media_reviews(db_url: str | Path | None) -> None:
    """Historial de revisión y vínculo durable de promociones; sin alterar originales."""
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
        schema = """
CREATE TABLE IF NOT EXISTS asset_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 media_id INTEGER NOT NULL REFERENCES media_assets(id),
 sha256 TEXT NOT NULL,
 brand_version INTEGER NOT NULL,
 decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected')),
 reason TEXT NOT NULL,
 reviewer_id INTEGER NOT NULL REFERENCES users(id),
 created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_tenant_media ON asset_reviews(tenant_id, media_id, id);
CREATE TABLE IF NOT EXISTS media_variation_origins (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 variation_id INTEGER NOT NULL,
 brief_id INTEGER NOT NULL REFERENCES generation_briefs(id),
 PRIMARY KEY(tenant_id, variation_id)
);
"""
        if con.dialect == "postgres":
            schema = db._schema_for_postgres(schema)
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
            "ON CONFLICT(version) DO NOTHING",
            ("media_reviews_v1", int(time.time())),
        )
