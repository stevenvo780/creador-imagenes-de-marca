"""Cobertura sintética de los módulos combinatorios + ranking + isotype + render_combination.

Este archivo agrupa ~50 tests enfocados en superficies con poca o nula cobertura
previa, manteniendo los tests existentes intactos y respetando los invariantes
críticos del proyecto:

  1. Multi-tenant: cada consulta está scoped por tenant_id (user A nunca ve a B).
  2. Determinismo: mismos (seed_salt, params, marca) producen seeds, hashes y
     dHashes idénticos entre re-ejecuciones.
  3. No destructive writes fuera de setup/teardown: tmp_path para PNGs y DBs.
  4. Sin mocks externos: usamos los dataclasses y funciones reales de eikon_core.

Secciones:
  - test_axes_*:        load_axes_config, validate_combination, dataclasses
  - test_ranking_*:     RankingSignal, VariationScore, _compute_dhash, rank()
  - test_render_comb_*: render_combination directo vía dry_run (sin Playwright)
  - test_isotype_*:     generate_isotype para los 4 estilos + determinismo
  - test_determinism_*: planner + ranking + render deterministas en re-runs
  - test_edge_cases_*:  hashes duplicados, layout fail, wcag fail, tenant scope

Tests de Playwright dependientes (render real) están marcados con skip si la
librería no está disponible, manteniendo verde la suite en CI mínimo.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from eikon_core.combinatorial import AxesConfig, load_axes_config
from eikon_core.combinatorial.axes import (
    AxesConfig as AxesConfigDataclass,
)
from eikon_core.combinatorial.axes import (
    Axis,
    AxisOption,
    validate_axes_config,
)
from eikon_core.combinatorial.planner import Combination, CombinationSpec, plan_combinations
from eikon_core.combinatorial.ranking import (
    RankingSignal,
    VariationScore,
    _compute_dhash,
    _dhash_distance,
    _signal_layout_status,
    rank,
)
from eikon_core.constants import OUTPUT_DIR, ROOT
from eikon_core.isotype import IsotypeParams, generate_isotype
from eikon_core.orchestrator import render_combination
from eikon_core.svg_generator import seeded_random
from webapp.app import create_app
from webapp.config import Settings

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


PASSWORD = "supersecret1"
AXES_PATH = ROOT / "config" / "axes.json"


def _settings(tmp_path: Path) -> Settings:
    """Settings con BD temporal aislada por test."""
    return Settings(data_root=tmp_path, sqlite_path=tmp_path / "eikon.db")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    """App FastAPI con BD temporal y axes.json real."""
    return create_app(_settings(tmp_path), output_root=OUTPUT_DIR, axes_config_path=AXES_PATH)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """TestClient sin levantar el worker pool (tests rápidos)."""
    return TestClient(app)


@pytest.fixture()
def axes() -> AxesConfig:
    """AxesConfig cargado desde el config/axes.json del repo."""
    return load_axes_config(AXES_PATH)


@pytest.fixture()
def minimal_marca() -> dict[str, object]:
    """Marca mínima con slug pinakotheke-kosmos (no requiere archivo en marcas/)."""
    return {
        "slug": "pinakotheke-kosmos",
        "nombre_producto": "Kósmos",
        "tagline": "Simulación del orden natural",
        "paleta": {
            "bg": "#0b1417",
            "primario": "#0b1417",
            "acento": "#43b5a6",
            "acento_2": "#8d7cc0",
            "texto": "#e8e0d4",
        },
        "tipografia": {"titulos": "Inter", "cuerpo": "Inter"},
        "logo_texto": "Kósmos",
        "logo_simbolo": "⬡",
        "textos": {"logos": {"titulo": "K", "copy": ""}},
    }


@pytest.fixture()
def high_contrast_pngs(tmp_path: Path) -> Path:
    """Genera 3 PNGs con alto contraste para diferenciar dHashes (dist > 20).

    Devuelve el directorio donde se escriben ``combo_{000,001,002}.png``.
    Los píxeles centrales son opuestos al fondo, garantizando dHashes distintos.
    """
    png_dir = tmp_path / "high_contrast"
    png_dir.mkdir(parents=True, exist_ok=True)
    palette = [(0, 0, 0), (255, 255, 255), (200, 30, 30)]
    for i, bg in enumerate(palette):
        img = Image.new("RGB", (96, 96), bg)
        fg = (255 - bg[0], 255 - bg[1], 255 - bg[2])
        for x in range(28, 68):
            for y in range(28, 68):
                img.putpixel((x, y), fg)
        img.save(png_dir / f"combo_{i:03d}.png")
    return png_dir


@pytest.fixture()
def png_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Directorio temporal limpio para escribir PNGs de prueba."""
    d = tmp_path / "pngs"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _register(client: TestClient, slug: str, email: str) -> None:
    """Helper: registra tenant + user vía API; assert 201."""
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
    """Helper: crea brand y devuelve su id."""
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


# ===========================================================================
# 1. Axes / AxesConfig
# ===========================================================================


def test_axes_config_load_real_file() -> None:
    """load_axes_config lee el axes.json real con todos los ejes canónicos."""
    cfg_obj = load_axes_config(AXES_PATH)
    assert isinstance(cfg_obj, AxesConfig)
    assert "palette_scheme" in cfg_obj.axes
    assert "typography_pairing" in cfg_obj.axes
    assert "isotype_style" in cfg_obj.axes
    # Cada eje canónico tiene opciones declaradas
    assert len(cfg_obj.axes["palette_scheme"].options) >= 3
    assert len(cfg_obj.axes["layout"].options) >= 2


def test_axes_config_file_not_found(tmp_path: Path) -> None:
    """load_axes_config lanza FileNotFoundError si el archivo no existe."""
    with pytest.raises(FileNotFoundError, match="Axes config not found"):
        load_axes_config(tmp_path / "missing.json")


