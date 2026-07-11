#!/usr/bin/env python3
"""Guard de regresión: el render de taxonomía existente debe quedar pixel-idéntico.

Compara hashes de PÍXELES decodificados (independiente del encoding PNG) contra
un golden committeado en ``tests/golden/``. Sirve para que cualquier refactor
confirme que no cambió la salida visual de las marcas canónicas.

Uso:
  python scripts/eikon_render_guard.py snapshot   # fija el golden desde el render actual
  python scripts/eikon_render_guard.py            # compara (exit 1 si hay regresión)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
GOLD = REPO / "tests" / "golden"
BRANDS = ("pinakotheke-kosmos", "prizma-iris")


def _pixhash(png: Path) -> str:
    with Image.open(png) as im:
        return hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest()


def _render(brand: str) -> None:
    subprocess.run(
        [sys.executable, "eikon.py", "--marca", brand, "--clean", "--skip-contraste"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )


def _current(brand: str) -> dict[str, str]:
    base = REPO / "output" / brand
    return {str(p.relative_to(base)): _pixhash(p) for p in sorted(base.rglob("*.png"))}


def snapshot() -> None:
    GOLD.mkdir(parents=True, exist_ok=True)
    for brand in BRANDS:
        _render(brand)
        data = _current(brand)
        (GOLD / f"{brand}.pix.json").write_text(json.dumps(data, indent=0, sort_keys=True))
        print(f"{brand}: {len(data)} assets -> golden")


def check() -> int:
    bad = 0
    for brand in BRANDS:
        _render(brand)
        cur = _current(brand)
        gold_file = GOLD / f"{brand}.pix.json"
        if not gold_file.exists():
            print(f"{brand}: NO golden ({len(cur)} assets) — run snapshot first")
            bad += 1
            continue
        old = json.loads(gold_file.read_text())
        changed = sorted(k for k in old if k in cur and old[k] != cur[k])
        missing = sorted(k for k in old if k not in cur)
        if changed or missing:
            bad += 1
            print(f"{brand}: REGRESSION changed={changed} missing={missing}")
        else:
            print(f"{brand}: OK {len(cur)} assets pixel-identical")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "snapshot":
        snapshot()
    else:
        sys.exit(check())
