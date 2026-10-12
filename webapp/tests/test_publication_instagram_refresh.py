"""Refresh oficial: sólo la red se sustituye; verify/import/vault son reales."""

import json
import logging
from dataclasses import replace

import httpx
import pytest

from webapp import db
from webapp.publications.connections import put_connection
from webapp.publications.contracts import Conflict, Forbidden
from webapp.publications.oauth import OAuthConfig, import_credential
from webapp.publications.oauth_providers import OfficialOAuthClient
from webapp.publications.vault import unseal

NOW = 1791680000
OLD_TOKEN = "synthetic-instagram-old-token"
NEW_TOKEN = "synthetic-instagram-refreshed-token"
APP_SECRET = "synthetic-instagram-app-secret"
FLOW = {"platform": "instagram", "api_mode": "instagram_login", "expected_remote_id": "ig-42"}
OFFICIAL_RESPONSE = {"access_token": NEW_TOKEN, "token_type": "bearer", "expires_in": 5183944}


def config(platform="instagram", mode="instagram_login"):
    return OAuthConfig(
        platform,
        mode,
        "synthetic-app",
        APP_SECRET,
        ("https://eikon.example.test/callback",),
        "v25.0",
    )


class InstagramNetwork:
    """Respuestas completas de prueba y registro privado de peticiones ficticias."""

    def __init__(self, response=None, status=200, failure=None, hook=None):
        self.response = OFFICIAL_RESPONSE if response is None else response
        self.status = status
        self.failure = failure
        self.hook = hook
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        assert request.url.host == "graph.instagram.com"
        if request.url.path == "/refresh_access_token":
            assert request.method == "GET"
            assert dict(request.url.params) == {
                "grant_type": "ig_refresh_token",
                "access_token": OLD_TOKEN,
            }
            assert "authorization" not in request.headers
            assert request.content == b""
            if self.hook:
                self.hook()
            if self.failure == "timeout":
                raise httpx.ReadTimeout("synthetic timeout", request=request)
            return httpx.Response(self.status, json=self.response)
        if request.url.path == "/v25.0/me":
            token = request.headers["authorization"]
            assert token in ("Bearer " + OLD_TOKEN, "Bearer " + NEW_TOKEN)
            remote = "other-account" if self.failure == token else "ig-42"
            return httpx.Response(200, json={"user_id": remote, "username": "Test Instagram"})
        assert request.url.path == "/v25.0/ig-42/content_publishing_limit"
        usage = 100 if self.failure == "probe" else 0
        return httpx.Response(
            200,
            json={
                "data": [
                    {"quota_usage": usage, "config": {"quota_total": 100, "quota_duration": 86400}}
                ]
            },
        )


class RefreshDuringImport:
    """Utility local: conserva el now y la captura owner/version de import real."""

    def __init__(self, official):
        self.official = official

    def exchange(self, flow, code, verifier):
        raise AssertionError("import must not exchange")

    def verify(self, flow, credential, now):
        self.official.verify(flow, credential, now)
        refreshed = self.official.refresh_instagram_token(credential)
        return self.official.verify(flow, refreshed, now)


@pytest.fixture
def connection(tmp_path):
    url = str(tmp_path / "instagram-refresh.sqlite")
    db.init_db(url)
    with db.connect(url) as con:
        con.execute("INSERT INTO tenants(id,slug,name,created_at) VALUES (1,'test','Test',0)")
        con.execute(
            "INSERT INTO users(id,tenant_id,email,password_hash,role,created_at) VALUES (1,1,'test@example.test','unused','owner',0)"
        )
        con.execute(
            "INSERT INTO projects(id,tenant_id,slug,name,created_at) VALUES (1,1,'test','Test',0)"
        )
    row = put_connection(
        url,
        1,
        1,
        {
            "platform": "instagram",
            "api_mode": "instagram_login",
            "remote_id": "ig-42",
            "project_ids": [1],
        },
    )
    return url, row


def apply_import(connection, client, credential=None, dry_run=False):
    url, row = connection
    return import_credential(
        url,
        1,
        1,
        row["id"],
        credential or {"access_token": OLD_TOKEN},
        NOW,
        client,
        key=b"k" * 32,
        key_id="test",
        dry_run=dry_run,
    )


def assert_no_vault(connection):
    with db.connect(connection[0]) as con:
        assert con.execute("SELECT * FROM publication_connection_vault").fetchall() == []


