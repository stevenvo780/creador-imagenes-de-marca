"""El plan HTTP usa la familia explícita, con logo exacto o sin inventarlo."""

import base64
import json

import pytest

from eikon_core.brand import brand_family, load_json
from eikon_core.constants import MARCAS_DIR
from webapp.jobs.worker import WorkerPool
from webapp.tests.media_helpers import brand, project
from webapp.tests.test_client_reference_logo import batch, logo_bytes
from webapp.tests.test_client_reference_logo import isolated_db as _isolated_db
from webapp.tests.test_client_reference_logo import media_clients as _media_clients
from webapp.tests.test_client_reference_logo import permission_db_clients as _permission_db_clients

isolated_db = _isolated_db
media_clients = _media_clients
permission_db_clients = _permission_db_clients


def humanizar_brand(client):
    b = brand(client, project(client, "family")["id"], "prizma-family-explicit")
    response = client.put(
        f"/api/v1/brands/{b['id']}", json={"texts": {"brand_family": "humanizar"}}
    )
    assert response.status_code == 200, response.text
    return b


@pytest.mark.parametrize("logo_style", ["", "none"])
def test_family_without_original_does_not_generate_orbital(media_clients, logo_style):
    b = humanizar_brand(media_clients.a)
    if logo_style:
        response = media_clients.a.put(f"/api/v1/brands/{b['id']}", json={"logo_style": logo_style})
        assert response.status_code == 200, response.text
    bid = batch(media_clients.a, b["id"])
    plan = media_clients.a.get(f"/api/v1/batches/{bid}/plan")
    assert plan.status_code == 200, plan.text
    combo = plan.json()["combinations"][0]
    assert combo["isotype_data_uri"] is None
    assert combo["vars"]["brand_family"] == "humanizar"
    assert combo["vars"]["font_cuerpo"] == "Manrope"
    assert combo["vars"]["logo_simbolo"] == ""
    assert combo["texts"]["logo-texto"] == b["name"]
    assert media_clients.b.get(f"/api/v1/batches/{bid}/plan").status_code == 404


@pytest.mark.parametrize(
    "kind,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("SVG", "image/svg+xml")]
)
def test_family_keeps_original_bytes(media_clients, kind, mime):
    b = humanizar_brand(media_clients.a)
    original = logo_bytes(kind)
    upload = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/reference-logo", files={"file": ("original", original, mime)}
    )
    assert upload.status_code == 201, upload.text
    plan = media_clients.a.get(f"/api/v1/batches/{batch(media_clients.a, b['id'])}/plan")
    assert plan.status_code == 200, plan.text
    combo = plan.json()["combinations"][0]
    assert combo["vars"]["brand_family"] == "humanizar"
    assert combo["vars"]["logo_object_fit"] == "contain"
    assert base64.b64decode(combo["isotype_data_uri"].split(",")[1]) == original


def test_family_preserves_fixed_procedural_identity(media_clients):
    b = humanizar_brand(media_clients.a)
    update = media_clients.a.post(
        f"/api/v1/brands/{b['id']}/set-identity", json={"logo_style": "orbital", "logo_seed": 0}
    )
    assert update.status_code == 200, update.text
    plan = media_clients.a.get(f"/api/v1/batches/{batch(media_clients.a, b['id'])}/plan")
    assert plan.status_code == 200, plan.text
    assert plan.json()["combinations"][0]["isotype_data_uri"].startswith(
        "data:image/svg+xml;base64,"
    )


def test_social_family_template_is_available_to_studio(media_clients):
    response = media_clients.a.get("/api/v1/templates/social_4x5")
    assert response.status_code == 200, response.text
    assert "fonts/Manrope-wght.ttf" in response.text
    media_clients.a.post("/auth/logout")
    assert media_clients.a.get("/api/v1/templates/social_4x5").status_code == 401


