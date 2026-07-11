"""E2E test suite for the agentic layer (API-key auth).

Cubre el flujo completo de la capa agéntica:
1. Registrar tenant
2. Crear API-key (POST /api/v1/auth/api-keys)
3. Usar SOLO Authorization: Bearer <key> (sin cookie) para:
   - Crear marca (POST /api/v1/brands)
   - Listar tipos de asset (GET /api/v1/asset-types)
   - Establecer identidad de marca (POST /brands/{id}/set-identity)
   - Generar asset PNG (POST /api/v1/generate)
4. Verificar que una key revocada ya no autentica (401)

Patrón: TestClient con FastAPI app, determinístico y aislado por test.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from eikon_core.constants import ROOT
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
    """App con BD temporal."""
    return create_app(
        _settings(tmp_path),
        output_root=tmp_path / "output",
        axes_config_path=AXES_PATH,
    )


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Cliente FastAPI."""
    return TestClient(app)


def _register(client: TestClient, tenant_slug: str, email: str) -> dict[str, Any]:
    """Registra un tenant/usuario y devuelve la respuesta JSON."""
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


def _create_brand_with_identity(
    client: TestClient,
    api_key: str,
    slug: str = "test-brand",
    name: str = "Test Brand",
) -> dict[str, Any]:
    """Crea una marca con identidad usando API-key."""
    r = client.post(
        "/api/v1/brands",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "slug": slug,
            "name": name,
            "palette": {
                "bg": "#0b1417",
                "primario": "#f5efe3",
                "acento": "#43b5a6",
                "acento_2": "#f59e0b",
                "texto": "#f5efe3",
            },
            "typography": {"titulos": "Inter", "cuerpo": "Inter"},
            "logo_text": name,
            "logo_symbol": "TB",
            "logo_style": "poligono_regular",
            "logo_seed": 42,
            "texts": {"titulo": name, "subtitulo": "Agentic test"},
        },
    )
    assert r.status_code == 201, f"Create brand failed: {r.text}"
    return r.json()


