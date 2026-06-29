#!/usr/bin/env python3
"""
Tests sintéticos para variations.py (Eikon Phase 6 scaffolding).

Ejecución:
    cd /workspace/Pinakotheke/eikon
    python3 tests/test_variations.py

Stdlib-only. No requiere Playwright / numpy / Pillow. Cubre:
  1.  deterministic_seed: estabilidad, rango uint64, distinción entre campos.
  2.  VariationRequest: construcción mínima, as_dict, defaults.
  3.  validate_request: campos obligatorios, category inválida, count fuera
      de rango, axis con 0 opciones, strategy inválida, bool rechazado.
  4.  expand_variations: count respetado, determinismo, estrategias,
      axes vacíos, count = 1 / 200 (bordes).
  5.  Variation: inmutabilidad, hashability, params_dict, as_dict.
  6.  VariationPlan: len / iter / getitem, to_dict, to_jsonl, inmutabilidad.
  7.  Aislamiento entre marcas y entre salts.
  8.  Caso real: 50 banners para prizma-iris con axes color+layout+copy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_EIKON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EIKON_DIR))

import variations  # noqa: E402

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        print(f"  ✗ {name}  — {detail}" if detail else f"  ✗ {name}")


def section(title: str) -> None:
    print(f"\n{'─' * 50}\n  {title}\n{'─' * 50}")


# =============================================================================
# 1. deterministic_seed
# =============================================================================
def test_deterministic_seed_stable() -> None:
    section("1. deterministic_seed: estabilidad y rango")
    s1 = variations.deterministic_seed(
        marca="prizma-iris", category="banners", type="ad_leaderboard",
        variant="color=red|layout=top", idx=3, salt="x",
    )
    s2 = variations.deterministic_seed(
        marca="prizma-iris", category="banners", type="ad_leaderboard",
        variant="color=red|layout=top", idx=3, salt="x",
    )
    check("mismos inputs → mismo seed", s1 == s2, f"got {s1} vs {s2}")
    check("seed es int", isinstance(s1, int), f"type={type(s1)}")
    check("seed cabe en uint64 (>= 0 y < 2**64)",
          0 <= s1 < 2**64, f"seed={s1}")


def test_deterministic_seed_distinct() -> None:
    section("2. deterministic_seed: distinción entre campos")
    base = dict(
        marca="prizma-iris", category="banners", type="ad_leaderboard",
        variant="v1", idx=0, salt="",
    )
    s_base = variations.deterministic_seed(**base)
    for changed in ("marca", "category", "type", "variant", "idx", "salt"):
        kw = dict(base)
        if changed == "idx":
            kw["idx"] = 1
        elif changed == "salt":
            kw["salt"] = "otro"
        else:
            kw[changed] = base[changed] + "_changed"
        s_other = variations.deterministic_seed(**kw)
        check(f"cambiar {changed!r} → seed distinto",
              s_other != s_base, f"both={s_base}")


# =============================================================================
# 2. VariationRequest
# =============================================================================
def test_variation_request_basic() -> None:
    section("3. VariationRequest: construcción mínima y defaults")
    req = variations.VariationRequest(
        marca="pinakotheke-kosmos", category="logos",
        type="lockup_horizontal", count=10,
    )
    check("se construye con args mínimos", req is not None)
    check("base_variants default es dict vacío", req.base_variants == {})
    check("strategy default es 'seeded'", req.strategy == "seeded")
    check("max_count default es 200", req.max_count == 200)
    check("locale default es 'es'", req.locale == "es")
    check("palette_override default es None", req.palette_override is None)

    d = req.as_dict()
    check("as_dict() tiene claves esperadas",
          {"marca", "category", "type", "count", "base_variants",
           "strategy"}.issubset(d.keys()))


def test_variation_request_frozen() -> None:
    section("4. VariationRequest: frozen (no reasignable)")
    req = variations.VariationRequest(
        marca="prizma-iris", category="banners",
        type="ad_leaderboard", count=5,
    )
    try:
        req.count = 999  # type: ignore[misc]
        check("count es frozen (no reasignable)", False, "asignó count")
    except Exception:
        check("count es frozen (no reasignable)", True)


# =============================================================================
# 3. validate_request
# =============================================================================
def test_validate_request_ok() -> None:
    section("5. validate_request: request válida pasa")
    req = variations.VariationRequest(
        marca="prizma-iris", category="banners",
        type="ad_leaderboard", count=10,
    )
    try:
        variations.validate_request(req)
        check("request válida → no raise", True)
    except ValueError as e:
        check("request válida → no raise", False, str(e))


def test_validate_request_errors() -> None:
    section("6. validate_request: errores claros")
    base_kw = dict(marca="prizma-iris", category="banners",
                   type="ad_leaderboard", count=10)

    cases: list[tuple[str, dict, str]] = [
        ("marca vacía", {"marca": ""}, "marca"),
        ("category inválida", {"category": "xxx"}, "category"),
        ("type vacío", {"type": ""}, "type"),
        ("count=0", {"count": 0}, "count"),
        ("count negativo", {"count": -5}, "count"),
        ("count > max_count", {"count": 9999, "max_count": 100}, "max_count"),
        ("strategy inválida", {"strategy": "magic"}, "strategy"),
        ("axis con 0 opciones",
         {"base_variants": {"color": ()}}, "axis"),
        ("axis con opción no-str",
         {"base_variants": {"color": ("a", 1)}}, "axis"),
    ]
    for label, override, needle in cases:
        kw = {**base_kw, **override}
        try:
            variations.validate_request(variations.VariationRequest(**kw))
            check(f"{label} → raise", False, "no raise")
        except ValueError as e:
            check(f"{label} → raise", needle in str(e), f"msg={e!s}")

    # bool como count (bool es subclase de int → debe rechazarse explícitamente)
    try:
        variations.validate_request(variations.VariationRequest(
            **{**base_kw, "count": True},  # type: ignore[arg-type]
        ))
        check("count=True (bool) → raise", False, "no raise")
    except ValueError as e:
        check("count=True (bool) → raise", "int" in str(e), f"msg={e!s}")


# =============================================================================
# 4. expand_variations: contrato básico
# =============================================================================
def test_expand_count_respected() -> None:
    section("7. expand_variations: count respetado (bordes 1 / 50 / 200)")
    for n in (1, 50, 200):
        plan = variations.expand_variations(
            count=n, category="banners", type="ad_leaderboard",
            base_variants={
                "color": ("red", "blue"),
                "layout": ("top", "bottom"),
            },
        )
        check(f"count={n} → len(plan)={n}", len(plan) == n, f"got {len(plan)}")
        check(f"count={n} → idx cubren 0..{n - 1}",
              [v.idx for v in plan] == list(range(n)))


def test_expand_deterministic() -> None:
    section("8. expand_variations: determinismo (mismos args → mismo plan)")
    kw = dict(
        count=20, category="logos", type="lockup_horizontal",
        base_variants={"color": ("v1_color", "v2_mono", "v3_inverse")},
        marca="pinakotheke-kosmos", seed_salt="phase6",
    )
    p1 = variations.expand_variations(**kw)
    p2 = variations.expand_variations(**kw)
    seeds1 = [v.seed for v in p1]
    seeds2 = [v.seed for v in p2]
    check("mismos args → mismos seeds", seeds1 == seeds2)
    check("mismos args → mismos variants",
          [v.variant_str for v in p1] == [v.variant_str for v in p2])
    # El plan completo es dataclass-eq por contenido:
    check("plans son dataclass-equal", p1 == p2)


def test_expand_seeds_unique_in_plan() -> None:
    section("9. expand_variations: seeds únicos dentro del plan")
    plan = variations.expand_variations(
        count=50, category="banners", type="ad_leaderboard",
        base_variants={
            "color": ("v1", "v2", "v3"),
            "layout": ("a", "b", "c", "d"),
        },
        marca="prizma-iris",
    )
    seeds = [v.seed for v in plan]
    check("50 seeds, todos distintos",
          len(set(seeds)) == 50, f"unique={len(set(seeds))}/50")


def test_expand_seeded_strategy_diversity() -> None:
    section("10. expand_variations: estrategia 'seeded' da diversidad")
    plan = variations.expand_variations(
        count=5, category="logos", type="wordmark",
        base_variants={
            "color": ("v1", "v2", "v3"),
            "layout": ("top", "bottom"),
        },
        marca="prizma-iris", strategy="seeded",
    )
    variants = [v.variant_str for v in plan]
    check("5 variations todas distintas (cartesiano 3×2=6 >= 5)",
          len(set(variants)) == 5, f"got {variants}")


def test_expand_round_robin_strategy() -> None:
    section("11. expand_variations: estrategia 'round_robin' cicla")
    plan = variations.expand_variations(
        count=6, category="logos", type="wordmark",
        base_variants={"color": ("v1", "v2", "v3")},
        marca="prizma-iris", strategy="round_robin",
    )
    colors = [v.params_dict()["color"] for v in plan]
    check("round_robin cicla: [v1,v2,v3,v1,v2,v3]",
          colors == ["v1", "v2", "v3", "v1", "v2", "v3"], f"got {colors}")


def test_expand_empty_axes() -> None:
    section("12. expand_variations: axes vacíos / None")
    plan = variations.expand_variations(
        count=5, category="logos", type="wordmark",
        base_variants=None, marca="prizma-iris",
    )
    check("5 variations con axes vacíos", len(plan) == 5)
    check("todas las variations tienen params={}",
          all(v.params_dict() == {} for v in plan))
    seeds = [v.seed for v in plan]
    check("seeds siguen siendo distintos (por idx)",
          len(set(seeds)) == 5, f"unique={len(set(seeds))}/5")


def test_expand_single_axis_single_option() -> None:
    section("13. expand_variations: eje con 1 sola opción")
    plan = variations.expand_variations(
        count=4, category="logos", type="wordmark",
        base_variants={"color": ("only",)},
        marca="prizma-iris",
    )
    check("4 variations con 1 opción", len(plan) == 4)
    check("todas params={color: only}",
          all(v.params_dict() == {"color": "only"} for v in plan))
    check("idx son 0..3",
          [v.idx for v in plan] == [0, 1, 2, 3])


# =============================================================================
# 5. Variation
# =============================================================================
def test_variation_inmutable_and_hashable() -> None:
    section("14. Variation: inmutable + hashable")
    plan = variations.expand_variations(
        count=3, category="logos", type="wordmark",
        base_variants={"color": ("v1", "v2")},
    )
    v = plan[0]
    try:
        v.idx = 999  # type: ignore[misc]
        check("Variation es frozen", False, "asignó idx")
    except Exception:
        check("Variation es frozen", True)
    try:
        h = hash(v)
        check("Variation es hashable", isinstance(h, int))
    except Exception as e:
        check("Variation es hashable", False, str(e))

    # Dos Variations con mismos campos → equal y mismo hash.
    req = variations.VariationRequest(
        marca="x", category="logos", type="wordmark", count=1,
    )
    p1 = variations.plan_from_request(req)
    p2 = variations.plan_from_request(req)
    check("Variations iguales → equal", p1[0] == p2[0])
    check("Variations iguales → mismo hash", hash(p1[0]) == hash(p2[0]))


# =============================================================================
# 6. VariationPlan
# =============================================================================
def test_plan_protocol() -> None:
    section("15. VariationPlan: len / iter / getitem (incluye índice negativo)")
    plan = variations.expand_variations(
        count=7, category="cards", type="stat_card",
        base_variants={"color": ("a", "b", "c")},
        marca="prizma-iris",
    )
    check("len(plan) == 7", len(plan) == 7)
    check("plan[0] es Variation",
          isinstance(plan[0], variations.Variation))
    check("plan[-1] es Variation (índice negativo)",
          isinstance(plan[-1], variations.Variation))
    check("plan[0].idx == 0", plan[0].idx == 0)
    check("plan[-1].idx == 6", plan[-1].idx == 6)
    check("iter(plan) yields 7 items",
          len([v for v in plan]) == 7)


def test_plan_to_jsonl() -> None:
    section("16. VariationPlan.to_jsonl")
    plan = variations.expand_variations(
        count=3, category="logos", type="wordmark",
        base_variants={"color": ("v1", "v2")},
    )
    s = plan.to_jsonl()
    lines = [ln for ln in s.splitlines() if ln]
    check("3 líneas JSONL", len(lines) == 3, f"got {len(lines)}")
    parsed = [json.loads(ln) for ln in lines]
    check("cada línea parseable a dict",
          all(isinstance(p, dict) for p in parsed))
    check("cada dict tiene 'seed' y 'params'",
          all("seed" in p and "params" in p for p in parsed))
    check("orden de idx es 0,1,2",
          [p["idx"] for p in parsed] == [0, 1, 2])

    # Plan vacío → string vacío
    empty = variations.expand_variations(
        count=1, category="logos", type="wordmark",
        base_variants={"k": ("a",)},
    )
    # Reusamos expand para count=1, no podemos pedir count=0 (validación).
    # Probamos to_jsonl en un plan de 1 elemento:
    check("to_jsonl en plan no-vacío termina con '\\n'",
          s.endswith("\n"))
    check("to_jsonl con 0 variations → ''",
          variations.VariationPlan(
              request=empty.request,
              variations=(),
              strategy_used="seeded",
          ).to_jsonl() == "")


def test_plan_to_dict_serializable() -> None:
    section("17. VariationPlan.to_dict es JSON-serializable")
    plan = variations.expand_variations(
        count=2, category="logos", type="wordmark",
        base_variants={"color": ("v1", "v2")},
        marca="prizma-iris", seed_salt="t1",
    )
    d = plan.to_dict()
    check("top-level tiene 'request' y 'variations'",
          "request" in d and "variations" in d)
    check("request.marca == prizma-iris",
          d["request"]["marca"] == "prizma-iris")
    check("request.strategy == 'seeded'",
          d["request"]["strategy"] == "seeded")
    check("2 variations en dict", len(d["variations"]) == 2)
    j = json.dumps(d, ensure_ascii=False, sort_keys=True)
    check("to_dict() round-trip JSON OK",
          isinstance(j, str) and len(j) > 0)


# =============================================================================
# 7. Aislamiento entre marcas y entre salts
# =============================================================================
def test_separate_marcas_different_plans() -> None:
    section("18. plans distintos para marcas distintas")
    kw = dict(count=10, category="banners", type="ad_leaderboard",
              base_variants={"color": ("a", "b")})
    p1 = variations.expand_variations(marca="prizma-iris", **kw)
    p2 = variations.expand_variations(marca="pinakotheke-kosmos", **kw)
    check("seeds prizma-iris ≠ pinakotheke-kosmos",
          [v.seed for v in p1] != [v.seed for v in p2])
    check("marca persistida en cada Variation",
          all(v.marca == "prizma-iris" for v in p1)
          and all(v.marca == "pinakotheke-kosmos" for v in p2))


def test_separate_salts_different_plans() -> None:
    section("19. seed_salt cambia el plan")
    kw = dict(count=10, category="logos", type="wordmark",
              base_variants={"color": ("a", "b", "c")},
              marca="prizma-iris")
    pA = variations.expand_variations(**kw, seed_salt="saltA")
    pB = variations.expand_variations(**kw, seed_salt="saltB")
    check("seeds saltA ≠ saltB",
          [v.seed for v in pA] != [v.seed for v in pB])


# =============================================================================
# 8. Caso real: 50 banners para prizma-iris
# =============================================================================
def test_real_case_50_banners_prizma_iris() -> None:
    section("20. Caso real: 50 banners prizma-iris (3×3×2 cartesiano)")
    base_kw = dict(
        count=50, category="banners", type="ad_leaderboard",
        base_variants={
            "color": ("v1_color", "v2_mono", "v3_inverse"),
            "layout": ("top", "middle", "bottom"),
            "copy": ("short", "long"),
        },
        marca="prizma-iris", strategy="seeded",
    )
    plan = variations.expand_variations(**base_kw)
    plan2 = variations.expand_variations(**base_kw)

    check("len(plan) == 50", len(plan) == 50)
    check("todas las variations son categoría=banners",
          all(v.category == "banners" for v in plan))
    check("todas son tipo=ad_leaderboard",
          all(v.type == "ad_leaderboard" for v in plan))
    check("todas son marca=prizma-iris",
          all(v.marca == "prizma-iris" for v in plan))
    check("idx cubren 0..49",
          [v.idx for v in plan] == list(range(50)))
    # Cartesiano = 3×3×2 = 18 → no podemos cubrir 18 únicos con 50 (ciclo).
    all_params = set(v.variant_str for v in plan)
    check("variants observados ≤ 18 (cartesiano)",
          len(all_params) <= 18, f"observed {len(all_params)}")
    check("variants observados >= 2 (no degenerado)",
          len(all_params) >= 2, f"observed {len(all_params)}")
    check("seeds son únicos en el plan",
          len({v.seed for v in plan}) == 50)
    check("re-correr produce seeds idénticos",
          [v.seed for v in plan] == [v.seed for v in plan2])
    check("re-correr produce plan dataclass-equal",
          plan == plan2)


# =============================================================================
# 9. Constantes públicas
# =============================================================================
def test_standard_categories_completeness() -> None:
    section("21. STANDARD_CATEGORIES contiene las 5 categorías canónicas")
    expected = {"logos", "cards", "og", "stationery", "banners"}
    check("categorías canónicas presentes",
          expected.issubset(variations.STANDARD_CATEGORIES),
          f"missing: {expected - variations.STANDARD_CATEGORIES}")


def test_module_metadata() -> None:
    section("22. Metadata del módulo")
    check("__version__ es str no-vacío",
          isinstance(variations.__version__, str)
          and len(variations.__version__) > 0)
    check("__all__ contiene símbolos públicos clave",
          {"VariationRequest", "Variation", "VariationPlan",
           "deterministic_seed", "expand_variations",
           "validate_request", "STANDARD_CATEGORIES"}.issubset(
              set(variations.__all__)))


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  EIKON variations.py — Tests de scaffolding (Fase 6)")
    print("=" * 60)
    print(f"  Module: {variations.__version__}")
    print(f"  Python: {sys.version.split()[0]}")

    test_deterministic_seed_stable()
    test_deterministic_seed_distinct()
    test_variation_request_basic()
    test_variation_request_frozen()
    test_validate_request_ok()
    test_validate_request_errors()
    test_expand_count_respected()
    test_expand_deterministic()
    test_expand_seeds_unique_in_plan()
    test_expand_seeded_strategy_diversity()
    test_expand_round_robin_strategy()
    test_expand_empty_axes()
    test_expand_single_axis_single_option()
    test_variation_inmutable_and_hashable()
    test_plan_protocol()
    test_plan_to_jsonl()
    test_plan_to_dict_serializable()
    test_separate_marcas_different_plans()
    test_separate_salts_different_plans()
    test_real_case_50_banners_prizma_iris()
    test_standard_categories_completeness()
    test_module_metadata()

    print(f"\n{'=' * 60}")
    print(f"  Resultado: {PASSED} ✓ / {FAILED} ✗")
    if FAILED == 0:
        print("  ✅ Todos los checks pasaron.")
    else:
        print("  ❌ Hay fallos que requieren atención.")
    print("=" * 60)
    sys.exit(0 if FAILED == 0 else 1)
