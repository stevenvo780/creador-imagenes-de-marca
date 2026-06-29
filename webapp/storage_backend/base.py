"""Protocolo de abstracción para almacenamiento multi-tenant (local, GCS, etc.)"""
from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """Interfaz de almacenamiento backend: guardar/abrir/listar archivos por tenant.

    Cada tenant tiene su propia carpeta de almacenamiento. Los paths relativos
    se validan contra path traversal.
    """

    def save(self, tenant_id: int, relative_path: str, content: bytes) -> str:
        """Guarda contenido en relative_path.

        Args:
            tenant_id: ID del tenant (scope de seguridad)
            relative_path: ruta relativa dentro de la carpeta del tenant
                          (ej: "marcas/prizma/logo.png")
            content: bytes a guardar

        Returns:
            Ruta absoluta o URI del archivo guardado

        Raises:
            ValueError: si relative_path contiene path traversal
        """
        ...

    def open(self, tenant_id: int, relative_path: str) -> bytes:
        """Lee contenido de un archivo.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa dentro de la carpeta del tenant

        Returns:
            Contenido del archivo en bytes

        Raises:
            FileNotFoundError: si el archivo no existe
            ValueError: si relative_path contiene path traversal
        """
        ...

    def url_for(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve URL (local o CDN) para servir el archivo.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa dentro de la carpeta del tenant

        Returns:
            URL para descargar el archivo

        Raises:
            ValueError: si relative_path contiene path traversal
        """
        ...

    def list_files(self, tenant_id: int, prefix: str = "") -> list[str]:
        """Lista archivos en la carpeta del tenant, opcionalmente filtrado por prefix.

        Args:
            tenant_id: ID del tenant
            prefix: prefijo de búsqueda dentro de la carpeta del tenant
                   (ej: "marcas/prizma/")

        Returns:
            Lista de rutas relativas (ej: ["marcas/prizma/logo.png", ...])
        """
        ...

    def zip_many(self, tenant_id: int, relative_paths: list[str]) -> bytes:
        """Empacar múltiples archivos en un ZIP.

        Args:
            tenant_id: ID del tenant
            relative_paths: lista de rutas relativas a incluir

        Returns:
            Contenido del ZIP en bytes

        Raises:
            FileNotFoundError: si algún archivo no existe
            ValueError: si algún path contiene path traversal
        """
        ...
