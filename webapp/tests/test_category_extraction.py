"""Tests para la extracción agnóstica de categoría desde paths de storage.

Valida que `_category_from_path()` funciona correctamente con:
- Paths GCS (gs://bucket/...)
- Paths locales absolutos (/abs/path/...)
- Paths relativos (tenants/...)
- Windows paths (con backslashes)
- Categorías válidas e inválidas
- Edge cases (None, vacío, path muy corto)
"""

from __future__ import annotations

from webapp.api.serializers import _category_from_path

# ── Tests con formato GCS ────────────────────────────────────────────────────


def test_category_from_path_gcs_logos() -> None:
    """GCS path con categoría 'logos'."""
    path = "gs://my-bucket/tenants/tenant-123/kosmos/logos/png_100x100/batch-abc/logo.png"
    assert _category_from_path(path) == "logos"


def test_category_from_path_gcs_banners() -> None:
    """GCS path con categoría 'banners'."""
    path = "gs://eikon-prod/tenants/tenant-xyz/acme/banners/jpg_1200x628/batch-def/banner.jpg"
    assert _category_from_path(path) == "banners"


def test_category_from_path_gcs_cards() -> None:
    """GCS path con categoría 'cards'."""
    path = "gs://bucket/tenants/t1/brand1/cards/svg/batch1/card.svg"
    assert _category_from_path(path) == "cards"


def test_category_from_path_gcs_og() -> None:
    """GCS path con categoría 'og'."""
    path = "gs://storage/tenants/tenant-og/brand/og/png_1200x630/batch123/og_image.png"
    assert _category_from_path(path) == "og"


def test_category_from_path_gcs_stationery() -> None:
    """GCS path con categoría 'stationery'."""
    path = "gs://cdn/tenants/t-stationery/mybrand/stationery/pdf/batch-s1/letterhead.pdf"
    assert _category_from_path(path) == "stationery"


# ── Tests con formato Local absoluto ────────────────────────────────────────


def test_category_from_path_local_absolute_logos() -> None:
    """Local absolute path con categoría 'logos'."""
    path = "/home/user/eikon/output/tenants/tenant-123/kosmos/logos/png_100x100/batch-abc/logo.png"
    assert _category_from_path(path) == "logos"


def test_category_from_path_local_absolute_banners() -> None:
    """Local absolute path con categoría 'banners'."""
    path = "/srv/eikon/data/tenants/t-banner/acme/banners/jpg_1200x628/batch-def/banner.jpg"
    assert _category_from_path(path) == "banners"


def test_category_from_path_local_absolute_cards() -> None:
    """Local absolute path con categoría 'cards'."""
    path = "/var/lib/eikon/output/tenants/t1/brand1/cards/svg/batch1/card.svg"
    assert _category_from_path(path) == "cards"


def test_category_from_path_local_absolute_og() -> None:
    """Local absolute path con categoría 'og'."""
    path = "/mnt/storage/tenants/tenant-og/brand/og/png_1200x630/batch123/og_image.png"
    assert _category_from_path(path) == "og"


def test_category_from_path_local_absolute_stationery() -> None:
    """Local absolute path con categoría 'stationery'."""
    path = "/eikon/output/tenants/t-stationery/mybrand/stationery/pdf/batch-s1/letterhead.pdf"
    assert _category_from_path(path) == "stationery"


# ── Tests con formato Relativo ──────────────────────────────────────────────


def test_category_from_path_relative_logos() -> None:
    """Relative path con categoría 'logos'."""
    path = "tenants/tenant-123/kosmos/logos/png_100x100/batch-abc/logo.png"
    assert _category_from_path(path) == "logos"


def test_category_from_path_relative_banners() -> None:
    """Relative path con categoría 'banners'."""
    path = "tenants/t-banner/acme/banners/jpg_1200x628/batch-def/banner.jpg"
    assert _category_from_path(path) == "banners"


def test_category_from_path_relative_cards() -> None:
    """Relative path con categoría 'cards'."""
    path = "tenants/t1/brand1/cards/svg/batch1/card.svg"
    assert _category_from_path(path) == "cards"


# ── Tests con Windows paths (backslashes) ───────────────────────────────────


def test_category_from_path_windows_backslash_logos() -> None:
    """Windows path con backslashes y categoría 'logos'."""
    path = (
        r"C:\Users\Dev\eikon\output\tenants\tenant-win\mybrand\logos\png_100x100\batch-a\logo.png"
    )
    assert _category_from_path(path) == "logos"


def test_category_from_path_windows_backslash_banners() -> None:
    """Windows path con backslashes y categoría 'banners'."""
    path = r"D:\data\tenants\t-windows\acme\banners\jpg_1200x628\batch-b\banner.jpg"
    assert _category_from_path(path) == "banners"


