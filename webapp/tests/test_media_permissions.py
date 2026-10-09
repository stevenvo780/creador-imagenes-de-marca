"""Permisos explícitos y administración humana de claves por empresa."""

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from webapp import db
from webapp.api.deps import current_user
from webapp.api.permissions import API_KEY_SCOPES, require_owner_session, require_scope
from webapp.security import create_jwt
from webapp.storage import (
    create_api_key,
    create_scoped_api_key,
    create_tenant_user,
    resolve_api_key,
)
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.media_helpers import project
from webapp.tests.test_projects import isolated_db as _isolated_db
from webapp.tests.test_projects import legacy_db as _legacy_db

isolated_db = _isolated_db
legacy_db = _legacy_db

media_clients = _media_clients


def test_key_cannot_mint_keys(media_clients):
    response = media_clients.a.post(
        "/api/v1/auth/api-keys",
        json={"name": "codex", "scopes": ["media:write"], "expires_in_days": 30},
    )
    assert response.status_code == 201
    row = response.json()
    agent = TestClient(media_clients.a.app)
    try:
        agent.headers["Authorization"] = f"Bearer {row['key']}"
        assert agent.post("/api/v1/auth/api-keys", json={}).status_code == 403
        assert agent.get("/api/v1/auth/api-keys").status_code == 403
        assert agent.delete(f"/api/v1/auth/api-keys/{row['id']}").status_code == 403
        assert agent.get("/api/v1/projects").status_code == 403
        assert media_clients.a.delete(f"/api/v1/auth/api-keys/{row['id']}").status_code == 204
        assert agent.get("/api/v1/projects").status_code == 401

    finally:
        agent.close()


@pytest.fixture
def agent(media_clients):
    client = TestClient(media_clients.a.app)
    try:
        yield client
    finally:
        client.close()


def get_principal(client):
    headers = [(name.lower().encode(), value.encode()) for name, value in client.headers.items()]
    cookies = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
    headers.append((b"cookie", cookies.encode()))
    request = Request(
        {
            "type": "http",
            "app": client.app,
            "method": "GET",
            "path": "/auth/me",
            "headers": headers,
            "route": SimpleNamespace(path="/auth/me"),
        }
    )
    return asyncio.run(current_user(request, Response()))


def mint(client, scopes=None, **fields):
    response = client.post(
        "/api/v1/auth/api-keys", json={"name": "codex", "scopes": scopes or [], **fields}
    )
    assert response.status_code == 201
    return response.json()


def test_default_key_has_no_scopes_and_limited_ttl(media_clients, agent):
    response = media_clients.a.post("/api/v1/auth/api-keys")
    assert response.status_code == 201
    row = response.json()
    assert row["scopes"] == []
    assert 30 * 86400 - 1 <= row["expires_at"] - row["created_at"] <= 30 * 86400
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/brands").status_code == 403
    assert agent.get("/api/v1/projects").status_code == 403
    assert media_clients.a.app.state.worker is None


@pytest.mark.parametrize(
    "payload",
    [
        {"scopes": ["media:approve"]},
        {"scopes": ["unknown"]},
        {"scopes": "media:write"},
        {"scopes": [123]},
        {"scopes": None},
        {"tenant_id": 2},
        {"role": "owner"},
        {"expires_at": 9999999999},
        {"expires_in_days": 0},
        {"expires_in_days": -1},
        {"expires_in_days": 366},
        {"expires_in_days": True},
        {"expires_in_days": "30"},
        {"expires_in_days": 1.5},
        {"name": ""},
        {"name": " "},
        {"name": "x" * 101},
    ],
)
def test_rejects_unknown_scopes_ttl_and_server_owned_fields(media_clients, payload):
    assert media_clients.a.post("/api/v1/auth/api-keys", json=payload).status_code == 422


