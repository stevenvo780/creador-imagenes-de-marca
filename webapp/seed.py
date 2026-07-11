"""Seed idempotente: convierte marcas/*.json en filas de la tabla brands.

Uso como función:
    from webapp.seed import seed_brands
    seed_brands(db_path, marcas_dir)

Uso como CLI:
    python -m webapp.seed [--db PATH] [--marcas DIR] [--tenant-slug SLUG]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Raíz del repo para localizar marcas/ cuando se ejecuta desde cualquier directorio
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MARCAS_DIR = _REPO_ROOT / "marcas"
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "webapp" / "eikon.db"

# Tenant propietario de los assets de marca oficiales
_OWNER_SLUG = "owner"
_OWNER_NAME = "Steven Vallejo"


def _parse_brand_file(path: Path) -> dict[str, Any]:
    """Lee un archivo JSON de marca y devuelve sus datos normalizados."""
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _brand_row_kwargs(data: dict[str, Any]) -> dict[str, Any]:
    """Extrae los campos necesarios para upsert_brand desde el dict de la marca."""
    return {
        "slug": str(data.get("slug", "")),
        "name": str(data.get("nombre_producto") or data.get("slug", "")),
        "palette": data.get("paleta") or {},
        "typography": data.get("tipografia") or {},
        "logo_text": str(data.get("logo_texto") or ""),
        "logo_symbol": str(data.get("logo_simbolo") or ""),
        "texts": data.get("textos") or {},
    }


def seed_brands(
    db_path: Path,
    marcas_dir: Path | None = None,
    tenant_slug: str = _OWNER_SLUG,
    tenant_name: str = _OWNER_NAME,
) -> dict[str, Any]:
    """Seed idempotente: carga todas las marcas en la BD.

    Crea el tenant 'owner' si no existe.
    Usa upsert por (tenant_id, slug) para ser idempotente.

    Returns:
        dict con tenant_id, brands_total, brands_upserted, slugs_procesados.
    """
    # Importación tardía para evitar circular imports si se usa desde tests
    from webapp.storage import (
        create_tenant,
        get_tenant_by_slug,
        init_db,
        upsert_brand,
    )

    if marcas_dir is None:
        marcas_dir = _DEFAULT_MARCAS_DIR

    # Inicializa BD si no existe (idempotente)
    init_db(db_path)

    # Obtiene o crea el tenant owner
    tenant = get_tenant_by_slug(db_path, tenant_slug)
    if tenant is None:
        tenant = create_tenant(db_path, tenant_slug, tenant_name)
    tenant_id: int = int(tenant["id"])

    # Archivos JSON de marca (excluye los protegidos por los invariantes del proyecto)
    json_files = sorted(marcas_dir.glob("*.json"))

    upserted: list[str] = []
    errors: list[str] = []

    for fpath in json_files:
        try:
            data = _parse_brand_file(fpath)
            kwargs = _brand_row_kwargs(data)
            slug = kwargs["slug"]
            if not slug:
                errors.append(f"{fpath.name}: sin slug")
                continue
            upsert_brand(
                db_path,
                tenant_id=tenant_id,
                **kwargs,
            )
            upserted.append(slug)
        except Exception as exc:
            errors.append(f"{fpath.name}: {exc}")

    return {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "brands_total": len(json_files),
        "brands_upserted": len(upserted),
        "slugs": upserted,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI del seed."""
    parser = argparse.ArgumentParser(
        description="Seed idempotente: carga marcas/*.json en la tabla brands."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB_PATH,
        help="Ruta a la base de datos SQLite (default: data/webapp/eikon.db)",
    )
    parser.add_argument(
        "--marcas",
        type=Path,
        default=_DEFAULT_MARCAS_DIR,
        help="Directorio con los archivos *.json de marca (default: marcas/)",
    )
    parser.add_argument(
        "--tenant-slug",
        default=_OWNER_SLUG,
        help=f"Slug del tenant propietario (default: {_OWNER_SLUG!r})",
    )
    parser.add_argument(
        "--tenant-name",
        default=_OWNER_NAME,
        help=f"Nombre del tenant a crear si no existe (default: {_OWNER_NAME!r})",
    )
    args = parser.parse_args(argv)

    result = seed_brands(
        db_path=args.db,
        marcas_dir=args.marcas,
        tenant_slug=args.tenant_slug,
        tenant_name=args.tenant_name,
    )

    print(f"Tenant: {result['tenant_slug']} (id={result['tenant_id']})")
    print(f"Archivos procesados: {result['brands_total']}")
    print(f"Brands upserted: {result['brands_upserted']}")
    if result["errors"]:
        print("Errores:")
        for err in result["errors"]:
            print(f"  ! {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
