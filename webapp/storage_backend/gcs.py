"""Almacenamiento en Google Cloud Storage (GCS) - stub para futuro."""
from __future__ import annotations


class GCSStorage:
    """Implementación de almacenamiento en Google Cloud Storage (GCS).

    Documentado para fase posterior: requiere google-cloud-storage SDK,
    autenticación a GCP, y configuración de credenciales.

    Placeholder: raises NotImplementedError hasta que se implemente.
    """

    def __init__(self, bucket_name: str, credentials_path: str | None = None):
        """Inicializa GCSStorage.

        Args:
            bucket_name: nombre del bucket en GCS (ej: "eikon-assets")
            credentials_path: ruta a archivo service-account.json
                             (None = usa Application Default Credentials)
        """
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        # TODO: inicializar cliente de GCS
        #   from google.cloud import storage
        #   client = storage.Client.from_service_account_json(...)
        #   self.bucket = client.bucket(bucket_name)

    def save(self, tenant_id: int, relative_path: str, content: bytes) -> str:
        """Guarda contenido en GCS bajo gs://bucket/tenants/<tenant_id>/...

        Raises:
            NotImplementedError: no implementado en esta fase
        """
        raise NotImplementedError("GCS no disponible en esta fase")

    def open(self, tenant_id: int, relative_path: str) -> bytes:
        """Lee contenido de GCS.

        Raises:
            NotImplementedError: no implementado en esta fase
        """
        raise NotImplementedError("GCS no disponible en esta fase")

    def url_for(self, tenant_id: int, relative_path: str) -> str:
        """Devuelve URL de GCS (gs:// o https://storage.googleapis.com/...).

        Raises:
            NotImplementedError: no implementado en esta fase
        """
        raise NotImplementedError("GCS no disponible en esta fase")

    def list_files(self, tenant_id: int, prefix: str = "") -> list[str]:
        """Lista archivos en GCS bajo tenants/<tenant_id>/<prefix>.

        Raises:
            NotImplementedError: no implementado en esta fase
        """
        raise NotImplementedError("GCS no disponible en esta fase")

    def zip_many(self, tenant_id: int, relative_paths: list[str]) -> bytes:
        """Descarga y empacar múltiples objetos desde GCS.

        Raises:
            NotImplementedError: no implementado en esta fase
        """
        raise NotImplementedError("GCS no disponible en esta fase")
