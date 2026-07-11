from __future__ import annotations

import colorsys
import re
import sys
from collections.abc import Mapping
from typing import Any

from .brand import brand_family
from .constants import DEFAULT_LOCALE
from .text import apply_text_limits

WCAG_AA_CONTRAST = 4.5
FONT_FALLBACK = "Inter"
FONT_WHITELIST = frozenset(
    {
        "Inter",
        "Playfair Display",
        "Space Grotesk",
        "JetBrains Mono",
        "Cormorant Garamond",
    }
)

COLOR_KEYS = ("bg", "primario", "acento", "acento_2", "texto")
BASE_COLOR_FALLBACKS = {
    "bg": "#0b1417",
    "primario": "#0b1417",
    "acento": "#43b5a6",
    "acento_2": "#8d7cc0",
    "texto": "#e8e0d4",
}

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
HEX_IN_TEXT_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_hue(hue: float) -> float:
    return hue % 360.0


def _normalize_hex_color(hex_color: str) -> str:
    value = hex_color.strip()
    if not HEX_COLOR_RE.fullmatch(value):
        msg = f"Expected hex color #RRGGBB or #RGB, got {hex_color!r}"
        raise ValueError(msg)

    digits = value[1:]
    if len(digits) == 3:
        digits = "".join(channel * 2 for channel in digits)
    return f"#{digits.lower()}"


def _extract_hex_color(value: str) -> str | None:
    match = HEX_IN_TEXT_RE.search(value.strip())
    if not match:
        return None
    try:
        return _normalize_hex_color(match.group(0))
    except ValueError:
        return None


def _normalize_color_value(value: str, fallback: str, warn_on_fallback: bool = False) -> str:
    """Normaliza valor de color a hex válido, con fallback.

    Si warn_on_fallback=True, emite WARN a stderr cuando se usa fallback.
    """
    try:
        return _normalize_hex_color(value)
    except ValueError:
        extracted = _extract_hex_color(value)
        if extracted:
            return extracted
    # Fallback necesario
    if warn_on_fallback and value and value.strip():
        print(
            f"[eikon mapping] Color inválido {value!r}; usando fallback {fallback!r}.",
            file=sys.stderr,
        )
    return _normalize_hex_color(fallback)


def _is_plain_hex(value: str) -> bool:
    try:
        _normalize_hex_color(value)
    except ValueError:
        return False
    return True


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    normalized = _normalize_hex_color(hex_color)
    return (
        int(normalized[1:3], 16),
        int(normalized[3:5], 16),
        int(normalized[5:7], 16),
    )


def hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB to HSL: H [0-360], S/L [0-100]."""
    red, green, blue = _hex_to_rgb(hex_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    return hue * 360, saturation * 100, lightness * 100


def hsl_to_hex(h: float, s: float, l: float) -> str:  # noqa: E741
    """Convert HSL H [0-360], S/L [0-100] to #RRGGBB."""
    red, green, blue = colorsys.hls_to_rgb(
        _normalize_hue(h) / 360,
        _clamp(l, 0, 100) / 100,
        _clamp(s, 0, 100) / 100,
    )
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def _lightness_steps(start: float, end: float, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [start]
    step = (end - start) / (count - 1)
    return [start + (step * index) for index in range(count)]


def derive_tints(base_hex: str, count: int = 5) -> list[str]:
    """Derive light-to-dark tints preserving hue and saturation."""
    hue, saturation, _lightness = hex_to_hsl(base_hex)
    return [hsl_to_hex(hue, saturation, lightness) for lightness in _lightness_steps(92, 52, count)]


def derive_shades(base_hex: str, count: int = 5) -> list[str]:
    """Derive dark-to-light shades preserving hue and saturation."""
    hue, saturation, _lightness = hex_to_hsl(base_hex)
    return [hsl_to_hex(hue, saturation, lightness) for lightness in _lightness_steps(12, 52, count)]


def generate_harmonies(base_hex: str) -> dict[str, str]:
    """Generate deterministic HSL color harmonies for a base color."""
    hue, saturation, lightness = hex_to_hsl(base_hex)
    return {
        "complementary": hsl_to_hex(hue + 180, saturation, lightness),
        "analogous_left": hsl_to_hex(hue - 30, saturation, lightness),
        "analogous_right": hsl_to_hex(hue + 30, saturation, lightness),
        "triadic_1": hsl_to_hex(hue + 120, saturation, lightness),
        "triadic_2": hsl_to_hex(hue + 240, saturation, lightness),
    }


def _relative_luminance(hex_color: str) -> float:
    red, green, blue = _hex_to_rgb(hex_color)
    channels = []
    for channel in (red, green, blue):
        srgb = channel / 255
        linear = srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4
        channels.append(linear)
    return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])


