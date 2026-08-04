"""Pipeline Eikón mockup -> refinado visual con controles de marca."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from .brand_spec import BrandSpec
from .refinement_providers import RefinementProvider


class RefinementError(RuntimeError):
    """El refinado no superó validación o no pudo persistirse."""


@dataclass(frozen=True)
class QualityGate:
    structure_score: float
    palette_adherence: float
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RefinementResult:
    source_path: str
    output_path: str
    metadata_path: str
    provider: str
    model: str
    source_sha256: str
    output_sha256: str
    brand_spec_digest: str
    api_size: str
    gate: QualityGate
    request_id: str | None = None


def build_refinement_prompt(spec: BrandSpec, asset_type: str) -> str:
    """Prompt estructurado: permite pulido, prohíbe rediseñar la maqueta."""
    context = json.dumps(
        spec.prompt_context(asset_type), ensure_ascii=False, sort_keys=True, indent=2
    )
    return f"""Edit the supplied Eikon brand mockup into a production-quality final image.

NON-NEGOTIABLE INVARIANTS:
- Preserve the exact canvas composition, hierarchy, spacing, logo geometry and crop.
- Preserve all readable text verbatim. Do not translate, rewrite, add or remove words.
- Use only the supplied brand palette and typography character.
- Do not add new logos, icons, watermarks, signatures, badges or calls to action.
- Improve only finish quality: antialiasing, subtle material depth, lighting coherence,
  edge definition, texture restraint and professional color balance.
- Keep this recognizably the same asset, not a redesign.

CANONICAL EIKON BRAND SPEC:
{context}

Return a single flat PNG with no surrounding frame or explanation."""


def gpt_edit_size(width: int, height: int) -> str:
    """Tamaño arbitrario válido para GPT Image 2, preservando el aspect ratio."""
    if width < 1 or height < 1:
        raise ValueError("Las dimensiones deben ser positivas")
    ratio = width / height
    if ratio > 3 or ratio < 1 / 3:
        raise ValueError("GPT Image admite aspect ratios entre 1:3 y 3:1")

    max_edge = 3840.0
    min_pixels = 655_360.0
    max_pixels = 8_294_400.0
    scale = min(1.0, max_edge / max(width, height), math.sqrt(max_pixels / (width * height)))
    if width * height * scale * scale < min_pixels:
        scale = math.sqrt(min_pixels / (width * height))
    scaled_w = min(3840, max(16, round(width * scale / 16) * 16))
    scaled_h = min(3840, max(16, round(height * scale / 16) * 16))
    if not 655_360 <= scaled_w * scaled_h <= 8_294_400:
        raise ValueError("No se pudo calcular un tamaño GPT Image válido")
    return f"{scaled_w}x{scaled_h}"


def _open_rgb(data: bytes, *, label: str) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(data)) as opened:
            return opened.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise RefinementError(f"{label} no es una imagen válida") from exc


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]


def evaluate_quality(
    source: Image.Image,
    candidate: Image.Image,
    spec: BrandSpec,
    *,
    min_structure: float = 0.62,
    min_palette: float = 0.12,
) -> QualityGate:
    """Gate conservador que evita rediseños y deriva evidente de paleta."""
    resampling = Image.Resampling.LANCZOS
    source_small = np.asarray(source.convert("L").resize((64, 64), resampling), dtype=np.float32)
    candidate_small = np.asarray(
        candidate.convert("L").resize((64, 64), resampling), dtype=np.float32
    )
    structure = max(0.0, 1.0 - float(np.mean(np.abs(source_small - candidate_small))) / 255.0)

    candidate_palette = np.asarray(
        candidate.resize((96, 96), resampling), dtype=np.int32
    ).reshape((-1, 3))
    brand_colors = np.asarray([_rgb(value) for value in spec.palette.values()], dtype=np.int32)
    distance = np.sqrt(
        np.sum((candidate_palette[:, None, :] - brand_colors[None, :, :]) ** 2, axis=2)
    )
    palette = float(np.mean(np.min(distance, axis=1) <= 72.0))
    reasons: list[str] = []
    if structure < min_structure:
        reasons.append(f"structure_score {structure:.3f} < {min_structure:.3f}")
    if palette < min_palette:
        reasons.append(f"palette_adherence {palette:.3f} < {min_palette:.3f}")
    return QualityGate(
        structure_score=round(structure, 6),
        palette_adherence=round(palette, 6),
        passed=not reasons,
        reasons=tuple(reasons),
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def refine_asset(
    *,
    source_path: Path,
    output_path: Path,
    spec: BrandSpec,
    asset_type: str,
    provider: RefinementProvider,
    quality: str = "high",
    overwrite: bool = False,
) -> RefinementResult:
    """Ejecuta la segunda capa, valida y persiste PNG + metadata atómicamente."""
    if not source_path.is_file():
        raise RefinementError(f"No existe la maqueta: {source_path}")
    if output_path.exists() and not overwrite:
        raise RefinementError(f"El destino ya existe (use --overwrite): {output_path}")
    if source_path.resolve() == output_path.resolve():
        raise RefinementError("La salida no puede sobrescribir la maqueta fuente")

    source_bytes = source_path.read_bytes()
    source_image = _open_rgb(source_bytes, label="La maqueta")
    api_size = gpt_edit_size(*source_image.size)
    provider_result = provider.refine(
        source_bytes,
        build_refinement_prompt(spec, asset_type),
        size=api_size,
        quality=quality,
    )
    candidate = _open_rgb(provider_result.image_bytes, label="La respuesta del proveedor")
    if candidate.size != source_image.size:
        candidate = candidate.resize(source_image.size, Image.Resampling.LANCZOS)

    gate = evaluate_quality(source_image, candidate, spec)
    if not gate.passed:
        raise RefinementError("La imagen fue rechazada por quality gates: " + "; ".join(gate.reasons))

    normalized = io.BytesIO()
    candidate.save(normalized, format="PNG", optimize=True)
    output_bytes = normalized.getvalue()
    metadata_path = output_path.with_suffix(output_path.suffix + ".json")
    result = RefinementResult(
        source_path=str(source_path),
        output_path=str(output_path),
        metadata_path=str(metadata_path),
        provider=provider_result.provider,
        model=provider_result.model,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        brand_spec_digest=spec.digest,
        api_size=api_size,
        gate=gate,
        request_id=provider_result.request_id,
    )
    metadata: dict[str, Any] = asdict(result)
    metadata["asset_type"] = asset_type
    metadata["quality"] = quality

    _atomic_write(output_path, output_bytes)
    try:
        _atomic_write(
            metadata_path,
            (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return result
