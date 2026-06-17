#!/usr/bin/env python3
"""
render_hires.py — Regenera og_product a 2x (2400x1260) y genera og_portrait (1080x1350)
para los productos del showcase de mi-cv.

Uso:
  python render_hires.py
  python render_hires.py --dry-run      # solo lista lo que haría
  python render_hires.py --portrait-only
  python render_hires.py --hires-only

Salida:
  /workspace/Stev/mi-cv/public/brand/<slug>/og_product.png   — 2400x1260 (reemplaza 1200x630)
  /workspace/Stev/mi-cv/public/brand/<slug>/portrait.png     — 1080x1350 (solo productos chicos)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT          = Path(__file__).resolve().parent
TMPL_DIR      = ROOT / "templates"
MARCAS_DIR    = ROOT / "marcas"
BRAND_OUT     = Path("/workspace/Stev/mi-cv/public/brand")

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False


# ── Mapping: brand-dir-slug → marca-json-slug ─────────────────────────────────
# Keys = directory name under public/brand/
# Values = marca JSON slug under marcas/
HIRES_MAP: dict[str, str] = {
    "paideia":                    "pinakotheke-paideia",
    "agon":                       "pinakotheke-agon",
    "estructuras-preontologicas": "pinakotheke-estructuras-preontologicas",
    "hinton":                     "pinakotheke-hinton",
    "kosmos":                     "pinakotheke-kosmos",
    "aporia":                     "pinakotheke-aporia",
    "organon":                    "pinakotheke-organon",
    "daimon":                     "pinakotheke-daimon",
    "techne":                     "pinakotheke-techne",
    "koinonia":                   "pinakotheke-koinonia",
    "ergon":                      "pinakotheke-ergon",
    "chronos":                    "pinakotheke-chronos",
    "xenia":                      "pinakotheke-xenia",
    "nomos":                      "pinakotheke-nomos",
    "apotheke":                   "pinakotheke-apotheke",
    "eikon":                      "pinakotheke-eikon",
    "prizma":                     "prizma",
    "agora":                      "agora",
}

# Products that land in a count≥3 grid (Ingeniería + Filosofía) → get a portrait.
# These grids are now uniform 2-col portrait cards (no featured span), so EVERY
# grid product needs a 4:5 portrait — including the ones that used to be featured
# (organon span-2 in Ingeniería; paideia + estructuras en Filosofía).
# Ciencias grid ahora también usa portrait cards: kosmos + estructuras-preontologicas.
# Still NO portrait (horizontal featured/showcase): aporia (Ciencias), prizma (Enterprise showcase).
PORTRAIT_SLUGS: set[str] = {
    "paideia",
    "estructuras-preontologicas",
    "organon",
    "agon",
    "hinton",
    "daimon",
    "techne",
    "koinonia",
    "ergon",
    "chronos",
    "xenia",
    "nomos",
    "apotheke",
    "eikon",
    "kosmos",
    "agora",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_marca(slug: str) -> dict:
    path = MARCAS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Marca '{slug}' no encontrada: {path}")
    return load_json(path)


def resolve_url(marca: dict) -> str:
    return (
        marca.get("url_producto")
        or marca.get("url")
        or marca.get("url_corporativa")
        or ""
    )


# frente slug → display label used in the portrait eyebrow.
FRENTE_LABEL: dict[str, str] = {
    "filosofia":   "Filosofía",
    "ciencia":     "Ciencias",
    "ciencias":    "Ciencias",
    "informatica": "Informática",
    "ingenieria":  "Ingeniería",
    "agora":       "Agora",
}


def resolve_frente(marca: dict) -> str:
    slug = (marca.get("frente") or "").strip().lower()
    return FRENTE_LABEL.get(slug, slug.capitalize() if slug else "Pinakothḗke")


def font_stack(name: str, serif_fallback: bool) -> str:
    """Wrap a bare font name from the marca JSON into a CSS family stack."""
    name = (name or "").strip()
    if not name:
        return "'Playfair Display', Georgia, serif" if serif_fallback else "'Inter', system-ui, sans-serif"
    fallback = "Georgia, serif" if serif_fallback else "system-ui, sans-serif"
    return f"'{name}', {fallback}"


def build_vars(marca: dict, layout_id: str) -> dict:
    textos  = marca.get("textos", {}).get(layout_id, {})
    # Fall back to og_product texts for portrait (same content, different shape)
    if not textos:
        textos = marca.get("textos", {}).get("og_product", {})
    paleta  = marca.get("paleta", {})
    is_portrait = layout_id == "og_portrait"

    # Portrait eyebrow/footer encode the catalog framing: frente label up top,
    # short tagline as the footer signature. Other layouts keep the legacy
    # behaviour (subtitulo = descriptor line, logo_texto = product name).
    nombre   = marca.get("nombre_producto", "")
    tagline  = marca.get("tagline", "")
    subtitulo_val = resolve_frente(marca) if is_portrait else textos.get("subtitulo", tagline)
    logo_texto_val = tagline if is_portrait else nombre

    return {
        "bg":          paleta.get("bg",          "#0b1417"),
        "primario":    paleta.get("primario",     "#0b1417"),
        "acento":      paleta.get("acento",       "#43b5a6"),
        "acento_2":    paleta.get("acento_2",     "#e0a85e"),
        "acento_3":    paleta.get("acento_3",     "#c0522a"),
        "texto":       paleta.get("texto",        "#e8e0d4"),
        "texto_muted": paleta.get("texto_muted",  "#8fa3a8"),
        "surface":     paleta.get("surface",      "#152028"),
        "grad_hero":   marca.get("gradiente_hero",
                           "linear-gradient(135deg,#e0a85e 0%,#c0522a 40%,#43b5a6 100%)"),
        "grad_bg":     marca.get("gradiente_bg",
                           "radial-gradient(ellipse at 20% 50%,#152028 0%,#0b1417 60%)"),
        "font_titulo": font_stack(marca.get("tipografia", {}).get("titulos", ""), serif_fallback=True),
        "font_cuerpo": font_stack(marca.get("tipografia", {}).get("cuerpo",  ""), serif_fallback=False),
        "logo_simbolo": marca.get("logo_simbolo", "") or marca.get("simbolo", ""),
        "logo_texto":   logo_texto_val,
        "plataforma":   "",
        "url":          resolve_url(marca),
        # Portrait hero is always the clean Greek wordmark; other layouts may
        # carry a longer headline from `textos`.
        "titulo":    nombre if is_portrait else textos.get("titulo", nombre),
        "subtitulo": subtitulo_val,
        "copy":      textos.get("copy",      tagline),
    }


def inject_css_vars_js(vars_dict: dict) -> str:
    ATTR_MAP = {
        "data-logo-simbolo": "logo_simbolo",
        "data-logo-texto":   "logo_texto",
        "data-titulo":       "titulo",
        "data-subtitulo":    "subtitulo",
        "data-copy":         "copy",
        "data-url":          "url",
        "data-plataforma":   "plataforma",
    }
    CSS_MAP = {
        "--bg":          "bg",
        "--primario":    "primario",
        "--acento":      "acento",
        "--acento-2":    "acento_2",
        "--acento-3":    "acento_3",
        "--texto":       "texto",
        "--texto-muted": "texto_muted",
        "--surface":     "surface",
        "--grad-hero":   "grad_hero",
        "--grad-bg":     "grad_bg",
        "--font-titulo": "font_titulo",
        "--font-cuerpo": "font_cuerpo",
    }

    lines = ["(() => {", "  const r = document.documentElement;"]
    for css_var, key in CSS_MAP.items():
        val = vars_dict.get(key, "").replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"  r.style.setProperty('{css_var}', '{val}');")
    for attr, key in ATTR_MAP.items():
        val = vars_dict.get(key, "").replace("\\", "\\\\").replace("`", "\\`").replace("\n", "<br>")
        selector = f"[{attr}]"
        lines.append(
            f"  document.querySelectorAll('{selector}').forEach(el => {{ el.innerHTML = `{val}`; }});"
        )
    # Re-fit the auto-sizing brand name now that the wordmark + fonts are set.
    lines.append("  if (typeof window.__fitTitulo === 'function') { try { window.__fitTitulo(); } catch (e) {} }")
    lines.append("})();")
    return "\n".join(lines)


async def render_page(
    browser,
    tmpl_path: Path,
    viewport_w: int,
    viewport_h: int,
    device_scale_factor: float,
    vars_dict: dict,
    output_path: Path,
    label: str,
) -> None:
    context = await browser.new_context(
        viewport={"width": viewport_w, "height": viewport_h},
        device_scale_factor=device_scale_factor,
    )
    page = await context.new_page()
    try:
        await page.goto(f"file://{tmpl_path}", wait_until="networkidle", timeout=20000)
        await page.evaluate(inject_css_vars_js(vars_dict))
        # Ensure the per-brand webfont is fully loaded, then re-run the
        # name auto-fit so the measurement reflects the real glyph metrics.
        try:
            await page.evaluate("() => document.fonts ? document.fonts.ready : null")
        except Exception:
            pass
        await page.wait_for_timeout(900)  # fonts + transitions
        try:
            await page.evaluate(
                "() => { if (typeof window.__fitTitulo === 'function') window.__fitTitulo(); }"
            )
        except Exception:
            pass
        await page.wait_for_timeout(120)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(
            path=str(output_path),
            full_page=False,
            clip={"x": 0, "y": 0, "width": viewport_w, "height": viewport_h},
            type="png",
        )
        phys_w = int(viewport_w * device_scale_factor)
        phys_h = int(viewport_h * device_scale_factor)
        print(f"  [ok] {label}  →  {output_path.relative_to(Path('/workspace'))}  ({phys_w}x{phys_h})")
    finally:
        await page.close()
        await context.close()


async def run(do_hires: bool, do_portrait: bool, dry_run: bool) -> None:
    tmpl_og       = TMPL_DIR / "og_product.html"
    tmpl_portrait = TMPL_DIR / "og_portrait.html"

    if not tmpl_og.exists():
        print(f"[ERROR] Template not found: {tmpl_og}")
        sys.exit(1)
    if do_portrait and not tmpl_portrait.exists():
        print(f"[ERROR] Template not found: {tmpl_portrait}")
        sys.exit(1)

    tasks_hires: list[tuple] = []
    tasks_portrait: list[tuple] = []

    for brand_slug, marca_slug in HIRES_MAP.items():
        try:
            marca = load_marca(marca_slug)
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")
            continue

        if do_hires:
            vars_dict = build_vars(marca, "og_product")
            out = BRAND_OUT / brand_slug / "og_product.png"
            tasks_hires.append((
                tmpl_og, 1200, 630, 2.0, vars_dict, out,
                f"{brand_slug}/og_product @2x"
            ))

        if do_portrait and brand_slug in PORTRAIT_SLUGS:
            vars_dict = build_vars(marca, "og_portrait")
            out = BRAND_OUT / brand_slug / "portrait.png"
            # Render at 2x: 1080x1350 CSS px → 2160x2700 physical px, sharp at Retina.
            tasks_portrait.append((
                tmpl_portrait, 1080, 1350, 2.0, vars_dict, out,
                f"{brand_slug}/portrait @2x"
            ))

    all_tasks = tasks_hires + tasks_portrait

    if dry_run:
        print(f"DRY RUN — {len(all_tasks)} images to generate:")
        for t in all_tasks:
            # t = (tmpl_path, viewport_w, viewport_h, dsf, vars_dict, out_path, label)
            print(f"  {t[6]}  →  {t[5]}")
        return

    if not all_tasks:
        print("Nothing to do.")
        return

    print(f"Generating {len(all_tasks)} images...")

    sem = asyncio.Semaphore(3)

    async def bounded(task):
        async with sem:
            await render_page(browser, *task)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"],
        )
        try:
            await asyncio.gather(*[bounded(t) for t in all_tasks], return_exceptions=False)
        finally:
            await browser.close()

    print(f"\nDone. {len(all_tasks)} images written.")


def main():
    parser = argparse.ArgumentParser(description="Hi-res brand cover generator for mi-cv")
    parser.add_argument("--hires-only",    action="store_true", help="Solo regenera og_product @2x")
    parser.add_argument("--portrait-only", action="store_true", help="Solo genera portrait.png")
    parser.add_argument("--dry-run",       action="store_true", help="Lista sin generar")
    args = parser.parse_args()

    do_hires    = not args.portrait_only
    do_portrait = not args.hires_only

    if not PLAYWRIGHT_OK:
        print("[ERROR] Playwright no está instalado. Instalar: pip install playwright && playwright install chromium")
        sys.exit(1)

    asyncio.run(run(do_hires, do_portrait, args.dry_run))


if __name__ == "__main__":
    main()
