"""Importador cliente: entorno privado, originales e idempotencia real HTTP."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from webapp import db
from webapp.storage import create_scoped_api_key
from webapp.tests.media_helpers import image_bytes, project
from webapp.tests.test_projects import isolated_db as _isolated_db

isolated_db = _isolated_db


def inventory(tmp_path, slug="pinakotheke-kosmos", missing=False):
    logo = tmp_path / "original.png"
    if not missing:
        logo.write_bytes(image_bytes(300, 90))
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "slug": slug,
                "nombre_producto": "Producto",
                "nombre_corporativo": "Corporativo",
                "paleta": {"bg": "#123456", "acento": "#abcdef", "surface": "#444444"},
                "tipografia": {"titulos": "Inter"},
                "logo_asset": "original.png",
            }
        )
    )
    return source, logo


def run(client, p, path, monkeypatch, apply=False):
    from scripts.import_brand_inventory import import_inventory

    monkeypatch.setenv("EIKON_OWNER_SESSION", client.cookies.get("eikon_jwt"))
    return import_inventory(client, p["id"], path, apply=apply)


def test_import_dry_run_then_owner_apply_idempotent_two_tenants(
    media_clients, tmp_path, monkeypatch
):
    source, logo = inventory(tmp_path)
    pa, pb = project(media_clients.a, "campaign"), project(media_clients.b, "campaign")
    result = run(media_clients.a, pa, source, monkeypatch)
    assert result["counts"]["create"] == 1
    assert media_clients.a.get("/api/v1/brands").json()["items"] == []
    for client, p in [(media_clients.a, pa), (media_clients.b, pb)]:
        assert run(client, p, source, monkeypatch, True)["counts"]["create"] == 1
        assert run(client, p, source, monkeypatch, True)["counts"]["skip_identical"] == 1
        brands = client.get("/api/v1/brands").json()["items"]
        assert len(brands) == 1
        b = brands[0]
        assert b["slug"] == "campaign-pinakotheke-kosmos"
        assert b["project_id"] == p["id"]
        assert b["reference_logo_sha256"] == hashlib.sha256(logo.read_bytes()).hexdigest()
        assert client.get(f"/api/v1/brands/{b['id']}/reference-logo").content == logo.read_bytes()
        assert b["texts"]["inventory_source"]["slug"] == "pinakotheke-kosmos"
        assert b["texts"]["inventory_source"]["nombre_corporativo"] == "Corporativo"


def test_import_conflict_missing_reference_and_no_reassignment(
    media_clients, tmp_path, monkeypatch
):
    source, logo = inventory(tmp_path)
    p = project(media_clients.a, "campaign")
    run(media_clients.a, p, source, monkeypatch, True)
    brand = media_clients.a.get("/api/v1/brands").json()["items"][0]
    changed = json.loads(source.read_text())
    changed["nombre_producto"] = "Different"
    source.write_text(json.dumps(changed))
    assert run(media_clients.a, p, source, monkeypatch, True)["counts"]["identity_conflict"] == 1
    assert media_clients.a.get(f"/api/v1/brands/{brand['id']}").json()["name"] == "Producto"
    logo.unlink()
    assert run(media_clients.a, p, source, monkeypatch, True)["counts"]["missing_reference"] == 1
    assert media_clients.a.get(f"/api/v1/brands/{brand['id']}").json()["project_id"] == p["id"]


def test_api_key_apply_denied_and_private_credential_not_logged(
    media_clients, tmp_path, monkeypatch, capsys
):
    from scripts.import_brand_inventory import ImportInventoryError, import_inventory

    p = project(media_clients.a, "campaign")
    source, _ = inventory(tmp_path)
    with db.connect(media_clients.db_path) as con:
        tid = con.execute("SELECT id FROM tenants WHERE slug='alpha'").fetchone()["id"]
    key, _ = create_scoped_api_key(
        media_clients.db_path, tid, "Read", ["brands:read", "projects:read"]
    )
    monkeypatch.delenv("EIKON_OWNER_SESSION", raising=False)
    monkeypatch.setenv("EIKON_API_KEY", key)
    from fastapi.testclient import TestClient

    agent = TestClient(media_clients.a.app)
    try:
        assert import_inventory(agent, p["id"], source)["counts"]["create"] == 1
    finally:
        agent.close()
    with pytest.raises(ImportInventoryError) as exc:
        import_inventory(media_clients.a, p["id"], source, apply=True)
    assert key not in str(exc.value)
    assert key not in capsys.readouterr().out
    assert media_clients.a.get("/api/v1/brands").json()["items"] == []


def test_wrong_role_apply_denied(media_clients, tmp_path, monkeypatch):
    from scripts.import_brand_inventory import ImportInventoryError, import_inventory

    p = project(media_clients.a, "campaign")
    source, _ = inventory(tmp_path)
    monkeypatch.setenv("EIKON_OWNER_SESSION", media_clients.a.cookies.get("eikon_jwt"))
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE users SET role='member' WHERE email='alpha@example.test'")
    with pytest.raises(ImportInventoryError, match="propietario"):
        import_inventory(media_clients.a, p["id"], source, apply=True)


from webapp.tests.test_media_permissions import permission_db_clients as _permission_db_clients

permission_db_clients = _permission_db_clients


@pytest.fixture
def media_clients(permission_db_clients):
    a, b, url = permission_db_clients
    return SimpleNamespace(a=a, b=b, db_path=url, output_root=a.app.state.output_root)


def test_same_source_does_not_move_projects(media_clients, tmp_path, monkeypatch):
    source, _ = inventory(tmp_path)
    first = project(media_clients.a, "first")
    second = project(media_clients.a, "second")
    assert run(media_clients.a, first, source, monkeypatch, True)["counts"]["create"] == 1
    assert (
        run(media_clients.a, second, source, monkeypatch, True)["counts"]["identity_conflict"] == 1
    )
    brands = media_clients.a.get("/api/v1/brands").json()["items"]
    assert len(brands) == 1
    assert brands[0]["project_id"] == first["id"]


def test_reserved_combined_slug_and_data_uri(media_clients, tmp_path, monkeypatch):
    import base64

    source, logo = inventory(tmp_path, slug="pistis")
    contents = json.loads(source.read_text())
    contents["logo_asset"] = "data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode()
    source.write_text(json.dumps(contents))
    p = project(media_clients.a, "prizma")
    assert run(media_clients.a, p, source, monkeypatch, True)["counts"]["create"] == 1
    b = media_clients.a.get("/api/v1/brands").json()["items"][0]
    assert b["slug"] == "prizma-import-pistis"
    assert b["reference_logo_sha256"] == hashlib.sha256(logo.read_bytes()).hexdigest()


@pytest.mark.parametrize("alias_palette", [True, False])
def test_import_preserves_schema_palette_aliases_two_tenants(
    media_clients, tmp_path, monkeypatch, alias_palette
):
    from scripts.import_brand_inventory import _payload

    source, _ = inventory(tmp_path)
    expected = {"bg": "#123456", "acento": "#abcdef", "primario": "#543210", "acento_2": "#fedcba"}
    palette = (
        {"bg": "#123456", "accent": "#abcdef", "primary": "#543210", "secondary": "#fedcba"}
        if alias_palette
        else expected
    )
    data = json.loads(source.read_text())
    data["paleta"] = {**palette, "surface": "#333333"}
    source.write_text(json.dumps(data))
    for client in [media_clients.a, media_clients.b]:
        p = project(client, "campaign")
        assert _payload(data, p)["palette"] == expected
        assert run(client, p, source, monkeypatch)["counts"]["create"] == 1
        assert client.get("/api/v1/brands").json()["items"] == []
        assert run(client, p, source, monkeypatch, True)["counts"]["create"] == 1
        first = client.get("/api/v1/brands").json()["items"][0]
        assert first["palette"] == expected
        assert run(client, p, source, monkeypatch, True)["counts"]["skip_identical"] == 1
        assert client.get("/api/v1/brands").json()["items"] == [first]