def wcag_contrast_ratio(hex_color1: str, hex_color2: str) -> float:
    """Return WCAG relative contrast ratio, from 1 to 21."""
    luminance1 = _relative_luminance(hex_color1)
    luminance2 = _relative_luminance(hex_color2)
    lighter = max(luminance1, luminance2)
    darker = min(luminance1, luminance2)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_adjust_luminosity(
    fg_hex: str,
    bg_hex: str,
    target_ratio: float = WCAG_AA_CONTRAST,
) -> str:
    """Adjust foreground HSL lightness until it reaches the target WCAG contrast."""
    normalized_fg = _normalize_hex_color(fg_hex)
    normalized_bg = _normalize_hex_color(bg_hex)
    if wcag_contrast_ratio(normalized_fg, normalized_bg) >= target_ratio:
        return normalized_fg

    hue, saturation, lightness = hex_to_hsl(normalized_fg)
    bg_luminance = _relative_luminance(normalized_bg)

    if bg_luminance >= 0.5:
        low = 0.0
        high = lightness
        for _index in range(28):
            middle = (low + high) / 2
            candidate = hsl_to_hex(hue, saturation, middle)
            if wcag_contrast_ratio(candidate, normalized_bg) >= target_ratio:
                low = middle
            else:
                high = middle
        adjusted = hsl_to_hex(hue, saturation, low)
    else:
        low = lightness
        high = 100.0
        for _index in range(28):
            middle = (low + high) / 2
            candidate = hsl_to_hex(hue, saturation, middle)
            if wcag_contrast_ratio(candidate, normalized_bg) >= target_ratio:
                high = middle
            else:
                low = middle
        adjusted = hsl_to_hex(hue, saturation, high)

    if wcag_contrast_ratio(adjusted, normalized_bg) >= target_ratio:
        return adjusted

    endpoints = ("#000000", "#ffffff")
    return max(endpoints, key=lambda color: wcag_contrast_ratio(color, normalized_bg))


def validate_and_normalize_font(font_name: str) -> tuple[str, bool]:
    """Return a packaged font name, warning clearly when falling back."""
    normalized = font_name.strip().strip("\"'")
    if normalized in FONT_WHITELIST:
        return normalized, True

    print(
        "[eikon mapping] Fuente no empaquetada "
        f"{font_name!r}; usando fallback {FONT_FALLBACK!r}. "
        f"Permitidas: {', '.join(sorted(FONT_WHITELIST))}.",
        file=sys.stderr,
    )
    return FONT_FALLBACK, False


def _palette_hexes(result: Mapping[str, str]) -> dict[str, str]:
    return {
        key: _normalize_color_value(result.get(key, ""), BASE_COLOR_FALLBACKS[key])
        for key in COLOR_KEYS
    }


def _hsl_color(
    base: tuple[float, float, float], lightness: float, saturation_delta: float = 0
) -> str:
    hue, saturation, _base_lightness = base
    return hsl_to_hex(hue, _clamp(saturation + saturation_delta, 0, 100), lightness)


