from __future__ import annotations

import time
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient

from eikon_core.constants import ROOT
from webapp.app import create_app
from webapp.config import Settings
from webapp.security import create_jwt, decode_jwt
from webapp.storage import create_tenant_user

AXES_PATH: Final = ROOT / "config" / "axes.json"
JWT_TTL_30_DAYS: Final = 2_592_000
JWT_SECRET: Final = "test-jwt-session-secret-" + "x" * 40


def test_settings_default_jwt_ttl_is_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EIKON_WEBAPP_JWT_TTL", raising=False)

    settings = Settings()

    assert settings.jwt_ttl_seconds == JWT_TTL_30_DAYS


def test_authenticated_request_refreshes_jwt_cookie(tmp_path: Path) -> None:
    settings = Settings(
        data_root=tmp_path,
        sqlite_path=tmp_path / "eikon.db",
        jwt_secret=JWT_SECRET,
        jwt_ttl_seconds=JWT_TTL_30_DAYS,
    )
    app = create_app(settings, output_root=tmp_path / "output", axes_config_path=AXES_PATH)
    user = create_tenant_user(
        settings.db_url,
        "acme",
        "Acme",
        "owner@acme.test",
        "supersecret1",
    )

    original_now = int(time.time()) - 300
    original_exp = original_now + settings.jwt_ttl_seconds
    original_token = create_jwt(
        {
            "sub": user["user_id"],
            "tenant_id": user["tenant_id"],
            "iat": original_now,
            "exp": original_exp,
        },
        settings.jwt_secret,
        settings.jwt_ttl_seconds,
    )
    assert int(decode_jwt(original_token, settings.jwt_secret)["exp"]) == original_exp

    client = TestClient(app)
    client.cookies.set(settings.cookie_name, original_token)

    request_started = int(time.time())
    response = client.get("/auth/me")
    request_finished = int(time.time())

    assert response.status_code == 200, response.text
    raw_set_cookie = response.headers.get("set-cookie")
    assert raw_set_cookie is not None
    assert "HttpOnly" in raw_set_cookie
    assert "SameSite=lax" in raw_set_cookie

    cookie = SimpleCookie()
    cookie.load(raw_set_cookie)
    assert settings.cookie_name in cookie
    refreshed = cookie[settings.cookie_name]
    refreshed_payload = decode_jwt(refreshed.value, settings.jwt_secret)
    refreshed_exp = int(refreshed_payload["exp"])
    refreshed_max_age = int(refreshed["max-age"])

    assert refreshed_payload["sub"] == user["user_id"]
    assert refreshed_payload["tenant_id"] == user["tenant_id"]
    assert request_started + settings.jwt_ttl_seconds <= refreshed_exp
    assert refreshed_exp <= request_finished + settings.jwt_ttl_seconds
    assert refreshed_exp > original_exp
    assert refreshed_max_age == settings.jwt_ttl_seconds
    assert refreshed_max_age > original_exp - request_started
