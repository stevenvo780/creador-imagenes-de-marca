from __future__ import annotations

from typing import Any

from . import constants as cfg
from .cache import compute_hash
from .injection import injection_script
from .layout import LAYOUT_INSPECTION_JS, aggregate_layout_status
from .mapping import map_marca_to_vars
from .templates import resolve_template
from .types import TypeSpec, VariantSpec


async def render_asset(
    browser: Any,
    marca_slug: str,
    categoria: str,
    tipo_spec: TypeSpec,
    variant_spec: VariantSpec,
    marca: dict[str, Any],
    cache: dict[str, str],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Renderiza un asset individual. Retorna metadata para el manifest."""
    template_path = resolve_template(tipo_spec.name, cfg.TEMPLATES_DIR)
    if template_path is None:
        return {
            "category": categoria,
            "type": tipo_spec.name,
            "variant": variant_spec.name,
            "status": "error",
            "warnings": ["template not found"],
        }

    vars_dict = map_marca_to_vars(marca, tipo_spec.name, variant_name=variant_spec.name)
    input_hash = compute_hash(
        marca, categoria, tipo_spec.name, variant_spec.name, template_path, vars_dict
    )
    cache_key = f"{categoria}/{tipo_spec.name}/{variant_spec.name}"
    output_path = (
        cfg.OUTPUT_DIR / marca_slug / categoria / tipo_spec.name / f"{variant_spec.name}.png"
    )

    asset_meta = {
        "path": str(output_path.relative_to(cfg.OUTPUT_DIR / marca_slug)),
        "category": categoria,
        "type": tipo_spec.name,
        "variant": variant_spec.name,
        "width": tipo_spec.get_output_width(categoria),
        "height": tipo_spec.get_output_height(categoria),
        "input_hash": input_hash,
        "status": "pending",
        "warnings": [],
        "layout_status": "skipped",
        "layout_warnings": [],
    }

    if cache is not None and cache.get(cache_key) == input_hash and output_path.exists():
        asset_meta["status"] = "cached"
        return asset_meta

    if dry_run:
        asset_meta["status"] = "dry_run"
        return asset_meta

    context = None
    page = None
    try:
        injection = injection_script(
            vars_dict, variant_name=variant_spec.name, template_name=tipo_spec.name
        )
        scale_factor = tipo_spec.get_device_scale_factor(categoria)

        context = await browser.new_context(
            viewport={"width": tipo_spec.width, "height": tipo_spec.height},
            device_scale_factor=scale_factor,
            locale="es-ES",
        )
        page = await context.new_page()

        url = f"{template_path.as_uri()}?variant={variant_spec.name}"
        await page.goto(url, wait_until="domcontentloaded", timeout=cfg.TIMEOUT_MS)
        await page.evaluate(injection)

        try:
            await page.evaluate(f"""() => Promise.race([
                document.fonts?.ready || Promise.resolve(),
                new Promise(resolve => setTimeout(resolve, {cfg.FONT_TIMEOUT_MS}))
            ])""")
        except Exception:
            pass

        await page.wait_for_timeout(100)

        try:
            layout_result = await page.evaluate(LAYOUT_INSPECTION_JS)
            raw_warnings = (
                layout_result.get("warnings", []) if isinstance(layout_result, dict) else []
            )
            asset_meta["layout_warnings"] = list(raw_warnings)
            asset_meta["layout_status"] = aggregate_layout_status(raw_warnings)
        except Exception as layout_err:
            asset_meta["layout_warnings"] = [
                {"type": "inspection_error", "detail": str(layout_err)}
            ]
            asset_meta["layout_status"] = aggregate_layout_status(asset_meta["layout_warnings"])

        output_path.parent.mkdir(parents=True, exist_ok=True)

        screenshot_taken = False
        last_error = None
        for attempt in range(2):
            try:
                await page.screenshot(
                    path=str(output_path), type="png", full_page=False, omit_background=False
                )
                screenshot_taken = True
                break
            except Exception as screenshot_err:
                last_error = screenshot_err
                err_msg = str(screenshot_err).lower()
                if attempt == 0 and (
                    "capturescreenshot" in err_msg
                    or "target closed" in err_msg
                    or "protocol error" in err_msg
                    or "session closed" in err_msg
                ):
                    print("⟳", end="", flush=True)
                    await page.wait_for_timeout(200)
                    continue
                raise

        if not screenshot_taken:
            raise last_error  # type: ignore[misc]

        asset_meta["status"] = "generated"
        if cache is not None:
            cache[cache_key] = input_hash

    except Exception as e:
        asset_meta["status"] = "error"
        asset_meta["warnings"].append(str(e))
    finally:
        if page:
            await page.close()
        if context:
            await context.close()

    return asset_meta
