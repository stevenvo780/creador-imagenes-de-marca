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


def variation_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Serializa una fila de variations a JSON, con file_url de descarga.

    No expone output_path (ruta absoluta del servidor) ni tenant_id (dato interno).
    """
    var_id = row["id"]
    return {
        "id": var_id,
        "batch_id": row.get("batch_id"),
        "brand_id": row["brand_id"],
        "axis_params": _loads(row.get("axis_params_json"), {}),
        "seed": row.get("seed"),
        "score": row.get("score"),
        "wcag": _loads(row.get("wcag_json"), None),
        "layout_status": row.get("layout_status"),
        "selected": bool(row.get("selected", 0)),
        "created_at": row.get("created_at"),
        "file_url": f"/api/v1/variations/{var_id}/file",
    }
