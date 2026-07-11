"""Pruebas para la abstracción de almacenamiento multi-tenant."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest

from webapp.storage_backend import LocalStorage


@pytest.fixture
def temp_storage_dir() -> Generator[str, None, None]:
    """Crea una carpeta temporal para pruebas."""
    tmp_dir = tempfile.mkdtemp(prefix="eikon_storage_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def local_storage(temp_storage_dir: str) -> LocalStorage:
    """Instancia de LocalStorage con base_dir temporal."""
    return LocalStorage(base_dir=temp_storage_dir)


class TestLocalStorageSave:
    """Pruebas de guardado de archivos."""

    def test_save_creates_parent_directories(self, local_storage: LocalStorage) -> None:
        """Verifica que save crea directorios padre automáticamente."""
        tenant_id = 1
        relative_path = "marcas/prizma/logo.png"
        content = b"PNG_DATA_HERE"

        result = local_storage.save(tenant_id, relative_path, content)

        assert Path(result).exists()
        assert Path(result).read_bytes() == content

    def test_save_overwrites_existing_file(self, local_storage: LocalStorage) -> None:
        """Verifica que save sobrescribe archivos existentes."""
        tenant_id = 1
        relative_path = "data/file.txt"
        content1 = b"OLD_CONTENT"
        content2 = b"NEW_CONTENT"

        local_storage.save(tenant_id, relative_path, content1)
        local_storage.save(tenant_id, relative_path, content2)

        assert local_storage.open(tenant_id, relative_path) == content2

    def test_save_multiple_tenants_isolated(self, local_storage: LocalStorage) -> None:
        """Verifica que archivos de diferentes tenants están aislados."""
        relative_path = "data/file.txt"
        content1 = b"TENANT_1_DATA"
        content2 = b"TENANT_2_DATA"

        local_storage.save(1, relative_path, content1)
        local_storage.save(2, relative_path, content2)

        assert local_storage.open(1, relative_path) == content1
        assert local_storage.open(2, relative_path) == content2


class TestLocalStorageOpen:
    """Pruebas de lectura de archivos."""

    def test_open_reads_saved_file(self, local_storage: LocalStorage) -> None:
        """Verifica que open lee archivos guardados correctamente."""
        tenant_id = 1
        relative_path = "test/data.bin"
        content = b"BINARY_CONTENT"

        local_storage.save(tenant_id, relative_path, content)
        result = local_storage.open(tenant_id, relative_path)

        assert result == content

    def test_open_raises_filenotfound_for_missing_file(self, local_storage: LocalStorage) -> None:
        """Verifica que open lanza FileNotFoundError para archivos inexistentes."""
        with pytest.raises(FileNotFoundError):
            local_storage.open(1, "nonexistent/file.txt")

    def test_open_respects_tenant_isolation(self, local_storage: LocalStorage) -> None:
        """Verifica que open solo puede leer archivos del tenant correcto."""
        local_storage.save(1, "file.txt", b"TENANT_1_DATA")
        local_storage.save(2, "file.txt", b"TENANT_2_DATA")

        # Tenant 1 solo ve su dato
        assert local_storage.open(1, "file.txt") == b"TENANT_1_DATA"
        # Tenant 2 solo ve su dato
        assert local_storage.open(2, "file.txt") == b"TENANT_2_DATA"


class TestLocalStorageUrlFor:
    """Pruebas de generación de URLs."""

    def test_url_for_returns_file_url(self, local_storage: LocalStorage) -> None:
        """Verifica que url_for devuelve una URL file://."""
        tenant_id = 1
        relative_path = "assets/logo.png"

        local_storage.save(tenant_id, relative_path, b"DATA")
        url = local_storage.url_for(tenant_id, relative_path)

        assert url.startswith("file://")
        assert "tenants/1" in url
        assert "logo.png" in url

    def test_url_for_is_path_specific(self, local_storage: LocalStorage) -> None:
        """Verifica que url_for cambia con diferentes paths."""
        tenant_id = 1

        local_storage.save(tenant_id, "file1.txt", b"DATA1")
        local_storage.save(tenant_id, "file2.txt", b"DATA2")

        url1 = local_storage.url_for(tenant_id, "file1.txt")
        url2 = local_storage.url_for(tenant_id, "file2.txt")

        assert url1 != url2
        assert "file1.txt" in url1
        assert "file2.txt" in url2


