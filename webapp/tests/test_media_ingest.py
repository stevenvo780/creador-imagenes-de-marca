"""Importación privada e inmutable con datos y archivos sintéticos."""

import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from webapp import db
from webapp.tests.media_helpers import brand, brief, image_bytes, project, upload
from webapp.tests.test_media_permissions import permission_db_clients as _permission_db_clients
from webapp.tests.test_projects import isolated_db as _isolated_db

isolated_db = _isolated_db
permission_db_clients = _permission_db_clients


@pytest.fixture
def media_clients(permission_db_clients):
    a, b, url = permission_db_clients
    return SimpleNamespace(a=a, b=b, db_path=url, storage=a.app.state.storage)


@pytest.fixture
def job(media_clients):
    p = project(media_clients.a, "campaign")
    b = brand(media_clients.a, p["id"], "brand")
    return brief(media_clients.a, b["id"])


def test_upload_does_not_overwrite(media_clients, job):
    content = image_bytes()
    first = upload(media_clients.a, job["id"], "same-key", content)
    assert first.status_code == 201, first.text
    again = upload(media_clients.a, job["id"], "same-key", content)
    assert again.status_code == 200, again.text
    assert again.json() == first.json()
    conflict = upload(media_clients.a, job["id"], "same-key", image_bytes(color="red"))
    assert conflict.status_code == 409
    result = first.json()
    assert result["status"] == "pending_review"
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["project_id"] == job["project_id"]
    assert result["brand_version"] == job["brand_version"]
    assert "storage_key" not in json.dumps(result)
    assert "url" not in result
    with db.connect(media_clients.db_path) as con:
        row = con.execute("SELECT * FROM media_assets WHERE id = ?", (result["id"],)).fetchone()
    assert media_clients.storage.open(row["tenant_id"], row["original_key"]) == content
    assert media_clients.a.get(f"/api/v1/media/{result['id']}").json() == result
    assert media_clients.b.get(f"/api/v1/media/{result['id']}").status_code == 404
    assert media_clients.b.get("/api/v1/media").json()["items"] == []
    assert upload(media_clients.b, job["id"], "foreign", content).status_code == 404


@pytest.mark.parametrize("changed", ["expiry", "identity", "archive"])
def test_stale_snapshot_rejected(media_clients, job, changed):
    if changed == "expiry":
        with db.connect(media_clients.db_path) as con:
            con.execute("UPDATE generation_briefs SET expires_at = 0 WHERE id = ?", (job["id"],))
    elif changed == "identity":
        media_clients.a.put(f"/api/v1/brands/{job['brand_id']}", json={"name": "Changed"})
    else:
        media_clients.a.post(f"/api/v1/projects/{job['project_id']}/archive")
    assert upload(media_clients.a, job["id"], "stale", image_bytes()).status_code == 409
    assert media_clients.a.get("/api/v1/media").json()["items"] == []


def test_idempotency_covers_provenance_source_and_brief(media_clients, job):
    assert upload(media_clients.a, job["id"], "metadata", image_bytes()).status_code == 201
    changed = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "metadata"},
        data={"brief_id": job["id"], "source": "codex", "provenance": '{"tool":"other"}'},
        files={"file": ("../../fake.png", image_bytes(), "image/png")},
    )
    assert changed.status_code == 409
    another = brief(media_clients.a, job["brand_id"])
    assert upload(media_clients.a, another["id"], "metadata", image_bytes()).status_code == 409