def _mix_hsl(left_hex: str, right_hex: str, ratio: float) -> str:
    left_hue, left_saturation, left_lightness = hex_to_hsl(left_hex)
    right_hue, right_saturation, right_lightness = hex_to_hsl(right_hex)
    clamped_ratio = _clamp(ratio, 0, 1)

    hue_delta = ((right_hue - left_hue + 540) % 360) - 180
    hue = _normalize_hue(left_hue + (hue_delta * clamped_ratio))
    saturation = left_saturation + ((right_saturation - left_saturation) * clamped_ratio)
    lightness = left_lightness + ((right_lightness - left_lightness) * clamped_ratio)
    return hsl_to_hex(hue, saturation, lightness)


def _palette_gradient(
    bg_hsl: tuple[float, float, float],
    primary_hsl: tuple[float, float, float],
    accent_hsl: tuple[float, float, float],
    accent_2_hsl: tuple[float, float, float],
) -> str:
    bg_stop = _hsl_color(bg_hsl, 7)
    primary_stop = _hsl_color(primary_hsl, 13)
    accent_stop = _hsl_color(accent_hsl, 27, 12)
    accent_2_stop = _hsl_color(accent_2_hsl, 34, 8)
    bridge = _mix_hsl(primary_stop, accent_stop, 0.48)
    angle = round(_normalize_hue((accent_hsl[0] + primary_hsl[0]) / 2))
    return (
        f"linear-gradient({angle}deg, {bg_stop} 0%, {primary_stop} 28%, "
        f"{bridge} 55%, {accent_stop} 78%, {accent_2_stop} 100%)"
    )


def _validate_palette_contrast(result: dict[str, str]) -> None:
    bg_hex = _extract_hex_color(result.get("bg", "")) or BASE_COLOR_FALLBACKS["bg"]
    if _is_plain_hex(result.get("bg", "")):
        result["bg"] = _normalize_hex_color(result["bg"])

    for key in ("texto", "primario", "acento"):
        current = _normalize_color_value(result.get(key, ""), BASE_COLOR_FALLBACKS[key])
        result[key] = wcag_adjust_luminosity(current, bg_hex, WCAG_AA_CONTRAST)

    result["acento_2"] = _normalize_color_value(
        result.get("acento_2", ""),
        BASE_COLOR_FALLBACKS["acento_2"],
    )


