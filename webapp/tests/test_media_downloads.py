"""Descargas autenticadas y promoción legacy sin aprobación implícita."""

import hashlib
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.storage import create_variation
from webapp.tests.media_helpers import image_bytes, upload
from webapp.tests.test_media_ingest import isolated_db as _isolated_db
from webapp.tests.test_media_ingest import job as _job
from webapp.tests.test_media_ingest import media_clients as _media_clients
from webapp.tests.test_media_ingest import permission_db_clients as _permission_db_clients

isolated_db = _isolated_db
job = _job
media_clients = _media_clients
permission_db_clients = _permission_db_clients


def test_private_downloads_scopes_and_logout(media_clients, job):
    content = image_bytes()
    asset = upload(media_clients.a, job["id"], "one", content).json()
    with closing(TestClient(media_clients.a.app)) as anonymous:
        for field in ("download_url", "thumbnail_url"):
            url = asset[field]
            assert anonymous.get(url).status_code == 401
            assert media_clients.b.get(url).status_code == 404
            result = media_clients.a.get(url)
            assert result.status_code == 200
            assert result.headers["cache-control"] == "private, no-store"
            assert result.headers["x-content-type-options"] == "nosniff"
            assert result.headers["content-type"] == "image/png"
            assert "location" not in result.headers
        assert media_clients.a.get(asset["download_url"]).content == content
        key = media_clients.a.post(
            "/api/v1/auth/api-keys", json={"name": "importer", "scopes": ["media:write"]}
        ).json()["key"]
        anonymous.headers["Authorization"] = f"Bearer {key}"
        assert anonymous.get(asset["download_url"]).status_code == 403
        key = media_clients.a.post(
            "/api/v1/auth/api-keys", json={"name": "reader", "scopes": ["media:read"]}
        ).json()["key"]
        anonymous.headers["Authorization"] = f"Bearer {key}"
        assert anonymous.get(asset["download_url"]).content == content
    media_clients.a.post("/auth/logout")
    assert media_clients.a.get(asset["download_url"]).status_code == 401


def legacy(media_clients, job, content=None):
    tenant = media_clients.a.get("/auth/me").json()["tenant"]["id"]
    content = content or image_bytes()
    path = media_clients.storage.save(tenant, "legacy/image.png", content)
    variation = create_variation(
        media_clients.db_path, tenant, job["brand_id"], output_path=path, score=100
    )
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE variations SET selected = 1 WHERE id = ?", (variation["id"],))
    return variation, tenant


def test_promotion_is_immutable_pending_and_scoped(media_clients, job):
    variation, tenant = legacy(media_clients, job)
    url = "/api/v1/media/from-variation"
    assert media_clients.b.post(url, json={"variation_id": variation["id"]}).status_code == 404
    response = media_clients.a.post(url, json={"variation_id": variation["id"]})
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["status"] == "pending_review" and not asset["approval_current"]
    assert asset["source"] == "legacy" and asset["provenance"]["variation_id"] == variation["id"]
    assert asset["sha256"] == hashlib.sha256(image_bytes()).hexdigest()
    assert media_clients.a.get("/api/v1/media?source=legacy").json()["items"] == [asset]
    assert media_clients.a.get("/api/v1/media?source=codex").json()["items"] == []
    assert media_clients.a.post(url, json={"variation_id": variation["id"]}).status_code == 200
    assert (
        media_clients.a.get(f"/api/v1/variations/{variation['id']}/file").content == image_bytes()
    )
    media_clients.storage.save(tenant, "legacy/image.png", image_bytes(color="red"))
    assert media_clients.a.get(asset["download_url"]).content == image_bytes()
    assert media_clients.a.post(url, json={"variation_id": variation["id"]}).status_code == 409


def test_promotion_rejects_small_legacy_without_changing_renderer(media_clients, job):
    variation, _ = legacy(media_clients, job, image_bytes(128, 512))
    response = media_clients.a.post(
        "/api/v1/media/from-variation", json={"variation_id": variation["id"]}
    )
    assert response.status_code == 422
    assert media_clients.a.get("/api/v1/media").json()["items"] == []


