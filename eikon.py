#!/usr/bin/env python3
"""Eikon compatibility shim.

La implementación vive en ``eikon_core/``. Este módulo mantiene el API
histórico (`from eikon import ...`) y el entrypoint `python eikon.py`.
"""
from __future__ import annotations

import sys

from eikon_core import constants as _constants
from eikon_core.constants import (
    ROOT,
    MARCAS_DIR,
    TEMPLATES_DIR,
    ENGINE_VERSION,
    TIMEOUT_MS,
    FONT_TIMEOUT_MS,
    DEFAULT_LOCALE,
    MIN_PNG_BYTES,
)
from eikon_core.types import TypeSpec, VariantSpec
from eikon_core.text import TEXT_LIMITS, shorten_text, apply_text_limits
from eikon_core.playwright_lazy import _get_playwright, async_playwright, PlaywrightTimeoutError
from eikon_core.taxonomy import (
    TAXONOMY_JSON_PATH,
    CLOUD_ATLAS_TAXONOMIA,
    PRIZMA_TAXONOMIA,
    _build_taxonomia,
    _legacy_python_taxonomia,
    _from_taxonomy_json,
    taxonomy_to_json_dict,
)
from eikon_core.validation import validate_taxonomy
from eikon_core.brand import load_json, brand_family
from eikon_core.mapping import map_marca_to_vars
from eikon_core.injection import injection_script
from eikon_core.layout import (
    LAYOUT_SELECTORS,
    LAYOUT_WARNING_SEVERITY,
    classify_layout_warning,
    aggregate_layout_status,
    LAYOUT_INSPECTION_JS,
)
from eikon_core.templates import _TEMPLATE_ALIASES, resolve_template
from eikon_core.cache import compute_hash, load_cache, save_cache
from eikon_core.manifest import post_validate_assets, write_manifest
from eikon_core.render import render_asset
from eikon_core.orchestrator import run_generator
from eikon_core.cli import main


class _EikonModule(type(sys.modules[__name__])):
    @property
    def OUTPUT_DIR(self):  # type: ignore[override]
        return _constants.OUTPUT_DIR

    @OUTPUT_DIR.setter
    def OUTPUT_DIR(self, value):  # type: ignore[override]
        _constants.OUTPUT_DIR = value


sys.modules[__name__].__class__ = _EikonModule

__all__ = [
    "ROOT", "MARCAS_DIR", "TEMPLATES_DIR", "OUTPUT_DIR", "ENGINE_VERSION",
    "TIMEOUT_MS", "FONT_TIMEOUT_MS", "DEFAULT_LOCALE", "MIN_PNG_BYTES",
    "TypeSpec", "VariantSpec", "TEXT_LIMITS", "shorten_text", "apply_text_limits",
    "_get_playwright", "async_playwright", "PlaywrightTimeoutError",
    "TAXONOMY_JSON_PATH", "CLOUD_ATLAS_TAXONOMIA", "PRIZMA_TAXONOMIA",
    "_build_taxonomia", "_legacy_python_taxonomia", "_from_taxonomy_json",
    "taxonomy_to_json_dict", "validate_taxonomy", "load_json", "brand_family",
    "map_marca_to_vars", "injection_script", "LAYOUT_SELECTORS",
    "LAYOUT_WARNING_SEVERITY", "classify_layout_warning", "aggregate_layout_status",
    "LAYOUT_INSPECTION_JS", "_TEMPLATE_ALIASES", "resolve_template", "compute_hash",
    "load_cache", "save_cache", "post_validate_assets", "write_manifest",
    "render_asset", "run_generator", "main",
]


if __name__ == "__main__":
    sys.exit(main())