@pytest.mark.parametrize(
    "kind", ["truncated", "too-small", "wrong-size", "gif", "fake-mime", "bytes", "pixels"]
)
def test_rejects_invalid_images(media_clients, job, kind):
    data, mime = image_bytes(), "image/png"
    if kind == "truncated":
        data = data[: len(data) // 2]
    elif kind == "too-small":
        data = image_bytes(255, 512)
    elif kind == "wrong-size":
        data = image_bytes(256, 512)
    elif kind == "gif":
        stream = io.BytesIO()
        Image.new("RGB", (512, 512)).save(stream, format="GIF")
        data = stream.getvalue()
    elif kind == "fake-mime":
        mime = "image/jpeg"
    elif kind == "bytes":
        data = b"x" * (20 * 1024 * 1024 + 1)
    else:
        # Cabecera válida de 8192²: se rechaza antes de load sin crear imagen gigante.
        import struct
        import zlib

        header = struct.pack(">IIBBBBB", 8192, 8192, 8, 2, 0, 0, 0)
        chunk = b"IHDR" + header
        data = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", len(header))
            + chunk
            + struct.pack(">I", zlib.crc32(chunk))
        )
    response = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "invalid"},
        data={"brief_id": job["id"], "source": "codex", "provenance": "{}"},
        files={"file": ("image.png", data, mime)},
    )
    assert response.status_code == (413 if kind == "bytes" else 422), response.text
    assert media_clients.a.get("/api/v1/media").json()["items"] == []


