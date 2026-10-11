"""Contrato del perfil explícito Humanizar y sus límites de variación."""

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from eikon_core.brand import brand_family
from eikon_core.injection import injection_script
from eikon_core.mapping import apply_combination_overrides, map_marca_to_vars, wcag_contrast_ratio
from eikon_core.render import _build_isotype_data_uri


def _brand(metadata_key="textos", **extra):
    return {
        "slug": "producto-independiente",
        "nombre_producto": "Cauce V3",
        metadata_key: {"brand_family": "humanizar"},
        **extra,
    }


@pytest.mark.parametrize("metadata_key", ["textos", "texts"])
def test_family_requires_explicit_brand_metadata(metadata_key):
    assert brand_family(_brand(metadata_key)) == "humanizar"
    assert brand_family({"slug": "humanizar", "tenant_id": 17}) == "cloud_atlas"
    assert brand_family({"slug": "prizma-iris"}) == "prizma"
    assert brand_family({"slug": "producto", "textos": {"brand_family": "other"}}) == "cloud_atlas"


def test_common_identity_overrides_product_base_without_mutating_original():
    brand = _brand(
        paleta={"bg": "#ff00ff", "primario": "#00ff00", "texto": "#ffff00", "acento": "#2563eb"},
        tipografia={"titulos": "Playfair Display", "cuerpo": "Inter"},
        logo_asset="marcas/producto/logo.svg",
    )
    original = deepcopy(brand)
    result = map_marca_to_vars(brand, "ig_post")
    assert (result["bg"], result["primario"], result["texto"]) == ("#fcfafd", "#29252d", "#29252d")
    assert (result["font_titulo"], result["font_cuerpo"]) == ("Manrope", "Manrope")
    assert result["acento"] == "#a63836"
    assert result["brand_coral"] == "#f46f65"
    assert result["surface_secondary"] == "#eae1f5"
    assert result["acento_2"] == "#2563eb"
    assert result["logo_simbolo"] == ""
    assert result["logo_texto"] == "Cauce V3"
    assert brand == original


@pytest.mark.parametrize(
    "scheme", ["brand", "mono", "light", "dark", "deep", "accent_bg", "gradient"]
)
def test_client_second_override_cannot_diversify_family(scheme):
    initial = map_marca_to_vars(_brand(), "ig_post")
    result = apply_combination_overrides(
        initial,
        {
            "palette_scheme": scheme,
            "typography_pairing": "serif_modern",
            "density_scale": "compact",
            "corner_shape": "sharp",
        },
    )
    expected_bg = "#111319" if scheme in {"dark", "deep"} else "#fcfafd"
    assert result["bg"] == expected_bg
    assert result["font_titulo"] == result["font_cuerpo"] == "Manrope"
    assert result["font_size_scale"] == result["space_scale"] == "1"
    assert result["corner_radius"] == "20px"
    assert "grad_hero" not in result
    for role in ("texto", "primario", "acento", "product_accent_text"):
        assert wcag_contrast_ratio(result[role], result["bg"]) >= 4.5


@pytest.mark.parametrize(
    "variant", ["", "v1_color", "v2_mono", "v3_light", "v4_dark", "v5_inverse"]
)
def test_variant_is_deterministic_and_retains_verified_layout_contract(variant):
    brand = _brand(paleta={"acento": "#fefefe"})
    result = map_marca_to_vars(brand, "ig_post", variant_name=variant)
    assert result == map_marca_to_vars(brand, "ig_post", variant_name=variant)
    assert result["grid_columns_mobile"] == "4"
    assert result["grid_columns_tablet"] == "8"
    assert result["grid_columns_desktop"] == "12"
    assert result["spacing_unit"] == "4px"
    assert float(result["logo_clearance_ratio"]) == 1 / 8
    assert result["acento_2"] == "#fefefe"  # Solo decoración, nunca texto sin ajuste.
    assert wcag_contrast_ratio(result["product_accent_text"], result["bg"]) >= 4.5
    assert wcag_contrast_ratio(result["texto"], result["bg"]) >= 4.5


