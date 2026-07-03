"""Router de brands: CRUD scoped por tenant vía cookie JWT."""

from __future__ import annotations

import json
import shutil
from base64 import b64encode
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as FPath

from eikon_core.isotype import IsotypeParams, generate_isotype
from eikon_core.isotypes.catalog import ALGORITHMS
from eikon_core.mapping import map_marca_to_vars
from webapp.services.eikon_runner import PROTECTED_BRAND_SLUGS, validate_slug
from webapp.storage import (
    create_brand,
    delete_brand,
    get_brand,
    list_brands,
    update_brand,
)

from .deps import current_user, get_settings, get_storage
from .schemas import _SQLITE_INT_MAX, BrandCreate, BrandUpdate
from .serializers import brand_to_dict

router = APIRouter(prefix="/api/v1/brands", tags=["brands"])

# Anotación compartida para brand_id en path params: valida rango int64.
_BrandId = Annotated[int, FPath(ge=1, le=_SQLITE_INT_MAX)]


@router.get("")
def list_brands_endpoint(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Lista los brands del tenant autenticado."""
    settings = get_settings(request)
    rows = list_brands(settings.db_url, user["tenant_id"])
    return {"items": [brand_to_dict(r) for r in rows]}


@router.post("", status_code=201)
def create_brand_endpoint(
    payload: BrandCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Crea un brand para el tenant. 409 si el slug ya existe en el tenant."""
    settings = get_settings(request)
    try:
        slug = validate_slug(payload.slug)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if slug in PROTECTED_BRAND_SLUGS:
        raise HTTPException(
            status_code=422,
            detail=f"slug reservado: {slug!r} no está disponible para uso de tenant",
        )
    try:
        row = create_brand(
            settings.db_url,
            user["tenant_id"],
            slug,
            payload.name,
            palette=payload.palette,
            typography=payload.typography,
            logo_text=payload.logo_text,
            logo_symbol=payload.logo_symbol,
            logo_style=payload.logo_style,
            logo_seed=payload.logo_seed,
            texts=payload.texts,
        )
    except Exception as e:
        # UNIQUE(tenant_id, slug) violado: no filtrar mensaje de SQLite al cliente.
        raise HTTPException(
            status_code=409, detail="slug ya existe en este tenant"
        ) from e
    return brand_to_dict(row)


@router.get("/{brand_id}")
def get_brand_endpoint(
    brand_id: _BrandId,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Devuelve un brand por id, scoped al tenant. 404 si no pertenece."""
    settings = get_settings(request)
    row = get_brand(settings.db_url, user["tenant_id"], brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="brand not found")
    return brand_to_dict(row)


@router.put("/{brand_id}")
def update_brand_endpoint(
    brand_id: _BrandId,
    payload: BrandUpdate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Actualiza campos de un brand del tenant. 404 si no pertenece."""
    settings = get_settings(request)
    fields: dict[str, Any] = {}
    if payload.name is not None:
        fields["name"] = payload.name
    if payload.palette is not None:
        fields["palette_json"] = json.dumps(payload.palette, sort_keys=True)
    if payload.typography is not None:
        fields["typography_json"] = json.dumps(payload.typography, sort_keys=True)
    if payload.logo_text is not None:
        fields["logo_text"] = payload.logo_text
    if payload.logo_symbol is not None:
        fields["logo_symbol"] = payload.logo_symbol
    if payload.logo_style is not None:
        fields["logo_style"] = payload.logo_style
    if payload.logo_seed is not None:
        fields["logo_seed"] = payload.logo_seed
    if payload.texts is not None:
        fields["texts_json"] = json.dumps(payload.texts, sort_keys=True)
    if not fields:
        raise HTTPException(
            status_code=422,
            detail=(
                "ningún campo actualizable recibido; "
                "campos permitidos: name, palette, typography, logo_text, logo_symbol, logo_style, logo_seed, texts"
            ),
        )
    try:
        row = update_brand(settings.db_url, user["tenant_id"], brand_id, **fields)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="brand not found") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return brand_to_dict(row)


@router.delete("/{brand_id}", status_code=204)
def delete_brand_endpoint(
    brand_id: _BrandId,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> None:
    """Elimina un brand del tenant junto con sus archivos de salida. 404 si no pertenece."""
    settings = get_settings(request)
    tenant_id = user["tenant_id"]

    # Leer el slug antes de borrar para poder limpiar el árbol de salida.
    brand_row = get_brand(settings.db_url, tenant_id, brand_id)
    if brand_row is None:
        raise HTTPException(status_code=404, detail="brand not found")

    try:
        delete_brand(settings.db_url, tenant_id, brand_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="brand not found") from e

    # Limpieza best-effort: borrar árbol de salida output/tenants/<tid>/<slug>/.
    # Usamos el seam para resolver la ruta y validar que está dentro del scope del tenant.
    storage = get_storage(request)
    brand_slug = str(brand_row["slug"])
    try:
        brand_dir = Path(storage.full_path(tenant_id, brand_slug))
        if brand_dir.exists() and brand_dir.is_dir():
            shutil.rmtree(brand_dir, ignore_errors=True)
    except (ValueError, OSError):
        # Nunca fallar la request por limpieza de archivos; el DB ya fue borrado.
        pass


@router.get("/{brand_id}/logo-options")
def get_logo_options(
    brand_id: _BrandId,
    request: Request,
    count: int = 24,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Devuelve variaciones de logo (isotipo) para que el usuario elija.

    Query params:
    - count: número de variaciones (default 24, max 100)

    Devuelve:
    {
        "options": [
            {"style": "poligono_regular", "seed": 12345, "svg_data_uri": "data:image/svg+xml;base64,..."},
            ...
        ]
    }

    Determinístico: las variaciones se generan con la PALETA de la marca y diferentes seeds.
    """
    settings = get_settings(request)
    tenant_id = user["tenant_id"]
    count = min(max(1, count), 100)  # Rango 1-100

    # Valida que el brand pertenece al tenant
    brand = get_brand(settings.db_url, tenant_id, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="brand not found")

    # Construye la marca desde el brand
    brand_slug = str(brand.get("slug", ""))
    marca = {
        "slug": brand_slug,
        "nombre_producto": str(brand.get("name", "")),
        "paleta": json.loads(str(brand.get("palette_json", "{}"))),
        "tipografia": json.loads(str(brand.get("typography_json", "{}"))),
        "logo_texto": str(brand.get("logo_text", "")),
        "logo_simbolo": str(brand.get("logo_symbol", "")),
        "textos": json.loads(str(brand.get("texts_json", "{}"))),
    }

    # Genera variaciones: recorre ALGORITHMS y varía seeds
    options = []
    styles = [algo[0] for algo in ALGORITHMS]  # Lista de style IDs
    for i in range(count):
        # Cicla entre estilos disponibles y varía el seed
        style_idx = i % len(styles)
        style = styles[style_idx]
        seed = (i // len(styles)) * 1000 + i  # Seed pseudo-aleatorio pero determinístico

        # Genera SVG isotipo
        try:
            vars_dict = map_marca_to_vars(marca, "isotipo")
            initials = (
                marca.get("logo_texto")
                or marca.get("nombre_producto")
                or marca.get("nombre_corporativo")
                or "E"
            ).strip()
            params = IsotypeParams(
                seed=seed,
                style=style,
                brand_initials=(initials[:2] or "E"),
                brand_symbol=str(marca.get("logo_simbolo") or "◆"),
                primary_color=vars_dict.get("primario") or vars_dict.get("acento") or "#43b5a6",
                accent_color=vars_dict.get("acento") or "#e0a85e",
                bg_color=vars_dict.get("bg") or "#0f1f1d",
            )
            svg = generate_isotype(params)
            if svg.strip():
                svg_data_uri = (
                    "data:image/svg+xml;base64," + b64encode(svg.encode("utf-8")).decode("ascii")
                )
                options.append({
                    "style": style,
                    "seed": seed,
                    "svg_data_uri": svg_data_uri,
                })
        except Exception:
            # Skip broken generations
            pass

    return {"options": options}
