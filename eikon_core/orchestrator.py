from __future__ import annotations

import time
from pathlib import Path

from . import constants as cfg
from .brand import brand_family, load_json
from .cache import load_cache, save_cache
from .manifest import post_validate_assets, write_manifest
from .playwright_lazy import _get_playwright
from .render import render_asset
from .taxonomy import CLOUD_ATLAS_TAXONOMIA, PRIZMA_TAXONOMIA


async def run_generator(  # noqa: C901
    marcas_a_procesar: list[str],
    filtro_categoria: str | None = None,
    dry_run: bool = False,
    use_cache: bool = False,
    max_parallel: int = 1,
    skip_contrast: bool = False,
) -> dict:
    """Genera assets para las marcas especificadas."""
    apw, _ = _get_playwright()
    counts: dict[str, dict[str, int]] = {}
    manifests: list[Path] = []
    total_gen = 0
    total_skip = 0
    total_err = 0
    total_layout_fail = 0

    if dry_run:
        print("⇢ DRY-RUN: Enumerando assets (sin renderizar).\n")

    async with apw() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        try:
            for marca_slug in marcas_a_procesar:
                t_start = time.time()
                print(f"\n→ Procesando marca: {marca_slug}")
                marca_path = cfg.MARCAS_DIR / f"{marca_slug}.json"
                if not marca_path.exists():
                    print(f"  ✗ Marca no encontrada: {marca_path}")
                    continue

                marca = load_json(marca_path)
                family = brand_family(marca)
                taxonomia = PRIZMA_TAXONOMIA if "prizma" in family else CLOUD_ATLAS_TAXONOMIA

                cache = load_cache(marca_slug) if use_cache else {}
                counts[marca_slug] = {}
                asset_metas: list[dict] = []
                gen = skip = err = 0

                total_types = sum(len(ts) for ts in taxonomia.values())
                type_idx = 0

                for categoria, type_specs in taxonomia.items():
                    if filtro_categoria and categoria != filtro_categoria:
                        continue
                    counts[marca_slug][categoria] = 0
                    print(f"  → Categoria [{categoria}]:")

                    for type_spec in type_specs:
                        type_idx += 1
                        scale = type_spec.get_device_scale_factor(categoria)
                        out_w = type_spec.get_output_width(categoria)
                        out_h = type_spec.get_output_height(categoria)
                        print(
                            f"    [{type_idx}/{total_types}] {type_spec.name} ({out_w}x{out_h}px @{scale}x) →",
                            end=" ",
                            flush=True,
                        )

                        success = 0
                        for variant_spec in type_spec.variants:
                            meta = await render_asset(
                                browser,
                                marca_slug,
                                categoria,
                                type_spec,
                                variant_spec,
                                marca,
                                cache,
                                dry_run=dry_run,
                            )
                            asset_metas.append(meta)

                            if meta["status"] == "generated":
                                success += 1
                                gen += 1
                                print("✓", end="", flush=True)
                            elif meta["status"] == "cached":
                                success += 1
                                skip += 1
                                print("↻", end="", flush=True)
                            elif meta["status"] == "dry_run":
                                success += 1
                                print("·", end="", flush=True)
                            else:
                                err += 1
                                print("⊘", end="", flush=True)

                        counts[marca_slug][categoria] += success
                        print()

                remarkeados = post_validate_assets(asset_metas, marca_slug)
                if remarkeados > 0:
                    print(
                        f"     ⟳ Post-validación: {remarkeados} assets re-marcados como generated (PNG existe)"
                    )
                    gen = sum(1 for a in asset_metas if a["status"] == "generated")
                    skip = sum(1 for a in asset_metas if a["status"] == "cached")
                    err = sum(1 for a in asset_metas if a["status"] == "error")

                manifest_path = write_manifest(marca_slug, asset_metas)
                manifests.append(manifest_path)
                print(f"     ✓ Manifest: {manifest_path.name} ({len(asset_metas)} assets)")

                if use_cache and not dry_run:
                    save_cache(marca_slug, cache)

                elapsed = time.time() - t_start
                print(f"  ✓ {marca_slug}: {gen} gen, {skip} cache, {err} err  ({elapsed:.1f}s)")

                total_gen += gen
                total_skip += skip
                total_err += err
                total_layout_fail += sum(1 for a in asset_metas if a.get("layout_status") == "fail")
        finally:
            await browser.close()

    if not dry_run and not skip_contrast:
        print("\n→ Ejecutando validador de contrastes WCAG AA...")
        try:
            from contrast_validator import ContrastValidator

            if len(marcas_a_procesar) == 1:
                slug = marcas_a_procesar[0]
                validator = ContrastValidator(cfg.OUTPUT_DIR)
                validator.validate_all(marca_slug=slug)
                validator.write_report(cfg.OUTPUT_DIR / slug / "_contraste-report.json")
            else:
                for slug in marcas_a_procesar:
                    validator = ContrastValidator(cfg.OUTPUT_DIR)
                    validator.validate_all(marca_slug=slug)
                    validator.write_report(cfg.OUTPUT_DIR / slug / "_contraste-report.json")
                validator_global = ContrastValidator(cfg.OUTPUT_DIR)
                validator_global.validate_all()
                validator_global.write_report(cfg.OUTPUT_DIR / "_contraste-report.json")
        except ImportError:
            print("  ⚠ contrast_validator.py no encontrado. Omitiendo validación.")
        except Exception as e:
            print(f"  ⚠ Error en validación de contraste: {e}")

    return {
        "counts": counts,
        "manifests": manifests,
        "total": {
            "generated": total_gen,
            "cached": total_skip,
            "errors": total_err,
            "layout_fails": total_layout_fail,
        },
    }
