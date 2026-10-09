"""Clientes aislados y helpers HTTP para el flujo de medios privados."""

from __future__ import annotations

import io
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from webapp.app import create_app
from webapp.config import Settings


@dataclass
class MediaClients:
    a: TestClient
    b: TestClient
    db_path: Path
    output_root: Path


@pytest.fixture
def media_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MediaClients]:
    """Dos cookies independientes; no entra al lifespan que arranca el worker."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    db_path = tmp_path / "eikon.db"
    output_root = tmp_path / "output"
    settings = Settings(
        data_root=tmp_path, sqlite_path=db_path, jwt_secret=secrets.token_urlsafe(48)
    )
    app = create_app(settings, output_root=output_root)
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
            assert response.status_code == 201, response.text
        assert app.state.worker is None
        yield MediaClients(a, b, db_path, output_root)
    finally:
        a.close()
        b.close()


def project(client: TestClient, slug: str) -> dict[str, Any]:
    response = client.post("/api/v1/projects", json={"slug": slug, "name": slug, "description": ""})
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def brand(client: TestClient, project_id: int, slug: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/brands",
        json={
            "project_id": project_id,
            "slug": slug,
            "name": slug,
            "palette": {"bg": "#0b1417", "acento": "#43b5a6"},
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def brief(client: TestClient, brand_id: int, width: int = 512, height: int = 512) -> dict[str, Any]:
    response = client.post(
        "/api/v1/generation-briefs",
        json={
            "brand_id": brand_id,
            "prompt": "Pieza de prueba",
            "width": width,
            "height": height,
            "expires_in_hours": 24,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def image_bytes(width: int = 512, height: int = 512, color: str = "teal") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (width, height), color).save(stream, format="PNG")
    return stream.getvalue()


def upload(client: TestClient, brief_id: int, key: str, data: bytes) -> Any:
    return client.post(
        "/api/v1/media",
        headers={"Idempotency-Key": key},
        data={
            "brief_id": str(brief_id),
            "source": "codex",
            "provenance": '{"tool":"image_gen","model":"declared-by-client"}',
        },
        files={"file": ("image.png", data, "image/png")},
    )
