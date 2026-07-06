"""Tests de regresión para los bugs corregidos en webapp/api + storage.

Cubre:
  Bug 1 — Paleta: claves en inglés se traducen; claves desconocidas se rechazan.
  Bug 2 — Delete: borrar un brand limpia el árbol de salida en disco.
  Bug 3 — Info-disclosure: variation_to_dict no expone output_path ni tenant_id.
  Bug 4 — Galería ordering: order=recientes/calidad, NULLs al final, batch_id server-side.
  Bug 5 — Minors: brand_id overflow 422, protected slugs, 409 genérico,
           PUT slug-only, variations response unificado, IDs duplicados en ZIP,
           asset_types vs taxonomy, eje en fixed Y permuted rechazado.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eikon_core.constants import ROOT as REPO_ROOT
from webapp.api.serializers import batch_to_dict, brand_to_dict, variation_to_dict
from webapp.app import create_app
from webapp.config import Settings
from webapp.storage import (
    create_brand,
    create_tenant,
    create_variation,
    init_db,
)
from webapp.storage_backend.local import LocalStorage

AXES_PATH = REPO_ROOT / "config" / "axes.json"
PASSWORD = "supersecret1"


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_root=tmp_path, sqlite_path=tmp_path / "eikon.db")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    return create_app(
        _settings(tmp_path), output_root=tmp_path / "output", axes_config_path=AXES_PATH
    )


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _register(client: TestClient, slug: str = "acme", email: str = "owner@acme.com") -> None:
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


def _create_brand(
    client: TestClient, slug: str = "kosmos", palette: dict[str, str] | None = None
) -> int:
    r = client.post(
        "/api/v1/brands",
        json={
            "slug": slug,
            "name": slug.title(),
            "palette": palette or {"bg": "#0b1417", "acento": "#43b5a6"},
        },
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


# ── Bug 1: Paleta — traducción inglés→español y rechazo de claves desconocidas ──


class TestPaletteKeys:
    def test_valid_spanish_keys_accepted(self, client: TestClient) -> None:
        """Claves válidas en español se aceptan sin transformación."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"bg": "#000", "primario": "#111", "acento": "#43b5a6"},
            },
        )
        assert r.status_code == 201
        p = r.json()["palette"]
        assert p["bg"] == "#000"
        assert p["primario"] == "#111"
        assert p["acento"] == "#43b5a6"

    def test_english_primary_translated_to_primario(self, client: TestClient) -> None:
        """'primary' se traduce a 'primario' en la paleta."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"primary": "#ff0000"},
            },
        )
        assert r.status_code == 201
        p = r.json()["palette"]
        assert "primario" in p
        assert p["primario"] == "#ff0000"
        assert "primary" not in p

    def test_english_accent_translated_to_acento(self, client: TestClient) -> None:
        """'accent' se traduce a 'acento'."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"accent": "#00ff00"},
            },
        )
        assert r.status_code == 201
        p = r.json()["palette"]
        assert "acento" in p
        assert "accent" not in p

    def test_english_background_translated_to_bg(self, client: TestClient) -> None:
        """'background' se traduce a 'bg'."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"background": "#0a0a0a"},
            },
        )
        assert r.status_code == 201
        p = r.json()["palette"]
        assert "bg" in p
        assert "background" not in p

    def test_english_text_translated_to_texto(self, client: TestClient) -> None:
        """'text' se traduce a 'texto'."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"text": "#ffffff"},
            },
        )
        assert r.status_code == 201
        p = r.json()["palette"]
        assert "texto" in p
        assert "text" not in p

    def test_unknown_palette_key_rejected_422(self, client: TestClient) -> None:
        """Claves desconocidas en paleta devuelven 422."""
        _register(client)
        r = client.post(
            "/api/v1/brands",
            json={
                "slug": "mybrand",
                "name": "My Brand",
                "palette": {"unknown_color": "#red"},
            },
        )
        assert r.status_code == 422, r.text

    def test_put_with_english_palette_updates_render(self, client: TestClient) -> None:
        """PUT con paleta en inglés traduce claves y el brand refleja el cambio."""
        _register(client)
        bid = _create_brand(client)
        r = client.put(
            f"/api/v1/brands/{bid}",
            json={"palette": {"primary": "#abcdef"}},
        )
        assert r.status_code == 200
        p = r.json()["palette"]
        assert "primario" in p
        assert p["primario"] == "#abcdef"

    def test_put_with_unknown_palette_key_rejected(self, client: TestClient) -> None:
        """PUT con clave desconocida en paleta devuelve 422."""
        _register(client)
        bid = _create_brand(client)
        r = client.put(
            f"/api/v1/brands/{bid}",
            json={"palette": {"color_x": "#ff00ff"}},
        )
        assert r.status_code == 422


