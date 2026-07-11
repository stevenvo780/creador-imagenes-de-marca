#!/usr/bin/env python3
"""
eikon_count.py — Inventario y tabla maestra de outputs de Eikon.

Recorre `output/`, cuenta PNGs, manifests y reportes WCAG por marca,
detecta marcas sin assets o sin alguno de los artefactos esperados,
y escribe `_STATUS.md` en la raíz de eikon con la tabla consolidada.

Es stdlib puro (sin dependencias externas). Pensado como "snap" rápido
del estado real del directorio de outputs.

Uso:
    python3 scripts/eikon_count.py
    python3 scripts/eikon_count.py --output-dir output --root /workspace/Pinakotheke/eikon
    python3 scripts/eikon_count.py --stdout   # imprime también la tabla en consola

Exit codes:
    0 — todo OK
    1 — no se encontraron marcas
    2 — error de E/S
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def discover_brands(output_dir: Path) -> list[Path]:
    """Devuelve las subcarpetas de marcas (excluye agregados y ocultos)."""
    if not output_dir.is_dir():
        return []
    brands: list[Path] = []
    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        brands.append(entry)
    return brands


def count_pngs(brand_dir: Path) -> int:
    """Cuenta archivos PNG (recursivo, sin filtro)."""
    return sum(1 for _ in brand_dir.rglob("*.png"))


def load_manifest_assets(manifest_path: Path) -> tuple[int, int, int]:
    """Lee _manifest.json y devuelve (total, generated, errors). 0/0/0 si falta."""
    if not manifest_path.is_file():
        return (0, 0, 0)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return (0, 0, 0)
    assets = data.get("assets") or []
    total = int(data.get("total_assets") or len(assets))
    generated = sum(1 for a in assets if isinstance(a, dict) and a.get("status") == "generated")
    errors = sum(1 for a in assets if isinstance(a, dict) and a.get("status") == "error")
    return (total, generated, errors)


def load_contraste(contraste_path: Path) -> dict[str, Any]:
    """Lee _contraste-report.json y devuelve un dict con métricas clave."""
    if not contraste_path.is_file():
        return {}
    try:
        data = json.loads(contraste_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "timestamp": str(data.get("timestamp", "")),
        "total_assets": int(data.get("total_assets", 0) or 0),
        "aa_pass": int(((data.get("wcag_aa") or {}).get("pass", 0)) or 0),
        "aa_fail": int(((data.get("wcag_aa") or {}).get("fail", 0)) or 0),
        "no_foreground": int(((data.get("wcag_aa") or {}).get("no_foreground", 0)) or 0),
        "aaa_pass": int(((data.get("wcag_aaa") or {}).get("pass", 0)) or 0),
        "aaa_fail": int(((data.get("wcag_aaa") or {}).get("fail", 0)) or 0),
    }


def build_rows(output_dir: Path) -> list[dict[str, Any]]:
    """Itera marcas y arma una fila por cada una con todas las métricas."""
    rows: list[dict[str, Any]] = []
    for brand_dir in discover_brands(output_dir):
        slug = brand_dir.name
        pngs = count_pngs(brand_dir)
        m_total, m_gen, m_err = load_manifest_assets(brand_dir / "_manifest.json")
        contraste = load_contraste(brand_dir / "_contraste-report.json")
        gallery = (output_dir / f"_gallery_{slug}.html").is_file()

        rows.append(
            {
                "marca": slug,
                "pngs": pngs,
                "manifest_total": m_total,
                "manifest_generated": m_gen,
                "manifest_errors": m_err,
                "has_manifest": m_total > 0,
                "contraste_total": contraste.get("total_assets", 0),
                "aa_pass": contraste.get("aa_pass", 0),
                "aa_fail": contraste.get("aa_fail", 0),
                "no_foreground": contraste.get("no_foreground", 0),
                "aaa_pass": contraste.get("aaa_pass", 0),
                "aaa_fail": contraste.get("aaa_fail", 0),
                "has_gallery": gallery,
            }
        )
    return rows


def aggregate_totals(rows: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """Calcula totales globales para el reporte."""
    total_pngs = sum(r["pngs"] for r in rows)
    total_manifested = sum(r["manifest_total"] for r in rows)
    total_generated = sum(r["manifest_generated"] for r in rows)
    total_errors = sum(r["manifest_errors"] for r in rows)

    total_aa_pass = sum(r["aa_pass"] for r in rows)
    total_aa_fail = sum(r["aa_fail"] for r in rows)
    total_no_fg = sum(r["no_foreground"] for r in rows)
    total_aaa_pass = sum(r["aaa_pass"] for r in rows)
    total_aaa_fail = sum(r["aaa_fail"] for r in rows)

    aggregated_html = (output_dir / "_gallery_aggregated.html").is_file()
    aggregated_contraste = (output_dir / "_contraste-report.json").is_file()

    return {
        "brands_total": len(rows),
        "pngs_total": total_pngs,
        "manifest_assets": total_manifested,
        "manifest_generated": total_generated,
        "manifest_errors": total_errors,
        "aa_pass": total_aa_pass,
        "aa_fail": total_aa_fail,
        "no_foreground": total_no_fg,
        "aaa_pass": total_aaa_pass,
        "aaa_fail": total_aaa_fail,
        "aggregated_gallery": aggregated_html,
        "aggregated_contraste": aggregated_contraste,
    }


def render_markdown(
    rows: list[dict[str, Any]], totals: dict[str, Any], output_dir: Path, root: Path
) -> str:
    """Genera el cuerpo Markdown del _STATUS.md."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    header_lines = [
        "# _STATUS — Eikon Output Snapshot",
        "",
        f"_Generado: {now}_  ",
        f"_Output dir: `{output_dir}`_  ",
        "_Source: `scripts/eikon_count.py`_",
        "",
        "## Resumen global",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Marcas | {totals['brands_total']} |",
        f"| PNGs totales (recursivo) | {totals['pngs_total']} |",
        f"| Assets en manifests | {totals['manifest_assets']} |",
        f"| Assets `generated` (manifest) | {totals['manifest_generated']} |",
        f"| Assets `error` (manifest) | {totals['manifest_errors']} |",
        f"| Assets WCAG AA pass | {totals['aa_pass']} |",
        f"| Assets WCAG AA fail | {totals['aa_fail']} |",
        f"|   ↳ sin foreground detectable | {totals['no_foreground']} |",
        f"| Assets WCAG AAA pass | {totals['aaa_pass']} |",
        f"| Assets WCAG AAA fail | {totals['aaa_fail']} |",
        f"| Galería agregada | {'sí' if totals['aggregated_gallery'] else 'NO'} |",
        f"| Reporte contraste agregado | {'sí' if totals['aggregated_contraste'] else 'NO'} |",
        "",
    ]

    body = [
        "## Tabla por marca",
        "",
        "| Marca | PNG | Manifest | AA pass | AA fail | no_fg | AAA pass | AAA fail | Galería | Layout |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for r in rows:
        manifest_cell = (
            f"{r['manifest_generated']}/{r['manifest_total']}" if r["has_manifest"] else "—"
        )
        layout_cell = (
            f"{r['layout_issues']}" if r["layout_issues"] > 0 else "✓" if r["has_manifest"] else "—"
        )
        body.append(
            f"| `{r['marca']}` | {r['pngs']} | {manifest_cell} | "
            f"{r['aa_pass']} | {r['aa_fail']} | {r['no_foreground']} | "
            f"{r['aaa_pass']} | {r['aaa_fail']} | "
            f"{'✓' if r['has_gallery'] else '✗'} | {layout_cell} |"
        )
    body.append("")
    body.append("Leyenda:")
    body.append("- `PNG` = archivos `.png` bajo `output/<marca>/` (recursivo).")
    body.append("- `Manifest` = `generated / total_assets` en `_manifest.json` (o `—` si falta).")
    body.append("- `Galería` = presencia de `output/_gallery_<marca>.html`.")
    body.append(
        "- `no_fg` = assets donde el validador WCAG no detectó foreground (no se cuentan como `AA fail` real)."
    )
    body.append(
        '- `Layout` = assets con `layout_status != "pass"` o `layout_warnings` no vacío (✓ = 0 issues, — = sin manifest). Ver `scripts/eikon_validate_layout.py`.'
    )
    body.append("")

    # Bloque de ayuda
    body.extend(
        [
            "## Cómo regenerar",
            "",
            "Asumiendo cwd = raíz de eikon:",
            "",
            "```bash",
            "# 1. Conteo + _STATUS.md (incluye columna Layout)",
            "python3 scripts/eikon_count.py",
            "",
            "# 2. Validación de layout por marca (assets con layout_status != pass",
            "#    o layout_warnings no vacío). --fail-on-errors → exit 1 si hay issues.",
            "python3 scripts/eikon_validate_layout.py",
            "python3 scripts/eikon_validate_layout.py --json",
            "python3 scripts/eikon_validate_layout.py --fail-on-errors",
            "",
            "# 3. Reporte WCAG agregado en output/_contraste-report.json",
            "python3 scripts/eikon_aggregate_wcag.py",
            "",
            "# 4. Galerías individuales + agregada",
            "python3 gallery.py --all-marcas",
            "python3 gallery.py --all-marcas --aggregated",
            "",
            "# 5. Re-render completo (cuando hay cambios en motor/plantillas)",
            "python3 eikon.py --all",
            "```",
            "",
            "Ver `docs/QA-CHECKLIST.md` para el checklist visual de QA.",
            "",
        ]
    )

    return "\n".join(header_lines + body)


def print_console_table(rows: list[dict[str, Any]], totals: dict[str, Any]) -> None:
    """Imprime tabla compacta en stdout."""
    headers = (
        "marca",
        "png",
        "manifest",
        "AA pass",
        "AA fail",
        "no_fg",
        "AAA pass",
        "AAA fail",
        "gal",
        "layout",
    )
    body_rows = []
    for r in rows:
        manifest = f"{r['manifest_generated']}/{r['manifest_total']}" if r["has_manifest"] else "—"
        layout_cell = (
            str(r["layout_issues"])
            if r.get("layout_issues", 0) > 0
            else ("ok" if r["has_manifest"] else "—")
        )
        body_rows.append(
            (
                r["marca"],
                str(r["pngs"]),
                manifest,
                str(r["aa_pass"]),
                str(r["aa_fail"]),
                str(r["no_foreground"]),
                str(r["aaa_pass"]),
                str(r["aaa_fail"]),
                "si" if r["has_gallery"] else "no",
                layout_cell,
            )
        )

    widths = [max(len(headers[i]), max(len(r[i]) for r in body_rows)) for i in range(len(headers))]
    sep = "  "
    print(sep.join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print(sep.join("-" * widths[i] for i in range(len(headers))))
    for r in body_rows:
        print(sep.join(r[i].ljust(widths[i]) for i in range(len(headers))))

    print(
        f"\nResumen: {totals['brands_total']} marcas, "
        f"{totals['pngs_total']} PNG, "
        f"AA {totals['aa_pass']}/{totals['aa_pass'] + totals['aa_fail']} pass, "
        f"no_fg {totals['no_foreground']}, "
        f"layout issues {sum(r.get('layout_issues', 0) for r in rows)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cuenta PNGs/manifests/WCAG por marca y escribe _STATUS.md.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Ruta al directorio output/ (default: <eikon>/output)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Raíz del proyecto eikon (default: <padre de scripts/>)",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=None,
        help="Ruta al _STATUS.md (default: <root>/_STATUS.md)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Imprime también la tabla en stdout (no afecta la escritura del .md)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    root = args.root.resolve()
    status_path = (args.status_path or (root / "_STATUS.md")).resolve()

    if not output_dir.is_dir():
        print(f"✗ No existe el directorio: {output_dir}", file=sys.stderr)
        return 2

    try:
        rows = build_rows(output_dir)
    except OSError as e:
        print(f"✗ Error de E/S leyendo {output_dir}: {e}", file=sys.stderr)
        return 2

    # Enriquecer cada fila con conteo de issues de layout (integración
    # opcional con eikon_validate_layout). Si el módulo no está disponible
    # o el scan falla, dejamos el campo en 0 (no rompe el flujo).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from eikon_validate_layout import layout_issues_by_brand  # type: ignore

        layout_map = layout_issues_by_brand(output_dir)
    except Exception:
        layout_map = {}
    for r in rows:
        r["layout_issues"] = int(layout_map.get(r["marca"], 0))

    if not rows:
        print(
            f"✗ No se encontraron marcas en {output_dir}/ (solo entradas agregadas u ocultas)",
            file=sys.stderr,
        )
        return 1

    totals = aggregate_totals(rows, output_dir)
    markdown = render_markdown(rows, totals, output_dir, root)

    try:
        status_path.write_text(markdown, encoding="utf-8")
    except OSError as e:
        print(f"✗ No se pudo escribir {status_path}: {e}", file=sys.stderr)
        return 2

    if args.stdout:
        print(f"✓ _STATUS.md escrito: {status_path}\n")
        print_console_table(rows, totals)

    return 0


if __name__ == "__main__":
    sys.exit(main())
