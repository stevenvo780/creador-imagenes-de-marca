"""Ranking and deduplication for variation scoring.

Scores variations by:
1. WCAG AA contrast (floor: 4.5:1 min, hard requirement)
2. Layout status/warnings (penalize fail/warn)
3. Perceptual diversity (dHash to detect near-identical, reward diverse)
4. Aesthetic heuristic (balanced foreground coverage)

Returns top-N variations with scores and reasons, deterministically.
No new dependencies: reuses Pillow + numpy (already required).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image
except ImportError as err:
    raise ImportError(
        "Ranking requires Pillow and numpy. Install with: pip install Pillow numpy"
    ) from err


@dataclass(frozen=True)
class RankingSignal:
    """A single scoring signal contributing to the final rank."""

    name: str
    weight: float
    value: float
    reason: str


@dataclass(frozen=True)
class VariationScore:
    """Scored variation with top-level score and contributing signals."""

    idx: int
    seed: int
    params: dict[str, str]
    marca: str
    asset_type: str
    png_path: Path
    final_score: float
    signals: tuple[RankingSignal, ...] = field(default_factory=tuple)
    dhash: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "idx": self.idx,
            "seed": self.seed,
            "params": dict(self.params),
            "marca": self.marca,
            "asset_type": self.asset_type,
            "png_path": str(self.png_path),
            "final_score": round(self.final_score, 3),
            "dhash": self.dhash,
            "signals": [
                {
                    "name": s.name,
                    "weight": s.weight,
                    "value": round(s.value, 2),
                    "reason": s.reason,
                }
                for s in self.signals
            ],
        }


def _compute_dhash(img_path: Path, size: int = 8) -> str:
    """Compute perceptual dHash (difference hash) for image.

    Args:
        img_path: Path to PNG image
        size: Hash grid size (8x8 default)

    Returns:
        Hex string of hash (64 bits for 8x8)
    """
    try:
        img = Image.open(img_path).convert("L")
        img = img.resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = np.array(img)

        # Compute horizontal gradients
        diff = pixels[:, :-1].astype(np.int16) < pixels[:, 1:].astype(np.int16)
        return "".join("1" if bit else "0" for bit in diff.flatten())
    except Exception as e:
        # Return null hash on error
        return f"error_{str(e)[:20]}"


def _dhash_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two dHashes.

    Args:
        hash1: Hex string hash
        hash2: Hex string hash

    Returns:
        Number of differing bits (0 = identical, 64 = completely different)
    """
    if not hash1 or not hash2 or hash1.startswith("error") or hash2.startswith("error"):
        return 64  # Max distance for invalid hashes

    try:
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2, strict=False))
    except Exception:
        return 64


def _signal_wcag_contrast(
    png_path: Path, min_ratio_threshold: float = 4.5
) -> RankingSignal:
    """Score WCAG AA contrast (hard floor: 4.5:1).

    Imports contrast_validator locally to avoid circular deps.
    Returns signal with 0 (fail) or 1 (pass).
    """
    try:
        # Import locally to avoid circular dependency
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from contrast_validator import ContrastValidator

        validator = ContrastValidator(png_path.parent.parent)
        result = validator.measure_contrast(png_path)

        if result.get("error"):
            reason = f"Measurement error: {result['error']}"
            value = 0.0
        elif result.get("decorative"):
            reason = "Decorative asset (exempt)"
            value = 1.0
        else:
            ratio = result.get("contrast_ratio")
            if ratio is None:
                reason = "No foreground detected"
                value = 0.0
            elif ratio >= min_ratio_threshold:
                reason = f"WCAG AA pass ({ratio:.2f}:1 >= 4.5:1)"
                value = 1.0
            else:
                reason = f"WCAG AA fail ({ratio:.2f}:1 < 4.5:1)"
                value = 0.0
    except Exception as e:
        reason = f"Contrast check error: {str(e)[:50]}"
        value = 0.0

    return RankingSignal(
        name="wcag_contrast",
        weight=0.40,  # 40% weight: hard requirement
        value=value,
        reason=reason,
    )


def _signal_layout_status(layout_warnings: list[dict[str, Any]]) -> RankingSignal:
    """Score layout warnings (penalize fail > warn > pass).

    Args:
        layout_warnings: List of layout warning dicts from render metadata

    Returns:
        Signal with score 0 (fail) / 0.5 (warn) / 1.0 (pass)
    """
    from eikon_core.layout import aggregate_layout_status

    status = aggregate_layout_status(layout_warnings)

    if status == "fail":
        value = 0.0
        reason = f"Layout fail: {len(layout_warnings)} warning(s)"
    elif status == "warn":
        value = 0.5
        reason = f"Layout warn: {len(layout_warnings)} warning(s) (non-critical)"
    else:
        value = 1.0
        reason = "Layout pass"

    return RankingSignal(
        name="layout_status",
        weight=0.25,  # 25% weight: structural integrity
        value=value,
        reason=reason,
    )


def _signal_perceptual_diversity(
    png_path: Path, all_hashes: dict[str, str], min_distance: int = 20
) -> RankingSignal:
    """Score perceptual diversity via dHash distance to nearest neighbor.

    Args:
        png_path: Path to PNG
        all_hashes: Dict mapping png_path -> dhash (pre-computed)
        min_distance: Hamming distance threshold for "distinct" (0-64)

    Returns:
        Signal with score based on min distance to any other variation
    """
    dhash = all_hashes.get(str(png_path), _compute_dhash(png_path))

    # Find minimum distance to any other variation
    min_dist = min_distance  # Default: fully distinct
    for other_path, other_hash in all_hashes.items():
        if other_path == str(png_path):
            continue
        dist = _dhash_distance(dhash, other_hash)
        min_dist = min(min_dist, dist)

    # Score: [0, min_distance] → [0, 1], capped at 1
    # 0 distance → 0.0 (duplicate)
    # min_distance → 1.0 (sufficiently distinct)
    value = min(1.0, max(0.0, min_dist / min_distance))
    reason = f"Min dHash distance: {min_dist}/64 bits (distinct if > {min_distance})"

    return RankingSignal(
        name="perceptual_diversity",
        weight=0.20,  # 20% weight: variety in the top-N
        value=value,
        reason=reason,
    )


