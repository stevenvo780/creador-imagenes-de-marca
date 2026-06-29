#!/usr/bin/env python3
"""
eikon_validate_layout.py — Resumen de validación de layout por marca.

Recorre `output/<marca>/_manifest.json`, detecta marcas/assets con
`layout_status != "pass"` o `layout_warnings` que clasifiquen como
fail/warn (no info), e imprime una tabla en stdout (o JSON con
`--json`). Pensado como un "snap" rápido del estado de validación de
layout, similar al inventario que ya hace `eikon_count.py` para WCAG.

**Contrato del manifest (alineado con `eikon.py` Fase 5):**
- `assets[i].layout_status` ∈ {"pass", "warn", "fail"} (output de
  `aggregate_layout_status()`). Cualquier valor ≠ "pass" es un issue.
- `assets[i].layout_warnings` es una lista de dicts con al menos
  clave `type` (p.ej. `{"type": "overflow_x", "detail": "..."}`).
  La severidad se obtiene con `classify_layout_warning()`.
- Opcionalmente, `manifest["layout_status"]` y
  `manifest["layout_warnings"]` a nivel de marca.

**Forward-compat:** si los campos no aparecen en el manifest, se
asume "pass / sin warnings" y la marca no se reporta como issue.

Stdlib puro (más `eikon.py` para clasificación — sin Playwright).

Uso:
    python3 scripts/eikon_validate_layout.py
    python3 scripts/eikon_validate_layout.py --json
    python3 scripts/eikon_validate_layout.py --fail-on-errors
    python3 scripts/eikon_validate_layout.py --output-dir output
    python3 scripts/eikon_validate_layout.py --only-issues

Exit codes:
    0 — sin issues de layout detectados (o sólo info)
    1 — con `--fail-on-errors`: hay al menos un issue
    2 — error de E/S (output dir inexistente)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Estado que se considera "pass". Cualquier otro valor es un issue.
LAYOUT_STATUS_PASS = "pass"

# Severidades que cuentan como issue (info NO cuenta).
ISSUE_SEVERITIES = frozenset({"fail", "warn"})

# Claves que se inspeccionan dentro de cada asset del manifest.
ASSET_LAYOUT_STATUS_KEY = "layout_status"
ASSET_LAYOUT_WARNINGS_KEY = "layout_warnings"

# Claves opcionales a nivel de marca (manifest raíz).
BRAND_LAYOUT_STATUS_KEY = "layout_status"
BRAND_LAYOUT_WARNINGS_KEY = "layout_warnings"


# ---------------------------------------------------------------------------
# Clasificación de warnings: delega al motor si está disponible
# ---------------------------------------------------------------------------
def _classify_warning(warning: Any) -> str:
    """Devuelve "fail" | "warn" | "info" para un warning individual.

    Usa `eikon.classify_layout_warning` si está disponible (contrato
    canónico). Si no, fallback a un clasificador mínimo compatible.
    """
    try:
        from eikon import classify_layout_warning  # type: ignore

        return classify_layout_warning(warning)
    except Exception:
        # Fallback mínimo: si el motor no está disponible, asumimos
        # severidad "warn" para cualquier warning no vacío. No es ideal,
        # pero evita falsos negativos (mejor sobre-reportar que sub-
        # reportar). "info" sólo si type explícitamente desconocido.
        if not isinstance(warning, dict):
            return "warn"
        wtype = str(warning.get("type", "")).strip()
        if not wtype:
            return "info"
        known = {
            "empty_required_text",
            "off_viewport",
            "overflow_x",
            "overflow_y",
            "inspection_error",
        }
        if wtype in known:
            return "fail" if wtype in {"empty_required_text", "off_viewport"} else "warn"
        return "info"


# ---------------------------------------------------------------------------
# Discovery + lectura de manifests
# ---------------------------------------------------------------------------
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


def load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    """Lee y parsea _manifest.json. Devuelve None si falta o es inválido."""
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# Detección de issues
# ---------------------------------------------------------------------------
def _asset_issues(asset: dict[str, Any]) -> list[dict[str, str]]:
    """Devuelve issues de layout para un asset individual.

    Cada issue es un dict {"severity", "field", "type", "detail"}.
    Sólo cuentan como issue los warnings con severidad fail/warn
    (no info), alineado con `aggregate_layout_status` del motor.
    """
    issues: list[dict[str, str]] = []

    # 1. layout_status != "pass" → issue de status
    layout_status = asset.get(ASSET_LAYOUT_STATUS_KEY)
    if layout_status is not None and str(layout_status).strip() != LAYOUT_STATUS_PASS:
        issues.append(
            {
                "severity": str(layout_status).strip(),  # "warn" o "fail"
                "field": ASSET_LAYOUT_STATUS_KEY,
                "type": "",
                "detail": f"layout_status={layout_status}",
            }
        )

    # 2. layout_warnings con severidad fail/warn → issues
    warnings = asset.get(ASSET_LAYOUT_WARNINGS_KEY) or []
    if isinstance(warnings, list):
        for w in warnings:
            if w is None:
                continue
            sev = _classify_warning(w)
            if sev not in ISSUE_SEVERITIES:
                continue  # info: no es issue
            wtype = ""
            detail = ""
            if isinstance(w, dict):
                wtype = str(w.get("type", "")).strip()
                d = w.get("detail", "")
                if d is not None:
                    detail = str(d).strip()
            else:
                # Admitimos strings legacy (defensivo)
                wtype = str(w).strip()
            if not wtype and not detail:
                continue
            issues.append(
                {
                    "severity": sev,
                    "field": ASSET_LAYOUT_WARNINGS_KEY,
                    "type": wtype,
                    "detail": detail,
                }
            )

    return issues


def _brand_issues(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Issues de layout a nivel de marca (top-level del manifest)."""
    issues: list[dict[str, str]] = []

    brand_status = manifest.get(BRAND_LAYOUT_STATUS_KEY)
    if brand_status is not None and str(brand_status).strip() != LAYOUT_STATUS_PASS:
        issues.append(
            {
                "severity": str(brand_status).strip(),
                "field": f"brand.{BRAND_LAYOUT_STATUS_KEY}",
                "type": "",
                "detail": f"brand.layout_status={brand_status}",
            }
        )

    brand_warnings = manifest.get(BRAND_LAYOUT_WARNINGS_KEY) or []
    if isinstance(brand_warnings, list):
        for w in brand_warnings:
            if w is None:
                continue
            sev = _classify_warning(w)
            if sev not in ISSUE_SEVERITIES:
                continue
            wtype = ""
            detail = ""
            if isinstance(w, dict):
                wtype = str(w.get("type", "")).strip()
                d = w.get("detail", "")
                if d is not None:
                    detail = str(d).strip()
            else:
                wtype = str(w).strip()
            if not wtype and not detail:
                continue
            issues.append(
                {
                    "severity": sev,
                    "field": f"brand.{BRAND_LAYOUT_WARNINGS_KEY}",
                    "type": wtype,
                    "detail": detail,
                }
            )

    return issues


