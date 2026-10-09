"""Encargos inmutables, logos originales y aislamiento real por empresa."""

import hashlib
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.storage import (
    create_api_key,
    create_brand,
    create_scoped_api_key,
    create_tenant_user,
    update_brand,
)
from webapp.tests.media_helpers import brand, brief, image_bytes, project
from webapp.tests.test_projects import isolated_db as _isolated_db

isolated_db = _isolated_db


def test_brief_cannot_use_other_company_brand(media_clients):
    p = project(media_clients.a, "alpha-campaign")
    b = brand(media_clients.a, p["id"], "alpha-brand")
    r = media_clients.b.post(
        "/api/v1/generation-briefs",
        json={"brand_id": b["id"], "prompt": "Private", "width": 512, "height": 512},
    )
    assert r.status_code == 404
    first = brief(media_clients.a, b["id"])
    media_clients.a.put(f"/api/v1/brands/{b['id']}", json={"name": "New name"})
    second = brief(media_clients.a, b["id"])
    assert second["brand_version"] > first["brand_version"]
    old = media_clients.a.get(f"/api/v1/generation-briefs/{first['id']}").json()
    assert old == first
    assert media_clients.b.get(f"/api/v1/generation-briefs/{first['id']}").status_code == 404
    canonical = json.dumps(
        first["snapshot"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert first["snapshot_hash"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_brand_project_and_general(media_clients):
    foreign = project(media_clients.b, "foreign")
    assert (
        media_clients.a.post(
            "/api/v1/brands", json={"slug": "bad", "name": "Bad", "project_id": foreign["id"]}
        ).status_code
        == 404
    )
    b = media_clients.a.post("/api/v1/brands", json={"slug": "old", "name": "Old"}).json()
    p = media_clients.a.get(f"/api/v1/projects/{b['project_id']}").json()
    assert p["slug"] == "general"
    own = project(media_clients.a, "own")
    assert (
        media_clients.a.put(
            f"/api/v1/brands/{b['id']}", json={"project_id": foreign["id"]}
        ).status_code
        == 404
    )
    assert (
        media_clients.a.put(f"/api/v1/brands/{b['id']}", json={"project_id": own["id"]}).json()[
            "project_id"
        ]
        == own["id"]
    )
    media_clients.a.post(f"/api/v1/projects/{own['id']}/archive")
    assert (
        media_clients.a.post(
            "/api/v1/generation-briefs",
            json={"brand_id": b["id"], "prompt": "test", "width": 512, "height": 512},
        ).status_code
        == 409
    )


def test_set_identity_versions_brief_and_logo_originals(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    first = brief(media_clients.a, b["id"])
    assert (
        media_clients.a.post(
            f"/api/v1/brands/{b['id']}/set-identity",
            json={"logo_style": "pack_brand_form", "logo_seed": 42},
        ).status_code
        == 200
    )
    assert brief(media_clients.a, b["id"])["brand_version"] > first["brand_version"]
    logos = [image_bytes(300, 80), image_bytes(300, 80, "red")]
    snapshots = []
    for data in logos:
        r = media_clients.a.post(
            f"/api/v1/brands/{b['id']}/reference-logo",
            files={"file": ("official.png", data, "image/png")},
        )
        assert r.status_code == 201, r.text
        snapshots.append(brief(media_clients.a, b["id"]))
    for data, snap in zip(logos, snapshots, strict=True):
        ref = snap["snapshot"]["reference_logo"]
        assert ref["sha256"] == hashlib.sha256(data).hexdigest()
        r = media_clients.a.get(ref["url"])
        assert r.content == data
        assert r.headers["cache-control"] == "private, no-store"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert media_clients.b.get(ref["url"]).status_code == 404
    assert snapshots[1]["brand_version"] > snapshots[0]["brand_version"]


@pytest.mark.parametrize(
    "data",
    [
        b"<svg",
        b"<!DOCTYPE svg><svg/>",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
        b'<svg xmlns:x="urn:x"><x:script/></svg>',
        b"<svg><foreignObject/></svg>",
        b'<svg><image href="https://x/logo.png"/></svg>',
        b"<svg><style>rect{fill:url(https://x)}</style></svg>",
        b'<svg><rect style="fill:u\\72l(https://x)"/></svg>',
        b'<svg><rect onload="alert(1)"/></svg>',
        b'<svg><image href="data:image/svg+xml;base64,aaa"/></svg>',
        b'<svg><animate attributeName="href" to="https://x"/></svg>',
    ],
)
def test_unsafe_svg_rejected(media_clients, data):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    r = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo",
        files={"file": ("logo.svg", data, "image/svg+xml")},
    )
    assert r.status_code == 422


def test_safe_svg_original_and_headers(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    data = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect fill="#123" width="20" height="10"/></svg>'
    r = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo",
        files={"file": ("logo.svg", data, "image/svg+xml")},
    )
    assert r.status_code == 201
    r = media_clients.a.get(f"/api/v1/brands/{b['id']}/reference-logo")
    assert r.content == data
    assert "sandbox" in r.headers["content-security-policy"]
    assert (
        media_clients.a.post(
            f"/api/v1/brands/{b['id']}/reference-logo",
            files={"file": ("logo.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
        ).status_code
        == 413
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"width": 255},
        {"height": 8193},
        {"width": 8192, "height": 8192},
        {"prompt": " "},
        {"expires_in_hours": 0},
        {"tenant_id": 55},
    ],
)
def test_brief_invalid_request(media_clients, payload):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    data = {"brand_id": b["id"], "prompt": "test", "width": 512, "height": 512, **payload}
    assert media_clients.a.post("/api/v1/generation-briefs", json=data).status_code == 422


def test_scoped_keys_and_legacy_do_not_inherit_new_routes(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    with db.connect(media_clients.db_path) as con:
        tid = con.execute("SELECT tenant_id FROM brands WHERE id = ?", (b["id"],)).fetchone()[
            "tenant_id"
        ]
    client = TestClient(media_clients.a.app)
    try:
        for scopes, expected in [(None, 403), ([], 403), (["brands:read"], 200)]:
            key, _ = (
                create_api_key(media_clients.db_path, tid)
                if scopes is None
                else create_scoped_api_key(media_clients.db_path, tid, "Test", scopes)
            )
            headers = {"Authorization": f"Bearer {key}"}
            assert (
                client.get(f"/api/v1/brands/{b['id']}/brief", headers=headers).status_code
                == expected
            )
            assert (
                client.post(
                    "/api/v1/generation-briefs",
                    headers=headers,
                    json={"brand_id": b["id"], "prompt": "test", "width": 512, "height": 512},
                ).status_code
                == 403
            )
        key, _ = create_scoped_api_key(
            media_clients.db_path, tid, "Writer", ["briefs:write", "media:write"]
        )
        headers = {"Authorization": f"Bearer {key}"}
        assert (
            client.post(
                "/api/v1/generation-briefs",
                headers=headers,
                json={"brand_id": b["id"], "prompt": "test", "width": 512, "height": 512},
            ).status_code
            == 201
        )
        assert (
            client.post(
                f"/api/v1/brands/{b['id']}/reference-logo",
                headers=headers,
                files={"file": ("logo.png", image_bytes(100, 50), "image/png")},
            ).status_code
            == 201
        )
    finally:
        client.close()


def test_brief_dialects_and_idempotent_migration(isolated_db):
    from webapp.brand_briefs import create_generation_brief, get_generation_brief, snapshot_brand

    db.init_db(isolated_db)
    user = create_tenant_user(isolated_db, "alpha", "Alpha", "alpha@example.test", "password123")
    b = create_brand(isolated_db, user["tenant_id"], "own", "Original")
    snapshot = snapshot_brand(isolated_db, user["tenant_id"], b["id"])
    first = create_generation_brief(
        isolated_db, user["tenant_id"], b["id"], "Test", 512, 512, int(time.time()) + 3600
    )
    update_brand(isolated_db, user["tenant_id"], b["id"], name="Changed")
    db.init_db(isolated_db)
    assert get_generation_brief(isolated_db, user["tenant_id"], first["id"]) == first
    assert first["snapshot"] == snapshot
    assert (
        snapshot_brand(isolated_db, user["tenant_id"], b["id"])["brand_version"]
        > snapshot["brand_version"]
    )
    assert get_generation_brief(isolated_db, user["tenant_id"] + 1, first["id"]) is None


from webapp.tests.test_media_permissions import permission_db_clients as _permission_db_clients

permission_db_clients = _permission_db_clients


@pytest.fixture
def media_clients(permission_db_clients):
    a, b, url = permission_db_clients
    return SimpleNamespace(a=a, b=b, db_path=url, output_root=a.app.state.output_root)


def test_briefs_pagination_scoped_and_expiry_preserved(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    other = brand(media_clients.b, project(media_clients.b, "own")["id"], "own")
    first = brief(media_clients.a, b["id"])
    brief(media_clients.b, other["id"])
    second = brief(media_clients.a, b["id"])
    assert first["expires_at"] - first["created_at"] == 24 * 3600
    page = media_clients.a.get("/api/v1/generation-briefs?limit=1").json()
    assert page["items"] == [first]
    assert page["next_cursor"] == first["id"]
    page = media_clients.a.get(f"/api/v1/generation-briefs?cursor={first['id']}&limit=1").json()
    assert page == {"items": [second], "next_cursor": None}
    assert media_clients.a.get("/api/v1/generation-briefs?limit=0").status_code == 422
    assert media_clients.a.get("/api/v1/generation-briefs?cursor=-1").status_code == 422


def test_version_migration_transaction_rollback_and_retry(isolated_db, monkeypatch):
    from webapp.migrations import _brand_columns, migrate_brand_briefs
    from webapp.storage import SCHEMA

    with db.connect(isolated_db) as con:
        con.executescript(SCHEMA)
    execute = db.DualConnection.execute

    def fail_marker(self, statement, params=()):
        if statement.startswith("INSERT INTO schema_migrations"):
            raise RuntimeError("marker failure")
        return execute(self, statement, params)

    # Actual startup prerequisites; failure rolls back only this coherent migration.
    from webapp.migrations import migrate_projects

    migrate_projects(isolated_db)
    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="marker failure"):
            migrate_brand_briefs(isolated_db)
    with db.connect(isolated_db) as con:
        assert "brand_version" not in _brand_columns(con)
    migrate_brand_briefs(isolated_db)
    migrate_brand_briefs(isolated_db)
    with db.connect(isolated_db) as con:
        assert "brand_version" in _brand_columns(con)
        assert (
            len(
                con.execute(
                    "SELECT * FROM schema_migrations WHERE version='brand_briefs_v1'"
                ).fetchall()
            )
            == 1
        )


def test_local_xlink_svg_retains_original_bytes(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    data = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><defs><path id="shape" d="M0 0h5v5z"/></defs><use xlink:href="#shape"/></svg>'
    r = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo",
        files={"file": ("logo.svg", data, "image/svg+xml")},
    )
    assert r.status_code == 201, r.text
    assert media_clients.a.get(r.json()["url"]).content == data


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
def test_truncated_raster_logo_rejected(media_clients, format_name):
    import io

    from PIL import Image

    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    stream = io.BytesIO()
    Image.new("RGB", (300, 90), "red").save(stream, format=format_name)
    content_type = "image/png" if format_name == "PNG" else "image/jpeg"
    truncated = stream.getvalue()[:-100]
    response = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo",
        files={"file": ("logo", truncated, content_type)},
    )
    assert response.status_code == 422
    assert media_clients.a.get(f"/api/v1/brands/{b['id']}/reference-logo").status_code == 404
    assert (
        media_clients.a.get(f"/api/v1/brands/{b['id']}").json()["brand_version"]
        == b["brand_version"]
    )


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
def test_fully_decoded_raster_logo_preserves_original(media_clients, format_name):
    import io

    from PIL import Image

    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    stream = io.BytesIO()
    Image.new("RGB", (300, 90), "red").save(stream, format=format_name)
    data = stream.getvalue()
    content_type = "image/png" if format_name == "PNG" else "image/jpeg"
    response = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo", files={"file": ("logo", data, content_type)}
    )
    assert response.status_code == 201
    assert response.json()["sha256"] == hashlib.sha256(data).hexdigest()
    downloaded = media_clients.a.get(response.json()["url"])
    assert downloaded.content == data
    with Image.open(io.BytesIO(downloaded.content)) as image:
        image.load()
        assert image.size == (300, 90)


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
def test_raster_decoder_warning_rejected_without_emitting_warning(
    media_clients, monkeypatch, format_name
):
    import io
    import warnings

    from PIL import Image

    b = brand(media_clients.a, project(media_clients.a, "own")["id"], "own")
    stream = io.BytesIO()
    Image.new("RGB", (300, 90), "red").save(stream, format=format_name)
    # Umbral artificial aislado: abre una imagen pequeña que dispara la advertencia.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 20_000)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        response = media_clients.a.post(
            f"/api/v1/brands/{b['id']}/reference-logo",
            files={"file": ("logo", stream.getvalue(), "image/png")},
        )
    assert response.status_code == 422
    assert emitted == []
    assert media_clients.a.get(f"/api/v1/brands/{b['id']}/reference-logo").status_code == 404
