"""Tests del planner combinatorio: distinción de param-sets, dedup y determinismo.

Regresión cubierta: antes el planner ciclaba con `i % n` y emitía combinaciones
DUPLICADAS cuando count > universo cartesiano (p.ej. combos 9 y 11 idénticos).
Ahora produce solo param-sets distintos o falla explícito.
"""

from __future__ import annotations

import pytest

from eikon_core.combinatorial.planner import CombinationSpec, plan_combinations

AXES = {
    "palette_scheme": ["brand", "mono", "light"],
    "background_treatment": ["solid", "gradient"],
    "corner_shape": ["sharp", "rounded"],
}


def _param_keys(plan) -> list[tuple]:
    return [tuple(sorted(c.params.items())) for c in plan]


def test_plan_produces_distinct_param_sets() -> None:
    """12 = 3x2x2 combinaciones, todas con param-sets únicos."""
    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        asset_types=["logo_symbol_color"],
        permuted=["palette_scheme", "background_treatment", "corner_shape"],
        count=12,
        seed_salt="t",
    )
    plan = plan_combinations(spec, AXES)
    keys = _param_keys(plan)
    assert len(plan) == 12
    assert len(set(keys)) == 12, "deben ser 12 param-sets DISTINTOS (sin duplicados)"


def test_plan_count_less_than_universe_takes_prefix() -> None:
    """Pedir menos que el universo devuelve los primeros N distintos, deterministas."""
    spec = CombinationSpec(brand="b", permuted=list(AXES), count=5, seed_salt="t")
    plan_a = plan_combinations(spec, AXES)
    plan_b = plan_combinations(spec, AXES)
    assert len(plan_a) == 5
    assert len(set(_param_keys(plan_a))) == 5
    # Determinismo: mismas params y mismas seeds en re-ejecución.
    assert _param_keys(plan_a) == _param_keys(plan_b)
    assert [c.seed for c in plan_a] == [c.seed for c in plan_b]


def test_plan_count_over_universe_raises() -> None:
    """count > universo cartesiano falla en vez de duplicar (la vieja bug)."""
    spec = CombinationSpec(brand="b", permuted=list(AXES), count=13, seed_salt="t")
    with pytest.raises(ValueError, match="distintas"):
        plan_combinations(spec, AXES)


def test_plan_dedups_duplicate_options() -> None:
    """Opciones duplicadas dentro de un eje no generan param-sets repetidos."""
    axes = {"palette_scheme": ["brand", "brand", "mono"], "corner_shape": ["sharp", "sharp"]}
    spec = CombinationSpec(brand="b", permuted=list(axes), count=2, seed_salt="t")
    plan = plan_combinations(spec, axes)
    # Universo real tras dedup: {brand,mono} x {sharp} = 2 distintos.
    assert len(plan) == 2
    assert len(set(_param_keys(plan))) == 2


def test_plan_fixed_params_merged() -> None:
    """Los params fijos se fusionan en cada combinación sin romper la distinción."""
    spec = CombinationSpec(
        brand="b",
        fixed={"density_scale": "compact"},
        permuted=["corner_shape"],
        count=2,
        seed_salt="t",
    )
    plan = plan_combinations(spec, AXES)
    assert len(plan) == 2
    assert all(c.params["density_scale"] == "compact" for c in plan)
    assert {c.params["corner_shape"] for c in plan} == {"sharp", "rounded"}
