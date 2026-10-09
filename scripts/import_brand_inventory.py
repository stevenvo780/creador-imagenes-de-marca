#!/usr/bin/env python3
"""Importa identidad original por proyecto desde la máquina cliente.

Dry-run por defecto. EIKON_API_KEY permite lecturas con scopes adecuados;
--apply exige EIKON_OWNER_SESSION de un login owner explícito y privado.
Los archivos locales se transmiten como bytes, nunca como rutas del servidor.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Permite ejecutar directamente scripts/import_brand_inventory.py.
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from webapp.api.schemas import VALID_PALETTE_KEYS, BrandCreate  # noqa: E402
from webapp.brand_briefs import LOGO_MAX_BYTES, validate_reference_logo  # noqa: E402
from webapp.services.eikon_runner import PROTECTED_BRAND_SLUGS, validate_slug  # noqa: E402


class ImportInventoryError(Exception):
    """Errores operativos sin headers, cookies ni respuesta privada del servidor."""


def _auth_headers(apply: bool) -> dict[str, str]:
    session = os.environ.get("EIKON_OWNER_SESSION")
    key = os.environ.get("EIKON_API_KEY")
    if apply and not session:
        raise ImportInventoryError("--apply requiere EIKON_OWNER_SESSION de propietario")
    if session:
        if any(ch in session for ch in "\r\n;"):
            raise ImportInventoryError("sesión privada inválida")
        return {"Cookie": f"eikon_jwt={session}"}
    if key:
        return {"Authorization": f"Bearer {key}"}
    raise ImportInventoryError("falta credencial privada en el entorno")


def _request(client, method, path, headers, **kwargs):
    try:
        result = client.request(method, path, headers=headers, **kwargs)
    except Exception:
        # No encadenar excepción: transportes pueden incluir headers sensibles.
        raise ImportInventoryError("falló la conexión al API") from None
    if result.status_code >= 400:
        raise ImportInventoryError(f"API rechazó operación ({result.status_code})")
    return result


def _logo_bytes(source: dict, config: Path, logo_root: Path | None) -> bytes | None:
    value = source.get("logo_asset")
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("referencia inválida")
    if value.startswith("data:"):
        _, encoded = value.split(";base64,", 1)
        if len(encoded) > (LOGO_MAX_BYTES * 4 // 3 + 8):
            raise ValueError("logo demasiado grande")
        content = base64.b64decode(encoded, validate=True)
    else:
        if "://" in value:
            raise ValueError("referencia remota inválida")
        path = Path(value)
        if not path.is_absolute():
            path = (logo_root or config.parent) / path
        with path.open("rb") as stream:
            content = stream.read(LOGO_MAX_BYTES + 1)
    validate_reference_logo(content)
    return content


def _payload(source: dict, project: dict) -> dict:
    original_slug = validate_slug(source["slug"])
    # Todo slug importado lleva namespace de proyecto, incluidos los reservados.
    slug = validate_slug(f"{project['slug']}-{original_slug}")
    if slug in PROTECTED_BRAND_SLUGS:
        slug = validate_slug(f"{project['slug']}-import-{original_slug}")
    payload = {
        "project_id": project["id"],
        "slug": slug,
        "name": source.get("nombre_producto") or source.get("nombre_corporativo") or original_slug,
        "palette": {
            key: value
            for key, value in source.get("paleta", {}).items()
            if key in VALID_PALETTE_KEYS
        },
        "typography": source.get("tipografia", {}),
        "logo_text": source.get("logo_texto", ""),
        "logo_symbol": source.get("logo_simbolo", source.get("simbolo", "")),
        "logo_style": source.get("logo_style", ""),
        "logo_seed": source.get("logo_seed", 0),
        "texts": {
            **source.get("textos", {}),
            "inventory_source": {
                "slug": original_slug,
                "nombre_corporativo": source.get("nombre_corporativo", ""),
            },
        },
    }
    return BrandCreate.model_validate(payload).model_dump(exclude={"logo_asset"})


def import_inventory(
    client,
    project_id: int,
    inventory_path: Path,
    *,
    apply: bool = False,
    logo_root: Path | None = None,
) -> dict:
    """Resumen de crear/idéntica/conflicto/ausente; nunca reemplaza identidad."""
    headers = _auth_headers(apply)
    if apply:
        me = _request(client, "GET", "/auth/me", headers).json()
        if me.get("user", {}).get("role") != "owner":
            raise ImportInventoryError("--apply requiere sesión de propietario")
    project = _request(client, "GET", f"/api/v1/projects/{project_id}", headers).json()
    if project["archived"]:
        raise ImportInventoryError("proyecto archivado")
    existing = _request(client, "GET", "/api/v1/brands", headers).json()["items"]
    by_slug = {item["slug"]: item for item in existing}
    files = sorted(inventory_path.rglob("*.json")) if inventory_path.is_dir() else [inventory_path]
    summary = {
        "mode": "apply" if apply else "dry-run",
        "project_id": project_id,
        "counts": dict.fromkeys(
            ["create", "skip_identical", "identity_conflict", "missing_reference"], 0
        ),
        "items": [],
    }
    for config in files:
        try:
            source = json.loads(config.read_text(encoding="utf-8"))
            payload = _payload(source, project)
        except Exception:
            raise ImportInventoryError("configuración de inventario inválida") from None
        try:
            logo = _logo_bytes(source, config, logo_root)
        except (OSError, ValueError):
            status = "missing_reference"
            logo = None
        else:
            old = by_slug.get(payload["slug"])
            # Si el mapeo de origen existe en otro proyecto, conservarlo.
            mapped = [
                b
                for b in existing
                if b.get("texts", {}).get("inventory_source", {}).get("slug") == source["slug"]
            ]
            if old is None and mapped:
                old = mapped[0]
            sha = hashlib.sha256(logo).hexdigest() if logo is not None else None
            if old is not None:
                identical = all(old.get(key) == value for key, value in payload.items())
                identical = identical and old.get("reference_logo_sha256") == sha
                status = "skip_identical" if identical else "identity_conflict"
            else:
                status = "create"
                if apply:
                    created = _request(
                        client, "POST", "/api/v1/brands", headers, json=payload
                    ).json()
                    # Registro antes de upload permite reportar fallo sin duplicar reintentos.
                    existing.append(created)
                    by_slug[created["slug"]] = created
                    if logo is not None:
                        content_type = validate_reference_logo(logo)
                        ref = _request(
                            client,
                            "POST",
                            f"/api/v1/brands/{created['id']}/reference-logo",
                            headers,
                            files={"file": ("reference-logo", logo, content_type)},
                        ).json()
                        created["reference_logo_sha256"] = ref["sha256"]
        summary["counts"][status] += 1
        summary["items"].append(
            {"source_slug": source["slug"], "slug": payload["slug"], "status": status}
        )
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, nargs="?", default=_REPO / "marcas")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--logo-root", type=Path, help="raíz local para referencias relativas")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="sólo resumen (predeterminado)")
    mode.add_argument("--apply", action="store_true", help="crear con sesión owner privada")
    args = parser.parse_args(argv)
    parsed = urlparse(args.base_url)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.hostname
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        print("Error: base-url debe ser HTTPS o loopback local, sin credenciales", file=sys.stderr)
        return 2
    try:
        with httpx.Client(base_url=args.base_url, timeout=30, follow_redirects=False) as client:
            summary = import_inventory(
                client, args.project_id, args.inventory, apply=args.apply, logo_root=args.logo_root
            )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except ImportInventoryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("Error: importación no completada", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
