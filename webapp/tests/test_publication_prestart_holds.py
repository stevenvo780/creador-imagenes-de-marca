"""Retención de preflight autoritativa, sin inicio ni guardias de publicación."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from webapp import db
from webapp.publications import deliveries
from webapp.publications.contracts import PublicationError
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case,
    campaign_clients,
    delivery_case,
    isolated_db,
    prepared,
)

__all__ = ["campaign_case", "campaign_clients", "delivery_case", "isolated_db"]


def hold(c, claim, reason="unsupported_media", **changes):
    values = dict(
        principal=c["worker"],
        claim_id=claim["claim_id"],
        contract_hash=claim["contract_hash"],
        reason=reason,
        now=c["now"],
    )
    return deliveries.hold_claim(c["url"], **(values | changes))


def test_prestart_hold_is_visible_idempotent_and_never_reclaimed(delivery_case):
    c = delivery_case
    claim = prepared(c)
    result = hold(c, claim)
    assert result["state"] == "held" and result["hold_reasons"] == ["unsupported_media"]
    assert hold(c, claim) == result
    assert deliveries.claim_due(c["url"], c["worker"], c["now"] + 301) is None
    assert (
        deliveries.schedule_revision(
            c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"] + 301
        )
        == result
    )
    with pytest.raises(PublicationError):
        hold(c, claim, "requires_auth")
    with pytest.raises(PublicationError):
        deliveries.start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
        )
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) n FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='attempt_started'",
                (c["a"]["tenant"], claim["attempt_id"]),
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("bad", ["hash", "tenant", "expired", "revoked", "reason", "started"])
def test_prestart_hold_rejects_invalid_authority(delivery_case, bad):
    c = delivery_case
    claim = prepared(c)
    changes = {}
    if bad == "hash":
        changes["contract_hash"] = "a" * 64
    elif bad == "tenant":
        changes["principal"] = c["worker"] | {"tenant_id": c["b"]["tenant"]}
    elif bad == "expired":
        changes["now"] = c["now"] + 301
    elif bad == "revoked":
        from webapp.publications.auth import revoke_grant

        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
    elif bad == "reason":
        changes["reason"] = "https://secret?token=sensitive"
    else:
        deliveries.start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
        )
    with pytest.raises(PublicationError):
        hold(c, claim, **changes)


def test_hold_start_race_only_one_effect(delivery_case):
    c = delivery_case
    claim, barrier = prepared(c), Barrier(2)

    def action(start):
        barrier.wait()
        try:
            if start:
                deliveries.start_attempt(
                    c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
                )
            else:
                hold(c, claim)
            return True
        except PublicationError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(action, (False, True))) == [False, True]


def test_hold_rolls_back_if_event_append_fails(delivery_case, monkeypatch):
    c = delivery_case
    claim = prepared(c)

    def fail(*args, **kwargs):
        raise RuntimeError("injected append failure")

    monkeypatch.setattr(deliveries, "_event", fail)
    with pytest.raises(RuntimeError):
        hold(c, claim)
    assert (
        deliveries.get_claim(c["url"], c["worker"], claim["claim_id"], c["now"])["state"]
        == "reserved"
    )


def test_hold_http_closed_schema_and_calendar(delivery_case, monkeypatch):
    from fastapi.testclient import TestClient

    c = delivery_case
    claim = prepared(c)
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    path = "/api/v1/publications/worker/claims/" + claim["claim_id"] + "/hold"
    headers = {"Authorization": "Bearer " + c["worker_token"]}
    body = {"contract_hash": claim["contract_hash"], "reason": "requires_post_consent"}
    with TestClient(c["app"], base_url="https://testserver") as client:
        assert client.post(path, headers=headers, json=body | {"now": c["now"]}).status_code == 422
        assert (
            client.post(path, headers=headers, json=body | {"reason": "verified"}).status_code
            == 422
        )
        assert (
            client.post(
                path, headers={"Authorization": "Bearer " + c["token"]}, json=body
            ).status_code
            == 403
        )
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 200 and first.json()["hold_reasons"] == [
            "requires_post_consent"
        ]
        assert client.post(path, headers=headers, json=body).json() == first.json()
    assert hold(c, claim, "requires_post_consent", now=c["now"] + 400) == first.json()
    rows = deliveries.list_calendar(c["url"], c["a"]["tenant"], c["a"]["owner"])
    assert rows["items"][0]["state"] == "held"