def test_exif_normalizes_only_thumbnail(media_clients):
    p = project(media_clients.a, "portrait")
    b = brand(media_clients.a, p["id"], "portrait")
    job = brief(media_clients.a, b["id"], 512, 256)
    stream = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (512, 256), "red").save(stream, "JPEG", exif=exif)
    content = stream.getvalue()
    r = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "rotated"},
        data={"brief_id": job["id"], "source": "codex", "provenance": "{}"},
        files={"file": ("image.jpg", content, "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    with db.connect(media_clients.db_path) as con:
        row = con.execute("SELECT * FROM media_assets WHERE id = ?", (r.json()["id"],)).fetchone()
    assert media_clients.storage.open(row["tenant_id"], row["original_key"]) == content
    thumb = Image.open(
        io.BytesIO(media_clients.storage.open(row["tenant_id"], row["thumbnail_key"]))
    )
    assert thumb.width < thumb.height
    assert thumb.getexif().get(274) is None


@pytest.mark.parametrize("provenance", ["[]", "null", "{", '{"x":"' + "x" * 16384 + '"}'])
def test_invalid_provenance_rejected(media_clients, job, provenance):
    response = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "metadata"},
        data={"brief_id": job["id"], "source": "codex", "provenance": provenance},
        files={"file": ("image.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 422


def test_media_scope_matrix(media_clients, job):
    from webapp.storage import create_api_key

    tenant = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    legacy, _ = create_api_key(media_clients.db_path, tenant)
    agent = TestClient(media_clients.a.app)
    try:
        agent.headers["Authorization"] = f"Bearer {legacy}"
        assert upload(agent, job["id"], "legacy", image_bytes()).status_code == 403
        assert agent.get("/api/v1/media").status_code == 403
        for scopes in (["media:write"], ["media:read"]):
            key = media_clients.a.post(
                "/api/v1/auth/api-keys", json={"name": "agent", "scopes": scopes}
            ).json()["key"]
            agent.headers["Authorization"] = f"Bearer {key}"
            r = upload(agent, job["id"], "scoped", image_bytes())
            assert r.status_code == (201 if scopes == ["media:write"] else 403)
            assert agent.get("/api/v1/media").status_code == (
                403 if scopes == ["media:write"] else 200
            )
    finally:
        agent.close()


def test_list_filters_and_cursor(media_clients, job):
    first = upload(media_clients.a, job["id"], "first", image_bytes()).json()
    second = upload(media_clients.a, job["id"], "second", image_bytes(color="red")).json()
    page = media_clients.a.get(f"/api/v1/media?limit=1&project_id={job['project_id']}").json()
    assert page["items"] == [first]
    assert page["next_cursor"] == first["id"]
    page = media_clients.a.get(
        f"/api/v1/media?limit=1&cursor={first['id']}&brief_id={job['id']}"
    ).json()
    assert page["items"] == [second] and page["next_cursor"] is None
    assert media_clients.a.get("/api/v1/media?brand_id=99999").json()["items"] == []
    assert media_clients.a.get("/api/v1/media?limit=101").status_code == 422


def test_multipart_reads_are_bounded_before_buffering(media_clients, job, monkeypatch):
    from starlette.datastructures import UploadFile

    sizes = []
    read = UploadFile.read

    async def spy(self, size=-1):
        sizes.append(size)
        return await read(self, size)

    monkeypatch.setattr(UploadFile, "read", spy)
    assert (
        upload(media_clients.a, job["id"], "large", b"x" * (20 * 1024 * 1024 + 65536)).status_code
        == 413
    )
    assert sizes and set(sizes) == {65536}
    assert len(sizes) == 321
    with db.connect(media_clients.db_path) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM media_assets").fetchone()["n"] == 0


def test_decompression_warning_is_error():
    from unittest.mock import patch

    from webapp.media_validation import validate_image

    with (
        patch.object(Image, "MAX_IMAGE_PIXELS", 200000),
        pytest.raises(ValueError, match="insegura"),
    ):
        validate_image(image_bytes(), 512, 512)


def test_invalid_exif_rejected():
    from webapp.media_validation import validate_image

    stream = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 9
    Image.new("RGB", (512, 512)).save(stream, "JPEG", exif=exif)
    with pytest.raises(ValueError, match="EXIF"):
        validate_image(stream.getvalue(), 512, 512)


@pytest.mark.parametrize("status", ["approved", "rejected", "archived"])
def test_review_states_keep_original_and_idempotency(media_clients, job, status):
    first = upload(media_clients.a, job["id"], "reviewed", image_bytes()).json()
    with db.connect(media_clients.db_path) as con:
        original = con.execute("SELECT * FROM media_assets WHERE id = ?", (first["id"],)).fetchone()
        con.execute("UPDATE media_assets SET status = ? WHERE id = ?", (status, first["id"]))
    replay = upload(media_clients.a, job["id"], "reviewed", image_bytes())
    assert replay.status_code == 200 and replay.json()["status"] == status
    with db.connect(media_clients.db_path) as con:
        current = con.execute("SELECT * FROM media_assets WHERE id = ?", (first["id"],)).fetchone()
    assert current["original_key"] == original["original_key"]
    assert current["attempt_token"] == original["attempt_token"]
    assert (
        media_clients.storage.open(current["tenant_id"], current["original_key"]) == image_bytes()
    )
    assert media_clients.a.get(f"/api/v1/media/{first['id']}").json()["status"] == status


def test_untrusted_metadata_cannot_assign_tenant_or_approval(media_clients, job):
    tenant = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    foreign = media_clients.b.get("/auth/me").json()["tenant"]["id"]
    response = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "untrusted"},
        data={
            "brief_id": job["id"],
            "source": "codex",
            "provenance": "{}",
            "tenant_id": foreign,
            "status": "approved",
            "brand_id": 9999,
            "brand_version": 9999,
        },
        files={"file": ("../../outside.jpg", image_bytes(), "image/png")},
    )
    assert response.status_code == 201 and response.json()["status"] == "pending_review"
    with db.connect(media_clients.db_path) as con:
        row = con.execute(
            "SELECT * FROM media_assets WHERE id = ?", (response.json()["id"],)
        ).fetchone()
    assert row["tenant_id"] == tenant
    assert row["brand_id"] == job["brand_id"] and row["brand_version"] == job["brand_version"]
    assert media_clients.b.get("/api/v1/media").json()["items"] == []


def test_truncated_jpeg_requires_second_decode():
    from webapp.media_validation import validate_image

    stream = io.BytesIO()
    Image.new("RGB", (512, 512)).save(stream, "JPEG")
    with pytest.raises(ValueError, match="dañada"):
        validate_image(stream.getvalue()[:-100], 512, 512)


def test_api_bomb_warning_is_rejected_without_warning(media_clients, job, monkeypatch):
    import warnings

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 200000)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        response = upload(media_clients.a, job["id"], "bomb", image_bytes())
    assert response.status_code == 422
    assert emitted == []