def test_no_family_state_leaks_to_other_brands_or_tenants():
    legacy = {"slug": "independent-brand", "tenant_id": 22}
    before = map_marca_to_vars(legacy, "ig_post")
    map_marca_to_vars(
        _brand(tenant_id=17), "ig_post", combination_params={"palette_scheme": "dark"}
    )
    after = map_marca_to_vars(legacy, "ig_post")
    assert before == after
    assert after["font_titulo"] == "Playfair Display"
    assert after["logo_simbolo"] == "∞"
    assert "brand_family" not in after
    prizma = map_marca_to_vars({"slug": "prizma-iris"}, "ig_post")
    assert prizma["logo_simbolo"] == "⚡"
    assert prizma["font_titulo"] == "Inter"


def test_invalid_product_accent_cannot_escape_color_contract():
    result = map_marca_to_vars(_brand(paleta={"acento": "url(https://invalid.example)"}), "ig_post")
    assert result["acento_2"] == "#eae1f5"
    assert result["product_accent_text"] == "#29252d"


def test_social_template_consumes_render_profile_and_retains_legacy_fallbacks():
    """Contrato CSS real: los valores inyectados llegan a las declaraciones."""
    template = (Path(__file__).resolve().parents[1] / "templates/social_4x5.html").read_text()
    style = template.split("<style>")[1].split("</style>")[0]
    script = injection_script(map_marca_to_vars(_brand(), "social_4x5"))
    payload = json.loads(re.search(r"const __e = (.*);", script).group(1))
    css = payload["css"]

    # Sustituir las variables simples exactamente como las usa la hoja; no basta
    # comprobar que el perfil contiene claves que el renderer nunca aplica.
    def resolved(rule):
        value = re.search(rule, style).group(1)
        return re.sub(r"var\((--[\w-]+),([^()]*)\)", lambda m: css.get(m[1], m[2]), value)

    assert resolved(r"body\{\s*font-family:([^;]+)") == "Manrope,system-ui,sans-serif"
    assert resolved(r"padding:(var\(--safe_margin_y[^;]+)") == "96px 96px"
    assert resolved(r"\.head\{[^}]*gap:([^;]+)") == "32px"
    assert resolved(r"\.sub\{[^}]*color:([^;]+)") == "#29252d"
    assert resolved(r"\.tag\{[^}]*color:([^;]+)") == "#29252d"
    assert resolved(r"\.tile:empty\{display:([^}]+)") == "none"
    assert resolved(r"body\{[^}]*display:([^;]+)") == "grid"
    assert css["--grid_template_columns"] == "repeat(12,minmax(0,1fr))"
    assert "grid-template-columns:var(--grid_template_columns,none)" in style
    assert "grid-column:var(--content_grid_span,auto)" in style
    assert css["--content_grid_span"] == "1 / -1"
    assert resolved(r"\.tile img[^}]*object-fit:([^}]+)") == "contain"
    assert css["--logo_clearance"] == "16.5px"
    assert css["--display_weight"] == "720"
    assert "font-weight:var(--display_weight,900)" in style
    assert "padding:var(--logo_clearance,0px)" in style

    legacy = injection_script(map_marca_to_vars({"slug": "old"}, "social_4x5"))
    legacy_css = json.loads(re.search(r"const __e = (.*);", legacy).group(1))["css"]
    assert "--safe_margin_y" not in legacy_css
    assert "--text_secondary" not in legacy_css
    assert "var(--safe_margin_y,104px) var(--safe_margin_x,96px)" in style


@pytest.mark.parametrize(
    "identity",
    [{}, {"logo_style": "none", "logo_seed": 0}, {"logo_style": "orbital", "logo_seed": None}],
)
def test_shared_isotype_helper_does_not_invent_missing_family_identity(identity):
    marca = _brand(**identity)
    assert (
        _build_isotype_data_uri("orbital", "00000000", marca, map_marca_to_vars(marca, "ig_post"))
        is None
    )


def test_shared_isotype_helper_retains_explicit_seed_zero_identity():
    marca = _brand(logo_style="orbital", logo_seed=0)
    mapped = map_marca_to_vars(marca, "ig_post")
    first = _build_isotype_data_uri("orbital", "00000000", marca, mapped)
    second = _build_isotype_data_uri("orbital", "00000000", marca, mapped)
    assert first and first.startswith("data:image/svg+xml;base64,")
    assert first == second


def test_partial_override_retains_previous_dark_family_mode():
    result = map_marca_to_vars(
        _brand(), "social_4x5", combination_params={"palette_scheme": "dark"}
    )
    updated = apply_combination_overrides(result, {"typography_pairing": "display"})
    assert updated["bg"] == "#111319"
    assert updated["font_titulo"] == "Manrope"
