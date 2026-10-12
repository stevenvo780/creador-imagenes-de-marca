"""Conexiones y vault reales; solo credenciales ficticias en pruebas aisladas."""

import json
import sqlite3

import psycopg
import pytest

from webapp import db
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.media_helpers import project
from webapp.tests.test_projects import isolated_db as _isolated_db
from webapp.tests.test_publication_policies import publication_db as _publication_db

isolated_db = _isolated_db
publication_db = _publication_db
media_clients = _media_clients


def connection_payload(payload):
    return {
        "platform": "facebook",
        "api_mode": "page",
        "remote_id": "page-42",
        "project_ids": payload["project_ids"],
    }


@pytest.mark.parametrize(
    "tenant,connection,key_id", [(2, 8, "test"), (1, 9, "test"), (1, 8, "altered")]
)
def test_ciphertext_context_cannot_cross_tenant_connection_or_key(tenant, connection, key_id):
    from cryptography.exceptions import InvalidTag

    from webapp.publications.vault import seal, unseal

    envelope = seal(b"k" * 32, "test", 1, 8, b"fake-token")
    with pytest.raises(InvalidTag):
        unseal(b"k" * 32, tenant, connection, {**envelope, "key_id": key_id})


def test_vault_random_nonce_roundtrip_and_wrong_key():
    from cryptography.exceptions import InvalidTag

    from webapp.publications.vault import seal, unseal

    a = seal(b"k" * 32, "test", 1, 8, b"fake-token")
    b = seal(b"k" * 32, "test", 1, 8, b"fake-token")
    assert a != b
    assert unseal(b"k" * 32, 1, 8, a) == b"fake-token"
    with pytest.raises(InvalidTag):
        unseal(b"x" * 32, 1, 8, a)


@pytest.mark.parametrize("key", [None, b"", b"short"])
def test_vault_missing_or_invalid_key_never_falls_back(key):
    from webapp.publications.contracts import Conflict
    from webapp.publications.vault import seal

    with pytest.raises(Conflict, match="vault_key_unavailable"):
        seal(key, "test", 1, 8, b"fake-token")


def test_pending_metadata_cannot_assert_verification(publication_db):
    from webapp.publications.connections import list_connections, put_connection
    from webapp.publications.contracts import InvalidInput

    url, owners, payloads = publication_db
    result = put_connection(url, *owners[0], connection_payload(payloads[0]))
    assert result["status"] == "held"
    assert result["hold_reason"] == "authorization_required"
    assert result["capabilities"] == {}
    assert result["project_ids"] == payloads[0]["project_ids"]
    for private in ("ciphertext", "nonce", "token", "envelope", "secret"):
        assert private not in json.dumps(result)
    for field, value in [
        ("verified", True),
        ("status", "active"),
        ("scopes", ["pages_manage_posts"]),
        ("token", "fake-token"),
    ]:
        with pytest.raises(InvalidInput):
            put_connection(url, *owners[0], {**connection_payload(payloads[0]), field: value})
    assert all(row["id"] != result["id"] for row in list_connections(url, *owners[1]))


def test_connection_updates_preserve_scope_and_invalidate_authorization(publication_db):
    from webapp.publications.connections import put_connection
    from webapp.publications.contracts import Conflict, Forbidden, NotFound

    url, owners, payloads = publication_db
    value = connection_payload(payloads[0])
    a = put_connection(url, *owners[0], value)
    with pytest.raises(NotFound):
        put_connection(
            url,
            *owners[1],
            {**connection_payload(payloads[1]), "id": a["id"], "expected_version": 1},
        )
    with pytest.raises(Forbidden):
        put_connection(url, *owners[0], {**value, "project_ids": payloads[1]["project_ids"]})
    with pytest.raises(Conflict):
        put_connection(url, *owners[0], {**value, "id": a["id"], "expected_version": 0})
    result = put_connection(
        url, *owners[0], {**value, "id": a["id"], "expected_version": 1, "remote_id": "page-other"}
    )
    assert result["version"] == 2
    assert result["status"] == "held"
    with db.connect(url) as con:
        con.execute("UPDATE users SET role='member' WHERE tenant_id=? AND id=?", owners[0])
    with pytest.raises(Forbidden):
        put_connection(url, *owners[0], value)