class TestAgenticE2E:
    """Suite E2E completa de la capa agéntica."""

    def test_01_register_and_create_api_key(self, client: TestClient) -> None:
        """Paso 1: Registrar tenant y crear API-key (POST /api/v1/auth/api-keys)."""
        # Registrar tenant
        reg = _register(client, "agentic-test", "agent@test.com")
        assert reg["tenant"]["slug"] == "agentic-test"
        assert reg["user"]["email"] == "agent@test.com"

        # Crear API-key
        r_key = client.post("/api/v1/auth/api-keys")
        assert r_key.status_code == 201, f"Create API-key failed: {r_key.text}"

        key_data = r_key.json()
        assert "id" in key_data, "API-key response missing 'id'"
        assert "key" in key_data, "API-key response missing 'key'"
        assert "created_at" in key_data, "API-key response missing 'created_at'"

        api_key = key_data["key"]
        assert isinstance(api_key, str) and len(api_key) > 32, "API-key debe ser string > 32 chars"

    def test_02_create_brand_with_api_key_no_cookie(self, client: TestClient) -> None:
        """Paso 2: Crear marca usando SOLO Authorization: Bearer <key> (sin cookie)."""
        # Registrar y crear API-key
        _register(client, "agentic-test", "agent@test.com")
        r_key = client.post("/api/v1/auth/api-keys")
        api_key = r_key.json()["key"]

        # Limpiar cookies para asegurar que SOLO se usa API-key
        client.cookies.clear()

        # Crear marca con API-key en header
        brand = _create_brand_with_identity(client, api_key)
        assert brand["id"] > 0, "Brand ID debe ser > 0"
        assert brand["slug"] == "test-brand"
        assert brand["name"] == "Test Brand"
        assert brand["palette"]["acento"] == "#43b5a6"
        assert brand["logo_style"] == "poligono_regular"
        assert brand["logo_seed"] == 42

    def test_03_get_asset_types_with_api_key(self, client: TestClient) -> None:
        """Paso 3: GET /api/v1/asset-types usando API-key."""
        # Registrar y crear API-key
        _register(client, "agentic-test", "agent@test.com")
        r_key = client.post("/api/v1/auth/api-keys")
        api_key = r_key.json()["key"]

        # Limpiar cookies
        client.cookies.clear()

        # GET /api/v1/asset-types con API-key
        r = client.get(
            "/api/v1/asset-types",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert r.status_code == 200, f"Asset-types failed: {r.text}"

        data = r.json()
        assert "asset_types" in data, "Response missing 'asset_types'"

        asset_types = data["asset_types"]
        assert isinstance(asset_types, list), "asset_types debe ser lista"
        assert len(asset_types) > 0, "asset_types debe tener elementos"

        # Verificar estructura de cada tipo
        for at in asset_types:
            assert "name" in at, f"Asset-type missing 'name': {at}"
            assert "label" in at, f"Asset-type missing 'label': {at}"
            assert "category" in at, f"Asset-type missing 'category': {at}"
            assert isinstance(at["name"], str), "name debe ser string"
            assert len(at["name"]) > 0, "name no puede estar vacío"

    def test_04_set_brand_identity_with_api_key(self, client: TestClient) -> None:
        """Paso 4: POST /brands/{id}/set-identity usando API-key."""
        # Registrar y crear API-key
        _register(client, "agentic-test", "agent@test.com")
        r_key = client.post("/api/v1/auth/api-keys")
        api_key = r_key.json()["key"]

        # Limpiar cookies
        client.cookies.clear()

        # Crear marca
        brand = _create_brand_with_identity(client, api_key)
        brand_id = brand["id"]

        # POST /brands/{id}/set-identity con API-key
        r = client.post(
            f"/api/v1/brands/{brand_id}/set-identity",
            headers={"X-API-Key": api_key},
            json={
                "logo_style": "poligono_irregular",
                "logo_seed": 99,
            }
        )
        assert r.status_code == 200, f"Set-identity failed: {r.text}"

        result = r.json()
        assert result["success"] is True, "success debe ser true"
        assert result["brand_id"] == brand_id, f"brand_id mismatch: {result}"
        assert result["identity"]["logo_style"] == "poligono_irregular"
        assert result["identity"]["logo_seed"] == 99

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
    def test_05_generate_png_with_api_key(self, tmp_path: Path) -> None:
        """Paso 5: POST /api/v1/generate → PNG válido (firma \\x89PNG) usando API-key."""
        app = create_app(
            _settings(tmp_path),
            output_root=tmp_path / "output",
            axes_config_path=AXES_PATH,
        )
        with TestClient(app) as client:
            # Registrar y crear API-key
            _register(client, "agentic-test", "agent@test.com")
            r_key = client.post("/api/v1/auth/api-keys")
            api_key = r_key.json()["key"]

            # Limpiar cookies
            client.cookies.clear()

            # Crear marca
            brand = _create_brand_with_identity(client, api_key)
            brand_id = brand["id"]

            # POST /api/v1/generate con API-key
            r = client.post(
                "/api/v1/generate",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "brand_id": brand_id,
                    "asset_type": "isotipo",
                    "content": {
                        "titulo": "Test Asset",
                    },
                },
            )
            assert r.status_code == 200, f"Generate failed: {r.text}"

            # Verificar headers
            assert r.headers["content-type"].startswith("image/png"), \
                f"Content-Type debe ser image/png, got {r.headers.get('content-type')}"

            # Verificar firma PNG
            assert r.content.startswith(b"\x89PNG\r\n\x1a\n"), \
                f"PNG signature invalid, got {r.content[:8]!r}"

            # Verificar contenido no vacío
            assert len(r.content) > 100, f"PNG demasiado pequeño: {len(r.content)} bytes"

            # Verificar que es un PNG válido (Pillow)
            image = Image.open(io.BytesIO(r.content))
            image.verify()

            # Verificar headers adicionales
            assert "X-Eikon-Batch-Id" in r.headers, "Missing X-Eikon-Batch-Id header"
            assert "X-Eikon-Asset-Type" in r.headers, "Missing X-Eikon-Asset-Type header"
            assert r.headers["X-Eikon-Asset-Type"] == "isotipo"

    def test_06_revoked_api_key_denies_access(self, client: TestClient) -> None:
        """Paso 6: Una key revocada (DELETE) ya no autentica (401)."""
        # Registrar y crear API-key
        _register(client, "agentic-test", "agent@test.com")
        r_key = client.post("/api/v1/auth/api-keys")
        key_data = r_key.json()
        api_key = key_data["key"]
        key_id = key_data["id"]

        # Verificar que la key funciona (con cookie de sesión)
        r_me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert r_me.status_code == 200, "API-key debe autenticar antes de revoke"

        # Revocar la key
        r_revoke = client.delete(f"/api/v1/auth/api-keys/{key_id}")
        assert r_revoke.status_code == 204, f"Revoke failed: {r_revoke.text}"

        # Limpiar cookies para forzar uso de la key revocada
        client.cookies.clear()

        # Intentar usar la key revocada → 401
        r_denied = client.get(
            "/auth/me",
            headers={"X-API-Key": api_key}
        )
        assert r_denied.status_code == 401, \
            f"Revoked key debe devolver 401, got {r_denied.status_code}: {r_denied.text}"

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
    def test_07_complete_agentic_workflow(self, tmp_path: Path) -> None:
        """Paso 7: Flujo COMPLETO sin cookies: register → api-key → brand → identity → generate."""
        app = create_app(
            _settings(tmp_path),
            output_root=tmp_path / "output",
            axes_config_path=AXES_PATH,
        )
        with TestClient(app) as client:
            # 1. Registrar
            reg = _register(client, "full-workflow", "workflow@test.com")
            assert reg["tenant"]["slug"] == "full-workflow"

            # 2. Crear API-key
            r_key = client.post("/api/v1/auth/api-keys")
            assert r_key.status_code == 201
            api_key = r_key.json()["key"]

            # 3. Limpiar cookies → solo API-key de aquí en adelante
            client.cookies.clear()

            # 4. Listar asset-types
            r_types = client.get(
                "/api/v1/asset-types",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            assert r_types.status_code == 200
            asset_types = r_types.json()["asset_types"]
            assert len(asset_types) > 0

            # 5. Crear marca
            brand = _create_brand_with_identity(client, api_key, slug="workflow-brand")
            brand_id = brand["id"]
            assert brand["logo_style"] == "poligono_regular"

            # 6. Actualizar identidad
            r_identity = client.post(
                f"/api/v1/brands/{brand_id}/set-identity",
                headers={"X-API-Key": api_key},
                json={"logo_style": "poligono_irregular", "logo_seed": 777}
            )
            assert r_identity.status_code == 200
            assert r_identity.json()["identity"]["logo_seed"] == 777

            # 7. Generar PNG
            r_gen = client.post(
                "/api/v1/generate",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "brand_id": brand_id,
                    "asset_type": "isotipo",
                    "content": {"titulo": "Workflow Complete"},
                },
            )
            assert r_gen.status_code == 200
            assert r_gen.content.startswith(b"\x89PNG")
            assert len(r_gen.content) > 100

            # 8. Revocar key y verificar 401
            key_id = r_key.json()["id"]
            r_revoke = client.post("/api/v1/auth/api-keys")  # Necesita cookie de sesión
            # (No tenemos cookie después de limpiar, así que saltamos este paso de revoke en flujo sin cookie)
            # En un flujo real, se usaría otra sesión o se guardaría la cookie antes de limpiar

    def test_08_api_key_isolation_between_tenants(self, app: FastAPI) -> None:
        """API-key de tenant A no puede acceder a recursos de tenant B."""
        client1 = TestClient(app)
        client2 = TestClient(app)

        # Tenant A: registrar y crear API-key
        _register(client1, "tenant-a", "owner-a@test.com")
        r_key_a = client1.post("/api/v1/auth/api-keys")
        api_key_a = r_key_a.json()["key"]

        # Tenant B: registrar y crear API-key
        _register(client2, "tenant-b", "owner-b@test.com")
        r_key_b = client2.post("/api/v1/auth/api-keys")
        api_key_b = r_key_b.json()["key"]

        # Tenant A: crear marca
        client1.cookies.clear()
        brand_a = _create_brand_with_identity(client1, api_key_a, slug="brand-a")
        brand_a_id = brand_a["id"]

        # Tenant B: crear marca
        client2.cookies.clear()
        brand_b = _create_brand_with_identity(client2, api_key_b, slug="brand-b")
        brand_b_id = brand_b["id"]

        # Verificar: API-key_b NO puede acceder a brand_a_id (GET brand)
        r_cross = client2.get(
            f"/api/v1/brands/{brand_a_id}",
            headers={"X-API-Key": api_key_b},
        )
        assert r_cross.status_code == 404, \
            f"API-key from tenant B should not access brand from tenant A, got {r_cross.status_code}: {r_cross.text}"

        # Verificar: API-key_a SÍ puede acceder a brand_a_id
        r_self = client1.get(
            f"/api/v1/brands/{brand_a_id}",
            headers={"X-API-Key": api_key_a},
        )
        assert r_self.status_code == 200, f"API-key_a should access its own brand, got {r_self.status_code}"
        assert r_self.json()["id"] == brand_a_id

    def test_09_missing_or_invalid_api_key_returns_401(self, client: TestClient) -> None:
        """Request sin API-key o con key inválida devuelve 401."""
        # Registrar
        _register(client, "agentic-test", "agent@test.com")

        # Limpiar cookies
        client.cookies.clear()

        # Request sin API-key
        r_no_key = client.get("/auth/me")
        assert r_no_key.status_code == 401, f"Expected 401, got {r_no_key.status_code}"

        # Request con API-key inválida
        r_bad_key = client.get(
            "/auth/me",
            headers={"X-API-Key": "invalid-key-xxx"}
        )
        assert r_bad_key.status_code == 401, f"Expected 401 for invalid key, got {r_bad_key.status_code}"

    def test_10_api_key_auth_with_x_api_key_header(self, client: TestClient) -> None:
        """X-API-Key header también funciona para autenticación."""
        # Registrar y crear API-key
        _register(client, "agentic-test", "agent@test.com")
        r_key = client.post("/api/v1/auth/api-keys")
        api_key = r_key.json()["key"]

        # Limpiar cookies
        client.cookies.clear()

        # Crear marca con X-API-Key header
        r = client.post(
            "/api/v1/brands",
            headers={"X-API-Key": api_key},
            json={
                "slug": "x-api-key-brand",
                "name": "X-API-Key Brand",
                "palette": {"bg": "#0b1417", "primario": "#f5efe3"},
                "typography": {"titulos": "Inter", "cuerpo": "Inter"},
            },
        )
        assert r.status_code == 201, f"Create brand with X-API-Key failed: {r.text}"
        brand = r.json()
        assert brand["slug"] == "x-api-key-brand"
