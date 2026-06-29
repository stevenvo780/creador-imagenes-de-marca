#!/usr/bin/env python3
"""
eikon_aggregate_wcag.py — Agrega reportes WCAG por marca en un solo global.

Lee cada `output/<marca>/_contraste-report.json`, consolida un resumen
global y lo escribe en `output/_contraste-report.json`. También imprime
una tabla compacta por marca en stdout.

Es un script de stdlib (sin dependencias externas) pensado para ejecutarse
DESPUÉS de una corrida de `eikon.py` que ya haya escrito reportes por marca.

Uso:
    python3 scripts/eikon_aggregate_wcag.py
    python3 scripts/eikon_aggregate_wcag.py --output-dir output
    python3 scripts/eikon_aggregate_wcag.py --quiet

Exit codes:
    0 — agregado OK (al menos 1 reporte por marca procesado)
    1 — no se encontraron reportes por marca
    2 — error de E/S inesperado
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Tamaño razonable para un reporte "vacío" pero válido
EMPTY_REPORT_PLACEHOLDER = "<empty>"


def discover_brand_reports(output_dir: Path) -> list[Path]:
    """Devuelve la lista de rutas a `_contraste-report.json` por marca, ordenadas."""
    reports: list[Path] = []
    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Ignorar dirs agregados o huérfanos que no sean marcas
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        report = entry / "_contraste-report.json"
        if report.is_file():
            reports.append(report)
    return reports


def load_brand_report(report_path: Path) -> dict[str, Any] | None:
    """Carga un reporte por marca. Retorna None si está corrupto."""
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ {report_path}: JSON inválido ({e})", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"  ⚠ {report_path}: estructura inesperada", file=sys.stderr)
        return None
    return data


def safe_get(d: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    """Acceso anidado tolerante a None."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def build_aggregate(output_dir: Path) -> dict[str, Any] | None:
    """Construye el reporte agregado. Retorna None si no hay datos."""
    brand_reports = discover_brand_reports(output_dir)
    if not brand_reports:
        return None

    per_brand_rows: list[dict[str, Any]] = []
    failing_assets: list[dict[str, Any]] = []

    total_assets = 0
    total_aa_pass = 0
    total_aa_fail = 0
    total_no_fg = 0
    total_aaa_pass = 0
    total_aaa_fail = 0
    brands_with_failures = 0

    for report_path in brand_reports:
        slug = report_path.parent.name
        data = load_brand_report(report_path)
        if data is None:
            continue

        assets = int(safe_get(data, "total_assets", default=0))
        aa_pass = int(safe_get(data, "wcag_aa", "pass", default=0))
        aa_fail = int(safe_get(data, "wcag_aa", "fail", default=0))
        no_fg = int(safe_get(data, "wcag_aa", "no_foreground", default=0))
        aaa_pass = int(safe_get(data, "wcag_aaa", "pass", default=0))
        aaa_fail = int(safe_get(data, "wcag_aaa", "fail", default=0))
        ts = str(data.get("timestamp", ""))
        summary = str(data.get("summary", ""))

        real_fails = aa_fail - no_fg
        if real_fails > 0:
            brands_with_failures += 1

        per_brand_rows.append(
            {
                "marca": slug,
                "assets": assets,
                "aa_pass": aa_pass,
                "aa_fail": aa_fail,
                "no_foreground": no_fg,
                "aaa_pass": aaa_pass,
                "aaa_fail": aaa_fail,
                "timestamp": ts,
            }
        )

        for fail in data.get("failing_assets_aa", []) or []:
            failing_assets.append(
                {
                    "marca": slug,
                    "img": fail.get("img"),
                    "contrast_ratio": fail.get("contrast_ratio"),
                    "bg_color": fail.get("bg_color"),
                    "text_color": fail.get("text_color"),
                    "issue": fail.get("issue"),
                    "no_foreground": bool(fail.get("no_foreground", False)),
                }
            )

        total_assets += assets
        total_aa_pass += aa_pass
        total_aa_fail += aa_fail
        total_no_fg += no_fg
        total_aaa_pass += aaa_pass
        total_aaa_fail += aaa_fail

    aggregate = {
        "timestamp": datetime.now(UTC).isoformat(),
        "config": {
            "source": "per-brand _contraste-report.json",
            "output_dir": str(output_dir),
        },
        "brands_total": len(per_brand_rows),
        "total_assets": total_assets,
        "wcag_aa": {
            "pass": total_aa_pass,
            "fail": total_aa_fail,
            "no_foreground": total_no_fg,
        },
        "wcag_aaa": {
            "pass": total_aaa_pass,
            "fail": total_aaa_fail,
        },
        "brands_with_failures": brands_with_failures,
        "per_brand": per_brand_rows,
        "failing_assets_aa": failing_assets,
        "summary": (
            f"{total_aa_pass}/{total_assets} assets cumplen WCAG AA (>= 4.5:1) "
            f"agregados sobre {len(per_brand_rows)} marcas"
            + (f" — {total_no_fg} sin foreground detectable" if total_no_fg else "")
        ),
    }
    return aggregate