def scan_brand(brand_dir: Path) -> dict[str, Any]:
    """Escanea una marca: parsea manifest y devuelve su reporte de layout."""
    manifest_path = brand_dir / "_manifest.json"
    manifest = load_manifest(manifest_path)

    assets_total = 0
    assets_with_issues = 0
    asset_issue_rows: list[dict[str, Any]] = []
    brand_issue_rows: list[dict[str, str]] = []

    if manifest is not None:
        brand_issue_rows = _brand_issues(manifest)
        raw_assets = manifest.get("assets") or []
        if isinstance(raw_assets, list):
            assets = [a for a in raw_assets if isinstance(a, dict)]
            assets_total = len(assets)
            for asset in assets:
                issues = _asset_issues(asset)
                if not issues:
                    continue
                assets_with_issues += 1
                # Mantener referencia al manifest original para fidelidad
                asset_issue_rows.append(
                    {
                        "asset_path": str(asset.get("path", "")),
                        "category": str(asset.get("category", "")),
                        "type": str(asset.get("type", "")),
                        "variant": str(asset.get("variant", "")),
                        "layout_status": (
                            str(asset.get(ASSET_LAYOUT_STATUS_KEY))
                            if asset.get(ASSET_LAYOUT_STATUS_KEY) is not None
                            else ""
                        ),
                        "layout_warnings": [
                            w for w in (asset.get(ASSET_LAYOUT_WARNINGS_KEY) or []) if w is not None
                        ],
                        "issues": issues,
                    }
                )

    return {
        "marca": brand_dir.name,
        "manifest_present": manifest is not None,
        "manifest_path": str(manifest_path),
        "assets_total": assets_total,
        "assets_with_issues": assets_with_issues,
        "brand_issues": brand_issue_rows,
        "asset_issues": asset_issue_rows,
    }


