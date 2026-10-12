"""Contratos exactos, aislamiento y autenticación de candidatos en dos motores."""

import hashlib
import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.app import create_app
from webapp.config import Settings
from webapp.tests.media_helpers import brand, brief, image_bytes, project, upload
from webapp.tests.test_projects import isolated_db as _isolated_db
from webapp.tests.test_publication_oauth import ProviderDouble
from webapp.tests.test_publication_policies import policy_payload

isolated_db = _isolated_db


@pytest.fixture
def campaign_clients(isolated_db, tmp_path, monkeypatch):
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    app = create_app(
        Settings(db_url=str(isolated_db), jwt_secret=secrets.token_urlsafe(48)),
        output_root=tmp_path / "output",
    )
    clients = [TestClient(app), TestClient(app)]
    try:
        for client, slug in zip(clients, ("alpha", "beta"), strict=True):
            assert (
                client.post(
                    "/auth/register",
                    json={
                        "tenant_slug": slug,
                        "tenant_name": slug,
                        "email": f"{slug}@example.test",
                        "password": "password123",
                    },
                ).status_code
                == 201
            )
        yield clients, isolated_db, app
    finally:
        for client in clients:
            client.close()


@pytest.fixture
def campaign_case(campaign_clients):
    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import import_credential
    from webapp.publications.policies import set_policy

    clients, url, app = campaign_clients
    cases = []
    for client, slug in zip(clients, ("alpha", "beta"), strict=True):
        p = project(client, slug)
        b = brand(client, p["id"], slug)
        job = brief(client, b["id"])
        piece = upload(client, job["id"], "piece", image_bytes()).json()
        me = client.get("/auth/me").json()
        tenant, owner = me["tenant"]["id"], me["user"]["id"]
        account = put_connection(
            url,
            tenant,
            owner,
            {
                "platform": "facebook",
                "api_mode": "page",
                "remote_id": "page-42",
                "project_ids": [p["id"]],
            },
        )
        account = import_credential(
            url,
            tenant,
            owner,
            account["id"],
            {"access_token": "fake-token"},
            int(time.time()),
            ProviderDouble(expires_at=9999999999),
            key=b"k" * 32,
            key_id="test",
            dry_run=False,
        )
        policy = set_policy(url, tenant, owner, 0, policy_payload(p["id"], b["id"], account["id"]))
        cases.append(
            dict(
                client=client,
                tenant=tenant,
                owner=owner,
                project=p,
                brand=b,
                brief=job,
                media=piece,
                connection=account,
                policy=policy,
            )
        )
    return url, cases, app


def freeze(url, case, campaign, **changes):
    from webapp.publications.campaigns import freeze_revision

    args = dict(
        media_id=case["media"]["id"],
        caption="Producto",
        connection_id=case["connection"]["id"],
        scheduled_at="2026-10-12T00:30:00Z",
        policy_version=1,
        channel_metadata={
            "sources": ["https://example.test/manual"],
            "rights": "owned",
            "context": "Lanzamiento",
        },
    )
    return freeze_revision(url, case["tenant"], campaign["id"], **(args | changes))


def campaign(url, case):
    from webapp.publications.campaigns import create_campaign

    return create_campaign(
        url,
        case["tenant"],
        case["owner"],
        case["project"]["id"],
        case["brand"]["id"],
        "Presentar producto",
    )


def test_revision_freezes_exact_bytes_identity_copy_and_destination(campaign_case):
    from webapp.publications.campaigns import get_revision

    url, (a, b), _ = campaign_case
    c = campaign(url, a)
    r = freeze(url, a, c)
    s = r["snapshot"]
    assert s["media"]["sha256"] == hashlib.sha256(image_bytes()).hexdigest()
    assert s["media"]["kind"] == "gallery_image"
    assert s["brief"]["id"] == a["brief"]["id"]
    assert s["brief"]["prompt"] == "Pieza de prueba"
    assert s["destination"] == "facebook:page-42"
    assert s["connection"]["version"] == a["connection"]["version"]
    assert s["scheduled_at_utc"] == 1791765000
    assert s["policy_timezone"] == "America/Bogota"
    assert s["scheduled_local_date"] == "2026-10-11"
    assert s["expires_at_utc"] == 1791768600
    assert s["visual_review"]["approval_current"] is False
    assert s["media"]["status"] == "pending_review"
    assert r["eligibility_reasons"] == []
    assert r["contract_hash"] == hashlib.sha256(r["frozen_json"].encode()).hexdigest()
    assert "fake-token" not in json.dumps(r) and "ciphertext" not in json.dumps(r)
    assert get_revision(url, a["tenant"], r["id"])["frozen_json"] == r["frozen_json"]
    from webapp.publications.contracts import NotFound

    with pytest.raises(NotFound):
        get_revision(url, b["tenant"], r["id"])
    assert a["client"].get(f"/api/v1/media/{a['media']['id']}").json()["approval_current"] is False


