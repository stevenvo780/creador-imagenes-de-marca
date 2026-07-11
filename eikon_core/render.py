from __future__ import annotations

import contextlib
import re
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

# Security constants
MAX_LOGO_ASSET_BYTES = 5 * 1024 * 1024  # 5 MB limit for logo assets


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


_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOGO_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _validate_path_not_traversal(path_str: str) -> bool:
    """Valida que el path no intente path traversal (contiene .. o empieza con /)."""
    return not (".." in path_str or path_str.startswith("/"))


def _resolve_logo_asset(path_str: str) -> Path | None:
    """Resuelve la ruta de un logo real: absoluta, o relativa al repo/marcas.

    Valida contra path traversal: rechaza paths con ".." o que comiencen con "/".
    """
    # Validación de seguridad contra path traversal
    if not _validate_path_not_traversal(path_str):
        return None

    p = Path(path_str)
    candidates = [p] if p.is_absolute() else [_REPO_ROOT / p, cfg.MARCAS_DIR / p, cfg.MARCAS_DIR.parent / p]
    for c in candidates:
        with contextlib.suppress(Exception):
            if c.is_file():
                # Extra safety: verify the resolved path is within expected bounds
                try:
                    c_resolved = c.resolve()
                    # Allow paths within REPO_ROOT, MARCAS_DIR, or their parents
                    repo_root = _REPO_ROOT.resolve()
                    marcas_parent = cfg.MARCAS_DIR.resolve().parent
                    if not (str(c_resolved).startswith(str(repo_root)) or
                            str(c_resolved).startswith(str(marcas_parent))):
                        continue
                except Exception:
                    continue
                return c
    return None


def _sanitize_svg_content(svg_text: str) -> str | None:
    """Sanitiza contenido SVG removiendo scripts y event handlers potencialmente peligrosos.

    Rechaza SVGs que contienen:
    - Elementos <script>
    - Event handlers (onclick, onload, etc.)
    - Referencias externas vía xlink:href a URLs no-data:
    """
    if not svg_text:
        return None

    # Rechazar si contiene <script>
    if re.search(r"<script[^>]*>", svg_text, re.IGNORECASE):
        return None

    # Rechazar si contiene event handlers HTML (onclick, onload, onerror, etc.)
    if re.search(r"\s+on\w+\s*=", svg_text, re.IGNORECASE):
        return None

    # Rechazar si contiene xlink:href no-data (SSRF risk)
    if re.search(r"xlink:href\s*=\s*['\"](?!data:)", svg_text, re.IGNORECASE):
        return None

    return svg_text


def _load_logo_asset_data_uri(path_str: str) -> str | None:
    """Carga un logo de marca pre-existente (SVG/PNG/JPG) como data URI.

    Permite que Eikón ADOPTE la imagen de marca oficial de un producto (ej. el
    isotipo de Ágora/Elenxos) en vez de generar uno procedural. También sirve para
    logos creados por profesionales que el usuario quiera inyectar.

    Valida:
    - Tamaño máximo de archivo (MAX_LOGO_ASSET_BYTES)
    - Para SVGs: contenido sin scripts o event handlers
    """
    f = _resolve_logo_asset(path_str)
    if f is None:
        return None
    mime = _LOGO_MIME.get(f.suffix.lower())
    if mime is None:
        return None
    with contextlib.suppress(Exception):
        # Validar tamaño del archivo
        file_size = f.stat().st_size
        if file_size > MAX_LOGO_ASSET_BYTES:
            return None

        data = f.read_bytes()
        if not data:
            return None

        # Para SVGs, sanitizar contenido
        if mime == "image/svg+xml":
            try:
                svg_text = data.decode("utf-8")
                if _sanitize_svg_content(svg_text) is None:
                    # SVG contiene contenido peligroso, rechazar
                    return None
            except (UnicodeDecodeError, Exception):
                return None

        return f"data:{mime};base64," + b64encode(data).decode("ascii")
    return None


def _build_isotype_data_uri(
    style: str,
    seed_hex: str,
    marca: dict[str, Any],
    vars_dict: dict[str, str],
) -> str | None:
    """Devuelve el isótipo como data URI base64.

    Prioridad: si la marca declara ``logo_asset`` (ruta a un logo real/oficial),
    se usa ese archivo (adopta marcas pre-existentes). Si no, genera el isótipo
    procedural determinístico. Devuelve None si no hay ni asset ni estilo válido.
    """
    asset = str(marca.get("logo_asset") or "").strip()
    if asset:
        uri = _load_logo_asset_data_uri(asset)
        if uri:
            return uri
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


async def render_asset(  # noqa: C901
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

    # Validar batch_subdir contra path traversal
    if batch_subdir and (".." in batch_subdir or batch_subdir.startswith(("/", "\\"))):
        return {
            "category": categoria,
            "type": tipo_spec.name,
            "variant": variant_spec.name,
            "status": "error",
            "warnings": ["invalid batch_subdir: path traversal detected"],
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