def test_mock_gcs_never_uses_public_url(media_clients, job, monkeypatch):
    from unittest.mock import MagicMock

    from webapp.storage_backend.gcs import GCSStorage

    store = GCSStorage.__new__(GCSStorage)
    store.bucket_name = "synthetic-private"
    objects = {}
    bucket = MagicMock()

    def blob(name):
        obj = MagicMock()
        obj.upload_from_string.side_effect = lambda data: objects.__setitem__(name, data)
        obj.download_as_bytes.side_effect = lambda: objects[name]
        return obj

    bucket.blob.side_effect = blob
    store._bucket = bucket
    monkeypatch.setattr(store, "url_for", lambda *a: pytest.fail("public URL used"))
    media_clients.a.app.state.storage = store
    asset = upload(media_clients.a, job["id"], "gcs", image_bytes()).json()
    assert media_clients.a.get(asset["download_url"]).content == image_bytes()
    assert media_clients.a.get(asset["thumbnail_url"]).status_code == 200
    assert "storage.googleapis.com" not in str(asset)
    assert all(name.startswith("tenants/") for name in objects)


def test_legacy_key_has_no_new_routes_and_body_cannot_forge_origin(media_clients, job):
    from webapp.storage import create_api_key

    variation, tenant = legacy(media_clients, job)
    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    key, _ = create_api_key(media_clients.db_path, tenant)
    agent = TestClient(media_clients.a.app)
    try:
        agent.headers["Authorization"] = f"Bearer {key}"
        assert agent.get(asset["download_url"]).status_code == 403
        assert agent.get(asset["thumbnail_url"]).status_code == 403
        assert (
            agent.post(
                "/api/v1/media/from-variation", json={"variation_id": variation["id"]}
            ).status_code
            == 403
        )
        assert agent.post(f"/api/v1/media/{asset['id']}/reviews", json={}).status_code == 403
        assert agent.get(f"/api/v1/variations/{variation['id']}/file").content == image_bytes()
    finally:
        agent.close()
    assert (
        media_clients.a.post(
            "/api/v1/media/from-variation",
            json={"variation_id": variation["id"], "tenant_id": tenant},
        ).status_code
        == 422
    )
    assert (
        media_clients.a.post(
            "/api/v1/media",
            headers={"Idempotency-Key": "forged"},
            data={"brief_id": job["id"], "source": "legacy", "provenance": "{}"},
            files={"file": ("image.png", image_bytes(), "image/png")},
        ).status_code
        == 422
    )


def test_promotion_retry_reuses_durable_ingest_journal(media_clients, job, monkeypatch):
    variation, tenant = legacy(media_clients, job)
    store = media_clients.storage
    save = store.save

    def fail_thumbnail(t, key, content):
        if key.endswith("thumbnail.png"):
            raise OSError("synthetic")
        return save(t, key, content)

    monkeypatch.setattr(store, "save", fail_thumbnail)
    url = "/api/v1/media/from-variation"
    assert media_clients.a.post(url, json={"variation_id": variation["id"]}).status_code == 503
    assert media_clients.a.get("/api/v1/media").json()["items"] == []
    with db.connect(media_clients.db_path) as con:
        first = con.execute("SELECT * FROM media_assets WHERE tenant_id = ?", (tenant,)).fetchone()
        assert first["status"] == "failed"
    monkeypatch.setattr(store, "save", save)
    result = media_clients.a.post(url, json={"variation_id": variation["id"]})
    assert result.status_code == 201, result.text
    assert result.json()["id"] == first["id"]
    assert result.json()["status"] == "pending_review"
    assert media_clients.a.get(result.json()["download_url"]).content == image_bytes()
    with db.connect(media_clients.db_path) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM media_variation_origins").fetchone()["n"] == 1


def test_download_jpeg_mime_and_safe_filename(media_clients):
    import io

    from PIL import Image

    from webapp.tests.media_helpers import brand, brief, project

    p = project(media_clients.a, "jpeg")
    b = brand(media_clients.a, p["id"], "jpeg")
    job = brief(media_clients.a, b["id"])
    stream = io.BytesIO()
    Image.new("RGB", (512, 512)).save(stream, "JPEG")
    content = stream.getvalue()
    result = media_clients.a.post(
        "/api/v1/media",
        headers={"Idempotency-Key": "jpeg"},
        data={"brief_id": job["id"], "source": "codex", "provenance": "{}"},
        files={"file": ("../../attack\r\nheader.jpg", content, "image/jpeg")},
    )
    assert result.status_code == 201, result.text
    response = media_clients.a.get(result.json()["download_url"])
    assert response.content == content and response.headers["content-type"] == "image/jpeg"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="media-{result.json()["id"]}.jpg"'
    )
    assert (
        media_clients.a.get(result.json()["thumbnail_url"]).headers["content-type"] == "image/png"
    )
