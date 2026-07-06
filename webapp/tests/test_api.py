"""Tests de la API JSON v1 vía TestClient: auth, brands, wizard, batches, downloads.

Los tests rápidos no levantan el worker (TestClient sin context manager). El test
E2E de render real usa `with TestClient(app)` para arrancar el WorkerPool en el
lifespan, encola un batch count=2, polea hasta completar, descarga PNG y ZIP, y
verifica aislamiento multi-tenant.
"""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eikon_core.constants import OUTPUT_DIR, ROOT
from webapp.app import create_app
from webapp.config import Settings

AXES_PATH = ROOT / "config" / "axes.json"
PASSWORD = "supersecret1"

try:
    HAS_PLAYWRIGHT = __import__("playwright", fromlist=["async_api"]) is not None
except ImportError:
    HAS_PLAYWRIGHT = False


def _settings(tmp_path: Path) -> Settings:
    """Settings con BD temporal aislada por test."""
    return Settings(data_root=tmp_path, sqlite_path=tmp_path / "eikon.db")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    """App con BD temporal; sin lifespan hasta que un test use `with TestClient`."""
    return create_app(_settings(tmp_path), output_root=OUTPUT_DIR, axes_config_path=AXES_PATH)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Cliente sin worker (tests rápidos)."""
    return TestClient(app)


def _register(client: TestClient, slug: str, email: str) -> None:
    r = client.post(
        "/auth/register",
        json={
            "tenant_slug": slug,
            "tenant_name": slug.title(),
            "email": email,
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, r.text


def _create_brand(client: TestClient, slug: str = "kosmos", name: str = "Kósmos") -> int:
    r = client.post(
        "/api/v1/brands",
        json={
            "slug": slug,
            "name": name,
            "palette": {"bg": "#0b1417", "acento": "#43b5a6", "primario": "#0b1417"},
            "typography": {"titulos": "Inter", "cuerpo": "Inter"},
            "logo_text": name,
            "logo_symbol": "⬡",
        },
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


# ── Health + auth ────────────────────────────────────────────────────────────


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_flow_register_login_me(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    # me funciona con la cookie puesta por register
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["tenant"]["slug"] == "acme"
    # logout limpia y luego login restablece la sesión
    assert client.post("/auth/logout").status_code == 204
    r = client.post("/auth/login", json={"email": "owner@acme.com", "password": PASSWORD})
    assert r.status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_unauthenticated_is_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/api/v1/brands").status_code == 401
    assert client.get("/api/v1/wizard/axes").status_code == 401


def test_login_bad_credentials(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    r = client.post("/auth/login", json={"email": "owner@acme.com", "password": "wrong-pass-xx"})
    assert r.status_code == 401


# ── Brands CRUD ──────────────────────────────────────────────────────────────


def test_brands_crud(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)

    # list
    r = client.get("/api/v1/brands")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["palette"]["acento"] == "#43b5a6"

    # get
    r = client.get(f"/api/v1/brands/{bid}")
    assert r.status_code == 200
    assert r.json()["slug"] == "kosmos"

    # update
    r = client.put(f"/api/v1/brands/{bid}", json={"name": "Kósmos v2", "palette": {"bg": "#fff"}})
    assert r.status_code == 200
    assert r.json()["name"] == "Kósmos v2"
    assert r.json()["palette"]["bg"] == "#fff"

    # delete
    assert client.delete(f"/api/v1/brands/{bid}").status_code == 204
    assert client.get(f"/api/v1/brands/{bid}").status_code == 404


def test_brand_duplicate_slug_conflict(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    _create_brand(client, "kosmos")
    r = client.post("/api/v1/brands", json={"slug": "kosmos", "name": "dup"})
    assert r.status_code == 409


def test_brand_invalid_slug_422(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    r = client.post("/api/v1/brands", json={"slug": "../etc/passwd", "name": "x"})
    assert r.status_code == 422


# ── Tenant isolation (sin render) ────────────────────────────────────────────


def test_brand_tenant_isolation(app: FastAPI) -> None:
    client_a = TestClient(app)
    client_b = TestClient(app)
    _register(client_a, "alpha", "a@alpha.com")
    _register(client_b, "beta", "b@beta.com")

    bid_a = _create_brand(client_a, "kosmos", "Kósmos A")

    # B no ve el brand de A
    assert client_b.get(f"/api/v1/brands/{bid_a}").status_code == 404
    assert len(client_b.get("/api/v1/brands").json()["items"]) == 0
    # B no puede modificar ni borrar el brand de A
    assert client_b.put(f"/api/v1/brands/{bid_a}", json={"name": "hack"}).status_code == 404
    assert client_b.delete(f"/api/v1/brands/{bid_a}").status_code == 404


# ── Wizard ───────────────────────────────────────────────────────────────────


def test_wizard_axes_catalog(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    r = client.get("/api/v1/wizard/axes")
    assert r.status_code == 200
    axes = r.json()["axes"]
    assert isinstance(axes, list) and len(axes) > 0
    by_name = {a["name"]: a for a in axes}
    assert "palette_scheme" in by_name
    palette = by_name["palette_scheme"]
    assert palette["label"]
    assert len(palette["options"]) >= 2
    opt = palette["options"][0]
    assert "name" in opt and "label" in opt


def test_wizard_brands(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    _create_brand(client)
    r = client.get("/api/v1/wizard/brands")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


# ── Batches: validación (sin render) ─────────────────────────────────────────


def test_batch_unknown_brand_404(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    r = client.post("/api/v1/batches", json={"brand_id": 9999, "permuted": ["palette_scheme"]})
    assert r.status_code == 404


def test_batch_invalid_asset_type_422(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    r = client.post(
        "/api/v1/batches",
        json={"brand_id": bid, "asset_types": ["../secret"], "permuted": ["palette_scheme"]},
    )
    assert r.status_code == 422


def test_batch_unknown_axis_422(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    r = client.post(
        "/api/v1/batches",
        json={"brand_id": bid, "permuted": ["no_such_axis"], "count": 1},
    )
    assert r.status_code == 422


def test_batch_count_exceeds_distinct_422(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    # palette_scheme tiene 6 opciones; count=10 > 6 -> plan_combinations falla -> 422
    r = client.post(
        "/api/v1/batches",
        json={
            "brand_id": bid,
            "asset_types": ["isotipo"],
            "permuted": ["palette_scheme"],
            "count": 10,
        },
    )
    assert r.status_code == 422


def test_batch_invalid_fixed_option_422(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    r = client.post(
        "/api/v1/batches",
        json={"brand_id": bid, "fixed": {"palette_scheme": "no_such_option"}, "count": 1},
    )
    assert r.status_code == 422


# ── Downloads: 404 sin render ────────────────────────────────────────────────


def test_variation_file_missing_404(client: TestClient) -> None:
    _register(client, "acme", "owner@acme.com")
    assert client.get("/api/v1/variations/424242/file").status_code == 404
    r = client.post("/api/v1/downloads/zip", json={"ids": [424242]})
    assert r.status_code == 404


# ── E2E: render real → variations → file → zip + aislamiento ─────────────────


@pytest.mark.integration
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
def test_full_flow_render_download_zip(app: FastAPI) -> None:
    with TestClient(app) as client:
        _register(client, "studio", "owner@studio.com")
        assert (
            client.post(
                "/auth/login", json={"email": "owner@studio.com", "password": PASSWORD}
            ).status_code
            == 200
        )

        # Brand con slug de una marca real => el worker carga marcas/pinakotheke-kosmos.json
        bid = _create_brand(client, "pinakotheke-kosmos", "Kósmos")

        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": bid,
                "asset_types": ["isotipo"],
                "permuted": ["palette_scheme"],
                "count": 2,
                "seed_salt": "api-e2e",
            },
        )
        assert r.status_code == 202, r.text
        batch = r.json()
        assert batch["status"] == "pending"
        batch_id = batch["id"]

        # Polling hasta completar
        deadline = time.time() + 90
        body: dict[str, Any] = {}
        while time.time() < deadline:
            rr = client.get(f"/api/v1/batches/{batch_id}")
            body = rr.json()
            if body["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.5)
        assert body.get("status") == "completed", f"batch no completó: {body}"
        # count=2 => se renderizan 2 PNGs. El ranking deduplica renders casi
        # idénticos (los templates aún no realizan variedad visual desde los ejes),
        # por lo que el nº de variaciones persistidas puede colapsar a 1. Lo que
        # importa para el wiring de la API: 2 renderizados + variaciones servibles.
        assert body["counts"].get("rendered") == 2, f"esperaba 2 renderizados: {body['counts']}"

        # Variations rankeadas (>=1 tras dedup), todas descargables
        rv = client.get(f"/api/v1/batches/{batch_id}/variations")
        assert rv.status_code == 200
        variations = rv.json()["items"]
        assert len(variations) >= 1, f"esperaba >=1 variación, obtuve {len(variations)}"
        for v in variations:
            assert v["seed"] is not None
            assert v["score"] is not None and v["score"] > 0
            assert v["axis_params"]
            # Descarga del PNG
            rf = client.get(v["file_url"])
            assert rf.status_code == 200
            assert rf.headers["content-type"] == "image/png"
            assert len(rf.content) > 100

        ids = [v["id"] for v in variations]

        # ZIP de las variaciones
        rz = client.post("/api/v1/downloads/zip", json={"ids": ids})
        assert rz.status_code == 200
        assert rz.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(rz.content))
        assert len(zf.namelist()) == len(ids)
        assert all(name.endswith(".png") for name in zf.namelist())

        # Galería + selección
        rg = client.get(f"/api/v1/gallery?brand_id={bid}")
        assert rg.status_code == 200
        assert len(rg.json()["items"]) == len(variations)
        rs = client.post("/api/v1/gallery/select", json={"variation_id": ids[0], "selected": True})
        assert rs.status_code == 200

        # ── Aislamiento multi-tenant: B no ve nada de A ──
        client_b = TestClient(app)
        _register(client_b, "rival", "spy@rival.com")
        assert client_b.get(f"/api/v1/batches/{batch_id}").status_code == 404
        assert client_b.get(f"/api/v1/batches/{batch_id}/variations").status_code == 404
        assert client_b.get(f"/api/v1/variations/{ids[0]}/file").status_code == 404
        assert client_b.post("/api/v1/downloads/zip", json={"ids": ids}).status_code == 404
        assert (
            client_b.post(
                "/api/v1/gallery/select", json={"variation_id": ids[0], "selected": True}
            ).status_code
            == 404
        )
        # B pide la galería del brand de A -> 404 (brand no pertenece a B)
        assert client_b.get(f"/api/v1/gallery?brand_id={bid}").status_code == 404
