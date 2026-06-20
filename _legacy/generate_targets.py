#!/usr/bin/env python3
"""
generate_targets.py — Genera imágenes específicas para brand covers.

Targets:
  1. agora/og_product.png (2400x1260)
  2. agora/portrait.png (2160x2700)
  3. kosmos/portrait.png (2160x2700)
  4. estructuras-preontologicas/portrait.png (2160x2700) — regenerar
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT      = Path(__file__).resolve().parent
TMPL_DIR  = ROOT / "templates"
MARCAS_DIR = ROOT / "marcas"
BRAND_OUT = Path("/workspace/Stev/mi-cv/public/brand")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def font_stack(name: str, serif_fallback: bool) -> str:
    name = (name or "").strip()
    if not name:
        return "'Playfair Display', Georgia, serif" if serif_fallback else "'Inter', system-ui, sans-serif"
    fallback = "Georgia, serif" if serif_fallback else "system-ui, sans-serif"
    return f"'{name}', {fallback}"


FRENTE_LABEL: dict[str, str] = {
    "filosofia":   "Filosofía",
    "ciencia":     "Ciencias",
    "ciencias":    "Ciencias",
    "informatica": "Informática",
    "ingenieria":  "Ingeniería",
    "agora":       "Agora",
}


def resolve_frente(marca: dict, override: str = None) -> str:
    if override:
        return override
    slug = (marca.get("frente") or "").strip().lower()
    return FRENTE_LABEL.get(slug, slug.capitalize() if slug else "")


def resolve_url(marca: dict) -> str:
    return (
        marca.get("url_producto")
        or marca.get("url")
        or marca.get("url_corporativa")
        or ""
    )


def build_vars_og_product(marca: dict) -> dict:
    textos = marca.get("textos", {}).get("og_product", {})
    paleta = marca.get("paleta", {})
    nombre = marca.get("nombre_producto", "")
    tagline = marca.get("tagline", "")

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
        "logo_texto":   nombre,
        "plataforma":   "",
        "url":          resolve_url(marca),
        "titulo":       textos.get("titulo", nombre),
        "subtitulo":    textos.get("subtitulo", tagline),
        "copy":         textos.get("copy", tagline),
    }


def build_vars_portrait(marca: dict, frente_override: str = None, casa_override: str = None) -> dict:
    paleta = marca.get("paleta", {})
    nombre = marca.get("nombre_producto", "")
    tagline = marca.get("tagline", "")
    frente = resolve_frente(marca, frente_override)

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
        "logo_texto":   tagline,  # bottom-right sign = tagline
        "plataforma":   "",
        "url":          resolve_url(marca),
        "titulo":       nombre,
        "subtitulo":    frente,  # top-left frente label
        "copy":         tagline,  # main body copy
        # casa_override passed separately so we can replace hardcoded "Pinakothḗke"
        "_casa": casa_override or "Pinakothḗke",
    }


def inject_css_vars_js(vars_dict: dict, casa: str = None) -> str:
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
    # Override the hardcoded .casa text if needed
    if casa:
        safe_casa = casa.replace("\\", "\\\\").replace("`", "\\`")
        lines.append(
            f"  document.querySelectorAll('.casa').forEach(el => {{ el.innerHTML = `{safe_casa}`; }});"
        )
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
    casa_override: str = None,
) -> None:
    context = await browser.new_context(
        viewport={"width": viewport_w, "height": viewport_h},
        device_scale_factor=device_scale_factor,
    )
    page = await context.new_page()
    try:
        await page.goto(f"file://{tmpl_path}", wait_until="networkidle", timeout=30000)
        await page.evaluate(inject_css_vars_js(vars_dict, casa=casa_override))
        try:
            await page.evaluate("() => document.fonts ? document.fonts.ready : null")
        except Exception:
            pass
        await page.wait_for_timeout(1000)
        try:
            await page.evaluate(
                "() => { if (typeof window.__fitTitulo === 'function') window.__fitTitulo(); }"
            )
        except Exception:
            pass
        await page.wait_for_timeout(200)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(
            path=str(output_path),
            full_page=False,
            clip={"x": 0, "y": 0, "width": viewport_w, "height": viewport_h},
            type="png",
        )
        phys_w = int(viewport_w * device_scale_factor)
        phys_h = int(viewport_h * device_scale_factor)
        print(f"  [ok] {label}  ->  {output_path}  ({phys_w}x{phys_h})")
    finally:
        await page.close()
        await context.close()


async def run():
    tmpl_og       = TMPL_DIR / "og_product.html"
    tmpl_portrait = TMPL_DIR / "og_portrait.html"

    from playwright.async_api import async_playwright

    tasks = []  # (tmpl, w, h, dsf, vars, out, label, casa)

    # ── 1. agora/og_product.png ───────────────────────────────────────────────
    agora_marca = load_json(MARCAS_DIR / "agora.json")
    tasks.append((
        tmpl_og, 1200, 630, 2.0,
        build_vars_og_product(agora_marca),
        BRAND_OUT / "agora" / "og_product.png",
        "agora/og_product @2x (2400x1260)",
        None,
    ))

    # ── 2. agora/portrait.png ─────────────────────────────────────────────────
    # Top-left: "AGORA" / "Elenxos". The portrait template has hardcoded
    # "Pinakothḗke" in .casa — override it via JS to "Elenxos".
    tasks.append((
        tmpl_portrait, 1080, 1350, 2.0,
        build_vars_portrait(agora_marca, frente_override="Agora", casa_override="Elenxos"),
        BRAND_OUT / "agora" / "portrait.png",
        "agora/portrait @2x (2160x2700)",
        "Elenxos",
    ))

    # ── 3. kosmos/portrait.png ────────────────────────────────────────────────
    kosmos_marca = load_json(MARCAS_DIR / "pinakotheke-kosmos.json")
    tasks.append((
        tmpl_portrait, 1080, 1350, 2.0,
        build_vars_portrait(kosmos_marca, frente_override="Ciencias"),
        BRAND_OUT / "kosmos" / "portrait.png",
        "kosmos/portrait @2x (2160x2700)",
        None,
    ))

    # ── 4. estructuras-preontologicas/portrait.png ────────────────────────────
    ep_marca = load_json(MARCAS_DIR / "pinakotheke-estructuras-preontologicas.json")
    tasks.append((
        tmpl_portrait, 1080, 1350, 2.0,
        build_vars_portrait(ep_marca, frente_override="Ciencias"),
        BRAND_OUT / "estructuras-preontologicas" / "portrait.png",
        "estructuras-preontologicas/portrait @2x (2160x2700)",
        None,
    ))

    print(f"Generating {len(tasks)} images...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"],
        )
        try:
            for tmpl, w, h, dsf, vars_dict, out, label, casa in tasks:
                await render_page(browser, tmpl, w, h, dsf, vars_dict, out, label, casa)
        finally:
            await browser.close()

    print(f"\nDone. {len(tasks)} images written.")


if __name__ == "__main__":
    asyncio.run(run())
