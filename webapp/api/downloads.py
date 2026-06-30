"""Router de descargas: servir el PNG de una variación y empacar ZIPs.

Las variaciones se resuelven scoped por tenant. Toda lectura/empaquetado de
assets pasa por el seam de almacenamiento (StorageBackend, inyectado vía
app.state), que aísla los archivos bajo output/tenants/<tenant_id>/... y valida
contra path-traversal. El output_path persistido es una ruta absoluta dentro del
scope del tenant; aquí se convierte a su clave relativa para el seam.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from webapp.storage import get_batch, get_variation, list_variations
from webapp.storage_backend import StorageBackend

from .deps import current_user, get_settings, get_storage
from .schemas import ZipRequest

router = APIRouter(prefix="/api/v1", tags=["downloads"])


def _seam_key(storage: StorageBackend, tenant_id: int, output_path: str | None) -> str:
    """Convierte el output_path persistido en la clave relativa del seam del tenant.

    Lanza 404 si la variación no tiene archivo y 400 si la ruta cae fuera del
    scope del tenant (defensa en profundidad contra cross-tenant / traversal).
    """
    if not output_path:
        raise HTTPException(status_code=404, detail="variation has no file")
    tenant_root = Path(storage.full_path(tenant_id, "."))
    try:
        return str(Path(output_path).resolve().relative_to(tenant_root))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid path") from e


def _zip_response(storage: StorageBackend, tenant_id: int, keys: list[str]) -> Response:
    """Empaca por el seam las claves relativas dadas en un único ZIP en memoria."""
    try:
        data = storage.zip_many(tenant_id, keys)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="file not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid path") from e
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="eikon-variations.zip"'},
    )


@router.get("/variations/{variation_id}/file")
def variation_file(
    variation_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Sirve el PNG renderizado de una variación del tenant (vía el seam)."""
    settings = get_settings(request)
    storage = get_storage(request)
    tenant_id = user["tenant_id"]
    var = get_variation(settings.db_url, tenant_id, variation_id)
    if var is None:
        raise HTTPException(status_code=404, detail="variation not found")
    key = _seam_key(storage, tenant_id, var.get("output_path"))
    try:
        data = storage.open(tenant_id, key)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="file not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid path") from e
    return Response(
        content=data,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{Path(key).name}"'},
    )


@router.post("/downloads/batch/{batch_id}")
def downloads_batch_zip(
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Empaca todos los PNG persistidos para un batch del tenant (vía el seam)."""
    settings = get_settings(request)
    storage = get_storage(request)
    tenant_id = user["tenant_id"]

    if get_batch(settings.db_url, tenant_id, batch_id) is None:
        raise HTTPException(status_code=404, detail="batch not found")

    keys = [
        _seam_key(storage, tenant_id, var.get("output_path"))
        for var in list_variations(settings.db_url, tenant_id, batch_id=batch_id)
    ]
    if not keys:
        raise HTTPException(status_code=404, detail="batch has no files")

    return _zip_response(storage, tenant_id, keys)


@router.post("/downloads/zip")
def downloads_zip(
    payload: ZipRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Empaca los PNG de varias variaciones del tenant en un único ZIP.

    IDs duplicados en la lista se deduplicán (manteniendo el primer orden).
    """
    settings = get_settings(request)
    storage = get_storage(request)
    tenant_id = user["tenant_id"]

    # Deduplicar IDs preservando el orden de aparición.
    unique_ids: list[int] = list(dict.fromkeys(payload.ids))

    keys: list[str] = []
    for var_id in unique_ids:
        var = get_variation(settings.db_url, tenant_id, var_id)
        if var is None:
            raise HTTPException(status_code=404, detail=f"variation {var_id} not found")
        keys.append(_seam_key(storage, tenant_id, var.get("output_path")))

    return _zip_response(storage, tenant_id, keys)
