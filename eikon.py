#!/usr/bin/env python3
"""Eikon compatibility shim.

La implementación vive en ``eikon_core/``. Este módulo mantiene el API
histórico (`from eikon import ...`) y el entrypoint `python eikon.py`.
"""

from __future__ import annotations

import sys

from eikon_core import constants as _constants
from eikon_core.brand import brand_family, load_json
from eikon_core.cache import compute_hash, load_cache, save_cache
from eikon_core.cli import main
from eikon_core.constants import (
    DEFAULT_LOCALE,
    ENGINE_VERSION,
    FONT_TIMEOUT_MS,
    MARCAS_DIR,
    MIN_PNG_BYTES,
    ROOT,
    TEMPLATES_DIR,
    TIMEOUT_MS,
)
from eikon_core.injection import injection_script
from eikon_core.layout import (
    LAYOUT_INSPECTION_JS,
    LAYOUT_SELECTORS,
    LAYOUT_WARNING_SEVERITY,
    aggregate_layout_status,
    classify_layout_warning,
)
from eikon_core.manifest import post_validate_assets, write_manifest
from eikon_core.mapping import map_marca_to_vars
from eikon_core.orchestrator import run_generator
from eikon_core.playwright_lazy import PlaywrightTimeoutError, _get_playwright, async_playwright
from eikon_core.render import render_asset
from eikon_core.taxonomy import (
    CLOUD_ATLAS_TAXONOMIA,
    PRIZMA_TAXONOMIA,
    TAXONOMY_JSON_PATH,
    _build_taxonomia,
    _from_taxonomy_json,
    _legacy_python_taxonomia,
    taxonomy_to_json_dict,
)
from eikon_core.templates import _TEMPLATE_ALIASES, resolve_template
from eikon_core.text import TEXT_LIMITS, apply_text_limits, shorten_text
from eikon_core.types import TypeSpec, VariantSpec
from eikon_core.validation import validate_taxonomy

__all__ = [
    "CLOUD_ATLAS_TAXONOMIA",
    "DEFAULT_LOCALE",
    "ENGINE_VERSION",
    "FONT_TIMEOUT_MS",
    "LAYOUT_INSPECTION_JS",
    "LAYOUT_SELECTORS",
    "LAYOUT_WARNING_SEVERITY",
    "MARCAS_DIR",
    "MIN_PNG_BYTES",
    "OUTPUT_DIR",  # noqa: F822  # Accessible via __getattr__
    "PRIZMA_TAXONOMIA",
    "ROOT",
    "TAXONOMY_JSON_PATH",
    "TEMPLATES_DIR",
    "TEXT_LIMITS",
    "TIMEOUT_MS",
    "_TEMPLATE_ALIASES",
    "PlaywrightTimeoutError",
    "TypeSpec",
    "VariantSpec",
    "_build_taxonomia",
    "_from_taxonomy_json",
    "_get_playwright",
    "_legacy_python_taxonomia",
    "aggregate_layout_status",
    "apply_text_limits",
    "async_playwright",
    "brand_family",
    "classify_layout_warning",
    "compute_hash",
    "injection_script",
    "load_cache",
    "load_json",
    "main",
    "map_marca_to_vars",
    "post_validate_assets",
    "render_asset",
    "resolve_template",
    "run_generator",
    "save_cache",
    "shorten_text",
    "taxonomy_to_json_dict",
    "validate_taxonomy",
    "write_manifest",
]

# OUTPUT_DIR forwarding: accessed through __getattr__, synchronized with constants.
# This replaces the previous metaclass implementation for cleaner architecture.


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Module-level attribute access for OUTPUT_DIR."""
    if name == "OUTPUT_DIR":
        return _constants.OUTPUT_DIR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():  # type: ignore[no-untyped-def]
    """Include OUTPUT_DIR in module directory."""
    import types

    items = list(types.ModuleType.__dir__(sys.modules[__name__]))
    if "OUTPUT_DIR" not in items:
        items.append("OUTPUT_DIR")
    return items


if __name__ == "__main__":
    sys.exit(main())