class TestLocalStorageListFiles:
    """Pruebas de listado de archivos."""

    def test_list_files_returns_empty_for_new_tenant(self, local_storage: LocalStorage) -> None:
        """Verifica que list_files devuelve lista vacía para tenant nuevo."""
        result = local_storage.list_files(1)
        assert result == []

    def test_list_files_returns_all_files(self, local_storage: LocalStorage) -> None:
        """Verifica que list_files retorna todos los archivos del tenant."""
        tenant_id = 1
        paths = [
            "marcas/prizma/logo.png",
            "marcas/prizma/palette.json",
            "assets/icon.svg",
        ]

        for path in paths:
            local_storage.save(tenant_id, path, b"DATA")

        result = local_storage.list_files(tenant_id)

        assert len(result) == 3
        assert sorted(result) == sorted(paths)

    def test_list_files_filters_by_prefix(self, local_storage: LocalStorage) -> None:
        """Verifica que list_files filtra por prefix."""
        tenant_id = 1
        paths = [
            "marcas/prizma/logo.png",
            "marcas/prizma/palette.json",
            "marcas/pistis/logo.png",
            "assets/icon.svg",
        ]

        for path in paths:
            local_storage.save(tenant_id, path, b"DATA")

        # Listar solo archivos en marcas/prizma/
        result = local_storage.list_files(tenant_id, prefix="marcas/prizma")

        assert len(result) == 2
        assert all("marcas/prizma" in p for p in result)

    def test_list_files_respects_tenant_isolation(self, local_storage: LocalStorage) -> None:
        """Verifica que list_files solo lista archivos del tenant."""
        local_storage.save(1, "marcas/logo.png", b"DATA1")
        local_storage.save(1, "assets/icon.svg", b"DATA1")
        local_storage.save(2, "marcas/logo.png", b"DATA2")

        result1 = local_storage.list_files(1)
        result2 = local_storage.list_files(2)

        assert len(result1) == 2
        assert len(result2) == 1
        assert result2 == ["marcas/logo.png"]


class TestLocalStorageZipMany:
    """Pruebas de empaquetamiento en ZIP."""

    def test_zip_many_creates_valid_zip(self, local_storage: LocalStorage) -> None:
        """Verifica que zip_many crea un ZIP válido con los archivos correctos."""
        tenant_id = 1
        files = {
            "marcas/logo.png": b"LOGO_DATA",
            "assets/icon.svg": b"ICON_DATA",
            "palette.json": b'{"color": "red"}',
        }

        for path, content in files.items():
            local_storage.save(tenant_id, path, content)

        zip_content = local_storage.zip_many(tenant_id, list(files.keys()))

        # Verificar que el ZIP es válido
        import io

        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            assert set(zf.namelist()) == set(files.keys())
            for path, expected_content in files.items():
                assert zf.read(path) == expected_content

    def test_zip_many_raises_filenotfound_for_missing(self, local_storage: LocalStorage) -> None:
        """Verifica que zip_many lanza FileNotFoundError si falta un archivo."""
        tenant_id = 1
        local_storage.save(tenant_id, "exists.txt", b"DATA")

        with pytest.raises(FileNotFoundError):
            local_storage.zip_many(tenant_id, ["exists.txt", "missing.txt"])

    def test_zip_many_empty_list(self, local_storage: LocalStorage) -> None:
        """Verifica que zip_many con lista vacía crea ZIP válido pero vacío."""
        tenant_id = 1
        zip_content = local_storage.zip_many(tenant_id, [])

        import io

        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            assert len(zf.namelist()) == 0


