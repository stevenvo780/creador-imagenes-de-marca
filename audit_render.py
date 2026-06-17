#!/usr/bin/env python3
"""Audita layouts de marca renderizados en DOM antes de exportar PNG.

Detecta tres problemas típicos del sistema:
- texto visible por debajo de mínimos prácticos;
- overflow/clipping después del autoajuste;
- duplicación de título/subtítulo/copy dentro de una misma pieza.
"""

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

import render


TEXT_MIN = {
    "data-titulo": 32,
    "data-subtitulo": 15,
    "data-copy": 15,
    "data-url": 11,
    "data-logo-texto": 11,
}

EXCLUDED_LAYOUTS = {
    "app_icon_1024",
    "favicon_512",
    "favicon_192",
    "favicon_180",
    "favicon_32",
    "logo_symbol_color",
    "logo_symbol_mono",
}


def threshold_for(layout_id: str, attrs: list[str]) -> int:
    if layout_id in EXCLUDED_LAYOUTS:
        return 0
    if layout_id == "banner_ad" and "data-titulo" in attrs:
        return 24
    if layout_id.startswith("logo_"):
        return 10
    for attr, min_size in TEXT_MIN.items():
        if attr in attrs:
            return min_size
    return 0


def has_orphan_line(line_texts: list[str]) -> bool:
    if len(line_texts) < 2:
        return False
    for line in line_texts[1:]:
        if 0 < len(render.compare_key(line)) <= 2:
            return True
    return False


async def audit_one(browser, marca_slug: str, layout: dict) -> list[str]:
    tmpl_path = render.TMPL_DIR / layout["template"]
    layout_scale = int(layout.get("scale") or (2 if layout["id"].endswith("_2x") else 1))
    width = layout["ancho"] // layout_scale
    height = layout["alto"] // layout_scale

    marca = render.load_marca(marca_slug)
    vars_dict = render.build_vars(marca, layout)
    issues: list[str] = []

    context = await browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=layout_scale,
    )
    page = await context.new_page()
    try:
        await page.goto(f"file://{tmpl_path}", wait_until="networkidle", timeout=15000)
        await page.evaluate(render.inject_css_vars_js(vars_dict))
        try:
            await page.evaluate("() => document.fonts ? document.fonts.ready : null")
        except Exception:
            pass
        await page.wait_for_timeout(120)
        await page.evaluate(
            "() => {"
            " if (typeof window.__fitBrandText === 'function') window.__fitBrandText();"
            " if (typeof window.__fitTitulo === 'function') window.__fitTitulo();"
            "}"
        )
        items = await page.evaluate("() => window.__auditBrandFrame ? window.__auditBrandFrame() : []")
    finally:
        await page.close()
        await context.close()

    comparable: list[tuple[str, str]] = []
    for item in items:
        text = item.get("text", "")
        attrs = item.get("attrs", [])
        if not text or item.get("display") == "none":
            continue
        if any(item.get(k) for k in ("overflowX", "overflowY")):
            issues.append(f"overflow en {attrs}: {text[:64]}")
        min_size = threshold_for(layout["id"], attrs)
        if min_size and item.get("fontSize", 0) < min_size:
            issues.append(
                f"texto pequeño {item.get('fontSize', 0):.0f}px < {min_size}px en {attrs}: {text[:64]}"
            )
        if "data-titulo" in attrs and has_orphan_line(item.get("lineTexts", [])):
            lines = " / ".join(item.get("lineTexts", []))
            issues.append(f"linea huerfana en titulo: {lines[:96]}")
        if any(attr in attrs for attr in ("data-titulo", "data-subtitulo", "data-copy")):
            comparable.append((",".join(attrs), text))

    seen: dict[str, tuple[str, str]] = {}
    for attrs, text in comparable:
        key = render.compare_key(text)
        if not key:
            continue
        if key in seen:
            prev_attrs, prev_text = seen[key]
            issues.append(f"duplicado {prev_attrs} / {attrs}: {prev_text[:48]}")
        else:
            seen[key] = (attrs, text)

    return issues


async def audit(marca_arg: str, layout_arg: str | None, concurrency: int) -> int:
    layouts = render.load_layouts()
    if layout_arg:
        layouts = [layout for layout in layouts if layout["id"] == layout_arg]
        if not layouts:
            raise SystemExit(f"Layout no encontrado: {layout_arg}")

    if marca_arg == "all":
        marcas = sorted(path.stem for path in render.MARCAS_DIR.glob("*.json"))
    else:
        marcas = [marca_arg]

    semaphore = asyncio.Semaphore(concurrency)
    total_issues = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            async def run_one(slug: str, layout: dict) -> tuple[str, str, list[str]]:
                async with semaphore:
                    issues = await audit_one(browser, slug, layout)
                    return slug, layout["id"], issues

            tasks = [run_one(slug, layout) for slug in marcas for layout in layouts]
            for result in await asyncio.gather(*tasks):
                slug, layout_id, issues = result
                if not issues:
                    continue
                total_issues += len(issues)
                print(f"[{slug}/{layout_id}]")
                for issue in issues:
                    print(f"  - {issue}")
        finally:
            await browser.close()

    if total_issues:
        print(f"\nIssues: {total_issues}")
    else:
        print("Sin issues de texto/overflow detectados.")
    return total_issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoría DOM de imágenes de marca antes del PNG")
    parser.add_argument("--marca", required=True, help="Slug de marca o 'all'")
    parser.add_argument("--layout", help="Auditar solo un layout")
    parser.add_argument("--concurrencia", type=int, default=6)
    args = parser.parse_args()

    if not render.PLAYWRIGHT_OK:
        raise SystemExit("Playwright no está instalado.")

    issues = asyncio.run(audit(args.marca, args.layout, args.concurrencia))
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
