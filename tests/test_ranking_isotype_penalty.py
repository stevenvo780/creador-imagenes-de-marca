"""Test ranking: placeholder isotopes ('none') MUST rank below real marks."""

from pathlib import Path

import pytest

from eikon_core.combinatorial.ranking import (
    _signal_placeholder_penalty,
    _signal_visual_richness,
)


def test_signal_placeholder_penalty_none():
    """Test that 'none' style gets 0.0 penalty signal."""
    params = {"isotype_style": "none"}
    sig = _signal_placeholder_penalty(params)

    assert sig.name == "placeholder_penalty"
    assert sig.value == 0.0
    assert sig.weight == 0.35
    assert "Placeholder" in sig.reason


def test_signal_placeholder_penalty_real():
    """Test that real styles get 1.0 penalty signal."""
    for style in ["lettermark", "geometric", "abstract", "enclosure"]:
        params = {"isotype_style": style}
        sig = _signal_placeholder_penalty(params)

        assert sig.value == 1.0, f"Failed for style={style}"
        assert sig.weight == 0.35
        assert "Real mark" in sig.reason or "real" in sig.reason.lower()


def test_signal_placeholder_penalty_missing():
    """Test that missing isotype_style is treated as real."""
    params = {}
    sig = _signal_placeholder_penalty(params)

    assert sig.value == 1.0
    assert sig.weight == 0.35


def test_signal_visual_richness_sparse():
    """Test visual richness on sparse content (like 3-dot placeholder)."""
    # Mock sparse image path (this would be a 3-dot image in reality)
    # For now, test that the function doesn't crash on a real file
    test_png = Path(__file__).parent / "../output/_demo_ranking_isotype/combo_000.png"
    if test_png.exists():
        sig = _signal_visual_richness(test_png)
        assert sig.name == "visual_richness"
        assert 0.0 <= sig.value <= 1.0
        assert sig.weight == 0.25


def test_ranking_preserves_placeholder_order():
    """Integration test: 'none' placeholders MUST rank below real marks.

    This is the core acceptance criterion.
    """
    test_dir = Path(__file__).parent / "../output/_demo_ranking_isotype"
    if not test_dir.exists():
        pytest.skip("Demo ranking output not found; run eikon_ranking_isotype_demo.py first")

    # Load variations from the demo manifest
    import json
    manifest_path = test_dir / "_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Manifest not found")

    with manifest_path.open() as f:
        manifest = json.load(f)

    ranked = manifest.get("ranking", [])
    if not ranked:
        pytest.skip("No ranked results in manifest")

    # Extract isotype_style for each ranked variation
    styles = [v["params"].get("isotype_style", "unknown") for v in ranked]

    # Find indices of 'none' and real marks
    none_indices = [i for i, s in enumerate(styles) if s == "none"]
    real_indices = [i for i, s in enumerate(styles) if s != "none"]

    # Core assertion: 'none' must come AFTER all real marks
    if none_indices and real_indices:
        max_real = max(real_indices)
        min_none = min(none_indices)
        assert min_none > max_real, (
            f"Placeholder 'none' ranked {min_none} but should be > {max_real} "
            f"(all reals must come before any placeholder)"
        )


def test_ranking_scores_reflect_penalty():
    """Test that scores numerically reflect placeholder penalty.

    For variations with similar visual properties, 'none' should score
    ~0.35 points LOWER (due to the 35% penalty_signal weight).
    """
    test_dir = Path(__file__).parent / "../output/_demo_ranking_isotype"
    if not test_dir.exists():
        pytest.skip("Demo ranking output not found")

    import json
    manifest_path = test_dir / "_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Manifest not found")

    with manifest_path.open() as f:
        manifest = json.load(f)

    ranked = manifest.get("ranking", [])
    if not ranked:
        pytest.skip("No ranked results")

    # Find a 'none' and a real mark with similar visual_richness
    none_vars = [v for v in ranked if v["params"].get("isotype_style") == "none"]
    real_vars = [v for v in ranked if v["params"].get("isotype_style") != "none"]

    if not none_vars or not real_vars:
        pytest.skip("Need both 'none' and real marks for comparison")

    none_var = none_vars[0]
    real_var = real_vars[0]

    # Compare penalty signal values
    none_penalty = next(
        (s["value"] for s in none_var["signals"] if s["name"] == "placeholder_penalty"),
        None,
    )
    real_penalty = next(
        (s["value"] for s in real_var["signals"] if s["name"] == "placeholder_penalty"),
        None,
    )

    assert none_penalty == 0.0, "Placeholder should have 0.0 penalty value"
    assert real_penalty == 1.0, "Real mark should have 1.0 penalty value"

    # The score difference should be ~0.35 (the weight) if other signals are similar
    score_diff = real_var["final_score"] - none_var["final_score"]
    assert score_diff >= 0.30, (
        f"Score difference too small: {score_diff:.3f} "
        f"(should be ~0.35 due to placeholder_penalty weight)"
    )