def _apply_palette_scheme(result: dict[str, str], scheme: str) -> None:
    """Apply palette_scheme overrides con lógica HSL real."""
    normalized_scheme = scheme.strip().lower()
    if normalized_scheme in ("", "brand"):
        return

    palette = _palette_hexes(result)
    bg_hsl = hex_to_hsl(palette["bg"])
    primary_hsl = hex_to_hsl(palette["primario"])
    accent_hsl = hex_to_hsl(palette["acento"])
    accent_2_hsl = hex_to_hsl(palette["acento_2"])
    text_hsl = hex_to_hsl(palette["texto"])

    if normalized_scheme == "mono":
        result["bg"] = _hsl_color(primary_hsl, 92)
        result["texto"] = _hsl_color(primary_hsl, 12)
        result["primario"] = _hsl_color(primary_hsl, 18)
        result["acento"] = _hsl_color(primary_hsl, 34)
        result["acento_2"] = _hsl_color(primary_hsl, 48)
    elif normalized_scheme == "light":
        result["bg"] = _hsl_color(bg_hsl, 92)
        result["texto"] = _hsl_color(primary_hsl, 12)
        result["primario"] = _hsl_color(primary_hsl, 18)
        result["acento"] = _hsl_color(
            accent_hsl,
            _clamp(accent_hsl[2] + 15, 18, 82),
            -15,
        )
        result["acento_2"] = _hsl_color(
            accent_2_hsl,
            _clamp(accent_2_hsl[2] + 12, 20, 86),
            -10,
        )
    elif normalized_scheme == "dark":
        result["bg"] = _hsl_color(bg_hsl, 8)
        result["texto"] = _hsl_color(text_hsl, 92)
        result["primario"] = _hsl_color(primary_hsl, 82)
        result["acento"] = _hsl_color(accent_hsl, 58, 18)
        result["acento_2"] = _hsl_color(accent_2_hsl, 66, 12)
    elif normalized_scheme == "deep":
        result["bg"] = _hsl_color(bg_hsl, 4)
        result["texto"] = _hsl_color(text_hsl, 94)
        result["primario"] = _hsl_color(primary_hsl, 86, 12)
        result["acento"] = _hsl_color(accent_hsl, 62, 28)
        result["acento_2"] = _hsl_color(accent_2_hsl, 70, 20)
    elif normalized_scheme == "accent_bg":
        text_hex = palette["texto"]
        text_is_light = _relative_luminance(text_hex) >= 0.5
        target_bg_lightness = 22 if text_is_light else 88
        accent_bg = _hsl_color(accent_hsl, target_bg_lightness, -(accent_hsl[1] / 2))
        result["bg"] = wcag_adjust_luminosity(accent_bg, text_hex, WCAG_AA_CONTRAST)
        bg_is_light = _relative_luminance(result["bg"]) >= 0.5
        result["texto"] = wcag_adjust_luminosity(text_hex, result["bg"], WCAG_AA_CONTRAST)
        result["primario"] = _hsl_color(primary_hsl, 16 if bg_is_light else 86)
        result["acento"] = _hsl_color(accent_hsl, 26 if bg_is_light else 70, 12)
        result["acento_2"] = _hsl_color(accent_2_hsl, 34 if bg_is_light else 78, 8)
    elif normalized_scheme == "gradient":
        result["grad_hero"] = _palette_gradient(bg_hsl, primary_hsl, accent_hsl, accent_2_hsl)
        result["bg"] = result["grad_hero"]
        result["texto"] = _hsl_color(text_hsl, 92)
        result["primario"] = _hsl_color(primary_hsl, 82)
        result["acento"] = _hsl_color(accent_hsl, 58, 18)
        result["acento_2"] = _hsl_color(accent_2_hsl, 66, 12)
    else:
        return

    _validate_palette_contrast(result)


def _apply_density_scale(result: dict[str, str], scale: str) -> None:
    """Apply density_scale overrides."""
    if scale == "compact":
        result["font_size_scale"] = "0.85"
        result["space_scale"] = "0.85"
    elif scale == "spacious":
        result["font_size_scale"] = "1.15"
        result["space_scale"] = "1.15"
    else:  # normal
        result["font_size_scale"] = "1"
        result["space_scale"] = "1"


def _apply_corner_shape(result: dict[str, str], shape: str) -> None:
    """Apply corner_shape overrides."""
    if shape == "sharp":
        result["corner_radius"] = "0"
    elif shape == "rounded":
        result["corner_radius"] = "14px"
    elif shape == "pill":
        result["corner_radius"] = "999px"


def _apply_typography_pairing(result: dict[str, str], pairing: str) -> None:
    """Apply typography_pairing overrides.

    Las familias referenciadas se empaquetan como woff2 en templates/fonts/ y se
    declaran via @font-face en templates/eikon-system.css, de modo que un pairing
    distinto al de la marca cambia de forma visible y determinista la fuente
    renderizada (sin depender de fuentes del sistema).
    """
    if pairing == "sans_serif":
        result["font_titulo"] = "Inter"
        result["font_cuerpo"] = "Inter"
    elif pairing == "serif_modern":
        result["font_titulo"] = "Playfair Display"
        result["font_cuerpo"] = "Inter"
    elif pairing == "display":
        result["font_titulo"] = "Playfair Display"
        result["font_cuerpo"] = "Playfair Display"
    elif pairing == "geometric_sans":
        result["font_titulo"] = "Space Grotesk"
        result["font_cuerpo"] = "Inter"