def test_axes_config_malformed_json(tmp_path: Path) -> None:
    """load_axes_config propaga JSONDecodeError ante JSON inválido."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_axes_config(bad)


def test_axes_config_axis_names_sorted() -> None:
    """axis_names() devuelve los nombres en orden alfabético determinista."""
    cfg_obj = load_axes_config(AXES_PATH)
    names = cfg_obj.axis_names()
    assert names == sorted(names)
    assert "palette_scheme" in names


def test_axes_config_get_axis_returns_axis(axes: AxesConfig) -> None:
    """get_axis devuelve el Axis dataclass cuando existe."""
    axis = axes.get_axis("palette_scheme")
    assert axis is not None
    assert axis.name == "palette_scheme"
    assert axis.axis_type == "enum"
    # Las opciones tienen descripciones cargadas del JSON
    assert any("Mono" in opt.description or "mono" in opt.description for opt in axis.options)


def test_axes_config_get_axis_missing(axes: AxesConfig) -> None:
    """get_axis devuelve None para un eje inexistente (no lanza)."""
    assert axes.get_axis("no_such_axis") is None


def test_axes_config_validate_combination_ok(axes: AxesConfig) -> None:
    """validate_combination acepta combinaciones correctas."""
    axes.validate_combination({"palette_scheme": "brand", "layout": "lockup_horizontal"})


def test_axes_config_validate_combination_unknown_axis(axes: AxesConfig) -> None:
    """validate_combination lanza ValueError ante eje desconocido."""
    with pytest.raises(ValueError, match="Unknown axis"):
        axes.validate_combination({"no_such_axis": "x"})


def test_axes_config_validate_combination_unknown_option(axes: AxesConfig) -> None:
    """validate_combination lista las opciones válidas cuando la opción falla."""
    with pytest.raises(ValueError) as exc_info:
        axes.validate_combination({"palette_scheme": "no_such_option"})
    msg = str(exc_info.value)
    assert "palette_scheme" in msg
    assert "Valid options" in msg
    assert "brand" in msg


def test_axes_config_validate_combination_empty_is_ok(axes: AxesConfig) -> None:
    """Una combinación vacía es válida (todos los ejes son opt-in)."""
    axes.validate_combination({})


def test_axis_option_as_dict_roundtrip() -> None:
    """AxisOption.as_dict() preserva todos los campos."""
    opt = AxisOption(
        name="brand",
        description="Default",
        overrides={"acento": "#fff"},
        data_attrs={"data-x": "y"},
    )
    d = opt.as_dict()
    assert d["name"] == "brand"
    assert d["description"] == "Default"
    assert d["overrides"]["acento"] == "#fff"
    assert d["data_attrs"]["data-x"] == "y"


def test_axis_get_option_returns_option_or_none() -> None:
    """Axis.get_option devuelve la opción o None."""
    axis = Axis(
        name="color",
        label="Color",
        options=(AxisOption(name="a"), AxisOption(name="b")),
    )
    option_a = axis.get_option("a")
    assert option_a is not None
    assert option_a.name == "a"
    assert axis.get_option("z") is None


def test_axis_option_names_returns_all() -> None:
    """Axis.option_names() devuelve todos los nombres en orden."""
    axis = Axis(name="x", options=(AxisOption(name="a"), AxisOption(name="b")))
    assert axis.option_names() == ["a", "b"]


def test_axes_config_as_dict_roundtrip(tmp_path: Path) -> None:
    """as_dict() de AxesConfig preserva la estructura jerárquica."""
    cfg_obj = AxesConfigDataclass(
        axes={"c": Axis(name="c", label="Color", options=(AxisOption(name="x"),))},
    )
    d = cfg_obj.as_dict()
    assert d["axes"]["c"]["label"] == "Color"
    assert d["axes"]["c"]["options"][0]["name"] == "x"


def test_validate_axes_config_empty_axes_raises() -> None:
    """validate_axes_config rechaza AxesConfig sin ejes."""
    with pytest.raises(ValueError, match="at least one axis"):
        validate_axes_config(AxesConfigDataclass(axes={}))


def test_validate_axes_config_axis_without_options_raises() -> None:
    """validate_axes_config rechaza ejes sin opciones."""
    cfg_obj = AxesConfigDataclass(
        axes={"x": Axis(name="x", options=())},
    )
    with pytest.raises(ValueError, match="at least one option"):
        validate_axes_config(cfg_obj)


def test_validate_axes_config_option_without_name_raises() -> None:
    """validate_axes_config rechaza opciones con name vacío."""
    cfg_obj = AxesConfigDataclass(
        axes={"x": Axis(name="x", options=(AxisOption(name=""),))},
    )
    with pytest.raises(ValueError, match="must have names"):
        validate_axes_config(cfg_obj)


# ===========================================================================
# 2. Ranking / deduplication
# ===========================================================================


def test_ranking_signal_is_dataclass() -> None:
    """RankingSignal es un frozen dataclass inmutable."""
    sig = RankingSignal(name="x", weight=0.5, value=0.8, reason="ok")
    assert sig.name == "x"
    assert sig.weight == 0.5
    assert sig.value == 0.8
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        sig.value = 0.0  # type: ignore[misc]


def test_variation_score_as_dict_serializable(tmp_path: Path) -> None:
    """VariationScore.as_dict() produce un dict JSON-serializable."""
    png = tmp_path / "combo_000.png"
    Image.new("RGB", (10, 10), (0, 0, 0)).save(png)
    score = VariationScore(
        idx=0,
        seed=12345,
        params={"a": "1"},
        marca="pinakotheke-kosmos",
        asset_type="isotipo",
        png_path=png,
        final_score=0.87,
        signals=(RankingSignal(name="s", weight=1.0, value=0.9, reason="ok"),),
        dhash="0" * 64,
    )
    d = score.as_dict()
    assert d["idx"] == 0
    assert d["seed"] == 12345
    assert d["marca"] == "pinakotheke-kosmos"
    assert d["final_score"] == 0.87
    assert d["dhash"] == "0" * 64
    assert len(d["signals"]) == 1
    # Round-trip JSON (sin path stray)
    json.dumps(d, default=str)


def test_compute_dhash_returns_64_char_string(tmp_path: Path) -> None:
    """_compute_dhash devuelve una cadena binaria de 64 chars."""
    png = tmp_path / "x.png"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(png)
    h = _compute_dhash(png)
    assert len(h) == 64
    assert all(c in ("0", "1") for c in h)


def test_compute_dhash_identical_images_same_hash(high_contrast_pngs: Path) -> None:
    """Imágenes idénticas → dHash idéntico (distancia 0)."""
    src = high_contrast_pngs / "combo_000.png"
    copy = high_contrast_pngs / "copy.png"
    shutil.copyfile(src, copy)
    assert _compute_dhash(src) == _compute_dhash(copy)


def test_compute_dhash_distinct_images_differ(high_contrast_pngs: Path) -> None:
    """Imágenes distintas (alto contraste opuesto) → dHash con distancia >= 20."""
    h0 = _compute_dhash(high_contrast_pngs / "combo_000.png")
    h1 = _compute_dhash(high_contrast_pngs / "combo_001.png")
    dist = _dhash_distance(h0, h1)
    assert dist >= 20, f"dist={dist}, esperado >= 20"


def test_compute_dhash_missing_file_returns_error_hash(tmp_path: Path) -> None:
    """_compute_dhash devuelve un hash de error ante archivos inexistentes."""
    h = _compute_dhash(tmp_path / "nope.png")
    assert h.startswith("error_")
    # La distancia contra cualquier hash real es 64 (máx = "diferentes")
    assert _dhash_distance(h, "0" * 64) == 64


def test_dhash_distance_identical_is_zero(tmp_path: Path) -> None:
    """_dhash_distance de un hash consigo mismo es 0."""
    png = tmp_path / "x.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(png)
    h = _compute_dhash(png)
    assert _dhash_distance(h, h) == 0


def test_dhash_distance_empty_or_error_returns_max() -> None:
    """_dhash_distance retorna 64 (max) si alguno de los hashes es vacío o error."""
    assert _dhash_distance("", "0" * 64) == 64
    assert _dhash_distance("0" * 64, "") == 64
    assert _dhash_distance("error_xx", "0" * 64) == 64
    assert _dhash_distance("", "") == 64


def test_rank_empty_variations_returns_empty(tmp_path: Path) -> None:
    """rank() con lista vacía devuelve lista vacía (sin errores)."""
    assert rank([], tmp_path) == []


def test_rank_skips_missing_pngs(tmp_path: Path) -> None:
    """rank() omite variaciones cuyo PNG no existe en disco."""
    variations = [
        {"idx": 0, "seed": 1, "params": {}, "marca": "x", "asset_type": "logo"},
        {"idx": 1, "seed": 2, "params": {}, "marca": "x", "asset_type": "logo"},
    ]
    # No hay PNGs en tmp_path → rank devuelve []
    assert rank(variations, tmp_path) == []


def test_rank_dedups_near_identical(high_contrast_pngs: Path) -> None:
    """rank() deduplica variaciones con dHash distance < threshold."""
    # Replicar la imagen 0 tres veces → mismo dHash → solo 1 sobrevive
    for i in range(1, 3):
        shutil.copyfile(
            high_contrast_pngs / "combo_000.png",
            high_contrast_pngs / f"combo_{i:03d}.png",
        )
    variations = [
        {"idx": 0, "seed": i, "params": {"k": str(i)}, "marca": "x", "asset_type": "logo"}
        for i in range(3)
    ]
    ranked = rank(variations, high_contrast_pngs, top_n=8, dedup_distance_threshold=20)
    assert len(ranked) == 1


def test_rank_top_n_limits_output(high_contrast_pngs: Path) -> None:
    """rank() respeta el parámetro top_n como máximo de salida."""
    variations = [
        {"idx": i, "seed": i, "params": {}, "marca": "x", "asset_type": "logo"} for i in range(3)
    ]
    ranked = rank(variations, high_contrast_pngs, top_n=2, dedup_distance_threshold=5)
    assert len(ranked) <= 2


def test_rank_sorts_by_score_descending(high_contrast_pngs: Path) -> None:
    """rank() ordena el output por final_score descendente."""
    variations = [
        {"idx": i, "seed": i, "params": {}, "marca": "x", "asset_type": "logo"} for i in range(3)
    ]
    ranked = rank(variations, high_contrast_pngs, top_n=8)
    scores = [s.final_score for s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_signal_layout_status_three_states() -> None:
    """_signal_layout_status mapea pass/warn/fail a 1.0/0.5/0.0."""
    sig_pass = _signal_layout_status([])
    assert sig_pass.value == 1.0 and sig_pass.reason == "Layout pass"

    sig_warn = _signal_layout_status([{"type": "overflow_x"}])
    assert sig_warn.value == 0.5
    assert "non-critical" in sig_warn.reason

    sig_fail = _signal_layout_status([{"type": "empty_required_text"}])
    assert sig_fail.value == 0.0
    assert "Layout fail" in sig_fail.reason


def test_signal_layout_status_unknown_warning_type_is_pass() -> None:
    """Un warning de tipo desconocido clasifica como 'info' → agregación 'pass'."""
    # aggregate_layout_status devuelve "pass" si no hay fail ni warn
    sig = _signal_layout_status([{"type": "info_only"}])
    assert sig.value == 1.0


@pytest.mark.parametrize("threshold,expected_count", [(8, 3), (15, 2), (30, 2), (50, 1)])
def test_rank_dedup_threshold_param(
    high_contrast_pngs: Path, threshold: int, expected_count: int
) -> None:
    """Variando dedup_distance_threshold se ajusta cuántas variaciones sobreviven.

    Las distancias dHash entre las 3 imágenes del fixture high_contrast_pngs son
    10/36/42. El threshold define hasta qué distancia dos imágenes se consideran
    "demasiado similares" para ser deduplicadas:

      - threshold=8  → todas las distancias (>=10) pasan → 3 sobreviven
      - threshold=15 → dist 0-2 (10) cae → idx=2 deduplicado vs idx=0 → 2
      - threshold=30 → igual al threshold=15 → 2 (1-2 dist=42 >= 30)
      - threshold=50 → idx=1 deduplicado vs idx=0 (36<50) → 1 sobrevive
    """
    variations = [
        {"idx": i, "seed": i, "params": {}, "marca": "x", "asset_type": "logo"} for i in range(3)
    ]
    ranked = rank(variations, high_contrast_pngs, top_n=8, dedup_distance_threshold=threshold)
    assert len(ranked) == expected_count


# ---------------------------------------------------------------------------
# 2.b rank() con permuted_axes: preservar variedad por eje permutado
# ---------------------------------------------------------------------------


def _identical_pngs_with_params(
    tmp_path: Path,
    params_per_idx: list[dict[str, str]],
    color: tuple[int, int, int] = (40, 80, 120),
) -> Path:
    """Genera PNGs IDÉNTICOS (mismo color sólido) asociados a params distintos.

    Simula el bug del isotype procedural: palette_scheme cambia CSS vars del
    template, pero el SVG generado en Python ignora esos cambios → todas las
    PNGs son visualmente idénticas. Mantener estos params distingue qué eje
    debería preservarse vía ``permuted_axes``.
    """
    png_dir = tmp_path / "identical_with_params"
    png_dir.mkdir(parents=True, exist_ok=True)
    for i in range(len(params_per_idx)):
        Image.new("RGB", (64, 64), color).save(png_dir / f"combo_{i:03d}.png")
    return png_dir


def test_rank_preserves_axis_variety_when_permuted_axes_supplied(tmp_path: Path) -> None:
    """Si ``permuted_axes`` declara ejes que el usuario pidió permutar, el
    ranking garantiza al menos un representante por valor declarado, incluso
    cuando los PNGs son visualmente idénticos (caso isotype procedural con
    palette_scheme que solo cambia CSS vars y no los píxeles del SVG).
    """
    variations: list[dict[str, Any]] = [
        {
            "idx": i,
            "seed": i,
            "params": {"palette_scheme": v},
            "marca": "x",
            "asset_type": "logo",
        }
        for i, v in enumerate(["brand", "mono", "light", "dark"])
    ]
    png_dir = _identical_pngs_with_params(tmp_path, [c["params"] for c in variations])

    # Baseline: SIN permuted_axes, el dedup colapsa los 4 a 1 (comportamiento legacy)
    legacy = rank(variations, png_dir, top_n=8, dedup_distance_threshold=20)
    assert len(legacy) == 1, "sin permuted_axes, dedup por dHash debe colapsar a 1"

    # Con permuted_axes: preserva variedad (>=3 valores de palette_scheme)
    preserved = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={"palette_scheme": ["brand", "mono", "light", "dark"]},
    )
    assert len(preserved) >= 3, (
        f"esperaba >=3 variations (uno por palette_scheme), obtuvo {len(preserved)}"
    )
    seen = {s.params["palette_scheme"] for s in preserved}
    assert len(seen) >= 3, f"esperaba >=3 palette_scheme distintos, vi {seen}"


def test_rank_permuted_axes_none_keeps_legacy_behavior(tmp_path: Path) -> None:
    """``permuted_axes=None`` (no se pasa o se pasa explícitamente) reproduce
    exactamente el comportamiento legacy: dedup por dHash colapsa duplicados.
    """
    png_dir = tmp_path / "v"
    png_dir.mkdir()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(png_dir / "combo_000.png")
    Image.new("RGB", (32, 32), (200, 100, 50)).save(png_dir / "combo_001.png")
    Image.new("RGB", (32, 32), (50, 200, 100)).save(png_dir / "combo_002.png")
    variations = [
        {
            "idx": i,
            "seed": i,
            "params": {"palette_scheme": "brand"},
            "marca": "x",
            "asset_type": "logo",
        }
        for i in range(3)
    ]
    r1 = rank(variations, png_dir, top_n=8, dedup_distance_threshold=20)
    r2 = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes=None,
    )
    assert len(r1) == len(r2)
    assert [s.idx for s in r1] == [s.idx for s in r2]
    # permuted_axes pasado pero eje NO presente en params → fallback legacy
    r3 = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={"otro_eje": ["x", "y"]},
    )
    assert [s.idx for s in r3] == [s.idx for s in r2]


def test_rank_permuted_axes_multi_axis_preserves_each_axis(tmp_path: Path) -> None:
    """Múltiples ejes permutados: cada eje garantiza su propia variedad.

    Una sola variación puede cubrir varios ejes a la vez si sus params
    intersectan sus valores; el algoritmo no duplica esfuerzos.
    """
    png_dir = tmp_path / "multi"
    png_dir.mkdir()
    # PNGs distintos para que el dedup normal no sea un problema (sirve además
    # para asegurar que cada candidato es "no-duplicado" perceptual del resto).
    palette = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (128, 0, 128),
        (0, 128, 128),
    ]
    for i, bg in enumerate(palette[:5]):
        img = Image.new("RGB", (96, 96), bg)
        fg = (255 - bg[0], 255 - bg[1], 255 - bg[2])
        for x in range(28, 68):
            for y in range(28, 68):
                img.putpixel((x, y), fg)
        img.save(png_dir / f"combo_{i:03d}.png")

    variations = [
        {
            "idx": 0,
            "seed": 0,
            "params": {"palette_scheme": "brand", "corner_shape": "sharp"},
            "marca": "x",
            "asset_type": "logo",
        },
        {
            "idx": 1,
            "seed": 1,
            "params": {"palette_scheme": "mono", "corner_shape": "rounded"},
            "marca": "x",
            "asset_type": "logo",
        },
        {
            "idx": 2,
            "seed": 2,
            "params": {"palette_scheme": "light", "corner_shape": "sharp"},
            "marca": "x",
            "asset_type": "logo",
        },
        {
            "idx": 3,
            "seed": 3,
            "params": {"palette_scheme": "dark", "corner_shape": "rounded"},
            "marca": "x",
            "asset_type": "logo",
        },
        {
            "idx": 4,
            "seed": 4,
            "params": {"palette_scheme": "brand", "corner_shape": "rounded"},
            "marca": "x",
            "asset_type": "logo",
        },
    ]
    preserved = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={
            "palette_scheme": ["brand", "mono", "light", "dark"],
            "corner_shape": ["sharp", "rounded"],
        },
    )
    palette_seen = {s.params["palette_scheme"] for s in preserved}
    corner_seen = {s.params["corner_shape"] for s in preserved}
    assert palette_seen == {"brand", "mono", "light", "dark"}
    assert corner_seen == {"sharp", "rounded"}


def test_rank_permuted_axes_idempotent(tmp_path: Path) -> None:
    """Determinismo: dos llamadas con los mismos permuted_axes producen el mismo output."""
    variations: list[dict[str, Any]] = [
        {
            "idx": i,
            "seed": i,
            "params": {"palette_scheme": v},
            "marca": "x",
            "asset_type": "logo",
        }
        for i, v in enumerate(["brand", "mono", "light", "dark"])
    ]
    png_dir = _identical_pngs_with_params(tmp_path, [c["params"] for c in variations])
    r1 = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={"palette_scheme": ["brand", "mono", "light", "dark"]},
    )
    r2 = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={"palette_scheme": ["brand", "mono", "light", "dark"]},
    )
    assert [s.idx for s in r1] == [s.idx for s in r2]
    assert [s.params for s in r1] == [s.params for s in r2]


def test_rank_permuted_axes_respects_top_n(tmp_path: Path) -> None:
    """El cap top_n se aplica DESPUÉS de la garantía por eje: si top_n es muy
    bajo, puede recortar variedad (decisión explícita del llamador)."""
    variations: list[dict[str, Any]] = [
        {
            "idx": i,
            "seed": i,
            "params": {"palette_scheme": v},
            "marca": "x",
            "asset_type": "logo",
        }
        for i, v in enumerate(["brand", "mono", "light", "dark"])
    ]
    png_dir = _identical_pngs_with_params(tmp_path, [c["params"] for c in variations])
    # top_n=2 con permuted_axes=4 values → cap gana, solo 2 sobreviven
    ranked = rank(
        variations,
        png_dir,
        top_n=2,
        dedup_distance_threshold=20,
        permuted_axes={"palette_scheme": ["brand", "mono", "light", "dark"]},
    )
    assert len(ranked) == 2
    # sin cap → 4 (uno por valor)
    ranked_full = rank(
        variations,
        png_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes={"palette_scheme": ["brand", "mono", "light", "dark"]},
    )
    assert len(ranked_full) == 4


# ---------------------------------------------------------------------------
# 2.c Regresión del BUG crítico: worker.py llama a rank() SIN permuted_axes
# ---------------------------------------------------------------------------


def test_worker_renders_and_passes_permuted_axes_to_rank(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regresión: cuando el usuario permuta ``palette_scheme``, el worker debe
    pasar ``permuted_axes`` a ``rank()`` para que el dedup preserve UN representante
    por valor del eje. Antes del fix, el worker llamaba a ``rank(rendered, png_dir)``
    sin el kwarg y, al colapsar el batch a 1 variación (por el isotype procedural
    que ignora CSS vars), se rompía la promesa de variedad del usuario.

    Estrategia:
      - Monkeypatch ``render_combination`` para escribir un PNG dummy sin browser.
      - Monkeypatch ``webapp.jobs.worker.rank`` con un spy que captura sus kwargs.
      - Invocar ``_render_and_rank`` (la función que contiene la llamada) y assert
        que el spy recibió ``permuted_axes`` con los valores declarados en
        ``spec.permuted``.
    """
    import webapp.jobs.worker as worker_module
    from eikon_core.combinatorial.axes import AxesConfig, Axis, AxisOption

    # 1. AxesConfig mínimo: solo palette_scheme con 4 valores
    axes_cfg = AxesConfig(
        axes={
            "palette_scheme": Axis(
                name="palette_scheme",
                label="Palette",
                options=tuple(
                    AxisOption(name=v) for v in ["brand", "mono", "light", "dark"]
                ),
            ),
        },
    )

    # 2. Plan con 4 combinaciones (cada una con palette_scheme distinto)
    spec = CombinationSpec(
        brand="x",
        permuted=["palette_scheme"],
        count=4,
    )
    spec.validate()
    axes_dict = {n: a.option_names() for n, a in axes_cfg.axes.items()}
    plan = plan_combinations(spec, axes_dict)
    assert len(plan) == 4
    assert {c.params["palette_scheme"] for c in plan} == {
        "brand",
        "mono",
        "light",
        "dark",
    }

    # 3. PNGs dummy idénticos en tmp_path (simula isotype procedural que ignora
    # CSS vars → todos los PNGs idénticos)
    png_dir = tmp_path / "pngs"
    png_dir.mkdir()

    async def _fake_render_combination(*args: Any, **kwargs: Any) -> dict[str, Any]:
        """Stub que escribe un PNG dummy y devuelve metadata mínima válida."""
        combination = kwargs.get("combination") or args[2]
        (png_dir / f"combo_{combination.idx:03d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return {"status": "generated", "layout_warnings": []}

    monkeypatch.setattr(worker_module, "render_combination", _fake_render_combination)

    # 4. Spy de rank: en lugar de rankear, capturar kwargs
    captured: dict[str, Any] = {}

    def _spy_rank(
        variations: list[dict[str, Any]],
        png_dir_arg: Path,
        top_n: int = 8,
        dedup_distance_threshold: int = 20,
        permuted_axes: dict[str, list[str]] | None = None,
    ) -> list[VariationScore]:
        captured["variations"] = variations
        captured["png_dir"] = png_dir_arg
        captured["top_n"] = top_n
        captured["permuted_axes"] = permuted_axes
        # Devolver stubs mínimos para que el caller no truene al iterar
        return [
            VariationScore(
                idx=v["idx"],
                seed=v["seed"],
                params=v["params"],
                marca=v["marca"],
                asset_type=v["asset_type"],
                png_path=png_dir_arg / f"combo_{v['idx']:03d}.png",
                final_score=0.5,
                signals=(),
                dhash="0" * 64,
            )
            for v in variations
        ]

    monkeypatch.setattr(worker_module, "rank", _spy_rank)

    # 5. Evitar _get_playwright: monkeypatch a no-op async context manager
    class _FakeAsyncPW:
        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        @property
        def chromium(self) -> Any:
            class _Browser:
                async def launch(self, **kw: Any) -> Any:
                    return _Browser()

                async def close(self) -> None:
                    return None

            return _Browser()

    def _fake_get_playwright() -> tuple[Any, Any]:
        return (lambda: _FakeAsyncPW(), None)

    monkeypatch.setattr(worker_module, "_get_playwright", _fake_get_playwright)
    # _make_png_dir debe usar nuestro tmp para no ensuciar el repo
    monkeypatch.setattr(worker_module, "_make_png_dir", lambda *a, **k: png_dir)

    # 6. Llamar a _render_and_rank con un batch_id cualquiera
    pool = worker_module.WorkerPool(tmp_path / "dummy.db", max_concurrent_jobs=1)
    pool._pending_batches[1] = {"rendered": 0, "ranked": 0, "status": "running"}
    marca = {"slug": "x", "nombre_producto": "X"}
    async def _drive() -> list[VariationScore] | None:
        return await pool._render_and_rank(
            batch_id=1,
            db_url=str(tmp_path / "dummy.db"),
            tenant_id=1,
            spec=spec,
            plan=plan,
            marca=marca,
            marca_slug="x",
            category="logos",
            asset_type="isotipo",
            axes_config=axes_cfg,
        )

    result = asyncio.run(_drive())

    # 7. Aserciones críticas
    assert result is not None, "_render_and_rank devolvió None"
    assert "permuted_axes" in captured, (
        "FAIL DE REGRESIÓN: rank() fue llamado sin kwarg 'permuted_axes'. "
        "Esto colapsa batches de palette_scheme a 1 sola variación cuando el "
        "isotype procedural genera PNGs idénticos."
    )
    pa = captured["permuted_axes"]
    assert pa is not None, "permuted_axes no debe ser None cuando spec.permuted declara ejes"
    assert "palette_scheme" in pa, f"permuted_axes debe incluir palette_scheme: {pa}"
    assert set(pa["palette_scheme"]) == {"brand", "mono", "light", "dark"}, (
        f"permuted_axes[palette_scheme] debe contener los 4 valores declarados, "
        f"recibí {pa['palette_scheme']}"
    )
    assert captured["top_n"] == 4
    assert len(captured["variations"]) == 4


def test_worker_passes_none_permuted_axes_when_spec_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cuando ``spec.permuted`` está vacío (caso legacy / fixed-only), el worker
    pasa ``permuted_axes=None`` para activar el camino legacy de dedup.
    """
    import webapp.jobs.worker as worker_module
    from eikon_core.combinatorial.axes import AxesConfig, Axis

    axes_cfg = AxesConfig(
        axes={
            "palette_scheme": Axis(
                name="palette_scheme",
                label="Palette",
                options=(),
            ),
        },
    )
    spec = CombinationSpec(brand="x", permuted=[], count=1)
    spec.validate()
    plan = plan_combinations(spec, {n: a.option_names() for n, a in axes_cfg.axes.items()})

    png_dir = tmp_path / "pngs"
    png_dir.mkdir()

    async def _fake_render(*args: Any, **kwargs: Any) -> dict[str, Any]:
        combination = kwargs.get("combination") or args[2]
        (png_dir / f"combo_{combination.idx:03d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return {"status": "generated", "layout_warnings": []}

    monkeypatch.setattr(worker_module, "render_combination", _fake_render)

    captured: dict[str, Any] = {}

    def _spy_rank(
        variations: list[dict[str, Any]],
        png_dir_arg: Path,
        top_n: int = 8,
        dedup_distance_threshold: int = 20,
        permuted_axes: dict[str, list[str]] | None = None,
    ) -> list[VariationScore]:
        captured["permuted_axes"] = permuted_axes
        return []

    monkeypatch.setattr(worker_module, "rank", _spy_rank)

    class _Noop:
        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *a: Any) -> bool:
            return False

        @property
        def chromium(self) -> Any:
            class _B:
                async def launch(self, **kw: Any) -> Any:
                    return _B()

                async def close(self) -> None:
                    return None

            return _B()

    monkeypatch.setattr(
        worker_module, "_get_playwright", lambda: (lambda: _Noop(), None)
    )
    monkeypatch.setattr(worker_module, "_make_png_dir", lambda *a, **k: png_dir)

    pool = worker_module.WorkerPool(tmp_path / "dummy.db", max_concurrent_jobs=1)
    pool._pending_batches[1] = {"rendered": 0, "ranked": 0, "status": "running"}

    async def _drive() -> None:
        await pool._render_and_rank(
            batch_id=1,
            db_url=str(tmp_path / "dummy.db"),
            tenant_id=1,
            spec=spec,
            plan=plan,
            marca={"slug": "x"},
            marca_slug="x",
            category="logos",
            asset_type="logo",
            axes_config=axes_cfg,
        )

    asyncio.run(_drive())
    # permuted_axes=None activa el camino legacy de dedup por dHash
    assert captured["permuted_axes"] is None


# ===========================================================================
# 3. render_combination (sin Playwright, vía dry_run=True)
# ===========================================================================


def test_render_combination_dry_run_returns_dry_run_status(
    axes: AxesConfig, minimal_marca: dict[str, object]
) -> None:
    """render_combination con dry_run=True devuelve status='dry_run' sin renderizar."""
    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme"],
        count=1,
        seed_salt="cov-test",
    )
    plan = plan_combinations(spec, {n: a.option_names() for n, a in axes.axes.items()})

    async def _run() -> dict[str, object]:
        return await render_combination(
            browser=None,  # dry_run no usa browser
            marca_slug="pinakotheke-kosmos",
            combination=plan[0],
            asset_type="isotipo",
            marca=minimal_marca,
            axes_config=axes,
            dry_run=True,
        )

    meta = asyncio.run(_run())
    assert meta["status"] == "dry_run"
    assert meta["category"] == "logos"
    assert meta["type"] == "isotipo"
    # Sin warnings porque dry_run no ejecuta el render real
    assert meta["warnings"] == []


def test_render_combination_validates_params_first(
    axes: AxesConfig, minimal_marca: dict[str, object]
) -> None:
    """render_combination valida params ANTES de invocar render_asset."""
    bad_combo = Combination(
        idx=0,
        seed=1,
        params={"palette_scheme": "no_such_option"},
        marca="pinakotheke-kosmos",
        asset_type="isotipo",
    )

    async def _run() -> None:
        await render_combination(
            browser=None,
            marca_slug="pinakotheke-kosmos",
            combination=bad_combo,
            asset_type="isotipo",
            marca=minimal_marca,
            axes_config=axes,
            dry_run=True,
        )

    with pytest.raises(ValueError, match="Unknown option"):
        asyncio.run(_run())


def test_render_combination_unknown_axis_raises(
    axes: AxesConfig, minimal_marca: dict[str, object]
) -> None:
    """render_combination rechaza combinaciones con ejes no declarados."""
    bad_combo = Combination(
        idx=0,
        seed=1,
        params={"completely_unknown_axis": "value"},
        marca="pinakotheke-kosmos",
        asset_type="isotipo",
    )

    async def _run() -> None:
        await render_combination(
            browser=None,
            marca_slug="pinakotheke-kosmos",
            combination=bad_combo,
            asset_type="isotipo",
            marca=minimal_marca,
            axes_config=axes,
            dry_run=True,
        )

    with pytest.raises(ValueError, match="Unknown axis"):
        asyncio.run(_run())


def test_render_combination_deterministic_input_hash(
    axes: AxesConfig, minimal_marca: dict[str, object]
) -> None:
    """El input_hash es determinista: misma combinación → mismo hash."""
    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme"],
        count=1,
        seed_salt="cov-test",
    )
    plan = plan_combinations(spec, {n: a.option_names() for n, a in axes.axes.items()})

    async def _run(combo: Combination) -> str:
        meta = await render_combination(
            browser=None,
            marca_slug="pinakotheke-kosmos",
            combination=combo,
            asset_type="isotipo",
            marca=minimal_marca,
            axes_config=axes,
            dry_run=True,
        )
        return str(meta["input_hash"])

    h1 = asyncio.run(_run(plan[0]))
    h2 = asyncio.run(_run(plan[0]))
    assert h1 == h2


def test_render_combination_different_combos_different_hashes(
    axes: AxesConfig, minimal_marca: dict[str, object]
) -> None:
    """Distintas combinaciones con distintos params → distintos input_hash."""
    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme", "layout"],
        count=2,
        seed_salt="cov-test",
    )
    plan = plan_combinations(spec, {n: a.option_names() for n, a in axes.axes.items()})

    async def _run(combo: Combination) -> str:
        meta = await render_combination(
            browser=None,
            marca_slug="pinakotheke-kosmos",
            combination=combo,
            asset_type="isotipo",
            marca=minimal_marca,
            axes_config=axes,
            dry_run=True,
        )
        return str(meta["input_hash"])

    h1 = asyncio.run(_run(plan[0]))
    h2 = asyncio.run(_run(plan[1]))
    assert h1 != h2


# ===========================================================================
# 4. Isotype (SVG procedural)
# ===========================================================================


@pytest.mark.parametrize("style", ["lettermark", "geometric", "abstract", "enclosure"])
def test_generate_isotype_returns_valid_svg(style: str) -> None:
    """generate_isotype devuelve SVG con namespace y viewBox correctos."""
    params = IsotypeParams(
        seed=42,
        style=style,
        brand_initials="K",
        brand_symbol="⬡",
        primary_color="#43b5a6",
        accent_color="#e8e0d4",
        bg_color="#0b1417",
        size=120,
    )
    svg = generate_isotype(params)
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'viewBox="0 0 120 120"' in svg


def test_generate_isotype_unknown_style_returns_empty_svg() -> None:
    """generate_isotype con style desconocido devuelve un SVG vacío (no falla)."""
    params = IsotypeParams(
        seed=1,
        style="nonexistent",
        brand_initials="X",
        brand_symbol="*",
        primary_color="#fff",
        accent_color="#000",
        bg_color="#222",
    )
    svg = generate_isotype(params)
    # wrap_svg con content vacío → solo el wrapper
    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_generate_isotype_lettermark_uses_initial_letter() -> None:
    """El lettermark contiene la inicial en mayúscula."""
    params = IsotypeParams(
        seed=1,
        style="lettermark",
        brand_initials="iris",
        brand_symbol="★",
        primary_color="#fff",
        accent_color="#000",
        bg_color="#222",
        size=100,
    )
    svg = generate_isotype(params)
    # La inicial debe estar en mayúsculas (I, no i)
    assert ">I</text>" in svg


def test_generate_isotype_deterministic_same_seed() -> None:
    """Mismos params + seed → SVG idéntico (determinismo del generador)."""
    params_a = IsotypeParams(
        seed=99,
        style="geometric",
        brand_initials="A",
        brand_symbol="",
        primary_color="#abc",
        accent_color="#def",
        bg_color="#012",
    )
    params_b = IsotypeParams(
        seed=99,
        style="geometric",
        brand_initials="A",
        brand_symbol="",
        primary_color="#abc",
        accent_color="#def",
        bg_color="#012",
    )
    svg_a = generate_isotype(params_a)
    svg_b = generate_isotype(params_b)
    assert svg_a == svg_b


def test_generate_isotype_different_seed_different_svg() -> None:
    """Distintos seeds → SVGs distintos (al menos en alguna sección no-trivial)."""
    base_kw: dict[str, object] = dict(
        style="abstract",
        brand_initials="K",
        brand_symbol="⬡",
        primary_color="#43b5a6",
        accent_color="#e8e0d4",
        bg_color="#0b1417",
        size=200,
    )
    p1 = IsotypeParams(seed=1, **base_kw)  # type: ignore[arg-type]
    p2 = IsotypeParams(seed=2, **base_kw)  # type: ignore[arg-type]
    svg1 = generate_isotype(p1)
    svg2 = generate_isotype(p2)
    assert svg1 != svg2


def test_isotype_size_param_affects_viewbox() -> None:
    """El parámetro size define el viewBox del SVG resultante."""
    p_small = IsotypeParams(
        seed=1,
        style="lettermark",
        brand_initials="K",
        brand_symbol="",
        primary_color="#fff",
        accent_color="#000",
        bg_color="#222",
        size=64,
    )
    p_large = IsotypeParams(
        seed=1,
        style="lettermark",
        brand_initials="K",
        brand_symbol="",
        primary_color="#fff",
        accent_color="#000",
        bg_color="#222",
        size=512,
    )
    assert 'viewBox="0 0 64 64"' in generate_isotype(p_small)
    assert 'viewBox="0 0 512 512"' in generate_isotype(p_large)


def test_seeded_random_deterministic() -> None:
    """seeded_random es determinista por (seed, index, range)."""
    a = seeded_random(seed=42, index=3, range_max=10.0)
    b = seeded_random(seed=42, index=3, range_max=10.0)
    assert a == b
    # Mismo seed, distinto index → valor distinto (con alta probabilidad)
    c = seeded_random(seed=42, index=4, range_max=10.0)
    assert a != c
    # range_max se respeta
    assert 0.0 <= a <= 10.0


# ===========================================================================
# 5. Determinism (axes + planner + ranking cross-run)
# ===========================================================================


def test_planner_same_inputs_same_seeds(axes: AxesConfig) -> None:
    """plan_combinations con los mismos inputs produce las mismas seeds."""
    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme", "layout"],
        count=4,
        seed_salt="cov-determinism",
    )
    axes_dict = {n: a.option_names() for n, a in axes.axes.items()}
    plan_a = plan_combinations(spec, axes_dict)
    plan_b = plan_combinations(spec, axes_dict)
    assert [c.seed for c in plan_a] == [c.seed for c in plan_b]
    assert [tuple(sorted(c.params.items())) for c in plan_a] == [
        tuple(sorted(c.params.items())) for c in plan_b
    ]


def test_planner_different_salt_different_seeds(axes: AxesConfig) -> None:
    """Cambiar seed_salt cambia los seeds aunque los params sean idénticos."""
    base_kw: dict[str, object] = dict(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme"],
        count=3,
    )
    axes_dict = {n: a.option_names() for n, a in axes.axes.items()}
    plan_a = plan_combinations(
        CombinationSpec(seed_salt="salt-A", **base_kw),  # type: ignore[arg-type]
        axes_dict,
    )
    plan_b = plan_combinations(
        CombinationSpec(seed_salt="salt-B", **base_kw),  # type: ignore[arg-type]
        axes_dict,
    )
    # Mismos params (axes idénticos)
    assert [c.params for c in plan_a] == [c.params for c in plan_b]
    # Pero seeds distintos
    assert [c.seed for c in plan_a] != [c.seed for c in plan_b]


def test_axes_load_is_deterministic(tmp_path: Path) -> None:
    """Cargar el mismo axes.json dos veces produce AxesConfig dataclass-equal."""
    copied = tmp_path / "axes_copy.json"
    shutil.copyfile(AXES_PATH, copied)
    cfg_a = load_axes_config(AXES_PATH)
    cfg_b = load_axes_config(copied)
    assert cfg_a.axes.keys() == cfg_b.axes.keys()
    for name, axis_a in cfg_a.axes.items():
        axis_b = cfg_b.axes[name]
        assert axis_a.name == axis_b.name
        assert axis_a.option_names() == axis_b.option_names()


def test_ranking_dhash_is_deterministic(high_contrast_pngs: Path) -> None:
    """_compute_dhash produce el mismo hash para el mismo archivo."""
    h1 = _compute_dhash(high_contrast_pngs / "combo_000.png")
    h2 = _compute_dhash(high_contrast_pngs / "combo_000.png")
    assert h1 == h2
    assert _dhash_distance(h1, h2) == 0


def test_ranking_same_input_same_output(high_contrast_pngs: Path) -> None:
    """rank() es determinista: misma entrada → misma lista de VariationScore."""
    variations = [
        {"idx": i, "seed": i, "params": {}, "marca": "x", "asset_type": "logo"} for i in range(3)
    ]
    r1 = rank(variations, high_contrast_pngs, top_n=8)
    r2 = rank(variations, high_contrast_pngs, top_n=8)
    assert len(r1) == len(r2)
    for s1, s2 in zip(r1, r2, strict=True):
        assert s1.idx == s2.idx
        assert s1.dhash == s2.dhash
        assert s1.final_score == s2.final_score


def test_isotype_same_params_same_svg() -> None:
    """generate_isotype es determinista: mismos params → SVG byte-idéntico."""
    params = IsotypeParams(
        seed=7,
        style="enclosure",
        brand_initials="M",
        brand_symbol="◆",
        primary_color="#112233",
        accent_color="#445566",
        bg_color="#778899",
        size=256,
    )
    s1 = generate_isotype(params)
    s2 = generate_isotype(params)
    assert s1 == s2


# ===========================================================================
# 6. Edge cases + multi-tenant isolation
# ===========================================================================


def test_axes_validate_empty_combination_ok(axes: AxesConfig) -> None:
    """Combinación vacía {} es válida (no requiere ejes específicos)."""
    axes.validate_combination({})


def test_axes_validate_extra_keys_rejected(axes: AxesConfig) -> None:
    """Validar con keys desconocidas en la combinación es rechazado."""
    with pytest.raises(ValueError, match="Unknown axis"):
        axes.validate_combination({"unknown_axis_xyz": "value"})


def test_rank_handles_missing_optional_pngs(tmp_path: Path) -> None:
    """rank() salta variaciones sin PNG pero incluye las que sí tienen archivo."""
    d = tmp_path / "mix"
    d.mkdir()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(d / "combo_000.png")
    # combo_001.png no existe
    variations = [
        {"idx": 0, "seed": 1, "params": {}, "marca": "x", "asset_type": "logo"},
        {"idx": 1, "seed": 2, "params": {}, "marca": "x", "asset_type": "logo"},
    ]
    ranked = rank(variations, d, top_n=8)
    # Solo la variación 0 (con PNG) sobrevive
    assert len(ranked) == 1
    assert ranked[0].idx == 0


def test_rank_with_solid_color_pngs_collapses(tmp_path: Path) -> None:
    """PNGs de color sólido tienen dHash todo-0 → dedup los colapsa en 1."""
    d = tmp_path / "solid"
    d.mkdir()
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        Image.new("RGB", (64, 64), color).save(d / f"combo_{i:03d}.png")
    variations = [
        {"idx": i, "seed": i, "params": {}, "marca": "x", "asset_type": "logo"} for i in range(3)
    ]
    ranked = rank(variations, d, top_n=8, dedup_distance_threshold=20)
    # Solid colors → todos con dHash 0000... → dedup deja solo 1
    assert len(ranked) == 1


def test_wizard_axes_returns_catalog(client: TestClient) -> None:
    """GET /api/v1/wizard/axes devuelve el catálogo completo de ejes."""
    _register(client, "acme", "owner@acme.com")
    r = client.get("/api/v1/wizard/axes")
    assert r.status_code == 200
    axes_payload = r.json()["axes"]
    names = {a["name"] for a in axes_payload}
    assert {"palette_scheme", "layout", "isotype_style"}.issubset(names)
    # Cada eje expone label, type y al menos una opción con name
    for axis in axes_payload:
        assert axis["label"]
        assert axis["type"] in {"enum", "string", "int"}
        assert axis["options"]
        for opt in axis["options"]:
            assert opt["name"]


def test_wizard_axes_tenant_isolation(app: FastAPI) -> None:
    """El catálogo de ejes es global (mismo para todos los tenants), pero
    autenticado: tenants no ven el catálogo del otro, solo el compartido.
    """
    client_a = TestClient(app)
    client_b = TestClient(app)
    _register(client_a, "alpha", "a@alpha.com")
    _register(client_b, "beta", "b@beta.com")
    r_a = client_a.get("/api/v1/wizard/axes")
    r_b = client_b.get("/api/v1/wizard/axes")
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    # Ambos ven el MISMO catálogo global (no hay scoping por tenant)
    assert r_a.json()["axes"] == r_b.json()["axes"]


def test_wizard_axes_unauthenticated_is_401(client: TestClient) -> None:
    """El catálogo requiere autenticación (no se filtra a anónimos)."""
    r = client.get("/api/v1/wizard/axes")
    assert r.status_code == 401


def test_batch_isotipo_unknown_axis_returns_422(client: TestClient) -> None:
    """POST /api/v1/batches rechaza ejes permutados desconocidos."""
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    r = client.post(
        "/api/v1/batches",
        json={"brand_id": bid, "permuted": ["no_such_axis"], "count": 1},
    )
    assert r.status_code == 422


def test_batch_invalid_combination_returns_422(client: TestClient) -> None:
    """POST /api/v1/batches rechaza fixed con opción no declarada en el eje."""
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    r = client.post(
        "/api/v1/batches",
        json={"brand_id": bid, "fixed": {"palette_scheme": "bogus"}, "count": 1},
    )
    assert r.status_code == 422


def test_batch_count_over_universe_returns_422(client: TestClient) -> None:
    """POST /api/v1/batches rechaza count > universo cartesiano de permutaciones."""
    _register(client, "acme", "owner@acme.com")
    bid = _create_brand(client)
    # palette_scheme tiene 6 opciones; count=100 > 6 → plan_combinations falla → 422
    r = client.post(
        "/api/v1/batches",
        json={
            "brand_id": bid,
            "asset_types": ["isotipo"],
            "permuted": ["palette_scheme"],
            "count": 100,
        },
    )
    assert r.status_code == 422


def test_batch_tenant_isolation_batch_not_found(app: FastAPI) -> None:
    """Tenant B no puede ver el batch de tenant A (404)."""
    client_a = TestClient(app)
    client_b = TestClient(app)
    _register(client_a, "alpha", "a@alpha.com")
    _register(client_b, "beta", "b@beta.com")
    bid = _create_brand(client_a)
    r_create = client_a.post(
        "/api/v1/batches",
        json={
            "brand_id": bid,
            "asset_types": ["isotipo"],
            "permuted": ["palette_scheme"],
            "count": 1,
        },
    )
    assert r_create.status_code == 202
    batch_id = int(r_create.json()["id"])
    # B no ve el batch de A
    assert client_b.get(f"/api/v1/batches/{batch_id}").status_code == 404
    assert client_b.get(f"/api/v1/batches/{batch_id}/variations").status_code == 404


@pytest.mark.integration
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
def test_render_combination_isotipo_template_via_api(app: FastAPI) -> None:
    """E2E mínimo: render real de una combinación isotipo y verificación de PNG."""
    with TestClient(app) as c:
        _register(c, "studio", "s@studio.com")
        bid = _create_brand(c, "pinakotheke-kosmos", "Kósmos")
        r = c.post(
            "/api/v1/batches",
            json={
                "brand_id": bid,
                "asset_types": ["isotipo"],
                "permuted": ["palette_scheme"],
                "count": 1,
                "seed_salt": "coverage-e2e",
            },
        )
        assert r.status_code == 202
        batch_id = int(r.json()["id"])
        # Esperar a que complete (timeout corto)
        import time as _t

        deadline = _t.time() + 60
        status = ""
        while _t.time() < deadline:
            rr = c.get(f"/api/v1/batches/{batch_id}")
            status = str(rr.json().get("status", ""))
            if status in {"completed", "failed", "cancelled"}:
                break
            _t.sleep(0.5)
        assert status == "completed", f"batch no completó: status={status}"
        # Verificar que hay al menos una variación con PNG
        rv = c.get(f"/api/v1/batches/{batch_id}/variations")
        assert rv.status_code == 200
        items = rv.json()["items"]
        assert items, "esperaba >=1 variación"
        # La primera variación es descargable como PNG
        file_url = items[0]["file_url"]
        rf = c.get(file_url)
        assert rf.status_code == 200
        assert rf.headers["content-type"] == "image/png"
        assert len(rf.content) > 100
