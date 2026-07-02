#!/usr/bin/env python3
"""Demo: renderiza 12 combinaciones de logo deterministas y distintas.

Permuta tres ejes sobre el template logo_symbol_color:
- palette_scheme (3 opciones: brand, mono, light)
- background_treatment (2 opciones: solid, gradient)
- corner_shape (2 opciones: sharp, rounded)

Total: 3 x 2 x 2 = 12 combinaciones, cada una con un hash de PIXELES-DECODIFICADOS
distinto. Re-ejecutar produce exactamente los mismos 12 hashes (determinismo).

Salida: output/_demo_core/
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

# Agregar el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core import constants as cfg
from eikon_core.brand import load_json
from eikon_core.combinatorial import CombinationSpec, load_axes_config
from eikon_core.combinatorial.planner import plan_combinations
from eikon_core.orchestrator import render_combination
from eikon_core.playwright_lazy import _get_playwright

ASSET_TYPE = "logo_symbol_color"
MARCA_SLUG = "pinakotheke-kosmos"

# Ejes y opciones permutadas (3 x 2 x 2 = 12).
AXES_AVAILABLE = {
    "palette_scheme": ["brand", "mono", "light"],
    "background_treatment": ["solid", "gradient"],
    "corner_shape": ["sharp", "rounded"],
}


def decoded_pixel_hash(png_path: Path) -> str:
    """sha256 de los PIXELES decodificados (RGBA), no de los bytes del archivo."""
    with Image.open(png_path) as img:
        return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


async def render_12_combinations() -> dict:
    """Renderiza 12 combinaciones deterministas y devuelve sus hashes."""
    apw, _ = _get_playwright()

    axes_path = cfg.ROOT / "config" / "axes.json"
    axes_config = load_axes_config(axes_path)

    marca_path = cfg.MARCAS_DIR / f"{MARCA_SLUG}.json"
    marca = load_json(marca_path)

    spec = CombinationSpec(
        brand=MARCA_SLUG,
        asset_types=[ASSET_TYPE],
        fixed={},
        permuted=["palette_scheme", "background_treatment", "corner_shape"],
        count=12,
        seed_salt="demo_run",
    )

    plan = plan_combinations(spec, AXES_AVAILABLE)
    print(f"\nGenerated {len(plan)} combinations:")
    distinct_params = {tuple(sorted(c.params.items())) for c in plan}
    print(f"  distinct param-sets: {len(distinct_params)}/{len(plan)}")
    for combo in plan:
        print(f"  [{combo.idx:2d}] seed={combo.seed:016x} {combo.params}")

    output_dir = cfg.OUTPUT_DIR / "_demo_core"
    output_dir.mkdir(parents=True, exist_ok=True)

    hashes: list[tuple[int, str]] = []
    async with apw() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        try:
            for combo in plan:
                result = await render_combination(
                    browser,
                    MARCA_SLUG,
                    combo,
                    ASSET_TYPE,
                    marca,
                    axes_config,
                    cache=None,
                    dry_run=False,
                )
                if result["status"] != "generated":
                    print(f"  ✗ combo_{combo.idx:03d} status={result['status']} {result.get('warnings')}")
                    continue
                png_path = (
                    cfg.OUTPUT_DIR / MARCA_SLUG / "logos" / ASSET_TYPE / f"combo_{combo.idx:03d}.png"
                )
                if not png_path.exists():
                    print(f"  ✗ combo_{combo.idx:03d}.png no encontrado tras render")
                    continue
                h = decoded_pixel_hash(png_path)
                hashes.append((combo.idx, h))
                print(f"  ✓ combo_{combo.idx:03d}.png  pix_sha256={h}")
        finally:
            await browser.close()

    distinct_hashes = {h for _, h in hashes}
    manifest = {
        "spec": {
            "brand": spec.brand,
            "asset_type": ASSET_TYPE,
            "count": spec.count,
            "permuted": spec.permuted,
            "axes": AXES_AVAILABLE,
            "seed_salt": spec.seed_salt,
        },
        "combinations": [c.as_dict() for c in plan],
        "decoded_pixel_hashes": hashes,
        "rendered": len(hashes),
        "distinct": len(distinct_hashes),
    }
    manifest_path = output_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nManifest: {manifest_path}")
    print(f"Rendered: {len(hashes)}/12   Distinct decoded-pixel hashes: {len(distinct_hashes)}/12")
    return {
        "rendered": len(hashes),
        "distinct": len(distinct_hashes),
        "hashes": hashes,
        "manifest_path": str(manifest_path),
    }


def main() -> int:
    """Punto de entrada. Exit 0 solo si hay 12 renders con 12 hashes distintos."""
    result = asyncio.run(render_12_combinations())
    ok = result["rendered"] == 12 and result["distinct"] == 12
    print(f"\n{'PASS' if ok else 'FAIL'}: rendered={result['rendered']}/12 distinct={result['distinct']}/12")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
