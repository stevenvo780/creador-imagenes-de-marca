#!/usr/bin/env python3
"""Genera una evidencia reproducible de las dos capas sin consumir una API."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eikon_core import constants as cfg  # noqa: E402
from eikon_core.brand import brand_family, load_json  # noqa: E402
from eikon_core.brand_library import BrandLibrary  # noqa: E402
from eikon_core.playwright_lazy import _get_playwright  # noqa: E402
from eikon_core.refinement import refine_asset  # noqa: E402
from eikon_core.refinement_providers import LocalPreviewProvider  # noqa: E402
from eikon_core.render import render_asset  # noqa: E402
from eikon_core.taxonomy import CLOUD_ATLAS_TAXONOMIA, PRIZMA_TAXONOMIA  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Muestra Eikón before/after sin red")
    parser.add_argument("--brand", default="pinakotheke-kosmos")
    parser.add_argument("--asset-type", default="ig_post")
    parser.add_argument("--variant", default="v1_square")
    parser.add_argument(
        "--sample-dir", type=Path, default=Path("docs/samples/eikon-gpt-pipeline")
    )
    parser.add_argument(
        "--chromium-executable",
        type=Path,
        help="Binario Chromium/Chrome alternativo para entornos sin browser Playwright",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> tuple[Path, Path]:
    marca = load_json(cfg.MARCAS_DIR / f"{args.brand}.json")
    taxonomy = PRIZMA_TAXONOMIA if "prizma" in brand_family(marca) else CLOUD_ATLAS_TAXONOMIA
    matches = [
        (category, type_spec, variant)
        for category, type_specs in taxonomy.items()
        for type_spec in type_specs
        if type_spec.name == args.asset_type
        for variant in type_spec.variants
        if variant.name == args.variant
    ]
    if len(matches) != 1:
        raise ValueError(
            f"No hay una combinación única para {args.asset_type}/{args.variant}"
        )
    category, type_spec, variant = matches[0]

    async_playwright, _ = _get_playwright()
    launch_options: dict[str, object] = {
        "headless": True,
        "args": ["--disable-dev-shm-usage"],
    }
    if args.chromium_executable:
        launch_options["executable_path"] = str(args.chromium_executable)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**launch_options)
        try:
            metadata = await render_asset(
                browser,
                args.brand,
                category,
                type_spec,
                variant,
                marca,
                {},
            )
        finally:
            await browser.close()
    if metadata["status"] != "generated":
        raise RuntimeError(f"Falló el render Eikón: {metadata['warnings']}")

    rendered = cfg.OUTPUT_DIR / args.brand / metadata["path"]
    args.sample_dir.mkdir(parents=True, exist_ok=True)
    before = args.sample_dir / "before-eikon-mockup.png"
    after = args.sample_dir / "after-local-preview.png"
    shutil.copyfile(rendered, before)
    refine_asset(
        source_path=before,
        output_path=after,
        spec=BrandLibrary.from_catalog().get(args.brand),
        asset_type=args.asset_type,
        provider=LocalPreviewProvider(),
        overwrite=True,
    )
    return before, after


def main() -> int:
    args = parse_args()
    before, after = asyncio.run(run(args))
    print(f"before={before}")
    print(f"after={after}")
    print("provider=local-preview (offline; no es GPT)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
