"""Combination planning and expansion for Eikon multi-axis rendering."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eikon_core.taxonomy import get_category_for_asset_type

# Add parent eikon directory to path for root-level module access
_EIKON_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_EIKON_DIR))

import variations  # noqa: E402


@dataclass(frozen=True)
class Combination:
    """A single combination of axis values."""

    idx: int
    seed: int
    params: dict[str, str]
    marca: str
    asset_type: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "idx": self.idx,
            "seed": self.seed,
            "params": dict(self.params),
            "marca": self.marca,
            "asset_type": self.asset_type,
        }


@dataclass(frozen=True)
class CombinationSpec:
    """Specification for combination generation."""

    brand: str
    asset_types: list[str] = field(default_factory=list)
    fixed: dict[str, str] = field(default_factory=dict)
    permuted: list[str] = field(default_factory=list)
    count: int = 1
    seed_salt: str = ""
    content: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate the spec."""
        if not self.brand:
            raise ValueError("brand is required")
        if self.count < 1:
            raise ValueError("count must be >= 1")


@dataclass(frozen=True)
class CombinationPlan:
    """A plan of multiple combinations."""

    spec: CombinationSpec
    combinations: tuple[Combination, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.combinations)

    def __iter__(self) -> Any:
        return iter(self.combinations)

    def __getitem__(self, idx: int) -> Combination:
        return self.combinations[idx]

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "spec": {
                "brand": self.spec.brand,
                "asset_types": self.spec.asset_types,
                "fixed": dict(self.spec.fixed),
                "permuted": self.spec.permuted,
                "count": self.spec.count,
            },
            "combinations": [c.as_dict() for c in self.combinations],
        }


def split_spec_by_asset_type(
    spec: CombinationSpec,
    *,
    default_asset_type: str = "logo",
) -> tuple[CombinationSpec, ...]:
    """Split one batch spec into one CombinationSpec per asset type.

    Counts are distributed evenly across requested asset types. If the requested
    count is smaller than the number of asset types, each type still receives
    one combination so every requested format is generated.
    """
    spec.validate()
    asset_types = list(spec.asset_types) or [default_asset_type]
    base_count = spec.count // len(asset_types)
    remainder = spec.count % len(asset_types)

    specs: list[CombinationSpec] = []
    for idx, asset_type in enumerate(asset_types):
        count = base_count + (1 if idx < remainder else 0)
        specs.append(
            CombinationSpec(
                brand=spec.brand,
                asset_types=[asset_type],
                fixed=dict(spec.fixed),
                permuted=list(spec.permuted),
                count=max(1, count),
                seed_salt=spec.seed_salt,
                content=dict(spec.content),
            )
        )
    return tuple(specs)


def _dedup_preserve_order(items: list[str]) -> list[str]:
    """Elimina duplicados preservando el orden de aparición."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _cartesian_product(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    """Genera el producto cartesiano de las opciones de cada eje.

    Las opciones de cada eje se deduplican preservando orden, de modo que el
    resultado NUNCA contiene param-sets repetidos. El orden de los ejes es
    determinista (nombres ordenados alfabéticamente).

    Args:
        axes: {axis_name: [option1, option2, ...]}

    Returns:
        Lista de dicts, cada uno un param-set distinto.
    """
    if not axes:
        return [{}]

    axis_names = sorted(axes.keys())
    combos: list[dict[str, str]] = [{}]

    for axis_name in axis_names:
        options = _dedup_preserve_order(axes[axis_name])
        if not options:
            # Un eje sin opciones no aporta variación; se omite.
            continue
        new_combos: list[dict[str, str]] = []
        for combo in combos:
            for option in options:
                new_combo = dict(combo)
                new_combo[axis_name] = option
                new_combos.append(new_combo)
        combos = new_combos

    return combos


def plan_combinations(
    spec: CombinationSpec,
    axes_config: dict[str, list[str]],
) -> CombinationPlan:
    """Generate a combination plan.

    Args:
        spec: CombinationSpec with brand, fixed, permuted, count
        axes_config: {axis_name: [option1, option2, ...]}

    Returns:
        CombinationPlan with deterministic combinations
    """
    spec.validate()

    # Determine which axes to permute
    permuted_axes: dict[str, list[str]] = {}
    for axis_name in spec.permuted:
        if axis_name in axes_config:
            permuted_axes[axis_name] = axes_config[axis_name]

    # Generate all DISTINCT combinations from permuted axes (cartesian product).
    all_combos = _cartesian_product(permuted_axes)

    # Defensa adicional: deduplicar param-sets ya fusionados con `fixed`. Si un eje
    # permutado coincide con una clave fija, el valor permutado gana, y aun así cada
    # param-set permanece distinto por construcción del producto cartesiano.
    distinct: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for combo in all_combos:
        merged = dict(spec.fixed)
        merged.update(combo)
        key = tuple(sorted(merged.items()))
        if key not in seen:
            seen.add(key)
            distinct.append(merged)

    n_distinct = len(distinct)
    if spec.count > n_distinct:
        # No es posible producir más param-sets DISTINTOS que el universo cartesiano.
        # Antes esto se "ciclaba" con i % n, generando duplicados (p.ej. combos 9 y 11
        # idénticos). Ahora fallamos explícito en lugar de emitir duplicados.
        raise ValueError(
            f"Se pidieron count={spec.count} combinaciones distintas pero solo existen "
            f"{n_distinct} param-sets únicos para los ejes permutados {spec.permuted}. "
            f"Reduce count a <= {n_distinct} o agrega más ejes/opciones."
        )

    # Tomar los primeros `count` param-sets distintos en orden determinista.
    selected_combos = distinct[: spec.count]

    # Build combinations with deterministic seeds
    combinations: list[Combination] = []
    for i, params in enumerate(selected_combos):
        # Generate deterministic seed
        param_str = "|".join(f"{k}={v}" for k, v in sorted(params.items()))
        category = (
            get_category_for_asset_type(spec.asset_types[0])
            if spec.asset_types
            else "logos"
        ) or "logos"
        seed = variations.deterministic_seed(
            marca=spec.brand,
            category=category,
            type="combination",
            variant=param_str,
            idx=i,
            salt=spec.seed_salt,
        )

        combination = Combination(
            idx=i,
            seed=seed,
            params=params,
            marca=spec.brand,
            asset_type=spec.asset_types[0] if spec.asset_types else "logo",
        )
        combinations.append(combination)

    return CombinationPlan(spec=spec, combinations=tuple(combinations))
