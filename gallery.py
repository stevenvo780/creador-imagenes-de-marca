#!/usr/bin/env python3
"""
Galería HTML local para assets de marca renderizados.

Genera una página HTML con thumbnails de todos los PNGs en
output/<marca>/, agrupados por categoría. Lee el _manifest.json
si existe para enriquecer la metadata.

Uso:
    python gallery.py pinakotheke-kosmos
    python gallery.py pinakotheke-kosmos --output gallery.html
    python gallery.py --all-marcas
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
THUMB_SIZE = (560, 560)
JPEG_QUALITY = 82

GALLERY_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Galería EIKON — {marca}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0b1417;
    color: #e8e0d4;
    padding: 20px;
  }}
  h1 {{
    font-size: 1.6rem;
    color: #43b5a6;
    margin-bottom: 4px;
  }}
  .meta {{
    font-size: 0.85rem;
    color: #8fa3a8;
    margin-bottom: 24px;
  }}
  .stats {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 24px;
  }}
  .stat {{
    background: #131e22;
    border: 1px solid #1e2d33;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.85rem;
  }}
  .stat strong {{ color: #43b5a6; }}
  .category {{
    margin-bottom: 32px;
  }}
  .category h2 {{
    font-size: 1.15rem;
    color: #e0a85e;
    border-bottom: 1px solid #1e2d33;
    padding-bottom: 6px;
    margin-bottom: 12px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: #131e22;
    border: 1px solid #1e2d33;
    border-radius: 8px;
    overflow: hidden;
    transition: border-color 0.2s;
  }}
  .card:hover {{ border-color: #43b5a6; }}
  .card a {{
    text-decoration: none;
    color: inherit;
    display: block;
  }}
  .card img {{
    display: block;
    width: 100%;
    height: auto;
    max-width: 100%;
    object-fit: contain;
    background: #0b1417;
  }}
  .card-info {{
    padding: 8px 10px;
    font-size: 0.78rem;
    line-height: 1.4;
  }}
  .card-name {{
    color: #e8e0d4;
    font-weight: 600;
    margin-bottom: 2px;
  }}
  .card-dims {{
    color: #8fa3a8;
    font-size: 0.72rem;
  }}
  .card-badge {{
    display: inline-block;
    background: #1e2d33;
    color: #43b5a6;
    font-size: 0.68rem;
    padding: 1px 6px;
    border-radius: 3px;
    margin-top: 4px;
  }}
  .card-badge.cached {{ background: #2d331e; color: #a6b543; }}
  .card-badge.error {{ background: #331e1e; color: #b54343; }}
  footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #1e2d33;
    font-size: 0.78rem;
    color: #8fa3a8;
    text-align: center;
  }}
</style>
</head>
<body>
<h1>🎨 {marca}</h1>
<div class="meta">{generated_at} · {engine_version} · {total} assets</div>

<div class="stats">
  <div class="stat">Generados: <strong>{generated}</strong></div>
  <div class="stat">Cache: <strong>{cached}</strong></div>
  <div class="stat">Errores: <strong>{errors}</strong></div>
</div>

{categories}

<footer>
  Galería generada por EIKON · {timestamp}
</footer>
</body>
</html>
"""


def make_thumbnail(png_path: Path) -> str:
    """Crea thumbnail base64 de un PNG."""
    if not HAS_PIL:
        return "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='560' height='320'%3E%3Crect fill='%23131e22' width='560' height='320'/%3E%3Ctext fill='%238fa3a8' x='50%25' y='50%25' text-anchor='middle' dy='.3em' font-size='16'%3Esin Pillow%3C/text%3E%3C/svg%3E"

    try:
        img = Image.open(png_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (11, 20, 23, 255))
            img = Image.alpha_composite(bg, img)
        img = img.convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"  ⚠ Error thumbnail {png_path.name}: {e}", file=sys.stderr)
        return ""


