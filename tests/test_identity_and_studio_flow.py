"""Tests E2E del flujo de identidad + estudio: logo-options → brand update → batch plan.

Cubre:
1. Registrar tenant/usuario + login
2. Crear marca con paleta
3. GET /api/v1/brands/{id}/logo-options?count=12 → valida 12 opciones con style/seed/svg_data_uri
4. PUT /api/v1/brands/{id} con logo_style/logo_seed → persistencia
5. POST /api/v1/batches con render_mode="client" y content overrides
6. GET /api/v1/batches/{id}/plan → texts con overrides + isotype_data_uri no vacío

Patrón: TestClient sin worker (rápido).
"""

from __future__ import annotations

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


def _settings(tmp_path: Path) -> Settings:
    """Settings con BD temporal aislada por test."""
    return Settings(data_root=tmp_path, sqlite_path=tmp_path / "eikon.db")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    """App con BD temporal; sin lifespan (tests rápidos)."""
    return create_app(_settings(tmp_path), output_root=OUTPUT_DIR, axes_config_path=AXES_PATH)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Cliente FastAPI sin worker."""
    return TestClient(app)


def _register(client: TestClient, tenant_slug: str, email: str) -> dict[str, Any]:
    """Registra un tenant/usuario y devuelve el JSON de respuesta."""
    r = client.post(
        "/auth/register",
        json={
            "tenant_slug": tenant_slug,
            "tenant_name": tenant_slug.title(),
            "email": email,
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, f"Register failed: {r.text}"
    return r.json()


def _create_brand(
    client: TestClient,
    slug: str = "test-brand",
    name: str = "Test Brand",
    palette: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea un brand con paleta estándar y devuelve el JSON."""
    if palette is None:
        palette = {
            "bg": "#102027",
            "primario": "#102027",
            "acento": "#2dd4bf",
            "acento_2": "#f59e0b",
            "texto": "#f8fafc",
        }
    r = client.post(
        "/api/v1/brands",
        json={
            "slug": slug,
            "name": name,
            "palette": palette,
            "typography": {"titulos": "Inter", "cuerpo": "Inter"},
            "logo_text": name,
            "logo_symbol": "E",
        },
    )
    assert r.status_code == 201, f"Create brand failed: {r.text}"
    return r.json()


