"""Almacenamiento local en disco bajo output/tenants/<tenant_id>/ con seguridad anti path-traversal."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path


class LocalStorage:
    """Implementación de almacenamiento en disco local con scope por tenant.

    Archivos se guardan bajo:
        output/tenants/<tenant_id>/...

    Validación de seguridad: rechaza paths con "..", absolutos, o symlinks fuera del scope.
    """

    def __init__(self, base_dir: str | Path = "output"):
        """Inicializa LocalStorage.

        Args:
            base_dir: carpeta base donde vivirán los tenants (default: "output")
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_relative_path(self, relative_path: str) -> None:
        """Valida que relative_path no contenga path traversal o sea absoluto.

        Raises:
            ValueError: si el path es inseguro
        """
        if not relative_path:
            raise ValueError("relative_path no puede estar vacío")
        if relative_path.startswith("/"):
            raise ValueError("relative_path no puede ser absoluto")
        if ".." in relative_path.split("/"):
            raise ValueError("relative_path contiene '..' (path traversal prohibido)")
        if relative_path.startswith("~"):
            raise ValueError("relative_path no puede contener '~' (expansión de home prohibida)")

    def _get_tenant_dir(self, tenant_id: int) -> Path:
        """Devuelve la carpeta raíz del tenant."""
        return self.base_dir / "tenants" / str(tenant_id)

    def _get_full_path(self, tenant_id: int, relative_path: str) -> Path:
        """Devuelve la ruta completa validada.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa (validada)

        Returns:
            Path absoluto validado

        Raises:
            ValueError: si el path sale del scope del tenant
        """
        self._validate_relative_path(relative_path)
        tenant_dir = self._get_tenant_dir(tenant_id)
        full_path = (tenant_dir / relative_path).resolve()
        tenant_dir_resolved = tenant_dir.resolve()

        # Verificar que full_path está dentro del scope del tenant
        try:
            full_path.relative_to(tenant_dir_resolved)
        except ValueError as err:
            raise ValueError(
                f"path escapa del scope del tenant: {relative_path} "
                f"(resolved: {full_path}, tenant_dir: {tenant_dir_resolved})"
            ) from err
        return full_path

    def save(self, tenant_id: int, relative_path: str, content: bytes) -> str:
        """Guarda contenido en relative_path. Crea directorios padre si es necesario.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa (ej: "marcas/prizma/logo.png")
            content: bytes a guardar

        Returns:
            Ruta absoluta del archivo guardado

        Raises:
            ValueError: si relative_path es inseguro
        """
        full_path = self._get_full_path(tenant_id, relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(full_path)

    def full_path(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve la ruta absoluta validada (anti path-traversal) sin exigir que exista.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa (ej: "marcas/prizma/logo.png")

        Returns:
            Ruta absoluta dentro del scope del tenant

        Raises:
            ValueError: si relative_path es inseguro
        """
        return str(self._get_full_path(tenant_id, relative_path))

    def open(self, tenant_id: int, relative_path: str) -> bytes:
        """Lee contenido de un archivo.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa

        Returns:
            Contenido del archivo en bytes

        Raises:
            FileNotFoundError: si el archivo no existe
            ValueError: si relative_path es inseguro
        """
        full_path = self._get_full_path(tenant_id, relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"archivo no existe: {full_path}")
        return full_path.read_bytes()

    def url_for(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve URL local (file://) para servir el archivo.

        En producción, esto se reemplazaría por CDN o Cloud Storage URLs.

        Args:
            tenant_id: ID del tenant
            relative_path: ruta relativa

        Returns:
            URL file:// (o URL real en implementación de GCS)

        Raises:
            ValueError: si relative_path es inseguro
        """
        full_path = self._get_full_path(tenant_id, relative_path)
        return f"file://{full_path}"

    def list_files(self, tenant_id: int, prefix: str = "") -> list[str]:
        """Lista archivos bajo la carpeta del tenant, opcionalmente filtrado por prefix.

        Args:
            tenant_id: ID del tenant
            prefix: prefijo dentro de la carpeta del tenant (ej: "marcas/")

        Returns:
            Lista de rutas relativas dentro del tenant
        """
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        if prefix:
            self._validate_relative_path(prefix)

        tenant_dir = self._get_tenant_dir(tenant_id)
        if not tenant_dir.exists():
            return []

        prefix_dir = tenant_dir / prefix if prefix else tenant_dir
        if not prefix_dir.exists():
            return []

        result: list[str] = []
        for file_path in prefix_dir.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(tenant_dir)
                result.append(str(relative))
        return sorted(result)

    def zip_many(self, tenant_id: int, relative_paths: list[str]) -> bytes:
        """Empacar múltiples archivos en un ZIP.

        Args:
            tenant_id: ID del tenant
            relative_paths: lista de rutas relativas a incluir

        Returns:
            Contenido del ZIP en bytes

        Raises:
            FileNotFoundError: si algún archivo no existe
            ValueError: si algún path es inseguro
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for relative_path in relative_paths:
                full_path = self._get_full_path(tenant_id, relative_path)
                if not full_path.exists():
                    raise FileNotFoundError(f"archivo no existe: {full_path}")
                # Guardar en el ZIP con la ruta relativa
                zf.write(full_path, arcname=relative_path)
        return zip_buffer.getvalue()
