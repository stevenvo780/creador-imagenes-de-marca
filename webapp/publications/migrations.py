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

_CONNECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_connection_details (
 tenant_id INTEGER NOT NULL,
 connection_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL,
 remote_name TEXT,
 scopes_json TEXT NOT NULL DEFAULT '[]',
 scope_evidence TEXT NOT NULL DEFAULT 'unverified' CHECK(scope_evidence IN ('unverified','remote_introspection','token_exchange','capability_probe')),
 verified_at BIGINT,
 expiry_state TEXT NOT NULL DEFAULT 'unknown' CHECK(expiry_state IN ('known','non_expiring','unknown')),
 hold_reason TEXT,
 requested_capabilities_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(tenant_id,connection_id),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES publication_connections(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_project_connections (
 tenant_id INTEGER NOT NULL,
 project_id INTEGER NOT NULL,
 connection_id INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,project_id,connection_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES projects(tenant_id,id),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES publication_connections(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_connection_vault (
 tenant_id INTEGER NOT NULL,
 connection_id INTEGER NOT NULL,
 envelope_json TEXT NOT NULL,
 PRIMARY KEY(tenant_id,connection_id),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES publication_connections(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_oauth_states (
 tenant_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL,
 connection_id INTEGER NOT NULL,
 connection_version INTEGER NOT NULL,
 state_hash TEXT NOT NULL UNIQUE,
 session_hash TEXT NOT NULL,
 config_hash TEXT NOT NULL,
 flow_json TEXT NOT NULL,
 verifier_envelope_json TEXT,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 consumed_at BIGINT,
 PRIMARY KEY(tenant_id,state_hash),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES publication_connections(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id)
);
"""


_CAMPAIGN_SCHEMA = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_briefs_tenant_id ON generation_briefs(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_images_tenant_id ON media_assets(tenant_id,id);
CREATE TABLE IF NOT EXISTS publication_campaigns (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 project_id INTEGER NOT NULL,
 brand_id INTEGER NOT NULL,
 objective TEXT NOT NULL,
 actor TEXT NOT NULL,
 archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES projects(tenant_id,id),
 FOREIGN KEY(tenant_id,brand_id) REFERENCES brands(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_video_media (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 project_id INTEGER NOT NULL,
 brand_id INTEGER NOT NULL,
 brief_id INTEGER NOT NULL,
 brand_version INTEGER NOT NULL,
 snapshot_hash TEXT NOT NULL,
 snapshot_json TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 mime TEXT NOT NULL,
 codec TEXT NOT NULL,
 audio_codec TEXT,
 width INTEGER NOT NULL CHECK(width>0),
 height INTEGER NOT NULL CHECK(height>0),
 duration_seconds DOUBLE PRECISION NOT NULL CHECK(duration_seconds>0),
 fps DOUBLE PRECISION NOT NULL CHECK(fps>0),
 byte_size BIGINT NOT NULL CHECK(byte_size>0),
 source TEXT NOT NULL,
 provenance_json TEXT NOT NULL,
 rights TEXT NOT NULL,
 idempotency_key TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 storage_key TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ingesting','pending_review','rejected','archived','failed')),
 lease_until BIGINT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,project_id) REFERENCES projects(tenant_id,id),
 FOREIGN KEY(tenant_id,brand_id) REFERENCES brands(tenant_id,id),
 FOREIGN KEY(tenant_id,brief_id) REFERENCES generation_briefs(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 campaign_id INTEGER NOT NULL,
 media_kind TEXT NOT NULL CHECK(media_kind IN ('gallery_image','publication_video')),
 gallery_image_id INTEGER,
 video_media_id INTEGER,
 connection_id INTEGER NOT NULL,
 policy_version INTEGER NOT NULL,
 scheduled_at_utc BIGINT NOT NULL,
 contract_hash TEXT NOT NULL,
 frozen_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 CHECK((media_kind='gallery_image' AND gallery_image_id IS NOT NULL AND video_media_id IS NULL) OR (media_kind='publication_video' AND gallery_image_id IS NULL AND video_media_id IS NOT NULL)),
 FOREIGN KEY(tenant_id,campaign_id) REFERENCES publication_campaigns(tenant_id,id),
 FOREIGN KEY(tenant_id,gallery_image_id) REFERENCES media_assets(tenant_id,id),
 FOREIGN KEY(tenant_id,video_media_id) REFERENCES publication_video_media(tenant_id,id),
 FOREIGN KEY(tenant_id,connection_id) REFERENCES publication_connections(tenant_id,id),
 FOREIGN KEY(tenant_id,policy_version) REFERENCES publication_policies(tenant_id,version)
);
CREATE INDEX IF NOT EXISTS idx_publication_revisions_tenant_id ON publication_revisions(tenant_id,id);
"""


def _immutable_revisions(con: db.DualConnection) -> None:
    """Impide sobrescribir/borrar el contrato aun con un escritor SQL accidental."""
    if con.dialect == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            con.execute(
                f"CREATE TRIGGER IF NOT EXISTS publication_revision_no_{operation.lower()} BEFORE {operation} ON publication_revisions BEGIN SELECT RAISE(ABORT, 'immutable_revision'); END"
            )
    else:
        con.execute(
            "CREATE OR REPLACE FUNCTION publication_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable_revision'; END $$"
        )
        con.execute(
            "DROP TRIGGER IF EXISTS publication_revision_immutable ON publication_revisions"
        )
        con.execute(
            "CREATE TRIGGER publication_revision_immutable BEFORE UPDATE OR DELETE ON publication_revisions FOR EACH ROW EXECUTE FUNCTION publication_revision_immutable()"
        )


def _immutable_videos(con: db.DualConnection) -> None:
    fields = (
        "id",
        "tenant_id",
        "project_id",
        "brand_id",
        "brief_id",
        "brand_version",
        "snapshot_hash",
        "snapshot_json",
        "sha256",
        "mime",
        "codec",
        "audio_codec",
        "width",
        "height",
        "duration_seconds",
        "fps",
        "byte_size",
        "source",
        "provenance_json",
        "rights",
        "idempotency_key",
        "request_hash",
        "created_at",
    )
    if con.dialect == "sqlite":
        changes = " OR ".join(f"OLD.{field} IS NOT NEW.{field}" for field in fields)
        con.execute(
            f"CREATE TRIGGER IF NOT EXISTS publication_video_no_replace BEFORE UPDATE ON publication_video_media WHEN {changes} OR (OLD.status NOT IN ('ingesting','failed') AND (OLD.storage_key IS NOT NEW.storage_key OR NEW.status IN ('ingesting','failed'))) BEGIN SELECT RAISE(ABORT, 'immutable_video'); END"
        )
        con.execute(
            "CREATE TRIGGER IF NOT EXISTS publication_video_no_delete BEFORE DELETE ON publication_video_media BEGIN SELECT RAISE(ABORT, 'immutable_video'); END"
        )
    else:
        changes = " OR ".join(f"OLD.{field} IS DISTINCT FROM NEW.{field}" for field in fields)
        con.execute(
            f"CREATE OR REPLACE FUNCTION publication_video_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'immutable_video'; END IF; IF {changes} OR (OLD.status NOT IN ('ingesting','failed') AND (OLD.storage_key IS DISTINCT FROM NEW.storage_key OR NEW.status IN ('ingesting','failed'))) THEN RAISE EXCEPTION 'immutable_video'; END IF; RETURN NEW; END $$"
        )
        con.execute("DROP TRIGGER IF EXISTS publication_video_immutable ON publication_video_media")
        con.execute(
            "CREATE TRIGGER publication_video_immutable BEFORE UPDATE OR DELETE ON publication_video_media FOR EACH ROW EXECUTE FUNCTION publication_video_immutable()"
        )


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
        source = _SCHEMA + _CONNECTION_SCHEMA + _CAMPAIGN_SCHEMA
        schema = db._schema_for_postgres(source) if con.dialect == "postgres" else source
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            (_VERSION, int(time.time())),
        )

        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_connections_v1", int(time.time())),
        )

        _immutable_revisions(con)
        _immutable_videos(con)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_campaigns_v1", int(time.time())),
        )
