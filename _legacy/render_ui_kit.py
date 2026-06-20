#!/usr/bin/env python3
"""Renderiza un UI kit de marca por categorias, no por redes sociales.

Cada categoria genera 10 variantes visualmente distintas por marca e idioma.
La salida queda organizada asi:

  output/<marca>/<locale>/<categoria>/01-<categoria>.png

Uso:
  python render_ui_kit.py --marca steven-vallejo --locale all --variants 10
  python render_ui_kit.py --marca all --locale es --categories banners sliders
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import render as brand_render


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates" / "ui_component.html"
DEFAULT_OUTPUT = ROOT / "output"


CATEGORIES: dict[str, dict[str, Any]] = {
    "banners": {
        "size": (1440, 360),
        "label": {"es": "Banners", "en": "Banners"},
        "purpose": {
            "es": "franjas de alto impacto para portada, campaña o módulo superior",
            "en": "high-impact strips for covers, campaigns, or upper modules",
        },
    },
    "sliders": {
        "size": (1440, 720),
        "label": {"es": "Sliders", "en": "Sliders"},
        "purpose": {
            "es": "diapositivas de producto para carruseles web o recorridos editoriales",
            "en": "product slides for web carousels or editorial walkthroughs",
        },
    },
    "heroes": {
        "size": (1440, 900),
        "label": {"es": "Heroes", "en": "Heroes"},
        "purpose": {
            "es": "primer viewport de sitio, landing o página de producto",
            "en": "first viewport for a site, landing page, or product page",
        },
    },
    "cards": {
        "size": (1080, 720),
        "label": {"es": "Cards", "en": "Cards"},
        "purpose": {
            "es": "tarjetas de producto, proyecto, servicio o frente de portafolio",
            "en": "cards for products, projects, services, or portfolio fronts",
        },
    },
    "logos": {
        "size": (1200, 600),
        "template": "ctas",
        "label": {"es": "Logos", "en": "Logos"},
        "purpose": {
            "es": "lockups, símbolos, wordmarks y firmas de marca",
            "en": "lockups, symbols, wordmarks, and brand signatures",
        },
    },
    "publicaciones": {
        "size": (1200, 1200),
        "template": "cards",
        "label": {"es": "Publicaciones", "en": "Posts"},
        "purpose": {
            "es": "piezas cuadradas para posts, anuncios y carruseles sociales",
            "en": "square pieces for posts, ads, and social carousels",
        },
    },
    "covers": {
        "size": (1280, 720),
        "template": "heroes",
        "label": {"es": "Covers", "en": "Covers"},
        "purpose": {
            "es": "portadas horizontales para video, proyecto o campaña",
            "en": "horizontal covers for videos, projects, or campaigns",
        },
    },
    "ads": {
        "size": (1456, 180),
        "template": "banners",
        "label": {"es": "Ads", "en": "Ads"},
        "purpose": {
            "es": "leaderboards y banners publicitarios compactos",
            "en": "leaderboards and compact ad banners",
        },
    },
    "stories": {
        "size": (1080, 1920),
        "template": "heroes",
        "label": {"es": "Stories", "en": "Stories"},
        "purpose": {
            "es": "piezas verticales para stories, reels y pantallas móviles",
            "en": "vertical pieces for stories, reels, and mobile screens",
        },
    },
    "thumbnails": {
        "size": (1280, 720),
        "template": "heroes",
        "label": {"es": "Thumbnails", "en": "Thumbnails"},
        "purpose": {
            "es": "miniaturas 16:9 para video, documentación o presentación",
            "en": "16:9 thumbnails for video, documentation, or presentations",
        },
    },
    "features": {
        "size": (1200, 720),
        "label": {"es": "Features", "en": "Features"},
        "purpose": {
            "es": "bloques de beneficios, capacidades o puntos diferenciales",
            "en": "blocks for benefits, capabilities, or differentiators",
        },
    },
    "stats": {
        "size": (1200, 620),
        "label": {"es": "Métricas", "en": "Stats"},
        "purpose": {
            "es": "bandas de números, tracción, alcance y evidencia",
            "en": "number bands for traction, scope, reach, and evidence",
        },
    },
    "ctas": {
        "size": (1200, 420),
        "label": {"es": "CTA", "en": "CTA"},
        "purpose": {
            "es": "llamados a la acción para contacto, demo o lectura",
            "en": "calls to action for contact, demos, or reading",
        },
    },
    "testimonials": {
        "size": (1080, 650),
        "label": {"es": "Testimonios", "en": "Testimonials"},
        "purpose": {
            "es": "citas, prueba social y voz editorial",
            "en": "quotes, social proof, and editorial voice",
        },
    },
    "pricing": {
        "size": (1100, 720),
        "label": {"es": "Pricing", "en": "Pricing"},
        "purpose": {
            "es": "planes, niveles de oferta y paquetes de servicio",
            "en": "plans, offer tiers, and service packages",
        },
    },
    "navbars": {
        "size": (1440, 260),
        "label": {"es": "Navegación", "en": "Navigation"},
        "purpose": {
            "es": "headers, menús principales y barras de acceso rápido",
            "en": "headers, main menus, and quick-access bars",
        },
    },
    "footers": {
        "size": (1440, 420),
        "label": {"es": "Footers", "en": "Footers"},
        "purpose": {
            "es": "cierres de página con enlaces, marca y rutas secundarias",
            "en": "page endings with links, brand, and secondary paths",
        },
    },
    "forms": {
        "size": (1000, 720),
        "label": {"es": "Formularios", "en": "Forms"},
        "purpose": {
            "es": "captura de contacto, briefs, solicitudes y registros",
            "en": "capture for contact, briefs, requests, and signups",
        },
    },
}


VARIANT_NAMES = {
    "es": [
        "Presencia principal",
        "Propuesta directa",
        "Ruta editorial",
        "Evidencia visible",
        "Versión clara",
        "Enfoque diagonal",
        "Marco institucional",
        "Sistema modular",
        "Edición de campaña",
        "Minimal esencial",
    ],
    "en": [
        "Primary presence",
        "Direct proposition",
        "Editorial route",
        "Visible evidence",
        "Light version",
        "Diagonal focus",
        "Institutional frame",
        "Modular system",
        "Campaign edition",
        "Essential minimal",
    ],
}


ITEMS = {
    "es": ["Filosofía", "Ciencias", "Ingeniería", "Servicios"],
    "en": ["Philosophy", "Sciences", "Engineering", "Services"],
}


CTA = {
    "es": {
        "banners": "Abrir portal",
        "sliders": "Explorar",
        "heroes": "Ver portafolio",
        "cards": "Ver proyecto",
        "logos": "Usar marca",
        "publicaciones": "Publicar",
        "covers": "Ver portada",
        "ads": "Abrir",
        "stories": "Ver historia",
        "thumbnails": "Ver pieza",
        "features": "Leer mas",
        "stats": "Ver evidencia",
        "ctas": "Contactar",
        "testimonials": "Conocer historia",
        "pricing": "Solicitar propuesta",
        "navbars": "Entrar",
        "footers": "Continuar",
        "forms": "Enviar",
    },
    "en": {
        "banners": "Open portal",
        "sliders": "Explore",
        "heroes": "View portfolio",
        "cards": "View project",
        "logos": "Use brand",
        "publicaciones": "Publish",
        "covers": "View cover",
        "ads": "Open",
        "stories": "View story",
        "thumbnails": "View piece",
        "features": "Read more",
        "stats": "View evidence",
        "ctas": "Contact",
        "testimonials": "Read story",
        "pricing": "Request proposal",
        "navbars": "Enter",
        "footers": "Continue",
        "forms": "Send",
    },
}


def normalize_categories(values: list[str] | None) -> list[str]:
    if not values:
        return list(CATEGORIES)
    unknown = [value for value in values if value not in CATEGORIES]
    if unknown:
        raise SystemExit(f"Categorias no encontradas: {', '.join(unknown)}")
    return values


def locale_list(value: str) -> list[str]:
    value = value.lower()
    if value == "all":
        return list(brand_render.SUPPORTED_LOCALES)
    if value not in brand_render.SUPPORTED_LOCALES:
        raise SystemExit("--locale debe ser es, en o all")
    return [value]


def short(text: str, limit: int) -> str:
    return brand_render.shorten_text(text, limit)


def category_copy(marca: dict, category: str, locale: str, variant: int) -> dict[str, str]:
    meta = CATEGORIES[category]
    name = marca.get("nombre_producto", "Marca")
    tagline = marca.get("tagline", "")
    label = meta["label"][locale]
    angle = VARIANT_NAMES[locale][variant - 1]
    purpose = meta["purpose"][locale]
    url = brand_render.resolve_url(marca)

    compact_categories = {"banners", "ads", "navbars", "footers", "ctas", "logos"}
    if category in compact_categories:
        title = angle
    elif locale == "es":
        title = f"{name}: {angle.lower()}"
    else:
        title = f"{name}: {angle.lower()}"

    if locale == "es":
        subtitle = f"{label} · {purpose}"
        copy = f"{short(tagline, 88)}. Variante {variant:02d} pensada para {purpose}."
    else:
        subtitle = f"{label} · {purpose}"
        copy = f"{short(tagline, 88)}. Variant {variant:02d} designed for {purpose}."

    return {
        "brand": name,
        "symbol": brand_render.normalize_symbol(marca),
        "label": f"{label} {variant:02d}/10",
        "title": short(title, 74),
        "subtitle": short(subtitle, 96),
        "copy": short(copy, 150),
        "cta": CTA[locale][category],
        "meta": url,
        "item_1": ITEMS[locale][0],
        "item_2": ITEMS[locale][1],
        "item_3": ITEMS[locale][2],
        "item_4": ITEMS[locale][3],
    }


def css_vars(marca: dict) -> dict[str, str]:
    paleta = marca.get("paleta", {})
    return {
        "--bg": paleta.get("bg", "#0b1417"),
        "--primario": paleta.get("primario", "#0b1417"),
        "--acento": paleta.get("acento", "#43b5a6"),
        "--acento-2": paleta.get("acento_2", "#e0a85e"),
        "--acento-3": paleta.get("acento_3", "#c0522a"),
        "--texto": paleta.get("texto", "#e8e0d4"),
        "--texto-muted": paleta.get("texto_muted", "#8fa3a8"),
        "--surface": paleta.get("surface", "#152028"),
        "--grad-hero": marca.get("gradiente_hero", "linear-gradient(135deg,#43b5a6,#e0a85e,#c0522a)"),
        "--grad-bg": marca.get("gradiente_bg", "radial-gradient(ellipse at 20% 50%,#152028 0%,#0b1417 60%)"),
        "--font-titulo": brand_render.font_stack(marca.get("tipografia", {}).get("titulos", "Inter"), True),
        "--font-cuerpo": brand_render.font_stack(marca.get("tipografia", {}).get("cuerpo", "Inter"), False),
    }


def inject_js(marca: dict, category: str, locale: str, variant: int) -> str:
    data = category_copy(marca, category, locale, variant)
    vars_dict = css_vars(marca)
    payload = {
        "category": category,
        "template_category": CATEGORIES[category].get("template", category),
        "variant": f"{variant:02d}",
        "lang": locale,
        "vars": vars_dict,
        "data": data,
    }
    return f"""
(() => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  document.documentElement.lang = payload.lang;
  document.body.dataset.category = payload.template_category;
  document.body.dataset.outputCategory = payload.category;
  document.body.dataset.variant = payload.variant;
  for (const [key, value] of Object.entries(payload.vars)) {{
    document.documentElement.style.setProperty(key, value);
  }}
  const setText = (selector, value) => {{
    document.querySelectorAll(selector).forEach((el) => {{
      el.textContent = value || "";
      el.dataset.empty = String(!String(value || "").trim());
    }});
  }};
  setText("[data-ui-brand]", payload.data.brand);
  setText("[data-ui-symbol]", payload.data.symbol);
  setText("[data-ui-label]", payload.data.label);
  setText("[data-ui-title]", payload.data.title);
  setText("[data-ui-subtitle]", payload.data.subtitle);
  setText("[data-ui-copy]", payload.data.copy);
  setText("[data-ui-cta]", payload.data.cta);
  setText("[data-ui-meta]", payload.data.meta);
  setText("[data-ui-item-1]", payload.data.item_1);
  setText("[data-ui-item-2]", payload.data.item_2);
  setText("[data-ui-item-3]", payload.data.item_3);
  setText("[data-ui-item-4]", payload.data.item_4);
  const style = document.createElement("style");
  style.textContent = '[data-empty="true"] {{ display: none !important; }}';
  document.head.appendChild(style);
}})();
"""


async def render_one(browser, marca: dict, category: str, locale: str, variant: int, output_path: Path) -> None:
    width, height = CATEGORIES[category]["size"]
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
    )
    page = await context.new_page()
    try:
        await page.goto(f"file://{TEMPLATE}", wait_until="networkidle", timeout=15000)
        await page.evaluate(inject_js(marca, category, locale, variant))
        try:
            await page.evaluate("() => document.fonts ? document.fonts.ready : null")
        except Exception:
            pass
        await page.wait_for_timeout(120)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(
            path=str(output_path),
            full_page=False,
            clip={"x": 0, "y": 0, "width": width, "height": height},
            type="png",
        )
    finally:
        await page.close()
        await context.close()


def output_path(output_dir: Path, slug: str, locale: str, category: str, variant: int) -> Path:
    return output_dir / slug / locale / category / f"{variant:02d}-{category}.png"


def write_index(output_dir: Path, slug: str, locales: list[str], categories: list[str], variants: int) -> None:
    root = output_dir / slug
    lines = [
        f"# UI kit de marca — {slug}",
        "",
        "Generado por Eikon por categorias de interfaz, no por red social.",
        "",
        f"- Idiomas: {', '.join(locales)}",
        f"- Categorias: {len(categories)}",
        f"- Variantes por categoria: {variants}",
        f"- Total piezas: {len(locales) * len(categories) * variants}",
        "",
    ]

    for locale in locales:
        lines += [f"## {locale}", ""]
        for category in categories:
            label = CATEGORIES[category]["label"].get(locale, category)
            lines += [f"### {label}", ""]
            for variant in range(1, variants + 1):
                rel = Path(locale) / category / f"{variant:02d}-{category}.png"
                lines.append(f"- [{variant:02d} {label}]({rel.as_posix()})")
            lines.append("")

    root.mkdir(parents=True, exist_ok=True)
    (root / "INDICE.md").write_text("\n".join(lines), encoding="utf-8")


async def render_ui_kit(
    slugs: list[str],
    locales: list[str],
    categories: list[str],
    variants: int,
    output_dir: Path,
    concurrency: int,
    verbose: bool,
    skip_existing: bool,
    progress_every: int,
) -> int:
    semaphore = asyncio.Semaphore(concurrency)
    count = 0
    skipped = 0
    completed = 0
    progress_lock = asyncio.Lock()

    async with brand_render.async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            tasks = []
            for slug in slugs:
                marca_base = brand_render.load_marca(slug)
                for locale in locales:
                    marca = brand_render.localized_marca(marca_base, locale)
                    for category in categories:
                        for variant in range(1, variants + 1):
                            out = output_path(output_dir, slug, locale, category, variant)
                            if skip_existing and out.exists():
                                skipped += 1
                                continue

                            async def _render(
                                marca_loc=marca,
                                cat=category,
                                loc=locale,
                                var=variant,
                                op=out,
                                brand_slug=slug,
                            ):
                                nonlocal completed
                                async with semaphore:
                                    if verbose:
                                        print(f"[ui] {brand_slug}/{loc}/{cat}/{var:02d} -> {op}")
                                    await render_one(browser, marca_loc, cat, loc, var, op)
                                    if progress_every:
                                        async with progress_lock:
                                            completed += 1
                                            if completed % progress_every == 0:
                                                print(f"[progress] generated={completed} skipped={skipped}")

                            tasks.append(_render())

            for result in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(result, Exception):
                    raise result
                count += 1
        finally:
            await browser.close()

    if skipped:
        print(f"Saltadas existentes: {skipped}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera UI kits de marca por categorias.")
    parser.add_argument("--marca", required=True, help="Slug de marca o 'all'")
    parser.add_argument("--locale", default="es", help="es, en o all")
    parser.add_argument("--categories", nargs="*", help="Categorias especificas a renderizar")
    parser.add_argument("--variants", type=int, default=10, help="Variantes por categoria (1-10)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--concurrencia", type=int, default=4)
    parser.add_argument("--write-index", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="No imprime una linea por imagen.")
    parser.add_argument("--skip-existing", action="store_true", help="No regenera PNG que ya existen.")
    parser.add_argument("--progress-every", type=int, default=0, help="Imprime progreso cada N imagenes generadas.")
    args = parser.parse_args()

    if not brand_render.PLAYWRIGHT_OK:
        raise SystemExit("Playwright no esta instalado.")
    if args.variants < 1 or args.variants > 10:
        raise SystemExit("--variants debe estar entre 1 y 10")

    categories = normalize_categories(args.categories)
    locales = locale_list(args.locale)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    if args.marca == "all":
        slugs = sorted(path.stem for path in brand_render.MARCAS_DIR.glob("*.json"))
    else:
        slugs = [args.marca]

    total = asyncio.run(
        render_ui_kit(
            slugs,
            locales,
            categories,
            args.variants,
            output_dir,
            args.concurrencia,
            verbose=not args.quiet,
            skip_existing=args.skip_existing,
            progress_every=args.progress_every,
        )
    )

    if args.write_index:
        for slug in slugs:
            write_index(output_dir, slug, locales, categories, args.variants)

    print(f"UI kit generado: {total} piezas")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
