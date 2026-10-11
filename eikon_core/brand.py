from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"Se esperaba dict, se obtuvo {type(data).__name__}"
        return data
    except Exception as e:
        print(f"✗ Error al cargar {path}: {e}", file=sys.stderr)
        raise


def brand_family(marca: dict[str, Any]) -> str:
    # El adaptador web llama «textos» al metadata «texts» de la API.
    # La pertenencia de Humanizar es explícita: nunca se infiere del tenant/slug.
    metadata = marca.get("textos", marca.get("texts"))
    if isinstance(metadata, dict) and metadata.get("brand_family") == "humanizar":
        return "humanizar"
    slug = str(marca.get("slug", "")).lower()
    return "prizma" if "prizma" in slug else "cloud_atlas"


def humanizar_marca_from_row(brand_row: dict[str, Any]) -> dict[str, Any] | None:
    """Perfil de la fila ya scoped por tenant, por encima del JSON legado.

    Otros perfiles siguen la ruta histórica. Un slug coincidente con una marca
    local nunca sustituye el nombre, textos ni paleta de la empresa que optó
    explícitamente por la familia Humanizar.
    """
    texts = json.loads(str(brand_row.get("texts_json", "{}")))
    if not isinstance(texts, dict) or texts.get("brand_family") != "humanizar":
        return None
    return {
        "slug": str(brand_row.get("slug", "")),
        "nombre_producto": str(brand_row.get("name", "")),
        "paleta": json.loads(str(brand_row.get("palette_json", "{}"))),
        "tipografia": json.loads(str(brand_row.get("typography_json", "{}"))),
        "logo_texto": str(brand_row.get("logo_text", "")),
        "logo_simbolo": str(brand_row.get("logo_symbol", "")),
        "logo_style": str(brand_row.get("logo_style", "")),
        "logo_seed": brand_row.get("logo_seed"),
        "logo_asset": brand_row.get("logo_asset"),
        "textos": texts,
    }
