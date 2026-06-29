#!/usr/bin/env python3
"""
web_icons.py — Generador del set web-icons estándar por marca.

Produce, por cada marca en output/<marca>/web-icons/:
  favicon.ico         multi-res (16, 32, 48)
  favicon-16.png      16x16 RGBA
  favicon-32.png      32x32 RGBA
  apple-touch-icon.png  180x180 RGB  (fondo de marca, sin transparencia)
  icon-192.png        192x192 RGBA
  icon-512.png        512x512 RGBA
  icon-512-maskable.png  512x512 RGBA (safe-zone 80%, padding ~10%)
  og-image.png        1200x630 RGB
  icon.svg            SVG isotipo vectorial (si se puede derivar)

Fuentes de imagen (en orden de preferencia):
  1. output/<marca>/logos/favicon/v1_32_alpha.png  → iconos pequeños (RGBA transparente)
  2. output/<marca>/logos/favicon/v3_512.png       → iconos grandes
  3. output/<marca>/logos/favicon/v2_180.png       → apple-touch-icon (tiene borde redondeado de marca)
  4. output/<marca>/og/og_general/v1_website.png   → og-image (Cloud Atlas)
     output/<marca>/og/og_general/v1_docs.png      → og-image (Prizma)
  5. Si no hay fuente, genera un placeholder con símbolo+colores de marca (Pillow puro).

Uso:
  python3 web_icons.py --marca pinakotheke-kosmos
  python3 web_icons.py --all
  python3 web_icons.py --only-marcas pinakotheke-kosmos,prizma-iris
  python3 web_icons.py --marca pinakotheke-kosmos --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow no instalado. Usa: pip install Pillow", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
MARCAS_DIR = ROOT / "marcas"
OUTPUT_DIR = ROOT / "output"

# Tamaños del set estándar
FAVICON_ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
FAVICON_16 = (16, 16)
FAVICON_32 = (32, 32)
APPLE_TOUCH_SIZE = (180, 180)
ICON_192 = (192, 192)
ICON_512 = (512, 512)
OG_SIZE = (1200, 630)

# Maskable safe-zone: el isotipo debe estar dentro del 80% central (40% padding por lado en %)
# En práctica: padding = 10% del lado = 51px sobre 512
MASKABLE_PADDING_RATIO = 0.10


def load_brand(slug: str) -> dict | None:
    path = MARCAS_DIR / f"{slug}.json"
    if not path.exists():
        print(f"  ERROR: {path} no existe", file=sys.stderr)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ERROR leyendo {path}: {e}", file=sys.stderr)
        return None


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convierte '#rrggbb' a (r, g, b)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return (11, 20, 23)  # fallback dark


def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, alpha)


def find_source_icon(marca_slug: str, brand: dict) -> Image.Image | None:
    """
    Busca la mejor fuente para el isotipo: RGBA (transparente) si existe, si no RGB.
    Retorna imagen RGBA 512px ya reescalada o None.
    """
    base = OUTPUT_DIR / marca_slug / "logos" / "favicon"

    # Preferencia: RGBA transparente con símbolo para resize limpio
    candidates = [
        base / "v1_32_alpha.png",  # RGBA — símbolo con fondo transparente
        base / "v3_512.png",  # RGB — símbolo en fondo de marca
        base / "v1_32.png",  # RGB — símbolo en fondo de marca
        base / "v2_180.png",  # RGB — variante redondeada
    ]

    for cand in candidates:
        if cand.exists():
            try:
                img = Image.open(cand).convert("RGBA")
                # Si la imagen es RGB sin alpha real (toda opaca), intentamos
                # hacer transparente el fondo (color de esquina).
                if cand.suffix == ".png" and "alpha" not in cand.stem and img.size[0] > 100:
                    img = make_transparent(img, brand)
                return img.resize(ICON_512, Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"    WARN: No se pudo cargar {cand}: {e}", file=sys.stderr)

    print(
        f"  WARN: No se encontró fuente favicon para {marca_slug}. Generando placeholder.",
        file=sys.stderr,
    )
    return None


def make_transparent(img: Image.Image, brand: dict) -> Image.Image:
    """
    Intenta hacer transparente el fondo de la imagen basándose en el color de fondo de marca.
    Usa flood-fill desde las esquinas con tolerancia.
    Retorna RGBA.
    """
    img = img.convert("RGBA")
    pixel_data = img.load()
    if pixel_data is None:
        return img
    w, h = img.size

    paleta = brand.get("paleta", {}) if isinstance(brand.get("paleta"), dict) else {}
    bg_hex = paleta.get("bg") or paleta.get("primario") or "#0b1417"
    bg_rgb = hex_to_rgb(bg_hex)

    # Tolerancia de color para eliminar el fondo
    tol = 30

    def similar(pix: tuple[Any, ...], ref: tuple[int, int, int]) -> bool:
        return all(abs(int(pix[i]) - int(ref[i])) < tol for i in range(3))

    # Flood-fill desde las 4 esquinas
    from collections import deque

    visited = set()
    queue: deque[tuple[int, int]] = deque()
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    for cx, cy in corners:
        pix = cast(tuple[Any, ...], pixel_data[cx, cy])
        if similar(pix, bg_rgb) and (cx, cy) not in visited:
            queue.append((cx, cy))
            visited.add((cx, cy))

    while queue:
        x, y = queue.popleft()
        pixel_data[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                pix = cast(tuple[Any, ...], pixel_data[nx, ny])
                if similar(pix, bg_rgb):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    return img


def find_source_og(marca_slug: str, brand: dict) -> Image.Image | None:
    """Busca la mejor fuente para og-image: 1200x630."""
    family = "prizma" if "prizma" in marca_slug else "cloud_atlas"
    base = OUTPUT_DIR / marca_slug / "og" / "og_general"

    # Prizma: v1_docs o v2_enterprise_blog; Cloud Atlas: v1_website
    if family == "prizma":
        candidates = [
            "v1_docs.png",
            "v2_enterprise_blog.png",
            "v3_tool.png",
            "v1_website.png",
            "v1_articulo.png",
        ]
    else:
        candidates = [
            "v1_website.png",
            "v1_articulo.png",
            "v2_articulo.png",
            "v1_docs.png",
            "v3_feature.png",
        ]

    for name in candidates:
        p = base / name
        if p.exists():
            try:
                return Image.open(p).convert("RGB")
            except Exception as e:
                print(f"    WARN: No se pudo cargar {p}: {e}", file=sys.stderr)

    # Fallback: buscar cualquier PNG en og/og_general
    if base.exists():
        for p in sorted(base.glob("*.png")):
            try:
                return Image.open(p).convert("RGB")
            except Exception:
                pass

    print(
        f"  WARN: No se encontró fuente og-image para {marca_slug}. Generando placeholder.",
        file=sys.stderr,
    )
    return None


def generate_placeholder_icon(brand: dict, size: tuple[int, int] = ICON_512) -> Image.Image:
    """
    Genera un icono placeholder RGBA usando Pillow puro:
    fondo de acento de marca + símbolo/letra centrado.
    """
    paleta = brand.get("paleta", {}) if isinstance(brand.get("paleta"), dict) else {}
    bg_hex = paleta.get("acento") or "#43b5a6"
    texto_hex = paleta.get("texto") or "#e8e0d4"

    bg_rgb = hex_to_rgb(bg_hex)
    texto_rgb = hex_to_rgb(texto_hex)

    img = Image.new("RGBA", size, (*bg_rgb, 255))
    draw = ImageDraw.Draw(img)

    symbol = str(brand.get("logo_simbolo") or brand.get("simbolo") or "")
    if not symbol or len(symbol) > 3:
        # Usar inicial del nombre del producto
        nombre = str(brand.get("nombre_producto") or brand.get("slug") or "X")
        symbol = nombre[0].upper()

    # Intentar fuente grande
    font_size = int(size[0] * 0.5)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    # Centrar texto
    bbox = draw.textbbox((0, 0), symbol, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size[0] - tw) // 2 - bbox[0]
    y = (size[1] - th) // 2 - bbox[1]
    draw.text((x, y), symbol, fill=(*texto_rgb, 255), font=font)

    return img


def generate_placeholder_og(brand: dict) -> Image.Image:
    """
    Genera og-image placeholder: fondo primario + símbolo+nombre centrado.
    """
    paleta = brand.get("paleta", {}) if isinstance(brand.get("paleta"), dict) else {}
    bg_hex = paleta.get("bg") or paleta.get("primario") or "#0b1417"
    acento_hex = paleta.get("acento") or "#43b5a6"
    texto_hex = paleta.get("texto") or "#e8e0d4"

    bg_rgb = hex_to_rgb(bg_hex)
    acento_rgb = hex_to_rgb(acento_hex)
    texto_rgb = hex_to_rgb(texto_hex)

    img = Image.new("RGB", OG_SIZE, bg_rgb)
    draw = ImageDraw.Draw(img)

    # Barra de acento a la izquierda
    draw.rectangle([(0, 0), (8, OG_SIZE[1])], fill=acento_rgb)

    nombre = str(brand.get("nombre_producto") or brand.get("slug") or "")
    tagline = str(brand.get("tagline") or "")
    symbol = str(brand.get("logo_simbolo") or brand.get("simbolo") or "")
    if symbol:
        nombre = f"{symbol}  {nombre}"

    font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
    font_sub: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except Exception:
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 80)
            font_sub = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 40)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = font_title

    # Nombre centrado verticalmente
    y_center = OG_SIZE[1] // 2
    if nombre:
        bbox = draw.textbbox((0, 0), nombre, font=font_title)
        th = bbox[3] - bbox[1]
        draw.text((80, y_center - th - 20), nombre, fill=texto_rgb, font=font_title)
    if tagline:
        bbox = draw.textbbox((0, 0), tagline, font=font_sub)
        draw.text((80, y_center + 20), tagline, fill=(*acento_rgb,), font=font_sub)

    return img


def make_maskable(icon_512: Image.Image) -> Image.Image:
    """
    Genera icon-512-maskable: isotipo centrado dentro del safe-zone (80% central).
    El fondo puede ser de marca (o transparente si el original tiene alpha).
    Padding: MASKABLE_PADDING_RATIO * 512 = ~51px por lado.
    """
    pad = int(ICON_512[0] * MASKABLE_PADDING_RATIO)
    inner_size = (ICON_512[0] - 2 * pad, ICON_512[1] - 2 * pad)

    # Fondo transparente para el maskable
    maskable = Image.new("RGBA", ICON_512, (0, 0, 0, 0))

    # Redimensionar el isotipo para el área interior
    inner = icon_512.convert("RGBA").resize(inner_size, Image.Resampling.LANCZOS)
    maskable.paste(inner, (pad, pad), inner)

    return maskable


def make_apple_touch(icon_512: Image.Image, brand: dict) -> Image.Image:
    """
    Apple Touch Icon 180x180 RGB con fondo de marca (sin transparencia).
    Apple añade sus propios bordes redondeados, no hace falta que nosotros los apliquemos.
    """
    paleta = brand.get("paleta", {}) if isinstance(brand.get("paleta"), dict) else {}
    bg_hex = paleta.get("bg") or paleta.get("primario") or "#0b1417"
    bg_rgb = hex_to_rgb(bg_hex)

    # Pegar el isotipo centrado con padding ~10%
    pad = int(APPLE_TOUCH_SIZE[0] * MASKABLE_PADDING_RATIO)
    inner_size = (APPLE_TOUCH_SIZE[0] - 2 * pad, APPLE_TOUCH_SIZE[1] - 2 * pad)
    inner = icon_512.convert("RGBA").resize(inner_size, Image.Resampling.LANCZOS)

    # Componer sobre fondo de marca
    bg_layer = Image.new("RGBA", APPLE_TOUCH_SIZE, (*bg_rgb, 255))
    bg_layer.paste(inner, (pad, pad), inner)
    return bg_layer.convert("RGB")


def generate_web_icons(marca_slug: str, brand: dict, dry_run: bool = False) -> dict:
    """
    Genera el set web-icons completo para una marca.
    Retorna dict con path→(ok, tamaño_bytes).
    """
    out_dir = OUTPUT_DIR / marca_slug / "web-icons"
    results: dict[str, tuple[bool, int]] = {}

    if dry_run:
        print(f"  [DRY-RUN] {marca_slug} → {out_dir}")
        for name in [
            "favicon.ico",
            "favicon-16.png",
            "favicon-32.png",
            "apple-touch-icon.png",
            "icon-192.png",
            "icon-512.png",
            "icon-512-maskable.png",
            "og-image.png",
            "icon.svg",
        ]:
            results[name] = (True, 0)
        return results

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Fuente: isotipo ──────────────────────────────────────────────
    icon_src = find_source_icon(marca_slug, brand)
    if icon_src is None:
        icon_src = generate_placeholder_icon(brand, ICON_512)
    # Asegurar RGBA y tamaño 512
    icon_src = icon_src.convert("RGBA").resize(ICON_512, Image.Resampling.LANCZOS)

    # ── 1. favicon-16.png ────────────────────────────────────────────
    fav16 = icon_src.resize(FAVICON_16, Image.Resampling.LANCZOS)
    p = out_dir / "favicon-16.png"
    fav16.save(p, "PNG", optimize=True)
    results["favicon-16.png"] = (True, p.stat().st_size)

    # ── 2. favicon-32.png ────────────────────────────────────────────
    fav32 = icon_src.resize(FAVICON_32, Image.Resampling.LANCZOS)
    p = out_dir / "favicon-32.png"
    fav32.save(p, "PNG", optimize=True)
    results["favicon-32.png"] = (True, p.stat().st_size)

    # ── 3. favicon.ico (multi-res: 16+32+48) ────────────────────────
    # Pillow ICO: guardar la imagen más grande con sizes= para incluir
    # todas las resoluciones en el mismo .ico. Pillow genera las miniaturas
    # automáticamente desde la imagen fuente.
    ico_path = out_dir / "favicon.ico"
    # Usar 256x256 como base (máximo que ICO puede almacenar eficientemente)
    ico_base = icon_src.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
    ico_base.save(
        str(ico_path),
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    results["favicon.ico"] = (True, ico_path.stat().st_size)

    # ── 4. apple-touch-icon.png (180x180 RGB, fondo de marca) ───────
    apple = make_apple_touch(icon_src, brand)
    p = out_dir / "apple-touch-icon.png"
    apple.save(p, "PNG", optimize=True)
    results["apple-touch-icon.png"] = (True, p.stat().st_size)

    # ── 5. icon-192.png (RGBA) ───────────────────────────────────────
    icon192 = icon_src.resize(ICON_192, Image.Resampling.LANCZOS)
    p = out_dir / "icon-192.png"
    icon192.save(p, "PNG", optimize=True)
    results["icon-192.png"] = (True, p.stat().st_size)

    # ── 6. icon-512.png (RGBA) ───────────────────────────────────────
    p = out_dir / "icon-512.png"
    icon_src.save(p, "PNG", optimize=True)
    results["icon-512.png"] = (True, p.stat().st_size)

    # ── 7. icon-512-maskable.png (RGBA, padding ~10%) ────────────────
    maskable = make_maskable(icon_src)
    p = out_dir / "icon-512-maskable.png"
    maskable.save(p, "PNG", optimize=True)
    results["icon-512-maskable.png"] = (True, p.stat().st_size)

    # ── 8. og-image.png (1200x630 RGB) ──────────────────────────────
    og_src = find_source_og(marca_slug, brand)
    if og_src is None:
        og_src = generate_placeholder_og(brand)
    # Asegurar tamaño exacto 1200x630 (crop/resize si difiere)
    if og_src.size != OG_SIZE:
        og_src = og_src.resize(OG_SIZE, Image.Resampling.LANCZOS)
    og_src = og_src.convert("RGB")
    p = out_dir / "og-image.png"
    og_src.save(p, "PNG", optimize=True)
    results["og-image.png"] = (True, p.stat().st_size)

    # ── 9. icon.svg (derivado del símbolo de marca) ──────────────────
    svg_ok = generate_svg(marca_slug, brand, out_dir)
    results["icon.svg"] = (svg_ok, (out_dir / "icon.svg").stat().st_size if svg_ok else 0)

    return results


def generate_svg(marca_slug: str, brand: dict, out_dir: Path) -> bool:
    """
    Genera icon.svg: un SVG minimalista con el símbolo de marca.
    Usa colores de la paleta. No depende de Playwright.
    """
    paleta = brand.get("paleta", {}) if isinstance(brand.get("paleta"), dict) else {}
    bg = paleta.get("bg") or paleta.get("primario") or "#0b1417"
    acento = paleta.get("acento") or "#43b5a6"
    acento_2 = paleta.get("acento_2") or "#8d7cc0"

    symbol = str(brand.get("logo_simbolo") or brand.get("simbolo") or "")
    nombre = str(brand.get("nombre_producto") or brand.get("slug") or "")
    if not symbol and nombre:
        symbol = nombre[0].upper()

    # SVG 512x512 — viewBox 0 0 100 100 para escalado
    # Fondo: círculo con color de marca, texto centrado con degradado
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512" role="img" aria-label="{nombre}">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{acento}"/>
      <stop offset="100%" stop-color="{acento_2}"/>
    </linearGradient>
  </defs>
  <rect width="100" height="100" rx="16" fill="{bg}"/>
  <text
    x="50" y="50"
    dominant-baseline="central"
    text-anchor="middle"
    font-size="52"
    font-family="system-ui, -apple-system, sans-serif"
    font-weight="700"
    fill="url(#g)"
  >{symbol}</text>
</svg>
"""
    try:
        svg_path = out_dir / "icon.svg"
        svg_path.write_text(svg, encoding="utf-8")
        return True
    except Exception as e:
        print(f"    WARN: No se pudo escribir icon.svg: {e}", file=sys.stderr)
        return False


