#!/usr/bin/env python3
"""Demo: verifica que placeholders (isotype_style='none') rankean ABAJO de marcas reales.

Genera 8 variaciones del MISMO brand permutando isotype_style: [none, lettermark, geometric, enclosure]
+ 2 paletas (brand, mono). Rankea y valida orden: 'none' siempre al final.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core import constants as cfg
from eikon_core.brand import load_json
from eikon_core.combinatorial import CombinationSpec, load_axes_config
from eikon_core.combinatorial.planner import plan_combinations
from eikon_core.combinatorial.ranking import rank
from eikon_core.orchestrator import render_combination
from eikon_core.playwright_lazy import _get_playwright

ASSET_TYPE = "logo_symbol_color"
MARCA_SLUG = "pinakotheke-kosmos"

# Ejes permutados: isotype_style x palette_scheme
AXES_AVAILABLE = {
    "isotype_style": ["none", "lettermark", "geometric", "enclosure"],
    "palette_scheme": ["brand", "mono"],
}


async def render_and_rank() -> dict:
    """Renderiza 8 variaciones y rankea."""
    apw, _ = _get_playwright()

    axes_path = cfg.ROOT / "config" / "axes.json"
    axes_config = load_axes_config(axes_path)

    marca_path = cfg.MARCAS_DIR / f"{MARCA_SLUG}.json"
    marca = load_json(marca_path)

    spec = CombinationSpec(
        brand=MARCA_SLUG,
        asset_types=[ASSET_TYPE],
        fixed={},
        permuted=list(AXES_AVAILABLE.keys()),
        count=8,
        seed_salt="ranking_isotype_demo",
    )

    plan = plan_combinations(spec, AXES_AVAILABLE)
    print(f"\n📋 Planned {len(plan)} combinations:")
    for combo in plan:
        print(f"  [{combo.idx:2d}] {combo.params}")

    output_dir = cfg.OUTPUT_DIR / "_demo_ranking_isotype"
    output_dir.mkdir(parents=True, exist_ok=True)

    variations_list = []
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
                    print(
                        f"  ✗ combo_{combo.idx:03d} status={result['status']}"
                    )
                    continue
                png_path = (
                    cfg.OUTPUT_DIR / MARCA_SLUG / "logos" / ASSET_TYPE / f"combo_{combo.idx:03d}.png"
                )
                if not png_path.exists():
                    print(f"  ✗ combo_{combo.idx:03d}.png not found after render")
                    continue

                # Copy to demo dir
                import shutil
                demo_path = output_dir / f"combo_{combo.idx:03d}.png"
                shutil.copy(png_path, demo_path)

                var_dict = combo.as_dict()
                var_dict["layout_warnings"] = result.get("layout_warnings", [])
                variations_list.append(var_dict)
                print(f"  ✓ combo_{combo.idx:03d}.png  params={combo.params}")
        finally:
            await browser.close()

    # Rank
    print(f"\n🏆 Ranking {len(variations_list)} variations...")
    ranked = rank(
        variations_list,
        output_dir,
        top_n=8,
        dedup_distance_threshold=20,
        permuted_axes=AXES_AVAILABLE,
    )

    print(f"\nTop {len(ranked)} ranked (best → worst):")
    for i, score in enumerate(ranked, 1):
        isotype = score.params.get("isotype_style", "?")
        palette = score.params.get("palette_scheme", "?")
        print(
            f"  [{i}] idx={score.idx:2d} isotype_style='{isotype:12s}' "
            f"palette_scheme='{palette:6s}' final_score={score.final_score:.3f}"
        )
        for sig in score.signals:
            print(
                f"      - {sig.name:20s} w={sig.weight:.2f} val={sig.value:.2f} | {sig.reason}"
            )

    # Validate: 'none' should appear LAST (indices >= real ones)
    none_indices = [i for i, s in enumerate(ranked) if s.params.get("isotype_style") == "none"]
    real_indices = [i for i, s in enumerate(ranked) if s.params.get("isotype_style") != "none"]

    result_dict = {
        "rendered": len(variations_list),
        "ranked": len(ranked),
        "permuted_axes": AXES_AVAILABLE,
        "ranking": [s.as_dict() for s in ranked],
        "validation": {
            "none_ranks": none_indices,
            "real_ranks": real_indices,
            "pass": (not none_indices) or (
                max(none_indices) > max(real_indices) if real_indices else True
            ),
        },
    }

    manifest_path = output_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(result_dict, indent=2, ensure_ascii=False))

    print(f"\n📄 Manifest: {manifest_path}")
    print(
        f"\n✅ VALIDATION: "
        f"'none' ranks = {result_dict['validation']['none_ranks']} "
        f"(should be >= max real ranks {max(result_dict['validation']['real_ranks']) if result_dict['validation']['real_ranks'] else 'N/A'})"
    )
    return result_dict


def main() -> int:
    """Entry point."""
    result = asyncio.run(render_and_rank())
    ok = result["validation"]["pass"]
    print(f"\n{'✅ PASS' if ok else '❌ FAIL'}: 'none' placeholders ranked below real marks")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
