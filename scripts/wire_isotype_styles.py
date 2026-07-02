#!/usr/bin/env python3
"""Wirea los algoritmos de símbolo IMPLEMENTADOS al wizard.

1) Expande config/axes.json → axis `isotype_style`.options con todos los estilos
   que tienen generador en el registro (eikon_core.isotypes.GENERATORS), con
   "none" al FINAL (para que "que varíe" muestree estilos reales primero).
2) Genera frontend/src/i18n/isotypeStyles.generated.ts con etiquetas claras
   (label_es) + agrupación por categoría, para mostrar nombres entendibles
   agrupados en el wizard.

Corré: ./.venv/bin/python scripts/wire_isotype_styles.py
"""
from __future__ import annotations

import json
from pathlib import Path

from eikon_core.isotypes import ALGORITHMS, GENERATORS, catalog_coverage

ROOT = Path(__file__).resolve().parent.parent
AXES_PATH = ROOT / "config" / "axes.json"
TS_PATH = ROOT / "frontend" / "src" / "i18n" / "isotypeStyles.generated.ts"

# Estilos built-in originales (siguen soportados por isotype.py _GENERATORS).
BUILTIN = [
    ("lettermark", "Monograma simple", "Básicos"),
    ("geometric", "Geométrico", "Básicos"),
    ("abstract", "Abstracto", "Básicos"),
    ("enclosure", "Encerrado", "Básicos"),
    ("orbital", "Órbitas", "Básicos"),
    ("facet", "Facetado", "Básicos"),
    ("concentric", "Anillos", "Básicos"),
    ("burst", "Ráfaga", "Básicos"),
    ("monogram", "Monograma a dos colores", "Básicos"),
    ("grid", "Retícula", "Básicos"),
]


def main() -> None:
    cov = catalog_coverage()
    print(f"catálogo={cov['catalog_total']} implementados={cov['implemented']} faltan={len(cov['missing'])}")
    if cov["missing"]:
        print("  faltan:", ", ".join(cov["missing"][:30]))

    # entradas (id, label, category) para estilos con generador disponible
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for bid, label, cat in BUILTIN:
        if bid in GENERATORS and bid not in seen:
            entries.append((bid, label, cat))
            seen.add(bid)
    for sid, label, cat, _math in ALGORITHMS:
        if sid in GENERATORS and sid not in seen:
            entries.append((sid, label, cat))
            seen.add(sid)

    # ── 1) axes.json ──────────────────────────────────────────────────────────
    axes = json.loads(AXES_PATH.read_text(encoding="utf-8"))
    opts: dict[str, dict] = {}
    for sid, label, _cat in entries:
        opts[sid] = {"description": label, "data_attrs": {"data-isotype-style": sid}}
    # "none" al final → "que varíe" muestrea estilos reales primero.
    opts["none"] = {"description": "Sin símbolo procedural", "data_attrs": {}}
    axes["axes"]["isotype_style"]["options"] = opts
    AXES_PATH.write_text(json.dumps(axes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"axes.json: {len(opts)} opciones de isotype_style escritas")

    # ── 2) labels TS agrupados por categoría ─────────────────────────────────
    by_cat: dict[str, list[tuple[str, str]]] = {}
    labels: dict[str, str] = {}
    for sid, label, cat in entries:
        labels[sid] = label
        by_cat.setdefault(cat, []).append((sid, label))

    lines = [
        "// AUTOGENERADO por scripts/wire_isotype_styles.py — no editar a mano.",
        "// Etiquetas claras + agrupación por categoría de los estilos de símbolo.",
        "",
        "export const ISOTYPE_LABELS: Record<string, string> = {",
    ]
    for sid, label in labels.items():
        esc = label.replace('"', '\\"')
        lines.append(f'  "{sid}": "{esc}",')
    lines.append("};")
    lines.append("")
    lines.append("export const ISOTYPE_CATEGORIES: { category: string; styles: string[] }[] = [")
    for cat, items in by_cat.items():
        ids = ", ".join(f'"{sid}"' for sid, _ in items)
        lines.append(f'  {{ category: "{cat}", styles: [{ids}] }},')
    lines.append("];")
    lines.append("")
    TS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"isotypeStyles.generated.ts: {len(labels)} labels en {len(by_cat)} categorías")


if __name__ == "__main__":
    main()
