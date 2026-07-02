"""Pruebas de GCSStorage con cliente GCS mockeado (sin red ni credenciales reales).

Mockea ``google.cloud.storage.Client`` a nivel de clase para aislar completamente
todas las llamadas HTTP/gRPC.  Verifica save / open / full_path / url_for /
list_files / zip_many y la selección local-vs-GCS mediante la factory get_storage.
"""
from __future__ import annotations

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from webapp.storage_backend import GCSStorage, LocalStorage, get_storage

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_gcs_client() -> tuple[MagicMock, MagicMock]:
    """Devuelve (mock_client, mock_bucket) con patch activo en el módulo gcs."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    return mock_client, mock_bucket


@pytest.fixture
def gcs_storage(mock_gcs_client: tuple[MagicMock, MagicMock]) -> GCSStorage:
    """GCSStorage con cliente GCS mockeado — sin red ni credenciales."""
    mock_client, mock_bucket = mock_gcs_client
    with patch("webapp.storage_backend.gcs.Client", return_value=mock_client):
        storage = GCSStorage(bucket_name="test-bucket")
    # Inyectar el bucket mock directamente (el client.bucket() ya devuelve mock_bucket
    # pero GCSStorage guarda la referencia en __init__)
    storage._client = mock_client
    storage._bucket = mock_bucket
    return storage


# ── save ──────────────────────────────────────────────────────────────────────


class TestGCSStorageSave:
    """Pruebas de subida de objetos a GCS."""

    def test_save_returns_gcs_uri(self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]) -> None:
        """save devuelve URI gs:// correcta."""
        _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = gcs_storage.save(1, "marcas/logo.png", b"PNG_DATA")

        assert result == "gs://test-bucket/tenants/1/marcas/logo.png"
        mock_blob.upload_from_string.assert_called_once_with(b"PNG_DATA")

    def test_save_uses_tenant_scope(self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]) -> None:
        """save separa objetos de distintos tenants."""
        _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        gcs_storage.save(1, "file.txt", b"T1")
        gcs_storage.save(2, "file.txt", b"T2")

        calls = [c.args[0] for c in mock_bucket.blob.call_args_list]
        assert "tenants/1/file.txt" in calls
        assert "tenants/2/file.txt" in calls

    def test_save_rejects_path_traversal(self, gcs_storage: GCSStorage) -> None:
        """save rechaza paths con '..'."""
        with pytest.raises(ValueError, match="path traversal"):
            gcs_storage.save(1, "../../../etc/passwd", b"EVIL")

    def test_save_rejects_absolute_path(self, gcs_storage: GCSStorage) -> None:
        """save rechaza paths absolutos."""
        with pytest.raises(ValueError, match="absoluto"):
            gcs_storage.save(1, "/etc/passwd", b"EVIL")

    def test_save_rejects_home_expansion(self, gcs_storage: GCSStorage) -> None:
        """save rechaza rutas con '~'."""
        with pytest.raises(ValueError, match="home"):
            gcs_storage.save(1, "~/secret", b"EVIL")

    def test_save_rejects_empty_path(self, gcs_storage: GCSStorage) -> None:
        """save rechaza relative_path vacío."""
        with pytest.raises(ValueError, match="vacío"):
            gcs_storage.save(1, "", b"DATA")


# ── open ──────────────────────────────────────────────────────────────────────