def apply_combination_overrides(
    vars_dict: dict[str, str],
    combination_params: dict[str, str] | None = None,
) -> dict[str, str]:
    """Apply combination parameter overrides to a vars_dict.

    Args:
        vars_dict: Base variables dictionary
        combination_params: Optional combination parameters to apply

    Returns:
        Updated vars_dict with overrides applied
    """
    if not combination_params:
        return vars_dict

    result = dict(vars_dict)

    # Apply palette_scheme overrides
    if "palette_scheme" in combination_params:
        _apply_palette_scheme(result, combination_params["palette_scheme"])

    # Apply density scale
    if "density_scale" in combination_params:
        _apply_density_scale(result, combination_params["density_scale"])

    # Apply corner radius
    if "corner_shape" in combination_params:
        _apply_corner_shape(result, combination_params["corner_shape"])

    # Apply typography pairing
    if "typography_pairing" in combination_params:
        _apply_typography_pairing(result, combination_params["typography_pairing"])

    return result


def wcag_adjust(vars_dict: dict[str, str]) -> dict[str, str]:
    """Normalize palette hex values and enforce WCAG AA contrast before rendering."""
    result = dict(vars_dict)
    bg_raw = result.get("bg", "")
    bg_hex = _extract_hex_color(bg_raw) or BASE_COLOR_FALLBACKS["bg"]

    if _is_plain_hex(bg_raw):
        result["bg"] = _normalize_hex_color(bg_raw)

    for key in ("texto", "primario", "acento"):
        color = _normalize_color_value(result.get(key, ""), BASE_COLOR_FALLBACKS[key])
        result[key] = wcag_adjust_luminosity(color, bg_hex, WCAG_AA_CONTRAST)

    result["acento_2"] = _normalize_color_value(
        result.get("acento_2", ""),
        BASE_COLOR_FALLBACKS["acento_2"],
    )
    return result


def _normalize_fonts(vars_dict: dict[str, str]) -> None:
    title_font, _title_is_valid = validate_and_normalize_font(vars_dict.get("font_titulo", ""))
    body_font, _body_is_valid = validate_and_normalize_font(vars_dict.get("font_cuerpo", ""))
    vars_dict["font_titulo"] = title_font
    vars_dict["font_cuerpo"] = body_font


def _dict_value(source: Mapping[str, Any], key: str) -> dict[str, Any]:
    raw_value = source.get(key)
    if not isinstance(raw_value, dict):
        return {}
    return {str(raw_key): raw_item for raw_key, raw_item in raw_value.items()}


def _textos_for_tipo(marca: Mapping[str, Any], tipo: str) -> dict[str, Any]:
    textos_container = _dict_value(marca, "textos")
    raw_textos = textos_container.get(tipo, {})
    if isinstance(raw_textos, list):
        raw_textos = raw_textos[0] if raw_textos else {}
    if not isinstance(raw_textos, dict):
        return {}
    return {str(raw_key): raw_item for raw_key, raw_item in raw_textos.items()}