def print_table(per_brand_rows: list[dict[str, Any]], totals: dict[str, int]) -> None:
    """Imprime tabla resumen en stdout."""
    headers = ("marca", "assets", "AA pass", "AA fail", "no_fg", "AAA pass", "AAA fail")
    body_rows = [
        (
            r["marca"],
            str(r["assets"]),
            str(r["aa_pass"]),
            str(r["aa_fail"]),
            str(r["no_foreground"]),
            str(r["aaa_pass"]),
            str(r["aaa_fail"]),
        )
        for r in per_brand_rows
    ]
    total_row = (
        "TOTAL",
        str(totals["assets"]),
        str(totals["aa_pass"]),
        str(totals["aa_fail"]),
        str(totals["no_fg"]),
        str(totals["aaa_pass"]),
        str(totals["aaa_fail"]),
    )

    all_rows = body_rows + [total_row]
    widths = [max(len(headers[i]), max(len(r[i]) for r in all_rows)) for i in range(len(headers))]
    sep = "  "
    print(sep.join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print(sep.join("-" * widths[i] for i in range(len(headers))))
    for r in body_rows:
        print(sep.join(r[i].ljust(widths[i]) for i in range(len(headers))))
    print(sep.join(total_row[i].ljust(widths[i]) for i in range(len(headers))))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agrega reportes WCAG por marca en `output/_contraste-report.json`.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Ruta al directorio output/ (default: <eikon>/output)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suprime la tabla en stdout (solo escribe el archivo agregado)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    if not output_dir.is_dir():
        print(f"✗ No existe el directorio: {output_dir}", file=sys.stderr)
        return 2

    try:
        aggregate = build_aggregate(output_dir)
    except OSError as e:
        print(f"✗ Error de E/S: {e}", file=sys.stderr)
        return 2

    if aggregate is None:
        print(
            f"✗ No se encontraron reportes por marca en {output_dir}/<marca>/_contraste-report.json",
            file=sys.stderr,
        )
        return 1

    target = output_dir / "_contraste-report.json"
    try:
        target.write_text(
            json.dumps(aggregate, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"✗ No se pudo escribir {target}: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        brands = aggregate["per_brand"]
        totals = {
            "assets": aggregate["total_assets"],
            "aa_pass": aggregate["wcag_aa"]["pass"],
            "aa_fail": aggregate["wcag_aa"]["fail"],
            "no_fg": aggregate["wcag_aa"]["no_foreground"],
            "aaa_pass": aggregate["wcag_aaa"]["pass"],
            "aaa_fail": aggregate["wcag_aaa"]["fail"],
        }
        print(
            f"\n✓ Reporte agregado: {target}\n"
            f"  Marcas: {aggregate['brands_total']}  ·  "
            f"Assets: {totals['assets']}  ·  "
            f"AA pass: {totals['aa_pass']}/{totals['assets']}  ·  "
            f"AAA pass: {totals['aaa_pass']}/{totals['assets']}\n"
        )
        print_table(brands, totals)

    return 0


if __name__ == "__main__":
    sys.exit(main())
