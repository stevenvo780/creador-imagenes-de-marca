from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from . import constants as cfg
from .cache import compute_hash
from .errors import EikonScreenshotError
from .injection import injection_script
from .layout import LAYOUT_INSPECTION_JS, aggregate_layout_status
from .mapping import map_marca_to_vars
from .templates import resolve_template
from .types import TypeSpec, VariantSpec


async def _wait_for_fonts_and_stabilize(page: Any) -> None:
    """Wait for fonts to load and stabilize layout before screenshot.

    This ensures deterministic rendering by:
    - Waiting for document.fonts.ready with timeout
    - Forcing layout reflow
    - Using double requestAnimationFrame for paint stability
    """
    with contextlib.suppress(Exception):
        # If fonts.ready is unsupported, exception is swallowed and we continue
        await page.evaluate(f"""() => {{
            // Ensure fonts are loaded with timeout fallback
            const fontReady = document.fonts?.ready || Promise.resolve();
            return Promise.race([
                fontReady,
                new Promise(r => setTimeout(r, {cfg.FONT_TIMEOUT_MS}))
            ]).then(() => {{
                // Force reflow to settle layout
                document.body.offsetHeight;
                // Double requestAnimationFrame for paint stability before screenshot
                return new Promise(resolve => {{
                    requestAnimationFrame(() => {{
                        requestAnimationFrame(resolve);
                    }});
                }});
            }}).catch(() => {{
                // If anything goes wrong, still try to stabilize
                return new Promise(resolve => {{
                    requestAnimationFrame(() => {{
                        requestAnimationFrame(resolve);
                    }});
                }});
            }});
        }}""")


async def _inspect_layout(page: Any, asset_meta: dict[str, Any]) -> None:
    """Inspect layout warnings and update asset metadata."""
    try:
        layout_result = await page.evaluate(LAYOUT_INSPECTION_JS)
        raw_warnings = layout_result.get("warnings", []) if isinstance(layout_result, dict) else []
        asset_meta["layout_warnings"] = list(raw_warnings)
        asset_meta["layout_status"] = aggregate_layout_status(raw_warnings)
    except Exception as layout_err:
        asset_meta["layout_warnings"] = [{"type": "inspection_error", "detail": str(layout_err)}]
        asset_meta["layout_status"] = aggregate_layout_status(asset_meta["layout_warnings"])


async def _capture_screenshot_with_retry(page: Any, output_path: Path) -> None:
    """Capture screenshot with retry logic for transient errors."""
    screenshot_taken = False
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            await page.screenshot(
                path=str(output_path), type="png", full_page=False, omit_background=False
            )
            screenshot_taken = True
            break
        except Exception as screenshot_err:
            last_error = screenshot_err
            # Check if this is a transient error worth retrying
            err_msg = str(screenshot_err).lower()
            is_transient = any(
                pattern in err_msg
                for pattern in (
                    "capturescreenshot",
                    "target closed",
                    "protocol error",
                    "session closed",
                )
            )

            if attempt == 0 and is_transient:
                # Retry once for transient errors
                print("⟳", end="", flush=True)
                await page.wait_for_timeout(200)
                continue

            # For other errors or second attempt, raise
            raise EikonScreenshotError(
                f"Failed to screenshot {output_path.name}: {screenshot_err}",
                recoverable=is_transient,
            ) from screenshot_err

    if not screenshot_taken and last_error is not None:
        raise last_error


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

        # Wait for fonts and stabilize layout (determinism fix)
        await _wait_for_fonts_and_stabilize(page)
        await page.wait_for_timeout(150)

        # Inspect layout warnings
        await _inspect_layout(page, asset_meta)

        # Create output directory and capture screenshot
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await _capture_screenshot_with_retry(page, output_path)

        asset_meta["status"] = "generated"
        if cache is not None:
            cache[cache_key] = input_hash

    except Exception as e:
        asset_meta["status"] = "error"
        warnings = asset_meta.get("warnings")
        if isinstance(warnings, list):
            warnings.append(str(e))
    finally:
        if page:
            await page.close()
        if context:
            await context.close()

    return asset_meta
