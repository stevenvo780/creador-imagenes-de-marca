#!/usr/bin/env python3
"""
Script RE-PILOTO: limpia y regenera pinakotheke-kosmos + prizma-iris
con las plantillas data-driven corregidas.
"""

import json
import shutil
import subprocess
from pathlib import Path
from contrast_validator import ContrastValidator

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
MARCAS_DIR = ROOT / "marcas"

def clean_marca(slug):
    """Limpia output de una marca."""
    marca_dir = OUTPUT_DIR / slug
    if marca_dir.exists():
        shutil.rmtree(marca_dir)
        print(f"✓ Limpiado: {marca_dir}")
    return marca_dir

def regenerate_marca(slug):
    """Re-genera assets para una marca usando render.py"""
    print(f"\n→ Regenerando {slug}...")
    result = subprocess.run(
        ["python3", "render.py", "--marca", slug],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"✓ {slug} regenerado exitosamente")
        return True
    else:
        print(f"✗ Error regenerando {slug}:")
        print(result.stderr[:500])
        return False

def count_assets(marca_dir):
    """Cuenta PNG en un directorio."""
    if not marca_dir.exists():
        return 0
    return len(list(marca_dir.rglob("*.png")))

def run_validation(marca_slug):
    """Valida assets de una marca."""
    marca_dir = OUTPUT_DIR / marca_slug
    if not marca_dir.exists():
        print(f"✗ Directorio no existe: {marca_dir}")
        return None

    validator = ContrastValidator(marca_dir)
    results = validator.validate_all()

    # Resumen
    total = len(results)
    passed_aa = len([r for r in results if r.get("wcag_aa")])
    failed_aa = len([r for r in results if not r.get("wcag_aa") and not r.get("decorative")])
    decorative = len([r for r in results if r.get("decorative")])

    print(f"\n📊 Resumen {marca_slug}:")
    print(f"  Total assets: {total}")
    print(f"  WCAG AA ✓: {passed_aa}")
    print(f"  WCAG AA ✗: {failed_aa}")
    print(f"  Decorativos (excluidos): {decorative}")

    return {
        "total": total,
        "passed_aa": passed_aa,
        "failed_aa": failed_aa,
        "decorative": decorative,
        "results": results,
    }

def main():
    print("🔧 RE-PILOTO EIKON: pinakotheke-kosmos + prizma-iris\n")

    marcas = ["pinakotheke-kosmos", "prizma-iris"]
    all_results = {}

    for slug in marcas:
        print(f"\n{'='*60}")
        print(f" {slug.upper()}")
        print(f"{'='*60}")

        # 1. Limpiar
        marca_dir = clean_marca(slug)

        # 2. Regenerar
        if not regenerate_marca(slug):
            print(f"⚠ Saltando validación de {slug} por error en regeneración")
            continue

        # 3. Contar assets
        count = count_assets(marca_dir)
        print(f"→ Generados {count} assets")

        # 4. Validar
        validation = run_validation(slug)
        all_results[slug] = validation

        # 5. Mostrar samples
        if validation and count > 0:
            png_files = sorted(marca_dir.rglob("*.png"))[:6]
            print(f"\n  Ejemplos (6 primeros):")
            for png in png_files:
                rel_path = png.relative_to(OUTPUT_DIR)
                print(f"    • {rel_path}")

    # REPORTE FINAL
    print(f"\n{'='*60}")
    print(" REPORTE FINAL")
    print(f"{'='*60}")

    for slug, data in all_results.items():
        if data:
            print(f"\n{slug}:")
            print(f"  Total: {data['total']} | ✓ {data['passed_aa']} | ✗ {data['failed_aa']} | 🎨 {data['decorative']}")

    print(f"\n✓ Re-piloto completado")

if __name__ == "__main__":
    main()
