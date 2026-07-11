"""Combinatorial parameter engine for Eikon rendering.

Provides axes loading, validation, and combination planning for
deterministic, reproducible multi-axis logo variations.

Core concepts:
- Axes: named dimensions of variation (palette_scheme, typography, etc.)
- Combinations: specific parameter choices across axes
- Determinism: deterministic_seed ensures re-renders are pixel-identical
"""

from __future__ import annotations

from .axes import AxesConfig, load_axes_config, validate_axes_config
from .planner import CombinationPlan, CombinationSpec, plan_combinations, split_spec_by_asset_type

__all__ = [
    "AxesConfig",
    "CombinationPlan",
    "CombinationSpec",
    "load_axes_config",
    "plan_combinations",
    "split_spec_by_asset_type",
    "validate_axes_config",
]
