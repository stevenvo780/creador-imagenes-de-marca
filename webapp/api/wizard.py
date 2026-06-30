"""Router del wizard: catálogo de ejes combinatorios, brands y tipos de asset.

Alimenta el formulario del SPA: qué ejes existen, sus opciones/labels, los
brands del tenant disponibles como base de un batch, y el catálogo de familias
de asset con labels en español derivados de config/taxonomy.json.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from eikon_core.constants import ROOT
from webapp.storage import list_brands

from .deps import current_user, get_axes_config, get_settings
from .serializers import brand_to_dict

router = APIRouter(prefix="/api/v1/wizard", tags=["wizard"])

# ── Labels en español para familias (categorías de asset) ─────────────────────

_FAMILY_META: dict[str, dict[str, str]] = {
    "logos": {
        "label": "Logos",
        "description": "Identificador principal de la marca: isotipo, lockup y wordmark",
    },
    "banners": {
        "label": "Banners",
        "description": "Imágenes de portada para redes sociales y sitio web",
    },
    "cards": {
        "label": "Tarjetas",
        "description": "Formatos cuadrados y rectangulares para posts e impresión",
    },
    "og": {
        "label": "OG / Meta",
        "description": "Imagen de previsualización al compartir el enlace en redes",
    },
    "stationery": {
        "label": "Papelería",
        "description": "Formatos de oficina: papel membretado, sobres y documentos",
    },
}

# ── Labels en español para cada tipo de asset ─────────────────────────────────

_TYPE_META: dict[str, dict[str, str]] = {
    # Logos
    "isotipo": {
        "label": "Símbolo / Isotipo",
        "description": "El ícono gráfico de la marca, sin texto",
    },
    "lockup_horizontal": {
        "label": "Logo horizontal",
        "description": "Símbolo y nombre de la marca dispuestos en horizontal",
    },
    "lockup_vertical": {
        "label": "Logo vertical",
        "description": "Símbolo arriba y nombre debajo",
    },
    "wordmark": {
        "label": "Wordmark (solo nombre)",
        "description": "El nombre de la marca como elemento tipográfico",
    },
    "favicon": {
        "label": "Favicon",
        "description": "Versión mínima del ícono para pestaña de navegador",
    },
    "watermark": {
        "label": "Marca de agua",
        "description": "Versión translúcida para aplicar sobre imágenes",
    },
    # Banners
    "linkedin_header": {
        "label": "Portada de LinkedIn",
        "description": "Portada para perfil o página de empresa en LinkedIn (1584x396 px)",
    },
    "twitter_header": {
        "label": "Portada de X / Twitter",
        "description": "Portada para perfil en X, antes Twitter (1500x500 px)",
    },
    "youtube_header": {
        "label": "Arte de canal YouTube",
        "description": "Imagen de cabecera del canal de YouTube (2560x1440 px)",
    },
    "web_hero_desktop": {
        "label": "Hero web",
        "description": "Imagen de cabecera para sitio web escritorio (1920x600 px)",
    },
    "ad_leaderboard": {
        "label": "Anuncio horizontal (leaderboard)",
        "description": "Banner publicitario estándar IAB (728x90 px)",
    },
    "ad_rectangle": {
        "label": "Anuncio rectangular (medium rectangle)",
        "description": "Banner publicitario mediano IAB (300x250 px)",
    },
    # Cards
    "business_card": {
        "label": "Tarjeta de presentación",
        "description": "Tarjeta de visita con anverso y reverso (1050x600 px)",
    },
    "stat_card": {
        "label": "Tarjeta de estadística",
        "description": "Post cuadrado con un dato o métrica destacada (1080x1080 px)",
    },
    # OG
    "og_general": {
        "label": "Imagen OG / Meta",
        "description": "Imagen que aparece al compartir el enlace en redes (1200x630 px)",
    },
    "og_product": {
        "label": "OG de producto",
        "description": "Imagen de previsualización específica de un producto (1200x630 px)",
    },
    # Stationery
    "letterhead": {
        "label": "Papel membretado",
        "description": "Hoja A4 con cabecera de la marca (2480x3508 px)",
    },
}

# Orden de aparición de las familias en el wizard
_FAMILY_ORDER = ["logos", "banners", "cards", "og", "stationery"]


@router.get("/axes")
def wizard_axes(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Catálogo de ejes: nombre, label, tipo y opciones (name + descripción)."""
    cfg = get_axes_config(request)
    axes: list[dict[str, Any]] = []
    for name in cfg.axis_names():
        axis = cfg.axes[name]
        axes.append(
            {
                "name": axis.name,
                "label": axis.label or axis.name,
                "type": axis.axis_type,
                "options": [
                    {
                        "name": opt.name,
                        "label": opt.description or opt.name,
                        "description": opt.description,
                    }
                    for opt in axis.options
                ],
            }
        )
    return {"axes": axes}


@router.get("/brands")
def wizard_brands(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Brands del tenant disponibles como base de un batch."""
    settings = get_settings(request)
    rows = list_brands(settings.sqlite_path, user["tenant_id"])
    return {"items": [brand_to_dict(r) for r in rows]}


@router.get("/asset-types")
def wizard_asset_types(
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Catálogo de familias de asset con tipos y labels en español.

    Lee config/taxonomy.json, unifica los tipos de todas las marcas/familias
    (cloud_atlas, prizma, …) y devuelve la estructura agrupada por categoría
    (logos, banners, cards, og, stationery) con labels en español.
    """
    taxonomy_path = ROOT / "config" / "taxonomy.json"
    try:
        raw = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"families": []}

    # Recolectar tipos por categoría (unión de todas las familias de marca)
    categories: dict[str, list[dict[str, Any]]] = {}
    for brand_family in raw.get("families", {}).values():
        for cat_id, cat in brand_family.get("categories", {}).items():
            if cat_id not in categories:
                categories[cat_id] = []
            seen = {t["name"] for t in categories[cat_id]}
            for t in cat.get("types", []):
                name = t.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    meta = _TYPE_META.get(name, {})
                    categories[cat_id].append(
                        {
                            "name": name,
                            "label": meta.get("label", name.replace("_", " ").title()),
                            "description": meta.get("description", ""),
                            "width": t.get("width"),
                            "height": t.get("height"),
                        }
                    )

    families: list[dict[str, Any]] = []
    for fid in _FAMILY_ORDER:
        if fid not in categories:
            continue
        fmeta = _FAMILY_META.get(fid, {})
        families.append(
            {
                "id": fid,
                "label": fmeta.get("label", fid.title()),
                "description": fmeta.get("description", ""),
                "types": categories[fid],
            }
        )

    return {"families": families}
