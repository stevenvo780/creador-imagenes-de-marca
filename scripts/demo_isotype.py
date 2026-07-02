#!/usr/bin/env python3
"""Demo: genera y RENDERIZA los 4 estilos de isotipo a PNG via Playwright.

Para 2 marcas (pinakotheke-kosmos, prizma-iris) x 4 estilos
(lettermark, geometric, abstract, enclosure) = 8 isotipos.

Cada estilo es un SVG procedural determinista (eikon_core.isotype). El demo:
  1. Guarda el SVG (+ data URI de referencia).
  2. Embebe el SVG en una pagina HTML y captura un PNG con Playwright.

Salida: output/_demo_isotype/ -> 8 PNG distintos y legibles (+ SVG/TXT).
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from PIL import Image

# Agregar el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core.brand import load_json
from eikon_core.isotype import IsotypeParams, generate_isotype
from eikon_core.mapping import map_marca_to_vars
from eikon_core.playwright_lazy import _get_playwright
from eikon_core.render import _capture_screenshot_with_retry, _wait_for_fonts_and_stabilize
from eikon_core.svg_generator import svg_to_base64_data_uri

BRANDS = ["pinakotheke-kosmos", "prizma-iris"]
STYLES = ["lettermark", "geometric", "abstract", "enclosure"]
# Lienzo claro: garantiza que el primario oscuro y el acento de marca sean legibles.
CARD_BG = "#efe9dd"


def _deterministic_seed(brand_slug: str, style: str) -> int:
    """Seed estable por marca+estilo (hash() de Python esta aleatorizado)."""
    seed_str = f"{brand_slug}:{style}"
    return int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


def _page_html(svg: str) -> str:
    """Envuelve un SVG de isotipo en una pagina 512x512 con tarjeta clara centrada."""
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><style>
      *{{margin:0;padding:0;box-sizing:border-box}}
      html,body{{width:512px;height:512px;overflow:hidden}}
      body{{display:flex;align-items:center;justify-content:center;background:{CARD_BG}}}
      .mark{{width:360px;height:360px;display:flex;align-items:center;justify-content:center}}
      .mark svg{{width:100%;height:100%}}
    </style></head><body><div class="mark">{svg}</div></body></html>"""


def _decoded_pixel_hash(png_path: Path) -> str:
    """sha256 de los pixeles decodificados (RGBA)."""
    with Image.open(png_path) as img:
        return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


def _build_isotypes(output_dir: Path) -> list[tuple[str, str]]:
    """Genera y guarda los 8 SVGs. Devuelve [(nombre_corto, svg), ...]."""
    eikon_root = Path(__file__).parent.parent
    built: list[tuple[str, str]] = []
    for brand_slug in BRANDS:
        marca_path = eikon_root / "marcas" / f"{brand_slug}.json"
        if not marca_path.exists():
            print(f"x Marca no encontrada: {marca_path}")
            continue
        marca = load_json(marca_path)
        vars_dict = map_marca_to_vars(marca, "favicon", variant_name="v1_32")
        brand_short = brand_slug.split("-")[-1]
        for style in STYLES:
            params = IsotypeParams(
                seed=_deterministic_seed(brand_slug, style),
                style=style,
                brand_initials=marca.get("nombre_producto", "X")[0],
                brand_symbol=marca.get("simbolo", "∞"),
                primary_color=vars_dict.get("primario", "#0b1417"),
                accent_color=vars_dict.get("acento", "#43b5a6"),
                bg_color=CARD_BG,
            )
            svg = generate_isotype(params)
            name = f"{brand_short}_{style}"
            (output_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
            (output_dir / f"{name}.txt").write_text(
                svg_to_base64_data_uri(svg), encoding="utf-8"
            )
            built.append((name, svg))
            print(f"+ {name}.svg generado")
    return built


async def render_isotypes() -> dict:
    """Genera SVGs y los renderiza a PNG. Devuelve resumen con hashes."""
    apw, _ = _get_playwright()
    eikon_root = Path(__file__).parent.parent
    output_dir = eikon_root / "output" / "_demo_isotype"
    output_dir.mkdir(parents=True, exist_ok=True)

    built = _build_isotypes(output_dir)

    hashes: list[tuple[str, str]] = []
    async with apw() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        try:
            for name, svg in built:
                # Escribir el HTML a disco y navegarlo via file:// (ruta probada por render.py;
                # set_content puede disparar "Unable to capture screenshot" intermitente).
                html_path = output_dir / f"_{name}.page.html"
                html_path.write_text(_page_html(svg), encoding="utf-8")

                context = await browser.new_context(
                    viewport={"width": 512, "height": 512},
                    device_scale_factor=2,
                    locale="es-ES",
                )
                page = await context.new_page()
                await page.goto(html_path.as_uri(), wait_until="domcontentloaded")
                await _wait_for_fonts_and_stabilize(page)
                await page.wait_for_timeout(120)
                png_path = output_dir / f"{name}.png"
                await _capture_screenshot_with_retry(page, png_path)
                await page.close()
                await context.close()
                html_path.unlink(missing_ok=True)
                h = _decoded_pixel_hash(png_path)
                hashes.append((name, h))
                print(f"+ {name}.png  pix_sha256={h}")
        finally:
            await browser.close()

    distinct = {h for _, h in hashes}
    print(f"\nRendered: {len(hashes)}/8   Distinct decoded-pixel hashes: {len(distinct)}/8")
    return {"rendered": len(hashes), "distinct": len(distinct), "hashes": hashes}


def main() -> int:
    """Punto de entrada. Exit 0 solo si hay 8 PNG con 8 hashes distintos."""
    print("-> Generando y renderizando isotipos...")
    result = asyncio.run(render_isotypes())
    ok = result["rendered"] == 8 and result["distinct"] == 8
    print(f"{'PASS' if ok else 'FAIL'}: rendered={result['rendered']}/8 distinct={result['distinct']}/8")
    print("Salida en output/_demo_isotype/")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