class TestPathTraversalSecurity:
    """Pruebas de seguridad: rechazo de path traversal."""

    def test_reject_parent_directory_traversal(self, local_storage: LocalStorage) -> None:
        """Verifica que ".." es rechazado en relative_path."""
        tenant_id = 1

        with pytest.raises(ValueError, match="path traversal"):
            local_storage.save(tenant_id, "../../../etc/passwd", b"DATA")

        with pytest.raises(ValueError, match="path traversal"):
            local_storage.open(tenant_id, "assets/../../../secret.txt")

    def test_reject_absolute_paths(self, local_storage: LocalStorage) -> None:
        """Verifica que paths absolutos son rechazados."""
        tenant_id = 1

        with pytest.raises(ValueError, match="absoluto"):
            local_storage.save(tenant_id, "/etc/passwd", b"DATA")

        with pytest.raises(ValueError, match="absoluto"):
            local_storage.open(tenant_id, "/etc/shadow")

    def test_reject_home_expansion(self, local_storage: LocalStorage) -> None:
        """Verifica que ~ (home expansion) es rechazado."""
        tenant_id = 1

        with pytest.raises(ValueError, match="home"):
            local_storage.save(tenant_id, "~/secret.txt", b"DATA")

    def test_reject_empty_path(self, local_storage: LocalStorage) -> None:
        """Verifica que relative_path vacío es rechazado."""
        tenant_id = 1

        with pytest.raises(ValueError, match="vacío"):
            local_storage.save(tenant_id, "", b"DATA")

    def test_safe_path_with_dots_in_filename(self, local_storage: LocalStorage) -> None:
        """Verifica que puntos en nombres de archivo (no path traversal) son seguros."""
        tenant_id = 1
        # "file.name.with.dots.png" es válido — solo ".." es peligroso
        relative_path = "assets/file.name.with.dots.png"

        local_storage.save(tenant_id, relative_path, b"DATA")
        result = local_storage.open(tenant_id, relative_path)

        assert result == b"DATA"

    def test_safe_nested_paths_in_bounds(self, local_storage: LocalStorage) -> None:
        """Verifica que paths profundos dentro del tenant son seguros."""
        tenant_id = 1
        relative_path = "a/b/c/d/e/f/g/file.txt"

        local_storage.save(tenant_id, relative_path, b"DATA")
        result = local_storage.open(tenant_id, relative_path)

        assert result == b"DATA"


class TestPathTraversalZipMany:
    """Pruebas de seguridad en zip_many."""

    def test_zip_many_rejects_path_traversal(self, local_storage: LocalStorage) -> None:
        """Verifica que zip_many rechaza paths con traversal."""
        tenant_id = 1
        local_storage.save(tenant_id, "file.txt", b"DATA")

        with pytest.raises(ValueError, match="path traversal"):
            local_storage.zip_many(tenant_id, ["../../../secret.txt"])

    def test_zip_many_rejects_absolute_paths(self, local_storage: LocalStorage) -> None:
        """Verifica que zip_many rechaza paths absolutos."""
        tenant_id = 1

        with pytest.raises(ValueError, match="absoluto"):
            local_storage.zip_many(tenant_id, ["/etc/passwd"])


class TestDirectoryStructure:
    """Pruebas de estructura de directorios creada."""

    def test_files_stored_under_tenant_dir(
        self, local_storage: LocalStorage, temp_storage_dir: str
    ) -> None:
        """Verifica que los archivos se guardan bajo output/tenants/<tenant_id>/."""
        tenant_id = 42
        local_storage.save(tenant_id, "file.txt", b"DATA")

        expected_base = Path(temp_storage_dir) / "tenants" / "42"
        assert expected_base.exists()
        assert (expected_base / "file.txt").exists()

    def test_different_tenants_separate_dirs(
        self, local_storage: LocalStorage, temp_storage_dir: str
    ) -> None:
        """Verifica que diferentes tenants usan directorios separados."""
        local_storage.save(1, "file.txt", b"DATA1")
        local_storage.save(2, "file.txt", b"DATA2")

        dir1 = Path(temp_storage_dir) / "tenants" / "1"
        dir2 = Path(temp_storage_dir) / "tenants" / "2"

        assert dir1.exists()
        assert dir2.exists()
        assert (dir1 / "file.txt").read_bytes() == b"DATA1"
        assert (dir2 / "file.txt").read_bytes() == b"DATA2"
