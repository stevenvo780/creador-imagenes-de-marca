"""Router del wizard: catálogo de ejes combinatorios y brands disponibles.

Alimenta el formulario del SPA: qué ejes existen, sus opciones/labels, y los
brands del tenant que pueden usarse como base de un batch.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from webapp.storage import list_brands

from .deps import current_user, get_axes_config, get_settings
from .serializers import brand_to_dict

router = APIRouter(prefix="/api/v1/wizard", tags=["wizard"])


@router.get("/axes")
def wizard_axes(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Catálogo de ejes: nombre, label, tipo y opciones (name + descripción)."""
    cfg = get_axes_config(request)
    axes: list[dict[str, Any]] = []
    for name in cfg.axis_names():
        axis = cfg.axes[name]
        axes.append(
            {
                "name": axis.name,
                "label": axis.label or axis.name,
                "type": axis.axis_type,
                "options": [
                    {
                        "name": opt.name,
                        "label": opt.description or opt.name,
                        "description": opt.description,
                    }
                    for opt in axis.options
                ],
            }
        )
    return {"axes": axes}


@router.get("/brands")
def wizard_brands(
    request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    """Brands del tenant disponibles como base de un batch."""
    settings = get_settings(request)
    rows = list_brands(settings.sqlite_path, user["tenant_id"])
    return {"items": [brand_to_dict(r) for r in rows]}
