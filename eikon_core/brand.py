from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"
        return data
    except Exception as e:
        print(f"✗ Error cargando {path}: {e}", file=sys.stderr)
        raise


def brand_family(marca: dict[str, Any]) -> str:
    slug = str(marca.get("slug", "")).lower()
    return "prizma" if "prizma" in slug else "cloud_atlas"
