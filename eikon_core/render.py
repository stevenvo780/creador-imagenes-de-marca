from __future__ import annotations

import contextlib
from base64 import b64encode
from pathlib import Path
from typing import Any

from . import constants as cfg
from .cache import compute_hash
from .errors import EikonScreenshotError
from .injection import injection_script, injection_script_with_isotype
from .isotype import IsotypeParams, generate_isotype
from .layout import LAYOUT_INSPECTION_JS, aggregate_layout_status
from .mapping import map_marca_to_vars
from .templates import resolve_template
from .types import TypeSpec, VariantSpec


def _get_default_variant_for_asset_type(asset_type: str) -> str:
    """Get the default variant for a given asset type.

    Used when client-side rendering doesn't have variant planning.
    Fallback logic: use v1_* pattern with sensible defaults per asset type.
    """
    # Map specific asset_types to their preferred default variant
    defaults = {
        "business_card": "v1_front",
        "letterhead": "v1_corporate",
        "stat_card": "v1_big_data",
        # og_general: v1_website (símbolo grande sobre disco) es más fuerte que
        # v1_docs (snippet de código con logo chico) para la preview de enlace.
        "og_general": "v1_website",
        "og_product": "v1_product",
        "ad_rectangle": "v1_visual",
        "favicon": "v3_512",
        "linkedin_header": "v1_institucional",
        "twitter_header": "v1_brand",
    }
    # Return mapped default or generic v1_* pattern
    return defaults.get(asset_type, "v1_color")


def _build_isotype_data_uri(
    style: str,
    seed_hex: str,
    marca: dict[str, Any],
    vars_dict: dict[str, str],
) -> str | None:
    """Genera el SVG procedural del isótipo y lo devuelve como data URI base64.

    Devuelve None para ``style == "none"`` (o vacío), para que el render use el
    mark por defecto del template. Determinístico: el seed deriva del input_hash.
    """
    if not style or style == "none":
        return None
    try:
        initials = str(
            marca.get("logo_texto")
            or marca.get("nombre_producto")
            or marca.get("nombre_corporativo")
            or "E"
        ).strip()
        params = IsotypeParams(
            seed=int(seed_hex[:8], 16),
            style=style,
            brand_initials=(initials[:2] or "E"),
            brand_symbol=str(marca.get("logo_simbolo") or marca.get("simbolo") or "◆"),
            primary_color=vars_dict.get("primario") or vars_dict.get("acento") or "#43b5a6",
            accent_color=vars_dict.get("acento") or "#e0a85e",
            bg_color=vars_dict.get("bg") or "#0f1f1d",
        )
        svg = generate_isotype(params)
        svg_text = svg.strip()
        if not svg_text or not svg_text.startswith("<svg") or "</svg" not in svg_text:
            return None
        return "data:image/svg+xml;base64," + b64encode(svg_text.encode("utf-8")).decode("ascii")
    except Exception:
        return None


def _brand_isotype_seed_hex(marca: dict[str, Any], fallback: str) -> str:
    """Devuelve el seed fijo de la marca en hex, o fallback si no es válido."""
    try:
        seed = int(marca.get("logo_seed", 0))
    except (TypeError, ValueError):
        return fallback
    return hex(seed & 0xFFFF_FFFF_FFFF_FFFF)[2:].zfill(16)


