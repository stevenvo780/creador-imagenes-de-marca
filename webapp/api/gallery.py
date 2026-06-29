"""Router de galería: listar variaciones de un brand y seleccionarlas."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from webapp.storage import get_brand, list_variations, select_variation

from .deps import current_user, get_settings
from .schemas import SelectRequest
from .serializers import variation_to_dict

router = APIRouter(prefix="/api/v1/gallery", tags=["gallery"])


def _gallery_items(
    request: Request,
    user: dict[str, Any],
    brand_id: int | None,
) -> dict[str, Any]:
    """Lista variaciones del tenant, opcionalmente filtradas por brand_id."""
    settings = get_settings(request)
    tenant_id = user["tenant_id"]
    if brand_id is not None and get_brand(settings.sqlite_path, tenant_id, brand_id) is None:
        raise HTTPException(status_code=404, detail="brand not found")
    rows = list_variations(settings.sqlite_path, tenant_id, brand_id=brand_id)
    rows.sort(key=lambda r: (r.get("score") or 0.0), reverse=True)
    return {"items": [variation_to_dict(r) for r in rows]}


@router.get("")
def gallery_list(
    request: Request,
    brand_id: int | None = Query(default=None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Lista variaciones del tenant, opcionalmente filtradas por brand_id."""
    return _gallery_items(request, user, brand_id)


@router.get("/{brand_id}")
def gallery_list_by_brand(
    brand_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Alias path-param para e2e y clientes que prefieren /gallery/{brand_id}."""
    return _gallery_items(request, user, brand_id)


@router.post("/select")
def gallery_select(
    payload: SelectRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Marca/desmarca una variación del tenant como seleccionada."""
    settings = get_settings(request)
    try:
        select_variation(
            settings.sqlite_path, user["tenant_id"], payload.variation_id, payload.selected
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="variation not found") from e
    return {"variation_id": payload.variation_id, "selected": payload.selected}
