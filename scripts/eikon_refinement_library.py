#!/usr/bin/env python3
"""Construye un indice verificable de una biblioteca before/after."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eikon_core.refinement import RefinementError  # noqa: E402
from eikon_core.refinement_library import write_refinement_library  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolida muestras refinadas de Eikon")
    parser.add_argument("root", type=Path, help="Directorio que contiene PNG + metadata")
    parser.add_argument("--output", type=Path, help="Destino; default: ROOT/_library.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        destination = write_refinement_library(
            args.root,
            base_dir=ROOT,
            output_path=args.output,
        )
        payload = json.loads(destination.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "library": str(destination),
                    "assets": payload["asset_count"],
                    "providers": payload["providers"],
                    "content_sha256": payload["content_sha256"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, RefinementError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