# ── Bug 2: Delete — limpieza de archivos en disco ────────────────────────────


class TestDeleteCleanup:
    def test_delete_removes_output_dir(self, app: FastAPI, tmp_path: Path) -> None:
        """Borrar un brand elimina el árbol de salida si existe."""
        # Crear la app con output_root en tmp_path/output
        output_root = tmp_path / "output"
        output_root.mkdir(parents=True, exist_ok=True)
        settings = _settings(tmp_path)
        app_local = create_app(settings, output_root=output_root, axes_config_path=AXES_PATH)

        with TestClient(app_local) as c:
            _register(c)
            bid = _create_brand(c, "delbrand")

            # Obtener tenant_id a partir del me endpoint
            me = c.get("/auth/me").json()
            tenant_id = int(me["tenant"]["id"])

            # Simular archivos de salida del brand
            brand_dir = output_root / "tenants" / str(tenant_id) / "delbrand"
            brand_dir.mkdir(parents=True, exist_ok=True)
            (brand_dir / "logo.png").write_bytes(b"fakepng")
            assert brand_dir.exists()

            # Borrar el brand
            r = c.delete(f"/api/v1/brands/{bid}")
            assert r.status_code == 204

            # El directorio de salida del brand debe haberse borrado
            assert not brand_dir.exists()

    def test_delete_nonexistent_output_is_graceful(self, client: TestClient) -> None:
        """Borrar un brand sin archivos de salida no falla (best-effort)."""
        _register(client)
        bid = _create_brand(client, "nodirband")
        r = client.delete(f"/api/v1/brands/{bid}")
        assert r.status_code == 204

    def test_delete_returns_404_for_unknown_brand(self, client: TestClient) -> None:
        """DELETE de un brand que no existe devuelve 404."""
        _register(client)
        r = client.delete("/api/v1/brands/999999")
        assert r.status_code == 404


# ── Bug 3: Info-disclosure — serializer no expone rutas absolutas ─────────────


