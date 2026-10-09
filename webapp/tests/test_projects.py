"""Proyectos privados y migración transaccional de marcas heredadas."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.storage import SCHEMA, create_brand, create_tenant_user, get_brand
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.media_helpers import project

media_clients = _media_clients


def test_project_is_private(media_clients):
    p = project(media_clients.a, "campaign")
    assert media_clients.b.get(f"/api/v1/projects/{p['id']}").status_code == 404
    assert (
        media_clients.b.patch(f"/api/v1/projects/{p['id']}", json={"name": "Changed"}).status_code
        == 404
    )
    assert media_clients.b.post(f"/api/v1/projects/{p['id']}/archive").status_code == 404
    assert media_clients.b.get("/api/v1/projects").json()["items"] == []


def test_project_crud_and_tenant_slug_uniqueness(media_clients):
    p = project(media_clients.a, "campaign")
    assert p["archived"] == 0
    assert p["description"] == ""
    assert project(media_clients.b, "campaign")["id"] != p["id"]
    assert (
        media_clients.a.post(
            "/api/v1/projects", json={"slug": "campaign", "name": "Duplicate"}
        ).status_code
        == 409
    )
    response = media_clients.a.patch(
        f"/api/v1/projects/{p['id']}",
        json={"slug": "new-campaign", "name": "Campaña", "description": "Descripción"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Campaña"
    assert response.json()["slug"] == "new-campaign"
    assert response.json()["description"] == "Descripción"
    assert media_clients.a.get(f"/api/v1/projects/{p['id']}").json() == response.json()


def test_project_archive_is_logical_and_idempotent(media_clients):
    p = project(media_clients.a, "campaign")
    for _ in range(2):
        response = media_clients.a.post(f"/api/v1/projects/{p['id']}/archive")
        assert response.status_code == 200
        assert response.json()["archived"] == 1
    assert media_clients.a.get("/api/v1/projects").json()["items"] == []
    assert media_clients.a.get("/api/v1/projects?include_archived=true").json()["items"] == [
        response.json()
    ]
    assert media_clients.a.get(f"/api/v1/projects/{p['id']}").status_code == 200


def test_project_pagination_has_no_overlap_or_tenant_leaks(media_clients):
    first = project(media_clients.a, "first")
    project(media_clients.b, "foreign")
    second = project(media_clients.a, "second")
    page = media_clients.a.get("/api/v1/projects?limit=1").json()
    assert page["items"] == [first]
    assert page["next_cursor"] == first["id"]
    page2 = media_clients.a.get(f"/api/v1/projects?limit=1&cursor={page['next_cursor']}").json()
    assert page2["items"] == [second]
    assert page2["next_cursor"] is None


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "cursor=-1", "cursor=nope"])
def test_project_pagination_rejects_invalid_values(media_clients, query):
    assert media_clients.a.get(f"/api/v1/projects?{query}").status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"slug": "../outside", "name": "Invalid"},
        {"slug": "valid", "name": " "},
        {"slug": "valid", "name": "Good", "tenant_id": 2},
        {"slug": "valid", "name": "Good", "archived": 1},
    ],
)
def test_project_rejects_invalid_and_server_owned_fields(media_clients, payload):
    assert media_clients.a.post("/api/v1/projects", json=payload).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"tenant_id": 2}, {"archived": 0}])
def test_project_patch_rejects_empty_null_or_server_owned_fields(media_clients, payload):
    p = project(media_clients.a, "campaign")
    assert media_clients.a.patch(f"/api/v1/projects/{p['id']}", json=payload).status_code == 422


def test_projects_require_session_and_do_not_grant_legacy_keys_permissions(media_clients):
    from webapp.storage import create_api_key

    with db.connect(media_clients.db_path) as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug = ?", ("alpha",)).fetchone()
    key, _ = create_api_key(media_clients.db_path, tenant["id"])
    client = TestClient(media_clients.a.app)
    try:
        assert client.get("/api/v1/projects").status_code == 401
        assert (
            client.get("/api/v1/projects", headers={"Authorization": f"Bearer {key}"}).status_code
            == 403
        )
    finally:
        client.close()


@pytest.fixture(params=["sqlite", "postgres"])
def isolated_db(request, tmp_path):
    """BD real vacía y aislada, para ambos dialectos."""
    if request.param == "sqlite":
        url = tmp_path / "legacy.db"
        yield url
        return

    pg_url = os.environ.get("EIKON_TEST_POSTGRES_URL")
    if not pg_url:
        pytest.skip("Postgres pendiente: definir EIKON_TEST_POSTGRES_URL de prueba")
    import psycopg
    from psycopg import sql

    schema = "eikon_test_" + uuid.uuid4().hex
    with psycopg.connect(pg_url, autocommit=True) as con:
        con.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    separator = "&" if "?" in pg_url else "?"
    url = pg_url + separator + urlencode({"options": f"-csearch_path={schema}"})
    try:
        yield url
    finally:
        with psycopg.connect(pg_url, autocommit=True) as con:
            con.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def legacy_db(isolated_db):
    """Schema heredado, sin proyectos, con todas sus tablas originales."""
    with db.connect(isolated_db) as con:
        con.executescript(SCHEMA)
    return isolated_db


def test_concurrent_startup_of_empty_installation(isolated_db):
    from webapp.project_storage import create_project

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: db.init_db(isolated_db), range(4)))
    user = create_tenant_user(isolated_db, "fresh", "Fresh", "fresh@example.test", "password123")
    assert create_project(isolated_db, user["tenant_id"], "campaign", "Campaign")["id"] > 0


def _legacy_brands(url):
    a = create_tenant_user(url, "alpha", "Alpha", "alpha@example.test", "password123")
    b = create_tenant_user(url, "beta", "Beta", "beta@example.test", "password123")
    original = create_brand(
        url,
        a["tenant_id"],
        "official",
        "Oficial",
        logo_asset="marcas/official/logo.png",
        logo_seed=41,
        logo_style="pack_brand_form",
    )
    other = create_brand(url, b["tenant_id"], "official", "Otro")
    return a, b, original, other


def test_migration_assigns_own_general_preserving_brands_twice(legacy_db):
    from webapp.migrations import migrate_projects
    from webapp.project_storage import get_project, list_projects

    a, b, original, other = _legacy_brands(legacy_db)
    migrate_projects(legacy_db)
    migrated = get_brand(legacy_db, a["tenant_id"], original["id"])
    assert {key: migrated[key] for key in original} == original
    first_project = get_project(legacy_db, a["tenant_id"], migrated["project_id"])
    assert first_project["slug"] == "general"
    assert first_project["name"] == "General"
    assert get_project(legacy_db, b["tenant_id"], migrated["project_id"]) is None
    other_project = get_brand(legacy_db, b["tenant_id"], other["id"])["project_id"]
    assert other_project != migrated["project_id"]
    migrate_projects(legacy_db)
    assert get_brand(legacy_db, a["tenant_id"], original["id"]) == migrated
    assert len(list_projects(legacy_db, a["tenant_id"])) == 1
    assert len(list_projects(legacy_db, b["tenant_id"])) == 1
    with db.connect(legacy_db) as con:
        assert len(con.execute("SELECT * FROM schema_migrations").fetchall()) == 1


def test_migration_rolls_back_and_can_retry(legacy_db, monkeypatch):
    from webapp.migrations import migrate_projects

    a, _, original, _ = _legacy_brands(legacy_db)
    with db.connect(legacy_db) as con:
        con.execute(
            "CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, applied_at BIGINT NOT NULL)"
        )
        con.execute("INSERT INTO schema_migrations VALUES ('previous', 1)")
    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if sql.startswith("INSERT INTO schema_migrations"):
            raise RuntimeError("fallo transaccional de prueba")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="fallo transaccional"):
            migrate_projects(legacy_db)
    assert get_brand(legacy_db, a["tenant_id"], original["id"]) == original
    with db.connect(legacy_db) as con:
        assert con.execute("SELECT version FROM schema_migrations").fetchall() == [
            {"version": "previous"}
        ]
    migrate_projects(legacy_db)
    assert get_brand(legacy_db, a["tenant_id"], original["id"])["project_id"] > 0


def test_concurrent_migrations_create_one_general_per_tenant(legacy_db):
    from webapp.migrations import migrate_projects
    from webapp.project_storage import list_projects

    a, b, _, _ = _legacy_brands(legacy_db)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: migrate_projects(legacy_db), range(4)))
    assert len(list_projects(legacy_db, a["tenant_id"])) == 1
    assert len(list_projects(legacy_db, b["tenant_id"])) == 1


def test_init_db_new_and_existing_and_later_legacy_brands(legacy_db):
    from webapp.project_storage import get_project, update_project

    db.init_db(legacy_db)
    a, _, original, _ = _legacy_brands(legacy_db)
    db.init_db(legacy_db)
    migrated = get_brand(legacy_db, a["tenant_id"], original["id"])
    project_id = migrated["project_id"]
    update_project(legacy_db, a["tenant_id"], project_id, {"archived": 1})
    db.init_db(legacy_db)
    assert get_brand(legacy_db, a["tenant_id"], original["id"])["project_id"] == project_id
    assert get_project(legacy_db, a["tenant_id"], project_id)["archived"] == 1


def test_storage_rejects_untrusted_update_columns(media_clients):
    from webapp.project_storage import update_project

    p = project(media_clients.a, "campaign")
    with pytest.raises(ValueError):
        update_project(media_clients.db_path, p["tenant_id"], p["id"], {"tenant_id": 2})
