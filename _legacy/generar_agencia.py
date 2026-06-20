#!/usr/bin/env python3
"""
Motor EIKON consolidado: genera matriz completa de assets de marca.
Integra validación WCAG AA automática.

Uso:
  python3 generar_agencia.py  # Piloto: pinakotheke-kosmos + prizma-iris
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
MARCAS_DIR = ROOT / "marcas"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"
PILOT_SLUGS = ("pinakotheke-kosmos", "prizma-iris")
TIMEOUT_MS = 18_000
FONT_TIMEOUT_MS = 2_500


def _import_playwright() -> tuple[Any, type[Exception]]:
    """Importa Playwright."""
    try:
        from playwright.async_api import async_playwright, TimeoutError
        return async_playwright, TimeoutError
    except ModuleNotFoundError:
        print("✗ Playwright no está instalado. Instala con: pip install playwright", file=sys.stderr)
        sys.exit(1)


async_playwright, PlaywrightTimeoutError = _import_playwright()


@dataclass(frozen=True)
class VariantSpec:
    """Especificación de una variante."""
    name: str
    label: str


@dataclass(frozen=True)
class TypeSpec:
    """Especificación de un tipo de asset."""
    name: str
    width: int
    height: int
    device_scale_factor: int
    variants: tuple[VariantSpec, ...]

    @property
    def output_width(self) -> int:
        return self.width * self.device_scale_factor

    @property
    def output_height(self) -> int:
        return self.height * self.device_scale_factor


# TAXONOMÍA COMPLETA

CLOUD_ATLAS_TAXONOMIA: dict[str, list[TypeSpec]] = {
    "logos": [
        TypeSpec("lockup_horizontal", 1200, 400, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("lockup_vertical", 800, 800, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("wordmark", 1000, 300, 2, (
            VariantSpec("v1_dark", "Dark"),
            VariantSpec("v2_light", "Light"),
        )),
        TypeSpec("isotipo", 800, 800, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("favicon", 512, 512, 2, (
            VariantSpec("v1_32", "32px"),
            VariantSpec("v2_180", "180px"),
            VariantSpec("v3_512", "512px"),
        )),
        TypeSpec("watermark", 1000, 1000, 2, (
            VariantSpec("v1_light", "Light"),
            VariantSpec("v2_dark", "Dark"),
        )),
    ],
    "banners": [
        TypeSpec("ad_leaderboard", 728, 90, 2, (
            VariantSpec("v1_brand", "Brand"),
            VariantSpec("v2_promo", "Promo"),
            VariantSpec("v3_cta_driven", "CTA"),
        )),
        TypeSpec("ad_rectangle", 300, 250, 2, (
            VariantSpec("v1_visual", "Visual"),
            VariantSpec("v2_data", "Data"),
            VariantSpec("v3_testimonial", "Testimonial"),
        )),
    ],
    "cards": [
        TypeSpec("business_card", 1050, 600, 2, (
            VariantSpec("v1_front", "Front"),
            VariantSpec("v2_back", "Back"),
        )),
        TypeSpec("stat_card", 1080, 1080, 2, (
            VariantSpec("v1_hero_num", "Hero"),
            VariantSpec("v2_dual_stat", "Dual"),
            VariantSpec("v3_graph_abstract", "Graph"),
        )),
    ],
    "og": [
        TypeSpec("og_general", 1200, 630, 2, (
            VariantSpec("v1_website", "Website"),
            VariantSpec("v2_articulo", "Article"),
            VariantSpec("v3_feature", "Feature"),
        )),
    ],
    "stationery": [
        TypeSpec("letterhead", 2480, 3508, 1, (
            VariantSpec("v1_oficial", "Official"),
            VariantSpec("v2_interno", "Internal"),
        )),
    ],
}

PRIZMA_TAXONOMIA: dict[str, list[TypeSpec]] = {
    "logos": [
        TypeSpec("lockup_horizontal", 1200, 400, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("lockup_vertical", 800, 800, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("wordmark", 1000, 300, 2, (
            VariantSpec("v1_dark", "Dark"),
            VariantSpec("v2_light", "Light"),
        )),
        TypeSpec("isotipo", 800, 800, 2, (
            VariantSpec("v1_color", "Color"),
            VariantSpec("v2_mono", "Mono"),
            VariantSpec("v3_inverse", "Inverse"),
        )),
        TypeSpec("favicon", 512, 512, 2, (
            VariantSpec("v1_32", "32px"),
            VariantSpec("v2_180", "180px"),
            VariantSpec("v3_512", "512px"),
        )),
        TypeSpec("watermark", 1000, 1000, 2, (
            VariantSpec("v1_light", "Light"),
            VariantSpec("v2_dark", "Dark"),
        )),
    ],
    "cards": [
        TypeSpec("business_card", 1050, 600, 2, (
            VariantSpec("v1_front", "Front"),
            VariantSpec("v2_back", "Back"),
        )),
        TypeSpec("stat_card", 1080, 1080, 2, (
            VariantSpec("v1_big_data", "BigData"),
            VariantSpec("v2_comparativa", "Comparative"),
            VariantSpec("v3_uptime", "Uptime"),
        )),
    ],
    "og": [
        TypeSpec("og_general", 1200, 630, 2, (
            VariantSpec("v1_docs", "Docs"),
            VariantSpec("v2_enterprise_blog", "Blog"),
            VariantSpec("v3_tool", "Tool"),
        )),
    ],
    "stationery": [
        TypeSpec("letterhead", 2480, 3508, 1, (
            VariantSpec("v1_corporate", "Corporate"),
            VariantSpec("v2_invoice", "Invoice"),
        )),
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    """Carga JSON con validación."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"✗ Error cargando {path}: {e}", file=sys.stderr)
        raise