def test_edits_insert_revision_and_equivalent_offsets_hash_identically(campaign_case):
    url, (a, _), _ = campaign_case
    c = campaign(url, a)
    r = freeze(url, a, c)
    equivalent = freeze(url, a, c, scheduled_at="2026-10-11T19:30:00-05:00")
    edited = freeze(url, a, c, caption="Otro producto")
    assert r["id"] != equivalent["id"] != edited["id"]
    assert r["contract_hash"] == equivalent["contract_hash"]
    assert r["contract_hash"] != edited["contract_hash"]
    from webapp.publications.campaigns import get_revision

    assert get_revision(url, a["tenant"], r["id"])["snapshot"]["caption"] == "Producto"


@pytest.mark.parametrize(
    "field,value",
    [
        ("caption", ""),
        ("caption", 123),
        ("channel_metadata", {"token": "no"}),
        ("channel_metadata", {"rights": 1}),
        ("channel_metadata", {"links": ["https://user:pass@example.test"]}),
        ("scheduled_at", "2026-11-01T01:30:00"),
        ("media_kind", "unknown"),
    ],
)
def test_invalid_copy_metadata_or_ambiguous_schedule_rejected(campaign_case, field, value):
    from webapp.publications.contracts import InvalidInput

    url, (a, _), _ = campaign_case
    with pytest.raises(InvalidInput):
        freeze(url, a, campaign(url, a), **{field: value})


@pytest.mark.parametrize("foreign", ["media", "connection", "project", "brand"])
def test_foreign_catalog_cannot_be_bound(campaign_case, foreign):
    from webapp.publications.campaigns import create_campaign
    from webapp.publications.contracts import PublicationError

    url, (a, b), _ = campaign_case
    with pytest.raises(PublicationError):
        if foreign in ("project", "brand"):
            create_campaign(
                url,
                a["tenant"],
                a["owner"],
                b["project"]["id"] if foreign == "project" else a["project"]["id"],
                b["brand"]["id"] if foreign == "brand" else a["brand"]["id"],
                "Objetivo",
            )
        else:
            freeze(url, a, campaign(url, a), **{f"{foreign}_id": b[foreign]["id"]})


@pytest.mark.parametrize("state", ["rejected", "archived"])
def test_owner_media_hold_and_archived_campaign_block_new_revisions(campaign_case, state):
    from webapp.publications.campaigns import archive_campaign
    from webapp.publications.contracts import Conflict

    url, (a, _), _ = campaign_case
    c = campaign(url, a)
    with db.connect(url) as con:
        con.execute(
            "UPDATE media_assets SET status=? WHERE tenant_id=? AND id=?",
            (state, a["tenant"], a["media"]["id"]),
        )
    with pytest.raises(Conflict, match="media_unavailable"):
        freeze(url, a, c)
    archive_campaign(url, a["tenant"], a["owner"], c["id"])
    with pytest.raises(Conflict, match="campaign_archived"):
        freeze(url, a, c)


def test_candidate_routes_are_tenant_scoped_and_old_keys_have_no_authority(campaign_case):
    from webapp.publications.auth import issue_grant

    url, (a, b), app = campaign_case
    c = campaign(url, a)
    r = freeze(url, a, c)
    token, _ = issue_grant(
        url, a["tenant"], a["owner"], "planner", "own-codex", 1, int(time.time()) + 600
    )
    client = TestClient(app)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/publications/planner/candidates?limit=1", headers=headers)
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [r["id"]]
        assert b["client"].get(f"/api/v1/publications/revisions/{r['id']}").status_code == 404
        old = (
            a["client"]
            .post("/api/v1/auth/api-keys", json={"name": "old", "scopes": ["media:write"]})
            .json()["key"]
        )
        assert (
            client.get(
                "/api/v1/publications/planner/candidates",
                headers={"Authorization": f"Bearer {old}"},
            ).status_code
            == 403
        )
        assert client.post(
            "/api/v1/publications/campaigns", headers=headers, json={}
        ).status_code in (401, 403)
    finally:
        client.close()


def test_connection_change_keeps_snapshot_but_holds_candidate(campaign_case):
    from webapp.publications.campaigns import get_revision
    from webapp.publications.connections import put_connection

    url, (a, _), _ = campaign_case
    r = freeze(url, a, campaign(url, a))
    put_connection(
        url,
        a["tenant"],
        a["owner"],
        {
            "id": a["connection"]["id"],
            "expected_version": a["connection"]["version"],
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "page-other",
            "project_ids": [a["project"]["id"]],
        },
    )
    current = get_revision(url, a["tenant"], r["id"])
    assert current["frozen_json"] == r["frozen_json"]
    assert "connection_changed" in current["eligibility_reasons"]


