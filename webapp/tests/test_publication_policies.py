"""Políticas autónomas: aislamiento, CAS, validación y migración real."""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from webapp import db
from webapp.tests.media_helpers import brand, project
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.test_projects import isolated_db as _isolated_db

media_clients = _media_clients
isolated_db = _isolated_db


def insert_catalog(url, tenant_id, owner_id):
    """Catálogo exclusivamente de prueba, sin credenciales de proveedores."""
    now = int(time.time())
    with db.connect(url) as con:
        con.execute(
            "INSERT INTO projects(tenant_id,slug,name,created_at) VALUES (?,'pub','Pub',?)",
            (tenant_id, now),
        )
        pid = db.get_last_insert_id(url, con, "projects")
        con.execute(
            "INSERT INTO brands(tenant_id,project_id,slug,name,created_at) VALUES (?,?,'product','Product',?)",
            (tenant_id, pid, now),
        )
        bid = db.get_last_insert_id(url, con, "brands")
        con.execute(
            "INSERT INTO publication_connections(tenant_id,platform,api_mode,remote_id,status,version,expires_at,capabilities_json,created_at) VALUES (?,'facebook','page','remote-test','active',1,?,'{}',?)",
            (tenant_id, now + 7200, now),
        )
        cid = db.get_last_insert_id(url, con, "publication_connections")
    return policy_payload(pid, bid, cid)


def policy_payload(pid, bid, cid):
    return {
        "enabled": True,
        "project_ids": [pid],
        "product_ids": [bid],
        "connection_ids": [cid],
        "allowed_sources": ["https://example.test/manual"],
        "timezone": "America/Bogota",
        "frequency_minutes": 60,
        "max_daily_per_destination": 2,
        "window_minutes": 60,
        "valid_from": "2020-01-01T00:00:00Z",
        "expires_at": "2090-01-01T00:00:00+00:00",
        "spend_allowed": False,
    }


@pytest.fixture
def publication_db(isolated_db):
    db.init_db(isolated_db)
    owners = []
    for slug in ("a", "b"):
        with db.connect(isolated_db) as con:
            con.execute("INSERT INTO tenants(slug,name,created_at) VALUES (?,?,0)", (slug, slug))
            tenant_id = db.get_last_insert_id(isolated_db, con, "tenants")
            con.execute(
                "INSERT INTO users(tenant_id,email,password_hash,role,created_at) VALUES (?,?,'unused','owner',0)",
                (tenant_id, f"{slug}@example.test"),
            )
            owner_id = db.get_last_insert_id(isolated_db, con, "users")
        owners.append((tenant_id, owner_id))
    payloads = [insert_catalog(isolated_db, *owner) for owner in owners]
    return isolated_db, owners, payloads


def api_payload(media_clients, client):
    p = project(client, "pub")
    b = brand(client, p["id"], "product")
    tenant_id = client.get("/auth/me").json()["tenant"]["id"]
    with db.connect(media_clients.db_path) as con:
        con.execute(
            "INSERT INTO publication_connections(tenant_id,platform,api_mode,remote_id,status,version,capabilities_json,created_at) VALUES (?,'facebook','page','remote-test','active',1,'{}',0)",
            (tenant_id,),
        )
        cid = db.get_last_insert_id(media_clients.db_path, con, "publication_connections")
    return policy_payload(p["id"], b["id"], cid)


def test_new_tenants_start_disabled(media_clients):
    for client in (media_clients.a, media_clients.b):
        r = client.get("/api/v1/publications/policy")
        assert r.status_code == 200
        assert r.json() == {"version": 0, "enabled": False}


@pytest.mark.parametrize(
    "scopes",
    [
        ["media:write"],
        [
            "projects:read",
            "projects:write",
            "brands:read",
            "briefs:write",
            "media:read",
            "media:write",
        ],
    ],
)
def test_no_legacy_scope_can_enable_autonomy(media_clients, scopes):
    a = media_clients.a
    key = a.post("/api/v1/auth/api-keys", json={"name": "existing", "scopes": scopes}).json()["key"]
    a.cookies.clear()
    r = a.post(
        "/api/v1/publications/policy",
        headers={"Authorization": f"Bearer {key}"},
        json={"expected_version": 0, "enabled": True},
    )
    assert r.status_code == 403


