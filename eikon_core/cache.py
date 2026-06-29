from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import constants as cfg


def compute_hash(
    marca: dict[str, Any],
    categoria: str,
    type_name: str,
    variant_name: str,
    template_path: Path,
    vars_dict: dict[str, str],
) -> str:
    """Hash estable para detectar cambios en inputs de un asset."""
    try:
        template_content = template_path.read_text(encoding="utf-8")
    except Exception:
        template_content = ""

    payload = json.dumps(
        {
            "engine": cfg.ENGINE_VERSION,
            "marca_slug": str(marca.get("slug", "")),
            "category": categoria,
            "type": type_name,
            "variant": variant_name,
            "vars": vars_dict,
            "template": template_content,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_cache(marca_slug: str) -> dict[str, str]:
    cache_path = cfg.OUTPUT_DIR / marca_slug / ".cache.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass
    return {}


def save_cache(marca_slug: str, cache: dict[str, str]) -> None:
    cache_path = cfg.OUTPUT_DIR / marca_slug / ".cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))
