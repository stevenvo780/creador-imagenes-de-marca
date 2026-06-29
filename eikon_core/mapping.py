from __future__ import annotations

from typing import Any

from .brand import brand_family
from .constants import DEFAULT_LOCALE
from .text import apply_text_limits


def map_marca_to_vars(
    marca: dict[str, Any],
    tipo: str,
    locale: str = DEFAULT_LOCALE,
    variant_name: str = "",
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
    return vars_dict
