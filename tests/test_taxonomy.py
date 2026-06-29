#!/usr/bin/env python3
"""Tests stdlib para taxonomy.json v1 y su validador."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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


def minimal_taxonomy(template: str = "lockup_horizontal.html") -> dict:
    type_entry = {
        "name": "lockup_horizontal",
        "width": 1200,
        "height": 400,
        "template": template,
        "variants": [{"id": "v1_color", "label": "Color"}],
    }
    return {
        "schema_version": 1,
        "version": "1.0.0",
        "families": {
            "cloud_atlas": {"categories": {"logos": {"device_scale": 3, "types": [type_entry]}}},
            "prizma": {"categories": {"logos": {"device_scale": 3, "types": [type_entry]}}},
        },
    }


def test_real_taxonomy_validates() -> None:
    section("1. taxonomy.json real")
    from scripts.eikon_validate_taxonomy import validate_taxonomy_file

    report = validate_taxonomy_file(
        ROOT / "config" / "taxonomy.json",
        ROOT / "templates",
        ROOT / "config" / "layouts.json",
        cross_check=True,
    )
    summary = report.summary()
    check("taxonomy real: 0 fails", summary["fail"] == 0, str(summary))
    check("taxonomy real: familias presentes", (ROOT / "config" / "taxonomy.json").is_file())


def test_schema_rejects_missing_family() -> None:
    section("2. validate_taxonomy rechaza familia faltante")
    from eikon import validate_taxonomy

    data = minimal_taxonomy()
    del data["families"]["prizma"]
    try:
        validate_taxonomy(data)
    except ValueError as e:
        check("levanta ValueError", "prizma" in str(e), str(e))
    else:
        check("levanta ValueError", False, "no falló")


def test_schema_rejects_duplicate_variant() -> None:
    section("3. validate_taxonomy rechaza variant duplicada")
    from eikon import validate_taxonomy

    data = minimal_taxonomy()
    variants = data["families"]["cloud_atlas"]["categories"]["logos"]["types"][0]["variants"]
    variants.append({"id": "v1_color", "label": "Dup"})
    try:
        validate_taxonomy(data)
    except ValueError as e:
        check("levanta duplicado", "duplicada" in str(e) or "duplicado" in str(e), str(e))
    else:
        check("levanta duplicado", False, "no falló")


def test_validator_detects_missing_template() -> None:
    section("4. validador detecta template faltante")
    from scripts.eikon_validate_taxonomy import validate_taxonomy_file

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        templates = tmp / "templates"
        templates.mkdir()
        taxonomy = tmp / "taxonomy.json"
        taxonomy.write_text(json.dumps(minimal_taxonomy("missing.html")), encoding="utf-8")
        layouts = tmp / "layouts.json"
        layouts.write_text('{"layouts": []}', encoding="utf-8")
        report = validate_taxonomy_file(taxonomy, templates, layouts, cross_check=False)
        codes = {i["code"] for i in report.issues}
        check("T002 presente", "T002" in codes, str(report.issues))
        check("hay fail", report.summary()["fail"] >= 1, str(report.summary()))


def test_cli_exit_codes() -> None:
    section("5. CLI exit codes")
    script = ROOT / "scripts" / "eikon_validate_taxonomy.py"
    clean = subprocess.run(
        ["python3", str(script), "--no-eikon-cross-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check("CLI real non-strict exit 0", clean.returncode == 0, clean.stdout + clean.stderr)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        templates = tmp / "templates"
        templates.mkdir()
        bad = tmp / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        layouts = tmp / "layouts.json"
        layouts.write_text('{"layouts": []}', encoding="utf-8")
        run = subprocess.run(
            ["python3", str(script), "--taxonomy", str(bad), "--templates", str(templates), "--layouts", str(layouts), "--no-eikon-cross-check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        check("CLI bad schema exit 1", run.returncode == 1, run.stdout + run.stderr)


def test_taxonomy_parity_helpers() -> None:
    section("6. JSON vs legacy parity")
    from eikon_core.taxonomy import _from_taxonomy_json, _legacy_python_taxonomia

    def serial(tax):
        return {
            cat: [(t.name, t.width, t.height, tuple(v.name for v in t.variants)) for t in specs]
            for cat, specs in tax.items()
        }

    check(
        "cloud_atlas parity",
        serial(_from_taxonomy_json(ROOT / "config" / "taxonomy.json", False)) == serial(_legacy_python_taxonomia(False)),
    )
    check(
        "prizma parity",
        serial(_from_taxonomy_json(ROOT / "config" / "taxonomy.json", True)) == serial(_legacy_python_taxonomia(True)),
    )


def main() -> int:
    print("=" * 60)
    print("  EIKON taxonomy.json — Tests")
    print("=" * 60)
    tests = [
        test_real_taxonomy_validates,
        test_schema_rejects_missing_family,
        test_schema_rejects_duplicate_variant,
        test_validator_detects_missing_template,
        test_cli_exit_codes,
        test_taxonomy_parity_helpers,
    ]
    for test in tests:
        test()
    print("\n" + "=" * 60)
    print(f"  Resultado: {PASSED} ✓ / {FAILED} ✗")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
