from __future__ import annotations

from typing import Any

from .brand import brand_family
from .constants import DEFAULT_LOCALE
from .text import apply_text_limits


def _apply_palette_scheme(result: dict[str, str], scheme: str) -> None:
    """Apply palette_scheme overrides."""
    if scheme == "mono":
        result["acento"] = result["texto"]
        result["acento_2"] = result["texto"]
        result["bg"] = result["texto"]
        result["texto"] = result["primario"]
    elif scheme == "light":
        result["bg"] = result["texto"]
        result["texto"] = result["primario"]
    elif scheme == "dark":
        result["bg"] = result["primario"]
    elif scheme == "accent_bg":
        result["bg"] = result["acento"]
        result["texto"] = result["primario"]
    elif scheme == "gradient":
        result["bg"] = result.get("grad_hero", result["bg"])


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


def map_marca_to_vars(
    marca: dict[str, Any],
    tipo: str,
    locale: str = DEFAULT_LOCALE,
    variant_name: str = "",
    combination_params: dict[str, str] | None = None,
) -> dict[str, str]:
    family = brand_family(marca)
    paleta = marca.get("paleta", {}) if isinstance(marca.get("paleta"), dict) else {}

    defaults = {
        "bg": "#0c0e10" if family == "prizma" else "#0b1417",
        "primario": "#0c0e10" if family == "prizma" else "#0b1417",
        "acento": "#f0b94a" if family == "prizma" else "#43b5a6",
        "acento_2": "#d4622e" if family == "prizma" else "#8d7cc0",
        "texto": "#f0ece6" if family == "prizma" else "#e8e0d4",
        "font_titulo_name": "Inter" if family == "prizma" else "Playfair Display",
    }

    tipografia = marca.get("tipografia", {}) if isinstance(marca.get("tipografia"), dict) else {}
    logo_simbolo = str(
        marca.get("logo_simbolo") or marca.get("simbolo") or ("⚡" if family == "prizma" else "∞")
    ).strip()
    logo_texto = str(
        marca.get("logo_texto")
        or marca.get("nombre_producto")
        or marca.get("nombre_corporativo")
        or ""
    ).strip()

    textos = marca.get("textos", {}).get(tipo, {})
    if isinstance(textos, list):
        textos = textos[0] if textos else {}
    if not isinstance(textos, dict):
        textos = {}

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
        "font_titulo": tipografia.get("titulos") or defaults["font_titulo_name"],
        "font_cuerpo": tipografia.get("cuerpo") or "Inter",
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
            vars_dict["bg"] = vars_dict["texto"]
            vars_dict["texto"] = vars_dict["primario"]
            vars_dict["primario"] = vars_dict["texto"]
        elif any(k in _vl for k in ("inverse", "dark", "_dark")):
            vars_dict["bg"] = vars_dict["primario"]
            vars_dict["texto"] = str(paleta.get("texto") or defaults["texto"])
        elif any(k in _vl for k in ("light",)):
            vars_dict["bg"] = str(paleta.get("texto") or defaults["texto"])
            vars_dict["texto"] = str(paleta.get("primario") or defaults["primario"])
        if "stat_card" in tipo:
            if "v1_hero_num" in _vl:
                pass
            elif "v2_dual_stat" in _vl:
                vars_dict["etiqueta_2"] = "Repos"
                vars_dict["numero_2"] = "16"
            elif "v3_graph_abstract" in _vl:
                vars_dict["etiqueta"] = "Tendencia"

    vars_dict = apply_text_limits(tipo, vars_dict)

    # Apply combination overrides last (highest priority)
    if combination_params:
        vars_dict = apply_combination_overrides(vars_dict, combination_params)

    return vars_dict
