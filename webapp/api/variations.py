"""Router de variaciones: borrado individual y en lote."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, Depends, Request

from webapp.storage import delete_variation, delete_variations

from .deps import current_user, get_settings, get_storage
from .schemas import DeleteVariationsRequest

router = APIRouter(prefix="/api/v1", tags=["variations"])


@router.delete("/variations/{variation_id}", status_code=204)
def delete_variation_endpoint(
    variation_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> None:
    """Borra una variación individual del tenant. Retorna 204 sin importar si existía (idempotente)."""
    settings = get_settings(request)
    storage = get_storage(request)
    tenant_id = user["tenant_id"]
    # DELETE idempotente: 204 aunque la variación no existiera / no sea del tenant.
    with contextlib.suppress(KeyError):
        delete_variation(settings.db_url, tenant_id, variation_id, storage=storage)


@router.post("/variations/delete")
def delete_variations_endpoint(
    payload: DeleteVariationsRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, int]:
    """Borra múltiples variaciones del tenant en lote.

    Ignora las que no pertenecen al tenant o no existen.
    """
    settings = get_settings(request)
    storage = get_storage(request)
    tenant_id = user["tenant_id"]
    deleted = delete_variations(settings.db_url, tenant_id, payload.ids, storage=storage)
    return {"deleted": deleted}
