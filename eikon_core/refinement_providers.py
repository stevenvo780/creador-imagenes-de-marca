"""Proveedores intercambiables para la segunda capa del pipeline de Eikón.

El proveedor OpenAI es *opt-in*: construirlo exige una clave y el CLI además
requiere un flag de gasto explícito. El proveedor local existe para tests,
demostraciones sin red y verificación del contrato; no se presenta como GPT.
"""

from __future__ import annotations

import base64
import io
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from PIL import Image, ImageEnhance, ImageFilter


class RefinementProviderError(RuntimeError):
    """El proveedor no pudo producir una imagen válida."""


@dataclass(frozen=True)
class ProviderResult:
    image_bytes: bytes
    provider: str
    model: str
    request_id: str | None = None


class RefinementProvider(Protocol):
    name: str
    model: str

    def refine(
        self,
        source_png: bytes,
        prompt: str,
        *,
        size: str,
        quality: str,
    ) -> ProviderResult:
        """Refina un PNG y devuelve bytes de imagen, sin escribir al disco."""


class LocalPreviewProvider:
    """Pulido determinista y offline para probar el pipeline sin simular GPT."""

    name = "local-preview"
    model = "pillow-deterministic-v1"

    def refine(
        self,
        source_png: bytes,
        prompt: str,
        *,
        size: str,
        quality: str,
    ) -> ProviderResult:
        del prompt, size, quality
        with Image.open(io.BytesIO(source_png)) as opened:
            image = opened.convert("RGB")
        image = image.filter(ImageFilter.UnsharpMask(radius=1.4, percent=115, threshold=3))
        image = ImageEnhance.Contrast(image).enhance(1.035)
        image = ImageEnhance.Color(image).enhance(1.045)
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return ProviderResult(
            image_bytes=output.getvalue(),
            provider=self.name,
            model=self.model,
        )


class OpenAIImageEditProvider:
    """Adaptador mínimo a ``POST /v1/images/edits`` para GPT Image."""

    name = "openai"
    TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-image-2",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 180.0,
        max_attempts: int = 3,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY no puede estar vacía")
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts debe estar entre 1 y 5")
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._client = client
        self._sleep = sleep

    def refine(
        self,
        source_png: bytes,
        prompt: str,
        *,
        size: str,
        quality: str,
    ) -> ProviderResult:
        files = {"image": ("eikon-mockup.png", source_png, "image/png")}
        data = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": "png",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        owned_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        try:
            response: httpx.Response | None = None
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = client.post(
                        f"{self._base_url}/images/edits",
                        headers=headers,
                        data=data,
                        files=files,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt == self._max_attempts:
                        raise RefinementProviderError(
                            "OpenAI Images no respondió tras los reintentos"
                        ) from exc
                    self._sleep(float(2 ** (attempt - 1)))
                    continue

                if response.status_code < 400:
                    break
                if (
                    response.status_code not in self.TRANSIENT_STATUS
                    or attempt == self._max_attempts
                ):
                    raise RefinementProviderError(self._safe_error(response))
                retry_after = response.headers.get("retry-after")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else float(
                    2 ** (attempt - 1)
                )
                self._sleep(min(delay, 20.0))

            if response is None:
                raise RefinementProviderError("OpenAI Images no devolvió respuesta")
            return self._decode_response(response)
        finally:
            if owned_client:
                client.close()

    def _decode_response(self, response: httpx.Response) -> ProviderResult:
        try:
            payload: Any = response.json()
            first = payload["data"][0]
            encoded = first["b64_json"]
            image_bytes = base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RefinementProviderError(
                "OpenAI Images devolvió una respuesta sin PNG base64 válido"
            ) from exc
        if not image_bytes:
            raise RefinementProviderError("OpenAI Images devolvió una imagen vacía")
        return ProviderResult(
            image_bytes=image_bytes,
            provider=self.name,
            model=self.model,
            request_id=response.headers.get("x-request-id"),
        )

    @staticmethod
    def _safe_error(response: httpx.Response) -> str:
        """Resume el error sin headers, request body, clave ni contenido sensible."""
        error_type = "unknown"
        error_code = "unknown"
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            if isinstance(error, dict):
                error_type = str(error.get("type") or "unknown")
                error_code = str(error.get("code") or "unknown")
        except ValueError:
            pass
        return (
            f"OpenAI Images rechazó la edición: HTTP {response.status_code} "
            f"type={error_type} code={error_code}"
        )