def map_marca_to_vars(
    marca: dict[str, Any],
    tipo: str,
    locale: str = DEFAULT_LOCALE,
    variant_name: str = "",
    combination_params: dict[str, str] | None = None,
) -> dict[str, str]:
    family = brand_family(marca)
    paleta = _dict_value(marca, "paleta")

    defaults = {
        "bg": "#0c0e10" if family == "prizma" else "#0b1417",
        "primario": "#0c0e10" if family == "prizma" else "#0b1417",
        "acento": "#f0b94a" if family == "prizma" else "#43b5a6",
        "acento_2": "#d4622e" if family == "prizma" else "#8d7cc0",
        "texto": "#f0ece6" if family == "prizma" else "#e8e0d4",
        "font_titulo_name": "Inter" if family == "prizma" else "Playfair Display",
    }

    tipografia = _dict_value(marca, "tipografia")
    logo_simbolo = str(
        marca.get("logo_simbolo") or marca.get("simbolo") or ("⚡" if family == "prizma" else "∞")
    ).strip()
    logo_texto = str(
        marca.get("logo_texto")
        or marca.get("nombre_producto")
        or marca.get("nombre_corporativo")
        or ""
    ).strip()

    textos = _textos_for_tipo(marca, tipo)
    titulo = str(textos.get("titulo") or marca.get("nombre_producto") or "").strip()
    subtitulo = str(textos.get("subtitulo") or marca.get("tagline") or "").strip()
    copy = str(textos.get("copy") or "").strip()
    url = str(marca.get("url_producto") or marca.get("url") or "").strip()

    vars_dict = {
        "bg": str(paleta.get("bg") or defaults["bg"]),
        "primario": str(paleta.get("primario") or defaults["primario"]),
        "acento": str(paleta.get("acento") or defaults["acento"]),
        "acento_2": str(paleta.get("acento_2") or defaults["acento_2"]),
        "texto": str(paleta.get("texto") or defaults["texto"]),
        "font_titulo": str(tipografia.get("titulos") or defaults["font_titulo_name"]),
        "font_cuerpo": str(tipografia.get("cuerpo") or "Inter"),
        "logo_simbolo": logo_simbolo,
        "logo_texto": logo_texto,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "copy": copy,
        "url": url,
        "variant": variant_name,
        "numero": str(textos.get("numero", "22")),
        "etiqueta": str(textos.get("etiqueta", "Simulaciones")),
        "numero_2": str(textos.get("numero_2", "16")),
        "etiqueta_2": str(textos.get("etiqueta_2", "Repositorios")),
    }

    _vl = variant_name.lower()
    if _vl:
        if any(k in _vl for k in ("mono",)):
            old_bg = vars_dict["bg"]
            old_texto = vars_dict["texto"]
            old_primario = vars_dict["primario"]
            vars_dict["bg"] = old_texto
            vars_dict["texto"] = old_primario
            vars_dict["primario"] = old_bg
        elif any(k in _vl for k in ("inverse", "dark", "_dark")):
            vars_dict["bg"] = vars_dict["primario"]
            vars_dict["texto"] = str(paleta.get("texto") or defaults["texto"])
        elif any(k in _vl for k in ("light",)):
            vars_dict["bg"] = str(paleta.get("texto") or defaults["texto"])
            vars_dict["texto"] = str(paleta.get("primario") or defaults["primario"])
        if "stat_card" in tipo:
            # Cloud Atlas stat_card variants
            if "v1_hero_num" in _vl:
                pass
            elif "v2_dual_stat" in _vl:
                vars_dict["etiqueta_2"] = "Repos"
                vars_dict["numero_2"] = "16"
            elif "v3_graph_abstract" in _vl:
                vars_dict["etiqueta"] = "Tendencia"
            # Prizma stat_card variants
            elif "v1_big_data" in _vl:
                # Hero metric: keep defaults, but ensure distinctiveness
                vars_dict["numero"] = vars_dict.get("numero", "22")
                vars_dict["etiqueta"] = "Big data · KPI"
            elif "v2_comparativa" in _vl:
                # Comparative: adjust labels for two-metric layout
                vars_dict["numero"] = "72"
                vars_dict["etiqueta"] = "Actual"
                vars_dict["numero_2"] = "80"
                vars_dict["etiqueta_2"] = "Objetivo"
            elif "v3_uptime" in _vl:
                # Uptime gauge: adjust for service metrics display
                vars_dict["numero"] = "99.3"
                vars_dict["etiqueta"] = "% uptime"
                vars_dict["numero_2"] = "30"
                vars_dict["etiqueta_2"] = "días"

    vars_dict = apply_text_limits(tipo, vars_dict)

    # Apply combination overrides last (highest priority)
    if combination_params:
        vars_dict = apply_combination_overrides(vars_dict, combination_params)

    _normalize_fonts(vars_dict)
    return wcag_adjust(vars_dict)