def _signal_foreground_balance(png_path: Path) -> RankingSignal:
    """Score balanced foreground coverage (aesthetic heuristic).

    Measures what fraction of the canvas is occupied by non-background pixels.
    Prefers moderate coverage (30-70%) over sparse or saturated.

    Args:
        png_path: Path to PNG

    Returns:
        Signal favoring balanced composition
    """
    try:
        img = Image.open(png_path)
        if img.mode == "RGBA":
            # Use alpha channel as proxy for content
            alpha = np.array(img.split()[3])
            fg_pixels = np.sum(alpha > 128)
            total_pixels = alpha.size
        else:
            img_rgb = img.convert("RGB")
            img_array = np.array(img_rgb)
            # Simple heuristic: compare center pixels to edge pixels
            h, w = img_array.shape[:2]
            center = img_array[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
            edges = np.concatenate(
                [
                    img_array[: h // 4, :],
                    img_array[3 * h // 4 :, :],
                    img_array[:, : w // 4],
                    img_array[:, 3 * w // 4 :],
                ]
            )

            # Count pixels that differ substantially
            center_gray = np.mean(center, axis=2)
            edges_gray = np.mean(edges, axis=2)
            center_var = np.std(center_gray)
            edges_var = np.std(edges_gray)

            # Prefer when center has content (higher variance)
            fg_ratio = min(1.0, center_var / max(edges_var, 1.0))
            value = min(1.0, fg_ratio * 1.3)  # Slight boost for balanced layouts

            reason = f"Center-to-edge contrast: {fg_ratio:.2f}"
            return RankingSignal(
                name="foreground_balance",
                weight=0.15,  # 15% weight: aesthetic polish
                value=value,
                reason=reason,
            )

        # For RGBA with alpha channel
        fg_ratio = fg_pixels / total_pixels if total_pixels > 0 else 0.0
        # Prefer 30-70% coverage
        ideal_ratio = 0.5
        distance_from_ideal = abs(fg_ratio - ideal_ratio) / ideal_ratio
        value = max(0.0, 1.0 - distance_from_ideal)

        reason = f"Foreground coverage: {fg_ratio:.1%} (prefer ~50%)"
        return RankingSignal(
            name="foreground_balance",
            weight=0.15,  # 15% weight
            value=value,
            reason=reason,
        )

    except Exception as e:
        reason = f"Foreground analysis error: {str(e)[:40]}"
        return RankingSignal(
            name="foreground_balance",
            weight=0.15,
            value=0.5,  # Neutral on error
            reason=reason,
        )


def rank(
    variations: list[dict[str, Any]],
    png_dir: Path,
    top_n: int = 8,
    dedup_distance_threshold: int = 20,
) -> list[VariationScore]:
    """Rank and deduplicate variations.

    Args:
        variations: List of variation dicts with idx, seed, params, marca, asset_type
        png_dir: Directory containing PNG files
        top_n: Number of top variations to return
        dedup_distance_threshold: dHash distance threshold for "near-identical" (0-64)

    Returns:
        Sorted list of top-N VariationScore objects (highest score first)
    """
    if not variations:
        return []

    # Precompute all dHashes for diversity scoring
    png_hashes: dict[str, str] = {}
    for var in variations:
        png_name = f"combo_{var.get('idx', 0):03d}.png"
        png_path = png_dir / png_name
        if png_path.exists():
            png_hashes[str(png_path)] = _compute_dhash(png_path)

    # Score each variation
    scores: list[VariationScore] = []
    for var in variations:
        idx = var.get("idx", 0)
        png_name = f"combo_{idx:03d}.png"
        png_path = png_dir / png_name

        if not png_path.exists():
            continue

        # Collect signals
        signals = [
            _signal_wcag_contrast(png_path),
            _signal_layout_status(var.get("layout_warnings", [])),
            _signal_perceptual_diversity(png_path, png_hashes, dedup_distance_threshold),
            _signal_foreground_balance(png_path),
        ]

        # Weighted average
        total_weight = sum(s.weight for s in signals)
        weighted_sum = sum(s.value * s.weight for s in signals)
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        dhash = png_hashes.get(str(png_path), "")

        score_obj = VariationScore(
            idx=idx,
            seed=var.get("seed", 0),
            params=var.get("params", {}),
            marca=var.get("marca", ""),
            asset_type=var.get("asset_type", ""),
            png_path=png_path,
            final_score=final_score,
            signals=tuple(signals),
            dhash=dhash,
        )
        scores.append(score_obj)

    # Sort by score (descending)
    scores.sort(key=lambda s: (-s.final_score, s.idx))

    # Dedup: if top scores have very similar dHashes, keep only the best
    deduplicated: list[VariationScore] = []
    for score in scores:
        # Check if too similar to any already-selected score
        is_duplicate = False
        for selected in deduplicated:
            dist = _dhash_distance(score.dhash, selected.dhash)
            if dist < dedup_distance_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            deduplicated.append(score)

        if len(deduplicated) >= top_n:
            break

    return deduplicated


__all__ = [
    "RankingSignal",
    "VariationScore",
    "rank",
]
