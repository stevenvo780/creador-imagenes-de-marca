#!/usr/bin/env python3
"""
Motor Eikon v2: Generador de matriz completa de assets de marca.

Renderiza todos los assets definidos en MASTER-TAXONOMIA.md usando Playwright.
- Input: plantillas HTML en templates/, marcas JSON en marcas/
- Output: PNGs @2x organizados en output/{marca}/{categoria}/{tipo}-v{N}.png
- Validación: Reporte de contrastes WCAG AA en output/_contraste-report.json

Uso:
  python generar_agencia_v2.py                           # Todas las marcas
  python generar_agencia_v2.py --marca pinakotheke-kosmos
  python generar_agencia_v2.py --solo logos --solo banners
  python generar_agencia_v2.py --variants 1-2            # Solo v1, v2
  python generar_agencia_v2.py --sin-contraste           # Sin validación
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import site
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
MARCAS_DIR = ROOT / "marcas"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"
OUTPUT_AGENCIA_DIR = ROOT / "output_agencia"

TIMEOUT_MS = 20_000
FONT_TIMEOUT_MS = 2_500
RETRIES = 2

TAXONOMIA_CANONICA: dict[str, dict[str, int]] = {
    "logos": {
        "lockup_horizontal": 3,
        "lockup_vertical": 3,
        "wordmark": 2,
        "isotipo": 3,
        "favicon": 3,
        "watermark": 2,
    },
    "banners": {
        "linkedin_banner": 3,
        "x_header": 3,
        "yt_banner": 3,
        "web_hero": 4,
        "web_hero_mobile": 4,
        "ad_leaderboard": 3,
        "ad_rectangle": 3,
    },
    "cards": {
        "business_card": 2,
        "stat_card": 3,
    },
    "social": {
        "linkedin_post": 6,
        "instagram_post": 8,
        "x_post": 3,
        "facebook_post": 3,
        "tiktok_cover": 3,
        "yt_thumbnail": 3,
        "ig_reel_cover": 3,
    },
    "stories": {
        "instagram_story": 5,
    },
    "carousels": {
        "instagram_carousel": 5,
    },
    "og": {
        "og_general": 3,
    },
    "stationery": {
        "letterhead": 2,
    },
}

VARIANT_NAMES: dict[str, list[str]] = {
    "lockup_horizontal": ["v1_color", "v2_mono", "v3_inverse"],
    "lockup_vertical": ["v1_color", "v2_mono", "v3_inverse"],
    "wordmark": ["v1_dark", "v2_light"],
    "isotipo": ["v1_color", "v2_mono", "v3_inverse"],
    "favicon": ["v1_32", "v2_180", "v3_512"],
    "watermark": ["v1_light", "v2_dark"],
    "linkedin_banner": ["v1_institucional", "v2_producto", "v3_evento"],
    "x_header": ["v1_brand", "v2_lanzamiento", "v3_comunidad"],
    "yt_banner": ["v1_visual", "v2_grid", "v3_textual"],
    "web_hero": ["v1_split", "v2_central", "v3_video_fallback", "v4_minimal"],
    "web_hero_mobile": ["v1_cover", "v2_focus", "v3_cta", "v4_minimal"],
    "ad_leaderboard": ["v1_brand", "v2_promo", "v3_cta_driven"],
    "ad_rectangle": ["v1_visual", "v2_data", "v3_testimonial"],
    "business_card": ["v1_front", "v2_back"],
    "stat_card": ["v1_hero_num", "v2_dual_stat", "v3_graph_abstract"],
    "linkedin_post": ["v1_tesis", "v2_framework", "v3_insight", "v4_noticia", "v5_equipo", "v6_informe"],
    "instagram_post": ["v1_tesis", "v2_diferenciador", "v3_dato", "v4_cita", "v5_cta", "v6_case_study", "v7_testimonial", "v8_promocion"],
    "x_post": ["v1_hilo", "v2_principal", "v3_quote"],
    "facebook_post": ["v1_editorial", "v2_comunidad", "v3_evento"],
    "instagram_story": ["v1_cover", "v2_text_block", "v3_poll_ready", "v4_qna", "v5_swipe_up"],
    "instagram_carousel": ["v1_portada", "v2_paso", "v3_continuo", "v4_destacado", "v5_cierre"],
    "tiktok_cover": ["v1_hook", "v2_stat", "v3_cta"],
    "yt_thumbnail": ["v1_visual", "v2_textual", "v3_data"],
    "ig_reel_cover": ["v1_cover", "v2_quote", "v3_series"],
    "og_general": ["v1_website", "v2_articulo", "v3_feature"],
    "letterhead": ["v1_oficial", "v2_interno"],
}

TEXT_ALIAS: dict[str, tuple[str, ...]] = {
    "instagram_post": ("instagram_post", "ig_post"),
    "instagram_story": ("instagram_story", "ig_story"),
    "instagram_carousel": ("instagram_carousel", "ig_carousel"),
    "facebook_post": ("facebook_post", "fb_cover"),
    "ad_leaderboard": ("ad_leaderboard", "banner_ad"),
    "ig_reel_cover": ("ig_reel_cover",),
}


def _prefer_repo_python() -> None:
    """Detecta venv local y reejcuta si es necesario."""
    if os.environ.get("EIKON_REEXEC") == "1":
        return
    candidates = (ROOT / "venv2" / "bin" / "python", ROOT / "venv" / "bin" / "python")
    current = Path(sys.executable).resolve()
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != current:
            os.environ["EIKON_REEXEC"] = "1"
            os.execv(str(candidate), [str(candidate), *sys.argv])


_prefer_repo_python()


def _import_playwright() -> tuple[Any, type[Exception], type[Exception]]:
    """Importa Playwright con fallback a site-packages."""
    try:
        from playwright.async_api import Error, TimeoutError, async_playwright
        return async_playwright, TimeoutError, Error
    except ModuleNotFoundError:
        candidates: list[Path] = []
        try:
            candidates.append(Path(site.getusersitepackages()))
        except Exception:
            pass
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        candidates.append(Path.home() / ".local" / "lib" / version / "site-packages")
        for candidate in candidates:
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.append(str(candidate))
        from playwright.async_api import Error, TimeoutError, async_playwright
        return async_playwright, TimeoutError, Error


async_playwright, PlaywrightTimeoutError, PlaywrightError = _import_playwright()


class EikonError(Exception):
    """Error base del motor Eikon."""
    def __init__(self, message: str, path: Optional[Path] = None, line: int = 0):
        self.message = message
        self.path = path
        self.line = line
        super().__init__(f"{path or 'eikon'}:{line}: {message}")


def limpiar_output() -> None:
    """Limpia carpetas output/ y output_agencia/ usando shutil."""
    for dir_path in [OUTPUT_DIR, OUTPUT_AGENCIA_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
    print("✓ Limpieza completada: output/ y output_agencia/ listos", flush=True)


def parse_taxonomia() -> dict[str, dict[str, int]]:
    """Retorna la taxonomía canónica de plantillas sin prefijos por línea."""
    return {
        "Cloud Atlas": TAXONOMIA_CANONICA,
        "Prizma": TAXONOMIA_CANONICA,
    }


def brand_line(marca: dict[str, Any]) -> str:
    slug = str(marca.get("slug", "")).lower()
    corporate = str(marca.get("nombre_corporativo", "")).lower()
    if slug.startswith("prizma") or "prizma" in corporate:
        return "prizma"
    return "cloud"


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = (hex_color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def auto_text_color(bg_hex: str, line: str) -> str:
    r, g, b = hex_to_rgb(bg_hex)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    if line == "prizma":
        return "#0c0e10" if luminance > 128 else "#f0ece6"
    return "#0b1417" if luminance > 128 else "#e8e0d4"


def normalize_url(url: str) -> str:
    url = " ".join((url or "").strip().split())
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.rstrip("/")


def resolve_url(marca: dict[str, Any]) -> str:
    return normalize_url(
        marca.get("url_producto")
        or marca.get("url")
        or marca.get("url_corporativa")
        or ""
    )


def resolve_symbol(marca: dict[str, Any]) -> str:
    raw = str(marca.get("logo_simbolo") or marca.get("simbolo") or "").strip()
    if raw.startswith("lemniscata"):
        return "∞"
    if raw:
        return raw
    slug = str(marca.get("slug", "")).lower()
    if slug.startswith("prizma"):
        return "⚡"
    if slug in ("pinakotheke", "steven-vallejo"):
        return "∞"
    return "•"


def resolve_logo_text(marca: dict[str, Any]) -> str:
    return str(
        marca.get("logo_texto")
        or marca.get("nombre_producto")
        or marca.get("nombre_corporativo")
        or ""
    )


def resolve_textos(marca: dict[str, Any], tipo: str) -> dict[str, Any]:
    textos_all = marca.get("textos", {})
    aliases = TEXT_ALIAS.get(tipo, (tipo,))
    for key in aliases:
        textos = textos_all.get(key)
        if isinstance(textos, list):
            return textos[0] if textos else {}
        if isinstance(textos, dict):
            return textos
    return {}


def variant_name_for(tipo: str, variant_num: int) -> str:
    variants = VARIANT_NAMES.get(tipo, [])
    if 1 <= variant_num <= len(variants):
        return variants[variant_num - 1]
    return f"v{variant_num}_default"


def enumerate_matrix(args: argparse.Namespace) -> list[tuple[str, str, str, int]]:
    """
    Enumera la matriz completa de assets a renderizar.
    Retorna: [(marca_slug, categoria, tipo, variant_num), ...]

    Filtra según argumentos CLI:
    - --marca: solo una marca
    - --solo: solo categorías especificadas
    - --variants: rango de variantes (ej: 1-2)
    """
    taxonomy = parse_taxonomia()

    # Carga marcas (excepto agora-*)
    marca_paths = sorted(p for p in MARCAS_DIR.glob("*.json")
                        if p.stem != "agora" and not p.stem.startswith("agora-"))

    matriz = []

    for marca_path in marca_paths:
        marca_slug = marca_path.stem

        # Filtro --marca
        if args.marca and marca_slug != args.marca:
            continue

        # Determina sección (Cloud Atlas o Prizma)
        section = "Prizma" if marca_slug.startswith("prizma") else "Cloud Atlas"
        if section not in taxonomy:
            continue

        section_tax = taxonomy[section]

        for categoria, tipos in section_tax.items():
            # Filtro --solo
            if args.solo and categoria not in args.solo:
                continue

            for tipo, num_variants in tipos.items():
                # Filtro --variants
                variants_to_render = parse_variants_range(args.variants, num_variants)

                for variant_num in variants_to_render:
                    matriz.append((marca_slug, categoria, tipo, variant_num))

    return matriz


def parse_variants_range(variants_arg: Optional[str], max_variant: int) -> list[int]:
    """Parsea --variants <N> o <N-M> y retorna lista de números."""
    if not variants_arg:
        return list(range(1, max_variant + 1))

    if "-" in variants_arg:
        parts = variants_arg.split("-")
        if len(parts) == 2:
            try:
                start = int(parts[0])
                end = int(parts[1])
                return list(range(start, min(end + 1, max_variant + 1)))
            except ValueError:
                pass
    else:
        try:
            n = int(variants_arg)
            return [n] if n <= max_variant else []
        except ValueError:
            pass

    return list(range(1, max_variant + 1))


def load_marca_json(marca_slug: str) -> dict[str, Any]:
    """Carga y parsea JSON de marca."""
    marca_path = MARCAS_DIR / f"{marca_slug}.json"
    if not marca_path.exists():
        raise EikonError(f"Marca JSON no encontrada", marca_path)

    try:
        return json.loads(marca_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise EikonError(f"JSON inválido: {e.msg}", marca_path, e.lineno)


def map_marca_to_css_vars(marca: dict[str, Any]) -> dict[str, str]:
    """Mapea datos de marca JSON a variables CSS para inyección."""
    paleta = marca.get("paleta", {})
    tipografia = marca.get("tipografia", {})
    line = brand_line(marca)

    # Defaults por línea
    if line == "prizma":
        defaults = {
            "bg": "#0c0e10",
            "primario": "#f0b94a",
            "acento": "#d4622e",
            "acento_2": "#e94b3c",
            "acento_3": "#43b5a6",
            "texto": "#f0ece6",
            "texto_muted": "#a09080",
            "surface": "#16120e",
            "grad_hero": "linear-gradient(135deg, #f0b94a 0%, #d4622e 55%, #e94b3c 100%)",
            "font_titulo": "Inter",
        }
    else:
        defaults = {
            "bg": "#0b1417",
            "primario": "#0b1417",
            "acento": "#43b5a6",
            "acento_2": "#8d7cc0",
            "acento_3": "#A3E4D7",
            "texto": "#e8e0d4",
            "texto_muted": "#8fa3a8",
            "surface": "#131e22",
            "grad_hero": "linear-gradient(135deg, #43b5a6 0%, #8d7cc0 60%, #4a3a80 100%)",
            "font_titulo": "Playfair Display",
        }

    bg = paleta.get("bg") or defaults["bg"]
    text_auto = auto_text_color(bg, line)
    gradient_hero = marca.get("gradiente_hero") or defaults["grad_hero"]
    font_titulo = tipografia.get("titulos") or defaults["font_titulo"]
    font_cuerpo = tipografia.get("cuerpo") or "Inter"

    css_vars = {
        "--bg": bg,
        "--primario": paleta.get("primario") or defaults["primario"],
        "--acento": paleta.get("acento") or defaults["acento"],
        "--acento-2": paleta.get("acento_2") or defaults["acento_2"],
        "--acento-3": paleta.get("acento_3") or defaults["acento_3"],
        "--texto": paleta.get("texto") or defaults["texto"],
        "--texto-muted": paleta.get("texto_muted") or defaults["texto_muted"],
        "--surface": paleta.get("surface") or defaults["surface"],
        "--gradient-hero": gradient_hero,
        "--grad-hero": gradient_hero,
        "--grad-bg": marca.get("gradiente_bg") or f"radial-gradient(circle at 20% 20%, {paleta.get('surface') or defaults['surface']} 0%, {bg} 70%)",
        "--font-titulo": f"'{font_titulo}', Georgia, serif" if line == "cloud" and font_titulo != "Inter" else f"'{font_titulo}', Inter, system-ui, sans-serif",
        "--font-cuerpo": f"'{font_cuerpo}', Inter, system-ui, sans-serif",
        "--texto-auto": text_auto,
        "--contrast-text": text_auto,
        "--contrast-dark": "#0c0e10" if line == "prizma" else "#0b1417",
        "--contrast-light": "#f0ece6" if line == "prizma" else "#e8e0d4",
    }

    return css_vars


def injection_script(css_vars: dict[str, str], data_attrs: dict[str, str], body_attrs: dict[str, str]) -> str:
    """Genera script JS que inyecta CSS vars y data-* attributes."""
    lines = ["(() => {", "  const root = document.documentElement;"]

    for css_var, value in css_vars.items():
        lines.append(f"  root.style.setProperty({json.dumps(css_var)}, {json.dumps(value)});")

    lines.append("  const body = document.body;")
    for attr, value in body_attrs.items():
        lines.append(f"  body.setAttribute({json.dumps(attr)}, {json.dumps(value)});")

    for attr, value in data_attrs.items():
        value_safe = str(value or "").replace("\n", " ")
        lines.append(
            f"  document.querySelectorAll({json.dumps(f'[{attr}]')}).forEach((el) => {{"
            f" el.textContent = {json.dumps(value_safe)};"
            f" el.dataset.empty = String(!String({json.dumps(value_safe)}).trim());"
            f" }});"
        )

    lines.append(
        r"""
  const style = document.createElement("style");
  style.textContent = `
    [data-empty="true"] { display: none !important; }
    [data-fit], [data-titulo], [data-subtitulo], [data-copy] {
      min-width: 0;
      overflow-wrap: break-word;
      text-rendering: geometricPrecision;
    }
  `;
  document.head.appendChild(style);

  const fit = (el) => {
    const min = Number(el.dataset.fitMin || 12);
    let style = window.getComputedStyle(el);
    let size = Number.parseFloat(style.fontSize);
    if (!Number.isFinite(size)) return;
    const overflows = () => {
      const overX = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
      return overX;
    };
    for (let i = 0; i < 100 && size > min && overflows(); i += 1) {
      size -= 1;
      el.style.fontSize = `${size}px`;
    }
  };
  window.__fitBrandText = () => document.querySelectorAll("[data-fit]").forEach(fit);
  if (typeof window.__eikonRuntimeRefresh === "function") window.__eikonRuntimeRefresh();
  window.__fitBrandText();
})();
"""
    )
    return "\n".join(lines)


async def launch_browser(playwright: Any) -> Any:
    """Lanza instancia de Chromium/Chrome con opciones sandbox."""
    chromium_cache = Path.home() / ".cache" / "ms-playwright" / "chromium-1223" / "chrome-linux64" / "chrome"
    launch_options = []

    if chromium_cache.exists():
        launch_options.append({"executable_path": str(chromium_cache)})

    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if chrome:
        launch_options.append({"executable_path": chrome})

    launch_options.append({"channel": "chrome"})
    launch_options.append({})

    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]

    errors: list[str] = []
    for options in launch_options:
        try:
            return await playwright.chromium.launch(
                headless=True,
                args=launch_args,
                chromium_sandbox=False,
                **options,
            )
        except Exception as exc:
            label = ", ".join(f"{k}={v}" for k, v in options.items()) or "bundled chromium"
            errors.append(f"{label}: {exc}")

    raise EikonError("No se pudo iniciar Chromium/Chrome: " + " | ".join(errors))


def get_asset_dimensions(tipo: str) -> tuple[int, int, int]:
    """Retorna (width, height, device_scale_factor) para un tipo de asset."""
    dims = {
        "lockup_horizontal": (1200, 400, 2),
        "lockup_vertical": (800, 800, 2),
        "wordmark": (1000, 300, 2),
        "isotipo": (800, 800, 2),
        "favicon": (512, 512, 2),
        "watermark": (1000, 1000, 2),
        "linkedin_banner": (1584, 396, 1),
        "x_header": (1500, 500, 2),
        "yt_banner": (2560, 1440, 1),
        "web_hero": (1920, 600, 2),
        "web_hero_mobile": (1080, 1920, 2),
        "ad_leaderboard": (728, 90, 2),
        "ad_rectangle": (300, 250, 2),
        "business_card": (1050, 600, 2),
        "stat_card": (1080, 1080, 2),
        "instagram_post": (1080, 1080, 2),
        "linkedin_post": (1200, 627, 2),
        "x_post": (1200, 675, 2),
        "facebook_post": (1200, 630, 2),
        "instagram_story": (1080, 1920, 2),
        "instagram_carousel": (1080, 1080, 2),
        "tiktok_cover": (1080, 1920, 2),
        "yt_thumbnail": (1280, 720, 2),
        "ig_reel_cover": (1080, 1920, 2),
        "og_general": (1200, 630, 2),
        "letterhead": (2480, 3508, 1),
    }
    return dims.get(tipo, (1200, 600, 2))


async def render_asset_full(
    browser: Any,
    marca_slug: str,
    categoria: str,
    tipo: str,
    variant_num: int,
) -> Path:
    """Renderiza un asset individual y lo guarda."""

    # Carga marca
    marca = load_marca_json(marca_slug)
    marca.setdefault("slug", marca_slug)

    # Busca plantilla
    template_name = f"{tipo}.html"
    template_path = TEMPLATES_DIR / template_name

    if not template_path.exists():
        raise EikonError(f"Plantilla no encontrada: {template_name}", template_path)

    # Dimensiones
    width, height, scale = get_asset_dimensions(tipo)

    # Variables CSS y data-*
    css_vars = map_marca_to_css_vars(marca)
    textos = resolve_textos(marca, tipo)
    line = brand_line(marca)
    logo_text = resolve_logo_text(marca)
    symbol = resolve_symbol(marca)
    titulo = textos.get("titulo") or marca.get("nombre_producto") or logo_text
    subtitulo = textos.get("subtitulo") or marca.get("tagline") or marca.get("nombre_corporativo") or ""
    copy = textos.get("copy") or marca.get("descripcion") or marca.get("tagline") or ""
    url = textos.get("url") or resolve_url(marca)
    data_attrs = {
        "data-titulo": str(titulo),
        "data-subtitulo": str(subtitulo),
        "data-copy": str(copy),
        "data-logo-simbolo": symbol,
        "data-logo-texto": logo_text,
        "data-numero": str(textos.get("numero") or textos.get("metric") or "01"),
        "data-etiqueta": str(textos.get("etiqueta") or textos.get("label") or subtitulo or "Sistema"),
        "data-autor": str(textos.get("autor") or marca.get("autor") or marca.get("nombre_corporativo") or logo_text),
        "data-cargo": str(textos.get("cargo") or marca.get("cargo") or subtitulo or ""),
        "data-url": str(url),
        "data-acento": str(marca.get("paleta", {}).get("acento") or ""),
        "data-acento-2": str(marca.get("paleta", {}).get("acento_2") or ""),
    }
    body_attrs = {
        "data-brand-line": line,
        "data-slug": marca_slug,
        "data-template": tipo,
    }

    # Contexto Playwright
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=scale,
        reduced_motion="reduce",
        locale="es-ES",
    )
    page = await context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    try:
        # Navega a plantilla con variante en URL
        variant_name = variant_name_for(tipo, variant_num)
        url = template_path.resolve().as_uri() + f"?variant={variant_name}"

        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # Inyecta variables
        await page.evaluate(injection_script(css_vars, data_attrs, body_attrs))

        # Espera fuentes
        try:
            await page.evaluate(
                f"() => Promise.race(["
                f"document.fonts ? document.fonts.ready : Promise.resolve(), "
                f"new Promise((resolve) => setTimeout(resolve, {FONT_TIMEOUT_MS}))"
                f"])"
            )
        except Exception:
            pass

        await page.wait_for_timeout(120)

        # Fit text
        await page.evaluate("() => window.__fitBrandText && window.__fitBrandText()")

        if page_errors:
            raise EikonError(f"Errores JS en página: {page_errors[0]}", template_path)

        # Screenshot
        output_path = OUTPUT_DIR / marca_slug / categoria / f"{tipo}-v{variant_num}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        await page.screenshot(
            path=str(output_path),
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": width, "height": height},
            omit_background=("isotipo" in tipo or "favicon" in tipo or "watermark" in tipo),
            animations="disabled",
        )

        return output_path

    finally:
        await page.close()
        await context.close()


async def run(args: argparse.Namespace) -> int:
    """Loop principal: limpia, enumera, renderiza."""

    try:
        # Limpia output
        limpiar_output()

        # Enumera matriz
        matriz = enumerate_matrix(args)
        if not matriz:
            print("✗ Matriz vacía. Verifica los filtros --marca y --solo.", file=sys.stderr)
            return 1

        print(f"ℹ Renderizando {len(matriz)} assets...", flush=True)

        # Browser
        async with async_playwright() as pw:
            browser = await launch_browser(pw)
            errors: list[EikonError] = []

            try:
                for idx, (marca_slug, categoria, tipo, variant_num) in enumerate(matriz, 1):
                    try:
                        output_path = await render_asset_full(
                            browser, marca_slug, categoria, tipo, variant_num
                        )
                        rel_path = output_path.relative_to(ROOT)
                        print(f"✓ [{idx}/{len(matriz)}] {rel_path}", flush=True)
                    except EikonError as exc:
                        errors.append(exc)
                        print(f"✗ {exc}", file=sys.stderr, flush=True)
                    except Exception as exc:
                        errors.append(EikonError(f"{type(exc).__name__}: {exc}"))
                        print(f"✗ {exc}", file=sys.stderr, flush=True)

            finally:
                await browser.close()

        if errors and len(errors) > 0:
            print(f"\n✗ {len(errors)} errores durante render", file=sys.stderr)
            return 1

        # Validación de contrastes
        if not args.sin_contraste:
            print("\nℹ Ejecutando validación de contrastes...", flush=True)
            try:
                from contrast_validator import ContrastValidator
                validator = ContrastValidator(OUTPUT_DIR)
                validator.validate_all()
                validator.write_report(OUTPUT_DIR / "_contraste-report.json")
                print(f"✓ Reporte guardado en output/_contraste-report.json", flush=True)
            except ImportError:
                print("⚠ Validador de contrastes no disponible (contrast_validator.py)", flush=True)
            except Exception as e:
                print(f"⚠ Error en validación: {e}", flush=True)

        print("\n✓ Proceso completado exitosamente", flush=True)
        return 0

    except EikonError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"✗ Error inesperado: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    """Parsea argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Motor Eikon: genera matriz de assets de marca (Pinakotheke + Prizma)"
    )
    parser.add_argument(
        "--marca",
        help="Procesa solo una marca (ej: pinakotheke-kosmos)",
    )
    parser.add_argument(
        "--solo",
        action="append",
        dest="solo",
        help="Procesa solo categorías especificadas (repetible: --solo logos --solo banners)",
    )
    parser.add_argument(
        "--variants",
        help="Rango de variantes: N (una) o N-M (rango). Ej: 1 o 1-2",
    )
    parser.add_argument(
        "--sin-contraste",
        action="store_true",
        help="NO ejecuta validador de contrastes",
    )

    return parser.parse_args()


def main() -> int:
    """Entry point."""
    try:
        return asyncio.run(run(parse_args()))
    except EikonError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"✗ Error fatal: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
