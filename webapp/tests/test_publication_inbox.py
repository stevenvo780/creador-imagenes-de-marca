"""Bandeja local dual: capacidad real, stock exacto y ninguna decisión fabricada."""

import json
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.publications.auth import issue_grant, revoke_grant
from webapp.publications.decisions import append_ai_decision
from webapp.publications.deliveries import schedule_revision
from webapp.tests.test_publication_campaigns import campaign, freeze
from webapp.tests.test_publication_decisions import (
    campaign_case,
    campaign_clients,
    decision_case,
    evaluated,
    isolated_db,
)
from webapp.tests.test_publication_delivery_concurrency import history

__all__ = ["campaign_case", "campaign_clients", "decision_case", "isolated_db"]
ROUTE = "/api/v1/publications/planner/inbox"


def planner(c):
    token, grant = issue_grant(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        "planner",
        "own-planner",
        1,
        int(time.time()) + 600,
    )
    return {"Authorization": "Bearer " + token}, grant


def get(c, headers, **params):
    client = TestClient(c["app"])
    try:
        return client.get(ROUTE, headers=headers, params=params)
    finally:
        client.close()


def today_revision(c, stamp=None):
    r = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        scheduled_at=datetime.fromtimestamp(stamp or int(time.time()), UTC).isoformat(),
    )
    return c | {"revision": r}


def authorize(c):
    history(c)
    append_ai_decision(c["url"], c["principal"], evaluated(c), int(time.time()))
    return schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], int(time.time()))


def counts(c):
    with db.connect(c["url"]) as con:
        return tuple(
            con.execute(
                f"SELECT COUNT(*) n FROM {table} WHERE tenant_id=?", (c["a"]["tenant"],)
            ).fetchone()["n"]
            for table in (
                "publication_material_deliveries",
                "publication_evaluations",
                "publication_ai_decisions",
                "publication_deliveries",
                "publication_events",
            )
        )


def test_inbox_pending_is_deficit_not_authorized_stock_and_read_is_no_write(decision_case):
    c = today_revision(decision_case)
    headers, _ = planner(c)
    before = counts(c)
    result = get(c, headers)
    assert result.status_code == 200
    body = result.json()
    assert body["timezone"] == "America/Bogota"
    assert body["day"] == datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
    assert isinstance(body["as_of"], int) and body["stock_target"] == 1
    assert body["policy"]["version"] == 1 and "owner_id" not in body["policy"]
    account = body["accounts"][0]
    assert account["authorized_stock"] == 0 and account["deficit"] == 1
    pending = next(
        r for r in account["pending_candidates"] if r["revision_id"] == c["revision"]["id"]
    )
    assert "ai_decision_required" in pending["reasons"]
    assert account["remaining_daily_capacity"] == 2
    assert counts(c) == before
    assert result.headers["cache-control"] == "private, no-store"
    assert "fake-token" not in json.dumps(body) and "ciphertext" not in json.dumps(body)


def test_inbox_counts_unique_valid_deliveries_only_and_excludes_tomorrow(decision_case):
    c = today_revision(decision_case)
    headers, _ = planner(c)
    delivery = authorize(c)
    assert delivery["state"] == "scheduled"
    # Mismo SHA/destino: otra revisión no duplica el stock, tampoco la pending original.
    duplicate = today_revision(c)
    authorize(duplicate)
    tomorrow = datetime.now(ZoneInfo("America/Bogota")).date() + timedelta(days=1)
    future = datetime.combine(tomorrow, datetime.min.time(), ZoneInfo("America/Bogota")).timestamp()
    authorize(today_revision(c, int(future)))
    before = counts(c)
    account = get(c, headers, stock_target=2).json()["accounts"][0]
    assert account["authorized_stock"] == 1 and len(account["stock"]) == 1
    assert account["deficit"] == 1
    assert account["remaining_daily_capacity"] == 2  # Scheduled no es intento ni cuota gastada.
    assert counts(c) == before
    revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["grant"]["id"])
    account = get(c, headers).json()["accounts"][0]
    assert account["authorized_stock"] == 0 and account["deficit"] == 1
    assert any(
        "reviewer_authorization_unavailable" in r["reasons"] for r in account["held_deliveries"]
    )


def test_inbox_refuses_foreign_roles_old_keys_invalid_queries_and_revocation(decision_case):
    c = today_revision(decision_case)
    headers, grant = planner(c)
    foreign = c["b"]
    ft, _ = issue_grant(
        c["url"],
        foreign["tenant"],
        foreign["owner"],
        "planner",
        "foreign",
        1,
        int(time.time()) + 600,
    )
    body = get(c, {"Authorization": "Bearer " + ft}).json()
    assert body["tenant_id"] == foreign["tenant"]
    assert body["campaigns"]["items"] == []
    assert all(a["connection"]["id"] != c["a"]["connection"]["id"] for a in body["accounts"])
    assert get(c, {"Authorization": "Bearer " + c["token"]}).status_code == 403
    assert get(c, {"Authorization": "Bearer eikon_key_legacy"}).status_code == 403
    for params in (
        {"stock_target": 0},
        {"stock_target": 101},
        {"stock_target": "true"},
        {"cursor": -1},
        {"limit": 0},
        {"limit": 101},
    ):
        assert get(c, headers, **params).status_code == 422
    assert get(c, headers, stock_target="1", cursor="0", limit="1").status_code == 200
    revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], grant["id"])
    assert get(c, headers).status_code == 403


