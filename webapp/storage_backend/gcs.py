"""Almacenamiento en Google Cloud Storage (GCS) con aislamiento por tenant.

Objetos almacenados bajo:  gs://<bucket>/tenants/<tenant_id>/<relative_path>

Autenticación: Application Default Credentials (ADC) por defecto.
En Cloud Run, ADC resuelve con la service account del servicio sin configuración
adicional.  En local se puede pasar credentials_path (service-account.json).
"""
from __future__ import annotations

import io
import zipfile

from google.cloud.exceptions import NotFound
from google.cloud.storage import Blob, Bucket, Client


class GCSStorage:
    """Backend de almacenamiento sobre Google Cloud Storage.

    Cada tenant queda aislado bajo ``tenants/<tenant_id>/`` dentro del bucket.
    Valida paths relativos con las mismas reglas anti-traversal que LocalStorage.
    """

    def __init__(self, bucket_name: str, credentials_path: str | None = None) -> None:
        """Inicializa el cliente GCS y selecciona el bucket.

        Args:
            bucket_name: nombre del bucket en GCS (ej: "eikon-assets-prod")
            credentials_path: ruta a service-account.json.
                              None → usa Application Default Credentials (ADC).
        """
        if credentials_path:
            client: Client = Client.from_service_account_json(credentials_path)
        else:
            client = Client()  # ADC: env GOOGLE_APPLICATION_CREDENTIALS o metadata server
        self._client = client
        self._bucket: Bucket = client.bucket(bucket_name)
        self.bucket_name = bucket_name

    # ── validación ────────────────────────────────────────────────────────────

    def _validate_relative_path(self, relative_path: str) -> None:
        """Rechaza paths con traversal, absolutos, home-expansion o vacíos.

        Raises:
            ValueError: si el path es inseguro.
        """
        if not relative_path:
            raise ValueError("relative_path no puede estar vacío")
        if relative_path.startswith("/"):
            raise ValueError("relative_path no puede ser absoluto")
        if ".." in relative_path.split("/"):
            raise ValueError("relative_path contiene '..' (path traversal prohibido)")
        if relative_path.startswith("~"):
            raise ValueError("relative_path no puede contener '~' (expansión de home prohibida)")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _blob_name(self, tenant_id: int, relative_path: str) -> str:
        """Nombre completo del objeto dentro del bucket."""
        return f"tenants/{tenant_id}/{relative_path}"

    def _blob(self, tenant_id: int, relative_path: str) -> Blob:
        """Devuelve el objeto Blob validado (sin requerir que exista)."""
        self._validate_relative_path(relative_path)
        return self._bucket.blob(self._blob_name(tenant_id, relative_path))

    # ── Protocol StorageBackend ───────────────────────────────────────────────

    def save(self, tenant_id: int, relative_path: str, content: bytes) -> str:
        """Sube *content* al bucket y devuelve la URI gs:// del objeto.

        Args:
            tenant_id: ID del tenant (scope de seguridad).
            relative_path: ruta relativa dentro del tenant (ej: "marcas/prizma/logo.png").
            content: bytes a guardar.

        Returns:
            URI ``gs://<bucket>/tenants/<tenant_id>/<relative_path>``.

        Raises:
            ValueError: si relative_path es inseguro.
        """
        self._validate_relative_path(relative_path)
        blob_name = self._blob_name(tenant_id, relative_path)
        blob = self._bucket.blob(blob_name)
        blob.upload_from_string(content)
        return f"gs://{self.bucket_name}/{blob_name}"

    def open(self, tenant_id: int, relative_path: str) -> bytes:
        """Descarga el objeto y devuelve sus bytes.

        Args:
            tenant_id: ID del tenant.
            relative_path: ruta relativa dentro del tenant.

        Returns:
            Contenido del objeto en bytes.

        Raises:
            FileNotFoundError: si el objeto no existe en GCS.
            ValueError: si relative_path es inseguro.
        """
        blob = self._blob(tenant_id, relative_path)
        try:
            return blob.download_as_bytes()  # type: ignore[no-any-return]
        except NotFound as exc:
            raise FileNotFoundError(
                f"objeto no existe en GCS: {blob.name}"
            ) from exc

    def full_path(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve la URI gs:// del objeto sin requerir que exista.

        Equivalente al resolutor de ruta autoritativo: permite al worker ubicar
        el destino de escritura.  Con GCS backend el worker debe usar ``save``
        para subir contenido; la URI sirve como identificador único del objeto.

        Args:
            tenant_id: ID del tenant.
            relative_path: ruta relativa dentro del tenant.

        Returns:
            URI ``gs://<bucket>/tenants/<tenant_id>/<relative_path>``.

        Raises:
            ValueError: si relative_path es inseguro.
        """
        self._validate_relative_path(relative_path)
        blob_name = self._blob_name(tenant_id, relative_path)
        return f"gs://{self.bucket_name}/{blob_name}"

    def relative_key(self, tenant_id: int, stored_path: str) -> str:
        """Invierte ``save()``: de la URI ``gs://`` persistida a la clave relativa.

        ``save()`` devuelve ``gs://<bucket>/tenants/<tenant_id>/<relative>``; aquí
        quitamos ese prefijo para reabrir/empacar el objeto por el seam.  Esto es
        lo que arregla servir imágenes en producción (antes el router hacía
        path-math de filesystem sobre una URI gs:// → 400 "invalid path").

        Raises:
            ValueError: si stored_path no pertenece al scope del tenant.
        """
        prefix = f"gs://{self.bucket_name}/tenants/{tenant_id}/"
        if not stored_path.startswith(prefix):
            raise ValueError(
                f"stored_path fuera del scope del tenant {tenant_id}: {stored_path}"
            )
        rel = stored_path[len(prefix):]
        self._validate_relative_path(rel)
        return rel

    def url_for(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve la URL HTTPS pública del objeto.

        Asume que el bucket/objeto es de acceso público o que el cliente tiene
        credenciales para descargarlo.  Para URLs firmadas (acceso privado), se
        necesitaría extender este método con ``generate_signed_url``.

        Args:
            tenant_id: ID del tenant.
            relative_path: ruta relativa dentro del tenant.

        Returns:
            URL ``https://storage.googleapis.com/<bucket>/tenants/<tenant_id>/<relative_path>``.

        Raises:
            ValueError: si relative_path es inseguro.
        """
        self._validate_relative_path(relative_path)
        blob_name = self._blob_name(tenant_id, relative_path)
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"

    def list_files(self, tenant_id: int, prefix: str = "") -> list[str]:
        """Lista objetos en el bucket bajo el scope del tenant.

        Args:
            tenant_id: ID del tenant.
            prefix: prefijo dentro del tenant (ej: "marcas/prizma/").
                    Si no termina en "/" se añade automáticamente.

        Returns:
            Lista de rutas relativas ordenadas (sin el prefijo ``tenants/<tenant_id>/``).
        """
        # Normalizar prefix
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        if prefix:
            self._validate_relative_path(prefix)

        gcs_prefix = f"tenants/{tenant_id}/"
        if prefix:
            gcs_prefix += prefix

        tenant_prefix = f"tenants/{tenant_id}/"
        result: list[str] = []
        for blob in self._client.list_blobs(self._bucket, prefix=gcs_prefix):
            name: str = blob.name
            if name.startswith(tenant_prefix):
                relative = name[len(tenant_prefix):]
                if relative:  # excluir el "directorio" ficticio (blob.name == prefijo exacto)
                    result.append(relative)
        return sorted(result)

    def zip_many(self, tenant_id: int, relative_paths: list[str]) -> bytes:
        """Descarga múltiples objetos GCS y los empaca en un ZIP en memoria.

        Args:
            tenant_id: ID del tenant.
            relative_paths: lista de rutas relativas a incluir.

        Returns:
            Contenido del ZIP en bytes.

        Raises:
            FileNotFoundError: si algún objeto no existe.
            ValueError: si algún path es inseguro.
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for relative_path in relative_paths:
                # open() ya valida y lanza FileNotFoundError/ValueError
                content = self.open(tenant_id, relative_path)
                zf.writestr(relative_path, content)
        return zip_buffer.getvalue()