def test_connection_routes_only_owner_and_no_private_json(media_clients):
    a, b = media_clients.a, media_clients.b
    p = project(a, "social")
    response = a.post(
        "/api/v1/publications/connections",
        json={
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "page-42",
            "project_ids": [p["id"]],
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "held"
    assert b.get("/api/v1/publications/connections").json() == {"items": []}
    key = a.post(
        "/api/v1/auth/api-keys", json={"name": "legacy", "scopes": ["media:write"]}
    ).json()["key"]
    a.cookies.clear()
    assert (
        a.post(
            "/api/v1/publications/connections", headers={"Authorization": f"Bearer {key}"}, json={}
        ).status_code
        == 403
    )


def test_project_and_vault_foreign_keys_are_tenant_scoped(publication_db):
    from webapp.publications.connections import put_connection

    url, owners, payloads = publication_db
    row = put_connection(url, *owners[0], connection_payload(payloads[0]))
    with (
        pytest.raises((sqlite3.IntegrityError, psycopg.errors.ForeignKeyViolation)),
        db.connect(url) as con,
    ):
        con.execute(
            "INSERT INTO publication_project_connections(tenant_id,project_id,connection_id) VALUES (?,?,?)",
            (owners[1][0], payloads[1]["project_ids"][0], row["id"]),
        )
    with (
        pytest.raises((sqlite3.IntegrityError, psycopg.errors.ForeignKeyViolation)),
        db.connect(url) as con,
    ):
        con.execute(
            "INSERT INTO publication_connection_vault(tenant_id,connection_id,envelope_json) VALUES (?,?,?)",
            (owners[1][0], row["id"], "{}"),
        )


def test_owner_cannot_store_arbitrary_private_capabilities(publication_db):
    from webapp.publications.connections import put_connection
    from webapp.publications.contracts import InvalidInput

    url, owners, payloads = publication_db
    with pytest.raises(InvalidInput):
        put_connection(
            url,
            *owners[0],
            {**connection_payload(payloads[0]), "capabilities": {"access_token": "fake-token"}},
        )


def test_safe_import_dry_run_and_apply_use_verification_transport(publication_db, tmp_path):
    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import import_credential
    from webapp.tests.test_publication_oauth import NOW, ProviderDouble

    url, owners, payloads = publication_db
    row = put_connection(url, *owners[0], connection_payload(payloads[0]))
    result = import_credential(
        url,
        *owners[0],
        row["id"],
        {"access_token": "fake-token"},
        NOW,
        ProviderDouble(),
        key=b"k" * 32,
        key_id="test",
    )
    assert result == {
        "dry_run": True,
        "connection_id": row["id"],
        "eligible": True,
        "hold_reason": None,
    }
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []
    result = import_credential(
        url,
        *owners[0],
        row["id"],
        {"access_token": "fake-token"},
        NOW,
        ProviderDouble(),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    assert result["status"] == "active"
    assert "fake-token" not in json.dumps(result) and "ciphertext" not in json.dumps(result)


def test_import_script_requires_protected_files_and_hides_secrets(publication_db, tmp_path, capsys):
    import argparse

    from scripts.import_publication_connections import run_import
    from webapp.publications.connections import put_connection
    from webapp.publications.contracts import Conflict
    from webapp.tests.test_publication_oauth import NOW, ProviderDouble

    url, owners, payloads = publication_db
    row = put_connection(url, *owners[0], connection_payload(payloads[0]))
    credential = tmp_path / "private.json"
    credential.write_text('{"access_token":"fake-token"}')
    credential.chmod(0o600)
    args = argparse.Namespace(
        tenant_id=owners[0][0],
        owner_id=owners[0][1],
        connection_id=row["id"],
        credential_file=str(credential),
        apply=False,
    )
    result = run_import(args, url, ProviderDouble(), b"k" * 32, "test", now=NOW)
    assert result["eligible"] is True
    assert "fake-token" not in capsys.readouterr().out
    credential.chmod(0o644)
    with pytest.raises(Conflict, match="private_configuration_unavailable"):
        run_import(args, url, ProviderDouble(), b"k" * 32, "test", now=NOW)


def test_new_connection_migration_upgrade_rollback_and_idempotency(publication_db, monkeypatch):
    from webapp.publications.migrations import migrate_publications

    url, _owners, _payloads = publication_db
    with db.connect(url) as con:
        originals = con.execute("SELECT * FROM publication_connections ORDER BY id").fetchall()
        for table in (
            "publication_oauth_states",
            "publication_connection_vault",
            "publication_project_connections",
            "publication_connection_details",
        ):
            con.execute(f"DROP TABLE {table}")
        con.execute("DELETE FROM schema_migrations WHERE version='publication_connections_v1'")
    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if (
            sql.startswith("INSERT INTO schema_migrations")
            and params[0] == "publication_connections_v1"
        ):
            raise RuntimeError("injected-connection-marker")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="injected-connection-marker"):
            migrate_publications(url)
    with db.connect(url) as con:
        if con.dialect == "sqlite":
            new = con.execute(
                "SELECT name FROM sqlite_master WHERE name='publication_connection_vault'"
            ).fetchone()
        else:
            new = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='publication_connection_vault'"
            ).fetchone()
        assert new is None
        assert (
            con.execute("SELECT * FROM publication_connections ORDER BY id").fetchall() == originals
        )
    migrate_publications(url)
    migrate_publications(url)
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM schema_migrations WHERE version='publication_connections_v1'"
            ).fetchone()["n"]
            == 1
        )
        assert (
            con.execute("SELECT * FROM publication_connections ORDER BY id").fetchall() == originals
        )


