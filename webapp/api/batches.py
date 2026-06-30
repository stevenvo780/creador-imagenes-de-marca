"""Router de batches: encola renders combinatorios, status, SSE y variaciones.

El batch se encola vía webapp.jobs.enqueue_batch; el WorkerPool (arrancado en
el lifespan de la app) lo procesa: planifica, renderiza con Playwright, rankea y
persiste variaciones. Todo scoped por tenant.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from eikon_core.combinatorial import (
    CombinationSpec,
    plan_combinations,
    split_spec_by_asset_type,
)
from eikon_core.constants import ROOT
from webapp.jobs import enqueue_batch, get_worker, job_events
from webapp.storage import get_batch, get_brand, list_variations

from .deps import current_user, get_axes_config, get_settings
from .schemas import BatchCreate
from .serializers import batch_to_dict, variation_to_dict

router = APIRouter(prefix="/api/v1/batches", tags=["batches"])

_ASSET_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,60}$")


# Tipos de asset válidos derivados de config/taxonomy.json (fuente de verdad del motor).
# Se cargan una sola vez al importar; si el archivo no existe, se usa un set vacío
# y la validación posterior rechazará todos los tipos.
def _load_valid_asset_types() -> frozenset[str]:
    taxonomy_path = ROOT / "config" / "taxonomy.json"
    try:
        data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        types: set[str] = set()
        for family in data.get("families", {}).values():
            for category in family.get("categories", {}).values():
                for t in category.get("types", []):
                    name = t.get("name")
                    if name:
                        types.add(name)
        return frozenset(types)
    except (OSError, json.JSONDecodeError, AttributeError):
        return frozenset()


_VALID_ASSET_TYPES: frozenset[str] = _load_valid_asset_types()


def _validate_asset_types(asset_types: list[str]) -> list[str]:
    """Valida que cada asset_type sea un tipo registrado en taxonomy.json."""
    if not asset_types:
        return ["isotipo"]
    for name in asset_types:
        if not _ASSET_TYPE_RE.match(name):
            raise HTTPException(status_code=422, detail=f"asset_type inválido: {name!r}")
        if _VALID_ASSET_TYPES and name not in _VALID_ASSET_TYPES:
            raise HTTPException(status_code=422, detail=f"asset_type desconocido: {name!r}")
    return asset_types


@router.post("", status_code=202)
async def create_batch_endpoint(
    payload: BatchCreate,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Encola un batch combinatorio para un brand del tenant.

    Valida pertenencia del brand, asset_types, ejes (fixed/permuted) y la
    factibilidad del plan (count <= combinaciones distintas) antes de encolar,
    devolviendo 422 ante entradas inválidas en vez de fallar de forma asíncrona.
    """
    settings = get_settings(request)
    db = settings.sqlite_path
    tenant_id = user["tenant_id"]

    brand = get_brand(db, tenant_id, payload.brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="brand not found")

    asset_types = _validate_asset_types(payload.asset_types)

    cfg = get_axes_config(request)
    # Ejes permutados deben existir en el catálogo.
    for axis_name in payload.permuted:
        if cfg.get_axis(axis_name) is None:
            raise HTTPException(status_code=422, detail=f"eje permutado desconocido: {axis_name!r}")
    # Valores fijos deben ser opciones válidas de sus ejes.
    try:
        cfg.validate_combination(payload.fixed)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    spec = CombinationSpec(
        brand=str(brand["slug"]),
        asset_types=asset_types,
        fixed=dict(payload.fixed),
        permuted=list(payload.permuted),
        count=payload.count,
        seed_salt=payload.seed_salt,
    )
    axes_dict = {name: axis.option_names() for name, axis in cfg.axes.items()}
    try:
        for spec_for_type in split_spec_by_asset_type(
            spec,
            default_asset_type="isotipo",
        ):
            plan_combinations(spec_for_type, axes_dict)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    batch = await enqueue_batch(db, tenant_id, payload.brand_id, spec, payload.count)

    # El worker rastrea el progreso de cada batch en _pending_batches; el poll_loop
    # lo siembra al descubrir batches 'pending'. Como enqueue_batch ya encoló el
    # batch directamente (worker activo), pre-registramos su entrada de progreso
    # aquí: (1) evita el KeyError cuando _render_and_rank actualiza 'rendered', y
    # (2) impide que el poll_loop lo reencole (doble-dispatch). Es race-free: el
    # await de queue.put no cede el loop hasta que este handler retorna.
    worker = get_worker()
    if worker is not None:
        worker._pending_batches.setdefault(
            int(batch["id"]), {"rendered": 0, "ranked": 0, "status": "queued"}
        )

    return batch_to_dict(batch)


@router.get("/{batch_id}")
def get_batch_endpoint(
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Devuelve el status (y counts) de un batch del tenant."""
    settings = get_settings(request)
    row = get_batch(settings.sqlite_path, user["tenant_id"], batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return batch_to_dict(row)


@router.get("/{batch_id}/variations")
def batch_variations_endpoint(
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Lista las variaciones rankeadas de un batch (mayor score primero).

    Devuelve tanto "variations" (clave canónica) como "items" (alias legacy).
    """
    settings = get_settings(request)
    tenant_id = user["tenant_id"]
    if get_batch(settings.sqlite_path, tenant_id, batch_id) is None:
        raise HTTPException(status_code=404, detail="batch not found")
    rows = list_variations(settings.sqlite_path, tenant_id, batch_id=batch_id)
    # NULLs al final; score descendente para los que tienen valor.
    rows.sort(
        key=lambda r: (r.get("score") is None, -(r.get("score") or 0.0)),
    )
    serialized = [variation_to_dict(r) for r in rows]
    return {"variations": serialized, "items": serialized}


@router.get("/{batch_id}/events")
async def batch_events_endpoint(
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> StreamingResponse:
    """Stream SSE con el progreso del batch (started/progress/completed/error)."""
    settings = get_settings(request)
    # Scoping: solo el dueño del batch puede suscribirse a sus eventos.
    if get_batch(settings.sqlite_path, user["tenant_id"], batch_id) is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return StreamingResponse(
        job_events(batch_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
