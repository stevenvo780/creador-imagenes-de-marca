#!/usr/bin/env python3
"""Refina una o muchas maquetas Eikón con un proveedor explícito."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eikon_core.brand_library import BrandLibrary  # noqa: E402
from eikon_core.refinement import RefinementError, refine_asset  # noqa: E402
from eikon_core.refinement_providers import (  # noqa: E402
    LocalPreviewProvider,
    OpenAIImageEditProvider,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segunda capa Eikón: mockup on-brand -> refinado visual"
    )
    parser.add_argument("--brand", required=True, help="Slug de config/brand-library.json")
    parser.add_argument("--asset-type", required=True, help="Tipo canónico, ej. ig_post")
    parser.add_argument("--input", type=Path, required=True, help="PNG fuente o directorio")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--glob", default="*.png", help="Patrón si --input es directorio")
    parser.add_argument("--max-assets", type=int, default=100)
    parser.add_argument(
        "--provider", choices=("local-preview", "openai"), default="local-preview"
    )
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="high")
    parser.add_argument("--allow-paid-api", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _inputs(path: Path, pattern: str, max_assets: int) -> list[Path]:
    if max_assets < 1 or max_assets > 1000:
        raise RefinementError("--max-assets debe estar entre 1 y 1000")
    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(item for item in path.glob(pattern) if item.is_file())
    else:
        raise RefinementError(f"--input no existe: {path}")
    candidates = candidates[:max_assets]
    if not candidates:
        raise RefinementError("No se encontraron PNGs para refinar")
    return candidates


def _provider(args: argparse.Namespace) -> LocalPreviewProvider | OpenAIImageEditProvider:
    if args.provider == "local-preview":
        return LocalPreviewProvider()
    if not args.allow_paid_api:
        raise RefinementError(
            "OpenAI está bloqueado: confirme gasto con --allow-paid-api"
        )
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RefinementError("Falta OPENAI_API_KEY en el entorno")
    return OpenAIImageEditProvider(api_key=api_key, model=args.model)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        spec = BrandLibrary.from_catalog().get(args.brand)
        inputs = _inputs(args.input, args.glob, args.max_assets)
        plan = [
            {
                "source": str(source),
                "output": str(args.output_dir / f"{source.stem}.refined.png"),
            }
            for source in inputs
        ]
        if args.dry_run:
            print(json.dumps({"provider": args.provider, "assets": plan}, indent=2))
            return 0
        provider = _provider(args)
        results = []
        for item, source in zip(plan, inputs, strict=True):
            result = refine_asset(
                source_path=source,
                output_path=Path(item["output"]),
                spec=spec,
                asset_type=args.asset_type,
                provider=provider,
                quality=args.quality,
                overwrite=args.overwrite,
            )
            results.append(
                {
                    "source": result.source_path,
                    "output": result.output_path,
                    "provider": result.provider,
                    "model": result.model,
                    "gate": {
                        "structure_score": result.gate.structure_score,
                        "palette_adherence": result.gate.palette_adherence,
                    },
                }
            )
        print(json.dumps({"refined": len(results), "assets": results}, indent=2))
        return 0
    except (KeyError, OSError, RefinementError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