def test_protected_import_main_defaults_dry_run_never_prints_material(
    publication_db, tmp_path, monkeypatch, capsys
):
    import base64

    from scripts import import_publication_connections as script
    from webapp.publications.connections import put_connection
    from webapp.tests.test_publication_oauth import ProviderDouble

    url, owners, payloads = publication_db
    row = put_connection(url, *owners[0], connection_payload(payloads[0]))
    input_file = tmp_path / "credential.json"
    input_file.write_text('{"access_token":"fake-token"}')
    input_file.chmod(0o600)
    key_file = tmp_path / "key"
    key_file.write_text(base64.b64encode(b"k" * 32).decode())
    key_file.chmod(0o600)
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            [
                {
                    "platform": "facebook",
                    "api_mode": "page",
                    "client_id": "fake-app",
                    "client_secret": "fake-secret",
                    "redirect_uris": ["https://eikon.example.test/callback"],
                    "graph_version": "v25.0",
                }
            ]
        )
    )
    config_file.chmod(0o600)

    class ImportDouble(ProviderDouble):
        def __init__(self, *args):
            super().__init__(expires_at=9999999999)

        def close(self):
            pass

    monkeypatch.setattr(script, "OfficialOAuthClient", ImportDouble)
    monkeypatch.setenv("DATABASE_URL", str(url))
    argv = [
        "--tenant-id",
        str(owners[0][0]),
        "--owner-id",
        str(owners[0][1]),
        "--connection-id",
        str(row["id"]),
        "--credential-file",
        str(input_file),
        "--key-file",
        str(key_file),
        "--config-file",
        str(config_file),
        "--key-id",
        "test",
    ]
    assert script.main(argv) == 0
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "dry_run": True,
        "connection_id": row["id"],
        "eligible": True,
        "hold_reason": None,
    }
    assert all(
        private not in output
        for private in (
            "fake-token",
            "fake-secret",
            base64.b64encode(b"k" * 32).decode(),
            "ciphertext",
        )
    )
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []
