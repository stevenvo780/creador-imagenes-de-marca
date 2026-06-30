"""Router de galería: listar variaciones de un brand y seleccionarlas."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from webapp.storage import get_brand, list_variations, select_variation

from .deps import current_user, get_settings
from .schemas import _SQLITE_INT_MAX, SelectRequest
from .serializers import variation_to_dict

router = APIRouter(prefix="/api/v1/gallery", tags=["gallery"])


def _sort_rows(rows: list[dict[str, Any]], order: str) -> list[dict[str, Any]]:
    """Ordena variaciones según el parámetro order.

    - "calidad": score DESC, NULLs al final (score None → -inf efectivo).
    - "recientes": created_at DESC.
    """
    if order == "recientes":
        return sorted(rows, key=lambda r: r.get("created_at") or 0, reverse=True)
    # "calidad" (default): score DESC, NULLs al final.
    return sorted(
        rows,
        key=lambda r: (r.get("score") is None, -(r.get("score") or 0.0)),
    )


def _gallery_items(
    request: Request,
    user: dict[str, Any],
    brand_id: int | None,
    batch_id: int | None = None,
    order: str = "calidad",
) -> dict[str, Any]:
    """Lista variaciones del tenant con filtros opcionales y ordenamiento server-side."""
    settings = get_settings(request)
    tenant_id = user["tenant_id"]
    if brand_id is not None and get_brand(settings.sqlite_path, tenant_id, brand_id) is None:
        raise HTTPException(status_code=404, detail="brand not found")
    rows = list_variations(settings.sqlite_path, tenant_id, brand_id=brand_id, batch_id=batch_id)
    rows = _sort_rows(rows, order)
    return {"items": [variation_to_dict(r) for r in rows]}


@router.get("")
def gallery_list(
    request: Request,
    brand_id: int | None = Query(default=None, ge=1, le=_SQLITE_INT_MAX),
    batch_id: int | None = Query(default=None, ge=1, le=_SQLITE_INT_MAX),
    order: Literal["calidad", "recientes"] = Query(default="calidad"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Lista variaciones del tenant con orden server-side y filtros opcionales.

    - order=calidad (default): score descendente, NULLs al final.
    - order=recientes: created_at descendente.
    - brand_id: filtra por brand.
    - batch_id: filtra por batch.
    """
    return _gallery_items(request, user, brand_id, batch_id=batch_id, order=order)


@router.get("/{brand_id}")
def gallery_list_by_brand(
    brand_id: int,
    request: Request,
    order: Literal["calidad", "recientes"] = Query(default="calidad"),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Alias path-param para e2e y clientes que prefieren /gallery/{brand_id}."""
    return _gallery_items(request, user, brand_id, order=order)


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