@pytest.mark.parametrize("token_type", ["bearer", "BeArEr"])
def test_official_refresh_imports_known_expiry_and_ciphertext(connection, token_type, caplog):
    caplog.set_level(logging.DEBUG)
    network = InstagramNetwork({**OFFICIAL_RESPONSE, "token_type": token_type})
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        result = apply_import(connection, RefreshDuringImport(client))
        assert result["status"] == "active"
        assert result["remote_id"] == "ig-42"
        assert result["expiry_state"] == "known"
        assert result["expires_at"] == 1796863944
        assert result["verified_at"] == NOW
        assert result["scope_evidence"] == "capability_probe"
        assert result["scopes"] == [
            "instagram_business_basic",
            "instagram_business_content_publish",
        ]
        assert result["version"] == connection[1]["version"] + 1
        assert [r.url.path for r in network.requests] == [
            "/v25.0/me",
            "/v25.0/ig-42/content_publishing_limit",
            "/refresh_access_token",
            "/v25.0/me",
            "/v25.0/ig-42/content_publishing_limit",
        ]
        with db.connect(connection[0]) as con:
            envelope = con.execute(
                "SELECT envelope_json FROM publication_connection_vault"
            ).fetchone()
        stored = json.loads(
            unseal(b"k" * 32, 1, result["id"], json.loads(envelope["envelope_json"]))
        )
        assert stored == {"access_token": NEW_TOKEN}
        for secret in (OLD_TOKEN, NEW_TOKEN, APP_SECRET, "access_token=", "ig_refresh_token"):
            assert secret not in caplog.text
            assert secret not in json.dumps(result)
    finally:
        client.close()


@pytest.mark.parametrize("source", ["copy", "external", "other_client"])
def test_external_or_copied_response_has_no_expiry_authority(connection, source):
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    other = OfficialOAuthClient(config(), httpx.MockTransport(InstagramNetwork()))
    try:
        exact = client.refresh_instagram_token({"access_token": OLD_TOKEN})
        credential = dict(exact) if source == "copy" else dict(OFFICIAL_RESPONSE)
        verifier = client
        if source == "other_client":
            credential, verifier = exact, other
        account = verifier.verify(FLOW, credential, NOW)
        assert account.expiry_state == "unknown"
        assert account.expires_at is None
        result = apply_import(connection, verifier, credential)
        assert result["status"] == "held"
        assert result["hold_reason"] == "token_expiry_unknown"
        assert_no_vault(connection)
    finally:
        client.close()
        other.close()


@pytest.mark.parametrize(
    "platform,mode",
    [
        ("instagram", "facebook_login"),
        ("facebook", "page"),
        ("tiktok", "oauth2"),
        ("x", "oauth2"),
    ],
)
def test_refresh_rejects_other_modes_before_network(platform, mode):
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(platform, mode), httpx.MockTransport(network))
    try:
        with pytest.raises(Conflict, match="oauth_not_configured"):
            client.refresh_instagram_token({"access_token": OLD_TOKEN})
        assert network.requests == []
    finally:
        client.close()


@pytest.mark.parametrize("token", [None, "", "   ", 123, False, []])
def test_refresh_rejects_invalid_input_without_network_and_invalidates_previous(token):
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        previous = client.refresh_instagram_token({"access_token": OLD_TOKEN})
        before = len(network.requests)
        with pytest.raises(Conflict, match="provider_verification_failed"):
            client.refresh_instagram_token({"access_token": token})
        assert len(network.requests) == before
        account = client.verify(FLOW, previous, NOW)
        assert account.expiry_state == "unknown"
        assert account.expires_at is None
    finally:
        client.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("expires_in", None),
        ("expires_in", True),
        ("expires_in", 1.5),
        ("expires_in", "5183944"),
        ("expires_in", 0),
        ("expires_in", -1),
        ("access_token", None),
        ("access_token", ""),
        ("access_token", "  "),
        ("access_token", 1),
        ("token_type", None),
        ("token_type", "basic"),
        ("token_type", 1),
    ],
)
def test_malformed_response_invalidates_previous_provenance(field, value, caplog):
    caplog.set_level(logging.DEBUG)
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        previous = client.refresh_instagram_token({"access_token": OLD_TOKEN})
        network.response = {**OFFICIAL_RESPONSE, field: value}
        if value is None:
            network.response.pop(field)
        with pytest.raises(Conflict, match="provider_verification_failed"):
            client.refresh_instagram_token({"access_token": OLD_TOKEN})
        account = client.verify(FLOW, previous, NOW)
        assert account.expiry_state == "unknown" and account.expires_at is None
        for secret in (OLD_TOKEN, NEW_TOKEN, APP_SECRET, "access_token="):
            assert secret not in caplog.text
    finally:
        client.close()


