from __future__ import annotations

import functools
import os
import time
from pathlib import Path
from typing import Any

from . import constants as cfg
from .brand import brand_family, load_json
from .cache import load_cache, save_cache
from .combinatorial import AxesConfig
from .manifest import post_validate_assets, write_manifest
from .playwright_lazy import _get_playwright
from .render import render_asset
from .taxonomy import CLOUD_ATLAS_TAXONOMIA, PRIZMA_TAXONOMIA, get_category_for_asset_type


async def run_generator(  # noqa: C901
    marcas_a_procesar: list[str],
    filtro_categoria: str | None = None,
    dry_run: bool = False,
    use_cache: bool = False,
    max_parallel: int = 1,
    skip_contrast: bool = False,
) -> dict[str, Any]:
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

                cache: dict[str, str] = load_cache(marca_slug) if use_cache else {}
                counts[marca_slug] = {}
                asset_metas: list[dict[str, Any]] = []
                gen = skip = err = 0

                total_types = sum(len(ts) for ts in taxonomia.values())
                type_idx = 0

                for categoria, type_specs in taxonomia.items():
                    if filtro_categoria and categoria != filtro_categoria:
                        continue
                    counts[marca_slug][categoria] = 0
                    print(f"  → Categoria [{categoria}]:")

                    _solo_tipo = os.environ.get("EIKON_SOLO_TIPO")
                    for type_spec in type_specs:
                        if _solo_tipo and type_spec.name != _solo_tipo:
                            continue
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


@functools.lru_cache(maxsize=1)
def _asset_dimensions() -> dict[str, tuple[int, int]]:
    """Mapa {nombre_tipo: (width, height)} desde la taxonomía (fuente de verdad
    de tamaños). Evita renderizar toda combinación a un 512x512 fijo y equivocado
    (que recortaba isotipos/banners/social)."""
    dims: dict[str, tuple[int, int]] = {}
    for tax in (CLOUD_ATLAS_TAXONOMIA, PRIZMA_TAXONOMIA):
        groups = tax.values() if isinstance(tax, dict) else tax
        for group in groups:
            specs = group if isinstance(group, list | tuple) else [group]
            for s in specs:
                name = getattr(s, "name", None)
                width = getattr(s, "width", None)
                height = getattr(s, "height", None)
                if name and width and height:
                    dims[name] = (int(width), int(height))
    return dims


async def render_combination(
    browser: Any,
    marca_slug: str,
    combination: Any,
    asset_type: str,
    marca: dict[str, Any],
    axes_config: AxesConfig,
    cache: dict[str, str] | None = None,
    dry_run: bool = False,
    batch_id: int | None = None,
    content_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Renderiza un asset con parametros de combinacion especificada.

    Args:
        browser: Playwright browser instance
        marca_slug: Slug de la marca
        combination: Combination object with params dict
        asset_type: Tipo de asset (ej. "logo_symbol_color")
        marca: Dict con datos de la marca
        axes_config: AxesConfig para validacion
        cache: Optional cache dict
        dry_run: Si True, no renderiza realmente
        batch_id: ID del batch. Cuando se proporciona, el PNG se escribe en
            .../asset_type/<batch_id>/combo_NNN.png, evitando que batches
            distintos sobre el mismo brand+asset_type se sobreescriban.

    Returns:
        Asset metadata dict
    """
    from .types import TypeSpec, VariantSpec

    # Validate combination params
    axes_config.validate_combination(combination.params)

    # Tamaño real del asset desde la taxonomía (no un 512x512 fijo que recorta).
    width, height = _asset_dimensions().get(asset_type, (512, 512))
    tipo_spec = TypeSpec(
        name=asset_type,
        width=width,
        height=height,
        variants=(),
    )
    variant_spec = VariantSpec(
        name=f"combo_{combination.idx:03d}",
        label=f"Combination {combination.idx}",
    )

    # Derivar categoría real desde el asset_type buscándolo en la taxonomía.
    # Si no se encuentra, usar "logos" como fallback (compatibilidad).
    is_prizma = "prizma" in brand_family(marca)
    categoria = get_category_for_asset_type(asset_type, is_prizma) or "logos"

    # batch_subdir aisla PNGs por batch_id, evitando sobreescrituras entre batches.
    return await render_asset(
        browser,
        marca_slug,
        categoria,
        tipo_spec,
        variant_spec,
        marca,
        cache or {},
        dry_run=dry_run,
        combination_params=combination.params,
        batch_subdir=str(batch_id) if batch_id is not None else None,
        content_overrides=content_overrides,
    )