# ── Tests con Edge Cases ─────────────────────────────────────────────────────


def test_category_from_path_invalid_category() -> None:
    """Categoría desconocida → None."""
    path = "gs://bucket/tenants/tenant-123/kosmos/invalid_cat/png/batch-abc/file.png"
    assert _category_from_path(path) is None


def test_category_from_path_no_tenants_segment_fallback() -> None:
    """Sin 'tenants' en el path → fallback a -4.

    Path sin 'tenants': /some/path/invalid_cat/png_100x100/batch/file.png
    parts[-4] = 'invalid_cat' (no es categoría) → None.
    """
    path = "/some/other/path/invalid_cat/png_100x100/batch/file.png"
    result = _category_from_path(path)
    assert result is None


def test_category_from_path_no_tenants_fallback_works() -> None:
    """Sin 'tenants' pero fallback a -4 detecta categoría válida.

    Path: /path/logos/png/batch_id/file.png
    parts[-4] = 'logos' (válida) → 'logos'.
    """
    path = "/some/path/logos/png/batch/file.png"
    assert _category_from_path(path) == "logos"


def test_category_from_path_none_input() -> None:
    """Input None → None."""
    assert _category_from_path(None) is None


def test_category_from_path_empty_string() -> None:
    """Input vacío → None."""
    assert _category_from_path("") is None


def test_category_from_path_path_too_short() -> None:
    """Path con menos de 4 segmentos → None."""
    path = "a/b/c"
    assert _category_from_path(path) is None


def test_category_from_path_only_tenants_no_category() -> None:
    """Path con 'tenants' pero sin suficientes segmentos para categoría.

    Path: tenants/tenant_id/brand (falta asset_type y más)
    cat_idx = 0 + 3 = 3, pero len(parts) = 3 → no procesa método agnóstico.
    Fallback a -4 = 'brand' (no válida) → None.
    """
    path = "tenants/t1/brand"
    assert _category_from_path(path) is None


def test_category_from_path_multiple_tenants_segments() -> None:
    """Path con múltiples 'tenants' (corner case) → usa el PRIMERO.

    Python's `str.index()` retorna la PRIMERA ocurrencia.
    """
    # Construcción artificial: tenants/.../tenants/.../logos/...
    path = "prefix/tenants/t1/mybrand/logos/png/batch/file"
    # parts.index("tenants") → 1 (primer tenants)
    # cat_idx = 1 + 3 = 4 → parts[4] = "logos" ✓
    assert _category_from_path(path) == "logos"


def test_category_from_path_tenants_as_last_segment() -> None:
    """'tenants' es el último segmento → cat_idx fuera de rango → fallback.

    Path: /path/tenants
    cat_idx = idx + 3 >= len(parts) → no procesa método agnóstico.
    """
    path = "/some/path/tenants"
    assert _category_from_path(path) is None


def test_category_from_path_all_categories_logos() -> None:
    """Prueba explícita: categoría 'logos'."""
    path = "tenants/t/b/logos/png/batch/file"
    assert _category_from_path(path) == "logos"


def test_category_from_path_all_categories_banners() -> None:
    """Prueba explícita: categoría 'banners'."""
    path = "tenants/t/b/banners/png/batch/file"
    assert _category_from_path(path) == "banners"


def test_category_from_path_all_categories_cards() -> None:
    """Prueba explícita: categoría 'cards'."""
    path = "tenants/t/b/cards/svg/batch/file"
    assert _category_from_path(path) == "cards"


def test_category_from_path_all_categories_og() -> None:
    """Prueba explícita: categoría 'og'."""
    path = "tenants/t/b/og/png/batch/file"
    assert _category_from_path(path) == "og"


def test_category_from_path_all_categories_stationery() -> None:
    """Prueba explícita: categoría 'stationery'."""
    path = "tenants/t/b/stationery/pdf/batch/file"
    assert _category_from_path(path) == "stationery"


def test_category_from_path_real_world_gcs_production() -> None:
    """Ejemplo real: GCS production con estructura estándar."""
    path = "gs://eikon-prod-bucket/tenants/org-acme-2024/kosmos-brand/logos/png_100x100_icon/batch-20240615-001/logo_variation_015.png"
    assert _category_from_path(path) == "logos"


def test_category_from_path_real_world_local_production() -> None:
    """Ejemplo real: Local production con estructura estándar."""
    path = "/mnt/eikon-data/output/tenants/org-startup-xyz/acme-corp/banners/jpg_1200x628_web/batch-20240701-abc/banner_var_042.jpg"
    assert _category_from_path(path) == "banners"
