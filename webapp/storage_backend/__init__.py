"""Abstracción de almacenamiento multi-tenant para eikon.

Soporta múltiples backends: local (disco), GCS (Google Cloud Storage).

Selección automática vía variable de entorno:
- ``GCS_BUCKET`` definida → GCSStorage(bucket_name=GCS_BUCKET)
- ``GCS_BUCKET`` ausente  → LocalStorage(base_dir)
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import StorageBackend
from .gcs import GCSStorage
from .local import LocalStorage

__all__ = ["GCSStorage", "LocalStorage", "StorageBackend", "get_storage"]


def get_storage(base_dir: str | Path | None = None) -> GCSStorage | LocalStorage:
    """Factory de backend de almacenamiento multi-tenant.

    Lee la variable de entorno ``GCS_BUCKET``:
    - Si está definida, devuelve ``GCSStorage(bucket_name=GCS_BUCKET)``.
      Usa Application Default Credentials (ADC) — funciona en Cloud Run sin
      configuración adicional.
    - Si no está definida, devuelve ``LocalStorage(base_dir)`` para
      almacenamiento en disco (dev / SQLite).

    Args:
        base_dir: carpeta base para LocalStorage.  Ignorado en modo GCS.
                  Por defecto ``"output"`` (directorio relativo al cwd).

    Returns:
        Instancia que cumple el Protocol ``StorageBackend``.
    """
    bucket = os.environ.get("GCS_BUCKET")
    if bucket:
        return GCSStorage(bucket_name=bucket)
    return LocalStorage(base_dir=Path(base_dir) if base_dir is not None else Path("output"))
