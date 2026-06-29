"""Abstracción de almacenamiento multi-tenant para eikon.

Soporta múltiples backends: local (disco), GCS (Google Cloud Storage).
"""
from __future__ import annotations

from .base import StorageBackend
from .gcs import GCSStorage
from .local import LocalStorage

__all__ = ["GCSStorage", "LocalStorage", "StorageBackend"]
