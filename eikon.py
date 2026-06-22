#!/usr/bin/env python3
"""
Motor EIKON: Generador canónico de assets de marca.

Narrativa del proceso:
  (a) Carga de marca: Lee datos JSON (colores, tipografía, textos).
  (b) Mapeo a taxonomía: Selecciona taxonomía (Prizma o Cloud Atlas) e inyecta variables.
  (c) Render con Playwright: Usa plantillas HTML inyectando data dinámica para generar PNGs Hi-Res.
  (d) Cache por hash: Salta assets sin cambios estructurales o de contenido.
  (e) Manifest: Genera _manifest.json por marca con metadata de cada asset.
  (f) Validación de contraste: Ejecuta contrast_validator.py sobre PNGs generados (WCAG AA).
  (g) CLI: Banderas --marca, --all, --dry-run, --resume, --parallel N, --solo.

Uso:
  python3 eikon.py --marca pinakotheke-kosmos
  python3 eikon.py --all
  python3 eikon.py --marca prizma-iris --solo logos
  python3 eikon.py --marca pinakotheke-kosmos --dry-run
  python3 eikon.py --marca pinakotheke-kosmos --resume
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import traceback
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List, Dict
import os

# Rutas principales
ROOT = Path(__file__).resolve().parent
MARCAS_DIR = ROOT / "marcas"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"

# Configuraciones
ENGINE_VERSION = "eikon-v1.2"
TIMEOUT_MS = 18_000
FONT_TIMEOUT_MS = 2_500
DEFAULT_LOCALE = "es"
MIN_PNG_BYTES = 100  # Tamaño mínimo razonable para un PNG válido

# =============================================================================
# LÍMITES DE TEXTO (portados desde _legacy/render.py — Fase 2)
# Evitan desbordamiento visual en plantillas donde el texto
# no cabe a la escala/área prevista.
# =============================================================================
TEXT_LIMITS: dict[str, dict[str, int]] = {
    "business_card":     {"titulo": 38, "subtitulo": 44, "copy": 62, "url": 36},
    "og_general":        {"titulo": 58, "subtitulo": 56, "copy": 132, "url": 42},
    "stat_card":         {"titulo": 48, "copy": 86, "url": 34},
    "ad_leaderboard":    {"titulo": 26, "copy": 58, "url": 32},
    "ad_rectangle":      {"titulo": 26, "copy": 58, "url": 32},
    "letterhead":        {"titulo": 68, "subtitulo": 62, "copy": 190, "url": 42},
    "lockup_horizontal": {"titulo": 42, "subtitulo": 58},
    "lockup_vertical":   {"titulo": 42, "subtitulo": 58},
    "wordmark":          {"titulo": 42, "subtitulo": 70},
    "isotipo":           {"titulo": 28},
    "watermark":         {"titulo": 42},
    "favicon":           {"titulo": 20},
    "linkedin_header":   {"titulo": 62, "subtitulo": 44, "copy": 90, "url": 42},
    "twitter_header":    {"titulo": 52, "copy": 72, "url": 42},
    "youtube_header":    {"titulo": 64, "copy": 100, "url": 42},
    "web_hero_desktop":  {"titulo": 56, "copy": 92, "url": 42},
}

# =============================================================================
# IMPORTS LAZY DE PLAYWRIGHT (no se carga si no se renderiza)
# =============================================================================
_playwright_cache: Any = None

def _get_playwright() -> Any:
    global _playwright_cache
    if _playwright_cache is None:
        try:
            from playwright.async_api import async_playwright as apw, TimeoutError as PWTimeout
            _playwright_cache = (apw, PWTimeout)
        except ModuleNotFoundError:
            print("✗ Playwright no instalado. Usa: pip install playwright", file=sys.stderr)
            sys.exit(1)
    return _playwright_cache

async_playwright = None   # lazy — usar _get_playwright()[0]
PlaywrightTimeoutError = Exception  # placeholder para tests

# =============================================================================
# (a) TAXONOMÍA Y CONFIGURACIÓN DE RESOLUCIÓN HI-RES
# =============================================================================

@dataclass(frozen=True)
class VariantSpec:
    name: str
    label: str

@dataclass(frozen=True)
class TypeSpec:
    name: str
    width: int
    height: int
    variants: tuple[VariantSpec, ...]

    def get_device_scale_factor(self, categoria: str) -> int:
        """deviceScaleFactor ALTO: 3 para logos/print, 2 para social/web/cards."""
        if categoria in ("logos", "stationery"):
            return 3
        return 2

    def get_output_width(self, categoria: str) -> int:
        return self.width * self.get_device_scale_factor(categoria)

    def get_output_height(self, categoria: str) -> int:
        return self.height * self.get_device_scale_factor(categoria)

def _build_taxonomia(is_prizma: bool) -> dict[str, list[TypeSpec]]:
    logos = [
        TypeSpec("lockup_horizontal", 1200, 400, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("lockup_vertical", 800, 800, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("wordmark", 1000, 300, (
            VariantSpec("v1_dark", "Dark"), VariantSpec("v2_light", "Light")
        )),
        TypeSpec("isotipo", 800, 800, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("favicon", 512, 512, (
            VariantSpec("v1_32", "32px"), VariantSpec("v2_180", "180px"), VariantSpec("v3_512", "512px")
        )),
        TypeSpec("watermark", 1000, 1000, (
            VariantSpec("v1_light", "Light"), VariantSpec("v2_dark", "Dark")
        )),
    ]

    cards_common = [
        TypeSpec("business_card", 1050, 600, (
            VariantSpec("v1_front", "Front"), VariantSpec("v2_back", "Back")
        ))
    ]

    if is_prizma:
        return {
            "logos": logos,
            "cards": cards_common + [
                TypeSpec("stat_card", 1080, 1080, (
                    VariantSpec("v1_big_data", "BigData"), VariantSpec("v2_comparativa", "Comparative"), VariantSpec("v3_uptime", "Uptime")
                )),
            ],
            "og": [
                TypeSpec("og_general", 1200, 630, (
                    VariantSpec("v1_docs", "Docs"), VariantSpec("v2_enterprise_blog", "Blog"), VariantSpec("v3_tool", "Tool")
                )),
                TypeSpec("og_product", 1200, 630, (
                    VariantSpec("v1_product", "Product"), VariantSpec("v2_product", "Product"), VariantSpec("v3_product", "Product")
                )),
            ],
            "stationery": [
                TypeSpec("letterhead", 2480, 3508, (
                    VariantSpec("v1_corporate", "Corporate"), VariantSpec("v2_invoice", "Invoice")
                )),
            ],
        }
    else:
        return {
            "logos": logos,
            "banners": [
                TypeSpec("linkedin_header", 1584, 396, (
                    VariantSpec("v1_institucional", "Institucional"),
                    VariantSpec("v2_producto", "Producto"),
                    VariantSpec("v3_evento", "Evento"),
                )),
                TypeSpec("twitter_header", 1500, 500, (
                    VariantSpec("v1_brand", "Brand"),
                    VariantSpec("v2_lanzamiento", "Lanzamiento"),
                    VariantSpec("v3_comunidad", "Comunidad"),
                )),
                TypeSpec("youtube_header", 2560, 1440, (
                    VariantSpec("v1_visual", "Visual"),
                    VariantSpec("v2_grid", "Grid"),
                    VariantSpec("v3_textual", "Textual"),
                )),
                TypeSpec("web_hero_desktop", 1920, 600, (
                    VariantSpec("v1_split", "Split"),
                    VariantSpec("v2_central", "Central"),
                    VariantSpec("v3_video_fallback", "VideoFallback"),
                    VariantSpec("v4_minimal", "Minimal"),
                )),
                TypeSpec("ad_leaderboard", 728, 90, (
                    VariantSpec("v1_brand", "Brand"), VariantSpec("v2_promo", "Promo"), VariantSpec("v3_cta_driven", "CTA")
                )),
                TypeSpec("ad_rectangle", 300, 250, (
                    VariantSpec("v1_visual", "Visual"), VariantSpec("v2_data", "Data"), VariantSpec("v3_testimonial", "Testimonial")
                )),
            ],
            "cards": cards_common + [
                TypeSpec("stat_card", 1080, 1080, (
                    VariantSpec("v1_hero_num", "Hero"), VariantSpec("v2_dual_stat", "Dual"), VariantSpec("v3_graph_abstract", "Graph")
                )),
            ],
            "og": [
                TypeSpec("og_general", 1200, 630, (
                    VariantSpec("v1_website", "Website"), VariantSpec("v2_articulo", "Article"), VariantSpec("v3_feature", "Feature")
                )),
            ],
            "stationery": [
                TypeSpec("letterhead", 2480, 3508, (
                    VariantSpec("v1_oficial", "Official"), VariantSpec("v2_interno", "Internal")
                )),
            ],
        }

CLOUD_ATLAS_TAXONOMIA = _build_taxonomia(is_prizma=False)
PRIZMA_TAXONOMIA = _build_taxonomia(is_prizma=True)

# =============================================================================
# (b) CARGA DE MARCA Y MAPEO INTACTO
# =============================================================================

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"✗ Error cargando {path}: {e}", file=sys.stderr)
        raise

def brand_family(marca: dict[str, Any]) -> str:
    slug = str(marca.get("slug", "")).lower()
    return "prizma" if "prizma" in slug else "cloud_atlas"

def shorten_text(text: str, limit: int) -> str:
    """Trunca texto en límites de frase/palabra con elipsis visible."""
    text = " ".join((text or "").split())
    if not limit or len(text) <= limit:
        return text
    cut = text[: limit + 1]
    for sep in (". ", "; ", ": ", ", ", " "):
        pos = cut.rfind(sep)
        if pos >= max(40, int(limit * 0.55)):
            return cut[:pos].rstrip(" .;:,") + "…"
    return cut[:limit].rstrip() + "…"

def apply_text_limits(tipo: str, vars_dict: dict[str, str]) -> dict[str, str]:
    """Aplica límites de texto a los campos de título, subtítulo, copy y url."""
    limits = TEXT_LIMITS.get(tipo, {})
    result = dict(vars_dict)
    for campo in ("titulo", "subtitulo", "copy", "url"):
        if campo in limits and campo in result:
            result[campo] = shorten_text(result[campo], limits[campo])
    return result

def map_marca_to_vars(marca: dict[str, Any], tipo: str, locale: str = DEFAULT_LOCALE,
                       variant_name: str = "") -> dict[str, str]:
    family = brand_family(marca)
    paleta = marca.get("paleta", {}) if isinstance(marca.get("paleta"), dict) else {}

    defaults = {
        "bg": "#0c0e10" if family == "prizma" else "#0b1417",
        "primario": "#0c0e10" if family == "prizma" else "#0b1417",
        "acento": "#f0b94a" if family == "prizma" else "#43b5a6",
        "acento_2": "#d4622e" if family == "prizma" else "#8d7cc0",
        "texto": "#f0ece6" if family == "prizma" else "#e8e0d4",
        "font_titulo_name": "Inter" if family == "prizma" else "Playfair Display",
    }

    tipografia = marca.get("tipografia", {}) if isinstance(marca.get("tipografia"), dict) else {}
    logo_simbolo = str(marca.get("logo_simbolo") or marca.get("simbolo") or ("⚡" if family == "prizma" else "∞")).strip()
    # logo_texto prioriza el campo específico de marca (no el corporativo)
    logo_texto = str(marca.get("logo_texto") or marca.get("nombre_producto") or marca.get("nombre_corporativo") or "").strip()

    textos = marca.get("textos", {}).get(tipo, {})
    if isinstance(textos, list): textos = textos[0] if textos else {}
    if not isinstance(textos, dict): textos = {}

    titulo = str(textos.get("titulo") or marca.get("nombre_producto") or "").strip()
    subtitulo = str(textos.get("subtitulo") or marca.get("tagline") or "").strip()
    copy = str(textos.get("copy") or "").strip()
    url = str(marca.get("url_producto") or marca.get("url") or "").strip()

    vars_dict = {
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
        "variant": variant_name,
        "numero": str(textos.get("numero", "22")),
        "etiqueta": str(textos.get("etiqueta", "Simulaciones")),
        "numero_2": str(textos.get("numero_2", "16")),
        "etiqueta_2": str(textos.get("etiqueta_2", "Repositorios")),
    }

    # ── Variant-aware overrides for logo/card types ──
    _vl = variant_name.lower()
    if _vl:
        # Logos: mono → light bg, inverse → dark bg, dark → dark bg, light → light bg
        if any(k in _vl for k in ("mono",)):
            vars_dict["bg"] = vars_dict["texto"]       # light bg
            vars_dict["texto"] = vars_dict["primario"]  # dark text
            vars_dict["primario"] = vars_dict["texto"]  # align primario
        elif any(k in _vl for k in ("inverse", "dark", "_dark")):
            vars_dict["bg"] = vars_dict["primario"]    # dark bg
            vars_dict["texto"] = str(paleta.get("texto") or defaults["texto"])  # light text
        elif any(k in _vl for k in ("light",)):
            vars_dict["bg"] = str(paleta.get("texto") or defaults["texto"])
            vars_dict["texto"] = str(paleta.get("primario") or defaults["primario"])
        # Cards: front/back use brand data via variant attr — no color overrides needed
        # Stat cards: different variants need different data injected
        if "stat_card" in tipo:
            if "v1_hero_num" in _vl:
                pass  # uses vars as-is, template injects big number
            elif "v2_dual_stat" in _vl:
                vars_dict["etiqueta_2"] = "Repos"
                vars_dict["numero_2"] = "16"
            elif "v3_graph_abstract" in _vl:
                vars_dict["etiqueta"] = "Tendencia"

    # Aplicar límites de texto (Fase 2)
    vars_dict = apply_text_limits(tipo, vars_dict)
    return vars_dict

def injection_script(vars_dict: dict[str, str], variant_name: str = "",
                     template_name: str = "") -> str:
    """JS que inyecta los valores de marca en vivo dentro del template renderizado."""
    css_map = {
        "--primario": "primario", "--acento": "acento", "--acento-2": "acento_2",
        "--texto": "texto", "--bg": "bg", "--font-titulo": "font_titulo", "--font-cuerpo": "font_cuerpo",
    }
    attr_map = {
        "data-logo-simbolo": "logo_simbolo", "data-logo-texto": "logo_texto",
        "data-titulo": "titulo", "data-subtitulo": "subtitulo",
        "data-copy": "copy", "data-url": "url",
        "data-etiqueta": "etiqueta", "data-numero": "numero",
        "data-etiqueta-2": "etiqueta_2", "data-numero-2": "numero_2",
    }

    lines = ["(() => {", "  const root = document.documentElement;"]
    for css_var, key in css_map.items():
        lines.append(f"  root.style.setProperty('{css_var}', '{vars_dict.get(key, '')}');")

    # Set variant and template on body for CSS selector matching
    if variant_name:
        lines.append(f"  document.body.dataset.variant = '{variant_name}';")
    if template_name:
        lines.append(f"  document.body.dataset.template = '{template_name}';")

    for attr, key in attr_map.items():
        value = vars_dict.get(key, "").replace("'", "\\'")
        lines.append(f"  document.querySelectorAll('[{attr}]').forEach(el => {{ el.textContent = '{value}'; }});")

    lines.append("  if (window.__eikonVariantRefresh) window.__eikonVariantRefresh();")
    lines.append("})();")
    return "\n".join(lines)


# =============================================================================
# (c.bis) VALIDADOR DOM MÍNIMO — FASE 5
# Inspecciona el DOM renderizado (post-injection) y reporta problemas de layout
# ANTES del screenshot. Produce warnings estructurados que se clasifican
# (puramente) en Python y se agregan al manifest.
# =============================================================================

# Selectores textuales visibles a inspeccionar.
LAYOUT_SELECTORS = (
    "h1,h2,h3,p,span,a,li,"
    "[data-required-text],"
    ".headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta"
)

# Tipos de warning y su severidad por defecto (función pura abajo).
LAYOUT_WARNING_SEVERITY: dict[str, str] = {
    "empty_required_text": "fail",   # contenido obligatorio ausente → asset incompleto
    "off_viewport": "fail",          # elemento fuera del rect visible → invisible
    "overflow_x": "warn",            # overflow horizontal → desborde visual
    "overflow_y": "warn",            # overflow vertical → texto cortado
    "inspection_error": "warn",      # el inspector JS falló → no pudimos verificar
}


def classify_layout_warning(warning: dict[str, Any]) -> str:
    """Pure: clasifica la severidad de UN warning de layout.

    Args:
        warning: dict con al menos clave "type". Tipos conocidos mapean a
            "fail"/"warn"; cualquier otro cae a "info".

    Returns:
        "fail" | "warn" | "info"
    """
    if not isinstance(warning, dict):
        return "info"
    wtype = str(warning.get("type", ""))
    return LAYOUT_WARNING_SEVERITY.get(wtype, "info")


def aggregate_layout_status(warnings: list[dict[str, Any]]) -> str:
    """Pure: agrega severidades en un status global.

    - 0 warnings → "pass"
    - algún "fail" → "fail"
    - algún "warn" (sin fail) → "warn"
    - solo "info" → "pass"
    """
    if not warnings:
        return "pass"
    severities = {classify_layout_warning(w) for w in warnings}
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


# JS que ejecuta en el page (vía page.evaluate) y devuelve
# {viewport: {w,h}, warnings: [...]}. Escrito como función IIFE que retorna JSON.
LAYOUT_INSPECTION_JS = r"""
() => {
  const SELECTORS = "h1,h2,h3,p,span,a,li,[data-required-text],.headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta";
  const vw = document.documentElement.clientWidth || window.innerWidth || 0;
  const vh = document.documentElement.clientHeight || window.innerHeight || 0;
  const warnings = [];

  function describeEl(el) {
    try {
      const tag = (el.tagName || "").toLowerCase();
      const id = el.id ? "#" + el.id : "";
      const cls = (typeof el.className === "string" ? el.className : "")
        .split(/\s+/).filter(Boolean).slice(0, 3).map(c => "." + c).join("");
      const attr = el.hasAttribute("data-required-text") ? "[data-required-text]" : "";
      const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
      return (tag + id + cls + attr + (text ? " \"" + text + "\"" : "")).trim();
    } catch (e) {
      return "<unknown>";
    }
  }

  const elements = document.querySelectorAll(SELECTORS);
  elements.forEach((el) => {
    let style, rect;
    try {
      style = window.getComputedStyle(el);
      rect = el.getBoundingClientRect();
    } catch (e) {
      return; // skip elementos inaccesibles
    }
    if (!style) return;

    // Saltar elementos no visibles (display:none o visibility:hidden o 0 size)
    if (style.display === "none" || style.visibility === "hidden") return;
    if (parseFloat(style.opacity || "1") === 0) return;

    const text = (el.textContent || "").trim();

    // 1) data-required-text → texto obligatorio vacío
    if (el.hasAttribute("data-required-text") && text.length === 0) {
      warnings.push({
        type: "empty_required_text",
        selector: describeEl(el),
        detail: "data-required-text element is empty"
      });
    }

    // 2) scrollWidth/clientWidth overflow (guard: clientWidth > 0 para
    //    saltar elementos inline cuyo clientWidth es 0 por especificación)
    if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1) {
      warnings.push({
        type: "overflow_x",
        selector: describeEl(el),
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        detail: "scrollWidth " + el.scrollWidth + " > clientWidth " + el.clientWidth
      });
    }
    if (el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 1) {
      warnings.push({
        type: "overflow_y",
        selector: describeEl(el),
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        detail: "scrollHeight " + el.scrollHeight + " > clientHeight " + el.clientHeight
      });
    }

    // 3) Rect completamente fuera del viewport (elemento invisible)
    if (rect.width > 0 && rect.height > 0 && vw > 0 && vh > 0) {
      if (rect.right < 0 || rect.bottom < 0 || rect.left > vw || rect.top > vh) {
        warnings.push({
          type: "off_viewport",
          selector: describeEl(el),
          rect: {
            left: Math.round(rect.left), top: Math.round(rect.top),
            right: Math.round(rect.right), bottom: Math.round(rect.bottom)
          },
          viewport: { width: vw, height: vh },
          detail: "element rect outside viewport"
        });
      }
    }
  });

  return { viewport: { width: vw, height: vh }, warnings: warnings };
}
"""


# =============================================================================
# (c) RESOLUCIÓN ROBUSTA DE TEMPLATES
# =============================================================================

_TEMPLATE_ALIASES: dict[str, tuple[str, ...]] = {
    "linkedin_header": ("linkedin_banner",),
    "twitter_header": ("x_header",),
    "youtube_header": ("yt_banner",),
    "web_hero_desktop": ("web_hero",),
}

def resolve_template(type_spec_name: str, templates_dir: Path) -> Optional[Path]:
    """
    Encuentra el archivo de plantilla HTML para un tipo de asset.

    Estrategia (en orden):
      1. Exacto: templates/<type_spec_name>.html
      2. Alias conocidos (diccionario _TEMPLATE_ALIASES)
      3. Si nada coincide → None + warning en stderr.

    Es testeable y no depende de Playwright.
    """
    exact = templates_dir / f"{type_spec_name}.html"
    if exact.exists():
        return exact

    candidates = _TEMPLATE_ALIASES.get(type_spec_name, ())
    for alias in candidates:
        candidate = templates_dir / f"{alias}.html"
        if candidate.exists():
            return candidate

    existing = sorted(p.name for p in templates_dir.glob("*.html"))
    print(
        f"  ⚠ Template no encontrado para '{type_spec_name}'. "
        f"Templates disponibles ({len(existing)}): {', '.join(existing[:12])}{'…' if len(existing) > 12 else ''}",
        file=sys.stderr,
    )
    return None


# =============================================================================
# (d) CACHE POR HASH — Fase 2
# =============================================================================

def compute_hash(marca: dict[str, Any], categoria: str, type_name: str,
                 variant_name: str, template_path: Path, vars_dict: dict[str, str]) -> str:
    """Hash estable para detectar cambios en inputs de un asset."""
    try:
        template_content = template_path.read_text(encoding="utf-8")
    except Exception:
        template_content = ""

    payload = json.dumps({
        "engine": ENGINE_VERSION,
        "marca_slug": str(marca.get("slug", "")),
        "category": categoria,
        "type": type_name,
        "variant": variant_name,
        "vars": vars_dict,
        "template": template_content,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def load_cache(marca_slug: str) -> dict[str, str]:
    cache_path = OUTPUT_DIR / marca_slug / ".cache.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass
    return {}

def save_cache(marca_slug: str, cache: dict[str, str]) -> None:
    cache_path = OUTPUT_DIR / marca_slug / ".cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))


# =============================================================================
# (e) MANIFEST DE SALIDA — Fase 2
# =============================================================================

def post_validate_assets(asset_metas: list[dict[str, Any]], marca_slug: str) -> int:
    """
    Post-valida que cada asset con status 'error' tenga un PNG real en disco.
    Si el PNG existe y tiene tamaño >= MIN_PNG_BYTES, sobrescribe status a 'generated'.

    Retorna el número de assets re-marcados.
    """
    remarkeados = 0
    for meta in asset_metas:
        if meta.get("status") != "error":
            continue
        png_path = OUTPUT_DIR / marca_slug / meta.get("path", "")
        if png_path.exists() and png_path.stat().st_size >= MIN_PNG_BYTES:
            meta["status"] = "generated"
            meta["warnings"].append("post-validated: PNG exists despite render error")
            remarkeados += 1
    return remarkeados


def write_manifest(marca_slug: str, assets: list[dict[str, Any]]) -> Path:
    """Escribe _manifest.json con metadata de todos los assets de una marca."""
    manifest_path = OUTPUT_DIR / marca_slug / "_manifest.json"
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "marca": marca_slug,
        "total_assets": len(assets),
        "assets": sorted(
            assets,
            key=lambda a: (a.get("category", ""), a.get("type", ""), a.get("variant", ""))
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest_path


# =============================================================================
# (f) RENDER PLAYWRIGHT HI-RES — con cache integrado
# =============================================================================

async def render_asset(
    browser: Any, marca_slug: str, categoria: str, tipo_spec: TypeSpec,
    variant_spec: VariantSpec, marca: dict[str, Any],
    cache: dict[str, str], dry_run: bool = False,
) -> dict[str, Any]:
    """
    Renderiza un asset individual. Retorna dict con metadata para el manifest.

    En dry_run solo simula y retorna sin escribir PNG.
    En modo cache, salta assets cuyo hash no ha cambiado.
    """
    template_path = resolve_template(tipo_spec.name, TEMPLATES_DIR)
    if template_path is None:
        return {
            "category": categoria, "type": tipo_spec.name, "variant": variant_spec.name,
            "status": "error", "warnings": ["template not found"],
        }

    vars_dict = map_marca_to_vars(marca, tipo_spec.name, variant_name=variant_spec.name)
    input_hash = compute_hash(marca, categoria, tipo_spec.name, variant_spec.name,
                              template_path, vars_dict)
    cache_key = f"{categoria}/{tipo_spec.name}/{variant_spec.name}"
    output_path = OUTPUT_DIR / marca_slug / categoria / tipo_spec.name / f"{variant_spec.name}.png"

    asset_meta = {
        "path": str(output_path.relative_to(OUTPUT_DIR / marca_slug)),
        "category": categoria,
        "type": tipo_spec.name,
        "variant": variant_spec.name,
        "width": tipo_spec.get_output_width(categoria),
        "height": tipo_spec.get_output_height(categoria),
        "input_hash": input_hash,
        "status": "pending",
        "warnings": [],
        "layout_status": "skipped",     # validado | skipped | pass | warn | fail
        "layout_warnings": [],          # lista cruda de {type, selector, detail, ...}
    }

    # Verificar cache
    if cache is not None and cache.get(cache_key) == input_hash and output_path.exists():
        asset_meta["status"] = "cached"
        return asset_meta

    if dry_run:
        asset_meta["status"] = "dry_run"
        return asset_meta

    # Render real
    context = None
    page = None
    try:
        injection = injection_script(vars_dict, variant_name=variant_spec.name,
                                       template_name=tipo_spec.name)
        scale_factor = tipo_spec.get_device_scale_factor(categoria)

        context = await browser.new_context(
            viewport={"width": tipo_spec.width, "height": tipo_spec.height},
            device_scale_factor=scale_factor,
            locale="es-ES"
        )
        page = await context.new_page()

        url = f"{template_path.as_uri()}?variant={variant_spec.name}"
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        await page.evaluate(injection)

        try:
            await page.evaluate(f"""() => Promise.race([
                document.fonts?.ready || Promise.resolve(),
                new Promise(resolve => setTimeout(resolve, {FONT_TIMEOUT_MS}))
            ])""")
        except Exception:
            pass

        await page.wait_for_timeout(100)

        # ── Validador DOM mínimo (Fase 5) — antes del screenshot ──
        # Inspecciona elementos textuales visibles y reporta overflows,
        # rects fuera del viewport, y data-required-text vacíos.
        # Clasificación de severidad es función pura en Python.
        try:
            layout_result = await page.evaluate(LAYOUT_INSPECTION_JS)
            raw_warnings = (
                layout_result.get("warnings", [])
                if isinstance(layout_result, dict) else []
            )
            asset_meta["layout_warnings"] = list(raw_warnings)
            asset_meta["layout_status"] = aggregate_layout_status(raw_warnings)
        except Exception as layout_err:
            # El inspector nunca debe romper el render: registramos y seguimos.
            asset_meta["layout_warnings"] = [{
                "type": "inspection_error",
                "detail": str(layout_err),
            }]
            asset_meta["layout_status"] = aggregate_layout_status(asset_meta["layout_warnings"])

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Screenshot con reintento simple (1 retry) para race conditions de Page.captureScreenshot
        screenshot_taken = False
        last_error = None
        for attempt in range(2):
            try:
                await page.screenshot(path=str(output_path), type="png", full_page=False, omit_background=False)
                screenshot_taken = True
                break
            except Exception as screenshot_err:
                last_error = screenshot_err
                err_msg = str(screenshot_err).lower()
                # Solo reintentar si parece race condition de captureScreenshot
                if attempt == 0 and ("capturescreenshot" in err_msg or "target closed" in err_msg
                                      or "protocol error" in err_msg or "session closed" in err_msg):
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
        if page: await page.close()
        if context: await context.close()

    return asset_meta


# =============================================================================
# (g) ORQUESTADOR DE GENERACIÓN POR MARCA
# =============================================================================

async def run_generator(
    marcas_a_procesar: List[str],
    filtro_categoria: Optional[str] = None,
    dry_run: bool = False,
    use_cache: bool = False,
    max_parallel: int = 1,
    skip_contrast: bool = False,
) -> dict:
    """
    Genera assets para las marcas especificadas.

    Retorna: {"counts": {marca: {cat: int}}, "manifests": [Path], "total": {gen, skip, err}}
    """
    apw, _ = _get_playwright()
    counts: dict[str, dict[str, int]] = {}
    manifests: list[Path] = []
    total_gen = 0
    total_skip = 0
    total_err = 0
    total_layout_fail = 0

    if dry_run:
        print("⇢ DRY-RUN: Enumerando assets (sin renderizar).\n")

    async with apw() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])

        try:
            for marca_slug in marcas_a_procesar:
                t_start = time.time()
                print(f"\n→ Procesando marca: {marca_slug}")
                marca_path = MARCAS_DIR / f"{marca_slug}.json"
                if not marca_path.exists():
                    print(f"  ✗ Marca no encontrada: {marca_path}")
                    continue

                marca = load_json(marca_path)
                family = brand_family(marca)
                taxonomia = PRIZMA_TAXONOMIA if "prizma" in family else CLOUD_ATLAS_TAXONOMIA

                cache = load_cache(marca_slug) if use_cache else {}
                counts[marca_slug] = {}
                asset_metas: list[dict[str, Any]] = []
                gen = skip = err = 0

                total_types = sum(len(ts) for ts in taxonomia.values())
                type_idx = 0

                for categoria, type_specs in taxonomia.items():
                    if filtro_categoria and categoria != filtro_categoria:
                        continue

                    counts[marca_slug][categoria] = 0
                    print(f"  → Categoria [{categoria}]:")

                    for type_spec in type_specs:
                        type_idx += 1
                        scale = type_spec.get_device_scale_factor(categoria)
                        out_w = type_spec.get_output_width(categoria)
                        out_h = type_spec.get_output_height(categoria)
                        print(f"    [{type_idx}/{total_types}] {type_spec.name} ({out_w}x{out_h}px @{scale}x) →", end=" ", flush=True)

                        success = 0
                        for variant_spec in type_spec.variants:
                            meta = await render_asset(
                                browser, marca_slug, categoria, type_spec, variant_spec,
                                marca, cache, dry_run=dry_run
                            )
                            asset_metas.append(meta)

                            if meta["status"] == "generated":
                                success += 1
                                gen += 1
                                print("✓", end="", flush=True)
                            elif meta["status"] == "cached":
                                success += 1
                                skip += 1
                                print("↻", end="", flush=True)
                            elif meta["status"] == "dry_run":
                                success += 1
                                print("·", end="", flush=True)
                            else:
                                err += 1
                                print("⊘", end="", flush=True)

                        counts[marca_slug][categoria] += success
                        print()

                # Post-validar: corregir status "error" espurio si el PNG existe
                remarkeados = post_validate_assets(asset_metas, marca_slug)
                if remarkeados > 0:
                    print(f"     ⟳ Post-validación: {remarkeados} assets re-marcados como generated (PNG existe)")
                    # Recalcular contadores
                    gen = sum(1 for a in asset_metas if a["status"] == "generated")
                    skip = sum(1 for a in asset_metas if a["status"] == "cached")
                    err = sum(1 for a in asset_metas if a["status"] == "error")

                # Escribir manifest
                manifest_path = write_manifest(marca_slug, asset_metas)
                manifests.append(manifest_path)
                print(f"     ✓ Manifest: {manifest_path.name} ({len(asset_metas)} assets)")

                # Guardar cache
                if use_cache and not dry_run:
                    save_cache(marca_slug, cache)

                elapsed = time.time() - t_start
                print(f"  ✓ {marca_slug}: {gen} gen, {skip} cache, {err} err  ({elapsed:.1f}s)")

                total_gen += gen
                total_skip += skip
                total_err += err
                total_layout_fail += sum(
                    1 for a in asset_metas if a.get("layout_status") == "fail"
                )

        finally:
            await browser.close()

    # Validación de contraste (salvo --skip-contraste o --dry-run)
    if not dry_run and not skip_contrast:
        print("\n→ Ejecutando validador de contrastes WCAG AA...")
        try:
            from contrast_validator import ContrastValidator

            if len(marcas_a_procesar) == 1:
                # Una sola marca: reporte per-brand
                slug = marcas_a_procesar[0]
                validator = ContrastValidator(OUTPUT_DIR)
                validator.validate_all(marca_slug=slug)
                validator.write_report(OUTPUT_DIR / slug / "_contraste-report.json")
            else:
                # Múltiples marcas: reporte per-brand + global
                for slug in marcas_a_procesar:
                    validator = ContrastValidator(OUTPUT_DIR)
                    validator.validate_all(marca_slug=slug)
                    validator.write_report(OUTPUT_DIR / slug / "_contraste-report.json")
                # Reporte global (compatibilidad)
                validator_global = ContrastValidator(OUTPUT_DIR)
                validator_global.validate_all()
                validator_global.write_report(OUTPUT_DIR / "_contraste-report.json")
        except ImportError:
            print("  ⚠ contrast_validator.py no encontrado. Omitiendo validación.")
        except Exception as e:
            print(f"  ⚠ Error en validación de contraste: {e}")

    return {
        "counts": counts,
        "manifests": manifests,
        "total": {
            "generated": total_gen,
            "cached": total_skip,
            "errors": total_err,
            "layout_fails": total_layout_fail,
        },
    }


# =============================================================================
# (h) CLI ROBUSTO
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Motor EIKON: Generador Canónico de Assets de Marca",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python eikon.py --marca pinakotheke-kosmos
  python eikon.py --marca pinakotheke-kosmos --dry-run
  python eikon.py --marca pinakotheke-kosmos --resume
  python eikon.py --all
  python eikon.py --marca prizma-iris --solo logos
  python eikon.py --marca pinakotheke-kosmos --skip-contraste
  python eikon.py --marca pinakotheke-kosmos --web-icons
  # Solo web-icons (sin re-renderizar Playwright): usa web_icons.py directamente
  python web_icons.py --marca pinakotheke-kosmos
  python web_icons.py --all
        """,
    )
    parser.add_argument("--marca", type=str, help="Slug de la marca (ej. pinakotheke-kosmos)")
    parser.add_argument("--all", action="store_true", help="Procesa todas las marcas EXCEPTO agora-*")
    parser.add_argument("--only-marcas", type=str,
                        help="Lista separada por comas de slugs a procesar (ej. pinakotheke-kosmos,prizma-iris)")
    parser.add_argument("--solo", type=str, help="Filtra categoría (ej. logos, cards)")
    parser.add_argument("--dry-run", action="store_true", help="Enumera assets sin renderizar ni escribir PNGs")
    parser.add_argument("--resume", "--solo-cambios", action="store_true", dest="resume",
                        help="Usa cache para saltar assets no modificados (= --solo-cambios)")
    parser.add_argument("--parallel", type=int, default=1, help="Número de workers paralelos (actualmente limitado a 1)")
    parser.add_argument("--skip-contraste", action="store_true", help="Omite validación WCAG al final")
    parser.add_argument("--clean", action="store_true",
                        help="Limpia output/<marca>/ antes de renderizar (opt-in, no implícito)")
    parser.add_argument("--fail-on-layout", action="store_true",
                        help="Devuelve exit code 1 si algún asset tiene layout_status=fail")
    parser.add_argument("--web-icons", action="store_true",
                        help="Genera el set web-icons estándar (favicon.ico multi-res, PWA, OG) tras el render Playwright")
    args = parser.parse_args()

    if not args.marca and not args.all and not args.only_marcas:
        parser.print_help()
        print("\n✗ Error: Especifica --marca <slug>, --all, o --only-marcas <slugs>")
        return 1

    if args.parallel > 1:
        print("⚠ --parallel > 1 no soportado aún. Limitando a 1 worker.", file=sys.stderr)

    marcas_a_procesar = []
    if args.all:
        if not MARCAS_DIR.exists():
            print("✗ Directorio marcas/ no existe", file=sys.stderr)
            return 1
        for f in MARCAS_DIR.glob("*.json"):
            if not f.stem.startswith("agora-"):
                marcas_a_procesar.append(f.stem)
    elif args.only_marcas:
        marcas_a_procesar = [s.strip() for s in args.only_marcas.split(",") if s.strip()]
    else:
        marcas_a_procesar.append(args.marca)

    # Limpieza opt-in de output/<marca>/ antes de renderizar
    if args.clean:
        import shutil
        for slug in marcas_a_procesar:
            brand_output = OUTPUT_DIR / slug
            if brand_output.exists():
                shutil.rmtree(brand_output)
                print(f"  🗑 Limpiado: {brand_output}")

    try:
        result = asyncio.run(run_generator(
            marcas_a_procesar=marcas_a_procesar,
            filtro_categoria=args.solo,
            dry_run=args.dry_run,
            use_cache=args.resume,
            max_parallel=args.parallel,
            skip_contrast=args.skip_contraste,
        ))

        # Reporte final
        print("\n" + "=" * 60 + "\nREPORTE FINAL\n" + "=" * 60)
        totals = result["total"]
        for slug, cats in result["counts"].items():
            total_assets = sum(cats.values())
            print(f"✓ {slug}: {total_assets} assets totales.")
        print(f"  Generados: {totals['generated']}")
        print(f"  Cache hit: {totals['cached']}")
        print(f"  Errores:   {totals['errors']}")
        print(f"  Layout fails: {totals.get('layout_fails', 0)}")
        if result["manifests"]:
            print(f"  Manifests: {len(result['manifests'])}")

        # Gate --fail-on-layout
        if args.fail_on_layout and totals.get("layout_fails", 0) > 0:
            print(f"  ✗ --fail-on-layout: {totals['layout_fails']} assets con layout_status=fail")
            return 1

        # Generación del set web-icons estándar (Pillow, sin Playwright)
        if args.web_icons and not args.dry_run:
            print("\n→ Generando web-icons estándar (favicon, PWA, OG)…")
            try:
                from web_icons import generate_web_icons, load_brand, verify_web_icons, print_verification
                for slug in marcas_a_procesar:
                    brand = load_brand(slug)
                    if brand is None:
                        continue
                    wi_results = generate_web_icons(slug, brand, dry_run=False)
                    ok_count = sum(1 for ok, _ in wi_results.values() if ok)
                    print(f"  ✓ {slug}: {ok_count}/{len(wi_results)} web-icons")
                    v = verify_web_icons(slug)
                    print_verification(slug, v)
            except Exception as e_wi:
                print(f"  ⚠ Error en web-icons: {e_wi}", file=sys.stderr)
                traceback.print_exc()

        return 0 if totals["errors"] == 0 else 1

    except Exception as e:
        print(f"✗ Error fatal: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
