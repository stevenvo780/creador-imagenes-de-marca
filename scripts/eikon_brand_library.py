#!/usr/bin/env python3
"""Genera o verifica ``config/brand-library.json`` desde ``marcas/*.json``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eikon_core.brand_library import BRAND_LIBRARY_PATH, BrandLibrary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida la biblioteca BrandSpec de Eikón")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="Regenera el catálogo consolidado")
    action.add_argument("--check", action="store_true", help="Verifica que no haya drift")
    args = parser.parse_args()

    if args.write:
        library = BrandLibrary.from_sources()
        path = library.write_catalog()
        print(f"OK: {len(library.brands)} marcas consolidadas en {path}")
        return 0

    catalog = BrandLibrary.from_catalog(BRAND_LIBRARY_PATH)
    catalog.assert_matches_sources()
    print(f"OK: {len(catalog.brands)} marcas sin drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
