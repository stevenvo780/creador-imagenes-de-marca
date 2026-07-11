#!/usr/bin/env python3
"""Validación del pack de emblemas: sintaxis SVG, determinismo, colores de marca."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eikon_core.isotype import IsotypeParams
from eikon_core.isotypes.pack_emblemas import PACK

PARAMS_BASE = IsotypeParams(
    seed=7,
    style="x",
    brand_initials="A",
    brand_symbol="◆",
    primary_color="#2FA89A",
    accent_color="#E0A85E",
    bg_color="#101418",
    size=100,
)

PARAMS_ALT = IsotypeParams(
    seed=42,
    style="x",
    brand_initials="A",
    brand_symbol="◆",
    primary_color="#2FA89A",
    accent_color="#E0A85E",
    bg_color="#101418",
    size=100,
)


def validate_pack() -> bool:
    print(f"Validando pack emblemas — {len(PACK)} generadores\n")
    errors: list[str] = []
    valid = 0

    for eid, fn in PACK.items():
        print(f"  {eid}... ", end="", flush=True)
        try:
            svg1 = fn(PARAMS_BASE)
            svg2 = fn(PARAMS_BASE)
            svg3 = fn(PARAMS_ALT)

            checks = {
                "svg_valid":     svg1.startswith("<svg") and svg1.endswith("</svg>"),
                "non_empty":     len(svg1) > 80,
                "deterministic": svg1 == svg2,
                "seed_varies":   svg1 != svg3,
                "primary_color": PARAMS_BASE.primary_color in svg1,
                "accent_color":  PARAMS_BASE.accent_color in svg1,
                "viewbox":       'viewBox="0 0 100 100"' in svg1,
            }
            if all(checks.values()):
                valid += 1
                print("OK")
            else:
                failed = [k for k, v in checks.items() if not v]
                print(f"FAIL {failed}")
                errors.append(f"{eid}: {failed}")
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors.append(f"{eid}: {type(exc).__name__}: {exc}")

    print(f"\n{'='*50}")
    print(f"RESULTADO: {valid}/{len(PACK)} generadores válidos")
    if errors:
        print("ERRORES:")
        for e in errors:
            print(f"  • {e}")
    else:
        print("Todos los checks pasaron.")

    print("\nIDs en PACK:")
    for k in PACK:
        print(f"  - {k}")

    return valid == len(PACK)


if __name__ == "__main__":
    ok = validate_pack()
    sys.exit(0 if ok else 1)
