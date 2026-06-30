"""Ranking and deduplication for variation scoring.

Scores variations by (deterministic, no randomness):
1. Placeholder penalty (HARD: isotype_style='none' → 0.0, else 1.0) [35%]
2. Visual richness (complexity/density: penalize 3-dot placeholders) [25%]
3. WCAG AA contrast (floor: 4.5:1 min, baseline requirement) [20%]
4. Layout status/warnings (penalize fail/warn) [15%]
5. Perceptual diversity (dHash to detect near-identical, reward diverse) [5%]

Key fix: 'none' (placeholder 3 dots) is penalized before contrast is measured.
Contrast becomes a floor (must pass AA), not the dominant signal.

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


def _signal_wcag_contrast(png_path: Path, min_ratio_threshold: float = 4.5) -> RankingSignal:
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
        weight=0.20,  # 20% weight: baseline requirement (floor, not dominant)
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
        weight=0.15,  # 15% weight: structural integrity
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
        weight=0.05,  # 5% weight: variety in the top-N (minor influence)
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


def _signal_placeholder_penalty(params: dict[str, str]) -> RankingSignal:
    """Penalize placeholder isotopes (isotype_style='none') heavily.

    Placeholder 'none' (3 black dots) is NOT a real brand mark. It should NEVER
    rank above lettermark/geometric/abstract/enclosure.

    Args:
        params: Variation params dict with optional 'isotype_style' key

    Returns:
        Signal: 0.0 if isotype_style=='none', 1.0 otherwise
    """
    isotype_style = params.get("isotype_style", "").lower()

    if isotype_style == "none":
        value = 0.0
        reason = "Placeholder (3 dots, not a real mark)"
    else:
        value = 1.0
        reason = f"Real mark style: '{isotype_style}'" if isotype_style else "No isotype (assumed real)"

    return RankingSignal(
        name="placeholder_penalty",
        weight=0.35,  # 35% weight: HARD requirement
        value=value,
        reason=reason,
    )


def _signal_visual_richness(png_path: Path) -> RankingSignal:
    """Score visual complexity/richness of the mark.

    Measures foreground density and edge complexity to reward marks with
    visual structure (geometric patterns, letter forms, etc.) and penalize
    sparse/trivial content (3 dots).

    Uses:
    - Foreground coverage (px/total)
    - Edge complexity (gradient variance across image)

    Args:
        png_path: Path to PNG image

    Returns:
        Signal favoring visually rich, complex marks
    """
    try:
        img = Image.open(png_path)

        # Compute foreground coverage
        if img.mode == "RGBA":
            alpha = np.array(img.split()[3])
            fg_pixels = np.sum(alpha > 128)
            total_pixels = alpha.size
            fg_coverage = float(fg_pixels / total_pixels) if total_pixels > 0 else 0.0
        else:
            img_rgb = img.convert("RGB")
            img_array = np.array(img_rgb)
            # Use color variance as proxy for content
            gray = np.mean(img_array, axis=2)
            fg_coverage = float(np.std(gray) / 255.0)  # Normalized

        # Compute edge complexity: variance of Sobel-like gradients
        # (without scipy.ndimage, compute manually with numpy)
        gray_img = np.array(img.convert("L"))

        h, w = gray_img.shape
        if h > 2 and w > 2:
            # Simple gradient: compare pixels horizontally and vertically
            dx = gray_img[:, :-1].astype(np.float32) - gray_img[:, 1:].astype(np.float32)
            dy = gray_img[:-1, :].astype(np.float32) - gray_img[1:, :].astype(np.float32)
            gradient_magnitude = np.sqrt(dx[:-1, :] ** 2 + dy[:, :-1] ** 2)
            edge_complexity = float(np.std(gradient_magnitude) / 255.0)  # Normalized
        else:
            edge_complexity = 0.0

        # Combine: reward moderate foreground + high edge complexity
        # - Very sparse (fg < 5%) → low score
        # - Moderate (5-40%) with high edges → high score
        # - Saturated (> 80%) → penalize (background missing)
        if fg_coverage < 0.05:
            # Placeholder-like (3 dots)
            value = 0.1 + edge_complexity * 0.2
        elif fg_coverage > 0.80:
            # Too saturated
            value = 0.3 + edge_complexity * 0.2
        else:
            # Good range: reward based on edge complexity
            value = min(1.0, 0.4 + fg_coverage * 0.3 + edge_complexity * 0.3)

        reason = (
            f"Richness: coverage={fg_coverage:.1%}, edge_complexity={edge_complexity:.2f} → {value:.2f}"
        )
        return RankingSignal(
            name="visual_richness",
            weight=0.25,  # 25% weight: structural complexity
            value=value,
            reason=reason,
        )

    except Exception as e:
        reason = f"Visual richness analysis error: {str(e)[:40]}"
        return RankingSignal(
            name="visual_richness",
            weight=0.25,
            value=0.5,  # Neutral on error
            reason=reason,
        )


def _pick_best_or_fallback(
    candidates: list[VariationScore],
    selected: list[VariationScore],
    dedup_distance_threshold: int,
) -> VariationScore:
    """Elige el primer candidato que NO sea perceptual-duplicado de ``selected``
    (preserva el orden best-first de entrada). Si todos lo son, retorna el
    mejor por ``(final_score, -idx)`` para honrar la garantía de variedad."""
    for cand in candidates:
        is_dup = False
        for s in selected:
            if _dhash_distance(cand.dhash, s.dhash) < dedup_distance_threshold:
                is_dup = True
                break
        if not is_dup:
            return cand
    return max(candidates, key=lambda s: (s.final_score, -s.idx))


def _mark_covered(
    score: VariationScore, permuted_axes: dict[str, list[str]]
) -> dict[str, set[str]]:
    """Devuelve el dict ``{axis: set(valores cubiertos)}`` después de añadir
    ``score`` como representante. Una variación puede cubrir múltiples ejes si
    sus ``params`` contienen sus valores."""
    covered: dict[str, set[str]] = {}
    for ax in permuted_axes:
        val = score.params.get(ax)
        if val is not None:
            covered[ax] = {val}
    return covered


def _dedup_preserve_axis_variety(
    scores: list[VariationScore],
    permuted_axes: dict[str, list[str]],
    dedup_distance_threshold: int,
) -> list[VariationScore]:
    """Dedup preservando al menos un representante por valor en cada eje permutado.

    Caso de uso (bug crítico reportado): el usuario pide permutar
    ``palette_scheme ∈ {brand, mono, light, dark}`` con ``count=4``. El isotype
    procedural (``isotype.py``) genera SVG en Python y no ve los cambios de CSS
    vars del template HTML, así que las 4 PNGs resultantes son visualmente
    idénticas. La deduplicación estándar por ``dHash < threshold`` colapsa las
    4 a 1, rompiendo la promesa del usuario.

    Esta función preserva la variedad declarada por el usuario: para cada eje
    en ``permuted_axes`` garantiza al menos una variación por valor declarado,
    incluso si las distancias dHash son < threshold. Si un candidato no es
    perceptual-duplicado de los ya seleccionados, se prefiere; en caso
    contrario se toma el mejor igual para honrar la garantía.

    Estrategia:
      1. Iterar ejes en orden declarado por el usuario.
      2. Para cada eje, iterar valores en orden declarado.
      3. Para cada (eje, valor) aún no cubierto, elegir el mejor score con ese
         valor que NO sea dedup-duplicado; si todos lo son, tomar el mejor de
         todas formas (preserva la promesa).
      4. Cuando una variación se selecciona, marcar TODOS los ejes permutados
         cuyos valores estén en sus ``params`` como cubiertos (una sola
         variación puede cubrir múltiples garantías si sus params intersectan
         varios ejes permutados).

    Args:
        scores: Lista de VariationScore ya ordenada por ``(-final_score, idx)``.
        permuted_axes: Mapeo ``axis_name -> [valores pedidos por el usuario]``.
            El orden de inserción se respeta al iterar.
        dedup_distance_threshold: Umbral perceptual para considerar "demasiado
            similar" dos variaciones.

    Returns:
        Lista deduplicada con al menos un representante por valor declarado
        en cada eje permutado presente en los params de las variaciones.
    """
    if not scores or not permuted_axes:
        return list(scores)

    selected: list[VariationScore] = []
    covered: dict[str, set[str]] = {axis: set() for axis in permuted_axes}

    for axis_name, axis_values in permuted_axes.items():
        for axis_val in axis_values:
            if axis_val in covered[axis_name]:
                continue

            candidates = [s for s in scores if s.params.get(axis_name) == axis_val]
            if not candidates:
                continue

            picked = _pick_best_or_fallback(candidates, selected, dedup_distance_threshold)
            selected.append(picked)
            # Una variación puede cubrir varios ejes a la vez → evita duplicados
            for ax, vals in _mark_covered(picked, permuted_axes).items():
                covered[ax].update(vals)

    return selected


def rank(
    variations: list[dict[str, Any]],
    png_dir: Path,
    top_n: int = 8,
    dedup_distance_threshold: int = 20,
    permuted_axes: dict[str, list[str]] | None = None,
) -> list[VariationScore]:
    """Rank and deduplicate variations.

    Args:
        variations: List of variation dicts with idx, seed, params, marca, asset_type
        png_dir: Directory containing PNG files
        top_n: Number of top variations to return
        dedup_distance_threshold: dHash distance threshold for "near-identical" (0-64)
        permuted_axes: Optional dict ``{axis_name: [valores pedidos]}``. Si las
            variaciones efectivamente llevan alguno de esos ejes en ``params``,
            la deduplicación garantiza al menos un representante por valor
            declarado (resuelve el caso de ``palette_scheme`` cuando el isotype
            procedural no refleja cambios de CSS). Si ``None`` o si ningún eje
            permutado aparece en las variaciones, se aplica el dedup estándar.

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

        # Collect signals (new: placeholder_penalty and visual_richness first)
        signals = [
            _signal_placeholder_penalty(var.get("params", {})),
            _signal_visual_richness(png_path),
            _signal_wcag_contrast(png_path),
            _signal_layout_status(var.get("layout_warnings", [])),
            _signal_perceptual_diversity(png_path, png_hashes, dedup_distance_threshold),
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

    # Decidir ruta de dedup según permuted_axes
    permuted = permuted_axes or {}
    has_relevant_axis = any(axis in s.params for s in scores for axis in permuted)

    if permuted and has_relevant_axis:
        deduplicated = _dedup_preserve_axis_variety(scores, permuted, dedup_distance_threshold)
    else:
        # Dedup estándar por dHash (comportamiento legacy)
        deduplicated = []
        for score in scores:
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

    # Re-sort deduplicated results by score (highest first)
    # This ensures that even after axis-variety dedup, the final order is by quality
    deduplicated.sort(key=lambda s: (-s.final_score, s.idx))
    return deduplicated[:top_n]


__all__ = [
    "RankingSignal",
    "VariationScore",
    "rank",
]