def test_policy_api_owner_tenant_and_history(media_clients):
    payload = api_payload(media_clients, media_clients.a)
    a = media_clients.a.post("/api/v1/publications/policy", json={"expected_version": 0, **payload})
    assert a.status_code == 201, a.text
    assert a.json()["version"] == 1
    assert media_clients.b.get("/api/v1/publications/policy").json() == {
        "version": 0,
        "enabled": False,
    }
    assert (
        media_clients.b.post(
            "/api/v1/publications/policy", json={"expected_version": 0, **payload}
        ).status_code
        == 403
    )
    assert (
        media_clients.a.post(
            "/api/v1/publications/policy", json={"expected_version": 0, **payload}
        ).status_code
        == 409
    )
    stopped = media_clients.a.post(
        "/api/v1/publications/policy", json={"expected_version": 1, "enabled": False}
    )
    assert stopped.status_code == 201
    assert stopped.json()["version"] == 2 and stopped.json()["enabled"] is False
    with db.connect(media_clients.db_path) as con:
        rows = con.execute(
            "SELECT version,enabled FROM publication_policies ORDER BY version"
        ).fetchall()
    assert rows == [{"version": 1, "enabled": 1}, {"version": 2, "enabled": 0}]


def test_cas_and_current_owner_in_both_databases(publication_db):
    from webapp.publications.contracts import Conflict, Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    tenant, owner = owners[0]
    policy = set_policy(url, tenant, owner, 0, payloads[0])
    assert policy["version"] == 1 and policy["enabled"] is True
    with pytest.raises(Forbidden):
        set_policy(url, tenant, owners[1][1], 1, payloads[0])
    with pytest.raises(Conflict):
        set_policy(url, tenant, owner, 0, payloads[0])
    with db.connect(url) as con:
        con.execute("UPDATE users SET role='member' WHERE tenant_id=? AND id=?", (tenant, owner))
    with pytest.raises(Forbidden):
        set_policy(url, tenant, owner, 1, {"enabled": False})


def test_concurrent_policy_cas_has_one_winner(publication_db):
    from webapp.publications.contracts import Conflict
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db

    def attempt(_):
        try:
            return set_policy(url, *owners[0], 0, payloads[0])["version"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2)), key=str) == [1, "conflict"]


@pytest.mark.parametrize(
    "field,bad",
    [
        ("project_ids", [True]),
        ("product_ids", [False]),
        ("connection_ids", [True]),
        ("project_ids", [0]),
        ("timezone", "Mars/Nowhere"),
        ("frequency_minutes", 0),
        ("frequency_minutes", True),
        ("max_daily_per_destination", 0),
        ("max_daily_per_destination", 1.5),
        ("window_minutes", 0),
        ("spend_allowed", True),
        ("enabled", 1),
        ("valid_from", "2020-01-01T00:00:00"),
        ("expires_at", "invalid"),
        ("expires_at", "2019-01-01T00:00:00Z"),
        ("allowed_sources", []),
        ("allowed_sources", ["*"]),
        ("allowed_sources", ["https://user:pass@example.test/x"]),
        ("unknown", "value"),
    ],
)
def test_invalid_policy_does_not_append(publication_db, field, bad):
    from webapp.publications.contracts import InvalidInput
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    with pytest.raises(InvalidInput):
        set_policy(url, *owners[0], 0, {**payloads[0], field: bad})
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_policies WHERE tenant_id=?", (owners[0][0],)
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("field", ["project_ids", "product_ids", "connection_ids"])
def test_policy_cannot_reference_foreign_catalog(publication_db, field):
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    with pytest.raises(Forbidden):
        set_policy(url, *owners[0], 0, {**payloads[0], field: payloads[1][field]})


def test_product_must_belong_to_allowed_project(publication_db):
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    with db.connect(url) as con:
        con.execute(
            "INSERT INTO projects(tenant_id,slug,name,created_at) VALUES (?,'other','Other',0)",
            (owners[0][0],),
        )
        other = db.get_last_insert_id(url, con, "projects")
    with pytest.raises(Forbidden):
        set_policy(url, *owners[0], 0, {**payloads[0], "project_ids": [other]})


@pytest.mark.parametrize("change", ["empty", "inactive", "expired", "archived"])
def test_activation_requires_available_owned_catalog(publication_db, change):
    from webapp.publications.contracts import Forbidden, InvalidInput
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    payload = payloads[0]
    with db.connect(url) as con:
        if change == "empty":
            payload = {**payload, "connection_ids": []}
        elif change == "archived":
            con.execute("UPDATE projects SET archived=1 WHERE tenant_id=?", (owners[0][0],))
        elif change == "inactive":
            con.execute(
                "UPDATE publication_connections SET status='held' WHERE tenant_id=?",
                (owners[0][0],),
            )
        else:
            con.execute(
                "UPDATE publication_connections SET expires_at=1 WHERE tenant_id=?", (owners[0][0],)
            )
    with pytest.raises((Forbidden, InvalidInput)):
        set_policy(url, *owners[0], 0, payload)


