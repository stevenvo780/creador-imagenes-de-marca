"""Initial TikTok consent using real OAuth validation and fictitious HTTP only."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import httpx
import pytest

from webapp import db
from webapp.publications.oauth import OAuthConfig
from webapp.publications.oauth_providers import OfficialOAuthClient
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.media_helpers import project
from webapp.tests.test_projects import isolated_db as _isolated_db

media_clients = _media_clients
CALLBACK = "https://testserver/api/v1/publications/oauth/callback"


def provider(
    config,
    *,
    token_id="open-42",
    profile_id="open-42",
    scope="user.info.basic,video.publish",
    expires=7200,
    hook=None,
    name="Test TikTok",
):
    def remote(request):
        assert request.url.host == "open.tiktokapis.com"
        if request.url.path == "/v2/oauth/token/":
            assert request.method == "POST"
            if hook:
                hook()
            return httpx.Response(
                200,
                json={
                    "access_token": "fictitious-token",
                    "refresh_token": "fictitious-refresh",
                    "open_id": token_id,
                    "scope": scope,
                    "expires_in": expires,
                    "token_type": "Bearer",
                },
            )
        assert request.url.path == "/v2/user/info/"
        assert request.headers["Authorization"] == "Bearer fictitious-token"
        return httpx.Response(
            200,
            json={
                "data": {"user": {"open_id": profile_id, "display_name": name}},
                "error": {"code": "ok", "message": "", "log_id": "fixture"},
            },
        )

    return OfficialOAuthClient(config, httpx.MockTransport(remote))


def test_api_initial_consent_discovers_identity_without_provisional_connection(media_clients):
    from webapp import db
    from webapp.publications.vault import unseal

    a = media_clients.a
    pid = project(a, "initial-tiktok")["id"]
    config = OAuthConfig("tiktok", "oauth2", "fixture-app", "fixture-secret", (CALLBACK,))
    a.app.state.settings = replace(
        a.app.state.settings,
        publication_vault_key=base64.b64encode(b"k" * 32).decode(),
        publication_vault_key_id="fixture",
    )
    a.app.state.publication_oauth_configs = {("tiktok", "oauth2"): config}
    a.app.state.publication_oauth_clients = {("tiktok", "oauth2"): provider(config)}
    started = a.post(
        "/api/v1/publications/oauth/onboarding/start",
        json={
            "platform": "tiktok",
            "api_mode": "oauth2",
            "project_ids": [pid],
            "redirect_uri": CALLBACK,
        },
    )
    assert started.status_code == 200, started.text
    assert a.get("/api/v1/publications/connections").json() == {"items": []}
    cookie = started.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    response = a.get(
        "/api/v1/publications/oauth/callback",
        params={"state": started.json()["state"], "code": "fixture-code"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["remote_id"] == "open-42"
    assert result["status"] == "active"
    assert result["project_ids"] == [pid]
    assert "fictitious-token" not in response.text
    with db.connect(media_clients.db_path) as con:
        vault = con.execute(
            "SELECT envelope_json FROM publication_connection_vault WHERE tenant_id=? AND connection_id=?",
            (result["tenant_id"], result["id"]),
        ).fetchone()
    credential = json.loads(
        unseal(b"k" * 32, result["tenant_id"], result["id"], json.loads(vault["envelope_json"]))
    )
    assert credential["access_token"] == "fictitious-token"


isolated_db = _isolated_db
NOW = 1791680000


@pytest.fixture
def case(isolated_db, monkeypatch):
    from webapp.publications import oauth_onboarding

    monkeypatch.setattr(oauth_onboarding.time, "time", lambda: NOW + 10)
    db.init_db(isolated_db)
    owners, projects = [], []
    for slug in ("a", "b"):
        with db.connect(isolated_db) as con:
            con.execute("INSERT INTO tenants(slug,name,created_at) VALUES (?,?,0)", (slug, slug))
            tid = db.get_last_insert_id(isolated_db, con, "tenants")
            con.execute(
                "INSERT INTO users(tenant_id,email,password_hash,role,created_at) VALUES (?,?,'unused','owner',0)",
                (tid, slug + "@example.test"),
            )
            uid = db.get_last_insert_id(isolated_db, con, "users")
            con.execute(
                "INSERT INTO projects(tenant_id,slug,name,created_at) VALUES (?,'pub','Pub',0)",
                (tid,),
            )
            pid = db.get_last_insert_id(isolated_db, con, "projects")
        owners.append((tid, uid))
        projects.append(pid)
    config = OAuthConfig("tiktok", "oauth2", "fixture-app", "fixture-secret", (CALLBACK,))
    return isolated_db, owners, projects, config


def principal(case, index=0):
    tid, uid = case[1][index]
    return {
        "tenant_id": tid,
        "user_id": uid,
        "auth_method": "session",
        "session_binding": "fixture-browser",
    }


def begin(case, index=0, **kwargs):
    from webapp.publications.oauth_onboarding import start_onboarding

    return start_onboarding(
        case[0],
        *case[1][index],
        "tiktok",
        CALLBACK,
        NOW,
        project_ids=kwargs.pop("project_ids", [case[2][index]]),
        session_binding="fixture-browser",
        config=case[3],
        key=b"k" * 32,
        key_id="fixture",
        **kwargs,
    )


def finish(case, state, client=None, **kwargs):
    from webapp.publications.oauth_onboarding import finish_onboarding

    return finish_onboarding(
        case[0],
        kwargs.pop("session_owner", principal(case)),
        state,
        "fixture-code",
        kwargs.pop("now", NOW + 10),
        client or provider(case[3]),
        key=kwargs.pop("key", b"k" * 32),
        key_id="fixture",
        **kwargs,
    )


def empty(case):
    with db.connect(case[0]) as con:
        for table in (
            "publication_connections",
            "publication_connection_details",
            "publication_project_connections",
            "publication_connection_vault",
        ):
            assert con.execute(f"SELECT * FROM {table}").fetchall() == []


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"profile_id": "another-id"}, "provider_verification_failed"),
        ({"scope": "user.info.basic"}, "insufficient_scopes"),
        ({"expires": 0}, "token_expiry_unknown"),
        ({"profile_id": "", "token_id": ""}, "provider_verification_failed"),
        ({"name": "fictitious-token"}, "provider_verification_failed"),
        ({"name": "fixture-secret"}, "provider_verification_failed"),
    ],
)
def test_invalid_official_evidence_creates_nothing_and_consumes_state(case, kwargs, reason):
    from webapp.publications.contracts import Conflict

    state = begin(case)["state"]
    with pytest.raises(Conflict, match=reason):
        finish(case, state, provider(case[3], **kwargs))
    empty(case)
    with pytest.raises(Conflict, match="oauth_state_unavailable"):
        finish(case, state)


@pytest.mark.parametrize("cause", ["nonce", "tenant", "owner", "expired", "member", "api_key"])
def test_foreign_or_expired_authority_never_creates_connection(case, cause):
    from webapp.publications.contracts import Conflict, Forbidden

    state = begin(case)["state"]
    who, now = principal(case), NOW + 10
    if cause == "nonce":
        who["session_binding"] = "other-browser"
    if cause == "tenant":
        who = principal(case, 1)
    if cause == "owner":
        who["user_id"] = case[1][1][1]
    if cause == "expired":
        now = NOW + 600
    if cause == "api_key":
        who["auth_method"] = "api_key"
    if cause == "member":
        with db.connect(case[0]) as con:
            con.execute("UPDATE users SET role='member' WHERE id=?", (case[1][0][1],))
    with pytest.raises((Conflict, Forbidden)):
        finish(case, state, session_owner=who, now=now)
    empty(case)


@pytest.mark.parametrize("cause", ["owner", "project", "config", "state_expiry", "token_expiry"])
def test_authority_and_expiry_revalidated_after_exchange(case, cause, monkeypatch):
    from webapp.publications import oauth_onboarding
    from webapp.publications.contracts import Conflict, Forbidden

    state = begin(case)["state"]

    def revoke():
        if cause in ("owner", "project"):
            with db.connect(case[0]) as con:
                if cause == "owner":
                    con.execute("UPDATE users SET role='member' WHERE id=?", (case[1][0][1],))
                else:
                    con.execute("UPDATE projects SET archived=1 WHERE id=?", (case[2][0],))
        if cause == "config":
            client.config = replace(case[3], client_id="rotated")
        if cause in ("state_expiry", "token_expiry"):
            monkeypatch.setattr(
                oauth_onboarding.time,
                "time",
                lambda: NOW + (600 if cause == "state_expiry" else 11),
            )

    client = provider(case[3], hook=revoke, expires=1 if cause == "token_expiry" else 7200)
    with pytest.raises((Conflict, Forbidden)):
        finish(case, state, client)
    empty(case)


@pytest.mark.parametrize("cause", ["denied", "vault", "remote"])
def test_failure_keeps_state_consumed_and_no_partial_records(case, cause):
    from webapp.publications.contracts import Conflict

    state = begin(case)["state"]

    def fail():
        raise RuntimeError("fictitious-token fixture-secret fixture-code")

    client = provider(case[3], hook=fail if cause == "remote" else None)
    with pytest.raises(Conflict) as error:
        finish(
            case,
            state,
            client,
            key=None if cause == "vault" else b"k" * 32,
            provider_error=cause == "denied",
        )
    assert all(
        secret not in str(error.value)
        for secret in ("fictitious-token", "fixture-secret", "fixture-code")
    )
    empty(case)
    with pytest.raises(Conflict, match="oauth_state_unavailable"):
        finish(case, state)


def test_duplicate_does_not_change_existing_metadata_projects_or_vault(case):
    from webapp.publications.contracts import Conflict

    first, second = begin(case)["state"], begin(case)["state"]
    row = finish(case, first)

    def snapshot():
        with db.connect(case[0]) as con:
            return {
                table: con.execute(f"SELECT * FROM {table}").fetchall()
                for table in (
                    "publication_connections",
                    "publication_connection_details",
                    "publication_project_connections",
                    "publication_connection_vault",
                )
            }

    before = snapshot()
    with pytest.raises(Conflict, match="connection_already_exists"):
        finish(case, second)
    assert snapshot() == before
    other = finish(case, begin(case, 1)["state"], session_owner=principal(case, 1))
    assert row["remote_id"] == other["remote_id"] and row["tenant_id"] != other["tenant_id"]


@pytest.mark.parametrize("same_state", [True, False])
def test_concurrent_callbacks_create_exactly_one_account(case, same_state):
    import threading

    from webapp.publications.contracts import Conflict

    states = [begin(case)["state"]]
    states.append(states[0] if same_state else begin(case)["state"])
    calls = []
    barrier = threading.Barrier(2) if not same_state else None

    def exchange():
        calls.append(1)
        if barrier:
            barrier.wait(timeout=10)

    def run(state):
        try:
            return finish(case, state, provider(case[3], hook=exchange))["status"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, states)) == ["active", "conflict"]
    assert len(calls) == (1 if same_state else 2)
    with db.connect(case[0]) as con:
        assert len(con.execute("SELECT * FROM publication_connection_vault").fetchall()) == 1


@pytest.mark.parametrize("projects", [[], [0], [True], ["1"], [2**63]])
def test_start_rejects_invalid_projects(case, projects):
    from webapp.publications.contracts import InvalidInput

    with pytest.raises(InvalidInput):
        begin(case, project_ids=projects)
    empty(case)


def test_start_rejects_foreign_or_archived_project_and_member(case):
    from webapp.publications.contracts import Forbidden

    with pytest.raises(Forbidden):
        begin(case, project_ids=[case[2][1]])
    with db.connect(case[0]) as con:
        con.execute("UPDATE projects SET archived=1 WHERE id=?", (case[2][0],))
    with pytest.raises(Forbidden):
        begin(case)
    with db.connect(case[0]) as con:
        con.execute("UPDATE users SET role='member' WHERE id=?", (case[1][1][1],))
    with pytest.raises(Forbidden):
        begin(case, 1)
    empty(case)


@pytest.mark.parametrize(
    "change",
    [
        {"remote_id": "browser-id"},
        {"connection_id": 1},
        {"access_token": "secret"},
        {"scopes": ["video.publish"]},
        {"platform": "facebook"},
        {"api_mode": "page"},
        {"project_ids": [True]},
    ],
)
def test_api_rejects_browser_authority_and_other_modes(media_clients, change):
    a = media_clients.a
    pid = project(a, "strict")["id"]
    response = a.post(
        "/api/v1/publications/oauth/onboarding/start",
        json={
            "platform": "tiktok",
            "api_mode": "oauth2",
            "project_ids": [pid],
            "redirect_uri": CALLBACK,
            **change,
        },
    )
    assert response.status_code == 422


def test_session_expires_during_exchange_before_atomic_create(case, monkeypatch):
    from webapp.publications import oauth_onboarding
    from webapp.publications.contracts import Forbidden

    state = begin(case)["state"]
    who = {**principal(case), "session_expires_at": NOW + 11}

    def expire():
        monkeypatch.setattr(oauth_onboarding.time, "time", lambda: NOW + 11)

    with pytest.raises(Forbidden):
        finish(case, state, provider(case[3], hook=expire), session_owner=who)
    empty(case)


def test_runtime_config_rotated_during_exchange_rejected_even_with_original_client(case):
    from webapp.publications.contracts import Conflict

    current = [case[3]]

    def rotate():
        current[0] = replace(case[3], client_id="rotated-app")

    state = begin(case)["state"]
    with pytest.raises(Conflict, match="oauth_not_configured"):
        finish(case, state, provider(case[3], hook=rotate), config_getter=lambda: current[0])
    empty(case)


def test_migration_is_additive_and_idempotent_with_existing_verified_account(case):
    from webapp.publications.migrations import migrate_publications

    finish(case, begin(case)["state"])

    def snapshot():
        with db.connect(case[0]) as con:
            return {
                table: con.execute(f"SELECT * FROM {table}").fetchall()
                for table in (
                    "publication_connections",
                    "publication_connection_details",
                    "publication_project_connections",
                    "publication_connection_vault",
                    "publication_oauth_onboarding_states",
                )
            }

    before = snapshot()
    migrate_publications(case[0])
    migrate_publications(case[0])
    assert snapshot() == before


def test_secure_api_callback_requires_original_browser_and_owner(media_clients):
    from fastapi.testclient import TestClient

    app = media_clients.a.app
    pid = project(media_clients.a, "secure-initial")["id"]
    config = OAuthConfig("tiktok", "oauth2", "fixture-app", "fixture-secret", (CALLBACK,))
    app.state.settings = replace(
        app.state.settings,
        publication_vault_key=base64.b64encode(b"k" * 32).decode(),
        publication_vault_key_id="fixture",
    )
    app.state.publication_oauth_configs = {("tiktok", "oauth2"): config}
    calls = []
    app.state.publication_oauth_clients = {
        ("tiktok", "oauth2"): provider(config, hook=lambda: calls.append(1))
    }
    first = TestClient(app, base_url="https://testserver")
    second = TestClient(app, base_url="https://testserver")
    try:
        assert app.state.worker is None
        credentials = {"email": "alpha@example.test", "password": "test-password-123"}
        assert first.post("/auth/login", json=credentials).status_code == 200
        assert second.post("/auth/login", json=credentials).status_code == 200
        start = first.post(
            "/api/v1/publications/oauth/onboarding/start",
            json={
                "platform": "tiktok",
                "api_mode": "oauth2",
                "project_ids": [pid],
                "redirect_uri": CALLBACK,
            },
        )
        assert start.status_code == 200
        cookie = start.headers["set-cookie"]
        assert all(
            part in cookie
            for part in (
                "__Host-eikon_publication_oauth=",
                "HttpOnly",
                "Secure",
                "SameSite=lax",
                "Path=/",
            )
        )
        assert "Domain=" not in cookie
        params = {"state": start.json()["state"], "code": "fixture-code"}
        assert second.get("/api/v1/publications/oauth/callback", params=params).status_code == 403
        assert (
            media_clients.b.get("/api/v1/publications/oauth/callback", params=params).status_code
            == 403
        )
        assert calls == []
        response = first.get("/api/v1/publications/oauth/callback", params=params)
        assert response.status_code == 200, response.text
        assert response.json()["remote_id"] == "open-42"
        assert calls == [1]
        assert first.get("/api/v1/publications/oauth/callback", params=params).status_code == 403
        assert app.state.worker is None
    finally:
        first.close()
        second.close()


def test_existing_tiktok_reconnection_still_rejects_changed_identity(case):
    from webapp.publications.oauth import finish_oauth, start_oauth

    row = finish(case, begin(case)["state"])
    flow = start_oauth(
        case[0],
        *case[1][0],
        "tiktok",
        CALLBACK,
        NOW,
        session_binding="fixture-browser",
        connection_id=row["id"],
        config=case[3],
    )
    result = finish_oauth(
        case[0],
        principal(case),
        flow["state"],
        "fixture-code",
        NOW + 10,
        provider(case[3], token_id="changed-id", profile_id="changed-id"),
        key=b"k" * 32,
        key_id="fixture",
    )
    assert result["status"] == "held"
    assert result["hold_reason"] == "remote_identity_mismatch"
    assert result["remote_id"] == "open-42"


def test_api_signed_session_expiring_during_exchange_creates_nothing(media_clients, monkeypatch):
    from webapp.publications import oauth_onboarding
    from webapp.security import create_jwt, decode_jwt

    a = media_clients.a
    pid = project(a, "expiring-browser")["id"]
    settings = a.app.state.settings
    claims = decode_jwt(a.cookies.get(settings.cookie_name), settings.jwt_secret)
    config = OAuthConfig("tiktok", "oauth2", "fixture-app", "fixture-secret", (CALLBACK,))
    a.app.state.settings = replace(
        settings,
        publication_vault_key=base64.b64encode(b"k" * 32).decode(),
        publication_vault_key_id="fixture",
    )
    a.app.state.publication_oauth_configs = {("tiktok", "oauth2"): config}
    monkeypatch.setattr(oauth_onboarding.time, "time", lambda: NOW)
    a.cookies.set(
        settings.cookie_name,
        create_jwt({**claims, "exp": NOW + 1}, settings.jwt_secret, 1),
        domain="testserver.local",
        path="/",
    )
    start = a.post(
        "/api/v1/publications/oauth/onboarding/start",
        json={
            "platform": "tiktok",
            "api_mode": "oauth2",
            "project_ids": [pid],
            "redirect_uri": CALLBACK,
        },
    )
    assert start.status_code == 200
    # The normal sliding login cookie refreshes; deliberately restore the verified
    # one-second browser session before the callback request.
    a.cookies.set(
        settings.cookie_name,
        create_jwt({**claims, "exp": NOW + 1}, settings.jwt_secret, 1),
        domain="testserver.local",
        path="/",
    )

    def expire():
        monkeypatch.setattr(oauth_onboarding.time, "time", lambda: NOW + 1)

    a.app.state.publication_oauth_clients = {("tiktok", "oauth2"): provider(config, hook=expire)}
    response = a.get(
        "/api/v1/publications/oauth/callback",
        params={"state": start.json()["state"], "code": "fixture-code"},
    )
    assert response.status_code == 403, response.text
    with db.connect(media_clients.db_path) as con:
        assert con.execute("SELECT * FROM publication_connections").fetchall() == []
        assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []
