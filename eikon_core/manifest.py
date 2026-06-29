from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import constants as cfg


def post_validate_assets(asset_metas: list[dict[str, Any]], marca_slug: str) -> int:
    """Re-marca errores espurios si el PNG existe y supera MIN_PNG_BYTES."""
    remarkeados = 0
    for meta in asset_metas:
        if meta.get("status") != "error":
            continue
        png_path = cfg.OUTPUT_DIR / marca_slug / meta.get("path", "")
        if png_path.exists() and png_path.stat().st_size >= cfg.MIN_PNG_BYTES:
            meta["status"] = "generated"
            meta["warnings"].append("post-validated: PNG exists despite render error")
            remarkeados += 1
    return remarkeados


def write_manifest(marca_slug: str, assets: list[dict[str, Any]]) -> Path:
    """Escribe _manifest.json con metadata de todos los assets de una marca."""
    manifest_path = cfg.OUTPUT_DIR / marca_slug / "_manifest.json"
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "engine_version": cfg.ENGINE_VERSION,
        "marca": marca_slug,
        "total_assets": len(assets),
        "assets": sorted(
            assets,
            key=lambda a: (a.get("category", ""), a.get("type", ""), a.get("variant", "")),
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest_path