@pytest.mark.parametrize(
    "platform,mode", [("instagram", "instagram_login"), ("tiktok", "oauth2"), ("x", "oauth2")]
)
def test_platforms_keep_own_contract_and_external_hold_reasons(campaign_case, platform, mode):
    from webapp.publications.connections import put_connection
    from webapp.publications.policies import set_policy

    url, (a, _), _ = campaign_case
    account = put_connection(
        url,
        a["tenant"],
        a["owner"],
        {
            "platform": platform,
            "api_mode": mode,
            "remote_id": "remote-72",
            "project_ids": [a["project"]["id"]],
        },
    )
    # Deshabilitada permite preparar contratos; jamás inventa cuenta autorizada.
    policy = set_policy(
        url,
        a["tenant"],
        a["owner"],
        1,
        {**policy_payload(a["project"]["id"], a["brand"]["id"], account["id"]), "enabled": False},
    )
    c = campaign(url, a)
    r = freeze(
        url,
        a,
        c,
        connection_id=account["id"],
        policy_version=policy["version"],
        channel_metadata={
            "rights": "owned",
            "privacy": "SELF_ONLY",
            "commercial_content": True,
            "branded_content": False,
            "sources": ["https://example.test/manual"],
        },
    )
    assert r["snapshot"]["destination"] == f"{platform}:remote-72"
    assert "connection_unavailable" in r["eligibility_reasons"]
    if platform == "tiktok":
        assert {"needs_platform_consent", "needs_platform_audit"} <= set(r["eligibility_reasons"])
    if platform == "x":
        assert "blocked_budget" in r["eligibility_reasons"]
    fb = freeze(url, a, c)
    assert fb["contract_hash"] != r["contract_hash"]