def brand_family(marca: dict[str, Any]) -> str:
    """Detecta línea de marca (cloud_atlas o prizma)."""
    slug = str(marca.get("slug", "")).lower()
    if "prizma" in slug:
        return "prizma"
    return "cloud_atlas"


def map_marca_to_vars(marca: dict[str, Any], tipo: str) -> dict[str, str]:
    """Mapea datos de marca a variables CSS/data-*."""
    family = brand_family(marca)
    paleta = marca.get("paleta", {})
    if not isinstance(paleta, dict):
        paleta = {}

    # Defaults por línea
    if family == "prizma":
        defaults = {
            "bg": "#0c0e10",
            "primario": "#0c0e10",
            "acento": "#f0b94a",
            "acento_2": "#d4622e",
            "texto": "#f0ece6",
            "font_titulo_name": "Inter",
        }
    else:
        defaults = {
            "bg": "#0b1417",
            "primario": "#0b1417",
            "acento": "#43b5a6",
            "acento_2": "#8d7cc0",
            "texto": "#e8e0d4",
            "font_titulo_name": "Playfair Display",
        }

    tipografia = marca.get("tipografia", {})
    if not isinstance(tipografia, dict):
        tipografia = {}

    logo_simbolo = str(marca.get("logo_simbolo") or marca.get("simbolo") or ("⚡" if family == "prizma" else "∞")).strip()
    logo_texto = str(marca.get("nombre_corporativo") or marca.get("logo_texto") or marca.get("nombre_producto") or "").strip()

    # Textos específicos del tipo (si existen)
    textos = marca.get("textos", {}).get(tipo, {})
    if isinstance(textos, list):
        textos = textos[0] if textos else {}
    if not isinstance(textos, dict):
        textos = {}

    titulo = str(textos.get("titulo") or marca.get("nombre_producto") or "").strip()
    subtitulo = str(textos.get("subtitulo") or marca.get("tagline") or "").strip()
    copy = str(textos.get("copy") or "").strip()
    url = str(marca.get("url_producto") or marca.get("url") or "").strip()

    return {
        "bg": str(paleta.get("bg") or defaults["bg"]),
        "primario": str(paleta.get("primario") or defaults["primario"]),
        "acento": str(paleta.get("acento") or defaults["acento"]),
        "acento_2": str(paleta.get("acento_2") or defaults["acento_2"]),
        "texto": str(paleta.get("texto") or defaults["texto"]),
        "font_titulo": tipografia.get("titulos") or defaults["font_titulo_name"],
        "font_cuerpo": tipografia.get("cuerpo") or "Inter",
        "logo_simbolo": logo_simbolo,
        "logo_texto": logo_texto,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "copy": copy,
        "url": url,
    }


def injection_script(vars_dict: dict[str, str]) -> str:
    """Genera script de inyección de variables."""
    css_map = {
        "--primario": "primario",
        "--acento": "acento",
        "--acento-2": "acento_2",
        "--texto": "texto",
        "--bg": "bg",
        "--font-titulo": "font_titulo",
        "--font-cuerpo": "font_cuerpo",
    }
    attr_map = {
        "data-logo-simbolo": "logo_simbolo",
        "data-logo-texto": "logo_texto",
        "data-titulo": "titulo",
        "data-subtitulo": "subtitulo",
        "data-copy": "copy",
        "data-url": "url",
    }

    lines = [
        "(() => {",
        "  const root = document.documentElement;",
    ]

    for css_var, key in css_map.items():
        value = vars_dict.get(key, "")
        lines.append(f"  root.style.setProperty('{css_var}', '{value}');")

    for attr, key in attr_map.items():
        value = vars_dict.get(key, "")
        lines.append(f"  const els = document.querySelectorAll('[{attr}]');")
        lines.append(f"  els.forEach(el => {{ el.textContent = '{value}'; }});")

    lines.append("})();")

    return "\n".join(lines)


