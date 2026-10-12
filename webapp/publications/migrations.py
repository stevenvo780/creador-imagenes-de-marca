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


_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_history_cuts (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 cut_id TEXT NOT NULL,
 manifest_hash TEXT NOT NULL,
 manifest_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,cut_id)
);
CREATE TABLE IF NOT EXISTS publication_history_sources (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 source_id TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,
 receipt_sha256 TEXT NOT NULL,
 evidence_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,source_id)
);
CREATE TABLE IF NOT EXISTS publication_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 source_id TEXT NOT NULL,
 source_delivery_id TEXT NOT NULL,
 attempt_id TEXT NOT NULL,
 platform TEXT NOT NULL CHECK(platform IN ('facebook','instagram','tiktok','x')),
 normalized_destination TEXT,
 image_sha256 TEXT,
 state TEXT NOT NULL CHECK(state IN ('published','failed','uncertain','inflight','attempt_started','held','cancelled','withdrawn')),
 hold_reason TEXT,
 item_hash TEXT NOT NULL,
 item_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,attempt_id),
 FOREIGN KEY(tenant_id,source_id) REFERENCES publication_history_sources(tenant_id,source_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS publication_history_origin ON publication_history(tenant_id,source_id,source_delivery_id);
CREATE TABLE IF NOT EXISTS publication_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 attempt_id TEXT NOT NULL,
 event_key TEXT NOT NULL,
 kind TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS publication_event_idempotency ON publication_events(tenant_id,attempt_id,event_key);
CREATE TABLE IF NOT EXISTS publication_media_guards (
 tenant_id INTEGER NOT NULL,
 normalized_destination TEXT NOT NULL,
 image_sha256 TEXT NOT NULL,
 event_id INTEGER NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,normalized_destination,image_sha256),
 FOREIGN KEY(tenant_id,event_id) REFERENCES publication_events(tenant_id,id)
);
"""


def _immutable_history(con: db.DualConnection) -> None:
    """Ni una retirada ni SQL accidental puede borrar historia o guardias."""
    tables = (
        "publication_history_cuts",
        "publication_history_sources",
        "publication_history",
        "publication_events",
        "publication_media_guards",
    )
    if con.dialect == "postgres":
        con.execute(
            "CREATE OR REPLACE FUNCTION publication_history_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable_history'; END $$"
        )
    for table in tables:
        if con.dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                con.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable_history'); END"
                )
        else:
            con.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            con.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION publication_history_immutable()"
            )


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


_EVALUATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_material_deliveries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 grant_id INTEGER NOT NULL,
 request_id TEXT NOT NULL,
 contract_hash TEXT NOT NULL,
 material_hashes_json TEXT NOT NULL,
 review_mode TEXT NOT NULL CHECK(review_mode IN ('exact_image','frames_only_silent')),
 evidence_json TEXT NOT NULL,
 prompt_hash TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,grant_id,request_id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,grant_id) REFERENCES publication_grants(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_evaluations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 grant_id INTEGER NOT NULL,
 delivery_id INTEGER NOT NULL,
 request_id TEXT NOT NULL,
 policy_version INTEGER NOT NULL,
 contract_hash TEXT NOT NULL,
 material_hashes_json TEXT NOT NULL,
 model_receipt_json TEXT NOT NULL,
 response_json TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,grant_id,request_id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,grant_id) REFERENCES publication_grants(tenant_id,id),
 FOREIGN KEY(tenant_id,delivery_id) REFERENCES publication_material_deliveries(tenant_id,id),
 FOREIGN KEY(tenant_id,policy_version) REFERENCES publication_policies(tenant_id,version)
);
CREATE TABLE IF NOT EXISTS publication_ai_decisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 grant_id INTEGER NOT NULL,
 evaluation_receipt_id INTEGER NOT NULL,
 policy_version INTEGER NOT NULL,
 contract_hash TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN ('approve','reject','hold')),
 reason TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,evaluation_receipt_id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,grant_id) REFERENCES publication_grants(tenant_id,id),
 FOREIGN KEY(tenant_id,evaluation_receipt_id) REFERENCES publication_evaluations(tenant_id,id),
 FOREIGN KEY(tenant_id,policy_version) REFERENCES publication_policies(tenant_id,version)
);
CREATE INDEX IF NOT EXISTS idx_publication_ai_decisions_revision ON publication_ai_decisions(tenant_id,revision_id,id);
"""


def _immutable_evaluations(con: db.DualConnection) -> None:
    tables = (
        "publication_material_deliveries",
        "publication_evaluations",
        "publication_ai_decisions",
    )
    if con.dialect == "postgres":
        con.execute(
            "CREATE OR REPLACE FUNCTION publication_evaluation_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable_evaluation'; END $$"
        )
    for table in tables:
        if con.dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                con.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable_evaluation'); END"
                )
        else:
            con.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            con.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION publication_evaluation_immutable()"
            )


_DELIVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_deliveries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 decision_id INTEGER,
 contract_hash TEXT NOT NULL,
 normalized_destination TEXT NOT NULL,
 media_sha256 TEXT NOT NULL,
 due_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('scheduled','held','reserved','attempt_started','published','failed','uncertain','expired','cancelled','withdrawn')),
 hold_reasons_json TEXT NOT NULL DEFAULT '[]',
 claim_id TEXT,
 worker_grant_id INTEGER,
 attempt_id TEXT,
 lease_until BIGINT,
 started_at BIGINT,
 result_json TEXT,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,revision_id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,decision_id) REFERENCES publication_ai_decisions(tenant_id,id),
 FOREIGN KEY(tenant_id,worker_grant_id) REFERENCES publication_grants(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS publication_due ON publication_deliveries(tenant_id,state,due_at);
CREATE TABLE IF NOT EXISTS publication_claims (
 tenant_id INTEGER NOT NULL,
 claim_id TEXT NOT NULL,
 delivery_id INTEGER NOT NULL,
 attempt_id TEXT NOT NULL,
 worker_grant_id INTEGER NOT NULL,
 contract_hash TEXT NOT NULL,
 claimed_at BIGINT NOT NULL,
 lease_until BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,claim_id), UNIQUE(tenant_id,attempt_id),
 FOREIGN KEY(tenant_id,delivery_id) REFERENCES publication_deliveries(tenant_id,id),
 FOREIGN KEY(tenant_id,worker_grant_id) REFERENCES publication_grants(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_claim_materials (
 tenant_id INTEGER NOT NULL,
 claim_id TEXT NOT NULL,
 media_sha256 TEXT NOT NULL,
 verified_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,claim_id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES publication_claims(tenant_id,claim_id)
);
CREATE TABLE IF NOT EXISTS publication_media_tickets (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL,
 claim_id TEXT NOT NULL,
 attempt_id TEXT NOT NULL,
 media_kind TEXT NOT NULL,
 media_id INTEGER NOT NULL,
 media_sha256 TEXT NOT NULL,
 ticket_hash TEXT NOT NULL UNIQUE,
 expires_at BIGINT NOT NULL,
 revoked_at BIGINT,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES publication_claims(tenant_id,claim_id),
 FOREIGN KEY(tenant_id,attempt_id) REFERENCES publication_claims(tenant_id,attempt_id)
);
"""


def _immutable_claims(con: db.DualConnection) -> None:
    if con.dialect == "postgres":
        con.execute(
            "CREATE OR REPLACE FUNCTION publication_claim_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable_claim'; END $$"
        )
    for table in ("publication_claims", "publication_claim_materials"):
        if con.dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                con.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable_claim'); END"
                )
        else:
            con.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            con.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION publication_claim_immutable()"
            )


_CONSENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_provider_proofs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL,
 proof_key TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,proof_key),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_creator_receipts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL,
 payload_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_post_consents (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 revision_id INTEGER NOT NULL,
 owner_id INTEGER NOT NULL,
 creator_id INTEGER NOT NULL,
 proof_id INTEGER NOT NULL,
 payload_json TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,revision_id) REFERENCES publication_revisions(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id),
 FOREIGN KEY(tenant_id,creator_id) REFERENCES publication_creator_receipts(tenant_id,id),
 FOREIGN KEY(tenant_id,proof_id) REFERENCES publication_provider_proofs(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_claim_consents (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 claim_id TEXT NOT NULL,
 receipt_id INTEGER NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,claim_id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES publication_claims(tenant_id,claim_id),
 FOREIGN KEY(tenant_id,receipt_id) REFERENCES publication_post_consents(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS publication_consent_revocations (
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 kind TEXT NOT NULL CHECK(kind IN ('proof','consent')),
 record_id INTEGER NOT NULL,
 created_at BIGINT NOT NULL,
 PRIMARY KEY(tenant_id,kind,record_id)
);
"""


def _immutable_consents(con: db.DualConnection) -> None:
    if con.dialect == "postgres":
        con.execute(
            "CREATE OR REPLACE FUNCTION publication_consent_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable_consent'; END $$"
        )
    for table in (
        "publication_provider_proofs",
        "publication_creator_receipts",
        "publication_post_consents",
        "publication_consent_revocations",
        "publication_claim_consents",
    ):
        if con.dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                con.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable_consent'); END"
                )
        else:
            con.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            con.execute(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION publication_consent_immutable()"
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
        source = (
            _SCHEMA
            + _CONNECTION_SCHEMA
            + _CAMPAIGN_SCHEMA
            + _HISTORY_SCHEMA
            + _EVALUATION_SCHEMA
            + _DELIVERY_SCHEMA
            + _CONSENT_SCHEMA
        )
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
        _immutable_history(con)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_history_v1", int(time.time())),
        )
        _immutable_evaluations(con)
        _immutable_claims(con)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_evaluations_v1", int(time.time())),
        )
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_deliveries_v1", int(time.time())),
        )

        _immutable_consents(con)
        con.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING",
            ("publication_consents_v1", int(time.time())),
        )