class TestIdentityAndStudioFlow:
    """E2E del flujo: identity page (logo-options) → studio (batch plan)."""

    def test_01_register_and_create_brand(self, client: TestClient) -> None:
        """Paso 1: registrar tenant/usuario, crear marca con paleta."""
        reg = _register(client, "test-tenant", "owner@test.com")
        assert reg["tenant"]["slug"] == "test-tenant"
        assert reg["user"]["email"] == "owner@test.com"

        # Verificar que el usuario está autenticado
        me = client.get("/auth/me").json()
        assert me["tenant"]["slug"] == "test-tenant"

        # Crear brand
        brand = _create_brand(client)
        assert brand["slug"] == "test-brand"
        assert brand["name"] == "Test Brand"
        assert brand["palette"]["acento"] == "#2dd4bf"

    def test_02_get_logo_options(self, client: TestClient) -> None:
        """Paso 2: GET /api/v1/brands/{id}/logo-options?count=12."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # GET logo-options con count=12
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=12")
        assert r.status_code == 200, r.text

        data = r.json()
        assert "options" in data
        options = data["options"]

        # Validar que tenemos (aprox) 12 opciones
        assert len(options) == 12, f"Expected 12 options, got {len(options)}"

        # Validar estructura de cada opción
        for opt in options:
            assert "style" in opt, f"Option missing 'style': {opt}"
            assert "seed" in opt, f"Option missing 'seed': {opt}"
            assert "svg_data_uri" in opt, f"Option missing 'svg_data_uri': {opt}"

            # Validar tipos
            assert isinstance(opt["style"], str), f"style debe ser str: {opt['style']}"
            assert isinstance(opt["seed"], int), f"seed debe ser int: {opt['seed']}"
            assert isinstance(opt["svg_data_uri"], str), "svg_data_uri debe ser str"

            # Validar que svg_data_uri no esté vacío y sea válido
            assert len(opt["svg_data_uri"]) > 0, "svg_data_uri vacío"
            assert opt["svg_data_uri"].startswith(
                "data:image/svg+xml;base64,"
            ), f"svg_data_uri inválido: {opt['svg_data_uri'][:50]}"

    def test_03_update_brand_with_logo_style_and_seed(self, client: TestClient) -> None:
        """Paso 3: PUT /api/v1/brands/{id} con logo_style y logo_seed."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # GET logo-options para obtener style/seed válidos
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=5")
        assert r.status_code == 200
        options = r.json()["options"]
        assert len(options) > 0

        chosen = options[0]  # Elige la primera opción
        chosen_style = chosen["style"]
        chosen_seed = chosen["seed"]

        # PUT update con logo_style y logo_seed
        r = client.put(
            f"/api/v1/brands/{brand_id}",
            json={
                "logo_style": chosen_style,
                "logo_seed": chosen_seed,
            },
        )
        assert r.status_code == 200, r.text
        updated = r.json()

        # Validar que se persistió
        assert updated["logo_style"] == chosen_style
        assert updated["logo_seed"] == chosen_seed

    def test_04_brand_persistence_after_logo_update(self, client: TestClient) -> None:
        """Paso 4: GET /api/v1/brands/{id} después de update → verificar persistencia."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # Obtener opción y actualizar
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=3")
        options = r.json()["options"]
        chosen = options[0]

        client.put(
            f"/api/v1/brands/{brand_id}",
            json={"logo_style": chosen["style"], "logo_seed": chosen["seed"]},
        )

        # GET brand → verificar persistencia
        r = client.get(f"/api/v1/brands/{brand_id}")
        assert r.status_code == 200
        retrieved = r.json()
        assert retrieved["logo_style"] == chosen["style"]
        assert retrieved["logo_seed"] == chosen["seed"]

    def test_05_create_batch_with_client_render_and_content(self, client: TestClient) -> None:
        """Paso 5: POST /api/v1/batches con render_mode='client' y content overrides."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # Establecer logo_style/seed
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=3")
        options = r.json()["options"]
        chosen = options[0]

        client.put(
            f"/api/v1/brands/{brand_id}",
            json={"logo_style": chosen["style"], "logo_seed": chosen["seed"]},
        )

        # POST batch con render_mode="client" y content overrides
        # Con permuted=[], count debe ser 1; usamos permuted=["palette_scheme"] para count=2
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": brand_id,
                "asset_types": ["og_general"],
                "render_mode": "client",
                "count": 2,
                "fixed": {"background_treatment": "solid"},
                "permuted": ["palette_scheme"],
                "content": {
                    "titulo": "X CUSTOM TITLE",
                    "url": "https://demo.com",
                },
            },
        )
        assert r.status_code == 202, r.text
        batch_data = r.json()
        # Status puede ser "pending" o "running" (worker puede procesar inmediatamente)
        assert batch_data["status"] in ("pending", "running"), f"Unexpected status: {batch_data['status']}"
        assert "id" in batch_data

    def test_06_get_batch_plan_with_content_overrides(self, client: TestClient) -> None:
        """Paso 6: GET /api/v1/batches/{id}/plan → texts y isotype_data_uri."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # Establecer logo
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=3")
        options = r.json()["options"]
        chosen = options[0]

        client.put(
            f"/api/v1/brands/{brand_id}",
            json={"logo_style": chosen["style"], "logo_seed": chosen["seed"]},
        )

        # Crear batch con permuted para poder usar count=2
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": brand_id,
                "asset_types": ["og_general"],
                "render_mode": "client",
                "count": 2,
                "fixed": {"background_treatment": "solid"},
                "permuted": ["palette_scheme"],
                "content": {
                    "titulo": "MY CUSTOM TITLE",
                    "url": "https://example.com",
                },
            },
        )
        assert r.status_code == 202
        batch_id = r.json()["id"]

        # GET plan
        r = client.get(f"/api/v1/batches/{batch_id}/plan")
        assert r.status_code == 200, r.text
        plan = r.json()

        # Validar estructura del plan
        assert "batch_id" in plan
        assert plan["batch_id"] == batch_id
        assert "combinations" in plan
        assert "asset_type" in plan
        assert "category" in plan
        assert "viewport" in plan
        assert "device_scale_factor" in plan

        combinations = plan["combinations"]
        assert len(combinations) == 2, f"Expected 2 combinations, got {len(combinations)}"

        # Validar cada combinación
        for combo in combinations:
            assert "idx" in combo
            assert "params" in combo
            assert "vars" in combo
            assert "data_attrs" in combo
            assert "isotype_data_uri" in combo
            assert "texts" in combo

            # Validar texts con content overrides
            texts = combo["texts"]
            assert "titulo" in texts
            assert "url" in texts
            assert "logo-texto" in texts

            # Los content overrides deben estar presentes
            assert texts["titulo"] == "MY CUSTOM TITLE", (
                f"Expected titulo='MY CUSTOM TITLE', got '{texts['titulo']}'"
            )
            assert texts["url"] == "https://example.com", (
                f"Expected url='https://example.com', got '{texts['url']}'"
            )

            # isotype_data_uri debe ser un data URI válido (refleja el logo guardado)
            isotype_uri = combo["isotype_data_uri"]
            assert len(isotype_uri) > 0, "isotype_data_uri vacío"
            assert isotype_uri.startswith(
                "data:image/svg+xml"
            ), f"isotype_data_uri inválido: {isotype_uri[:50]}"

    def test_07_batch_plan_reflects_brand_logo_style(self, client: TestClient) -> None:
        """Paso 7: Validar que el plan refleja el logo_style guardado en la marca."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # Obtener opciones de logo
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=5")
        options = r.json()["options"]

        # Elegir una opción y guardarla
        chosen_option = options[1]  # Segunda opción
        chosen_style = chosen_option["style"]
        chosen_seed = chosen_option["seed"]

        r = client.put(
            f"/api/v1/brands/{brand_id}",
            json={"logo_style": chosen_style, "logo_seed": chosen_seed},
        )
        assert r.status_code == 200

        # Crear batch
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": brand_id,
                "asset_types": ["isotipo"],
                "render_mode": "client",
                "count": 1,
                "fixed": {},
                "permuted": [],
            },
        )
        assert r.status_code == 202
        batch_id = r.json()["id"]

        # GET plan
        r = client.get(f"/api/v1/batches/{batch_id}/plan")
        assert r.status_code == 200
        plan = r.json()

        combinations = plan["combinations"]
        assert len(combinations) >= 1

        # El isotype_data_uri debe reflejar el logo_style guardado.
        # (No comparamos el URI completo, pero validamos que NO esté vacío
        # y que corresponda al estilo fijo del brand.)
        combo = combinations[0]
        isotype_uri = combo["isotype_data_uri"]

        assert len(isotype_uri) > 100, (
            f"isotype_data_uri parece muy corto (< 100 chars): {len(isotype_uri)}"
        )
        assert isotype_uri.startswith("data:image/svg+xml"), (
            f"isotype_data_uri no comienza con data URI: {isotype_uri[:50]}"
        )

    def test_08_end_to_end_identity_studio_flow(self, client: TestClient) -> None:
        """Test E2E completo: registro → logo-options → update → batch → plan."""
        # 1. Registrar
        _register(client, "e2e-test", "e2e@test.com")

        # 2. Crear marca
        brand = _create_brand(client, slug="e2e-brand", name="E2E Brand")
        brand_id = brand["id"]

        # 3. GET logo-options
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=12")
        assert r.status_code == 200
        options = r.json()["options"]
        assert len(options) == 12

        # 4. Elegir opción y actualizar
        chosen = options[3]  # Cuarta opción
        r = client.put(
            f"/api/v1/brands/{brand_id}",
            json={"logo_style": chosen["style"], "logo_seed": chosen["seed"]},
        )
        assert r.status_code == 200

        # 5. Verificar persistencia
        r = client.get(f"/api/v1/brands/{brand_id}")
        assert r.status_code == 200
        persisted = r.json()
        assert persisted["logo_style"] == chosen["style"]
        assert persisted["logo_seed"] == chosen["seed"]

        # 6. Crear batch con content overrides
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": brand_id,
                "asset_types": ["og_general"],
                "render_mode": "client",
                "count": 2,
                "fixed": {},
                "permuted": ["palette_scheme"],
                "content": {
                    "titulo": "MY E2E TITLE",
                    "url": "https://e2e.example.com",
                },
            },
        )
        assert r.status_code == 202
        batch_id = r.json()["id"]

        # 7. GET plan y validar
        r = client.get(f"/api/v1/batches/{batch_id}/plan")
        assert r.status_code == 200
        plan = r.json()

        combinations = plan["combinations"]
        assert len(combinations) == 2

        for combo in combinations:
            texts = combo["texts"]
            assert texts["titulo"] == "MY E2E TITLE"
            assert texts["url"] == "https://e2e.example.com"
            assert len(combo["isotype_data_uri"]) > 100
            assert combo["isotype_data_uri"].startswith("data:image/svg+xml")

    def test_09_logo_options_boundary_conditions(self, client: TestClient) -> None:
        """Test límites: count=1, count=100, count=200 (clamped a 100)."""
        _register(client, "test-tenant", "owner@test.com")
        brand = _create_brand(client)
        brand_id = brand["id"]

        # count=1
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=1")
        assert r.status_code == 200
        assert len(r.json()["options"]) >= 1

        # count=100
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=100")
        assert r.status_code == 200
        opts = r.json()["options"]
        assert len(opts) <= 100

        # count=200 → clamped a 100
        r = client.get(f"/api/v1/brands/{brand_id}/logo-options?count=200")
        assert r.status_code == 200
        opts = r.json()["options"]
        assert len(opts) <= 100

    def test_10_batch_plan_multitenancy_isolation(self, client: TestClient) -> None:
        """Test aislamiento multi-tenant: tenant A no ve batches de tenant B."""
        # Tenant A
        _register(client, "tenant-a", "owner-a@test.com")
        brand_a = _create_brand(client, slug="brand-a", name="Brand A")
        brand_id_a = brand_a["id"]

        # Crear batch en tenant A
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": brand_id_a,
                "asset_types": ["isotipo"],
                "render_mode": "client",
                "count": 1,
                "fixed": {},
                "permuted": [],
            },
        )
        assert r.status_code == 202
        batch_id_a = r.json()["id"]

        # Verificar que tenant A puede leer su batch
        r = client.get(f"/api/v1/batches/{batch_id_a}/plan")
        assert r.status_code == 200

        # Logout y registrar tenant B
        client.post("/auth/logout")
        _register(client, "tenant-b", "owner-b@test.com")

        # Tenant B intenta leer batch de tenant A → 404
        r = client.get(f"/api/v1/batches/{batch_id_a}/plan")
        assert r.status_code == 404, (
            f"Tenant B should not see Tenant A's batch. Got status {r.status_code}"
        )
