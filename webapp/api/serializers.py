"""Serializadores de filas de DB a dicts JSON-friendly para la API.

Las filas de storage llegan como dicts con columnas *_json en texto; aquí se
parsean a objetos y se exponen URLs de descarga relativas para el SPA.
"""

from __future__ import annotations

import json
from typing import Any


def _loads(raw: Any, default: Any) -> Any:
    """Parsea JSON de una columna de texto; devuelve default si está vacío."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def brand_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serializa una fila de brands a JSON con los *_json ya parseados."""
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "palette": _loads(row.get("palette_json"), {}),
        "typography": _loads(row.get("typography_json"), {}),
        "logo_text": row.get("logo_text", ""),
        "logo_symbol": row.get("logo_symbol", ""),
        "logo_style": row.get("logo_style", ""),
        "logo_seed": row.get("logo_seed", 0),
        "logo_asset": row.get("logo_asset"),
        "texts": _loads(row.get("texts_json"), {}),
        "created_at": row.get("created_at"),
    }


def batch_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serializa una fila de batches a JSON con spec/counts parseados.

    No expone tenant_id (dato interno de multi-tenancy).
    """
    return {
        "id": row["id"],
        "brand_id": row["brand_id"],
        "spec": _loads(row.get("spec_json"), {}),
        "status": row["status"],
        "counts": _loads(row.get("counts_json"), {}),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


_KNOWN_CATEGORIES: frozenset[str] = frozenset({"logos", "banners", "cards", "og", "stationery"})


def _category_from_path(output_path: str | None) -> str | None:
    """Extrae la categoría del asset desde su output_path (agnóstico de backend).

    Busca el segmento "tenants" en el path; la categoría está 3 posiciones después:

        [36m.../tenants/{tenant_id}/{brand}/{**category**}/{asset_type}/...[0m
        tenants → tenant_id → brand → **(category)** → asset_type → ...

    Soportado en los tres formatos:
      - GCS:    gs://bucket/tenants/{tenant_id}/{brand}/{category}/...
      - Local:  /abs/path/output/tenants/{tenant_id}/{brand}/{category}/...
      - Relativo: tenants/{tenant_id}/{brand}/{category}/...

    Fallback: si no se encuentra "tenants", usa el índice fijo -4 (comportamiento antiguo).
    Retorna None si output_path es nulo o el segmento no es una categoría conocida.
    """
    if not output_path:
        return None
    parts = output_path.replace("\\", "/").split("/")
    if len(parts) < 4:
        return None

    # Método agnóstico: localizar "tenants" → category = +3 posiciones
    # tenants[0] / tenant_id[1] / brand[2] / category[3] / asset_type[4] / ...
    try:
        tenant_idx = parts.index("tenants")
        cat_idx = tenant_idx + 3
        if cat_idx < len(parts):
            candidate = parts[cat_idx]
            if candidate in _KNOWN_CATEGORIES:
                return candidate
    except ValueError:
        pass

    # Fallback al índice negativo fijo (-4) si el método agnóstico falló
    candidate = parts[-4]
    return candidate if candidate in _KNOWN_CATEGORIES else None


def variation_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serializa una fila de variations a JSON, con file_url de descarga.

    No expone output_path (ruta absoluta del servidor) ni tenant_id (dato interno).
    Expone category derivada del output_path: logos | banners | cards | og | stationery.
    """
    var_id = row["id"]
    return {
        "id": var_id,
        "batch_id": row.get("batch_id"),
        "brand_id": row["brand_id"],
        "axis_params": _loads(row.get("axis_params_json"), {}),
        "seed": row.get("seed"),
        "score": row.get("score"),
        "category": _category_from_path(row.get("output_path")),
        "wcag": _loads(row.get("wcag_json"), None),
        "layout_status": row.get("layout_status"),
        "selected": bool(row.get("selected", 0)),
        "created_at": row.get("created_at"),
        "file_url": f"/api/v1/variations/{var_id}/file",
    }