class TestInfoDisclosure:
    def test_variation_serializer_no_output_path(self) -> None:
        """variation_to_dict NO debe incluir output_path."""
        row = {
            "id": 1,
            "batch_id": 2,
            "tenant_id": 99,
            "brand_id": 3,
            "axis_params_json": "{}",
            "seed": 12345,
            "score": 0.9,
            "output_path": "/absolute/server/path/to/file.png",
            "wcag_json": None,
            "layout_status": None,
            "selected": 0,
            "created_at": 1700000000,
        }
        result = variation_to_dict(row)
        assert "output_path" not in result
        assert "/absolute/server" not in str(result)

    def test_variation_serializer_no_tenant_id(self) -> None:
        """variation_to_dict NO debe exponer tenant_id."""
        row = {
            "id": 1,
            "batch_id": 2,
            "tenant_id": 99,
            "brand_id": 3,
            "axis_params_json": "{}",
            "seed": 12345,
            "score": 0.9,
            "output_path": "/some/path.png",
            "wcag_json": None,
            "layout_status": None,
            "selected": 0,
            "created_at": 1700000000,
        }
        result = variation_to_dict(row)
        assert "tenant_id" not in result

    def test_variation_serializer_has_file_url(self) -> None:
        """variation_to_dict expone file_url relativa (no absoluta)."""
        row = {
            "id": 42,
            "batch_id": None,
            "tenant_id": 1,
            "brand_id": 1,
            "axis_params_json": "{}",
            "seed": None,
            "score": None,
            "output_path": "/some/absolute/path.png",
            "wcag_json": None,
            "layout_status": None,
            "selected": 0,
            "created_at": 1700000000,
        }
        result = variation_to_dict(row)
        assert result["file_url"] == "/api/v1/variations/42/file"
        assert result["file_url"].startswith("/api/")  # relativa, no absoluta

    def test_batch_serializer_no_tenant_id(self) -> None:
        """batch_to_dict NO debe exponer tenant_id."""
        row = {
            "id": 1,
            "tenant_id": 99,
            "brand_id": 3,
            "spec_json": "{}",
            "status": "pending",
            "counts_json": "{}",
            "created_at": 1700000000,
            "started_at": None,
            "finished_at": None,
        }
        result = batch_to_dict(row)
        assert "tenant_id" not in result

    def test_brand_serializer_no_tenant_id(self) -> None:
        """brand_to_dict NO debe exponer tenant_id."""
        row = {
            "id": 1,
            "tenant_id": 99,
            "slug": "test",
            "name": "Test",
            "palette_json": "{}",
            "typography_json": "{}",
            "logo_text": "",
            "logo_symbol": "",
            "texts_json": "{}",
            "created_at": 1700000000,
        }
        result = brand_to_dict(row)
        assert "tenant_id" not in result

    def test_api_brand_response_no_tenant_id(self, client: TestClient) -> None:
        """Endpoint GET /brands/{id} no expone tenant_id."""
        _register(client)
        bid = _create_brand(client)
        r = client.get(f"/api/v1/brands/{bid}")
        assert r.status_code == 200
        assert "tenant_id" not in r.json()


# ── Bug 4: Galería ordering ───────────────────────────────────────────────────