def test_real_legacy_slug_collision_uses_explicit_tenant_profile_in_both_adapters(media_clients):
    slug = "prizma-iris"
    assert (MARCAS_DIR / f"{slug}.json").exists()
    own = brand(media_clients.a, project(media_clients.a, "own")["id"], slug)
    foreign = brand(media_clients.b, project(media_clients.b, "foreign")["id"], slug)
    response = media_clients.a.put(
        f"/api/v1/brands/{own['id']}",
        json={
            "name": "Producto propio Humanizar",
            "palette": {"acento": "#2563eb"},
            "texts": {
                "brand_family": "humanizar",
                "ig_post": {"titulo": "Contenido propio de esta empresa"},
            },
        },
    )
    assert response.status_code == 200, response.text
    own_id = batch(media_clients.a, own["id"])
    foreign_id = batch(media_clients.b, foreign["id"])
    own_plan = media_clients.a.get(f"/api/v1/batches/{own_id}/plan")
    assert own_plan.status_code == 200, own_plan.text
    combo = own_plan.json()["combinations"][0]
    assert combo["vars"]["brand_family"] == "humanizar"
    assert combo["vars"]["acento_2"] == "#2563eb"
    assert combo["texts"]["titulo"] == "Contenido propio de esta empresa"
    assert combo["texts"]["logo-texto"] == "Producto propio Humanizar"
    assert combo["isotype_data_uri"] is None

    foreign_plan = media_clients.b.get(f"/api/v1/batches/{foreign_id}/plan")
    assert foreign_plan.status_code == 200
    assert "brand_family" not in foreign_plan.json()["combinations"][0]["vars"]
    worker = WorkerPool(media_clients.db_path, max_concurrent_jobs=1)
    own_context = worker._load_batch_context(own_id, media_clients.db_path)
    foreign_context = worker._load_batch_context(foreign_id, media_clients.db_path)
    assert own_context is not None and foreign_context is not None
    own_marca = own_context[3]
    assert brand_family(own_marca) == "humanizar"
    assert own_marca["nombre_producto"] == "Producto propio Humanizar"
    assert own_marca["textos"]["ig_post"]["titulo"] == "Contenido propio de esta empresa"
    assert own_marca["paleta"]["acento"] == "#2563eb"
    assert brand_family(foreign_context[3]) == "prizma"
    assert (
        foreign_context[3]["nombre_producto"]
        == load_json(MARCAS_DIR / f"{slug}.json")["nombre_producto"]
    )


@pytest.mark.parametrize("family", ["humanizar", "legacy"])
def test_social_4x5_batch_plan_and_content_are_reachable(media_clients, family):
    b = brand(media_clients.a, project(media_clients.a, "social")["id"], "social-own")
    if family == "humanizar":
        response = media_clients.a.put(
            f"/api/v1/brands/{b['id']}",
            json={
                "texts": {
                    "brand_family": "humanizar",
                    "social_4x5": {
                        "titulo": "Pedidos en orden",
                        "subtitulo": "Una vista compartida",
                        "copy": "Contenido del producto real",
                    },
                },
            },
        )
        assert response.status_code == 200, response.text
    created = media_clients.a.post(
        "/api/v1/batches",
        json={
            "brand_id": b["id"],
            "asset_types": ["social_4x5"],
            "count": 1,
            "render_mode": "client",
        },
    )
    assert created.status_code == 202, created.text
    bid = created.json()["id"]
    response = media_clients.a.get(f"/api/v1/batches/{bid}/plan")
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["asset_type"] == "social_4x5"
    assert plan["template_name"] == "social_4x5"
    assert plan["viewport"] == {"w": 1080, "h": 1350}
    assert media_clients.a.get("/api/v1/templates/" + plan["template_name"]).status_code == 200
    assert media_clients.b.get(f"/api/v1/batches/{bid}/plan").status_code == 404
    combo = plan["combinations"][0]
    if family == "humanizar":
        assert combo["isotype_data_uri"] is None
        assert combo["texts"]["titulo"] == "Pedidos en orden"
        assert combo["texts"]["subtitulo"] == "Una vista compartida"
        assert combo["texts"]["copy"] == "Contenido del producto real"
        assert combo["texts"]["etiqueta"] == "de Humanizar Systems"
        assert combo["texts"]["numero"] == ""
        assert combo["vars"]["numero_2"] == ""
    else:
        assert "brand_family" not in combo["vars"]
        assert combo["isotype_data_uri"].startswith("data:image/svg+xml;base64,")


def test_social_4x5_is_registered_in_layout_catalog():
    layouts = json.loads((MARCAS_DIR.parent / "config/layouts.json").read_text())["layouts"]
    matching = [layout for layout in layouts if layout["id"] == "social_4x5"]
    assert len(matching) == 1
    assert matching[0]["template"] == "social_4x5.html"
    assert matching[0]["ancho"] == 1080
    assert matching[0]["alto"] == 1350
