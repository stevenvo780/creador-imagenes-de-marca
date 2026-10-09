"""Revisión humana tenant-scoped de originales/versiones inmutables."""

from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.tests.media_helpers import image_bytes, upload
from webapp.tests.test_media_ingest import isolated_db as _isolated_db
from webapp.tests.test_media_ingest import job as _job
from webapp.tests.test_media_ingest import media_clients as _media_clients
from webapp.tests.test_media_ingest import permission_db_clients as _permission_db_clients

isolated_db = _isolated_db
job = _job
media_clients = _media_clients
permission_db_clients = _permission_db_clients


def review(client, asset, **changes):
    payload = {
        "decision": "approved",
        "expected_sha256": asset["sha256"],
        "expected_brand_version": asset["brand_version"],
        "reason": "Logo y texto revisados",
    }
    payload.update(changes)
    return client.post(f"/api/v1/media/{asset['id']}/reviews", json=payload)


def test_review_append_only_and_keys_cannot_review(media_clients, job):
    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    with closing(TestClient(media_clients.a.app)) as agent:
        key = media_clients.a.post(
            "/api/v1/auth/api-keys",
            json={"name": "reader", "scopes": ["media:read", "media:write"]},
        ).json()["key"]
        agent.headers["Authorization"] = f"Bearer {key}"
        assert review(agent, asset).status_code == 403
    assert review(media_clients.b, asset).status_code == 404
    assert review(media_clients.a, asset).status_code == 201
    assert review(media_clients.a, asset, decision="rejected", reason=" ").status_code == 422
    assert (
        review(media_clients.a, asset, decision="rejected", reason="Corregir texto").status_code
        == 201
    )
    assert review(media_clients.a, asset).status_code == 201
    result = media_clients.a.get(f"/api/v1/media/{asset['id']}").json()
    assert result["status"] == "approved" and result["approval_current"] is True
    assert [r["decision"] for r in result["reviews"]] == ["approved", "rejected", "approved"]
    assert all(r["sha256"] == asset["sha256"] for r in result["reviews"])
    assert media_clients.a.get("/api/v1/media?status=approved").json()["items"] == [result]
    with db.connect(media_clients.db_path) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM asset_reviews").fetchone()["n"] == 3


@pytest.mark.parametrize("change", ["hash", "version", "identity", "archive", "asset_archived"])
def test_review_conflicts_preserve_history(media_clients, job, change):
    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    assert review(media_clients.a, asset).status_code == 201
    changes = {}
    if change == "hash":
        changes["expected_sha256"] = "0" * 64
    elif change == "version":
        changes["expected_brand_version"] = asset["brand_version"] + 1
    elif change == "identity":
        media_clients.a.put(f"/api/v1/brands/{job['brand_id']}", json={"name": "Changed"})
    elif change == "archive":
        media_clients.a.post(f"/api/v1/projects/{job['project_id']}/archive")
    else:
        with db.connect(media_clients.db_path) as con:
            con.execute("UPDATE media_assets SET status = 'archived' WHERE id = ?", (asset["id"],))
    assert review(media_clients.a, asset, **changes).status_code == 409
    result = media_clients.a.get(f"/api/v1/media/{asset['id']}").json()
    assert len(result["reviews"]) == 1
    if change in {"identity", "archive"}:
        assert result["status"] == "pending_review" and result["approval_current"] is False
        assert media_clients.a.get("/api/v1/media?status=approved").json()["items"] == []
        assert upload(media_clients.a, job["id"], "one", image_bytes()).status_code == 409


def test_owner_downgrade_checked_inside_review_transaction(media_clients, job):
    from webapp.api.media_reviews import review_media

    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    me = media_clients.a.get("/auth/me").json()
    with db.connect(media_clients.db_path) as con:
        con.execute("UPDATE users SET role = 'member' WHERE id = ?", (me["user"]["id"],))
    assert review(media_clients.a, asset).status_code == 403
    with pytest.raises(PermissionError):
        review_media(
            media_clients.db_path,
            me["tenant"]["id"],
            asset["id"],
            me["user"]["id"],
            "approved",
            asset["sha256"],
            asset["brand_version"],
            "checked",
        )
    with db.connect(media_clients.db_path) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM asset_reviews").fetchone()["n"] == 0


def test_expired_brief_can_be_reviewed_and_original_is_unchanged(media_clients, job):
    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    with db.connect(media_clients.db_path) as con:
        before = con.execute("SELECT * FROM media_assets WHERE id = ?", (asset["id"],)).fetchone()
        con.execute("UPDATE generation_briefs SET expires_at = 0 WHERE id = ?", (job["id"],))
    assert review(media_clients.a, asset).status_code == 201
    with db.connect(media_clients.db_path) as con:
        after = con.execute("SELECT * FROM media_assets WHERE id = ?", (asset["id"],)).fetchone()
    assert {k: v for k, v in before.items() if k not in {"status", "updated_at"}} == {
        k: v for k, v in after.items() if k not in {"status", "updated_at"}
    }
    assert media_clients.storage.open(before["tenant_id"], before["original_key"]) == image_bytes()


def test_review_migration_is_additive_idempotent(media_clients, job):
    from webapp.migrations import migrate_media_reviews

    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    assert review(media_clients.a, asset).status_code == 201
    with db.connect(media_clients.db_path) as con:
        before = con.execute("SELECT * FROM media_assets WHERE id = ?", (asset["id"],)).fetchone()
        reviews = con.execute("SELECT * FROM asset_reviews").fetchall()
    migrate_media_reviews(media_clients.db_path)
    migrate_media_reviews(media_clients.db_path)
    with db.connect(media_clients.db_path) as con:
        assert (
            con.execute("SELECT * FROM media_assets WHERE id = ?", (asset["id"],)).fetchone()
            == before
        )
        assert con.execute("SELECT * FROM asset_reviews").fetchall() == reviews
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM schema_migrations WHERE version = 'media_reviews_v1'"
            ).fetchone()["n"]
            == 1
        )


def test_helper_rejects_foreign_reviewer_and_media(media_clients, job):
    from webapp.api.media_reviews import review_media

    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    a = media_clients.a.get("/auth/me").json()
    b = media_clients.b.get("/auth/me").json()
    with pytest.raises(PermissionError):
        review_media(
            media_clients.db_path,
            a["tenant"]["id"],
            asset["id"],
            b["user"]["id"],
            "approved",
            asset["sha256"],
            asset["brand_version"],
            "checked",
        )
    with pytest.raises(KeyError):
        review_media(
            media_clients.db_path,
            b["tenant"]["id"],
            asset["id"],
            b["user"]["id"],
            "approved",
            asset["sha256"],
            asset["brand_version"],
            "checked",
        )


def test_changed_project_description_revokes_approval(media_clients, job):
    asset = upload(media_clients.a, job["id"], "one", image_bytes()).json()
    assert review(media_clients.a, asset).status_code == 201
    media_clients.a.patch(
        f"/api/v1/projects/{job['project_id']}", json={"description": "Nuevo contexto"}
    )
    result = media_clients.a.get(f"/api/v1/media/{asset['id']}").json()
    assert result["status"] == "pending_review" and result["approval_current"] is False
    assert review(media_clients.a, asset).status_code == 409
    assert len(result["reviews"]) == 1
