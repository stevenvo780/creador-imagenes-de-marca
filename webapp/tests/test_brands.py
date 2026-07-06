"""Tests pytest: brands CRUD + tenant isolation + seed idempotente."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from webapp.storage import (
    create_batch,
    create_brand,
    create_tenant,
    create_tenant_user,
    create_variation,
    delete_brand,
    get_batch,
    get_brand,
    get_brand_by_slug,
    get_tenant_by_slug,
    get_variation,
    init_db,
    list_batches,
    list_brands,
    list_variations,
    select_variation,
    update_batch_status,
    update_brand,
    upsert_brand,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """BD temporal limpia para cada test."""
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture()
def two_tenants(db: Path) -> tuple[int, int]:
    """Devuelve (tenant_a_id, tenant_b_id) con dos tenants independientes."""
    t_a = create_tenant(db, "tenant-alpha", "Tenant Alpha")
    t_b = create_tenant(db, "tenant-beta", "Tenant Beta")
    return int(t_a["id"]), int(t_b["id"])


# ---------------------------------------------------------------------------
# get_tenant_by_slug
# ---------------------------------------------------------------------------


def test_get_tenant_by_slug_missing(db: Path) -> None:
    assert get_tenant_by_slug(db, "no-existe") is None


def test_get_tenant_by_slug_found(db: Path) -> None:
    create_tenant(db, "my-tenant", "My Tenant")
    row = get_tenant_by_slug(db, "my-tenant")
    assert row is not None
    assert row["slug"] == "my-tenant"
    assert row["name"] == "My Tenant"


# ---------------------------------------------------------------------------
# Brands CRUD básico
# ---------------------------------------------------------------------------


def test_create_brand_returns_row(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(
        db,
        tenant_id=tid_a,
        slug="kosmos",
        name="Kósmos",
        palette={"bg": "#000", "acento": "#43b5a6"},
        typography={"titulos": "Inter"},
        logo_text="Kósmos",
        logo_symbol="⬡",
        texts={"og_general": {"titulo": "Kósmos"}},
    )
    assert brand["id"] > 0
    assert brand["slug"] == "kosmos"
    assert brand["name"] == "Kósmos"
    assert brand["tenant_id"] == tid_a
    assert json.loads(brand["palette_json"])["acento"] == "#43b5a6"
    assert json.loads(brand["typography_json"])["titulos"] == "Inter"
    assert brand["logo_text"] == "Kósmos"
    assert brand["logo_symbol"] == "⬡"


def test_create_brand_duplicate_slug_same_tenant_fails(
    db: Path, two_tenants: tuple[int, int]
) -> None:
    tid_a, _ = two_tenants
    create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(sqlite3.IntegrityError):
        create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos duplicate")


def test_create_brand_same_slug_different_tenants_ok(
    db: Path, two_tenants: tuple[int, int]
) -> None:
    """El mismo slug puede existir en dos tenants distintos."""
    tid_a, tid_b = two_tenants
    b_a = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos A")
    b_b = create_brand(db, tenant_id=tid_b, slug="kosmos", name="Kósmos B")
    assert b_a["id"] != b_b["id"]


def test_get_brand_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    """get_brand devuelve None si el brand no pertenece al tenant solicitado."""
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    assert get_brand(db, tid_a, brand["id"]) is not None
    assert get_brand(db, tid_b, brand["id"]) is None


def test_get_brand_by_slug_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    create_brand(db, tenant_id=tid_a, slug="iris", name="Iris A")
    assert get_brand_by_slug(db, tid_a, "iris") is not None
    assert get_brand_by_slug(db, tid_b, "iris") is None


def test_list_brands_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    create_brand(db, tenant_id=tid_a, slug="brand-1", name="Brand 1")
    create_brand(db, tenant_id=tid_a, slug="brand-2", name="Brand 2")
    create_brand(db, tenant_id=tid_b, slug="brand-x", name="Brand X")

    brands_a = list_brands(db, tid_a)
    brands_b = list_brands(db, tid_b)
    assert len(brands_a) == 2
    assert len(brands_b) == 1
    assert brands_b[0]["slug"] == "brand-x"


def test_update_brand_ok(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Old Name")
    updated = update_brand(db, tid_a, brand["id"], name="New Name")
    assert updated["name"] == "New Name"


def test_update_brand_wrong_tenant_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(KeyError):
        update_brand(db, tid_b, brand["id"], name="Hacked")


def test_update_brand_no_valid_fields_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(ValueError):
        update_brand(db, tid_a, brand["id"], nonexistent_field="x")


def test_delete_brand_ok(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    delete_brand(db, tid_a, brand["id"])
    assert get_brand(db, tid_a, brand["id"]) is None


def test_delete_brand_wrong_tenant_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(KeyError):
        delete_brand(db, tid_b, brand["id"])


# ---------------------------------------------------------------------------
# upsert_brand — idempotencia
# ---------------------------------------------------------------------------


def test_upsert_brand_inserts_on_first_call(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = upsert_brand(db, tid_a, "iris", "Iris")
    assert brand["id"] > 0
    assert brand["slug"] == "iris"


def test_upsert_brand_updates_on_second_call(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    b1 = upsert_brand(db, tid_a, "iris", "Iris v1")
    b2 = upsert_brand(db, tid_a, "iris", "Iris v2")
    # Mismo id (no se duplica)
    assert b1["id"] == b2["id"]
    # Nombre actualizado
    assert b2["name"] == "Iris v2"
    # Sigue siendo solo 1 brand
    assert len(list_brands(db, tid_a)) == 1


# ---------------------------------------------------------------------------
# Batches CRUD
# ---------------------------------------------------------------------------


def test_create_batch_ok(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    batch = create_batch(db, tid_a, brand["id"], spec={"n": 5})
    assert batch["id"] > 0
    assert batch["tenant_id"] == tid_a
    assert batch["brand_id"] == brand["id"]
    assert batch["status"] == "pending"
    assert json.loads(batch["spec_json"])["n"] == 5


def test_create_batch_wrong_tenant_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(KeyError):
        create_batch(db, tid_b, brand["id"])


def test_get_batch_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    batch = create_batch(db, tid_a, brand["id"])
    assert get_batch(db, tid_a, batch["id"]) is not None
    assert get_batch(db, tid_b, batch["id"]) is None


def test_list_batches_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand_a = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    brand_b = create_brand(db, tenant_id=tid_b, slug="iris", name="Iris")
    create_batch(db, tid_a, brand_a["id"])
    create_batch(db, tid_a, brand_a["id"])
    create_batch(db, tid_b, brand_b["id"])
    assert len(list_batches(db, tid_a)) == 2
    assert len(list_batches(db, tid_b)) == 1


def test_list_batches_filtered_by_brand(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    b1 = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    b2 = create_brand(db, tenant_id=tid_a, slug="iris", name="Iris")
    create_batch(db, tid_a, b1["id"])
    create_batch(db, tid_a, b2["id"])
    assert len(list_batches(db, tid_a, brand_id=b1["id"])) == 1


def test_update_batch_status(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    batch = create_batch(db, tid_a, brand["id"])
    update_batch_status(db, batch["id"], "running", tenant_id=tid_a)
    update_batch_status(
        db, batch["id"], "completed", counts={"ok": 10, "fail": 0}, tenant_id=tid_a
    )
    row = get_batch(db, tid_a, batch["id"])
    assert row is not None
    assert row["status"] == "completed"
    assert json.loads(row["counts_json"])["ok"] == 10
    assert row["started_at"] is not None
    assert row["finished_at"] is not None


# ---------------------------------------------------------------------------
# Variations CRUD
# ---------------------------------------------------------------------------


def test_create_variation_ok(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    var = create_variation(
        db,
        tid_a,
        brand["id"],
        axis_params={"layout": "horizontal", "color_mode": "dark"},
        seed=42,
        score=0.87,
        output_path="output/kosmos/v1.png",
        wcag={"AA": True},
        layout_status="ok",
    )
    assert var["id"] > 0
    assert var["tenant_id"] == tid_a
    assert var["brand_id"] == brand["id"]
    assert var["seed"] == 42
    assert abs(float(var["score"]) - 0.87) < 1e-6
    assert var["selected"] == 0
    assert json.loads(var["axis_params_json"])["layout"] == "horizontal"
    assert json.loads(var["wcag_json"])["AA"] is True


def test_create_variation_wrong_tenant_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    with pytest.raises(KeyError):
        create_variation(db, tid_b, brand["id"])


def test_get_variation_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    var = create_variation(db, tid_a, brand["id"])
    assert get_variation(db, tid_a, var["id"]) is not None
    assert get_variation(db, tid_b, var["id"]) is None


def test_list_variations_scoped(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    b_a = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    b_b = create_brand(db, tenant_id=tid_b, slug="iris", name="Iris")
    create_variation(db, tid_a, b_a["id"])
    create_variation(db, tid_a, b_a["id"])
    create_variation(db, tid_b, b_b["id"])
    assert len(list_variations(db, tid_a)) == 2
    assert len(list_variations(db, tid_b)) == 1


def test_list_variations_filtered_by_brand(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    b1 = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    b2 = create_brand(db, tenant_id=tid_a, slug="iris", name="Iris")
    create_variation(db, tid_a, b1["id"])
    create_variation(db, tid_a, b2["id"])
    assert len(list_variations(db, tid_a, brand_id=b1["id"])) == 1


def test_list_variations_filtered_by_batch(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    batch_1 = create_batch(db, tid_a, brand["id"])
    batch_2 = create_batch(db, tid_a, brand["id"])
    create_variation(db, tid_a, brand["id"], batch_id=batch_1["id"])
    create_variation(db, tid_a, brand["id"], batch_id=batch_1["id"])
    create_variation(db, tid_a, brand["id"], batch_id=batch_2["id"])
    assert len(list_variations(db, tid_a, batch_id=batch_1["id"])) == 2
    assert len(list_variations(db, tid_a, batch_id=batch_2["id"])) == 1


def test_select_variation(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, _ = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    var = create_variation(db, tid_a, brand["id"])
    assert var["selected"] == 0
    select_variation(db, tid_a, var["id"], selected=True)
    updated = get_variation(db, tid_a, var["id"])
    assert updated is not None and updated["selected"] == 1
    select_variation(db, tid_a, var["id"], selected=False)
    reverted = get_variation(db, tid_a, var["id"])
    assert reverted is not None and reverted["selected"] == 0


def test_select_variation_wrong_tenant_raises(db: Path, two_tenants: tuple[int, int]) -> None:
    tid_a, tid_b = two_tenants
    brand = create_brand(db, tenant_id=tid_a, slug="kosmos", name="Kósmos")
    var = create_variation(db, tid_a, brand["id"])
    with pytest.raises(KeyError):
        select_variation(db, tid_b, var["id"])


# ---------------------------------------------------------------------------
# Coexistencia: tenants existentes con jobs/assets no se rompen
# ---------------------------------------------------------------------------


def test_existing_tables_unaffected(db: Path) -> None:
    """init_db sobre una BD con datos previos no borra nada."""
    u = create_tenant_user(db, "tenant-c", "Tenant C", "c@example.com", "password123")
    # Re-init no debe dañar nada
    init_db(db)
    # Tenant sigue existiendo
    row = get_tenant_by_slug(db, "tenant-c")
    assert row is not None
    assert row["id"] == u["tenant_id"]


# ---------------------------------------------------------------------------
# Seed — idempotencia
# ---------------------------------------------------------------------------


def test_seed_brands_idempotent(db: Path, tmp_path: Path) -> None:
    """Ejecutar seed dos veces no duplica brands."""
    from webapp.seed import seed_brands

    # Directorio temporal con marcas de prueba
    marcas_dir = tmp_path / "marcas"
    marcas_dir.mkdir()
    for i in range(3):
        brand_data = {
            "slug": f"test-brand-{i}",
            "nombre_producto": f"Test Brand {i}",
            "paleta": {"bg": "#000"},
            "tipografia": {"titulos": "Inter"},
            "logo_texto": f"TB{i}",
            "logo_simbolo": "★",
            "textos": {},
        }
        (marcas_dir / f"test-brand-{i}.json").write_text(json.dumps(brand_data), encoding="utf-8")

    result_1 = seed_brands(db, marcas_dir=marcas_dir, tenant_slug="seed-owner")
    result_2 = seed_brands(db, marcas_dir=marcas_dir, tenant_slug="seed-owner")

    assert result_1["brands_upserted"] == 3
    assert result_2["brands_upserted"] == 3
    assert not result_1["errors"]
    assert not result_2["errors"]

    # Solo 1 tenant creado
    assert result_1["tenant_id"] == result_2["tenant_id"]

    # Solo 3 brands en BD (no duplicados)
    brands = list_brands(db, result_1["tenant_id"])
    assert len(brands) == 3


def test_seed_brands_real_marcas(db: Path) -> None:
    """Seed con los archivos reales de marcas/ del repo."""
    from webapp.seed import _DEFAULT_MARCAS_DIR, seed_brands

    if not _DEFAULT_MARCAS_DIR.exists():
        pytest.skip("directorio marcas/ no encontrado")

    result = seed_brands(db, marcas_dir=_DEFAULT_MARCAS_DIR, tenant_slug="seed-real")
    assert result["brands_upserted"] > 0
    assert not result["errors"], f"Errores en seed: {result['errors']}"

    # Segunda ejecución sigue siendo idempotente
    result2 = seed_brands(db, marcas_dir=_DEFAULT_MARCAS_DIR, tenant_slug="seed-real")
    count_1 = result["brands_upserted"]
    count_2 = result2["brands_upserted"]
    assert count_1 == count_2

    # Brands en BD coincide con los upserted
    brands = list_brands(db, result["tenant_id"])
    assert len(brands) == count_1
