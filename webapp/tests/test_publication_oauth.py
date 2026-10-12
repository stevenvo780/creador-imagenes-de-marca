"""OAuth aislado: ProviderDouble simula exchange e identidad, nunca red real."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from webapp import db
from webapp.tests.media_helpers import media_clients as _media_clients
from webapp.tests.media_helpers import project
from webapp.tests.test_projects import isolated_db as _isolated_db
from webapp.tests.test_publication_connections import connection_payload
from webapp.tests.test_publication_policies import publication_db as _publication_db

isolated_db = _isolated_db
publication_db = _publication_db
media_clients = _media_clients
NOW = 1791680000
BINDING = "test-browser-nonce-" + "a" * 32


class ProviderDouble:
    """Contrato privado configurado por servidor; no evidencia productiva."""

    calls = 0

    def __init__(
        self, remote_id="page-42", scopes=None, expires_at=NOW + 7200, expiry_state="known"
    ):
        self.remote_id = remote_id
        self.scopes = (
            scopes
            if scopes is not None
            else ["pages_manage_posts", "pages_read_engagement", "pages_show_list"]
        )
        self.expires_at = expires_at
        self.expiry_state = expiry_state
        self.calls = 0

    def exchange(self, flow, code, verifier):
        assert code == "fake-code"
        self.calls += 1
        return {"access_token": "fake-token", "refresh_token": "fake-refresh"}

    def verify(self, flow, secrets, now):
        from webapp.publications.oauth import VerifiedAccount

        return VerifiedAccount(
            remote_id=self.remote_id,
            name="Test Page",
            scopes=tuple(self.scopes),
            expires_at=self.expires_at,
            expiry_state=self.expiry_state,
            evidence_hosts=("graph.facebook.com",),
            credential=secrets,
        )


@pytest.fixture
def oauth_case(publication_db):
    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import OAuthConfig

    url, owners, payloads = publication_db
    row = put_connection(url, *owners[0], connection_payload(payloads[0]))
    config = OAuthConfig(
        platform="facebook",
        api_mode="page",
        client_id="fake-app",
        client_secret="fake-app-secret",
        redirect_uris=("https://eikon.example.test/api/v1/publications/oauth/callback",),
        graph_version="v25.0",
    )
    return url, owners, row, config


def start(case, binding=BINDING):
    from webapp.publications.oauth import start_oauth

    url, owners, row, config = case
    return start_oauth(
        url,
        *owners[0],
        "facebook",
        config.redirect_uris[0],
        NOW,
        session_binding=binding,
        connection_id=row["id"],
        config=config,
    )


def owner(case, binding=BINDING, index=0):
    tenant, uid = case[1][index]
    return {
        "tenant_id": tenant,
        "user_id": uid,
        "session_binding": binding,
        "auth_method": "session",
    }


def finish(case, state, client=None, session_owner=None, now=NOW + 10, key=b"k" * 32):
    from webapp.publications.oauth import finish_oauth

    return finish_oauth(
        case[0],
        session_owner or owner(case),
        state,
        "fake-code",
        now,
        client or ProviderDouble(),
        key=key,
        key_id="test",
    )


def test_oauth_active_only_verified_identity_scopes_and_private_vault(oauth_case):
    from webapp.publications.vault import unseal

    flow = start(oauth_case)
    result = finish(oauth_case, flow["state"])
    assert result["status"] == "active"
    assert result["remote_id"] == "page-42"
    assert result["scopes"] == ["pages_manage_posts", "pages_read_engagement", "pages_show_list"]
    assert result["capabilities"]["publish"] is True
    assert "fake-token" not in json.dumps(result)
    assert "ciphertext" not in json.dumps(result)
    with db.connect(oauth_case[0]) as con:
        vault = con.execute(
            "SELECT envelope_json FROM publication_connection_vault WHERE tenant_id=? AND connection_id=?",
            (result["tenant_id"], result["id"]),
        ).fetchone()
        history = con.execute(
            "SELECT consumed_at,verifier_envelope_json FROM publication_oauth_states WHERE tenant_id=?",
            (result["tenant_id"],),
        ).fetchone()
    private = json.loads(
        unseal(b"k" * 32, result["tenant_id"], result["id"], json.loads(vault["envelope_json"]))
    )
    assert private["access_token"] == "fake-token"
    assert history["consumed_at"] == NOW + 10
    assert history["verifier_envelope_json"] is None


@pytest.mark.parametrize(
    "cause", ["wrong_tenant", "wrong_browser", "expired", "repeated", "wrong_owner", "demoted"]
)
def test_state_invalid_never_exchanges(oauth_case, cause):
    from webapp.publications.contracts import Conflict, Forbidden

    flow = start(oauth_case)
    principal = owner(oauth_case)
    now = NOW + 10
    if cause == "wrong_tenant":
        principal = owner(oauth_case, index=1)
    if cause == "wrong_browser":
        principal["session_binding"] = "other-browser"
    if cause == "expired":
        now = NOW + 601
    if cause == "wrong_owner":
        principal["user_id"] = oauth_case[1][1][1]
    if cause == "repeated":
        finish(oauth_case, flow["state"])
    if cause == "demoted":
        with db.connect(oauth_case[0]) as con:
            con.execute(
                "UPDATE users SET role='member' WHERE tenant_id=? AND id=?", oauth_case[1][0]
            )
    client = ProviderDouble()
    with pytest.raises((Forbidden, Conflict)):
        finish(oauth_case, flow["state"], client, principal, now)
    assert client.calls == 0


@pytest.mark.parametrize(
    "remote,scopes,expiry,state,reason",
    [
        ("other-id", None, NOW + 7200, "known", "remote_identity_mismatch"),
        ("page-42", ["pages_read_engagement"], NOW + 7200, "known", "insufficient_scopes"),
        ("page-42", None, None, "unknown", "token_expiry_unknown"),
        ("page-42", None, NOW - 1, "known", "token_expired"),
    ],
)
def test_invalid_remote_evidence_holds_not_activates(
    oauth_case, remote, scopes, expiry, state, reason
):
    result = finish(
        oauth_case, start(oauth_case)["state"], ProviderDouble(remote, scopes, expiry, state)
    )
    assert result["status"] == "held"
    assert result["hold_reason"] == reason
    assert result["capabilities"] == {}
    with db.connect(oauth_case[0]) as con:
        assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []


def test_missing_key_or_remote_error_is_safe_and_state_stays_consumed(oauth_case):
    from webapp.publications.contracts import Conflict

    flow = start(oauth_case)
    result = finish(oauth_case, flow["state"], key=None)
    assert result["status"] == "held"
    assert result["hold_reason"] == "vault_key_unavailable"
    with pytest.raises(Conflict):
        finish(oauth_case, flow["state"])

    class ErrorDouble(ProviderDouble):
        def exchange(self, *args):
            raise RuntimeError("provider fake-token payload")

    result = finish(oauth_case, start(oauth_case)["state"], ErrorDouble())
    assert result["hold_reason"] == "provider_verification_failed"
    assert "fake-token" not in json.dumps(result)


def test_concurrent_callbacks_exchange_once(oauth_case):
    from webapp.publications.contracts import Conflict

    state = start(oauth_case)["state"]
    client = ProviderDouble()

    def run(_):
        try:
            return finish(oauth_case, state, client)["status"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(results) == ["active", "conflict"]
    assert client.calls == 1


def test_start_rejects_unconfigured_redirect_and_binding(oauth_case):
    from webapp.publications.contracts import Conflict, InvalidInput
    from webapp.publications.oauth import start_oauth

    url, owners, row, config = oauth_case
    with pytest.raises(InvalidInput):
        start_oauth(
            url,
            *owners[0],
            "facebook",
            "https://attacker.test/callback",
            NOW,
            session_binding=BINDING,
            connection_id=row["id"],
            config=config,
        )
    with pytest.raises(Conflict):
        start_oauth(url, *owners[0], "facebook", config.redirect_uris[0], NOW)
    with pytest.raises(InvalidInput):
        start_oauth(
            url,
            *owners[0],
            "facebook",
            config.redirect_uris[0],
            NOW,
            connection_id=row["id"],
            config=config,
        )


def test_oauth_start_api_binds_actual_browser_and_does_not_fake_config(media_clients):
    a = media_clients.a
    response = a.post(
        "/api/v1/publications/oauth/start",
        json={
            "platform": "facebook",
            "connection_id": 1,
            "redirect_uri": "https://eikon.example.test/callback",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "oauth_not_configured"}


def test_connection_changed_during_flow_prevents_exchange(oauth_case):
    from webapp.publications.connections import put_connection
    from webapp.publications.contracts import Conflict

    flow = start(oauth_case)
    url, owners, row, _ = oauth_case
    put_connection(
        url,
        *owners[0],
        {
            "id": row["id"],
            "expected_version": 2,
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "different-page",
            "project_ids": row["project_ids"],
        },
    )
    client = ProviderDouble()
    with pytest.raises(Conflict):
        finish(oauth_case, flow["state"], client)
    assert client.calls == 0


def test_provider_consent_denied_consumes_state_without_exchange(oauth_case):
    from webapp.publications.oauth import finish_oauth

    flow = start(oauth_case)
    client = ProviderDouble()
    result = finish_oauth(
        oauth_case[0],
        owner(oauth_case),
        flow["state"],
        "",
        NOW + 10,
        client,
        key=b"k" * 32,
        key_id="test",
        provider_error=True,
    )
    assert result["hold_reason"] == "provider_consent_denied"
    assert client.calls == 0
    with db.connect(oauth_case[0]) as con:
        assert (
            con.execute("SELECT consumed_at FROM publication_oauth_states").fetchone()[
                "consumed_at"
            ]
            == NOW + 10
        )


def test_secure_callback_cannot_cross_browser_with_same_owner(media_clients):
    import base64
    import time
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from webapp.publications.oauth import OAuthConfig

    a = media_clients.a
    p = project(a, "callback")
    row = a.post(
        "/api/v1/publications/connections",
        json={
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "page-42",
            "project_ids": [p["id"]],
        },
    ).json()
    app = a.app
    app.state.settings = replace(
        app.state.settings,
        publication_vault_key=base64.b64encode(b"k" * 32).decode(),
        publication_vault_key_id="test",
    )
    config = OAuthConfig(
        "facebook",
        "page",
        "fake-app",
        "fake-secret",
        ("https://testserver/api/v1/publications/oauth/callback",),
        "v25.0",
    )
    app.state.publication_oauth_configs = {("facebook", "page"): config}
    client = ProviderDouble(expires_at=int(time.time()) + 7200)
    app.state.publication_oauth_clients = {("facebook", "page"): client}
    first = TestClient(app, base_url="https://testserver")
    second = TestClient(app, base_url="https://testserver")
    try:
        credentials = {"email": "alpha@example.test", "password": "test-password-123"}
        assert first.post("/auth/login", json=credentials).status_code == 200
        assert second.post("/auth/login", json=credentials).status_code == 200
        response = first.post(
            "/api/v1/publications/oauth/start",
            json={
                "platform": "facebook",
                "connection_id": row["id"],
                "redirect_uri": config.redirect_uris[0],
            },
        )
        assert response.status_code == 200, response.text
        cookie = response.headers.get("set-cookie")
        assert (
            "__Host-eikon_publication_oauth=" in cookie
            and "HttpOnly" in cookie
            and "Secure" in cookie
            and "SameSite=lax" in cookie
            and "Path=/" in cookie
            and "Domain=" not in cookie
        )
        params = {"state": response.json()["state"], "code": "fake-code"}
        assert second.get("/api/v1/publications/oauth/callback", params=params).status_code == 403
        assert client.calls == 0
        # current_user renovó la cookie JWT, pero el binding dedicado conserva validez.
        assert first.get("/auth/me").status_code == 200
        result = first.get("/api/v1/publications/oauth/callback", params=params)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "active"
        assert client.calls == 1
        assert "fake-token" not in result.text and "ciphertext" not in result.text
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "platform,mode",
    [
        ("facebook", "facebook_login"),
        ("instagram", "instagram_login"),
        ("instagram", "facebook_login"),
        ("tiktok", "oauth2"),
        ("x", "oauth2"),
    ],
)
def test_provider_http_contract_with_network_double(platform, mode, caplog):
    """Ejecuta transportes reales; HTTP replies simuladas son evidencia de contrato."""
    import logging
    from urllib.parse import parse_qs

    import httpx

    from webapp.publications.connections import REQUIRED_SCOPES
    from webapp.publications.oauth import OAuthConfig
    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = OAuthConfig(
        platform,
        mode,
        "fake-app",
        "fake-secret",
        ("https://eikon.example.test/callback",),
        "v25.0" if platform in ("facebook", "instagram") else None,
    )
    remote = (
        "ig-42"
        if platform == "instagram"
        else "page-42"
        if platform == "facebook"
        else "open-42"
        if platform == "tiktok"
        else "x-42"
    )
    flow = {
        **config.public(),
        "redirect_uri": config.redirect_uris[0],
        "expected_remote_id": remote,
    }
    calls = []
    scopes = list(REQUIRED_SCOPES[(platform, mode)])

    def network_double(request):
        calls.append(request)
        path = request.url.path
        if (
            path.endswith(("/oauth/access_token", "/oauth/token/"))
            or request.url.host == "api.instagram.com"
        ):
            form = parse_qs(request.content.decode())
            assert form["code"] == ["fake-code"] and form["client_secret"] == ["fake-secret"]
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-token",
                    "expires_in": 7200,
                    "refresh_token": "fake-refresh",
                    "open_id": "open-42",
                    "scope": ",".join(scopes),
                },
            )
        if path == "/access_token":
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 7200})
        if path.endswith("/debug_token"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "app_id": "fake-app",
                        "is_valid": True,
                        "type": "PAGE",
                        "expires_at": NOW + 7200,
                        "data_access_expires_at": 0,
                        "scopes": scopes,
                        "granular_scopes": [],
                    }
                },
            )
        if path.endswith("/content_publishing_limit"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"quota_usage": 0, "config": {"quota_total": 100, "quota_duration": 86400}}
                    ]
                },
            )
        if platform == "tiktok":
            return httpx.Response(
                200,
                json={
                    "data": {"user": {"open_id": "open-42", "display_name": "TikTok Test"}},
                    "error": {"code": "ok", "message": "", "log_id": "test"},
                },
            )
        if platform == "instagram" and mode == "instagram_login":
            return httpx.Response(200, json={"user_id": "ig-42", "username": "TestIG"})
        return httpx.Response(
            200,
            json={
                "id": "page-42",
                "name": "Page Test",
                "instagram_business_account": {"id": "ig-42", "username": "TestIG"},
            },
        )

    client = OfficialOAuthClient(config, httpx.MockTransport(network_double))
    with caplog.at_level(logging.DEBUG):
        if platform == "x":
            from webapp.publications.contracts import Conflict

            with pytest.raises(Conflict, match="blocked_budget"):
                client.exchange(flow, "fake-code", "fake-verifier")
            with pytest.raises(Conflict, match="blocked_budget"):
                client.verify(flow, {"access_token": "fake-token"}, NOW)
            assert calls == []
        else:
            secrets = client.exchange(flow, "fake-code", None)
            account = client.verify(flow, secrets, NOW)
            assert account.remote_id == remote
            assert set(account.scopes) == set(scopes)
            assert account.expiry_state == "known"
            assert account.expires_at == NOW + 7200
            if mode == "instagram_login":
                assert {r.url.host for r in calls} == {"api.instagram.com", "graph.instagram.com"}
            if mode == "facebook_login":
                assert {r.url.host for r in calls} == {"graph.facebook.com"}
    assert "fake-token" not in caplog.text and "fake-secret" not in caplog.text
    client.close()


def test_official_transport_never_follows_authenticated_redirects():
    import httpx

    from webapp.publications.contracts import Conflict
    from webapp.publications.oauth import OAuthConfig
    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = OAuthConfig(
        "tiktok", "oauth2", "fake-app", "fake-secret", ("https://eikon.example.test/callback",)
    )
    visited = []

    def redirect_double(request):
        visited.append(request.url.host)
        return httpx.Response(
            302, headers={"Location": "https://evil.example.test/?access_token=fake-token"}
        )

    client = OfficialOAuthClient(config, httpx.MockTransport(redirect_double))
    with pytest.raises(Conflict, match="provider_verification_failed"):
        client.exchange(
            {**config.public(), "redirect_uri": config.redirect_uris[0]}, "fake-code", None
        )
    assert visited == ["open.tiktokapis.com"]
    client.close()


def test_import_does_not_trust_file_scopes_or_expiry_for_tiktok():
    import httpx

    from webapp.publications.oauth import OAuthConfig
    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = OAuthConfig(
        "tiktok", "oauth2", "fake-app", "fake-secret", ("https://eikon.example.test/callback",)
    )
    client = OfficialOAuthClient(
        config,
        httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "data": {"user": {"open_id": "open-42", "display_name": "Test"}},
                    "error": {"code": "ok"},
                },
            )
        ),
    )
    account = client.verify(
        {"platform": "tiktok", "api_mode": "oauth2", "expected_remote_id": "open-42"},
        {
            "access_token": "fake-token",
            "scope": "user.info.basic,video.publish",
            "expires_in": 7200,
        },
        NOW,
    )
    assert account.scopes == ()
    assert account.expiry_state == "unknown"
    client.close()


def test_x_pkce_verifier_encrypted_and_erased_before_exchange(publication_db):
    import base64
    import hashlib
    from urllib.parse import parse_qs, urlsplit

    from webapp.publications.connections import put_connection
    from webapp.publications.contracts import Conflict
    from webapp.publications.oauth import OAuthConfig, finish_oauth, start_oauth

    url, owners, payloads = publication_db
    row = put_connection(
        url,
        *owners[0],
        {
            "platform": "x",
            "api_mode": "oauth2",
            "remote_id": "x-42",
            "project_ids": payloads[0]["project_ids"],
        },
    )
    config = OAuthConfig(
        "x", "oauth2", "fake-app", "fake-secret", ("https://eikon.example.test/callback",)
    )
    flow = start_oauth(
        url,
        *owners[0],
        "x",
        config.redirect_uris[0],
        NOW,
        session_binding=BINDING,
        connection_id=row["id"],
        config=config,
        key=b"k" * 32,
        key_id="test",
    )
    query = parse_qs(urlsplit(flow["authorization_url"]).query)
    assert query["code_challenge_method"] == ["S256"]

    class BudgetDouble:
        def exchange(self, flow, code, verifier):
            assert (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
                == query["code_challenge"][0]
            )
            with db.connect(url) as con:
                state = con.execute(
                    "SELECT verifier_envelope_json,consumed_at FROM publication_oauth_states"
                ).fetchone()
                assert state["verifier_envelope_json"] is None
                assert state["consumed_at"] == NOW + 10
            raise Conflict("blocked_budget")

    result = finish_oauth(
        url,
        {
            "tenant_id": owners[0][0],
            "user_id": owners[0][1],
            "auth_method": "session",
            "session_binding": BINDING,
        },
        flow["state"],
        "fake-code",
        NOW + 10,
        BudgetDouble(),
        key=b"k" * 32,
        key_id="test",
    )
    assert result["hold_reason"] == "blocked_budget"


def test_unknown_and_explicit_non_expiring_meta_tokens_are_distinct(oauth_case):
    result = finish(
        oauth_case,
        start(oauth_case)["state"],
        ProviderDouble(expires_at=None, expiry_state="non_expiring"),
    )
    assert result["status"] == "active"
    assert result["expiry_state"] == "non_expiring"
    assert result["expires_at"] is None


def test_instagram_login_does_not_invent_facebook_debug_token():
    import httpx

    from webapp.publications.oauth import OAuthConfig
    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = OAuthConfig(
        "instagram",
        "instagram_login",
        "fake-app",
        "fake-secret",
        ("https://eikon.example.test/callback",),
        "v25.0",
    )
    calls = []

    def network_double(request):
        calls.append(request.url.path)
        if request.url.host == "api.instagram.com":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "access_token": "short-fake-token",
                            "user_id": "ig-42",
                            "permissions": [
                                "instagram_business_basic",
                                "instagram_business_content_publish",
                            ],
                        }
                    ]
                },
            )
        if request.url.path == "/access_token":
            return httpx.Response(
                200,
                json={
                    "access_token": "long-fake-token",
                    "token_type": "bearer",
                    "expires_in": 5184000,
                },
            )
        if request.url.path.endswith("/content_publishing_limit"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"quota_usage": 0, "config": {"quota_total": 100, "quota_duration": 86400}}
                    ]
                },
            )
        if request.url.path.endswith("/permissions"):
            pytest.fail("No inventar introspección /permissions para Instagram Login")
        if request.url.path.endswith("/debug_token"):
            pytest.fail("Instagram Login tiene otro contrato, no endpoint debug de Facebook")
        return httpx.Response(200, json={"user_id": "ig-42", "username": "IG Test"})

    client = OfficialOAuthClient(config, httpx.MockTransport(network_double))
    flow = {
        **config.public(),
        "redirect_uri": config.redirect_uris[0],
        "expected_remote_id": "ig-42",
    }
    credential = client.exchange(flow, "fake-code", None)
    account = client.verify(flow, credential, NOW)
    assert account.remote_id == "ig-42" and account.credential["access_token"] == "long-fake-token"
    assert account.expires_at == NOW + 5184000
    assert "/access_token" in calls
    client.close()


@pytest.mark.parametrize(
    "problem",
    ["wrong_app", "invalid", "personal", "granular_other_page", "unknown_expiry", "remote_other"],
)
def test_meta_provider_evidence_failures_do_not_activate(oauth_case, problem):
    import httpx

    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = oauth_case[3]

    def network_double(request):
        if request.url.path.endswith("/oauth/access_token"):
            return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 7200})
        if request.url.path.endswith("/debug_token"):
            debug = {
                "app_id": "fake-app",
                "is_valid": True,
                "type": "PAGE",
                "expires_at": NOW + 7200,
                "scopes": ["pages_manage_posts", "pages_read_engagement", "pages_show_list"],
            }
            if problem == "wrong_app":
                debug["app_id"] = "another-app"
            if problem == "invalid":
                debug["is_valid"] = False
            if problem == "personal":
                debug["type"] = "APP"
            if problem == "granular_other_page":
                debug["granular_scopes"] = [
                    {"scope": "pages_manage_posts", "target_ids": ["other-page"]}
                ]
            if problem == "unknown_expiry":
                debug["expires_at"] = "undecodable"
            return httpx.Response(200, json={"data": debug})
        return httpx.Response(
            200,
            json={
                "id": "other-page" if problem == "remote_other" else "page-42",
                "name": "Test Page",
            },
        )

    client = OfficialOAuthClient(config, httpx.MockTransport(network_double))
    result = finish(oauth_case, start(oauth_case)["state"], client)
    assert result["status"] == "held"
    assert "fake-token" not in json.dumps(result)
    client.close()


def test_meta_oauth_selects_page_identity_and_page_token_not_user_id(oauth_case):
    import httpx

    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = oauth_case[3]

    def network_double(request):
        path = request.url.path
        if path.endswith("/oauth/access_token"):
            return httpx.Response(200, json={"access_token": "fake-user-token", "expires_in": 7200})
        if path.endswith("/debug_token"):
            token = request.url.params["input_token"]
            return httpx.Response(
                200,
                json={
                    "data": {
                        "is_valid": True,
                        "app_id": "fake-app",
                        "type": "USER" if token == "fake-user-token" else "PAGE",
                        "expires_at": 0,
                        "scopes": [
                            "pages_manage_posts",
                            "pages_read_engagement",
                            "pages_show_list",
                        ],
                    }
                },
            )
        if path.endswith("/me/accounts"):
            assert request.headers["Authorization"] == "Bearer fake-user-token"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "page-42",
                            "name": "Test Page",
                            "access_token": "fake-page-token",
                            "tasks": ["CREATE_CONTENT"],
                        },
                        {
                            "id": "wrong-page",
                            "access_token": "fake-other-token",
                            "tasks": ["CREATE_CONTENT"],
                        },
                    ]
                },
            )
        assert request.headers["Authorization"] == "Bearer fake-page-token"
        return httpx.Response(200, json={"id": "page-42", "name": "Test Page"})

    client = OfficialOAuthClient(config, httpx.MockTransport(network_double))
    result = finish(oauth_case, start(oauth_case)["state"], client)
    assert result["status"] == "active" and result["remote_id"] == "page-42"
    from webapp.publications.vault import unseal

    with db.connect(oauth_case[0]) as con:
        envelope = con.execute("SELECT envelope_json FROM publication_connection_vault").fetchone()[
            "envelope_json"
        ]
    assert json.loads(
        unseal(b"k" * 32, result["tenant_id"], result["id"], json.loads(envelope))
    ) == {"access_token": "fake-page-token"}
    client.close()


@pytest.mark.parametrize(
    "identity,quota",
    [
        (
            {"id": "app-scoped-id", "username": "Test"},
            {"data": [{"quota_usage": 0, "config": {"quota_total": 100, "quota_duration": 86400}}]},
        ),
        ({"user_id": "ig-42", "username": "Test"}, {"data": []}),
        (
            {"user_id": "ig-42", "username": "Test"},
            {
                "data": [
                    {"quota_usage": False, "config": {"quota_total": 100, "quota_duration": 86400}}
                ]
            },
        ),
    ],
)
def test_instagram_login_requires_canonical_user_and_real_capability_probe(identity, quota):
    import httpx

    from webapp.publications.contracts import Conflict
    from webapp.publications.oauth import OAuthConfig
    from webapp.publications.oauth_providers import OfficialOAuthClient

    config = OAuthConfig(
        "instagram",
        "instagram_login",
        "fake-app",
        "fake-secret",
        ("https://eikon.example.test/callback",),
        "v25.0",
    )

    def probe_double(request):
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=identity)
        if request.url.path.endswith("/content_publishing_limit"):
            return httpx.Response(200, json=quota)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"permission": "instagram_business_basic", "status": "granted"},
                    {"permission": "instagram_business_content_publish", "status": "granted"},
                ]
            },
        )

    client = OfficialOAuthClient(config, httpx.MockTransport(probe_double))
    with pytest.raises(Conflict, match="provider_verification_failed"):
        client.verify(
            {"platform": "instagram", "api_mode": "instagram_login", "expected_remote_id": "ig-42"},
            {"access_token": "fake-token"},
            NOW,
        )
    client.close()


def test_remote_name_cannot_reflect_private_token_into_metadata(oauth_case):
    from dataclasses import replace

    class EchoDouble(ProviderDouble):
        def verify(self, *args):
            return replace(super().verify(*args), name="Error fake-token echoed")

    result = finish(oauth_case, start(oauth_case)["state"], EchoDouble())
    assert result["status"] == "held" and result["hold_reason"] == "provider_verification_failed"
    assert "fake-token" not in json.dumps(result)


def test_oauth_initializes_legacy_catalog_before_remote_activation(oauth_case, publication_db):
    url, owners, payloads = publication_db
    cid = payloads[0]["connection_ids"][0]
    case = (url, owners, {"id": cid}, oauth_case[3])
    flow = start(case)
    with db.connect(url) as con:
        detail = con.execute(
            "SELECT * FROM publication_connection_details WHERE tenant_id=? AND connection_id=?",
            (owners[0][0], cid),
        ).fetchone()
        assert detail is not None
        assert detail["owner_id"] == owners[0][1]
        assert detail["hold_reason"] == "authorization_pending"
        assert detail["scope_evidence"] == "unverified" and detail["verified_at"] is None
    result = finish(case, flow["state"], ProviderDouble(remote_id="remote-test"))
    assert result["status"] == "active" and result["remote_name"] == "Test Page"
    assert result["verified_at"] == NOW + 10 and result["expiry_state"] == "known"
    assert result["scopes"] == sorted(ProviderDouble().scopes)
    assert result["scope_evidence"] == "remote_introspection" and result["hold_reason"] is None
    with db.connect(url) as con:
        detail = con.execute(
            "SELECT * FROM publication_connection_details WHERE tenant_id=? AND connection_id=?",
            (owners[0][0], cid),
        ).fetchone()
        assert detail["owner_id"] == owners[0][1] and detail["verified_at"] == NOW + 10
        assert json.loads(detail["scopes_json"]) == result["scopes"]


@pytest.mark.parametrize(
    "operation,reflected",
    [
        ("oauth", "fake-user-token"),
        ("oauth", "fake-app-secret"),
        ("oauth", "fake-code"),
        ("import", "fake-user-token"),
        ("import", "fake-app-secret"),
    ],
)
def test_meta_rejects_reflection_of_private_material_before_page_token(
    oauth_case, operation, reflected
):
    import httpx

    from webapp.publications.oauth_providers import OfficialOAuthClient

    def network_double(request):
        path = request.url.path
        if path.endswith("/oauth/access_token"):
            return httpx.Response(200, json={"access_token": "fake-user-token", "expires_in": 7200})
        if path.endswith("/debug_token"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "is_valid": True,
                        "app_id": "fake-app",
                        "expires_at": 0,
                        "type": "USER"
                        if request.url.params["input_token"] == "fake-user-token"
                        else "PAGE",
                        "scopes": sorted(ProviderDouble().scopes),
                    }
                },
            )
        if path.endswith("/me/accounts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "page-42",
                            "access_token": "fake-page-token",
                            "tasks": ["CREATE_CONTENT"],
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"id": "page-42", "name": "Reflected " + reflected})

    client = OfficialOAuthClient(oauth_case[3], httpx.MockTransport(network_double))
    try:
        if operation == "oauth":
            result = finish(oauth_case, start(oauth_case)["state"], client)
        else:
            from webapp.publications.oauth import import_credential

            result = import_credential(
                oauth_case[0],
                *oauth_case[1][0],
                oauth_case[2]["id"],
                {"access_token": "fake-user-token"},
                NOW,
                client,
                key=b"k" * 32,
                key_id="test",
                dry_run=False,
            )
        assert "sensitive_material" not in json.dumps(result)
        assert (
            result["status"] == "held" and result["hold_reason"] == "provider_verification_failed"
        )
        assert reflected not in json.dumps(result)
        with db.connect(oauth_case[0]) as con:
            assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []
            details = con.execute(
                "SELECT remote_name,scopes_json FROM publication_connection_details"
            ).fetchall()
            assert reflected not in json.dumps(details)
    finally:
        client.close()


@pytest.mark.parametrize("reflected", ["fake-short-token", "fake-ig-secret", "fake-code"])
def test_instagram_rejects_reflection_of_private_material_before_long_token(
    publication_db, reflected
):
    import httpx

    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import OAuthConfig, finish_oauth, start_oauth
    from webapp.publications.oauth_providers import OfficialOAuthClient

    url, owners, payloads = publication_db
    row = put_connection(
        url,
        *owners[0],
        {
            **connection_payload(payloads[0]),
            "platform": "instagram",
            "api_mode": "instagram_login",
            "remote_id": "ig-42",
        },
    )
    config = OAuthConfig(
        "instagram",
        "instagram_login",
        "fake-app",
        "fake-ig-secret",
        ("https://eikon.example.test/callback",),
        "v25.0",
    )
    flow = start_oauth(
        url,
        *owners[0],
        "instagram",
        config.redirect_uris[0],
        NOW,
        session_binding=BINDING,
        connection_id=row["id"],
        config=config,
    )

    def network_double(request):
        if request.url.host == "api.instagram.com":
            return httpx.Response(200, json={"data": [{"access_token": "fake-short-token"}]})
        if request.url.path == "/access_token":
            assert request.url.params["access_token"] == "fake-short-token"
            return httpx.Response(200, json={"access_token": "fake-long-token", "expires_in": 7200})
        if request.url.path.endswith("/content_publishing_limit"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "quota_usage": 0,
                            "config": {
                                "quota_total": 100,
                                "quota_duration": 86400,
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"user_id": "ig-42", "username": "Reflected " + reflected})

    client = OfficialOAuthClient(config, httpx.MockTransport(network_double))
    try:
        result = finish_oauth(
            url,
            {
                "tenant_id": owners[0][0],
                "user_id": owners[0][1],
                "session_binding": BINDING,
                "auth_method": "session",
            },
            flow["state"],
            "fake-code",
            NOW + 10,
            client,
            key=b"k" * 32,
            key_id="test",
        )
        assert (
            result["status"] == "held" and result["hold_reason"] == "provider_verification_failed"
        )
        assert reflected not in json.dumps(result)
        with db.connect(url) as con:
            assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []
            assert reflected not in json.dumps(
                con.execute(
                    "SELECT remote_name,scopes_json FROM publication_connection_details"
                ).fetchall()
            )
    finally:
        client.close()
