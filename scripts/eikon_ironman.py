#!/usr/bin/env python3
"""
eikon_ironman.py — gate agregado de estado real para outputs Eikon.

Este script NO renderiza assets por defecto. Lee/compone los tres frentes de
auditoría que ya existen sobre `output/`:

1. Layout: `scripts/eikon_validate_layout.py` en modo in-process.
2. Pixels: `_pixel-report.json` por marca (o recomputa con `--refresh-pixels`).
3. WCAG: `_contraste-report.json` por marca vía `eikon_aggregate_wcag.build_aggregate`.

La meta es que la Fase 2 tenga un artefacto reproducible: una tabla humana,
JSON opcional y exit code fallable por thresholds explícitos.

Uso:
    python3 scripts/eikon_ironman.py
    python3 scripts/eikon_ironman.py --json
    python3 scripts/eikon_ironman.py --write-json output/_ironman-report.json
    python3 scripts/eikon_ironman.py --fail-on-thresholds
    python3 scripts/eikon_ironman.py --fail-on-thresholds --max-pixel-warnings 100

Exit codes:
    0 — reporte generado; thresholds OK o no se pidió fallo.
    1 — con `--fail-on-thresholds`: algún threshold fue superado.
    2 — error de E/S/configuración (p.ej. output dir inexistente).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eikon_aggregate_wcag import build_aggregate  # noqa: E402
from eikon_validate_layout import scan_layout  # noqa: E402

DEFAULT_MANIFEST = "_manifest.json"
DEFAULT_PIXEL_REPORT = "_pixel-report.json"
DEFAULT_MIN_BYTES = 1024
DEFAULT_FG_DENSITY_MIN = 0.005


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{type(e).__name__}: {e}"
    if not isinstance(data, dict):
        return None, "estructura JSON inesperada (root no es object)"
    return data, None


def _discover_brand_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.is_dir():
        return []
    return [
        entry
        for entry in sorted(output_dir.iterdir())
        if entry.is_dir() and not entry.name.startswith(("_", "."))
    ]


def _parse_allow_list(raw: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(raw, str):
        pieces: Iterable[str] = raw.split(",")
    else:
        pieces = raw
    return tuple(piece.strip() for piece in pieces if piece and piece.strip())


def _pixel_row_from_report(
    brand_dir: Path,
    report: dict[str, Any] | None,
    *,
    source: str,
    error: str | None = None,
) -> dict[str, Any]:
    if report is None:
        return {
            "marca": brand_dir.name,
            "report_present": False,
            "report_valid": error is None,
            "report_source": source,
            "report_error": error,
            "assets": 0,
            "errors": 0,
            "warnings": 0,
            "identical_variant_pairs": 0,
            "identical_variants": [],
            "issue_assets": [],
        }

    totals = report.get("totals") or {}
    assets = report.get("assets") or []
    issue_assets: list[dict[str, Any]] = []
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            issues = asset.get("issues") or []
            if issues:
                issue_assets.append(
                    {
                        "path": asset.get("path"),
                        "category": asset.get("category"),
                        "type": asset.get("type"),
                        "variant": asset.get("variant"),
                        "issues": issues,
                    }
                )

    identical = report.get("identical_variants") or []
    if not isinstance(identical, list):
        identical = []

    return {
        "marca": str(report.get("marca") or brand_dir.name),
        "report_present": True,
        "report_valid": True,
        "report_source": source,
        "report_error": None,
        "assets": _safe_int(totals.get("assets_in_manifest")),
        "errors": _safe_int(totals.get("errors")),
        "warnings": _safe_int(totals.get("warnings")),
        "identical_variant_pairs": _safe_int(totals.get("identical_variant_pairs")),
        "identical_variants": identical,
        "issue_assets": issue_assets,
    }


def scan_pixels(
    output_dir: Path,
    *,
    refresh: bool = False,
    manifest_name: str = DEFAULT_MANIFEST,
    min_bytes: int = DEFAULT_MIN_BYTES,
    fg_density_min: float = DEFAULT_FG_DENSITY_MIN,
    allow_identical_types: Sequence[str] = (),
    compute_fg: bool = True,
) -> dict[str, Any]:
    """Carga o recomputa reportes pixel por marca y devuelve resumen."""
    brand_dirs = _discover_brand_dirs(output_dir)
    rows: list[dict[str, Any]] = []
    reports_missing = 0
    reports_invalid = 0

    validate_marca = None
    if refresh:
        try:
            from eikon_validate_pixels import validate_marca as _validate_marca
        except Exception as e:
            return {
                "refresh": True,
                "refresh_error": f"No se pudo importar eikon_validate_pixels: {type(e).__name__}: {e}",
                "reports_total": 0,
                "reports_missing": 0,
                "reports_invalid": len(brand_dirs),
                "assets_total": 0,
                "errors": 0,
                "warnings": 0,
                "identical_variant_pairs": 0,
                "brands_with_errors": 0,
                "brands_with_warnings": 0,
                "brands": [
                    _pixel_row_from_report(
                        b,
                        None,
                        source="refresh-error",
                        error="import eikon_validate_pixels failed",
                    )
                    for b in brand_dirs
                ],
            }
        validate_marca = _validate_marca

    for brand_dir in brand_dirs:
        if refresh:
            try:
                assert validate_marca is not None
                report = validate_marca(
                    brand_dir,
                    manifest_name=manifest_name,
                    min_bytes=min_bytes,
                    fg_density_min=fg_density_min,
                    allow_identical_types=allow_identical_types,
                    compute_fg=compute_fg,
                )
            except FileNotFoundError as e:
                reports_missing += 1
                rows.append(
                    _pixel_row_from_report(
                        brand_dir,
                        None,
                        source="computed",
                        error=str(e),
                    )
                )
                continue
            except (OSError, json.JSONDecodeError, ValueError) as e:
                reports_invalid += 1
                rows.append(
                    _pixel_row_from_report(
                        brand_dir,
                        None,
                        source="computed",
                        error=f"{type(e).__name__}: {e}",
                    )
                )
                continue
            rows.append(_pixel_row_from_report(brand_dir, report, source="computed"))
            continue

        report_path = brand_dir / DEFAULT_PIXEL_REPORT
        if not report_path.is_file():
            reports_missing += 1
            rows.append(
                _pixel_row_from_report(
                    brand_dir,
                    None,
                    source="disk",
                    error=f"missing {report_path}",
                )
            )
            continue

        report, error = _load_json(report_path)
        if error:
            reports_invalid += 1
            rows.append(
                _pixel_row_from_report(
                    brand_dir,
                    None,
                    source="disk",
                    error=error,
                )
            )
            continue
        rows.append(_pixel_row_from_report(brand_dir, report, source="disk"))

    reports_total = sum(1 for r in rows if r["report_present"] and r["report_valid"])
    total_errors = sum(r["errors"] for r in rows)
    total_warnings = sum(r["warnings"] for r in rows)
    total_identical = sum(r["identical_variant_pairs"] for r in rows)

    return {
        "refresh": refresh,
        "refresh_error": None,
        "reports_total": reports_total,
        "reports_missing": reports_missing,
        "reports_invalid": reports_invalid,
        "assets_total": sum(r["assets"] for r in rows),
        "errors": total_errors,
        "warnings": total_warnings,
        "identical_variant_pairs": total_identical,
        "brands_with_errors": sum(
            1
            for r in rows
            if r["errors"] > 0 or r["identical_variant_pairs"] > 0 or r["report_error"]
        ),
        "brands_with_warnings": sum(1 for r in rows if r["warnings"] > 0),
        "brands": rows,
    }


def summarize_layout(layout_report: dict[str, Any]) -> dict[str, Any]:
    rows = layout_report.get("brands") or []
    manifests_missing = sum(
        1 for row in rows if isinstance(row, dict) and not row.get("manifest_present")
    )
    brand_level_issues = sum(
        len(row.get("brand_issues") or []) for row in rows if isinstance(row, dict)
    )
    summary = dict(layout_report.get("summary") or {})
    summary["manifests_missing"] = manifests_missing
    summary["brand_level_issues"] = brand_level_issues
    return summary


def summarize_wcag(
    aggregate: dict[str, Any] | None,
    brand_names: set[str],
) -> dict[str, Any]:
    if aggregate is None:
        return {
            "reports_total": 0,
            "reports_missing": len(brand_names),
            "assets_total": 0,
            "aa_pass": 0,
            "aa_fail": 0,
            "aa_real_fail": 0,
            "no_foreground": 0,
            "aaa_pass": 0,
            "aaa_fail": 0,
            "brands_with_failures": 0,
            "brands": [],
        }

    per_brand = aggregate.get("per_brand") or []
    report_names = {
        str(row.get("marca")) for row in per_brand if isinstance(row, dict) and row.get("marca")
    }
    aa_fail = _safe_int((aggregate.get("wcag_aa") or {}).get("fail"))
    no_fg = _safe_int((aggregate.get("wcag_aa") or {}).get("no_foreground"))
    return {
        "reports_total": _safe_int(aggregate.get("brands_total"), len(report_names)),
        "reports_missing": len(brand_names - report_names),
        "assets_total": _safe_int(aggregate.get("total_assets")),
        "aa_pass": _safe_int((aggregate.get("wcag_aa") or {}).get("pass")),
        "aa_fail": aa_fail,
        "aa_real_fail": max(0, aa_fail - no_fg),
        "no_foreground": no_fg,
        "aaa_pass": _safe_int((aggregate.get("wcag_aaa") or {}).get("pass")),
        "aaa_fail": _safe_int((aggregate.get("wcag_aaa") or {}).get("fail")),
        "brands_with_failures": _safe_int(aggregate.get("brands_with_failures")),
        "brands": per_brand if isinstance(per_brand, list) else [],
    }


def _index_layout_brands(layout_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in layout_report.get("brands") or []:
        if isinstance(row, dict) and row.get("marca"):
            result[str(row["marca"])] = row
    return result


def _index_rows(rows: Iterable[dict[str, Any]], key: str = "marca") -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get(key):
            result[str(row[key])] = row
    return result


def _brand_status(
    layout_row: dict[str, Any] | None,
    pixel_row: dict[str, Any] | None,
    wcag_row: dict[str, Any] | None,
) -> str:
    layout_issue = bool(
        layout_row
        and (
            not layout_row.get("manifest_present")
            or layout_row.get("assets_with_issues", 0) > 0
            or layout_row.get("brand_issues")
        )
    )
    pixel_fail = bool(
        pixel_row
        and (
            pixel_row.get("errors", 0) > 0
            or pixel_row.get("identical_variant_pairs", 0) > 0
            or pixel_row.get("report_error")
        )
    )
    wcag_real_fail = 0
    no_fg = 0
    if wcag_row:
        aa_fail = _safe_int(wcag_row.get("aa_fail"))
        no_fg = _safe_int(wcag_row.get("no_foreground"))
        wcag_real_fail = max(0, aa_fail - no_fg)

    if layout_issue or pixel_fail or wcag_real_fail > 0:
        return "fail"
    if pixel_row and pixel_row.get("warnings", 0) > 0:
        return "warn"
    if no_fg > 0 or wcag_row is None:
        return "warn"
    return "ok"


def build_brand_rows(
    layout_report: dict[str, Any],
    pixels: dict[str, Any],
    wcag: dict[str, Any],
    brand_names: set[str],
) -> list[dict[str, Any]]:
    layout_by_brand = _index_layout_brands(layout_report)
    pixel_by_brand = _index_rows(pixels.get("brands") or [])
    wcag_by_brand = _index_rows(wcag.get("brands") or [])

    rows: list[dict[str, Any]] = []
    for marca in sorted(brand_names):
        lr = layout_by_brand.get(marca)
        pr = pixel_by_brand.get(marca)
        wr = wcag_by_brand.get(marca)
        aa_fail = _safe_int((wr or {}).get("aa_fail"))
        no_fg = _safe_int((wr or {}).get("no_foreground"))
        rows.append(
            {
                "marca": marca,
                "layout_manifest_present": bool(lr and lr.get("manifest_present")),
                "layout_assets": _safe_int((lr or {}).get("assets_total")),
                "layout_assets_with_issues": _safe_int((lr or {}).get("assets_with_issues")),
                "layout_brand_issues": len((lr or {}).get("brand_issues") or []),
                "pixel_report_present": bool(pr and pr.get("report_present")),
                "pixel_report_valid": bool(pr and pr.get("report_valid")),
                "pixel_errors": _safe_int((pr or {}).get("errors")),
                "pixel_warnings": _safe_int((pr or {}).get("warnings")),
                "pixel_identical_variant_pairs": _safe_int(
                    (pr or {}).get("identical_variant_pairs")
                ),
                "wcag_report_present": wr is not None,
                "wcag_aa_fail": aa_fail,
                "wcag_aa_real_fail": max(0, aa_fail - no_fg),
                "wcag_no_foreground": no_fg,
                "status": _brand_status(lr, pr, wr),
            }
        )
    return rows


def evaluate_thresholds(report: dict[str, Any], thresholds: dict[str, int]) -> list[dict[str, Any]]:
    summary = report["summary"]
    metrics = {
        "layout_assets_with_issues": summary["layout"]["assets_with_issues"],
        "layout_manifests_missing": summary["layout"]["manifests_missing"],
        "pixel_errors": summary["pixels"]["errors"],
        "pixel_warnings": summary["pixels"]["warnings"],
        "pixel_identical_variant_pairs": summary["pixels"]["identical_variant_pairs"],
        "pixel_reports_missing": summary["pixels"]["reports_missing"],
        "pixel_reports_invalid": summary["pixels"]["reports_invalid"],
        "wcag_aa_real_fails": summary["wcag"]["aa_real_fail"],
        "wcag_no_foreground": summary["wcag"]["no_foreground"],
        "wcag_reports_missing": summary["wcag"]["reports_missing"],
    }

    breaches: list[dict[str, Any]] = []
    for name, maximum in thresholds.items():
        value = _safe_int(metrics.get(name))
        if value > maximum:
            breaches.append({"metric": name, "value": value, "max": maximum})
    return breaches


def build_ironman_report(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir).resolve()
    brand_dirs = _discover_brand_dirs(output_dir)
    brand_names = {b.name for b in brand_dirs}

    layout_report = scan_layout(output_dir)
    pixels = scan_pixels(
        output_dir,
        refresh=args.refresh_pixels,
        manifest_name=args.manifest,
        min_bytes=args.min_bytes,
        fg_density_min=args.fg_density_min,
        allow_identical_types=_parse_allow_list(args.allow_identical_types),
        compute_fg=not args.skip_fg_check,
    )
    wcag_aggregate = build_aggregate(output_dir)
    wcag = summarize_wcag(wcag_aggregate, brand_names)

    # Incluir marcas que aparezcan sólo en algún reporte legacy.
    for row in layout_report.get("brands") or []:
        if isinstance(row, dict) and row.get("marca"):
            brand_names.add(str(row["marca"]))
    for row in pixels.get("brands") or []:
        if isinstance(row, dict) and row.get("marca"):
            brand_names.add(str(row["marca"]))
    for row in wcag.get("brands") or []:
        if isinstance(row, dict) and row.get("marca"):
            brand_names.add(str(row["marca"]))

    thresholds = {
        "layout_assets_with_issues": args.max_layout_issues,
        "layout_manifests_missing": args.max_layout_missing_manifests,
        "pixel_errors": args.max_pixel_errors,
        "pixel_warnings": args.max_pixel_warnings,
        "pixel_identical_variant_pairs": args.max_identical_variants,
        "pixel_reports_missing": args.max_missing_pixel_reports,
        "pixel_reports_invalid": args.max_invalid_pixel_reports,
        "wcag_aa_real_fails": args.max_wcag_aa_real_fails,
        "wcag_no_foreground": args.max_wcag_no_foreground,
        "wcag_reports_missing": args.max_missing_wcag_reports,
    }

    report = {
        "generated_at": _utc_now(),
        "output_dir": str(output_dir),
        "config": {
            "pixel_source": "computed" if args.refresh_pixels else "disk _pixel-report.json",
            "skip_fg_check": bool(args.skip_fg_check),
            "allow_identical_types": list(_parse_allow_list(args.allow_identical_types)),
        },
        "thresholds": thresholds,
        "summary": {
            "brands_total": len(brand_names),
            "layout": summarize_layout(layout_report),
            "pixels": {k: v for k, v in pixels.items() if k not in {"brands"}},
            "wcag": wcag,
        },
        "brands": build_brand_rows(layout_report, pixels, wcag, brand_names),
        "raw_refs": {
            "layout_report_in_memory": True,
            "wcag_aggregate_present": wcag_aggregate is not None,
        },
    }
    report["threshold_breaches"] = evaluate_thresholds(report, thresholds)
    return report


def _row_has_issue(row: dict[str, Any]) -> bool:
    return row.get("status") != "ok"


def render_table(report: dict[str, Any], *, only_issues: bool = False) -> str:
    summary = report["summary"]
    layout = summary["layout"]
    pixels = summary["pixels"]
    wcag = summary["wcag"]

    lines = [
        f"Ironman QA — output_dir: {report['output_dir']}",
        (
            f"Marcas: {summary['brands_total']}  ·  "
            f"Threshold breaches: {len(report['threshold_breaches'])}"
        ),
        "",
        (
            "Layout  "
            f"assets={layout['assets_total_scanned']}  "
            f"issues={layout['assets_with_issues']}  "
            f"brand_issues={layout['brand_level_issues']}  "
            f"missing_manifests={layout['manifests_missing']}"
        ),
        (
            "Pixels  "
            f"reports={pixels['reports_total']}  "
            f"missing={pixels['reports_missing']}  "
            f"invalid={pixels['reports_invalid']}  "
            f"assets={pixels['assets_total']}  "
            f"errors={pixels['errors']}  "
            f"warnings={pixels['warnings']}  "
            f"identical={pixels['identical_variant_pairs']}"
        ),
        (
            "WCAG    "
            f"reports={wcag['reports_total']}  "
            f"missing={wcag['reports_missing']}  "
            f"assets={wcag['assets_total']}  "
            f"AA pass={wcag['aa_pass']}  "
            f"AA fail={wcag['aa_fail']}  "
            f"real_fail={wcag['aa_real_fail']}  "
            f"no_fg={wcag['no_foreground']}"
        ),
    ]

    if report["threshold_breaches"]:
        lines.append("")
        lines.append("Thresholds superados:")
        for breach in report["threshold_breaches"]:
            lines.append(f"  · {breach['metric']}: {breach['value']} > {breach['max']}")

    rows = [r for r in report["brands"] if not only_issues or _row_has_issue(r)]
    if not rows:
        lines.append("")
        lines.append("✓ Sin issues por marca bajo el filtro actual.")
        return "\n".join(lines)

    headers = (
        "marca",
        "layout",
        "px E/W/I",
        "WCAG real/no_fg",
        "missing",
        "status",
    )
    table_rows: list[tuple[str, ...]] = []
    for row in rows:
        missing = []
        if not row["layout_manifest_present"]:
            missing.append("layout")
        if not row["pixel_report_present"] or not row["pixel_report_valid"]:
            missing.append("pixel")
        if not row["wcag_report_present"]:
            missing.append("wcag")
        table_rows.append(
            (
                str(row["marca"]),
                f"{row['layout_assets_with_issues']}/{row['layout_assets']}",
                f"{row['pixel_errors']}/{row['pixel_warnings']}/{row['pixel_identical_variant_pairs']}",
                f"{row['wcag_aa_real_fail']}/{row['wcag_no_foreground']}",
                ",".join(missing) if missing else "—",
                str(row["status"]),
            )
        )

    widths = [max(len(headers[i]), max(len(r[i]) for r in table_rows)) for i in range(len(headers))]
    sep = "  "
    lines.append("")
    lines.append("Resumen por marca" + (" (sólo issues)" if only_issues else "") + ":")
    lines.append(sep.join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    lines.append(sep.join("-" * widths[i] for i in range(len(headers))))
    for row in table_rows:
        lines.append(sep.join(row[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate agregado layout/pixels/WCAG para outputs Eikon.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output",
        help="Ruta al directorio output/ (default: <repo>/output).",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"Nombre del manifest por marca (default: {DEFAULT_MANIFEST}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el reporte completo como JSON en stdout.",
    )
    parser.add_argument(
        "--write-json",
        type=Path,
        help="Además escribe el reporte completo en esta ruta.",
    )
    parser.add_argument(
        "--only-issues",
        action="store_true",
        help="En tabla, muestra sólo marcas con status != ok.",
    )
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit 1 si algún metric supera su máximo configurado.",
    )

    # Pixel refresh opcional (por defecto se leen reportes ya generados).
    parser.add_argument(
        "--refresh-pixels",
        action="store_true",
        help="Recalcula pixel checks en memoria en vez de leer _pixel-report.json.",
    )
    parser.add_argument(
        "--skip-fg-check",
        action="store_true",
        help="Con --refresh-pixels, omite foreground density.",
    )
    parser.add_argument(
        "--allow-identical-types",
        default="",
        help="Con --refresh-pixels, allow-list separada por comas para variantes idénticas.",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=f"Con --refresh-pixels, tamaño mínimo PNG (default: {DEFAULT_MIN_BYTES}).",
    )
    parser.add_argument(
        "--fg-density-min",
        type=float,
        default=DEFAULT_FG_DENSITY_MIN,
        help=(
            f"Con --refresh-pixels, densidad mínima foreground (default: {DEFAULT_FG_DENSITY_MIN})."
        ),
    )

    # Thresholds estrictos por defecto; sólo afectan exit code con --fail-on-thresholds.
    parser.add_argument("--max-layout-issues", type=int, default=0)
    parser.add_argument("--max-layout-missing-manifests", type=int, default=0)
    parser.add_argument("--max-pixel-errors", type=int, default=0)
    parser.add_argument("--max-pixel-warnings", type=int, default=0)
    parser.add_argument("--max-identical-variants", type=int, default=0)
    parser.add_argument("--max-missing-pixel-reports", type=int, default=0)
    parser.add_argument("--max-invalid-pixel-reports", type=int, default=0)
    parser.add_argument("--max-wcag-aa-real-fails", type=int, default=0)
    parser.add_argument("--max-wcag-no-foreground", type=int, default=0)
    parser.add_argument("--max-missing-wcag-reports", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_dir():
        print(f"✗ No existe el directorio: {output_dir}", file=sys.stderr)
        return 2

    try:
        report = build_ironman_report(args)
    except OSError as e:
        print(f"✗ Error de E/S leyendo {output_dir}: {e}", file=sys.stderr)
        return 2

    if args.write_json:
        target = Path(args.write_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_table(report, only_issues=args.only_issues))

    if args.fail_on_thresholds and report["threshold_breaches"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
