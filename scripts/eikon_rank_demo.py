#!/usr/bin/env python3
"""Demo script: ranks 20 variations down to top-8 using perceptual diversity + WCAG.

Demonstrates the ranking engine by:
1. Generating 20 distinct banner variations for pinakotheke-kosmos
2. Rendering each to PNG
3. Scoring via: WCAG AA contrast, layout status, perceptual diversity, foreground balance
4. Deduplicating near-identical variations (dHash distance)
5. Saving top-8 to output/_demo_rank/

Acceptance criteria:
- 20 variations generated, ranked, deduplicated
- Top-8 are pairwise-distinct (dHash distance >= threshold)
- All top-8 pass WCAG AA (4.5:1 contrast minimum)
- Scores and reasons exported to JSON manifest
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core import constants as cfg
from eikon_core.brand import load_json
from eikon_core.combinatorial import CombinationSpec, load_axes_config
from eikon_core.combinatorial.planner import plan_combinations
from eikon_core.combinatorial.ranking import rank
from eikon_core.orchestrator import render_combination
from eikon_core.playwright_lazy import _get_playwright


async def _render_combinations(
    plan: Any,
    marca_slug: str,
    marca: dict,
    axes_config: Any,
    apw: Any,
) -> tuple[list[dict], Path]:
    """Render all combinations and return metadata + output dir."""
    output_dir = cfg.OUTPUT_DIR / "_demo_rank"
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered_variations = []
    async with apw() as pw:
        browser = await pw.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage"]
        )
        try:
            for combo in plan:
                try:
                    result = await render_combination(
                        browser,
                        marca_slug,
                        combo,
                        "ad_leaderboard",
                        marca,
                        axes_config,
                        cache=None,
                        dry_run=False,
                    )

                    if result["status"] == "generated":
                        rendered_variations.append({
                            "idx": combo.idx,
                            "seed": combo.seed,
                            "params": combo.params,
                            "marca": marca_slug,
                            "asset_type": "ad_leaderboard",
                            "layout_warnings": result.get("layout_warnings", []),
                            "status": "generated",
                        })
                        print(f"  ✓ combo_{combo.idx:03d} rendered")
                    else:
                        print(f"  ✗ combo_{combo.idx:03d} failed: {result.get('status')}")
                except Exception as e:
                    print(f"  ✗ combo_{combo.idx:03d} exception: {e}")

        finally:
            await browser.close()

    print(f"\n→ Rendered {len(rendered_variations)}/{len(plan)} variations successfully")

    # Copy PNGs to demo directory
    source_dir = cfg.OUTPUT_DIR / marca_slug / "banners" / "ad_leaderboard"
    if source_dir.exists():
        for combo in plan:
            src = source_dir / f"combo_{combo.idx:03d}.png"
            dst = output_dir / f"combo_{combo.idx:03d}.png"
            if src.exists() and not dst.exists():
                import shutil

                shutil.copy2(src, dst)

    return rendered_variations, output_dir


def _verify_and_save_results(
    ranked: list, marca_slug: str, rendered_variations: list, output_dir: Path
) -> dict:
    """Verify results and save manifest."""
    from eikon_core.combinatorial.ranking import _dhash_distance

    # Verify pairwise distinctness
    threshold = 20
    all_distinct = True
    print("\n→ Pairwise dHash distances (top-8):")
    for i, score1 in enumerate(ranked):
        for _j, score2 in enumerate(ranked[i + 1 :], i + 1):
            dist = _dhash_distance(score1.dhash, score2.dhash)
            is_distinct = "✓" if dist >= threshold else "✗"
            if dist < threshold:
                all_distinct = False
            print(
                f"  combo_{score1.idx:03d} ↔ combo_{score2.idx:03d}: "
                f"{dist}/64 bits {is_distinct}"
            )

    # Verify WCAG AA compliance
    wcag_passes = 0
    print("\n→ WCAG AA compliance check (top-8):")
    for scored in ranked:
        wcag_signal = next(
            (s for s in scored.signals if s.name == "wcag_contrast"), None
        )
        if wcag_signal and wcag_signal.value >= 0.9:
            wcag_passes += 1
            print(f"  ✓ combo_{scored.idx:03d}: {wcag_signal.reason}")
        else:
            print(
                f"  ✗ combo_{scored.idx:03d}: "
                f"{wcag_signal.reason if wcag_signal else 'no signal'}"
            )

    # Save manifest
    manifest = {
        "spec": {
            "brand": marca_slug,
            "asset_type": "ad_leaderboard",
            "total_generated": len(rendered_variations),
            "top_n": len(ranked),
            "dedup_threshold": 20,
        },
        "top_ranked": [score.as_dict() for score in ranked],
        "stats": {
            "total_variations": len(rendered_variations),
            "top_8_count": len(ranked),
            "wcag_aa_pass": wcag_passes,
            "wcag_aa_pass_rate": f"{wcag_passes}/{len(ranked)}",
            "all_pairwise_distinct": all_distinct,
        },
    }

    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Manifest saved: {manifest_path}")

    return {
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "total_generated": len(rendered_variations),
        "top_8_count": len(ranked),
        "wcag_aa_pass": wcag_passes,
        "all_pairwise_distinct": all_distinct,
        "top_indices": [s.idx for s in ranked],
    }


async def render_20_variations() -> dict:
    """Render 20 deterministic banner variations for ranking demo."""
    apw, _ = _get_playwright()

    # Load axes config
    axes_path = cfg.ROOT / "config" / "axes.json"
    axes_config = load_axes_config(axes_path)

    # Load brand
    marca_slug = "pinakotheke-kosmos"
    marca_path = cfg.MARCAS_DIR / f"{marca_slug}.json"
    marca = load_json(marca_path)

    # Define combo spec
    spec = CombinationSpec(
        brand=marca_slug,
        asset_types=["ad_leaderboard"],
        fixed={},
        permuted=[
            "palette_scheme",
            "background_treatment",
            "corner_shape",
        ],
        count=20,
        seed_salt="rank_demo_v1",
    )

    # Available axes
    axes_available = {
        "palette_scheme": ["brand", "mono", "light"],
        "background_treatment": ["solid", "gradient"],
        "corner_shape": ["sharp", "rounded"],
    }

    # Plan combinations
    plan = plan_combinations(spec, axes_available)
    print(f"\n→ Generated {len(plan)} combinations for ranking:")
    for combo in plan[:5]:
        print(f"  [{combo.idx:2d}] {combo.params}")
    if len(plan) > 5:
        print(f"  ... ({len(plan) - 5} more)")

    # Render combinations
    rendered_variations, output_dir = await _render_combinations(
        plan, marca_slug, marca, axes_config, apw
    )

    # Rank variations
    print("\n→ Ranking variations...")
    ranked = rank(
        rendered_variations,
        png_dir=output_dir,
        top_n=8,
        dedup_distance_threshold=20,
    )

    print("\n→ Top-8 variations (after deduplication):")
    for i, scored in enumerate(ranked, 1):
        wcag_signal = next(
            (s for s in scored.signals if s.name == "wcag_contrast"), None
        )
        wcag_status = "✓ AA" if wcag_signal and wcag_signal.value >= 0.9 else "✗ FAIL"
        print(
            f"  [{i}] combo_{scored.idx:03d}: "
            f"score={scored.final_score:.3f} {wcag_status} dhash={scored.dhash[:16]}..."
        )
        for signal in scored.signals:
            print(f"      - {signal.name}: {signal.value:.2f} ({signal.reason})")

    # Verify and save
    return _verify_and_save_results(ranked, marca_slug, rendered_variations, output_dir)


def main():
    """Entry point."""
    result = asyncio.run(render_20_variations())
    print("\n" + "=" * 70)
    print("Demo complete:")
    print(json.dumps(result, indent=2))
    print("=" * 70)


if __name__ == "__main__":
    main()