def verify_web_icons(marca_slug: str) -> dict:
    """
    Verifica los archivos generados: tamaño, formato, dimensiones.
    Retorna dict con info de verificación.
    """
    out_dir = OUTPUT_DIR / marca_slug / "web-icons"
    verification: dict[str, dict] = {}

    expected: dict[str, dict[str, str | tuple[int, int]]] = {
        "favicon.ico": {"format": "ICO"},
        "favicon-16.png": {"format": "PNG", "size": (16, 16)},
        "favicon-32.png": {"format": "PNG", "size": (32, 32)},
        "apple-touch-icon.png": {"format": "PNG", "size": (180, 180)},
        "icon-192.png": {"format": "PNG", "size": (192, 192)},
        "icon-512.png": {"format": "PNG", "size": (512, 512)},
        "icon-512-maskable.png": {"format": "PNG", "size": (512, 512)},
        "og-image.png": {"format": "PNG", "size": (1200, 630)},
        "icon.svg": {"format": "SVG"},
    }

    for fname, spec in expected.items():
        p = out_dir / fname
        entry: dict = {"exists": p.exists(), "path": str(p)}
        if p.exists():
            entry["bytes"] = p.stat().st_size
            if spec["format"] in ("PNG", "ICO"):
                try:
                    img = Image.open(p)
                    entry["pil_size"] = img.size
                    entry["pil_mode"] = img.mode
                    entry["pil_format"] = img.format
                    if spec["format"] == "ICO":
                        # Verificar que contiene múltiples tamaños
                        ico_sizes = set()
                        try:
                            import struct

                            raw = p.read_bytes()
                            count = struct.unpack_from("<H", raw, 4)[0]
                            for i in range(count):
                                off = 6 + i * 16
                                w = raw[off]
                                h = raw[off + 1]
                                w = 256 if w == 0 else w
                                h = 256 if h == 0 else h
                                ico_sizes.add((w, h))
                        except Exception:
                            ico_sizes = {img.size}
                        entry["ico_sizes"] = sorted(ico_sizes)
                        entry["size_ok"] = len(ico_sizes) >= 2
                    if "size" in spec:
                        entry["size_ok"] = img.size == spec["size"]
                    else:
                        entry["size_ok"] = True
                except Exception as e:
                    entry["pil_error"] = str(e)
                    entry["size_ok"] = False
            elif spec["format"] == "SVG":
                content = p.read_text(encoding="utf-8", errors="ignore")
                entry["has_viewbox"] = "viewBox" in content
                entry["size_ok"] = entry["has_viewbox"]
        else:
            entry["size_ok"] = False

        verification[fname] = entry

    return verification