class TestGalleryOrdering:
    @pytest.fixture()
    def db(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        return db_path

    def _make_variations(self, db: Path, scores: list[float | None]) -> tuple[int, int]:
        """Crea un tenant + brand + variaciones con los scores dados. Devuelve (tid, bid)."""
        t = create_tenant(db, "t1", "Tenant 1")
        tid = int(t["id"])
        brand = create_brand(db, tenant_id=tid, slug="brand1", name="Brand 1")
        bid = int(brand["id"])
        for i, score in enumerate(scores):
            create_variation(
                db,
                tid,
                bid,
                seed=i,
                score=score,
            )
        return tid, bid

    def test_calidad_order_score_desc_nulls_last(self, db: Path) -> None:
        """order=calidad: las variaciones con score más alto van primero, NULLs al final."""
        from typing import Any

        from webapp.api.gallery import _sort_rows

        rows: list[dict[str, Any]] = [
            {"id": 1, "score": 0.5, "created_at": 1000},
            {"id": 2, "score": None, "created_at": 2000},
            {"id": 3, "score": 0.9, "created_at": 900},
            {"id": 4, "score": None, "created_at": 3000},
            {"id": 5, "score": 0.1, "created_at": 800},
        ]
        sorted_rows = _sort_rows(rows, "calidad")
        # Con score: 0.9, 0.5, 0.1 primero; NULLs al final
        assert sorted_rows[0]["id"] == 3  # score=0.9
        assert sorted_rows[1]["id"] == 1  # score=0.5
        assert sorted_rows[2]["id"] == 5  # score=0.1
        # NULLs al final (orden entre NULLs no está garantizado)
        assert sorted_rows[3]["score"] is None
        assert sorted_rows[4]["score"] is None

    def test_recientes_order_by_created_at_desc(self, db: Path) -> None:
        """order=recientes: las variaciones más recientes van primero."""
        from typing import Any

        from webapp.api.gallery import _sort_rows

        rows: list[dict[str, Any]] = [
            {"id": 1, "score": 0.9, "created_at": 1000},
            {"id": 2, "score": 0.1, "created_at": 3000},
            {"id": 3, "score": 0.5, "created_at": 2000},
        ]
        sorted_rows = _sort_rows(rows, "recientes")
        assert sorted_rows[0]["id"] == 2  # created_at=3000
        assert sorted_rows[1]["id"] == 3  # created_at=2000
        assert sorted_rows[2]["id"] == 1  # created_at=1000

    def test_gallery_api_order_recientes(self, client: TestClient) -> None:
        """GET /gallery?order=recientes responde 200."""
        _register(client)
        bid = _create_brand(client)
        r = client.get(f"/api/v1/gallery?brand_id={bid}&order=recientes")
        assert r.status_code == 200

    def test_gallery_api_order_calidad(self, client: TestClient) -> None:
        """GET /gallery?order=calidad responde 200."""
        _register(client)
        bid = _create_brand(client)
        r = client.get(f"/api/v1/gallery?brand_id={bid}&order=calidad")
        assert r.status_code == 200

    def test_gallery_api_invalid_order_422(self, client: TestClient) -> None:
        """GET /gallery?order=invalid devuelve 422."""
        _register(client)
        bid = _create_brand(client)
        r = client.get(f"/api/v1/gallery?brand_id={bid}&order=invalid")
        assert r.status_code == 422

    def test_gallery_api_batch_id_filter_respected(self, app: FastAPI, tmp_path: Path) -> None:
        """GET /gallery?batch_id=X filtra correctamente por batch."""
        from webapp.storage import create_batch

        settings = _settings(tmp_path)
        app_local = create_app(
            settings, output_root=tmp_path / "output", axes_config_path=AXES_PATH
        )
        db = settings.sqlite_path

        with TestClient(app_local) as c:
            _register(c)
            bid = _create_brand(c, "filterbrand")
            me = c.get("/auth/me").json()
            tenant_id = int(me["tenant"]["id"])

        # Crear 2 batches y variaciones a nivel de storage directamente
        b1 = create_batch(db, tenant_id, bid, spec={})
        b2 = create_batch(db, tenant_id, bid, spec={})
        create_variation(db, tenant_id, bid, batch_id=int(b1["id"]), score=0.8)
        create_variation(db, tenant_id, bid, batch_id=int(b1["id"]), score=0.7)
        create_variation(db, tenant_id, bid, batch_id=int(b2["id"]), score=0.6)

        with TestClient(app_local) as c:
            # Re-autenticar
            c.post("/auth/login", json={"email": "owner@acme.com", "password": PASSWORD})
            r = c.get(f"/api/v1/gallery?batch_id={b1['id']}")
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) == 2, (
                f"esperaba 2 variaciones de batch {b1['id']}, obtuve {len(items)}"
            )

            r2 = c.get(f"/api/v1/gallery?batch_id={b2['id']}")
            assert r2.status_code == 200
            assert len(r2.json()["items"]) == 1

    def test_null_scores_at_end_in_api(self, app: FastAPI, tmp_path: Path) -> None:
        """Variaciones con score=NULL aparecen al final en order=calidad."""
        settings = _settings(tmp_path)
        app_local = create_app(
            settings, output_root=tmp_path / "output", axes_config_path=AXES_PATH
        )
        db = settings.sqlite_path

        with TestClient(app_local) as c:
            _register(c)
            bid = _create_brand(c, "nullscore")
            me = c.get("/auth/me").json()
            tenant_id = int(me["tenant"]["id"])

        # Crear variaciones directamente en storage
        create_variation(db, tenant_id, bid, score=None)
        create_variation(db, tenant_id, bid, score=0.9)
        create_variation(db, tenant_id, bid, score=None)

        with TestClient(app_local) as c:
            c.post("/auth/login", json={"email": "owner@acme.com", "password": PASSWORD})
            r = c.get(f"/api/v1/gallery?brand_id={bid}&order=calidad")
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) == 3
            # El primero debe tener score no-nulo
            assert items[0]["score"] is not None
            # Los últimos son NULLs
            assert items[1]["score"] is None or items[2]["score"] is None


