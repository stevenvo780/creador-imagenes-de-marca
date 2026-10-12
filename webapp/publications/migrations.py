"""DDL incremental, transaccional y compatible con ambos motores."""

import time
from pathlib import Path

from webapp import db

_VERSION = "publication_policies_v1"
_SCHEMA = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_users_tenant_id ON users(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_projects_tenant_id ON projects(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_brands_tenant_id ON brands(tenant_id,id);
CREATE TABLE IF NOT EXISTS publication_connections (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 platform TEXT NOT NULL CHECK(platform IN ('facebook','instagram','tiktok','x')),
 api_mode TEXT NOT NULL,
 remote_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'held',
 version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
 expires_at BIGINT,
 capabilities_json TEXT NOT NULL DEFAULT '{}',
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_policies (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 owner_id INTEGER NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 payload_json TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 valid_from BIGINT,
 expires_at BIGINT,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,version),
 UNIQUE(tenant_id,version,owner_id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_grants (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 owner_id INTEGER NOT NULL,
 policy_version INTEGER NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('planner','reviewer','worker')),
 subject TEXT NOT NULL,
 secret_hash TEXT NOT NULL UNIQUE,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 revoked_at BIGINT,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id),
 FOREIGN KEY(tenant_id,policy_version) REFERENCES publication_policies(tenant_id,version)
);
CREATE INDEX IF NOT EXISTS idx_publication_grants_tenant_id ON publication_grants(tenant_id,id);
"""


def migrate_publications(db_url: str | Path | None) -> None:
    """Sin seeds: una instalación nueva no recibe autorización autónoma."""
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("SELECT pg_advisory_xact_lock(?)", (2026100801,))
        con.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY,applied_at BIGINT NOT NULL)"
        )
        schema = db._schema_for_postgres(_SCHEMA) if con.dialect == "postgres" else _SCHEMA
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            (_VERSION, int(time.time())),
        )
