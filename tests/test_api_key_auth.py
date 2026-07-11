"""Tests de auth por API key y generación síncrona para agentes."""

from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from eikon_core.constants import ROOT
from webapp import db
from webapp.app import create_app
from webapp.config import Settings
from webapp.security import create_jwt
from webapp.storage import connect

AXES_PATH = ROOT / "config" / "axes.json"
PASSWORD = "supersecret1"

try:
    HAS_PLAYWRIGHT = __import__("playwright", fromlist=["async_api"]) is not None
except ImportError:
    HAS_PLAYWRIGHT = False


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_root=tmp_path, sqlite_path=tmp_path / "eikon.db")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    return create_app(
        _settings(tmp_path),
        output_root=tmp_path / "output",
        axes_config_path=AXES_PATH,
    )


def _register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "tenant_slug": "agents",
            "tenant_name": "Agents",
            "email": "owner@agents.test",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text


def _login(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "owner@agents.test", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def _seed_session(app: FastAPI) -> str:
    settings = app.state.settings
    now = int(time.time())
    with connect(settings.db_url) as con:
        con.execute(
            "INSERT INTO tenants(slug, name, created_at) VALUES (?, ?, ?)",
            ("agents", "Agents", now),
        )
        tenant_id = db.get_last_insert_id(settings.db_url, con, "tenants")
        con.execute(
            "INSERT INTO users(tenant_id, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (tenant_id, "owner@agents.test", "unused", "owner", now),
        )
        user_id = db.get_last_insert_id(settings.db_url, con, "users")

    token = create_jwt(
        {"sub": user_id, "tenant_id": tenant_id},
        settings.jwt_secret,
        settings.jwt_ttl_seconds,
    )
    return token


def test_api_key_auth_headers_and_revoke(app: FastAPI) -> None:
    async def run() -> None:
        settings = app.state.settings
        session_token = _seed_session(app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set(settings.cookie_name, session_token)

            created_key = await client.post("/api/v1/auth/api-keys")
            assert created_key.status_code == 201, created_key.text
            api_key_body = created_key.json()
            api_key = api_key_body["key"]
            assert api_key and len(api_key) > 32

            listed = await client.get("/api/v1/auth/api-keys")
            assert listed.status_code == 200, listed.text
            listed_key = listed.json()["keys"][0]
            assert listed_key["id"] == api_key_body["id"]
            assert "key" not in listed_key
            assert "last_used_at" not in listed_key
            assert api_key not in listed.text

            client.cookies.clear()
            me = await client.get("/auth/me", headers={"Authorization": f"Bearer {api_key}"})
            assert me.status_code == 200, me.text
            assert me.json()["user"]["role"] == "api"

            brand_response = await client.post(
                "/api/v1/brands",
                headers={"X-API-Key": api_key},
                json={
                    "slug": "api-key-brand",
                    "name": "API Key Brand",
                    "palette": {"bg": "#0b1417", "primario": "#f5efe3"},
                    "typography": {"titulos": "Inter", "cuerpo": "Inter"},
                },
            )
            assert brand_response.status_code == 201, brand_response.text

            client.cookies.set(settings.cookie_name, session_token)
            revoked = await client.delete(f"/api/v1/auth/api-keys/{api_key_body['id']}")
            assert revoked.status_code == 204, revoked.text

            client.cookies.clear()
            denied = await client.get("/auth/me", headers={"X-API-Key": api_key})
            assert denied.status_code == 401, denied.text

    asyncio.run(run())


@pytest.mark.integration
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
def test_api_key_creates_brand_and_generate_returns_png(app: FastAPI) -> None:
    with TestClient(app) as client:
        _register(client)

        created_key = client.post("/api/v1/auth/api-keys")
        assert created_key.status_code == 201, created_key.text
        api_key_body = created_key.json()
        api_key = api_key_body["key"]
        assert api_key and len(api_key) > 32

        listed = client.get("/api/v1/auth/api-keys")
        assert listed.status_code == 200, listed.text
        assert listed.json()["keys"][0]["id"] == api_key_body["id"]
        assert "key" not in listed.json()["keys"][0]

        client.cookies.clear()
        bearer_headers = {"Authorization": f"Bearer {api_key}"}
        brand_response = client.post(
            "/api/v1/brands",
            headers=bearer_headers,
            json={
                "slug": "agent-visible-logo",
                "name": "Agent Visible Logo",
                "palette": {
                    "bg": "#0b1417",
                    "primario": "#f5efe3",
                    "acento": "#43b5a6",
                    "texto": "#f5efe3",
                },
                "typography": {"titulos": "Inter", "cuerpo": "Inter"},
                "logo_text": "Agent Visible Logo",
                "logo_symbol": "AV",
                "logo_style": "poligono_regular",
                "logo_seed": 12345,
                "texts": {"titulo": "Agent Visible Logo", "subtitulo": "API render"},
            },
        )
        assert brand_response.status_code == 201, brand_response.text
        brand_id = int(brand_response.json()["id"])

        generated = client.post(
            "/api/v1/generate",
            headers={"X-API-Key": api_key},
            json={
                "brand_id": brand_id,
                "asset_type": "business_card",
                "content": {
                    "titulo": "Agent Visible Logo",
                    "subtitulo": "Generated with an API key",
                    "url": "eikon.test",
                },
            },
        )
        assert generated.status_code == 200, generated.text
        assert generated.headers["content-type"].startswith("image/png")
        assert generated.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(generated.content) > 100

        image = Image.open(io.BytesIO(generated.content))
        image.verify()
