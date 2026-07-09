#!/usr/bin/env python3
"""Validación del pack de espirales: sintaxis SVG, determinismo, colores."""

import sys
from pathlib import Path

# Agregar eikon_core al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core.isotype import IsotypeParams
from eikon_core.isotypes.pack_espirales import PACK


def _run_checks(spiral_id: str, svg1: str, svg2: str, svg3: str, params_base: IsotypeParams, results: dict) -> dict:
    """Ejecuta checks de validación individuales."""
    checks = {}

    # ✓ SVG válido
    checks["svg_valid"] = svg1.startswith("<svg") and svg1.endswith("</svg>")
    if not checks["svg_valid"]:
        results["errors"].append(f"{spiral_id}: SVG structure invalid")

    # ✓ SVG no vacío
    checks["svg_nonempty"] = len(svg1) > 100
    if not checks["svg_nonempty"]:
        results["errors"].append(f"{spiral_id}: SVG too short ({len(svg1)} bytes)")

    # ✓ Determinismo
    checks["deterministic"] = svg1 == svg2
    if not checks["deterministic"]:
        results["errors"].append(f"{spiral_id}: SVG not deterministic")

    # ✓ Variabilidad
    checks["varied"] = svg1 != svg3
    if not checks["varied"]:
        results["errors"].append(f"{spiral_id}: SVG identical for different seeds")

    # ✓ Colores presentes
    checks["colors_present"] = (
        params_base.primary_color in svg1 and params_base.accent_color in svg1
    )
    if not checks["colors_present"]:
        results["errors"].append(f"{spiral_id}: Missing brand colors")

    # ✓ ViewBox correcto
    viewbox_str = f'viewBox="0 0 {params_base.size} {params_base.size}"'
    checks["viewbox_correct"] = viewbox_str in svg1
    if not checks["viewbox_correct"]:
        results["errors"].append(f"{spiral_id}: ViewBox incorrect")

    return checks


def validate_pack():
    """Valida que cada generador de espiral sea válido."""

    # Parámetros base para prueba
    params_base = IsotypeParams(
        seed=7,
        style="abstract",
        brand_initials="A",
        brand_symbol="◆",
        primary_color="#2FA89A",
        accent_color="#E0A85E",
        bg_color="#101418",
        size=100,
    )

    print("Validando pack de espirales...")
    print(f"Total de generadores: {len(PACK)}")
    print()

    results = {
        "total": len(PACK),
        "valid": 0,
        "errors": [],
        "determinism_checks": {},
    }

    for spiral_id, gen_func in PACK.items():
        print(f"Testing: {spiral_id}... ", end="", flush=True)

        try:
            # Generar SVGs
            svg1 = gen_func(params_base)
            svg2 = gen_func(params_base)
            params_diff = params_base.__class__(
                seed=42,
                style=params_base.style,
                brand_initials=params_base.brand_initials,
                brand_symbol=params_base.brand_symbol,
                primary_color=params_base.primary_color,
                accent_color=params_base.accent_color,
                bg_color=params_base.bg_color,
                size=params_base.size,
            )
            svg3 = gen_func(params_diff)

            # Ejecutar checks
            checks = _run_checks(spiral_id, svg1, svg2, svg3, params_base, results)
            results["determinism_checks"][spiral_id] = checks

            # Reportar resultado
            if all(checks.values()):
                results["valid"] += 1
                print("✓ OK")
            else:
                print("✗ FAIL")
                for check_name, passed in checks.items():
                    if not passed:
                        print(f"  - {check_name}: FAILED")

        except Exception as e:
            results["errors"].append(f"{spiral_id}: {type(e).__name__}: {e}")
            print(f"✗ ERROR: {e}")

    # Resumen
    print()
    print("=" * 60)
    print(f"RESUMEN: {results['valid']}/{results['total']} generadores válidos")

    if results["errors"]:
        print()
        print("ERRORES ENCONTRADOS:")
        for error in results["errors"]:
            print(f"  • {error}")
    else:
        print("✓ Todos los generadores pasaron validación")

    print()

    # Lista de IDs implementados
    print("IDs Implementados:")
    for spiral_id in sorted(PACK.keys()):
        status = "✓" if results["determinism_checks"].get(spiral_id, {}).get("svg_valid") else "✗"
        print(f"  {status} {spiral_id}")

    return results["valid"] == results["total"]


if __name__ == "__main__":
    success = validate_pack()
    sys.exit(0 if success else 1)