def print_verification(marca_slug: str, verification: dict):
    """Imprime el reporte de verificación."""
    out_dir = OUTPUT_DIR / marca_slug / "web-icons"
    print(f"\n  Verificación web-icons [{marca_slug}]:")
    all_ok = True
    for fname, info in verification.items():
        if info["exists"]:
            size_ok = info.get("size_ok", True)
            pil_size = info.get("pil_size", "")
            pil_mode = info.get("pil_mode", "")
            bytes_str = f"{info.get('bytes', 0):,} B"
            dim_str = f" {pil_size} {pil_mode}" if pil_size else ""
            print(f"    {'✓' if size_ok else '⚠'} {fname:<28} {bytes_str:<12}{dim_str}")
            if not size_ok:
                all_ok = False
        else:
            print(f"    ✗ {fname:<28} FALTA")
            all_ok = False
    print(f"  {'All OK' if all_ok else 'Hay warnings'}: {out_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generador del set web-icons estándar (favicon, PWA, OG) por marca.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 web_icons.py --marca pinakotheke-kosmos
  python3 web_icons.py --all
  python3 web_icons.py --only-marcas pinakotheke-kosmos,prizma-iris
  python3 web_icons.py --marca pinakotheke-kosmos --dry-run
        """,
    )
    parser.add_argument("--marca", type=str, help="Slug de la marca")
    parser.add_argument(
        "--all", action="store_true", help="Procesa todas las marcas (excl. agora-*)"
    )
    parser.add_argument("--only-marcas", type=str, help="Lista separada por comas de slugs")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin escribir archivos")
    parser.add_argument("--verify-only", action="store_true", help="Solo verifica sin generar")
    args = parser.parse_args()

    if not args.marca and not args.all and not args.only_marcas:
        parser.print_help()
        print("\nERROR: Especifica --marca, --all, o --only-marcas", file=sys.stderr)
        return 1

    # Determinar marcas a procesar
    marcas: list[str] = []
    if args.all:
        if not MARCAS_DIR.exists():
            print(f"ERROR: {MARCAS_DIR} no existe", file=sys.stderr)
            return 1
        marcas = [
            f.stem for f in sorted(MARCAS_DIR.glob("*.json")) if not f.stem.startswith("agora-")
        ]
    elif args.only_marcas:
        marcas = [s.strip() for s in args.only_marcas.split(",") if s.strip()]
    else:
        marcas = [args.marca]

    total_ok = 0
    total_err = 0

    for slug in marcas:
        print(f"\n→ {slug}")
        brand = load_brand(slug)
        if brand is None:
            total_err += 1
            continue

        if args.verify_only:
            v = verify_web_icons(slug)
            print_verification(slug, v)
            continue

        try:
            results = generate_web_icons(slug, brand, dry_run=args.dry_run)
            ok_count = sum(1 for ok, _ in results.values() if ok)
            err_count = sum(1 for ok, _ in results.values() if not ok)
            print(
                f"  Generados: {ok_count}/{len(results)}" + (" [DRY-RUN]" if args.dry_run else "")
            )
            if err_count:
                print(f"  Errores:   {err_count}")
            for fname, (ok, sz) in results.items():
                sz_str = f"{sz:,} B" if sz else "-"
                print(f"    {'✓' if ok else '✗'} {fname:<28} {sz_str}")
            total_ok += ok_count
            total_err += err_count

            # Verificar resultados (no en dry-run)
            if not args.dry_run:
                v = verify_web_icons(slug)
                print_verification(slug, v)

        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            total_err += 1

    print(f"\n{'=' * 50}")
    print(f"Total: {total_ok} OK, {total_err} errores")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