@pytest.mark.parametrize(
    "failure",
    ["Bearer " + OLD_TOKEN, "Bearer " + NEW_TOKEN, "probe", "timeout", "http_error", "redirect"],
)
def test_identity_probe_or_transport_failure_cannot_authorize(connection, failure, caplog):
    caplog.set_level(logging.DEBUG)
    status = 400 if failure == "http_error" else 302 if failure == "redirect" else 200
    network = InstagramNetwork(status=status, failure=failure)
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        result = apply_import(connection, RefreshDuringImport(client))
        assert result["status"] == "held"
        assert result["hold_reason"] == "provider_verification_failed"
        assert result["expires_at"] is None
        assert_no_vault(connection)
        refreshes = [r for r in network.requests if r.url.path == "/refresh_access_token"]
        assert len(refreshes) == (0 if failure in ("Bearer " + OLD_TOKEN, "probe") else 1)
        for secret in (OLD_TOKEN, NEW_TOKEN, APP_SECRET, "access_token="):
            assert secret not in caplog.text
            assert secret not in json.dumps(result)
    finally:
        client.close()


@pytest.mark.parametrize("change", ["owner", "version"])
def test_import_captures_owner_and_version_before_refresh_network(connection, change):
    def concurrent_update():
        with db.connect(connection[0]) as con:
            if change == "owner":
                con.execute("UPDATE users SET role='member' WHERE tenant_id=1 AND id=1")
            else:
                con.execute(
                    "UPDATE publication_connections SET version=version+1 WHERE tenant_id=1 AND id=?",
                    (connection[1]["id"],),
                )

    network = InstagramNetwork(hook=concurrent_update)
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        error = Forbidden if change == "owner" else Conflict
        with pytest.raises(error):
            apply_import(connection, RefreshDuringImport(client))
        assert_no_vault(connection)
        with db.connect(connection[0]) as con:
            row = con.execute(
                "SELECT status,expires_at FROM publication_connections WHERE id=?",
                (connection[1]["id"],),
            ).fetchone()
        assert row == {"status": "held", "expires_at": None}
    finally:
        client.close()


def test_normal_dry_run_does_not_refresh_or_write(connection):
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        result = apply_import(connection, client, dry_run=True)
        assert result == {
            "dry_run": True,
            "connection_id": connection[1]["id"],
            "eligible": False,
            "hold_reason": "token_expiry_unknown",
        }
        assert [r.url.path for r in network.requests] == [
            "/v25.0/me",
            "/v25.0/ig-42/content_publishing_limit",
        ]
        assert_no_vault(connection)
    finally:
        client.close()


@pytest.mark.parametrize("failure", ["mode", "timeout", "http_error", "redirect", "success"])
def test_next_refresh_attempt_revokes_previous_result_authority(failure):
    network = InstagramNetwork()
    client = OfficialOAuthClient(config(), httpx.MockTransport(network))
    try:
        previous = client.refresh_instagram_token({"access_token": OLD_TOKEN})
        if failure == "mode":
            client.config = replace(config(), api_mode="facebook_login")
        elif failure == "timeout":
            network.failure = "timeout"
        elif failure == "http_error":
            network.status = 400
        elif failure == "redirect":
            network.status = 302
        if failure == "success":
            current = client.refresh_instagram_token({"access_token": OLD_TOKEN})
            assert client.verify(FLOW, current, NOW).expires_at == 1796863944
        else:
            with pytest.raises(Conflict):
                client.refresh_instagram_token({"access_token": OLD_TOKEN})
        client.config = config()
        account = client.verify(FLOW, previous, NOW)
        assert account.expiry_state == "unknown"
        assert account.expires_at is None
        refreshes = [r for r in network.requests if r.url.path == "/refresh_access_token"]
        assert len(refreshes) == (1 if failure == "mode" else 2)
    finally:
        client.close()


def test_flow_mismatch_rejected_before_refresh_during_import(connection):
    network = InstagramNetwork()
    client = OfficialOAuthClient(
        replace(config(), api_mode="facebook_login"), httpx.MockTransport(network)
    )
    try:
        result = apply_import(connection, RefreshDuringImport(client))
        assert result["hold_reason"] == "oauth_not_configured"
        assert result["status"] == "held"
        assert network.requests == []
        assert_no_vault(connection)
    finally:
        client.close()
