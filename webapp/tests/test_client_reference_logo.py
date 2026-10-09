"""Render-plan preserves the private original, never silently redraws a reference."""

import base64
import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from eikon_core.mapping import map_marca_to_vars
from webapp import db
from webapp.tests.media_helpers import brand, project
from webapp.tests.test_media_ingest import (
    isolated_db as _isolated_db,
)
from webapp.tests.test_media_ingest import (
    media_clients as _media_clients,
)
from webapp.tests.test_media_ingest import (
    permission_db_clients as _permission_db_clients,
)

isolated_db = _isolated_db
media_clients = _media_clients
permission_db_clients = _permission_db_clients


def batch(client, brand_id):
    r = client.post(
        "/api/v1/batches",
        json={
            "brand_id": brand_id,
            "asset_types": ["ig_post"],
            "count": 1,
            "render_mode": "client",
        },
    )
    assert r.status_code == 202, r.text
    return r.json()["id"]


def logo_bytes(kind):
    if kind == "SVG":
        return b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80"><rect width="300" height="80" fill="#227d84"/></svg>'
    stream = io.BytesIO()
    Image.new("RGB", (300, 80), "teal").save(stream, format=kind)
    return stream.getvalue()


@pytest.mark.parametrize(
    "kind,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("SVG", "image/svg+xml")]
)
def test_plan_uses_exact_official_private_bytes(media_clients, kind, mime):
    b = brand(media_clients.a, project(media_clients.a, "official")["id"], "official")
    data = logo_bytes(kind)
    r = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo", files={"file": ("original", data, mime)}
    )
    assert r.status_code == 201, r.text
    bid = batch(media_clients.a, b["id"])
    r = media_clients.a.get(f"/api/v1/batches/{bid}/plan")
    assert r.status_code == 200, r.text
    uri = r.json()["combinations"][0]["isotype_data_uri"]
    assert uri.startswith(f"data:{mime};base64,")
    assert base64.b64decode(uri.split(",")[1]) == data
    assert r.headers["cache-control"] == "private, no-store"
    assert media_clients.b.get(f"/api/v1/batches/{bid}/plan").status_code == 404


@pytest.mark.parametrize("failure", ["missing", "hash", "mime", "metadata", "invalid"])
def test_bad_reference_fails_instead_of_procedural_redraw(media_clients, failure):
    b = brand(media_clients.a, project(media_clients.a, "broken")["id"], "broken")
    data = logo_bytes("PNG")
    r = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo", files={"file": ("logo.png", data, "image/png")}
    )
    assert r.status_code == 201
    bid = batch(media_clients.a, b["id"])
    with db.connect(media_clients.db_path) as con:
        row = con.execute(
            "SELECT * FROM brand_logo_versions WHERE brand_id=?", (b["id"],)
        ).fetchone()
        if failure == "metadata":
            con.execute("DELETE FROM brand_logo_versions WHERE brand_id=?", (b["id"],))
        if failure == "mime":
            con.execute(
                "UPDATE brand_logo_versions SET content_type='image/jpeg' WHERE brand_id=?",
                (b["id"],),
            )
        if failure == "invalid":
            corrupt = b"not an image"
            sha = hashlib.sha256(corrupt).hexdigest()
            con.execute("UPDATE brand_logo_versions SET sha256=? WHERE brand_id=?", (sha, b["id"]))
            con.execute("UPDATE brands SET reference_logo_sha256=? WHERE id=?", (sha, b["id"]))
            media_clients.storage.save(row["tenant_id"], row["storage_key"], corrupt)
    if failure == "missing":
        media_clients.storage.delete(row["tenant_id"], row["storage_key"])
    if failure == "hash":
        media_clients.storage.save(row["tenant_id"], row["storage_key"], b"corrupt")
    r = media_clients.a.get(f"/api/v1/batches/{bid}/plan")
    assert r.status_code == 409, r.text
    assert "combinations" not in r.json()


def test_plan_without_reference_retains_procedural_behavior(media_clients):
    b = brand(media_clients.a, project(media_clients.a, "legacy")["id"], "legacy")
    r = media_clients.a.get(f"/api/v1/batches/{batch(media_clients.a, b['id'])}/plan")
    assert r.status_code == 200
    assert r.json()["combinations"][0]["isotype_data_uri"].startswith("data:image/svg+xml;base64,")


def test_manrope_is_packaged_and_maps_without_fallback():
    result = map_marca_to_vars(
        {"tipografia": {"titulos": "Manrope", "cuerpo": "Manrope"}}, "ig_post"
    )
    assert "Manrope" in result["font_titulo"]
    assert "Manrope" in result["font_cuerpo"]
    root = Path(__file__).resolve().parents[2]
    assert root.joinpath("templates/fonts/Manrope-wght.ttf").read_bytes()[:4] == b"\x00\x01\x00\x00"
    assert "SIL OPEN FONT LICENSE" in root.joinpath("templates/fonts/Manrope-OFL.txt").read_text()


def test_reference_metadata_is_scoped_by_tenant_and_brand(media_clients):
    own = brand(media_clients.a, project(media_clients.a, "own-ref")["id"], "own-ref")
    foreign = brand(media_clients.b, project(media_clients.b, "foreign-ref")["id"], "foreign-ref")
    content = logo_bytes("PNG")
    result = media_clients.b.post(
        f"/api/v1/brands/{foreign['id']}/reference-logo",
        files={"file": ("logo.png", content, "image/png")},
    )
    assert result.status_code == 201
    with db.connect(media_clients.db_path) as con:
        con.execute(
            "UPDATE brands SET reference_logo_sha256=? WHERE id=? AND tenant_id=?",
            (
                result.json()["sha256"],
                own["id"],
                media_clients.a.get("/auth/me").json()["tenant"]["id"],
            ),
        )
    plan = media_clients.a.get(f"/api/v1/batches/{batch(media_clients.a, own['id'])}/plan")
    assert plan.status_code == 409
    assert "combinations" not in plan.json()
