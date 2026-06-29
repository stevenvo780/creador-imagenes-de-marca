#!/usr/bin/env python3
"""
Mueve scripts redundantes/obsoletos al directorio de retención _legacy/.
"""

import shutil
from pathlib import Path

def main():
    root = Path("/workspace/Pinakotheke/eikon")
    legacy_dir = root / "_legacy"
    legacy_dir.mkdir(exist_ok=True)

    obsoletos = [
        "generar_agencia.py",
        "generar_agencia_v2.py",
        "re_pilot.py",
        "render.py",
        "render_hires.py",
        "render_ui_kit.py",
        "generar_maxcalidad.py",
        "generate_targets.py",
        "generate_templates.py",
        "render_publication_cards.py",
        "audit_render.py",
        "sync_publication_assets.py"
    ]

    print("Limpiando Motor EIKON...\n")
    movidos = 0
    for file_name in obsoletos:
        target = root / file_name
        if target.exists():
            dest = legacy_dir / file_name
            shutil.move(str(target), str(dest))
            print(f"✓ Movido: {file_name} → _legacy/")
            movidos += 1
        else:
            print(f"- Omitido (no existe): {file_name}")

    print(f"\nLimpieza finalizada. {movidos} scripts enviados a cuarentena.")

if __name__ == "__main__":
    main()
