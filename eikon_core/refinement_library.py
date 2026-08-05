"""Catalogo verificable de salidas de la segunda capa de Eikon."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .refinement import RefinementError

REQUIRED_METADATA_FIELDS = {
    "source_path",
    "output_path",
    "provider",
    "model",
    "source_sha256",
    "output_sha256",
    "brand_spec_digest",
    "asset_type",
    "gate",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_record_path(value: str, *, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _relative(path: Path, *, root: Path, base_dir: Path) -> str:
    resolved = path.resolve()
    for anchor in (root.resolve(), base_dir.resolve()):
        try:
            return str(resolved.relative_to(anchor))
        except ValueError:
            continue
    return str(resolved)


def build_refinement_library(root: Path, *, base_dir: Path) -> dict[str, Any]:
    """Indexa metadata existente y verifica los hashes de cada par before/after."""
    if not root.is_dir():
        raise RefinementError(f"No existe el directorio de muestras: {root}")

    entries: list[dict[str, Any]] = []
    for metadata_path in sorted(root.rglob("*.png.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RefinementError(f"Metadata invalida: {metadata_path}") from exc

        missing = sorted(REQUIRED_METADATA_FIELDS - metadata.keys())
        if missing:
            raise RefinementError(
                f"Metadata incompleta en {metadata_path}: faltan {', '.join(missing)}"
            )

        source_path = _resolve_record_path(metadata["source_path"], base_dir=base_dir)
        output_path = _resolve_record_path(metadata["output_path"], base_dir=base_dir)
        for label, path, expected in (
            ("source", source_path, metadata["source_sha256"]),
            ("output", output_path, metadata["output_sha256"]),
        ):
            if not path.is_file():
                raise RefinementError(f"Falta {label} referenciado por {metadata_path}: {path}")
            actual = _sha256(path)
            if actual != expected:
                raise RefinementError(
                    f"Hash invalido para {label} en {metadata_path}: {actual} != {expected}"
                )

        gate = metadata["gate"]
        entries.append(
            {
                "source": _relative(source_path, root=root, base_dir=base_dir),
                "output": _relative(output_path, root=root, base_dir=base_dir),
                "metadata": _relative(metadata_path, root=root, base_dir=base_dir),
                "source_sha256": metadata["source_sha256"],
                "output_sha256": metadata["output_sha256"],
                "brand_spec_digest": metadata["brand_spec_digest"],
                "asset_type": metadata["asset_type"],
                "provider": metadata["provider"],
                "model": metadata["model"],
                "gate": {
                    "structure_score": gate["structure_score"],
                    "palette_adherence": gate["palette_adherence"],
                    "passed": gate["passed"],
                },
            }
        )

    if not entries:
        raise RefinementError(f"No se encontraron metadatas de refinado en {root}")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "asset_count": len(entries),
        "providers": sorted({entry["provider"] for entry in entries}),
        "brand_spec_digests": sorted({entry["brand_spec_digest"] for entry in entries}),
        "assets": entries,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_refinement_library(
    root: Path, *, base_dir: Path, output_path: Path | None = None
) -> Path:
    """Persiste el catalogo de forma atomica dentro del lote."""
    destination = output_path or root / "_library.json"
    payload = build_refinement_library(root, base_dir=base_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return destination
