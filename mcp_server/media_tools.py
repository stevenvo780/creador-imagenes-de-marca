"""Cliente HTTP de encargos y medios; importa bytes del equipo del cliente MCP."""

from __future__ import annotations

import io
import json
import os
import re
import stat
import warnings
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
_ERRORS = {
    401: ("unauthorized", "Clave inválida, caducada o revocada."),
    403: ("forbidden", "La clave no tiene el permiso requerido."),
    404: ("not_found", "Recurso no disponible para esta empresa."),
    409: ("conflict", "Conflicto: revise encargo, identidad o idempotencia."),
    413: ("too_large", "La imagen excede el límite permitido."),
    422: ("invalid_request", "Revise los campos y las dimensiones del encargo."),
}


def failure(code: str, message: str, status: int | None = None) -> dict[str, Any]:
    """Nunca incluir excepciones, cuerpos remotos, tokens ni rutas privadas."""
    result: dict[str, Any] = {"success": False, "error_code": code, "error": message}
    if status is not None:
        result["http_status"] = status
    return result


class MediaTools:
    """Unidad inyectable; sólo envía Authorization a la base configurada."""

    def __init__(self, base_url: str, api_key: str, client: httpx.AsyncClient):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = client

    def _configured(self) -> bool:
        try:
            url = httpx.URL(self.base_url)
        except (httpx.InvalidURL, ValueError):
            return False
        secure = url.scheme == "https" or (
            url.scheme == "http" and url.host in {"localhost", "127.0.0.1", "::1"}
        )
        return bool(
            secure
            and url.host
            and not url.userinfo
            and not url.query
            and not url.fragment
            and url.path in {"", "/"}
            and re.fullmatch(r"[A-Za-z0-9._~-]+", self.api_key)
        )

    async def _request(
        self, method: str, route: str, resource: str, **kwargs: Any
    ) -> dict[str, Any]:
        if not self._configured():
            return failure(
                "configuration_error",
                "Configure una base HTTPS y una clave privada válida; HTTP sólo en localhost.",
            )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        headers.update(kwargs.pop("headers", {}))
        try:
            response = await self.client.request(
                method,
                f"{self.base_url}{route}",
                headers=headers,
                timeout=30.0,
                follow_redirects=False,
                **kwargs,
            )
        except httpx.HTTPError:
            return failure("connection_error", "No se pudo contactar con Eikón.")
        if 300 <= response.status_code < 400:
            return failure(
                "redirect_refused",
                "Eikón devolvió una redirección; revise la base configurada.",
                response.status_code,
            )
        if not 200 <= response.status_code < 300:
            code, message = _ERRORS.get(
                response.status_code, ("backend_error", "Eikón no pudo completar la solicitud.")
            )
            return failure(code, message, response.status_code)
        try:
            data = response.json()
        except ValueError:
            return failure("invalid_response", "Respuesta JSON inválida de Eikón.")
        if not isinstance(data, dict):
            return failure("invalid_response", "Formato de respuesta inválido de Eikón.")
        return {"success": True, resource: data}

    @staticmethod
    def _pagination(cursor: int | None, limit: int | None) -> dict[str, int]:
        params = {}
        for name, value, low, high in (("cursor", cursor, 0, 2**63 - 1), ("limit", limit, 1, 100)):
            if value is not None:
                if type(value) is not int or not low <= value <= high:
                    raise ValueError("paginación inválida")
                params[name] = value
        return params

    async def list_projects(
        self, cursor: int | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        try:
            params = self._pagination(cursor, limit)
        except ValueError:
            return failure("invalid_request", "Cursor o límite inválidos.")
        return await self._request("GET", "/api/v1/projects", "projects", params=params)

    async def create_project(self, name: str, slug: str, description: str = "") -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/projects",
            "project",
            json={
                "name": name,
                "slug": slug,
                "description": description,
            },
        )

    async def get_brand_brief(self, brand_id: int) -> dict[str, Any]:
        if type(brand_id) is not int or brand_id < 1:
            return failure("invalid_request", "brand_id debe ser un entero positivo.")
        return await self._request("GET", f"/api/v1/brands/{brand_id}/brief", "brand_brief")

    async def create_generation_brief(
        self, brand_id: int, prompt: str, width: int, height: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/generation-briefs",
            "brief",
            json={
                "brand_id": brand_id,
                "prompt": prompt,
                "width": width,
                "height": height,
            },
        )

    async def list_media(
        self,
        project_id: int | None = None,
        brand_id: int | None = None,
        status: str | None = None,
        cursor: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        try:
            pagination = self._pagination(cursor, limit)
        except ValueError:
            return failure("invalid_request", "Cursor o límite inválidos.")
        params = {
            key: value
            for key, value in {
                "project_id": project_id,
                "brand_id": brand_id,
                "status": status,
            }.items()
            if value is not None
        }
        return await self._request("GET", "/api/v1/media", "media", params={**params, **pagination})

    @staticmethod
    def _read_image(file_path: str) -> tuple[bytes, str, str]:
        # O_NOFOLLOW evita symlinks finales y O_NONBLOCK evita bloquearse en FIFO.
        fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                raise ValueError("archivo inválido")
            content = stream.read(MAX_BYTES + 1)
        if not content or len(content) > MAX_BYTES:
            raise ValueError("tamaño inválido")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                fmt = image.format
                width, height = image.size
                if (
                    fmt not in {"PNG", "JPEG"}
                    or not (256 <= width <= 8192 and 256 <= height <= 8192)
                    or width * height > MAX_PIXELS
                ):
                    raise ValueError("imagen inválida")
                image.verify()
            # verify() comprueba estructura; load() también exige datos decodificables.
            with Image.open(io.BytesIO(content)) as image:
                image.load()
        return (
            (content, "image.png", "image/png")
            if fmt == "PNG"
            else (content, "image.jpg", "image/jpeg")
        )

    async def import_image(
        self,
        brief_id: int,
        file_path: str,
        idempotency_key: str,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._configured():
            return failure(
                "configuration_error",
                "Configure una base HTTPS y una clave privada válida; HTTP sólo en localhost.",
            )
        if (
            type(brief_id) is not int
            or brief_id < 1
            or not isinstance(idempotency_key, str)
            or not re.fullmatch(r"[\x21-\x7e]{1,128}", idempotency_key)
        ):
            return failure("invalid_request", "Encargo o clave de idempotencia inválidos.")
        try:
            if provenance is not None and not isinstance(provenance, dict):
                raise ValueError("metadata inválida")
            metadata = json.dumps(provenance or {}, allow_nan=False)
            if len(metadata.encode()) > 16000:
                raise ValueError("metadata excesiva")
        except (TypeError, ValueError):
            return failure("invalid_request", "Provenance debe ser un objeto JSON acotado.")
        try:
            content, filename, mime = self._read_image(file_path)
        except (
            OSError,
            ValueError,
            TypeError,
            UnidentifiedImageError,
            SyntaxError,  # Pillow verify() rechaza CRC PNG corrupto con esta excepción.
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ):
            return failure(
                "invalid_image",
                "Seleccione un archivo regular PNG/JPEG válido, máximo 20 MiB y 40 millones de píxeles, 256-8192 por eje.",
            )
        return await self._request(
            "POST",
            "/api/v1/media",
            "media",
            headers={"Idempotency-Key": idempotency_key},
            data={"brief_id": str(brief_id), "source": "codex", "provenance": metadata},
            files={"file": (filename, content, mime)},
        )