def load_manifest(marca_slug: str) -> dict | None:
    """Carga _manifest.json si existe."""
    manifest_path = OUTPUT_DIR / marca_slug / "_manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def build_gallery(marca_slug: str) -> str:
    """Construye HTML de galería para una marca."""
    marca_dir = OUTPUT_DIR / marca_slug
    if not marca_dir.exists():
        return f"<p>Directorio {marca_dir} no existe.</p>"

    manifest = load_manifest(marca_slug)

    # Si hay manifest, usar sus datos
    assets_by_cat: dict[str, list[dict]] = {}
    generated = cached = errors_count = 0
    total = 0

    if manifest:
        for asset in manifest.get("assets", []):
            cat = asset.get("category", "otros")
            assets_by_cat.setdefault(cat, []).append(asset)
            total += 1
            if asset.get("status") == "generated":
                generated += 1
            elif asset.get("status") == "cached":
                cached += 1
            elif asset.get("status") in ("error", "dry_run"):
                errors_count += 1
        generated_at = manifest.get("generated_at", "")[:16].replace("T", " ")
        engine_version = manifest.get("engine_version", "")
    else:
        # Fallback: escanear PNGs
        for png in sorted(marca_dir.rglob("*.png")):
            if png.name.startswith("_"):
                continue
            rel = png.relative_to(marca_dir)
            parts = rel.parts
            cat = parts[0] if len(parts) > 1 else "root"
            type_name = parts[1] if len(parts) > 2 else png.stem

            asset = {
                "path": str(rel),
                "category": cat,
                "type": type_name,
                "variant": png.stem,
                "width": 0,
                "height": 0,
                "status": "unknown",
            }
            # Intentar leer dimensiones reales
            try:
                from PIL import Image

                with Image.open(png) as img:
                    asset["width"] = img.width
                    asset["height"] = img.height
            except Exception:
                pass

            assets_by_cat.setdefault(cat, []).append(asset)
            total += 1
        generated = total
        generated_at = "(sin manifest)"
        engine_version = ""

    # Construir HTML de categorías
    categories_html = ""
    for cat_name in sorted(assets_by_cat):
        assets = assets_by_cat[cat_name]
        cat_title = cat_name.capitalize()
        cards = ""

        for a in assets:
            png_path = OUTPUT_DIR / marca_slug / a["path"]
            thumb = make_thumbnail(png_path) if HAS_PIL else ""
            name = a.get("type", a.get("variant", ""))
            variant = a.get("variant", "")
            display_name = f"{name} · {variant}" if variant and variant != name else name
            dims = f"{a.get('width', 0)}×{a.get('height', 0)}" if a.get("width", 0) > 0 else ""  # noqa: RUF001 (multiplication sign is intentional dimension separator)
            status = a.get("status", "unknown")
            badge_class = f" {status}" if status in ("cached", "error") else ""

            cards += f"""
        <div class="card">
          <a href="{a["path"]}" target="_blank">
            <img src="{thumb}" alt="{display_name}" loading="lazy">
            <div class="card-info">
              <div class="card-name">{display_name}</div>
              <div class="card-dims">{dims}</div>
              <div class="card-badge{badge_class}">{status}</div>
            </div>
          </a>
        </div>"""

        categories_html += f"""
  <div class="category">
    <h2>{cat_title} ({len(assets)})</h2>
    <div class="grid">{cards}
    </div>
  </div>"""

    from datetime import datetime

    return GALLERY_TEMPLATE.format(
        marca=marca_slug,
        generated_at=generated_at,
        engine_version=engine_version,
        total=total,
        generated=generated,
        cached=cached,
        errors=errors_count,
        categories=categories_html,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def build_aggregated_gallery(marca_slugs: list[str]) -> str:
    """Construye una galería HTML agregada con todas las marcas en una sola página."""
    all_categories_html = ""
    total_assets = 0
    total_generated = 0
    total_cached = 0
    total_errors = 0

    for slug in marca_slugs:
        manifest = load_manifest(slug)
        if not manifest:
            continue

        all_categories_html += (
            f'<h2 style="color:#43b5a6;margin-top:32px;font-size:1.3rem;">{slug}</h2>\n'
        )

        assets_by_cat: dict[str, list[dict]] = {}
        for asset in manifest.get("assets", []):
            cat = asset.get("category", "otros")
            assets_by_cat.setdefault(cat, []).append(asset)
            total_assets += 1
            if asset.get("status") == "generated":
                total_generated += 1
            elif asset.get("status") == "cached":
                total_cached += 1
            elif asset.get("status") in ("error", "dry_run"):
                total_errors += 1

        for cat_name in sorted(assets_by_cat):
            assets = assets_by_cat[cat_name]
            cards = ""
            for a in assets:
                png_path = OUTPUT_DIR / slug / a["path"]
                thumb = make_thumbnail(png_path) if HAS_PIL else ""
                name = a.get("type", a.get("variant", ""))
                variant = a.get("variant", "")
                display_name = f"{name} · {variant}" if variant and variant != name else name
                dims = f"{a.get('width', 0)}×{a.get('height', 0)}" if a.get("width", 0) > 0 else ""  # noqa: RUF001 (multiplication sign is intentional dimension separator)
                status = a.get("status", "unknown")
                badge_class = f" {status}" if status in ("cached", "error") else ""
                cards += f"""
        <div class="card">
          <a href="{slug}/{a["path"]}" target="_blank">
            <img src="{thumb}" alt="{display_name}" loading="lazy">
            <div class="card-info">
              <div class="card-name">{display_name}</div>
              <div class="card-dims">{dims}</div>
              <div class="card-badge{badge_class}">{status}</div>
            </div>
          </a>
        </div>"""
            all_categories_html += f"""
  <div class="category">
    <h3>{cat_name.capitalize()} ({len(assets)})</h3>
    <div class="grid">{cards}
    </div>
  </div>"""

    from datetime import datetime

    return GALLERY_TEMPLATE.format(
        marca="TODAS LAS MARCAS (agregado)",
        generated_at="",
        engine_version="",
        total=total_assets,
        generated=total_generated,
        cached=total_cached,
        errors=total_errors,
        categories=all_categories_html,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Galería HTML de assets de marca")
    parser.add_argument("marca", nargs="?", help="Slug de la marca (ej. pinakotheke-kosmos)")
    parser.add_argument(
        "--all-marcas",
        "--all",
        action="store_true",
        dest="all_marcas",
        help="Genera galerías para todas las marcas",
    )
    parser.add_argument(
        "--aggregated",
        action="store_true",
        help="Genera una galería agregada (todas las marcas en un solo HTML)",
    )
    parser.add_argument("--output", type=str, help="Ruta del archivo HTML de salida")
    args = parser.parse_args()

    if not args.marca and not args.all_marcas:
        parser.print_help()
        print("\n✗ Error: Especifica una marca, --all, o --all-marcas")
        return 1

    if args.all_marcas:
        marca_dirs = sorted(
            d.name
            for d in OUTPUT_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        )
        if not marca_dirs:
            print("✗ No se encontraron marcas en output/")
            return 1

        if args.aggregated:
            # Una sola galería agregada
            print(f"Generando galería agregada para {len(marca_dirs)} marcas...")
            html = build_aggregated_gallery(marca_dirs)
            out_path = Path(args.output) if args.output else OUTPUT_DIR / "_gallery_aggregated.html"
            out_path.write_text(html, encoding="utf-8")
            print(f"  ✓ Galería agregada: {out_path}")
        else:
            # Galerías individuales
            print(f"Generando galerías para {len(marca_dirs)} marcas...")
            for slug in marca_dirs:
                html = build_gallery(slug)
                out_path = OUTPUT_DIR / f"_gallery_{slug}.html"
                out_path.write_text(html, encoding="utf-8")
                print(f"  ✓ {out_path}")
        return 0
    else:
        slug = args.marca
        html = build_gallery(slug)
        out_path = Path(args.output) if args.output else OUTPUT_DIR / f"_gallery_{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"✓ Galería guardada: {out_path}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
