"""Registro central de generadores de isotipo (símbolos procedurales).

Junta los dicts PACK de todos los packs de categoría + los ejemplos en un único
`GENERATORS = {style_id: gen_fn}`. Importa cada pack de forma DEFENSIVA: un pack
que todavía no existe o que falla al importar NO rompe el resto.

isotype.py usa este registro para despachar `isotype_style` → generador.
"""
from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any

from .catalog import ALGORITHMS, by_category

logger = logging.getLogger(__name__)

# Orden de carga (los ejemplos primero; luego cada pack de categoría).
_PACK_MODULES = [
    "_example",
    "pack_curvas",
    "pack_espirales",
    "pack_poligonos",
    "pack_teselados",
    "pack_fractales",
    "pack_organico",
    "pack_ondas",
    "pack_circulos",
    "pack_distribucion",
    "pack_tipografico",
    "pack_emblemas",
]

GENERATORS: dict[str, Callable[[Any], str]] = {}
_LOAD_ERRORS: dict[str, str] = {}

for _mod in _PACK_MODULES:
    try:
        _m = importlib.import_module(f"eikon_core.isotypes.{_mod}")
        _pack = getattr(_m, "PACK", {})
        if isinstance(_pack, dict):
            GENERATORS.update(_pack)
    except Exception as _e:  # noqa: BLE001 — un pack roto no debe tumbar el import
        _LOAD_ERRORS[_mod] = str(_e)
        logger.warning("pack de isotipos no cargado: %s (%s)", _mod, _e)


def available_styles() -> list[str]:
    """Lista ordenada de `isotype_style` con generador disponible."""
    return sorted(GENERATORS.keys())


def catalog_coverage() -> dict[str, Any]:
    """Diagnóstico: cuántos ids del catálogo tienen generador implementado."""
    catalog_ids = {a[0] for a in ALGORITHMS}
    have = set(GENERATORS.keys())
    return {
        "catalog_total": len(catalog_ids),
        "implemented": len(catalog_ids & have),
        "missing": sorted(catalog_ids - have),
        "extra": sorted(have - catalog_ids),
        "load_errors": dict(_LOAD_ERRORS),
    }


__all__ = ["ALGORITHMS", "GENERATORS", "available_styles", "by_category", "catalog_coverage"]