# ── Bug 5: Minors ─────────────────────────────────────────────────────────────


class TestMinorBugs:
    # brand_id > 2^63 → 422
    def test_brand_id_overflow_is_422(self, client: TestClient) -> None:
        """brand_id fuera de rango int64 devuelve 422 en lugar de 500."""
        _register(client)
        huge_id = 2**64
        r = client.get(f"/api/v1/brands/{huge_id}")
        assert r.status_code == 422

    def test_brand_id_overflow_delete_is_422(self, client: TestClient) -> None:
        """DELETE brand_id > 2^63 devuelve 422."""
        _register(client)
        r = client.delete(f"/api/v1/brands/{2**64}")
        assert r.status_code == 422

    def test_brand_id_overflow_put_is_422(self, client: TestClient) -> None:
        """PUT brand_id > 2^63 devuelve 422."""
        _register(client)
        r = client.put(f"/api/v1/brands/{2**64}", json={"name": "x"})
        assert r.status_code == 422

    # PROTECTED_BRAND_SLUGS
    def test_protected_slug_prizma_rejected(self, client: TestClient) -> None:
        """Slug 'prizma' está reservado y debe devolver 422."""
        _register(client)
        r = client.post("/api/v1/brands", json={"slug": "prizma", "name": "Prizma"})
        assert r.status_code == 422

    def test_protected_slug_prizma_pistis_rejected(self, client: TestClient) -> None:
        """Slug 'prizma-pistis' está reservado y debe devolver 422."""
        _register(client)
        r = client.post("/api/v1/brands", json={"slug": "prizma-pistis", "name": "Prizma Pistis"})
        assert r.status_code == 422

    # 409 genérico (no filtra SQLite)
    def test_409_does_not_leak_sqlite_text(self, client: TestClient) -> None:
        """409 de slug duplicado tiene mensaje genérico, no detalles de SQLite."""
        _register(client)
        _create_brand(client, "dup")
        r = client.post("/api/v1/brands", json={"slug": "dup", "name": "dup2"})
        assert r.status_code == 409
        detail = r.json()["detail"]
        # El mensaje NO debe contener referencias a SQLite ni UNIQUE constraint
        assert "UNIQUE" not in detail
        assert "sqlite" not in detail.lower()
        assert "IntegrityError" not in detail

    # PUT slug-only: mensaje más útil
    def test_put_slug_only_gives_clear_message(self, client: TestClient) -> None:
        """PUT con solo 'slug' devuelve 422 con mensaje que menciona campos permitidos."""
        _register(client)
        bid = _create_brand(client)
        r = client.put(f"/api/v1/brands/{bid}", json={"slug": "new-slug"})
        assert r.status_code == 422
        detail = r.json()["detail"]
        # El mensaje debe mencionar qué campos se permiten
        assert "name" in detail or "palette" in detail or "campos permitidos" in detail

    # batch variations → {"variations": [...], "items": [...]}
    def test_batch_variations_has_both_keys(self, app: FastAPI, tmp_path: Path) -> None:
        """GET /batches/{id}/variations devuelve tanto 'variations' como 'items'."""
        from webapp.storage import create_batch

        settings = _settings(tmp_path)
        app_local = create_app(
            settings, output_root=tmp_path / "output", axes_config_path=AXES_PATH
        )
        db = settings.sqlite_path

        with TestClient(app_local) as c:
            _register(c)
            bid = _create_brand(c, "batchbrand")
            me = c.get("/auth/me").json()
            tenant_id = int(me["tenant"]["id"])

        batch = create_batch(db, tenant_id, bid, spec={})
        create_variation(db, tenant_id, bid, batch_id=int(batch["id"]))

        with TestClient(app_local) as c:
            c.post("/auth/login", json={"email": "owner@acme.com", "password": PASSWORD})
            r = c.get(f"/api/v1/batches/{batch['id']}/variations")
            assert r.status_code == 200
            body = r.json()
            assert "variations" in body
            assert "items" in body
            assert len(body["variations"]) == len(body["items"])

    # ZIP con IDs duplicados → deduplicados
    def test_zip_duplicate_ids_deduplicated(self, app: FastAPI, tmp_path: Path) -> None:
        """POST /downloads/zip con IDs duplicados no duplica archivos en el ZIP."""
        settings = _settings(tmp_path)
        output_root = tmp_path / "output"
        app_local = create_app(settings, output_root=output_root, axes_config_path=AXES_PATH)
        db = settings.sqlite_path

        with TestClient(app_local) as c:
            _register(c)
            bid = _create_brand(c, "zipbrand")
            me = c.get("/auth/me").json()
            tenant_id = int(me["tenant"]["id"])

        # Crear un PNG falso bajo la ruta que espera el seam
        storage = LocalStorage(base_dir=output_root)
        rel_path = "zipbrand/logos/isotipo/1/combo_001.png"
        abs_path = storage.save(tenant_id, rel_path, b"fakepngdata")

        # Crear variación que apunte a ese archivo
        var = create_variation(db, tenant_id, bid, output_path=abs_path)
        var_id = int(var["id"])

        with TestClient(app_local) as c:
            c.post("/auth/login", json={"email": "owner@acme.com", "password": PASSWORD})
            # Enviar el mismo ID dos veces
            r = c.post("/api/v1/downloads/zip", json={"ids": [var_id, var_id, var_id]})
            assert r.status_code == 200
            import io
            import zipfile

            zf = zipfile.ZipFile(io.BytesIO(r.content))
            # Debe haber solo 1 archivo (deduplicado)
            assert len(zf.namelist()) == 1

    # asset_types: validación vs taxonomy.json
    def test_asset_type_from_taxonomy_isotipo_valid(self, client: TestClient) -> None:
        """'isotipo' es un tipo válido según taxonomy.json."""
        _register(client)
        bid = _create_brand(client)
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": bid,
                "asset_types": ["isotipo"],
                "permuted": ["palette_scheme"],
                "count": 1,
            },
        )
        # 202 (encolado) o 422 si no hay opciones de paleta suficientes
        assert r.status_code in (202, 422)

    def test_asset_type_not_in_taxonomy_rejected(self, client: TestClient) -> None:
        """Un asset_type que no existe en taxonomy.json devuelve 422."""
        _register(client)
        bid = _create_brand(client)
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": bid,
                "asset_types": ["tipo_inventado_xyz"],
                "permuted": ["palette_scheme"],
            },
        )
        assert r.status_code == 422

    # Eje en fixed Y permuted al mismo tiempo → 422
    def test_axis_in_fixed_and_permuted_rejected(self, client: TestClient) -> None:
        """Un eje en fixed y permuted simultáneamente devuelve 422."""
        _register(client)
        bid = _create_brand(client)
        r = client.post(
            "/api/v1/batches",
            json={
                "brand_id": bid,
                "fixed": {"palette_scheme": "brand"},
                "permuted": ["palette_scheme"],  # mismo eje en ambos
                "count": 1,
            },
        )
        assert r.status_code == 422
        # El detail puede ser string o lista (Pydantic v2); verificar como texto
        detail_str = str(r.json()["detail"])
        assert "palette_scheme" in detail_str

    # batch_id > 2^63 en galería → 422
    def test_gallery_batch_id_overflow_422(self, client: TestClient) -> None:
        """batch_id fuera de rango int64 en /gallery devuelve 422."""
        _register(client)
        r = client.get(f"/api/v1/gallery?batch_id={2**64}")
        assert r.status_code == 422
