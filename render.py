#!/usr/bin/env python3
"""
render.py — Motor CSS/HTML → PNG para imágenes de marca
=========================================================

Reemplaza generar_maxcalidad.py (difusión GPU).
Motor: Playwright headless → screenshot exacto al tamaño del layout.
Sin IA de pago. Sin torch. Sin GPU. 100% vectorial/CSS.

Uso
---
  python render.py --marca agora
  python render.py --marca steven-vallejo --layout og_general
  python render.py --marca all
  python render.py --marca prizma --layout linkedin_post --solo-cambios

  # o via el wrapper:
  ./generar agora
  ./generar all

Dependencias
------------
  pip install playwright
  playwright install chromium
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path

# ── Rutas base ─────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
MARCAS_DIR  = ROOT / "marcas"
TMPL_DIR    = ROOT / "templates"
LAYOUTS_FILE= ROOT / "layouts.json"
OUTPUT_DIR  = ROOT / "output"

ENGINE_VERSION = "brand-render-v7"

SERIF_STACK = "Georgia, 'DejaVu Serif', serif"
SANS_STACK = "'DejaVu Sans', Arial, system-ui, sans-serif"
SYMBOL_STACK = "'DejaVu Sans', 'DejaVu Serif', 'Noto Color Emoji', sans-serif"

# Glifos bonitos pero poco seguros en la imagen headless actual.
SYMBOL_REPLACEMENTS = {
    "⟡": "◇",
}

FRENTE_LABELS = {
    "agora": "Agora",
    "ciencia": "Ciencias",
    "ciencias": "Ciencias",
    "filosofia": "Filosofía",
    "informatica": "Informática",
    "ingenieria": "Ingeniería",
}

TEXT_LIMITS = {
    # Feed y share cards: una promesa dominante + apoyo corto.
    "linkedin_post":     {"titulo": 58, "subtitulo": 58, "copy": 132, "url": 44},
    "x_post":            {"titulo": 52, "copy": 104, "url": 40},
    "og_general":        {"titulo": 58, "subtitulo": 56, "copy": 132, "url": 42},
    "og_product":        {"titulo": 60, "subtitulo": 72, "copy": 150, "url": 42},
    "og_product_2x":     {"titulo": 60, "subtitulo": 72, "copy": 150, "url": 42},
    "og_portrait":       {"titulo": 64, "subtitulo": 58, "copy": 120, "url": 38},
    # Miniaturas: lectura a distancia, casi sin párrafo.
    "yt_thumbnail":      {"titulo": 44, "copy": 46, "url": 34},
    "contra_cover":      {"titulo": 50, "copy": 90, "url": 36},
    # Vertical mobile: 1 idea + 1 línea, evitando texto de hormiga.
    "ig_story":          {"titulo": 52, "copy": 84, "url": 34},
    "ig_reel_cover":     {"titulo": 46, "copy": 72, "url": 34},
    "tiktok_cover":      {"titulo": 46, "copy": 72, "url": 34},
    "web_hero_mobile":   {"titulo": 52, "subtitulo": 48, "copy": 98, "url": 36},
    # Cuadrados sociales.
    "ig_post":           {"titulo": 46, "subtitulo": 48, "copy": 96},
    "ig_carousel":       {"titulo": 48, "copy": 86, "url": 34},
    # Banners: zona segura, mensaje breve, nada de microcopy largo.
    "linkedin_banner":   {"titulo": 48, "copy": 82, "url": 34},
    "x_header":          {"titulo": 48, "copy": 82, "url": 34},
    "fb_cover":          {"titulo": 54, "copy": 92, "url": 36},
    "yt_banner":         {"titulo": 48, "subtitulo": 58, "url": 36},
    "email_header":      {"titulo": 46, "subtitulo": 70, "copy": 82, "url": 36},
    "banner_ad":         {"titulo": 26, "copy": 58, "url": 32},
    # Print/brand collateral.
    "business_card":     {"titulo": 38, "subtitulo": 44, "copy": 62, "url": 36},
    "poster_a4":         {"titulo": 68, "subtitulo": 62, "copy": 190, "url": 42},
    "sticker":           {"titulo": 28, "copy": 32},
    "logo_wordmark":     {"titulo": 42, "subtitulo": 70},
    "logo_lockup_color": {"titulo": 42, "subtitulo": 58},
    "logo_lockup_dark":  {"titulo": 42, "subtitulo": 58},
    "logo_lockup_light": {"titulo": 42, "subtitulo": 58},
}

FALLBACK_COPY_LIMITS = {
    layout_id: fields["copy"]
    for layout_id, fields in TEXT_LIMITS.items()
    if "copy" in fields
}

# ── Importación de Playwright (con error amable) ────────────────────────────
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_marca(slug: str) -> dict:
    path = MARCAS_DIR / f"{slug}.json"
    if not path.exists():
        available = [p.stem for p in MARCAS_DIR.glob("*.json")]
        raise FileNotFoundError(
            f"Marca '{slug}' no encontrada en marcas/. "
            f"Disponibles: {', '.join(available)}"
        )
    return load_json(path)


def load_layouts() -> list[dict]:
    return load_json(LAYOUTS_FILE)["layouts"]


def resolve_url(marca: dict) -> str:
    """Devuelve la URL principal de la marca."""
    url = (
        marca.get("url_producto")
        or marca.get("url")
        or marca.get("url_corporativa")
        or ""
    )
    return normalize_url(url)


def normalize_url(url: str) -> str:
    url = " ".join((url or "").strip().split())
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.rstrip("/")


def font_stack(name: str, serif_fallback: bool) -> str:
    """Devuelve una pila CSS robusta para texto y glifos de marca."""
    name = (name or "").strip()
    base = f"'{name}', " if name else ""
    fallback = SERIF_STACK if serif_fallback else SANS_STACK
    # Los símbolos de marca viven a veces en rangos matemáticos/geométricos;
    # añadir DejaVu evita renders vacíos cuando la familia principal no cubre el glifo.
    return f"{base}{SYMBOL_STACK}, {fallback}"


def normalize_symbol(marca: dict) -> str:
    """Resuelve un símbolo visible incluso cuando el JSON usa un glifo no soportado."""
    raw = (marca.get("logo_simbolo") or marca.get("simbolo") or "").strip()
    if raw.startswith("lemniscata"):
        raw = "∞"
    return SYMBOL_REPLACEMENTS.get(raw, raw) or "•"


def resolve_subtitulo_fallback(marca: dict) -> str:
    """Etiqueta corta para layouts que necesitan contexto sin repetir el copy."""
    frente_slug = (marca.get("frente") or "").strip().lower()
    frente = FRENTE_LABELS.get(frente_slug, frente_slug.capitalize() if frente_slug else "")
    corporativo = (marca.get("nombre_corporativo") or "").strip()
    suite = (marca.get("suite") or "").strip()

    if frente and corporativo:
        return f"{frente} · {corporativo}"
    if corporativo:
        return corporativo
    if suite:
        return f"Suite {suite.capitalize()}"
    if frente:
        return frente
    return marca.get("tagline", "")


def shorten_text(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if not limit or len(text) <= limit:
        return text

    cut = text[: limit + 1]
    for sep in (". ", "; ", ": ", ", ", " "):
        pos = cut.rfind(sep)
        if pos >= max(40, int(limit * 0.55)):
            return cut[:pos].rstrip(" .;:,") + "..."
    return cut[:limit].rstrip() + "..."


def apply_field_limit(layout_id: str, field: str, value: str) -> str:
    limit = TEXT_LIMITS.get(layout_id, {}).get(field)
    return shorten_text(value, limit) if limit else " ".join((value or "").split())


def compare_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return "".join(ch for ch in text if ch.isalnum())


def same_text(a: str, b: str) -> bool:
    ka = compare_key(a)
    kb = compare_key(b)
    return bool(ka and kb and ka == kb)


def resolve_copy(marca: dict, layout_id: str, textos: dict) -> str:
    if "copy" in textos:
        return textos.get("copy", "")
    fallback = marca.get("tagline", "")
    return shorten_text(fallback, FALLBACK_COPY_LIMITS.get(layout_id, 220))


def build_vars(marca: dict, layout: dict) -> dict:
    """Construye el diccionario de variables que se inyectan en el HTML."""
    lid = layout["id"]
    textos = marca.get("textos", {}).get(lid, {})
    paleta = marca.get("paleta", {})
    grad_text = marca.get("gradiente_texto") or (
        "linear-gradient(135deg, "
        f"{paleta.get('acento', '#43b5a6')} 0%, "
        f"{paleta.get('acento_2', '#e0a85e')} 58%, "
        f"{paleta.get('texto', '#e8e0d4')} 100%)"
    )

    subtitulo_fallback = resolve_subtitulo_fallback(marca)

    titulo = textos.get("titulo", marca.get("nombre_producto", ""))
    subtitulo = textos.get("subtitulo", subtitulo_fallback)
    copy = resolve_copy(marca, lid, textos)
    url = resolve_url(marca)
    logo_texto = marca.get("nombre_producto", "")

    # Evita que piezas de marketing parezcan eco de la misma frase.
    # La firma/logo puede repetirse, pero titulo/subtitulo/copy deben cumplir roles distintos.
    if same_text(subtitulo, titulo):
        subtitulo = subtitulo_fallback if not same_text(subtitulo_fallback, titulo) else ""
    if same_text(copy, titulo) or same_text(copy, subtitulo):
        copy = ""

    titulo = apply_field_limit(lid, "titulo", titulo)
    subtitulo = apply_field_limit(lid, "subtitulo", subtitulo)
    copy = apply_field_limit(lid, "copy", copy)
    url = apply_field_limit(lid, "url", url)
    if lid == "banner_ad" and url:
        url = "Ver sitio"
    logo_texto = apply_field_limit(lid, "logo_texto", logo_texto)

    return {
        # Paleta (CSS custom properties → data-attrs para inyección JS)
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
        "grad_text":   grad_text,
        "grad_bg":     marca.get("gradiente_bg",
                           "radial-gradient(ellipse at 20% 50%,#152028 0%,#0b1417 60%)"),
        # Tipografía
        "font_titulo": font_stack(
            marca.get("tipografia", {}).get("titulos", "Playfair Display"),
            serif_fallback=True,
        ),
        "font_cuerpo": font_stack(
            marca.get("tipografia", {}).get("cuerpo", "Inter"),
            serif_fallback=False,
        ),
        # Identidad
        "logo_simbolo": normalize_symbol(marca),
        "logo_texto":   logo_texto,
        "plataforma":   layout.get("plataforma", ""),
        "url":          url,
        # Textos por layout
        "titulo":    titulo,
        "subtitulo": subtitulo,
        "copy":      copy,
    }


def inject_css_vars_js(vars_dict: dict) -> str:
    """Genera JS que inyecta CSS custom properties y rellena data-attrs."""
    # Mapeo data-attr → clave de vars
    ATTR_MAP = {
        "data-logo-simbolo": "logo_simbolo",
        "data-logo-texto":   "logo_texto",
        "data-titulo":       "titulo",
        "data-subtitulo":    "subtitulo",
        "data-copy":         "copy",
        "data-url":          "url",
        "data-plataforma":   "plataforma",
    }
    # CSS var map: nombre-CSS → clave Python
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
        "--grad-text":   "grad_text",
        "--grad-bg":     "grad_bg",
        "--font-titulo": "font_titulo",
        "--font-cuerpo": "font_cuerpo",
    }

    lines = ["(() => {", "  const r = document.documentElement;"]
    # CSS vars en :root
    for css_var, key in CSS_MAP.items():
        val = json.dumps(str(vars_dict.get(key, "")))
        lines.append(f"  r.style.setProperty('{css_var}', {val});")
    # Rellena elementos con data-attrs como texto plano.
    for attr, key in ATTR_MAP.items():
        val = json.dumps(str(vars_dict.get(key, "")))
        selector = f"[{attr}]"
        lines.append(
            f"  document.querySelectorAll('{selector}').forEach(el => {{"
            f" el.textContent = {val};"
            f" el.dataset.empty = String(!String({val}).trim());"
            f" }});"
        )
    lines.append("""
  const guard = document.createElement('style');
  guard.textContent = `
    [data-empty="true"] { display: none !important; }
    [data-fit], [data-titulo], [data-subtitulo], [data-copy], [data-url], [data-logo-texto] {
      min-width: 0;
    }
    [data-titulo], [data-logo-texto] {
      overflow-wrap: normal;
      word-break: normal;
      hyphens: none;
      text-wrap: balance;
    }
    [data-subtitulo], [data-copy], [data-url] {
      overflow-wrap: break-word;
    }
  `;
  document.head.appendChild(guard);
  const fit = (el) => {
    const min = Number(el.dataset.fitMin || 18);
    const maxLoops = 80;
    let loops = 0;
    const style = window.getComputedStyle(el);
    let size = Number.parseFloat(style.fontSize);
    if (!Number.isFinite(size)) return;
    const hasVerticalConstraint = style.maxHeight !== 'none';
    const isOverflowing = () => {
      const overX = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
      const overY = hasVerticalConstraint && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 12;
      return overX || overY;
    };
    while (loops < maxLoops && size > min && isOverflowing()) {
      size -= 1;
      el.style.fontSize = `${size}px`;
      loops += 1;
    }
  };
  window.__fitBrandText = () => document.querySelectorAll('[data-fit]').forEach(fit);
  window.__fitBrandText();
  const lineTexts = (el) => {
    const node = Array.from(el.childNodes).find((child) => child.nodeType === Node.TEXT_NODE);
    if (!node || !node.textContent) return [];
    const range = document.createRange();
    const groups = new Map();
    for (let i = 0; i < node.textContent.length; i += 1) {
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      const rect = range.getBoundingClientRect();
      if (!rect.width && !rect.height) continue;
      const key = Math.round(rect.top);
      groups.set(key, `${groups.get(key) || ''}${node.textContent[i]}`);
    }
    range.detach();
    return Array.from(groups.entries())
      .sort((a, b) => a[0] - b[0])
      .map((entry) => entry[1].replace(/\\s+/g, ' ').trim())
      .filter(Boolean);
  };
  window.__auditBrandFrame = () => Array.from(document.querySelectorAll('[data-titulo], [data-subtitulo], [data-copy], [data-url], [data-logo-texto]')).map(el => {
    const rect = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || '').trim(),
      attrs: Array.from(el.attributes).map(a => a.name).filter(n => n.startsWith('data-')),
      fontSize: Number.parseFloat(st.fontSize) || 0,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      overflowX: el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2,
      overflowY: st.maxHeight !== 'none' && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 12,
      display: st.display,
      lineTexts: lineTexts(el),
    };
  });
  if (typeof window.__fitTitulo === 'function') { try { window.__fitTitulo(); } catch (e) {} }
