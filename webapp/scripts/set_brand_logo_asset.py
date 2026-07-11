#!/usr/bin/env python3
"""Script para setear logo_asset de un brand por (tenant_slug, brand_slug).

Uso:
    python webapp/scripts/set_brand_logo_asset.py <tenant_slug> <brand_slug> <logo_asset_path>

Ejemplo:
    python webapp/scripts/set_brand_logo_asset.py steven-vallejo agora assets/logos/agora.svg

Esto actualiza el brand "agora" del tenant "steven-vallejo" para usar el logo en assets/logos/agora.svg
como su isotipo (en vez del procedural generado).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar webapp
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from webapp import storage


def main() -> None:
    if len(sys.argv) != 4:
        print("Uso: python webapp/scripts/set_brand_logo_asset.py <tenant_slug> <brand_slug> <logo_asset_path>")
        print("\nEjemplo:")
        print("  python webapp/scripts/set_brand_logo_asset.py steven-vallejo agora assets/logos/agora.svg")
        sys.exit(1)

    tenant_slug = sys.argv[1]
    brand_slug = sys.argv[2]
    logo_asset_path = sys.argv[3]

    db_url = os.environ.get("DATABASE_URL") or (repo_root / "data" / "webapp" / "eikon.db")
    print(f"Database URL: {db_url}")

    # Obtener el tenant por slug
    tenant = storage.get_tenant_by_slug(db_url, tenant_slug)
    if tenant is None:
        print(f"Error: tenant '{tenant_slug}' no encontrado", file=sys.stderr)
        sys.exit(1)

    tenant_id = int(tenant["id"])
    print(f"Tenant {tenant_slug} (id={tenant_id})")

    # Obtener el brand por slug dentro del tenant
    brand = storage.get_brand_by_slug(db_url, tenant_id, brand_slug)
    if brand is None:
        print(f"Error: brand '{brand_slug}' no encontrado en tenant '{tenant_slug}'", file=sys.stderr)
        sys.exit(1)

    brand_id = int(brand["id"])
    print(f"Brand {brand_slug} (id={brand_id})")

    # Actualizar logo_asset
    try:
        updated = storage.update_brand(
            db_url,
            tenant_id,
            brand_id,
            logo_asset=logo_asset_path,
        )
        print(f"✓ Brand actualizado")
        print(f"  logo_asset: {updated.get('logo_asset')}")
    except Exception as e:
        print(f"Error al actualizar brand: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