def test_canonical_contract_and_offset_normalization():
    from webapp.publications.contracts import InvalidInput, canonical_hash, normalize_schedule

    assert (
        canonical_hash({"b": 2, "a": "á"}) == hashlib.sha256(b'{"a":"\xc3\xa1","b":2}').hexdigest()
    )
    assert normalize_schedule("2026-10-11T09:00:00-05:00") == 1791727200
    assert normalize_schedule("2026-10-11T14:00:00Z") == 1791727200
    for value in (
        "2026-10-11T14:00:00",
        "2026-02-30T00:00:00Z",
        "2026-10-11T14:00:00+00:00:01",
        "invalid",
        7,
    ):
        with pytest.raises(InvalidInput):
            normalize_schedule(value)
    for value in (float("nan"), float("inf")):
        with pytest.raises(InvalidInput):
            canonical_hash({"x": value})


def test_policy_normalizes_sources_and_canonical_snapshot(publication_db):
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    row = set_policy(
        url,
        *owners[0],
        0,
        {**payloads[0], "allowed_sources": ["https://EXAMPLE.test:443/manual#section"]},
    )
    assert row["allowed_sources"] == ["https://example.test/manual"]
    with db.connect(url) as con:
        stored = con.execute(
            "SELECT payload_json,payload_hash FROM publication_policies WHERE tenant_id=?",
            (owners[0][0],),
        ).fetchone()
    assert stored["payload_hash"] == hashlib.sha256(stored["payload_json"].encode()).hexdigest()
    assert json.loads(stored["payload_json"])["spend_allowed"] is False


def test_publication_migration_is_idempotent_and_rolls_back(isolated_db, monkeypatch):
    from webapp.publications.migrations import migrate_publications

    db.init_db(isolated_db)
    db.init_db(isolated_db)
    with db.connect(isolated_db) as con:
        con.execute("DROP TABLE publication_grants")
        con.execute("DROP TABLE publication_policies")
        con.execute("DROP TABLE publication_connections")
        con.execute("DELETE FROM schema_migrations WHERE version='publication_policies_v1'")
    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if (
            sql.startswith("INSERT INTO schema_migrations")
            and params[0] == "publication_policies_v1"
        ):
            raise RuntimeError("injected-marker-failure")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="injected-marker-failure"):
            migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        if con.dialect == "sqlite":
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE name='publication_policies'"
            ).fetchone()
        else:
            row = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='publication_policies'"
            ).fetchone()
        assert row is None
    migrate_publications(isolated_db)
    migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM schema_migrations WHERE version='publication_policies_v1'"
            ).fetchone()["n"]
            == 1
        )


def test_schedule_accepts_iso_minute_precision_and_valid_offsets():
    from webapp.publications.contracts import InvalidInput, normalize_schedule

    assert normalize_schedule("2026-10-11T14:00Z") == 1791727200
    assert normalize_schedule("2026-10-11T09:00-0500") == 1791727200
    for value in ("2026-10-11T14:00:00+00:60", "2026-10-11T14:00:00+24:00"):
        with pytest.raises(InvalidInput):
            normalize_schedule(value)


def test_invalid_unicode_is_a_safe_domain_error():
    from webapp.publications.contracts import InvalidInput, canonical_hash

    with pytest.raises(InvalidInput):
        canonical_hash({"source": "\ud800"})


def test_owner_validation_safe_errors_and_legacy_key(media_clients):
    from webapp.storage import create_api_key

    a = media_clients.a
    me = a.get("/auth/me").json()
    for payload in (
        {"expected_version": True, "enabled": False},
        {"expected_version": 0, "enabled": False, "owner_id": 123},
        ["not-an-object"],
    ):
        r = a.post("/api/v1/publications/policy", json=payload)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str)
    r = a.post(
        "/api/v1/publications/policy",
        content=b"{invalid",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    key, _ = create_api_key(media_clients.db_path, me["tenant"]["id"])
    a.cookies.clear()
    assert (
        a.post(
            "/api/v1/publications/policy",
            headers={"Authorization": f"Bearer {key}"},
            content=b"{invalid",
        ).status_code
        == 403
    )


def test_member_cannot_manage_policy_even_with_minimal_body(media_clients):
    a = media_clients.a
    me = a.get("/auth/me").json()
    with db.connect(media_clients.db_path) as con:
        con.execute(
            "UPDATE users SET role='member' WHERE tenant_id=? AND id=?",
            (me["tenant"]["id"], me["user"]["id"]),
        )
    for route in ("/api/v1/publications/policy", "/api/v1/publications/grants"):
        assert a.post(route, json={}).status_code == 403
        assert a.get(route).status_code == 403


def test_expected_version_rejects_bool_without_appending(publication_db):
    from webapp.publications.contracts import InvalidInput
    from webapp.publications.policies import set_policy

    url, owners, _ = publication_db
    with pytest.raises(InvalidInput):
        set_policy(url, *owners[0], False, {"enabled": False})
