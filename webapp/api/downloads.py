"""Router de descargas: servir el PNG de una variación y empacar ZIPs.

Las variaciones se resuelven scoped por tenant; sus output_path apuntan al árbol
de salida del worker. Se valida que cada ruta quede dentro de output_root (anti
path-traversal) antes de servir o empacar.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from webapp.services.eikon_runner import safe_relative_path
from webapp.storage import get_batch, get_variation, list_variations

from .deps import current_user, get_output_root, get_settings
from .schemas import ZipRequest

router = APIRouter(prefix="/api/v1", tags=["downloads"])


def _resolve_variation_file(output_root: Path, output_path: str | None) -> Path:
    """Valida que output_path exista y quede dentro de output_root.

    Lanza HTTPException 404 si falta el path o el archivo, y 400 si escapa del
    árbol de salida (path-traversal).
    """
    if not output_path:
        raise HTTPException(status_code=404, detail="variation has no file")
    try:
        absolute = safe_relative_path(output_root, Path(output_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid path") from e
    if not absolute.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return absolute


def _zip_response(files: list[tuple[Path, str]]) -> Response:
    """Construye un ZIP en memoria a partir de rutas ya validadas."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for absolute, arcname in files:
            zf.write(absolute, arcname=arcname)
    data = buffer.getvalue()

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
) -> FileResponse:
    """Sirve el PNG renderizado de una variación del tenant."""
    settings = get_settings(request)
    output_root = get_output_root(request)
    var = get_variation(settings.sqlite_path, user["tenant_id"], variation_id)
    if var is None:
        raise HTTPException(status_code=404, detail="variation not found")
    absolute = _resolve_variation_file(output_root, var.get("output_path"))
    return FileResponse(str(absolute), media_type="image/png", filename=absolute.name)


@router.post("/downloads/batch/{batch_id}")
def downloads_batch_zip(
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Empaca todos los PNG persistidos para un batch del tenant."""
    settings = get_settings(request)
    output_root = get_output_root(request)
    tenant_id = user["tenant_id"]

    if get_batch(settings.sqlite_path, tenant_id, batch_id) is None:
        raise HTTPException(status_code=404, detail="batch not found")

    files: list[tuple[Path, str]] = []
    for var in list_variations(settings.sqlite_path, tenant_id, batch_id=batch_id):
        absolute = _resolve_variation_file(output_root, var.get("output_path"))
        arcname = str(absolute.relative_to(output_root.resolve()))
        files.append((absolute, arcname))

    if not files:
        raise HTTPException(status_code=404, detail="batch has no files")

    return _zip_response(files)


@router.post("/downloads/zip")
def downloads_zip(
    payload: ZipRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> Response:
    """Empaca los PNG de varias variaciones del tenant en un único ZIP."""
    settings = get_settings(request)
    output_root = get_output_root(request)
    tenant_id = user["tenant_id"]

    files: list[tuple[Path, str]] = []
    for var_id in payload.ids:
        var = get_variation(settings.sqlite_path, tenant_id, var_id)
        if var is None:
            raise HTTPException(status_code=404, detail=f"variation {var_id} not found")
        absolute = _resolve_variation_file(output_root, var.get("output_path"))
        # arcname relativo a output_root: conserva marca/categoría/tipo sin colisiones.
        arcname = str(absolute.relative_to(output_root.resolve()))
        files.append((absolute, arcname))

    return _zip_response(files)