""")
    lines.append("})();")
    return "\n".join(lines)


def compute_hash(marca: dict, layout: dict, render_scale: int = 1) -> str:
    tmpl_path = TMPL_DIR / layout["template"]
    try:
        template_payload = tmpl_path.read_text(encoding="utf-8")
    except OSError:
        template_payload = ""
    payload = json.dumps(
        {
            "engine": ENGINE_VERSION,
            "render_scale": render_scale,
            "marca": marca,
            "layout": layout,
            "template": template_payload,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_cache(marca_slug: str) -> dict:
    cache_path = OUTPUT_DIR / marca_slug / ".cache.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass
    return {}


def save_cache(marca_slug: str, cache: dict) -> None:
    cache_path = OUTPUT_DIR / marca_slug / ".cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))


# ── Render async ─────────────────────────────────────────────────────────────

async def render_one(
    browser,
    marca: dict,
    layout: dict,
    output_path: Path,
    vars_dict: dict,
    render_scale: int = 1,
) -> None:
    """Renderiza una sola imagen con Playwright headless."""
    tmpl_path = TMPL_DIR / layout["template"]
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template no encontrado: {tmpl_path}")

    out_w = layout["ancho"]
    out_h = layout["alto"]
    layout_scale = int(layout.get("scale") or (2 if layout["id"].endswith("_2x") else 1))
    device_scale = layout_scale * max(1, int(render_scale))
    w = out_w // layout_scale
    h = out_h // layout_scale

    context = await browser.new_context(
        viewport={"width": w, "height": h},
        device_scale_factor=device_scale,
    )
    page = await context.new_page()
    try:
        await page.goto(f"file://{tmpl_path}", wait_until="networkidle", timeout=15000)
        await page.evaluate(inject_css_vars_js(vars_dict))
        try:
            await page.evaluate("() => document.fonts ? document.fonts.ready : null")
        except Exception:
            pass
        await page.wait_for_timeout(250)
        try:
            await page.evaluate(
                "() => {"
                " if (typeof window.__fitBrandText === 'function') window.__fitBrandText();"
                " if (typeof window.__fitTitulo === 'function') window.__fitTitulo();"
                "}"
            )
        except Exception:
            pass
        await page.wait_for_timeout(120)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(
            path=str(output_path),
            full_page=False,
            clip={"x": 0, "y": 0, "width": w, "height": h},
            type="png",
        )
    finally:
        await page.close()
        await context.close()


async def render_marca(
    marca_slug: str,
    layouts: list[dict],
    filter_layout: str | None = None,
    solo_cambios: bool = False,
    concurrency: int = 4,
    render_scale: int = 1,
) -> tuple[int, int, list[str]]:
    """Renderiza todos (o un subset) de layouts para una marca."""
    marca = load_marca(marca_slug)
    cache = load_cache(marca_slug) if solo_cambios else {}

    if filter_layout:
        layouts = [l for l in layouts if l["id"] == filter_layout]
        if not layouts:
            raise ValueError(f"Layout '{filter_layout}' no existe en layouts.json")

    semaphore = asyncio.Semaphore(concurrency)
    ok = 0
    skipped = 0
    errors: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            tasks = []
            task_labels: list[str] = []
            for layout in layouts:
                vars_dict   = build_vars(marca, layout)
                h_new       = compute_hash(marca, layout, render_scale)
                layout_id   = layout["id"]
                plat        = layout["plataforma"]
                out_path    = OUTPUT_DIR / marca_slug / plat / f"{layout_id}.png"

                if solo_cambios and cache.get(layout_id) == h_new and out_path.exists():
                    print(f"  [skip] {marca_slug}/{layout_id} (sin cambios)")
                    skipped += 1
                    continue

                async def _render(lo=layout, vd=vars_dict, op=out_path, lid=layout_id, hn=h_new):
                    async with semaphore:
                        out_w = lo["ancho"] * max(1, int(render_scale))
                        out_h = lo["alto"] * max(1, int(render_scale))
                        print(f"  [render] {marca_slug}/{lid}  {out_w}×{out_h}")
                        await render_one(browser, marca, lo, op, vd, render_scale)
                        cache[lid] = hn

                tasks.append(_render())
                task_labels.append(layout_id)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    lid = task_labels[i] if i < len(task_labels) else "?"
                    errors.append(f"{lid}: {res}")
                    print(f"  [ERROR] {res}")
                else:
                    ok += 1
        finally:
            await browser.close()

    if solo_cambios or True:
        save_cache(marca_slug, cache)

    return ok, skipped, errors


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generador CSS/HTML→PNG de imágenes de marca",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python render.py --marca agora
  python render.py --marca steven-vallejo --layout linkedin_post
  python render.py --marca all
  python render.py --marca prizma --solo-cambios
        """,
    )
    parser.add_argument(
        "--marca",
        help="Slug de la marca (ej: agora, steven-vallejo, prizma, pinakotheke) o 'all'",
    )
    parser.add_argument(
        "--layout",
        help="Generar solo un layout (ej: linkedin_post, ig_story, og_general)",
    )
    parser.add_argument(
        "--solo-cambios", action="store_true",
        help="Regenera solo las piezas cuyos tokens/textos cambiaron",
    )
    parser.add_argument(
        "--concurrencia", type=int, default=4,
        help="Páginas de Playwright en paralelo (default: 4)",
    )
    parser.add_argument(
        "--scale", type=int, default=1,
        help="Multiplicador global de resolución. Ej: --scale 2 exporta al doble de píxeles.",
    )
    parser.add_argument(
        "--hires", action="store_true",
        help="Atajo para alta resolución: usa --scale 2 y output_hires si no se indica otra carpeta.",
    )
    parser.add_argument(
        "--output-dir", default="output",
        help="Carpeta de salida relativa al repo o ruta absoluta (default: output).",
    )
    parser.add_argument(
        "--lista-marcas", action="store_true",
        help="Lista las marcas disponibles y sale",
    )
    parser.add_argument(
        "--lista-layouts", action="store_true",
        help="Lista los layouts disponibles y sale",
    )
    args = parser.parse_args()
    global OUTPUT_DIR

    if args.hires:
        args.scale = max(args.scale, 2)
        if args.output_dir == "output":
            args.output_dir = "output_hires"
    if args.scale < 1:
        parser.error("--scale debe ser >= 1")
    output_dir = Path(args.output_dir)
    OUTPUT_DIR = output_dir if output_dir.is_absolute() else ROOT / output_dir

    # Info rápida
    if args.lista_marcas:
        marcas = sorted(p.stem for p in MARCAS_DIR.glob("*.json"))
        print("Marcas disponibles:")
        for m in marcas:
            print(f"  {m}")
        return

    layouts = load_layouts()

    if args.lista_layouts:
        print("Layouts disponibles:")
        for l in layouts:
            print(f"  {l['id']:20s}  {l['ancho']}x{l['alto']}  ({l['plataforma']})")
        return

    if not args.marca:
        parser.error("--marca es obligatorio salvo con --lista-marcas o --lista-layouts")

    if not PLAYWRIGHT_OK:
        print("[ERROR] Playwright no está instalado.")
        print("  Instalar: pip install playwright && playwright install chromium")
        sys.exit(1)

    # Determinar marcas a procesar
    if args.marca == "all":
        slugs = sorted(p.stem for p in MARCAS_DIR.glob("*.json"))
    else:
        slugs = [args.marca]

    print("=" * 60)
    print(f"  Motor: CSS/HTML → PNG (Playwright headless)")
    print(f"  Marcas: {', '.join(slugs)}")
    print(f"  Layout: {args.layout or 'todos'}")
    print(f"  Solo cambios: {args.solo_cambios}")
    print(f"  Scale: {args.scale}x")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    total_ok = total_skip = 0
    total_errors: list[str] = []

    for slug in slugs:
        print(f"\n[marca] {slug}")
        ok, skip, errs = asyncio.run(
            render_marca(
                slug, layouts,
                filter_layout=args.layout,
                solo_cambios=args.solo_cambios,
                concurrency=args.concurrencia,
                render_scale=args.scale,
            )
        )
        total_ok   += ok
        total_skip += skip
        total_errors.extend(errs)

    print()
    print("=" * 60)
    print(f"  Generadas : {total_ok}")
    print(f"  Saltadas  : {total_skip}")
    print(f"  Errores   : {len(total_errors)}")
    for e in total_errors:
        print(f"    ✗ {e}")
    print(f"  Output    : {OUTPUT_DIR}")
    print("=" * 60)

    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