class TestGCSStorageOpen:
    """Pruebas de descarga de objetos desde GCS."""

    def test_open_returns_content(self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]) -> None:
        """open devuelve los bytes del objeto."""
        _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"CONTENT"
        mock_bucket.blob.return_value = mock_blob

        result = gcs_storage.open(1, "assets/icon.svg")

        assert result == b"CONTENT"
        mock_blob.download_as_bytes.assert_called_once()

    def test_open_raises_filenotfound_when_missing(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """open lanza FileNotFoundError si el objeto no existe en GCS."""
        from google.cloud.exceptions import NotFound

        _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.side_effect = NotFound("objeto no existe")
        mock_bucket.blob.return_value = mock_blob

        with pytest.raises(FileNotFoundError, match="objeto no existe en GCS"):
            gcs_storage.open(1, "nonexistent.png")

    def test_open_rejects_path_traversal(self, gcs_storage: GCSStorage) -> None:
        """open rechaza paths con '..'."""
        with pytest.raises(ValueError, match="path traversal"):
            gcs_storage.open(1, "assets/../../../secret")


# ── full_path ─────────────────────────────────────────────────────────────────


class TestGCSStorageFullPath:
    """Pruebas del resolutor de URI sin red."""

    def test_full_path_returns_gs_uri(self, gcs_storage: GCSStorage) -> None:
        """full_path devuelve URI gs:// sin contactar GCS."""
        result = gcs_storage.full_path(42, "marcas/prizma/logo.png")
        assert result == "gs://test-bucket/tenants/42/marcas/prizma/logo.png"

    def test_full_path_rejects_traversal(self, gcs_storage: GCSStorage) -> None:
        """full_path rechaza paths inseguros."""
        with pytest.raises(ValueError, match="path traversal"):
            gcs_storage.full_path(1, "../../secret")


# ── url_for ───────────────────────────────────────────────────────────────────


class TestGCSStorageUrlFor:
    """Pruebas de generación de URLs HTTPS."""

    def test_url_for_returns_https_url(self, gcs_storage: GCSStorage) -> None:
        """url_for devuelve URL pública de Cloud Storage."""
        url = gcs_storage.url_for(7, "assets/banner.png")
        assert url == "https://storage.googleapis.com/test-bucket/tenants/7/assets/banner.png"

    def test_url_for_encodes_tenant_id(self, gcs_storage: GCSStorage) -> None:
        """url_for incluye el tenant_id en la URL."""
        url1 = gcs_storage.url_for(1, "file.png")
        url2 = gcs_storage.url_for(2, "file.png")
        assert "tenants/1/" in url1
        assert "tenants/2/" in url2
        assert url1 != url2


# ── list_files ────────────────────────────────────────────────────────────────


class TestGCSStorageListFiles:
    """Pruebas de listado de objetos."""

    def _make_blob(self, name: str) -> MagicMock:
        blob = MagicMock()
        blob.name = name
        return blob

    def test_list_files_returns_relative_paths(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """list_files devuelve rutas relativas sin el prefijo del tenant."""
        mock_client, _ = mock_gcs_client
        mock_client.list_blobs.return_value = [
            self._make_blob("tenants/1/marcas/logo.png"),
            self._make_blob("tenants/1/assets/icon.svg"),
        ]

        result = gcs_storage.list_files(1)

        assert sorted(result) == ["assets/icon.svg", "marcas/logo.png"]

    def test_list_files_returns_empty_for_no_objects(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """list_files devuelve lista vacía si no hay objetos."""
        mock_client, _ = mock_gcs_client
        mock_client.list_blobs.return_value = []

        result = gcs_storage.list_files(99)

        assert result == []

    def test_list_files_filters_by_prefix(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """list_files pasa el prefix al cliente GCS."""
        mock_client, _ = mock_gcs_client
        mock_client.list_blobs.return_value = [
            self._make_blob("tenants/1/marcas/prizma/logo.png"),
            self._make_blob("tenants/1/marcas/prizma/palette.json"),
        ]

        result = gcs_storage.list_files(1, prefix="marcas/prizma")

        # Verificar que el prefix llega a list_blobs
        call_kwargs = mock_client.list_blobs.call_args[1]
        assert "marcas/prizma/" in call_kwargs.get("prefix", "")
        assert all("marcas/prizma" in p for p in result)

    def test_list_files_sorted(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """list_files devuelve rutas en orden alfabético."""
        mock_client, _ = mock_gcs_client
        mock_client.list_blobs.return_value = [
            self._make_blob("tenants/3/z_file.png"),
            self._make_blob("tenants/3/a_file.png"),
            self._make_blob("tenants/3/m_file.png"),
        ]

        result = gcs_storage.list_files(3)

        assert result == ["a_file.png", "m_file.png", "z_file.png"]


# ── zip_many ──────────────────────────────────────────────────────────────────


class TestGCSStorageZipMany:
    """Pruebas de empaquetamiento en ZIP descargando desde GCS."""

    def test_zip_many_creates_valid_zip(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """zip_many crea un ZIP en memoria con el contenido de los objetos GCS."""
        _, mock_bucket = mock_gcs_client
        files = {
            "marcas/logo.png": b"LOGO_DATA",
            "assets/icon.svg": b"ICON_DATA",
        }

        def make_blob(path: str) -> MagicMock:
            blob = MagicMock()
            # Deducir la clave relativa del blob_name (tenants/1/<path>)
            relative = path.split("tenants/1/", 1)[-1]
            blob.download_as_bytes.return_value = files.get(relative, b"")
            blob.name = path
            return blob

        mock_bucket.blob.side_effect = lambda name: make_blob(name)

        zip_bytes = gcs_storage.zip_many(1, list(files.keys()))

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            assert set(zf.namelist()) == set(files.keys())
            for path, expected in files.items():
                assert zf.read(path) == expected

    def test_zip_many_empty_list(self, gcs_storage: GCSStorage) -> None:
        """zip_many con lista vacía crea ZIP vacío válido."""
        zip_bytes = gcs_storage.zip_many(1, [])
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            assert len(zf.namelist()) == 0

    def test_zip_many_raises_filenotfound_for_missing(
        self, gcs_storage: GCSStorage, mock_gcs_client: tuple[MagicMock, MagicMock]
    ) -> None:
        """zip_many propaga FileNotFoundError si un objeto no existe."""
        from google.cloud.exceptions import NotFound

        _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.side_effect = NotFound("missing")
        mock_bucket.blob.return_value = mock_blob

        with pytest.raises(FileNotFoundError):
            gcs_storage.zip_many(1, ["missing_file.png"])


# ── get_storage factory ───────────────────────────────────────────────────────


class TestGetStorageFactory:
    """Pruebas de la factory get_storage: selección local vs GCS."""

    def test_returns_local_storage_when_no_bucket(self, tmp_path: str) -> None:
        """Sin GCS_BUCKET, get_storage devuelve LocalStorage."""
        env = {k: v for k, v in os.environ.items() if k != "GCS_BUCKET"}
        with patch.dict(os.environ, env, clear=True):
            storage = get_storage(base_dir=tmp_path)
        assert isinstance(storage, LocalStorage)

    def test_returns_gcs_storage_when_bucket_set(self) -> None:
        """Con GCS_BUCKET definida, get_storage devuelve GCSStorage."""
        mock_client = MagicMock()
        mock_client.bucket.return_value = MagicMock()
        with (
            patch.dict(os.environ, {"GCS_BUCKET": "my-bucket"}),
            patch("webapp.storage_backend.gcs.Client", return_value=mock_client),
        ):
            storage = get_storage()
        assert isinstance(storage, GCSStorage)
        assert storage.bucket_name == "my-bucket"

    def test_local_storage_default_base_dir(self) -> None:
        """Sin base_dir explícito, LocalStorage usa 'output'."""
        env = {k: v for k, v in os.environ.items() if k != "GCS_BUCKET"}
        with patch.dict(os.environ, env, clear=True):
            storage = get_storage()
        assert isinstance(storage, LocalStorage)
        assert "output" in str(storage.base_dir)