def scan_layout(output_dir: Path) -> dict[str, Any]:
    """Escanea todas las marcas y devuelve el reporte agregado."""
    brands = discover_brands(output_dir)
    brand_reports = [scan_brand(b) for b in brands]

    assets_total_scanned = sum(r["assets_total"] for r in brand_reports)
    assets_with_issues = sum(r["assets_with_issues"] for r in brand_reports)
    brands_with_issues = sum(
        1 for r in brand_reports if r["assets_with_issues"] > 0 or r["brand_issues"]
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "output_dir": str(output_dir.resolve()),
        "summary": {
            "brands_total": len(brand_reports),
            "brands_with_issues": brands_with_issues,
            "assets_total_scanned": assets_total_scanned,
            "assets_with_issues": assets_with_issues,
        },
        "brands": brand_reports,
    }


# ---------------------------------------------------------------------------
# Resumen flat para integración con eikon_count.py
# ---------------------------------------------------------------------------
def layout_issues_by_brand(output_dir: Path) -> dict[str, int]:
    """Devuelve {marca: n_assets_con_issues} para alimentar eikon_count.py.

    Las marcas sin manifest o sin issues devuelven 0 (entrada presente
    con 0 si el manifest existe, ausente si no hay manifest — el caller
    puede usar dict.get con default 0).
    """
    report = scan_layout(output_dir)
    return {
        r["marca"]: r["assets_with_issues"] + (1 if r["brand_issues"] else 0)
        for r in report["brands"]
        if r["manifest_present"]
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1) :]