async def render_asset(
    page: Any,
    marca_slug: str,
    categoria: str,
    tipo_spec: TypeSpec,
    variant_spec: VariantSpec,
    marca: dict[str, Any],
    line_prefix: str,
) -> Optional[Path]:
    """Renderiza un asset individual usando una página reutilizable."""

    template_path = TEMPLATES_DIR / f"{line_prefix}_{tipo_spec.name}.html"

    if not template_path.exists():
        return None  # Plantilla no existe

    try:
        # Inyecta variables
        vars_dict = map_marca_to_vars(marca, tipo_spec.name)
        injection = injection_script(vars_dict)

        # Lee plantilla
        html = template_path.read_text(encoding="utf-8")

        # Inyecta script ANTES del cierre </head>
        html = html.replace("</head>", f"<script>{injection}</script></head>")

        # Navega a plantilla con variante en URL
        html_file = template_path.as_uri()
        url = f"{html_file}?variant={variant_spec.name}"

        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # Espera fuentes
        try:
            await page.evaluate(f"""
                () => Promise.race([
                    document.fonts?.ready || Promise.resolve(),
                    new Promise(resolve => setTimeout(resolve, {FONT_TIMEOUT_MS}))
                ])
            """)
        except Exception:
            pass

        await page.wait_for_timeout(100)

        # Renderiza a PNG
        output_path = OUTPUT_DIR / marca_slug / categoria / f"{tipo_spec.name}-v{variant_spec.name.split('_')[0][1:]}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        await page.screenshot(
            path=str(output_path),
            type="png",
            full_page=False,
            omit_background=False,
        )

        return output_path

    except Exception as e:
        print(f"  ⚠ Error renderizando {marca_slug}/{categoria}/{tipo_spec.name}-{variant_spec.name}: {e}")
        return None


async def run_pilot() -> None:
    """Ejecuta piloto completo."""

    # Limpia output previos
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    if (ROOT / "output_agencia").exists():
        shutil.rmtree(ROOT / "output_agencia", ignore_errors=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Contador de assets
    counts: dict[str, dict[str, int]] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )

        try:
            # Crea una página reutilizable
            context = await browser.new_context(locale="es-ES")
            page = await context.new_page()

            try:
                for marca_slug in PILOT_SLUGS:
                    print(f"\n→ Procesando {marca_slug}...")

                    marca_path = MARCAS_DIR / f"{marca_slug}.json"
                    if not marca_path.exists():
                        print(f"  ✗ Marca no encontrada: {marca_path}")
                        continue

                    marca = load_json(marca_path)
                    line_prefix = brand_family(marca)
                    taxonomia = PRIZMA_TAXONOMIA if "prizma" in line_prefix else CLOUD_ATLAS_TAXONOMIA

                    counts[marca_slug] = {}

                    for categoria, type_specs in taxonomia.items():
                        counts[marca_slug][categoria] = 0
                        print(f"  → {categoria}:", end=" ", flush=True)

                        for type_spec in type_specs:
                            for variant_spec in type_spec.variants:
                                # Ajusta viewport antes de cada render
                                await page.set_viewport_size({
                                    "width": type_spec.width,
                                    "height": type_spec.height,
                                })

                                output_path = await render_asset(
                                    page,
                                    marca_slug,
                                    categoria,
                                    type_spec,
                                    variant_spec,
                                    marca,
                                    line_prefix,
                                )

                                if output_path:
                                    counts[marca_slug][categoria] += 1
                                    status = "✓"
                                else:
                                    # Plantilla no existe
                                    status = "⊘"

                                print(status, end="", flush=True)

                        print()

            finally:
                await page.close()
                await context.close()

        finally:
            await browser.close()

    # Validación de contrastes
    print("\n→ Validando contrastes WCAG AA...")
    try:
        from contrast_validator import ContrastValidator

        validator = ContrastValidator(OUTPUT_DIR)
        validator.validate_all()
        validator.write_report(OUTPUT_DIR / "_contraste-report.json")
    except ImportError as e:
        print(f"  ⚠ No se pudo importar validador: {e}")
    except Exception as e:
        print(f"  ⚠ Error en validación: {e}")

    # Reporte final
    print("\n" + "=" * 60)
    print("REPORTE FINAL")
    print("=" * 60)

    for marca_slug in PILOT_SLUGS:
        if marca_slug not in counts:
            continue
        print(f"\n{marca_slug}:")
        for categoria, count in counts[marca_slug].items():
            print(f"  {categoria}: {count} assets")

    # Muestras
    print("\nMUESTRAS POR CATEGORÍA:")
    for marca_slug in PILOT_SLUGS:
        print(f"\n{marca_slug}:")
        marca_output = OUTPUT_DIR / marca_slug
        for categoria in ["logos", "banners", "cards", "og", "stationery"]:
            categoria_path = marca_output / categoria
            if categoria_path.exists():
                pngs = sorted(categoria_path.glob("*.png"))[:2]
                for png in pngs:
                    rel_path = png.relative_to(ROOT)
                    print(f"  {rel_path}")

    print("\nReporte de contrastes: output/_contraste-report.json")


def main() -> int:
    """Punto de entrada."""
    try:
        asyncio.run(run_pilot())
        return 0
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