def test_caption_and_account_each_change_contract(campaign_case):
    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import import_credential

    url, (a, _), _ = campaign_case
    account = put_connection(
        url,
        a["tenant"],
        a["owner"],
        {
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "page-72",
            "project_ids": [a["project"]["id"]],
        },
    )
    import_credential(
        url,
        a["tenant"],
        a["owner"],
        account["id"],
        {"access_token": "fake-token"},
        int(time.time()),
        ProviderDouble(remote_id="page-72", expires_at=9999999999),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    c = campaign(url, a)
    original = freeze(url, a, c)
    changed = freeze(url, a, c, connection_id=account["id"])
    assert original["contract_hash"] != changed["contract_hash"]
    assert "outside_policy_scope" in changed["eligibility_reasons"]


def test_revision_sql_update_or_delete_cannot_rewrite_history(campaign_case):
    import sqlite3

    import psycopg

    url, (a, _), _ = campaign_case
    r = freeze(url, a, campaign(url, a))
    for query in (
        "UPDATE publication_revisions SET frozen_json='{}' WHERE tenant_id=? AND id=?",
        "DELETE FROM publication_revisions WHERE tenant_id=? AND id=?",
    ):
        with (
            pytest.raises((sqlite3.IntegrityError, psycopg.errors.RaiseException)),
            db.connect(url) as con,
        ):
            con.execute(query, (a["tenant"], r["id"]))


def test_planner_revocation_and_wrong_role_block_function_calls(campaign_case):
    from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
    from webapp.publications.campaigns import list_candidates
    from webapp.publications.contracts import Forbidden

    url, (a, _), _ = campaign_case
    token, grant = issue_grant(
        url, a["tenant"], a["owner"], "planner", "codex", 1, int(time.time()) + 600
    )
    principal = resolve_grant(url, token, "planner", int(time.time()))
    revoke_grant(url, a["tenant"], a["owner"], grant["id"])
    with pytest.raises(Forbidden):
        list_candidates(url, principal)
    with pytest.raises(Forbidden):
        list_candidates(url, {**principal, "role": "reviewer"})


def test_identity_change_holds_old_exact_snapshot(campaign_case):
    from webapp.publications.campaigns import get_revision

    url, (a, _), _ = campaign_case
    r = freeze(url, a, campaign(url, a))
    with db.connect(url) as con:
        con.execute(
            "UPDATE brands SET brand_version=brand_version+1 WHERE tenant_id=? AND id=?",
            (a["tenant"], a["brand"]["id"]),
        )
    current = get_revision(url, a["tenant"], r["id"])
    assert "identity_changed" in current["eligibility_reasons"]
    assert current["frozen_json"] == r["frozen_json"]


def test_freeze_revalidates_planner_inside_write_transaction(campaign_case):
    from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
    from webapp.publications.contracts import Forbidden

    url, (a, _), _ = campaign_case
    c = campaign(url, a)
    token, grant = issue_grant(
        url, a["tenant"], a["owner"], "planner", "codex", 1, int(time.time()) + 600
    )
    principal = resolve_grant(url, token, "planner", int(time.time()))
    revoke_grant(url, a["tenant"], a["owner"], grant["id"])
    with pytest.raises(Forbidden):
        freeze(url, a, c, actor=principal)


def test_link_and_caption_are_exact_even_when_source_url_normalized(campaign_case):
    url, (a, _), _ = campaign_case
    r = freeze(
        url,
        a,
        campaign(url, a),
        caption="  Texto exacto\n",
        channel_metadata={
            "links": ["https://EXAMPLE.test:443/product#buy"],
            "sources": ["https://EXAMPLE.test:443/manual#section"],
            "rights": "owned",
        },
    )
    assert r["snapshot"]["caption"] == "  Texto exacto\n"
    assert r["snapshot"]["channel_metadata"]["links"] == ["https://EXAMPLE.test:443/product#buy"]
    assert r["snapshot"]["channel_metadata"]["sources"] == ["https://example.test/manual"]


def test_owner_and_planner_prepare_campaign_and_revision_routes(campaign_case):
    from webapp.publications.auth import issue_grant

    url, (a, _), app = campaign_case
    body = {
        "project_id": a["project"]["id"],
        "brand_id": a["brand"]["id"],
        "objective": "Presentación",
    }
    revision_body = {
        "media_id": a["media"]["id"],
        "caption": "Texto final",
        "connection_id": a["connection"]["id"],
        "scheduled_at": "2026-10-12T14:00:00Z",
        "policy_version": 1,
        "channel_metadata": {"rights": "owned", "sources": ["https://example.test/manual"]},
    }
    owner_campaign = a["client"].post("/api/v1/publications/campaigns", json=body)
    assert owner_campaign.status_code == 201
    owner_revision = a["client"].post(
        f"/api/v1/publications/campaigns/{owner_campaign.json()['id']}/revisions",
        json=revision_body,
    )
    assert owner_revision.status_code == 201, owner_revision.text
    token, _ = issue_grant(
        url, a["tenant"], a["owner"], "planner", "codex", 1, int(time.time()) + 600
    )
    client = TestClient(app)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        planner_campaign = client.post(
            "/api/v1/publications/planner/campaigns", headers=headers, json=body
        )
        assert planner_campaign.status_code == 201, planner_campaign.text
        planner_revision = client.post(
            f"/api/v1/publications/planner/campaigns/{planner_campaign.json()['id']}/revisions",
            headers=headers,
            json=revision_body,
        )
        assert planner_revision.status_code == 201, planner_revision.text
        assert planner_revision.json()["snapshot"]["caption"] == "Texto final"
    finally:
        client.close()


def test_jpeg_variant_has_own_original_hash_and_revision(campaign_case):
    import io

    from PIL import Image

    url, (a, _), _ = campaign_case
    jpeg = io.BytesIO()
    Image.new("RGB", (512, 512), "teal").save(jpeg, format="JPEG")
    content = jpeg.getvalue()
    response = a["client"].post(
        "/api/v1/media",
        headers={"Idempotency-Key": "jpeg"},
        data={
            "brief_id": a["brief"]["id"],
            "source": "codex",
            "provenance": '{"tool":"variant-conversion"}',
        },
        files={"file": ("variant.jpeg", content, "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    c = campaign(url, a)
    original = freeze(url, a, c)
    variant = freeze(url, a, c, media_id=response.json()["id"])
    assert variant["snapshot"]["media"]["mime"] == "image/jpeg"
    assert variant["snapshot"]["media"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert original["contract_hash"] != variant["contract_hash"]
    assert original["snapshot"]["media"]["sha256"] == hashlib.sha256(image_bytes()).hexdigest()


def test_campaign_schema_migration_rollback_no_seeds_and_idempotency(isolated_db, monkeypatch):
    from webapp.publications.migrations import migrate_publications

    db.init_db(isolated_db)
    with db.connect(isolated_db) as con:
        for table in ("publication_revisions", "publication_video_media", "publication_campaigns"):
            con.execute(f"DROP TABLE {table}")
        con.execute("DELETE FROM schema_migrations WHERE version='publication_campaigns_v1'")
    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if (
            sql.startswith("INSERT INTO schema_migrations")
            and params[0] == "publication_campaigns_v1"
        ):
            raise RuntimeError("injected-campaign-marker")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="injected-campaign-marker"):
            migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        if con.dialect == "sqlite":
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE name='publication_campaigns'"
            ).fetchone()
        else:
            row = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='publication_campaigns'"
            ).fetchone()
        assert row is None
    migrate_publications(isolated_db)
    migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM schema_migrations WHERE version='publication_campaigns_v1'"
            ).fetchone()["n"]
            == 1
        )
        for table in ("publication_revisions", "publication_video_media", "publication_campaigns"):
            assert con.execute(f"SELECT * FROM {table}").fetchall() == []