def render_table(report: dict[str, Any], *, only_issues: bool = False) -> str:
    """Genera tabla en texto plano para stdout."""
    summary = report["summary"]
    lines: list[str] = []

    lines.append(f"Layout validation — output_dir: {report['output_dir']}")
    lines.append(
        f"Marcas: {summary['brands_total']}  ·  "
        f"Assets escaneados: {summary['assets_total_scanned']}  ·  "
        f"Assets con issues: {summary['assets_with_issues']}  ·  "
        f"Marcas con issues: {summary['brands_with_issues']}"
    )
    lines.append("")

    if summary["assets_with_issues"] == 0 and summary["brands_with_issues"] == 0:
        lines.append("✓ Sin issues de layout detectados.")
        if not only_issues:
            scanned = [r["marca"] for r in report["brands"] if r["manifest_present"]]
            missing = [r["marca"] for r in report["brands"] if not r["manifest_present"]]
            if scanned:
                lines.append("")
                lines.append(f"Marcas escaneadas ({len(scanned)}):")
                for m in scanned:
                    lines.append(f"  · {m}")
            if missing:
                lines.append("")
                lines.append(f"Marcas sin _manifest.json ({len(missing)}):")
                for m in missing:
                    lines.append(f"  · {m}")
        return "\n".join(lines)

    # Tabla de issues por asset (compacta)
    headers = ("MARCA", "SEV", "ASSET", "CAT", "TYPE", "VARIANT", "STATUS", "WARN_TYPE", "DETAIL")
    rows: list[tuple[str, ...]] = []

    for brand in report["brands"]:
        for ai in brand["asset_issues"]:
            # Un row por cada warning con severidad fail/warn
            warn_rows = [i for i in ai["issues"] if i["field"] == ASSET_LAYOUT_WARNINGS_KEY]
            # Si el asset tiene layout_status issue pero ningún warning
            # concreto, igual emitimos una fila.
            status_rows = [i for i in ai["issues"] if i["field"] == ASSET_LAYOUT_STATUS_KEY]
            if not warn_rows and not status_rows:
                continue
            if not warn_rows:
                warn_rows = [{"severity": "", "type": "", "detail": ""}]
            for wr in warn_rows:
                rows.append(
                    (
                        brand["marca"],
                        wr.get("severity", "") or status_rows[0]["severity"]
                        if status_rows
                        else (wr.get("severity", "") or "—"),
                        _truncate(ai["asset_path"], 44),
                        ai["category"] or "—",
                        ai["type"] or "—",
                        ai["variant"] or "—",
                        ai["layout_status"] or "—",
                        wr.get("type", "") or "—",
                        _truncate(wr.get("detail", "") or "—", 50),
                    )
                )
        # Issues de marca (top-level)
        for bi in brand["brand_issues"]:
            rows.append(
                (
                    brand["marca"],
                    bi.get("severity", "—"),
                    "<brand-level>",
                    "—",
                    "—",
                    "—",
                    "—",
                    bi.get("type", "") or "—",
                    _truncate(bi.get("detail", "") or "—", 50),
                )
            )

    if not only_issues:
        # Tabla resumen por marca
        lines.append("Resumen por marca:")
        brand_headers = ("marca", "assets", "assets_issues", "estado")
        body_data = []
        for r in report["brands"]:
            estado = "fail" if (r["assets_with_issues"] or r["brand_issues"]) else "ok"
            body_data.append(
                (
                    r["marca"],
                    str(r["assets_total"]),
                    str(r["assets_with_issues"]),
                    estado,
                )
            )
        widths = [
            max(len(brand_headers[i]), max((len(row[i]) for row in body_data), default=0))
            for i in range(4)
        ]
        if not body_data:
            widths = [len(h) for h in brand_headers]
        sep = "  "
        lines.append(sep.join(brand_headers[i].ljust(widths[i]) for i in range(4)))
        lines.append(sep.join("-" * widths[i] for i in range(4)))
        for row in body_data:
            lines.append(sep.join(row[i].ljust(widths[i]) for i in range(4)))
        lines.append("")

    # Tabla detallada de issues
    widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(headers))
    ]
    sep = "  "
    lines.append("Issues detectados:")
    lines.append(sep.join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    lines.append(sep.join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        lines.append(sep.join(r[i].ljust(widths[i]) for i in range(len(headers))))

    return "\n".join(lines)


def render_json(report: dict[str, Any]) -> str:
    """Devuelve el reporte como JSON (indentado, ascii-safe)."""
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lee output/*/_manifest.json y reporta marcas/assets con "
            "layout_status != 'pass' o layout_warnings no vacío."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Ruta al directorio output/ (default: <eikon>/output)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el reporte como JSON en stdout (default: tabla en texto).",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit code 1 si hay al menos un issue de layout.",
    )
    parser.add_argument(
        "--only-issues",
        action="store_true",
        help="En modo tabla, sólo imprime el bloque de issues (omite resumen).",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()

    if not output_dir.is_dir():
        print(f"✗ No existe el directorio: {output_dir}", file=sys.stderr)
        return 2

    try:
        report = scan_layout(output_dir)
    except OSError as e:
        print(f"✗ Error de E/S leyendo {output_dir}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(render_json(report))
    else:
        print(render_table(report, only_issues=args.only_issues))

    has_issues = (
        report["summary"]["assets_with_issues"] > 0 or report["summary"]["brands_with_issues"] > 0
    )
    if args.fail_on_errors and has_issues:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