def test_inbox_reuses_daily_capacity_and_excludes_started_stock(decision_case):
    from webapp.publications.auth import resolve_grant
    from webapp.publications.deliveries import claim_due, claim_original, start_attempt

    c = today_revision(decision_case)
    headers, _ = planner(c)
    authorize(c)
    token, _ = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "server2", 1, int(time.time()) + 600
    )
    now = int(time.time())
    worker = resolve_grant(c["url"], token, "worker", now)
    claim = claim_due(c["url"], worker, now)
    assert claim
    reserved = get(c, headers).json()["accounts"][0]
    assert reserved["authorized_stock"] == 1 and reserved["remaining_daily_capacity"] == 1
    claim_original(c["url"], c["app"].state.storage, worker, claim["claim_id"], now)
    start_attempt(c["url"], worker, claim["claim_id"], claim["contract_hash"], now)
    started = get(c, headers, stock_target=100).json()["accounts"][0]
    assert started["authorized_stock"] == 0 and started["remaining_daily_capacity"] == 1
    assert started["deficit"] == 1
    assert "destination_attempt_unresolved" in started["hold_reasons"]


def test_inbox_campaign_pagination_excludes_outside_policy_and_owner_cookie(decision_case):
    from webapp.publications.campaigns import create_campaign
    from webapp.tests.media_helpers import brand, project

    c = today_revision(decision_case)
    headers, _ = planner(c)
    extra = campaign(c["url"], c["a"])
    p = project(c["a"]["client"], "outside-policy")
    b = brand(c["a"]["client"], p["id"], "outside-policy")
    outside = create_campaign(
        c["url"], c["a"]["tenant"], c["a"]["owner"], p["id"], b["id"], "Outside"
    )
    all_ids = []
    cursor = 0
    while True:
        page = get(c, headers, cursor=cursor, limit=1).json()["campaigns"]
        all_ids.extend(x["id"] for x in page["items"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    assert extra["id"] in all_ids and outside["id"] not in all_ids
    assert len(all_ids) == len(set(all_ids))
    # Una cookie owner no se convierte en autoridad planner; Bearer+cookie tampoco.
    assert c["a"]["client"].get(ROUTE).status_code == 403
    assert c["a"]["client"].get(ROUTE, headers=headers).status_code == 403


@pytest.mark.parametrize(
    "block", ["expired", "worker_hold", "dedup", "identity", "connection", "scopes"]
)
def test_inbox_retains_current_blocked_delivery_without_mutating_state(
    decision_case, monkeypatch, block
):
    from types import SimpleNamespace

    from webapp.publications import inbox
    from webapp.publications.auth import resolve_grant
    from webapp.publications.deliveries import claim_due, hold_claim

    c = today_revision(decision_case)
    headers, _ = planner(c)
    delivery = authorize(c)
    if block == "expired":
        monkeypatch.setattr(
            inbox, "time", SimpleNamespace(time=lambda: c["revision"]["snapshot"]["expires_at_utc"])
        )
        expected = "revision_expired"
    elif block == "worker_hold":
        token, _ = issue_grant(
            c["url"],
            c["a"]["tenant"],
            c["a"]["owner"],
            "worker",
            "server2",
            1,
            int(time.time()) + 600,
        )
        now = int(time.time())
        worker = resolve_grant(c["url"], token, "worker", now)
        claim = claim_due(c["url"], worker, now)
        hold_claim(
            c["url"], worker, claim["claim_id"], claim["contract_hash"], "requires_auth", now
        )
        expected = "requires_auth"
    elif block == "dedup":
        from webapp.publications.ledger import append_event

        append_event(
            c["url"],
            c["a"]["tenant"],
            "old-attempt",
            "old-withdrawal",
            "withdrawn",
            {
                "normalized_destination": "facebook:page-42",
                "image_sha256": c["revision"]["snapshot"]["media"]["sha256"],
            },
        )
        expected = "media_already_attempted"
    elif block == "identity":
        with db.connect(c["url"]) as con:
            con.execute(
                "UPDATE brands SET brand_version=brand_version+1 WHERE tenant_id=? AND id=?",
                (c["a"]["tenant"], c["a"]["brand"]["id"]),
            )
        expected = "identity_changed"
    elif block == "scopes":
        with db.connect(c["url"]) as con:
            con.execute(
                "UPDATE publication_connection_details SET scopes_json='[]' WHERE tenant_id=? AND connection_id=?",
                (c["a"]["tenant"], c["a"]["connection"]["id"]),
            )
        expected = "connection_unavailable"
    else:
        with db.connect(c["url"]) as con:
            con.execute(
                "UPDATE publication_connections SET version=version+1 WHERE tenant_id=? AND id=?",
                (c["a"]["tenant"], c["a"]["connection"]["id"]),
            )
        expected = "connection_changed"
    before = counts(c)
    account = get(c, headers).json()["accounts"][0]
    assert account["authorized_stock"] == 0
    assert any(expected in x["reasons"] for x in account["held_deliveries"])
    assert counts(c) == before
    with db.connect(c["url"]) as con:
        actual = con.execute(
            "SELECT state FROM publication_deliveries WHERE tenant_id=? AND id=?",
            (c["a"]["tenant"], delivery["id"]),
        ).fetchone()["state"]
    assert actual == ("held" if block == "worker_hold" else "scheduled")


def test_inbox_policy_change_invalidates_old_planner_without_fallback(decision_case):
    from webapp.publications.policies import set_policy
    from webapp.tests.test_publication_policies import policy_payload

    c = today_revision(decision_case)
    headers, _ = planner(c)
    payload = policy_payload(
        c["a"]["project"]["id"], c["a"]["brand"]["id"], c["a"]["connection"]["id"]
    )
    set_policy(c["url"], c["a"]["tenant"], c["a"]["owner"], 1, payload)
    assert get(c, headers).status_code == 403


def test_inbox_history_projection_is_bounded_canonical_and_never_claims_missing_cut(decision_case):
    from webapp.publications.ledger import append_event, import_history

    c = today_revision(decision_case)
    headers, _ = planner(c)
    # Corte sólo crea alias comprobado; guards anteriores conservan sus bytes/fecha.
    old = {
        "source_delivery_id": "alias-old",
        "platform": "facebook",
        "normalized_destination": "facebook:old-profile",
        "image_sha256": "a" * 64,
        "state": "withdrawn",
        "receipt": {"remote_id": "old-removed"},
        "original": {"completed_at": "2020-01-01T10:00:00Z"},
    }
    proof = {
        "source_sha256": "b" * 64,
        "receipt_sha256": "c" * 64,
        "cut_manifest": {
            "cut_id": "alias-complete",
            "scope": "known_inventory",
            "sources": [{"source_id": "legacy", "source_sha256": "b" * 64, "items": [old]}],
            "aliases": [
                {
                    "alias": "facebook:old-profile",
                    "destination": "facebook:page-42",
                    "evidence": {"same_photo": "synthetic-proof"},
                }
            ],
        },
    }
    import_history(c["url"], c["a"]["tenant"], "legacy", [old], proof)
    for index in range(103):
        append_event(
            c["url"],
            c["a"]["tenant"],
            f"past-{index}",
            "past",
            "failed",
            {"normalized_destination": "facebook:page-42", "image_sha256": f"{index:064x}"},
        )
    append_event(
        c["url"],
        c["b"]["tenant"],
        "foreign",
        "past",
        "published",
        {"normalized_destination": "facebook:page-42", "image_sha256": "d" * 64},
    )
    append_event(
        c["url"],
        c["a"]["tenant"],
        "other-account",
        "past",
        "uncertain",
        {"normalized_destination": "facebook:other", "image_sha256": "e" * 64},
    )
    append_event(
        c["url"],
        c["a"]["tenant"],
        "cancelled-before-start",
        "cancelled",
        "cancelled",
        {"normalized_destination": "facebook:page-42", "image_sha256": "f" * 64},
    )
    first = get(c, headers).json()["accounts"][0]
    assert first["authorized_stock"] == 0
    assert len(first["history"]["media_sha256"]) == 100
    assert not first["history"]["complete"] and first["history"]["next_cursor"]
    second = get(c, headers, history_cursor=first["history"]["next_cursor"]).json()["accounts"][0][
        "history"
    ]
    combined = first["history"]["media_sha256"] + second["media_sha256"]
    assert len(set(combined)) == 104 and "a" * 64 in combined
    assert not {"d" * 64, "e" * 64, "f" * 64}.intersection(combined)
    assert second["next_cursor"] is None and second["complete"]
    assert set(second) == {"media_sha256", "next_cursor", "complete", "history_ready"}
    empty = get(
        c,
        {
            "Authorization": "Bearer "
            + issue_grant(
                c["url"],
                c["b"]["tenant"],
                c["b"]["owner"],
                "planner",
                "foreign",
                1,
                int(time.time()) + 600,
            )[0]
        },
    ).json()["accounts"][0]
    assert not empty["history"]["history_ready"] and not empty["history"]["complete"]
    assert get(c, headers, history_cursor="bad").status_code == 422