def _extract_data_attrs_from_combination(
    combination_params: dict[str, str] | None,
    asset_type: str = "",
) -> dict[str, str]:
    """Extract data attributes from combination params.

    Maps combination parameter axes to HTML data attributes.
    Always includes data-variant (required for CSS selector matching in templates).

    Args:
        combination_params: Combination parameters dict
        asset_type: Asset type for default variant selection

    Returns:
        Dict of data-* attributes to set on document body element
    """
    data_attrs_to_inject = {}
    if combination_params:
        # Map combination param axes to data attributes
        if "layout" in combination_params:
            data_attrs_to_inject["data-layout"] = combination_params["layout"]
        if "background_treatment" in combination_params:
            data_attrs_to_inject["data-bg-treatment"] = combination_params["background_treatment"]
        if "isotype_style" in combination_params:
            data_attrs_to_inject["data-isotype-style"] = combination_params["isotype_style"]
        if "accent_placement" in combination_params:
            data_attrs_to_inject["data-accent-placement"] = combination_params["accent_placement"]

    # Always set data-variant (critical for CSS selector matching)
    # If specified in params use it, otherwise derive from asset_type
    if combination_params and "variant" in combination_params:
        data_attrs_to_inject["data-variant"] = combination_params["variant"]
    else:
        data_attrs_to_inject["data-variant"] = _get_default_variant_for_asset_type(asset_type)

    return data_attrs_to_inject


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
    combination_params: dict[str, str] | None = None,
    batch_subdir: str | None = None,
    content_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Renderiza un asset individual. Retorna metadata para el manifest.

    Args:
        batch_subdir: Subdirectorio opcional (tipicamente str(batch_id)) entre
            tipo_spec.name y el nombre de archivo. Garantiza que dos batches
            distintos sobre el mismo brand+asset_type no compartan rutas de PNG.
    """
    template_path = resolve_template(tipo_spec.name, cfg.TEMPLATES_DIR)
    if template_path is None:
        return {
            "category": categoria,
            "type": tipo_spec.name,
            "variant": variant_spec.name,
            "status": "error",
            "warnings": ["template not found"],
        }

    vars_dict = map_marca_to_vars(
        marca,
        tipo_spec.name,
        variant_name=variant_spec.name,
        combination_params=combination_params,
    )

    _brand_name = str(marca.get("nombre_producto") or marca.get("nombre_corporativo") or "")
    texts_dict: dict[str, str] | None = None
    if content_overrides:
        texts_dict = {
            "titulo": content_overrides.get("titulo") or vars_dict.get("titulo", ""),
            "subtitulo": content_overrides.get("subtitulo") or vars_dict.get("subtitulo", ""),
            "etiqueta": content_overrides.get("etiqueta") or vars_dict.get("etiqueta", ""),
            "numero": content_overrides.get("numero") or vars_dict.get("numero", ""),
            "copy": content_overrides.get("copy")
            or content_overrides.get("subtitulo")
            or vars_dict.get("copy", ""),
            "url": content_overrides.get("url") or vars_dict.get("url", ""),
            # data-logo-texto = firma de marca (SIEMPRE el nombre); el headline del
            # contenido va por data-titulo (evita duplicar el título en la pieza).
            "logo_texto": content_overrides.get("logo_texto") or _brand_name,
        }

    input_hash = compute_hash(
        marca, categoria, tipo_spec.name, variant_spec.name, template_path, vars_dict
    )
    cache_key = f"{categoria}/{tipo_spec.name}/{variant_spec.name}"
    # Cuando se proporciona batch_subdir, el PNG queda en
    # .../categoria/tipo/batch_subdir/variant.png, aislando batches distintos.
    _type_dir = cfg.OUTPUT_DIR / marca_slug / categoria / tipo_spec.name
    output_path = (
        _type_dir / batch_subdir / f"{variant_spec.name}.png"
        if batch_subdir
        else _type_dir / f"{variant_spec.name}.png"
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
        # Extract and prepare data attributes from combination params
        data_attrs_to_inject = _extract_data_attrs_from_combination(
            combination_params, tipo_spec.name
        )

        # Si la combinación pide un isótipo procedural, generarlo e inyectar el SVG
        # real en el contenedor [data-isotype-container] del template (en vez del
        # mark por defecto). No-op para templates sin ese contenedor.
        brand_isotype_style = str(marca.get("logo_style") or "").strip()
        isotype_style = brand_isotype_style or (combination_params or {}).get(
            "isotype_style", "none"
        )
        seed_hex = _brand_isotype_seed_hex(marca, input_hash) if brand_isotype_style else input_hash
        if isotype_style and isotype_style != "none":
            data_attrs_to_inject["data-isotype-style"] = isotype_style
        isotype_uri = _build_isotype_data_uri(isotype_style, seed_hex, marca, vars_dict)
        if isotype_uri:
            injection = injection_script_with_isotype(
                vars_dict,
                isotype_svg=isotype_uri,
                variant_name=variant_spec.name,
                template_name=tipo_spec.name,
                data_attrs=data_attrs_to_inject if data_attrs_to_inject else None,
                texts_dict=texts_dict,
            )
        else:
            injection = injection_script(
                vars_dict,
                variant_name=variant_spec.name,
                template_name=tipo_spec.name,
                data_attrs=data_attrs_to_inject if data_attrs_to_inject else None,
                texts_dict=texts_dict,
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