def test_key_metadata_stores_only_hash_and_no_hash_is_returned(media_clients):
    row = mint(media_clients.a, list(API_KEY_SCOPES), expires_in_days=365)
    assert 365 * 86400 - 1 <= row["expires_at"] - row["created_at"] <= 365 * 86400
    assert set(row["scopes"]) == API_KEY_SCOPES
    with db.connect(media_clients.db_path) as con:
        stored = con.execute("SELECT * FROM api_keys WHERE id = ?", (row["id"],)).fetchone()
    assert row["key"] not in stored.values()
    assert len(stored["key_hash"]) == 64
    assert json.loads(stored["scopes_json"]) == sorted(API_KEY_SCOPES)
    resolved = resolve_api_key(media_clients.db_path, row["key"])
    assert "key_hash" not in resolved
    assert "key" not in resolved
    listing = media_clients.a.get("/api/v1/auth/api-keys").json()["keys"]
    assert len(listing) == 1
    assert "key_hash" not in listing[0]
    assert "key" not in listing[0]
    assert listing[0]["name"] == "codex"
    assert media_clients.b.get("/api/v1/auth/api-keys").json()["keys"] == []
    assert media_clients.b.delete(f"/api/v1/auth/api-keys/{row['id']}").status_code == 404


def test_projects_read_write_scopes_are_independent_and_tenant_scoped(media_clients, agent):
    own = project(media_clients.a, "own")
    foreign = project(media_clients.b, "foreign")
    row = mint(media_clients.a, ["projects:read"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/projects").json()["items"] == [own]
    assert agent.get(f"/api/v1/projects/{foreign['id']}").status_code == 404
    assert agent.post("/api/v1/projects", json={"slug": "new", "name": "New"}).status_code == 403
    assert agent.patch(f"/api/v1/projects/{own['id']}", json={"name": "Changed"}).status_code == 403
    assert agent.post(f"/api/v1/projects/{own['id']}/archive").status_code == 403
    row = mint(media_clients.a, ["projects:write"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/projects").status_code == 403
    assert agent.post("/api/v1/projects", json={"slug": "new", "name": "New"}).status_code == 201
    assert (
        agent.patch(f"/api/v1/projects/{foreign['id']}", json={"name": "Changed"}).status_code
        == 404
    )
    assert agent.post(f"/api/v1/projects/{foreign['id']}/archive").status_code == 404
    assert agent.patch(f"/api/v1/projects/{own['id']}", json={"name": "Changed"}).status_code == 200
    assert agent.post(f"/api/v1/projects/{own['id']}/archive").status_code == 200


def test_legacy_key_has_no_new_permissions(media_clients, agent):
    tenant_id = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    key, row = create_api_key(media_clients.db_path, tenant_id)
    agent.headers["X-API-Key"] = key
    assert agent.get("/api/v1/brands").status_code == 200
    assert agent.get("/api/v1/projects").status_code == 403
    assert agent.post("/api/v1/auth/api-keys").status_code == 403
    assert agent.get("/api/v1/auth/api-keys").status_code == 403
    assert agent.delete(f"/api/v1/auth/api-keys/{row['id']}").status_code == 403
    me = get_principal(agent)
    assert me["auth_method"] == "api_key"
    assert me["api_key_id"] == row["id"]
    assert me["scopes"] == frozenset()
    assert resolve_api_key(media_clients.db_path, key)["expires_at"] is None
    with pytest.raises(HTTPException) as err:
        require_owner_session(me)
    assert err.value.status_code == 403


@pytest.mark.parametrize("header", ["Authorization", "X-API-Key"])
def test_expiry_and_updated_scopes_are_checked_per_request(media_clients, agent, header):
    row = mint(media_clients.a, ["projects:read"])
    agent.headers[header] = f"Bearer {row['key']}" if header == "Authorization" else row["key"]
    assert agent.get("/api/v1/projects").status_code == 200
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE api_keys SET scopes_json = ? WHERE id = ?", ("[]", row["id"]))
    assert agent.get("/api/v1/projects").status_code == 403
    with db.connect(media_clients.db_path) as con:
        con.execute(
            "UPDATE api_keys SET expires_at = ? WHERE id = ?", (int(time.time()), row["id"])
        )
    assert agent.get("/api/v1/projects").status_code == 401
    assert agent.get("/api/v1/brands").status_code == 401


@pytest.mark.parametrize("cookie", ["invalid", "", "expired", "missing-user", "bad-sub"])
def test_invalid_cookie_does_not_fall_back_to_valid_bearer(media_clients, agent, cookie):
    row = mint(media_clients.a, ["projects:read"])
    settings = media_clients.a.app.state.settings
    me = media_clients.a.get("/auth/me").json()["user"]
    if cookie == "expired":
        cookie = create_jwt({"sub": me["id"], "exp": int(time.time()) - 1}, settings.jwt_secret, 60)
    elif cookie == "missing-user":
        cookie = create_jwt({"sub": 999999}, settings.jwt_secret, 60)
    elif cookie == "bad-sub":
        cookie = create_jwt({"sub": "not-a-number"}, settings.jwt_secret, 60)
    agent.cookies.set(settings.cookie_name, cookie)
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/projects").status_code == 401
    assert agent.post("/api/v1/auth/api-keys").status_code == 401


def test_valid_cookie_tenant_a_wins_over_bearer_b(media_clients):
    own = project(media_clients.a, "own")
    foreign = project(media_clients.b, "foreign")
    foreign_key = mint(media_clients.b, ["projects:read", "projects:write"])
    media_clients.a.headers["Authorization"] = f"Bearer {foreign_key['key']}"
    me = media_clients.a.get("/auth/me").json()
    assert me["tenant"]["id"] == own["tenant_id"]
    assert media_clients.a.get("/api/v1/projects").json()["items"] == [own]
    assert media_clients.a.get(f"/api/v1/projects/{foreign['id']}").status_code == 404
    assert (
        media_clients.a.patch(f"/api/v1/projects/{foreign['id']}", json={"name": "Bad"}).status_code
        == 404
    )
    assert media_clients.a.delete(f"/api/v1/auth/api-keys/{foreign_key['id']}").status_code == 404
    own_key = mint(media_clients.a)
    assert resolve_api_key(media_clients.db_path, own_key["key"])["tenant_id"] == own["tenant_id"]


@pytest.mark.parametrize("bearer", ["invalid", ""])
def test_bearer_precedes_x_api_key_without_fallback(media_clients, agent, bearer):
    row = mint(media_clients.a, ["projects:read"])
    agent.headers["Authorization"] = f"Bearer {bearer}"
    agent.headers["X-API-Key"] = row["key"]
    assert agent.get("/api/v1/projects").status_code == 401


def test_role_and_tenant_are_read_from_db_on_every_session_request(media_clients):
    response = media_clients.a.get("/auth/me").json()
    user = response["user"]
    tenant_id = response["tenant"]["id"]
    settings = media_clients.a.app.state.settings
    foreign_tenant = media_clients.b.get("/auth/me").json()["tenant"]["id"]
    token = create_jwt(
        {"sub": user["id"], "tenant_id": foreign_tenant, "role": "owner"}, settings.jwt_secret, 60
    )
    media_clients.a.cookies.clear()
    media_clients.a.cookies.set(settings.cookie_name, token)
    assert media_clients.a.get("/auth/me").json()["tenant"]["id"] == tenant_id
    assert media_clients.a.get("/api/v1/projects").status_code == 200
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE users SET role = ? WHERE id = ?", ("member", user["id"]))
    assert media_clients.a.post("/api/v1/auth/api-keys").status_code == 403
    assert media_clients.a.get("/api/v1/auth/api-keys").status_code == 403
    assert media_clients.a.delete("/api/v1/auth/api-keys/1").status_code == 403
    assert media_clients.a.get("/api/v1/projects").status_code == 403
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE users SET role = ? WHERE id = ?", ("owner", user["id"]))
    assert media_clients.a.post("/api/v1/auth/api-keys").status_code == 201


def test_human_review_helper_never_accepts_api_keys_even_with_all_scopes(media_clients, agent):
    owner = get_principal(media_clients.a)
    require_owner_session(owner)
    require_scope(owner, "media:write")
    row = mint(media_clients.a, list(API_KEY_SCOPES))
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    principal = get_principal(agent)
    require_scope(principal, "media:write")
    with pytest.raises(HTTPException) as err:
        require_owner_session({**principal, "role": "owner"})
    assert err.value.status_code == 403
    with pytest.raises(HTTPException):
        require_scope(principal, "media:approve")
    with pytest.raises(HTTPException):
        require_scope({"role": "owner", "scopes": API_KEY_SCOPES}, "media:write")


@pytest.mark.parametrize("raw", ["null", "{}", '"media:write"', '["media:approve"]', "[123]", "{"])
def test_corrupt_scope_metadata_denies_authentication(media_clients, agent, raw):
    row = mint(media_clients.a, ["projects:read"])
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE api_keys SET scopes_json = ? WHERE id = ?", (raw, row["id"]))
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/projects").status_code == 401


def test_scope_migration_preserves_legacy_keys_and_is_idempotent(legacy_db):
    from webapp.migrations import migrate_api_key_scopes

    user = create_tenant_user(legacy_db, "keys", "Keys", "keys@example.test", "password123")
    key, original = create_api_key(legacy_db, user["tenant_id"])
    with db.connect(legacy_db) as con:
        before = con.execute("SELECT * FROM api_keys WHERE id = ?", (original["id"],)).fetchone()
    for _ in range(2):
        migrate_api_key_scopes(legacy_db)
    with db.connect(legacy_db) as con:
        after = con.execute("SELECT * FROM api_keys WHERE id = ?", (original["id"],)).fetchone()
        versions = con.execute("SELECT version FROM schema_migrations").fetchall()
    assert {field: after[field] for field in before} == before
    assert after["scopes_json"] is None
    assert after["expires_at"] is None
    assert versions == [{"version": "api_key_scopes_v1"}]
    assert resolve_api_key(legacy_db, key)["scopes"] == []
    new_key, row = create_scoped_api_key(legacy_db, user["tenant_id"], "new", ["media:write"])
    assert resolve_api_key(legacy_db, new_key)["scopes"] == ["media:write"]
    assert row["expires_at"] - row["created_at"] == 30 * 86400


def test_scope_migration_rolls_back_ddl_on_failure_and_retries(legacy_db, monkeypatch):
    from webapp.migrations import migrate_api_key_scopes

    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if sql.startswith("INSERT INTO schema_migrations"):
            raise RuntimeError("fallo sintético del marcador")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="fallo sintético"):
            migrate_api_key_scopes(legacy_db)
    with db.connect(legacy_db) as con:
        columns = (
            con.execute("PRAGMA table_info(api_keys)").fetchall()
            if con.dialect == "sqlite"
            else con.execute(
                "SELECT column_name AS name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = ?",
                ("api_keys",),
            ).fetchall()
        )
    assert "scopes_json" not in {row["name"] for row in columns}
    migrate_api_key_scopes(legacy_db)


@pytest.mark.parametrize("expiry", [0, -1, True, "future", 1.5, "too-far"])
def test_storage_validates_expiration_even_outside_http(media_clients, expiry):
    tenant_id = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    if expiry == "too-far":
        expiry = int(time.time()) + 366 * 86400
    with pytest.raises(ValueError, match="caducidad"):
        create_scoped_api_key(media_clients.db_path, tenant_id, "bad", [], expiry)


@pytest.mark.parametrize(
    "method,path,scope",
    [
        ("GET", "/api/v1/brands", "brands:read"),
        ("GET", "/api/v1/brands/999", "brands:read"),
        ("GET", "/api/v1/brands/999/logo-options", "brands:read"),
        ("GET", "/api/v1/wizard/brands", "brands:read"),
        ("GET", "/api/v1/gallery", "media:read"),
        ("GET", "/api/v1/gallery/999", "media:read"),
        ("GET", "/api/v1/variations/999/file", "media:read"),
        ("GET", "/api/v1/batches/999", "media:read"),
        ("GET", "/api/v1/batches/999/variations", "media:read"),
        ("GET", "/api/v1/batches/999/events", "media:read"),
        ("GET", "/api/v1/batches/999/plan", "media:read"),
        ("POST", "/api/v1/downloads/batch/999", "media:read"),
        ("POST", "/api/v1/downloads/zip", "media:read"),
    ],
)
def test_scoped_key_cannot_bypass_read_scopes_on_legacy_routes(
    media_clients, agent, method, path, scope
):
    from webapp.api.permissions import require_legacy_route_scope

    row = mint(media_clients.a, ["projects:read"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.request(method, path, json={}).status_code == 403
    # El helper prueba la concesión exacta sin inventar recursos de terceros.
    principal = get_principal(agent)
    routes = {
        "/api/v1/brands/999": "/api/v1/brands/{brand_id}",
        "/api/v1/brands/999/logo-options": "/api/v1/brands/{brand_id}/logo-options",
        "/api/v1/gallery/999": "/api/v1/gallery/{brand_id}",
        "/api/v1/variations/999/file": "/api/v1/variations/{variation_id}/file",
        "/api/v1/batches/999": "/api/v1/batches/{batch_id}",
        "/api/v1/batches/999/variations": "/api/v1/batches/{batch_id}/variations",
        "/api/v1/batches/999/events": "/api/v1/batches/{batch_id}/events",
        "/api/v1/batches/999/plan": "/api/v1/batches/{batch_id}/plan",
        "/api/v1/downloads/batch/999": "/api/v1/downloads/batch/{batch_id}",
    }
    route = routes.get(path, path)
    require_legacy_route_scope({**principal, "scopes": frozenset({scope})}, method, route)


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("POST", "/api/v1/brands", {"slug": "bad", "name": "Bad"}),
        ("PUT", "/api/v1/brands/999", {"name": "Bad"}),
        ("DELETE", "/api/v1/brands/999", None),
        ("POST", "/api/v1/brands/999/set-identity", {"logo_seed": 1}),
        ("POST", "/api/v1/gallery/select", {}),
        ("DELETE", "/api/v1/variations/999", None),
        ("POST", "/api/v1/variations/delete", {}),
    ],
)
def test_scoped_keys_cannot_mutate_identity_or_select_legacy_assets(
    media_clients, agent, method, path, payload
):
    row = mint(media_clients.a, list(API_KEY_SCOPES))
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.request(method, path, json=payload).status_code == 403


@pytest.mark.parametrize(
    "method,route",
    [
        ("GET", "/api/v1/new-route"),
        ("POST", "/api/v1/projects/{project_id}/approve"),
        ("PUT", "/api/v1/projects"),
        ("POST", "/auth/me"),
    ],
)
def test_unregistered_scoped_operations_fail_closed(method, route):
    from webapp.api.permissions import require_legacy_route_scope

    with pytest.raises(HTTPException) as err:
        require_legacy_route_scope(
            {"auth_method": "api_key", "scopes": API_KEY_SCOPES}, method, route
        )
    assert err.value.status_code == 403


def test_scoped_storage_resolves_expiry_revocation_and_metadata_in_both_dialects(isolated_db):
    from webapp.storage import revoke_api_key

    db.init_db(isolated_db)
    user = create_tenant_user(isolated_db, "keys", "Keys", "keys@example.test", "password123")
    key, row = create_scoped_api_key(isolated_db, user["tenant_id"], "new", ["projects:read"])
    resolved = resolve_api_key(isolated_db, key)
    assert resolved["id"] == row["id"]
    assert resolved["legacy"] is False
    assert resolved["scopes"] == ["projects:read"]
    assert "key_hash" not in resolved
    with db.connect(isolated_db) as con:
        con.execute(
            "UPDATE api_keys SET expires_at = ? WHERE tenant_id = ? AND id = ?",
            (int(time.time()) - 1, user["tenant_id"], row["id"]),
        )
    assert resolve_api_key(isolated_db, key) is None
    key, row = create_scoped_api_key(isolated_db, user["tenant_id"], "new", ["media:write"])
    assert not revoke_api_key(isolated_db, user["tenant_id"] + 1, row["id"])
    assert resolve_api_key(isolated_db, key) is not None
    assert revoke_api_key(isolated_db, user["tenant_id"], row["id"])
    assert resolve_api_key(isolated_db, key) is None


def test_read_scopes_allow_real_legacy_routes_without_granting_other_reads(media_clients, agent):
    row = mint(media_clients.a, ["brands:read"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/brands").status_code == 200
    assert agent.get("/api/v1/wizard/brands").status_code == 200
    assert agent.get("/api/v1/gallery").status_code == 403
    row = mint(media_clients.a, ["media:read"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/gallery").status_code == 200
    assert agent.get("/api/v1/brands").status_code == 403
    # Pasar la autorización no elimina el aislamiento ni fabrica un archivo.
    assert agent.get("/api/v1/variations/999/file").status_code == 404


def test_write_scope_does_not_inherit_media_read(media_clients, agent):
    row = mint(media_clients.a, ["media:write"])
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/gallery").status_code == 403
    assert agent.get("/api/v1/batches/999").status_code == 403
    # Encargo de render inválido: el scope pasó y la validación del cuerpo falla.
    assert agent.post("/api/v1/generate", json={}).status_code == 422
    assert agent.post("/api/v1/batches", json={}).status_code == 422


def test_future_route_requires_explicit_scoped_registration(media_clients, agent):
    from fastapi import Depends
    from fastapi.routing import APIRoute

    def future_private(user: Annotated[dict, Depends(current_user)]):
        return {"tenant_id": user["tenant_id"]}

    app = media_clients.a.app
    app.router.routes.insert(
        0, APIRoute("/api/v1/_future-private", future_private, methods=["GET"])
    )
    row = mint(media_clients.a, list(API_KEY_SCOPES))
    agent.headers["Authorization"] = f"Bearer {row['key']}"
    assert agent.get("/api/v1/_future-private").status_code == 403
    assert media_clients.a.get("/api/v1/_future-private").status_code == 200
    tenant_id = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    legacy_key, _ = create_api_key(media_clients.db_path, tenant_id)
    agent.headers["Authorization"] = f"Bearer {legacy_key}"
    assert agent.get("/api/v1/_future-private").status_code == 403


@pytest.fixture
def permission_db_clients(isolated_db, tmp_path, monkeypatch):
    """Reutiliza la BD aislada de Task1 para HTTP real en ambos dialectos."""
    import secrets

    from webapp.app import create_app
    from webapp.config import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    settings = Settings(
        data_root=tmp_path,
        sqlite_path=tmp_path / "http-permissions.db",
        db_url=str(isolated_db),
        jwt_secret=secrets.token_urlsafe(48),
    )
    app = create_app(settings, output_root=tmp_path / "output")
    a, b = TestClient(app), TestClient(app)
    try:
        for client, slug in ((a, "alpha"), (b, "beta")):
            response = client.post(
                "/auth/register",
                json={
                    "tenant_slug": slug,
                    "tenant_name": slug,
                    "email": f"{slug}@example.test",
                    "password": "test-password-123",
                },
            )
            assert response.status_code == 201
        assert app.state.worker is None
        yield a, b, isolated_db
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("operation", ["create", "update", "delete", "set-identity"])
def test_member_session_cannot_mutate_identity_after_db_role_change(
    permission_db_clients, operation
):
    owner, other, url = permission_db_clients
    response = owner.post(
        "/api/v1/brands", json={"slug": "original", "name": "Original", "logo_seed": 1}
    )
    assert response.status_code == 201
    original = response.json()
    user = owner.get("/auth/me").json()["user"]
    tenant_id = owner.get("/auth/me").json()["tenant"]["id"]
    foreign_key = mint(other, list(API_KEY_SCOPES))
    owner.headers["Authorization"] = f"Bearer {foreign_key['key']}"
    with db.connect(url) as con:
        con.execute(
            "UPDATE users SET role = ? WHERE tenant_id = ? AND id = ?",
            ("member", tenant_id, user["id"]),
        )
    me = owner.get("/auth/me").json()
    assert me["user"]["role"] == "member"
    assert me["tenant"]["id"] == tenant_id
    assert owner.get(f"/api/v1/brands/{original['id']}").json() == original
    assert owner.get("/api/v1/brands").json()["items"] == [original]
    assert owner.get("/api/v1/wizard/brands").status_code == 200
    assert owner.get("/api/v1/gallery").status_code == 200
    mutations = {
        "create": ("POST", "/api/v1/brands", {"slug": "blocked", "name": "Blocked"}, 201),
        "update": ("PUT", f"/api/v1/brands/{original['id']}", {"logo_seed": 99}, 200),
        "delete": ("DELETE", f"/api/v1/brands/{original['id']}", None, 204),
        "set-identity": (
            "POST",
            f"/api/v1/brands/{original['id']}/set-identity",
            {"logo_seed": 99},
            200,
        ),
    }
    method, path, payload, owner_status = mutations[operation]
    assert owner.request(method, path, json=payload).status_code == 403
    assert owner.get(f"/api/v1/brands/{original['id']}").json() == original
    assert owner.get("/api/v1/brands").json()["items"] == [original]
    with db.connect(url) as con:
        con.execute(
            "UPDATE users SET role = ? WHERE tenant_id = ? AND id = ?",
            ("owner", tenant_id, user["id"]),
        )
    assert owner.request(method, path, json=payload).status_code == owner_status


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer",
        "Bearer\tinvalid",
        "",
        "Basic invalid",
        "Bearer invalid extra",
        "Bearer \tinvalid",
        "Bearer invalid\t",
    ],
)
def test_malformed_bearer_never_falls_back_to_x_api_key(permission_db_clients, authorization):
    owner, _, _ = permission_db_clients
    row = mint(owner, ["projects:read"])
    agent = TestClient(owner.app)
    try:
        agent.headers["X-API-Key"] = row["key"]
        assert agent.get("/api/v1/projects").status_code == 200
        agent.headers["Authorization"] = authorization
        assert agent.get("/api/v1/projects").status_code == 401
        # La cookie válida mantiene prioridad sobre el header malformado.
        owner.headers["Authorization"] = authorization
        assert owner.get("/api/v1/projects").status_code == 200
    finally:
        agent.close()
