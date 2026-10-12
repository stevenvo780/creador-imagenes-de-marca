"""Read model público real: aislamiento, whitelist y recibos conservadores."""

from webapp import db
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case,
    campaign_clients,
    delivery_case,
    isolated_db,
    scheduled,
)

__all__ = ["campaign_case", "campaign_clients", "delivery_case", "isolated_db"]


def test_owner_overview_campaign_and_delivery_are_private_and_scoped(delivery_case):
    c = delivery_case
    delivery = scheduled(c)
    a, b = c["a"]["client"], c["b"]["client"]
    base = "/api/v1/publications"
    overview = a.get(base + "/overview")
    assert overview.status_code == 200
    assert overview.headers["cache-control"] == "private, no-store"
    data = overview.json()
    assert data["tenant"]["id"] == c["a"]["tenant"]
    assert data["campaigns"]["items"][0]["project_id"] == c["a"]["project"]["id"]
    revision = data["campaigns"]["items"][0]["revisions"][0]
    assert revision["decision"]["outcome"] == "approve"
    assert revision["media"]["sha256"] == c["a"]["media"]["sha256"]
    assert revision["visual_review"]["approval_current"] is False
    assert "frozen_json" not in revision and "snapshot" not in revision
    assert "fake-token" not in overview.text and "ciphertext" not in overview.text
    detail = a.get(base + f"/deliveries/{delivery['id']}")
    assert detail.status_code == 200 and detail.json()["state"] == "scheduled"
    assert b.get(base + f"/deliveries/{delivery['id']}").status_code == 404
    assert b.get(base + "/campaigns").json()["items"] == []
    assert a.get(base + "/campaigns?limit=101").status_code == 422
    with db.connect(c["url"]) as con:
        con.execute(
            "UPDATE users SET role='member' WHERE tenant_id=? AND id=?",
            (c["a"]["tenant"], c["a"]["owner"]),
        )
    assert a.get(base + "/overview").status_code == 403


def test_public_view_never_promotes_uncertain_receipt(delivery_case):
    import json

    c = delivery_case
    delivery = scheduled(c)
    with db.connect(c["url"]) as con:
        con.execute(
            "UPDATE publication_deliveries SET state='uncertain',result_json=? WHERE tenant_id=? AND id=?",
            (
                json.dumps(
                    {
                        "state": "uncertain",
                        "remote_id": "pending-id",
                        "permalink": "https://example.test/post",
                        "evidence": {"secret": "not-public"},
                    }
                ),
                c["a"]["tenant"],
                delivery["id"],
            ),
        )
    result = c["a"]["client"].get(f"/api/v1/publications/deliveries/{delivery['id']}")
    assert result.status_code == 200
    assert result.json()["result"]["permalink"] is None
    assert "not-public" not in result.text


def test_owner_edit_creates_new_hash_without_reusing_ai_decision(delivery_case):
    c = delivery_case
    r = c["revision"]
    s = r["snapshot"]
    client = c["a"]["client"]
    result = client.post(
        f"/api/v1/publications/campaigns/{r['campaign_id']}/revisions",
        json={
            "media_id": s["media"]["id"],
            "media_kind": s["media"]["kind"],
            "caption": "Texto modificado",
            "connection_id": s["connection"]["id"],
            "scheduled_at": "2080-10-12T00:30:00Z",
            "policy_version": s["policy_version"],
            "channel_metadata": s["channel_metadata"] | {"privacy": "SELF_ONLY"},
        },
    )
    assert result.status_code == 201, result.text
    new = result.json()
    assert new["id"] != r["id"] and new["contract_hash"] != r["contract_hash"]
    campaign = client.get("/api/v1/publications/campaigns").json()["items"][0]
    assert (
        campaign["revisions"][0]["id"] == new["id"] and campaign["revisions"][0]["decision"] is None
    )
    assert campaign["revisions"][1]["decision"]["outcome"] == "approve"
    preview = client.get(
        f"/api/v1/publications/revisions/{new['id']}/preview",
        params={"contract_hash": new["contract_hash"]},
    )
    assert preview.status_code == 200 and preview.headers["cache-control"] == "private, no-store"
    import hashlib

    assert hashlib.sha256(preview.content).hexdigest() == s["media"]["sha256"]
    assert (
        c["b"]["client"]
        .get(
            f"/api/v1/publications/revisions/{new['id']}/preview",
            params={"contract_hash": new["contract_hash"]},
        )
        .status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/publications/revisions/{new['id']}/preview",
            params={"contract_hash": "0" * 64},
        ).status_code
        == 409
    )
