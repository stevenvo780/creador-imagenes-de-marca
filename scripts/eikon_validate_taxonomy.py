#!/usr/bin/env python3
"""Validador stdlib de taxonomy.json v1 para Eikon.

No modifica archivos. Verifica estructura, templates existentes y paridad con
la taxonomía legacy en Python. Los warnings documentan drift con layouts.json;
solo fallan con --strict.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY = ROOT / "config" / "taxonomy.json"
DEFAULT_TEMPLATES = ROOT / "templates"
DEFAULT_LAYOUTS = ROOT / "config" / "layouts.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class Report:
    issues: list[dict[str, Any]] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str, where: str = "") -> None:
        row = {"severity": severity, "code": code, "message": message}
        if where:
            row["where"] = where
        self.issues.append(row)

    def summary(self) -> dict[str, int]:
        return {
            "fail": sum(1 for i in self.issues if i["severity"] == "fail"),
            "warn": sum(1 for i in self.issues if i["severity"] == "warn"),
            "info": sum(1 for i in self.issues if i["severity"] == "info"),
            "total": len(self.issues),
        }

    def should_fail(self, strict: bool) -> bool:
        s = self.summary()
        return s["fail"] > 0 or (strict and s["warn"] > 0)

    def to_json(self) -> str:
        return json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "summary": self.summary(),
                "issues": self.issues,
            },
            indent=2,
            ensure_ascii=False,
        )

    def to_table(self) -> str:
        summary = self.summary()
        lines = [
            "Taxonomy validation — taxonomy.json",
            f"fail={summary['fail']} warn={summary['warn']} info={summary['info']} total={summary['total']}",
        ]
        if not self.issues:
            lines.append("✓ Sin issues detectados.")
            return "\n".join(lines)
        lines.append("")
        for issue in self.issues:
            where = f" [{issue['where']}]" if issue.get("where") else ""
            lines.append(
                f"[{issue['severity'].upper():4}] {issue['code']}: {issue['message']}{where}"
            )
        return "\n".join(lines)


def load_json(path: Path, report: Report) -> dict[str, Any] | None:
    if not path.is_file():
        report.add("fail", "E001", f"archivo no existe: {path}", str(path))
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        report.add("fail", "E002", f"JSON inválido: {e}", str(path))
        return None
    if not isinstance(data, dict):
        report.add("fail", "E003", "root debe ser object", str(path))
        return None
    return data


def validate_content(data: dict[str, Any], templates_dir: Path, report: Report) -> None:
    try:
        from eikon_core.validation import validate_taxonomy

        validate_taxonomy(data)
    except Exception as e:
        report.add("fail", "S001", str(e), "taxonomy.json")
        return

    protected = set(data.get("protected_templates") or [])
    for family_name, family in (data.get("families") or {}).items():
        for category_name, category in (family.get("categories") or {}).items():
            seen_types: set[str] = set()
            for type_entry in category.get("types") or []:
                type_name = str(type_entry.get("name", ""))
                where = f"families.{family_name}.categories.{category_name}.{type_name}"
                if type_name in seen_types:
                    report.add("fail", "T001", f"type duplicado: {type_name}", where)
                seen_types.add(type_name)
                template = type_entry.get("template")
                if isinstance(template, str):
                    path = templates_dir / template
                    if not path.is_file():
                        report.add("fail", "T002", f"template no existe: {template}", where)
                    if template in protected or type_entry.get("protected"):
                        report.add(
                            "info", "T003", f"template protegido/read-only: {template}", where
                        )


def _spec_map(
    types_by_category: dict[str, list[Any]],
) -> dict[str, list[tuple[str, int, int, tuple[str, ...]]]]:
    return {
        category: [
            (t.name, t.width, t.height, tuple(v.name for v in t.variants)) for t in type_specs
        ]
        for category, type_specs in types_by_category.items()
    }


def cross_check_legacy(taxonomy_path: Path, report: Report) -> None:
    try:
        from eikon_core.taxonomy import _from_taxonomy_json, _legacy_python_taxonomia
    except Exception as e:
        report.add(
            "warn", "X001", f"no se pudo importar eikon_core.taxonomy: {type(e).__name__}: {e}"
        )
        return

    for is_prizma, family in ((False, "cloud_atlas"), (True, "prizma")):
        try:
            legacy = _spec_map(_legacy_python_taxonomia(is_prizma))
            current = _spec_map(_from_taxonomy_json(taxonomy_path, is_prizma))
        except Exception as e:
            report.add(
                "fail", "X002", f"no se pudo cargar taxonomía {family}: {type(e).__name__}: {e}"
            )
            continue
        if legacy != current:
            report.add("warn", "X003", "taxonomy.json difiere de _legacy_python_taxonomia", family)


def cross_check_layouts(  # noqa: C901  # validación cruzada taxonomía/layouts con muchas ramas
    data: dict[str, Any], layouts_path: Path, templates_dir: Path, report: Report
) -> None:
    if not layouts_path.is_file():
        report.add("info", "L000", f"layouts.json ausente: {layouts_path}")
        return
    try:
        layouts_data = json.loads(layouts_path.read_text(encoding="utf-8"))
    except Exception as e:
        report.add("warn", "L001", f"layouts.json inválido: {e}")
        return
    layouts = layouts_data.get("layouts") or []
    if not isinstance(layouts, list):
        report.add("warn", "L002", "layouts.json layouts no es lista")
        return

    type_dims: dict[str, tuple[int, int]] = {}
    for family in (data.get("families") or {}).values():
        for category in (family.get("categories") or {}).values():
            for type_entry in category.get("types") or []:
                if isinstance(type_entry, dict):
                    type_dims[str(type_entry.get("name"))] = (
                        int(type_entry.get("width", 0)),
                        int(type_entry.get("height", 0)),
                    )

    for idx, layout in enumerate(layouts):
        if not isinstance(layout, dict):
            continue
        lid = layout.get("id")
        template = layout.get("template")
        where = f"layouts[{idx}]"
        if isinstance(template, str) and not (templates_dir / template).is_file():
            report.add(
                "warn",
                "L010",
                f"template referenciado por layouts.json no existe: {template}",
                where,
            )
        if isinstance(lid, str) and lid in type_dims:
            expected = type_dims[lid]
            actual = (int(layout.get("ancho", 0)), int(layout.get("alto", 0)))
            if expected != actual:
                report.add(
                    "warn",
                    "L011",
                    f"dims layouts {actual[0]}x{actual[1]} != taxonomy {expected[0]}x{expected[1]}",
                    where,
                )


def validate_taxonomy_file(
    taxonomy_path: Path,
    templates_dir: Path,
    layouts_path: Path,
    *,
    cross_check: bool = True,
) -> Report:
    report = Report()
    data = load_json(taxonomy_path, report)
    if data is None:
        return report
    validate_content(data, templates_dir, report)
    if cross_check:
        cross_check_legacy(taxonomy_path, report)
    cross_check_layouts(data, layouts_path, templates_dir, report)
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida taxonomy.json v1 y drift mecánico.")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--layouts", type=Path, default=DEFAULT_LAYOUTS)
    parser.add_argument("--strict", action="store_true", help="warnings cuentan como fallo")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument("--no-eikon-cross-check", action="store_true", help="omite paridad legacy")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = validate_taxonomy_file(
        args.taxonomy.resolve(),
        args.templates.resolve(),
        args.layouts.resolve(),
        cross_check=not args.no_eikon_cross_check,
    )
    print(report.to_json() if args.json else report.to_table())
    return 1 if report.should_fail(args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
