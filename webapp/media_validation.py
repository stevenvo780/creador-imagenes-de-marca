"""Valida bytes originales; normaliza exclusivamente la miniatura privada."""

from __future__ import annotations

import hashlib
import io
import warnings
from typing import Any

from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_PROVENANCE_BYTES = 16 * 1024


def validate_image(content: bytes, expected_width: int, expected_height: int) -> dict[str, Any]:
    """Verifica formato, cabecera y decodificación completa sin reescribir originales."""
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Tamaño de imagen fuera de los límites")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG"}:
                    raise ValueError("Formato de imagen no admitido")
                mime = "image/png" if image.format == "PNG" else "image/jpeg"
                width, height = image.size
                if width * height > 40_000_000 or not all(
                    256 <= v <= 8192 for v in (width, height)
                ):
                    raise ValueError("Dimensiones fuera de los límites")
                if (width, height) != (expected_width, expected_height):
                    raise ValueError("Dimensiones diferentes del encargo")
                image.verify()
            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
                orientation = decoded.getexif().get(274, 1)
                if not isinstance(orientation, int) or orientation not in range(1, 9):
                    raise ValueError("Orientación EXIF inválida")
                normalized = ImageOps.exif_transpose(decoded).convert("RGBA")
                normalized.thumbnail((512, 512), Image.Resampling.LANCZOS)
                # Una imagen nueva excluye EXIF, ICC, comentarios y metadata del original.
                thumbnail = Image.new("RGBA", normalized.size)
                thumbnail.paste(normalized)
                stream = io.BytesIO()
                thumbnail.save(stream, "PNG")
    except (
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("Imagen dañada o insegura") from error
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "mime": mime,
        "width": width,
        "height": height,
        "byte_size": len(content),
        "thumbnail_bytes": stream.getvalue(),
    }
