"""Reservas reales duales y autorización sintética, sin POST remoto."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest

from webapp import db
from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
from webapp.publications.contracts import Conflict, Forbidden, PublicationError
from webapp.publications.decisions import append_ai_decision
from webapp.publications.ledger import import_history
from webapp.tests.test_publication_campaigns import campaign, freeze
from webapp.tests.test_publication_decisions import (
    campaign_case as _campaign_case,
)
from webapp.tests.test_publication_decisions import (
    campaign_clients as _campaign_clients,
)
from webapp.tests.test_publication_decisions import (
    evaluated,
)
from webapp.tests.test_publication_decisions import (
    isolated_db as _isolated_db,
)

campaign_case = _campaign_case
campaign_clients = _campaign_clients
isolated_db = _isolated_db


def history(case, items=None):
    items = (
        items
        if items is not None
        else [
            {
                "source_delivery_id": "old",
                "platform": "facebook",
                "normalized_destination": "facebook:page-42",
                "image_sha256": "a" * 64,
                "state": "published",
                "receipt": {"remote_id": "old-post"},
                "original": {"completed_at": "2020-01-01T10:00:00Z"},
            }
        ]
    )
    manifest = {
        "cut_id": "complete",
        "scope": "known_inventory",
        "sources": [{"source_id": "legacy", "source_sha256": "b" * 64, "items": items}],
        "aliases": [],
    }
    return import_history(
        case["url"],
        case["a"]["tenant"],
        "legacy",
        items,
        {"source_sha256": "b" * 64, "receipt_sha256": "c" * 64, "cut_manifest": manifest},
    )


@pytest.fixture
def delivery_case(campaign_case):
    url, (a, b), app = campaign_case
    now = int(time.time()) + 5
    revision = freeze(
        url, a, campaign(url, a), scheduled_at=datetime.fromtimestamp(now, UTC).isoformat()
    )
    token, grant = issue_grant(
        url, a["tenant"], a["owner"], "reviewer", "own-codex", 1, now + 200000
    )
    case = dict(
        url=url,
        a=a,
        b=b,
        app=app,
        revision=revision,
        principal=resolve_grant(url, token, "reviewer", now),
        grant=grant,
        token=token,
        now=now,
    )
    append_ai_decision(url, case["principal"], evaluated(case), now)
    worker_token, _ = issue_grant(
        url, a["tenant"], a["owner"], "worker", "server2", 1, now + 200000
    )
    case["worker"] = resolve_grant(url, worker_token, "worker", now)
    case["worker_token"] = worker_token
    return case


def scheduled(c):
    from webapp.publications.deliveries import schedule_revision

    history(c)
    return schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])


def claimed(c):
    from webapp.publications.deliveries import claim_due

    scheduled(c)
    claim = claim_due(c["url"], c["worker"], c["now"])
    assert claim
    return claim


def prepared(c):
    from webapp.publications.deliveries import claim_original

    claim = claimed(c)
    content, mime = claim_original(
        c["url"], c["app"].state.storage, c["worker"], claim["claim_id"], c["now"]
    )
    assert content and mime == "image/png"
    return claim


def parallel(fn):
    barrier = Barrier(2)

    def run(_):
        barrier.wait()
        try:
            return fn()
        except PublicationError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


def test_single_claim_and_single_confirmed_start(delivery_case):
    from webapp.publications.deliveries import claim_due, claim_original, start_attempt

    c = delivery_case
    scheduled(c)
    results = parallel(lambda: claim_due(c["url"], c["worker"], c["now"]))
    assert sum(isinstance(r, dict) for r in results) == 1
    claim = next(r for r in results if isinstance(r, dict))
    claim_original(c["url"], c["app"].state.storage, c["worker"], claim["claim_id"], c["now"])
    results = parallel(
        lambda: start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
        )
    )
    assert sum(isinstance(r, dict) and r["post_permitted"] is True for r in results) == 1
    assert "attempt_already_started" in results


def test_started_attempt_is_never_reclaimed_and_ack_loss_is_read_only(delivery_case):
    from webapp.publications.deliveries import claim_due, get_claim, start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    assert claim_due(c["url"], c["worker"], c["now"] + 7200) is None
    status = get_claim(c["url"], c["worker"], claim["claim_id"], c["now"] + 7200)
    assert status["state"] == "attempt_started" and status["post_permitted"] is False
    with pytest.raises(Conflict, match="attempt_already_started"):
        start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"] + 7200
        )


def test_expired_unstarted_lease_reclaims_but_old_claim_cannot_start(delivery_case):
    from webapp.publications.deliveries import claim_due, start_attempt

    c = delivery_case
    old = prepared(c)
    new = claim_due(c["url"], c["worker"], old["lease_until"])
    assert new and new["claim_id"] != old["claim_id"] and new["attempt_id"] != old["attempt_id"]
    with pytest.raises(Conflict):
        start_attempt(
            c["url"], c["worker"], old["claim_id"], old["contract_hash"], old["lease_until"]
        )


def test_window_boundary_is_durable_expired(delivery_case):
    from webapp.publications.deliveries import claim_due, list_calendar

    c = delivery_case
    scheduled(c)
    assert claim_due(c["url"], c["worker"], c["now"] + 3600) is None
    assert (
        list_calendar(c["url"], c["a"]["tenant"], c["a"]["owner"])["items"][0]["state"] == "expired"
    )


@pytest.mark.parametrize("change", ["worker", "reviewer", "hash", "original_missing"])
def test_start_revalidates_authority_and_exact_material(delivery_case, change):
    from webapp.publications.deliveries import start_attempt

    c = delivery_case
    claim = claimed(c) if change == "original_missing" else prepared(c)
    if change in ("worker", "reviewer"):
        p = c["worker"] if change == "worker" else c["principal"]
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], p["grant_id"])
    with pytest.raises(PublicationError):
        start_attempt(
            c["url"],
            c["worker"],
            claim["claim_id"],
            "f" * 64 if change == "hash" else claim["contract_hash"],
            c["now"],
        )
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT count(*) AS n FROM publication_deliveries WHERE started_at IS NOT NULL"
            ).fetchone()["n"]
            == 0
        )


def result(state="published"):
    return dict(
        state=state,
        remote_id="post-1" if state == "published" else None,
        permalink="https://www.facebook.com/page-42/posts/post-1" if state == "published" else None,
        evidence={"receipt_sha256": "d" * 64},
    )


def test_report_replay_loss_conflict_and_url_validation(delivery_case):
    from webapp.publications.deliveries import claim_due, report_attempt, start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    first = report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "receipt-1", result(), c["now"]
    )
    assert first == report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "receipt-1", result(), c["now"] + 1
    )
    with pytest.raises(Conflict):
        report_attempt(
            c["url"], c["worker"], claim["attempt_id"], "receipt-1", result("failed"), c["now"]
        )
    with pytest.raises(PublicationError):
        report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "bad-url",
            result() | {"permalink": "https://facebook.com.evil.test/post"},
            c["now"],
        )
    with pytest.raises(Conflict):
        report_attempt(
            c["url"], c["worker"], claim["attempt_id"], "downgrade", result("uncertain"), c["now"]
        )
    assert claim_due(c["url"], c["worker"], c["now"] + 7200) is None


def test_schedule_requires_history_and_deduplicates_revision(delivery_case):
    from webapp.publications.deliveries import claim_due, schedule_revision

    c = delivery_case
    held = schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])
    assert held["state"] == "held" and "history_not_ready" in held["hold_reasons"]
    assert claim_due(c["url"], c["worker"], c["now"]) is None
    history(c)
    active = schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])
    assert active["id"] == held["id"] and active["state"] == "scheduled"
    assert schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"]) == active


def test_cancel_only_before_start_and_foreign_owner_rejected(delivery_case):
    from webapp.publications.deliveries import cancel_delivery, start_attempt

    c = delivery_case
    claim = prepared(c)
    with pytest.raises(PublicationError):
        cancel_delivery(c["url"], c["b"]["tenant"], c["b"]["owner"], claim["delivery_id"], c["now"])
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    with pytest.raises(Conflict):
        cancel_delivery(c["url"], c["a"]["tenant"], c["a"]["owner"], claim["delivery_id"], c["now"])


def test_old_history_import_today_does_not_consume_today_quota(delivery_case):
    c = delivery_case
    from webapp.publications.deliveries import claim_due

    scheduled(c)
    assert claim_due(c["url"], c["worker"], c["now"]) is not None


@pytest.mark.parametrize(
    "timestamp,reason",
    [
        (None, "history_time_unknown"),
        ("ambiguous", "history_time_unknown"),
        ("today", "daily_quota_reached"),
    ],
)
def test_history_actual_day_and_ambiguous_time_hold(delivery_case, timestamp, reason):
    from webapp.publications.deliveries import claim_due, schedule_revision

    c = delivery_case
    value = (
        datetime.fromtimestamp(c["now"] - 7200, UTC).isoformat()
        if timestamp == "today"
        else timestamp
    )
    rows = [
        dict(
            source_delivery_id=str(i),
            platform="facebook",
            normalized_destination="facebook:page-42",
            image_sha256=str(i) * 64,
            state="published",
            receipt={"remote_id": str(i)},
            original={"completed_at": value},
        )
        for i in (1, 2)
    ]
    history(c, rows)
    row = schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])
    assert reason in row["hold_reasons"]
    assert claim_due(c["url"], c["worker"], c["now"]) is None


def confirmation(claim, remote_id="post-1"):
    return {
        "confirmed": True,
        "attempt_id": claim["attempt_id"],
        "normalized_destination": "facebook:page-42",
        "remote_id": remote_id,
        "receipt": {"sha256": "e" * 64, "operation": "remote_lookup"},
    }


def test_revoked_worker_keeps_attempt_owner_can_reconcile_then_withdraw(delivery_case):
    from webapp.publications.deliveries import reconcile_attempt, report_attempt, start_attempt
    from webapp.publications.ledger import seen_media

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
    with pytest.raises(Forbidden):
        report_attempt(c["url"], c["worker"], claim["attempt_id"], "remote", result(), c["now"])
    with pytest.raises(PublicationError):
        reconcile_attempt(
            c["url"],
            c["b"]["tenant"],
            c["b"]["owner"],
            claim["attempt_id"],
            "lookup",
            result(),
            confirmation(claim),
            c["now"],
        )
    with pytest.raises(PublicationError):
        reconcile_attempt(
            c["url"],
            c["a"]["tenant"],
            c["b"]["owner"],
            claim["attempt_id"],
            "lookup",
            result(),
            confirmation(claim),
            c["now"],
        )
    bad = confirmation(claim) | {"receipt": {}}
    with pytest.raises(PublicationError):
        reconcile_attempt(
            c["url"],
            c["a"]["tenant"],
            c["a"]["owner"],
            claim["attempt_id"],
            "lookup",
            result(),
            bad,
            c["now"],
        )
    good = reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "lookup",
        result(),
        confirmation(claim),
        c["now"],
    )
    assert good == reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "lookup",
        result(),
        confirmation(claim),
        c["now"] + 1,
    )
    with pytest.raises(Conflict):
        reconcile_attempt(
            c["url"],
            c["a"]["tenant"],
            c["a"]["owner"],
            claim["attempt_id"],
            "lookup",
            result("failed"),
            confirmation(claim),
            c["now"],
        )
    removed = reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "withdraw",
        result(),
        confirmation(claim),
        c["now"],
        withdrawn=True,
    )
    assert removed["state"] == "withdrawn"
    assert seen_media(
        c["url"], c["a"]["tenant"], "facebook:page-42", c["revision"]["snapshot"]["media"]["sha256"]
    )
    with db.connect(c["url"]) as con:
        events = con.execute(
            "SELECT kind FROM publication_events WHERE tenant_id=? AND attempt_id=? ORDER BY id",
            (c["a"]["tenant"], claim["attempt_id"]),
        ).fetchall()
    assert [e["kind"] for e in events] == ["reserved", "attempt_started", "reconciled", "withdrawn"]


def test_uncertain_report_cannot_be_silently_overwritten(delivery_case):
    from webapp.publications.deliveries import reconcile_attempt, report_attempt, start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    assert (
        report_attempt(
            c["url"], c["worker"], claim["attempt_id"], "timeout", result("uncertain"), c["now"]
        )["state"]
        == "uncertain"
    )
    with pytest.raises(Conflict, match="reconciliation_required"):
        report_attempt(c["url"], c["worker"], claim["attempt_id"], "late", result(), c["now"])
    assert (
        reconcile_attempt(
            c["url"],
            c["a"]["tenant"],
            c["a"]["owner"],
            claim["attempt_id"],
            "lookup",
            result(),
            confirmation(claim),
            c["now"],
        )["state"]
        == "published"
    )


def test_start_failure_rolls_back_cas_guard_and_event(delivery_case, monkeypatch):
    from webapp.publications import deliveries
    from webapp.publications.ledger import seen_media

    c = delivery_case
    claim = prepared(c)
    original = deliveries.append_event_in_transaction

    def fail(con, tenant, attempt, key, kind, payload):
        row = original(con, tenant, attempt, key, kind, payload)
        if kind == "attempt_started":
            raise RuntimeError("simulated crash before commit")
        return row

    monkeypatch.setattr(deliveries, "append_event_in_transaction", fail)
    with pytest.raises(RuntimeError):
        deliveries.start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
        )
    with db.connect(c["url"]) as con:
        row = con.execute(
            "SELECT state,started_at FROM publication_deliveries WHERE tenant_id=?",
            (c["a"]["tenant"],),
        ).fetchone()
        assert row == {"state": "reserved", "started_at": None}
        assert (
            con.execute(
                "SELECT count(*) AS n FROM publication_events WHERE kind='attempt_started'"
            ).fetchone()["n"]
            == 0
        )
    assert not seen_media(
        c["url"], c["a"]["tenant"], "facebook:page-42", c["revision"]["snapshot"]["media"]["sha256"]
    )


def test_credentials_and_original_only_for_live_exact_claim(delivery_case):
    from webapp.publications.deliveries import claim_credential, claim_original

    c = delivery_case
    claim = claimed(c)
    assert (
        claim_credential(c["url"], c["worker"], claim["claim_id"], c["now"], key=b"k" * 32)[
            "access_token"
        ]
        == "fake-token"
    )
    for p, t in (
        (c["principal"], c["now"]),
        (c["worker"] | {"tenant_id": c["b"]["tenant"]}, c["now"]),
        (c["worker"], claim["lease_until"]),
    ):
        with pytest.raises(PublicationError):
            claim_credential(c["url"], p, claim["claim_id"], t, key=b"k" * 32)
        with pytest.raises(PublicationError):
            claim_original(c["url"], c["app"].state.storage, p, claim["claim_id"], t)


def test_claim_record_is_append_only(delivery_case):
    c = delivery_case
    claim = prepared(c)
    for table in ("publication_claims", "publication_claim_materials"):
        with pytest.raises(Exception, match="immutable_claim"), db.connect(c["url"]) as con:
            con.execute(
                f"DELETE FROM {table} WHERE tenant_id=? AND claim_id=?",
                (c["a"]["tenant"], claim["claim_id"]),
            )


def test_http_routes_exclude_wrong_roles_and_use_server_clock(delivery_case, monkeypatch):
    from fastapi.testclient import TestClient

    c = delivery_case
    scheduled(c)
    with TestClient(c["app"], base_url="https://testserver") as client:
        root = "/api/v1/publications/worker"
        for token in (c["token"], "eikon_fake", ""):
            r = client.post(root + "/claims", headers={"Authorization": "Bearer " + token}, json={})
            assert r.status_code == 403
        # Un reloj cliente no adelanta una entrega futura.
        h = {"Authorization": "Bearer " + c["worker_token"]}
        assert client.post(root + "/claims", headers=h, json={"now": c["now"]}).status_code == 422
        monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
        r = client.post(root + "/claims", headers=h, json={})
        assert r.status_code == 200 and r.json()["claim_id"]
        claim = r.json()
        image = client.get(root + "/claims/" + claim["claim_id"] + "/original", headers=h)
        assert image.status_code == 200 and image.headers["cache-control"] == "private, no-store"
        r = client.post(
            root + "/claims/" + claim["claim_id"] + "/start",
            headers=h,
            json={"contract_hash": claim["contract_hash"]},
        )
        assert r.status_code == 200 and r.json()["post_permitted"]
        replay = client.post(
            root + "/claims/" + claim["claim_id"] + "/start",
            headers=h,
            json={"contract_hash": claim["contract_hash"]},
        )
        assert replay.status_code == 409
        status = client.get(root + "/claims/" + claim["claim_id"], headers=h).json()
        assert status["state"] == "attempt_started" and status["post_permitted"] is False
        assert (
            client.post(
                root + "/attempts/" + claim["attempt_id"] + "/media-ticket", headers=h, json={}
            ).status_code
            == 409
        )


def test_policy_day_changes_at_midnight_not_frozen_schedule_date(delivery_case):
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from webapp.publications.deliveries import claim_due, schedule_revision

    c = delivery_case
    midnight = datetime.now(ZoneInfo("America/Bogota")).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    due = int(midnight.timestamp()) - 30
    # Grants de prueba vigentes a ambos lados de la frontera.
    token, grant = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "reviewer", "own-codex", 1, due + 20000
    )
    c["principal"] = resolve_grant(c["url"], token, "reviewer", int(time.time()))
    c["grant"] = grant
    token, _ = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "server2-midnight", 1, due + 20000
    )
    c["worker"] = resolve_grant(c["url"], token, "worker", int(time.time()))
    c["revision"] = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        scheduled_at=datetime.fromtimestamp(due, UTC).isoformat(),
    )
    append_ai_decision(c["url"], c["principal"], evaluated(c), int(time.time()))
    items = [
        dict(
            source_delivery_id=str(i),
            platform="facebook",
            normalized_destination="facebook:page-42",
            image_sha256=str(i) * 64,
            state="published",
            receipt={"remote_id": str(i)},
            original={"completed_at": datetime.fromtimestamp(due - 7200, UTC).isoformat()},
        )
        for i in (1, 2)
    ]
    history(c, items)
    row = schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], due)
    assert "daily_quota_reached" in row["hold_reasons"]
    claim = claim_due(c["url"], c["worker"], due + 60)
    assert claim is not None


def test_two_distinct_workers_cannot_claim_same_revision(delivery_case):
    from webapp.publications.deliveries import claim_due

    c = delivery_case
    scheduled(c)
    token, _ = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "server2-other", 1, c["now"] + 20000
    )
    other = resolve_grant(c["url"], token, "worker", c["now"])
    gate = Barrier(2)

    def run(principal):
        gate.wait()
        return claim_due(c["url"], principal, c["now"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [c["worker"], other]))
    assert sum(r is not None for r in results) == 1


def test_changed_caption_does_not_evade_destination_sha_dedup(delivery_case):
    from webapp.publications.deliveries import schedule_revision, start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    c["revision"] = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        caption="Otro texto",
        scheduled_at=datetime.fromtimestamp(c["now"], UTC).isoformat(),
    )
    append_ai_decision(c["url"], c["principal"], evaluated(c), c["now"])
    row = schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])
    assert row["state"] == "held" and "media_already_attempted" in row["hold_reasons"]


def test_delivery_schema_rollback_no_seed_and_idempotency(isolated_db, monkeypatch):
    from webapp.publications.migrations import migrate_publications

    db.init_db(isolated_db)
    tables = (
        "publication_media_tickets",
        "publication_claim_materials",
        "publication_claims",
        "publication_deliveries",
    )
    with db.connect(isolated_db) as con:
        for table in tables:
            con.execute(f"DROP TABLE {table}")
        con.execute("DELETE FROM schema_migrations WHERE version='publication_deliveries_v1'")
    execute = db.DualConnection.execute

    def fail(self, query, params=()):
        if (
            query.startswith("INSERT INTO schema_migrations")
            and params[0] == "publication_deliveries_v1"
        ):
            raise RuntimeError("marker failure")
        return execute(self, query, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail)
        with pytest.raises(RuntimeError):
            migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        if con.dialect == "sqlite":
            assert (
                con.execute(
                    "SELECT name FROM sqlite_master WHERE name='publication_deliveries'"
                ).fetchall()
                == []
            )
        else:
            assert (
                con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='publication_deliveries'"
                ).fetchall()
                == []
            )
    migrate_publications(isolated_db)
    migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        for table in tables:
            assert con.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
        assert (
            con.execute(
                "SELECT count(*) AS n FROM schema_migrations WHERE version='publication_deliveries_v1'"
            ).fetchone()["n"]
            == 1
        )


def submission(c, outcome="approve"):
    from webapp.tests.test_publication_decisions import delivered, receipt, response

    answer = response(outcome)
    material = delivered(c)
    return {
        "expected_contract_hash": c["revision"]["contract_hash"],
        "policy_version": 1,
        "material_hashes": material["material_hashes"],
        "model_receipt": receipt(c, material, answer),
        "response": answer,
    }


@pytest.mark.parametrize("outcome", ["approve", "reject", "hold"])
def test_reviewer_submission_schedules_only_approve_without_owner(delivery_case, outcome):
    from fastapi.testclient import TestClient

    c = delivery_case
    history(c)
    payload = submission(c, outcome)
    with TestClient(c["app"]) as client:
        path = f"/api/v1/publications/reviewer/candidates/{c['revision']['id']}/evaluations"
        r = client.post(path, headers={"Authorization": "Bearer " + c["token"]}, json=payload)
        assert r.status_code == 201
        assert r.json()["decision"]["outcome"] == outcome
        if outcome == "approve":
            assert r.json()["delivery"]["state"] == "scheduled"
        else:
            assert r.json()["delivery"] is None
    with db.connect(c["url"]) as con:
        assert con.execute("SELECT count(*) AS n FROM publication_deliveries").fetchone()[
            "n"
        ] == int(outcome == "approve")


def test_scheduling_failure_is_visible_and_exact_evaluation_replay_recovers(
    delivery_case, monkeypatch
):
    from fastapi.testclient import TestClient

    from webapp.publications import deliveries

    c = delivery_case
    history(c)
    payload = submission(c)
    path = f"/api/v1/publications/reviewer/candidates/{c['revision']['id']}/evaluations"
    original = deliveries.schedule_revision

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise Conflict("simulated_schedule_ack_loss")

    with TestClient(c["app"]) as client:
        with monkeypatch.context() as patch:
            patch.setattr("webapp.api.publication_reviewer.schedule_revision", fail)
            r = client.post(path, headers={"Authorization": "Bearer " + c["token"]}, json=payload)
            assert r.status_code == 409 and r.json()["detail"] == "simulated_schedule_ack_loss"
        first = client.post(path, headers={"Authorization": "Bearer " + c["token"]}, json=payload)
        second = client.post(path, headers={"Authorization": "Bearer " + c["token"]}, json=payload)
        assert first.status_code == second.status_code == 201
        assert first.json()["delivery"] == second.json()["delivery"]
        assert first.json()["decision"] == second.json()["decision"]
    with db.connect(c["url"]) as con:
        assert con.execute("SELECT count(*) AS n FROM publication_deliveries").fetchone()["n"] == 1


def test_revocation_between_approve_and_schedule_is_visible_hold(delivery_case, monkeypatch):
    from fastapi.testclient import TestClient

    from webapp.publications import deliveries

    c = delivery_case
    history(c)
    payload = submission(c)

    def revoked(*args, **kwargs):
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["principal"]["grant_id"])
        return deliveries.schedule_revision(*args, **kwargs)

    monkeypatch.setattr("webapp.api.publication_reviewer.schedule_revision", revoked)
    with TestClient(c["app"]) as client:
        r = client.post(
            f"/api/v1/publications/reviewer/candidates/{c['revision']['id']}/evaluations",
            headers={"Authorization": "Bearer " + c["token"]},
            json=payload,
        )
        assert r.status_code == 201
        assert r.json()["decision"]["outcome"] == "approve"
        assert r.json()["delivery"]["state"] == "held"
        assert "reviewer_authorization_unavailable" in r.json()["delivery"]["hold_reasons"]
    assert deliveries.claim_due(c["url"], c["worker"], c["now"]) is None


def test_same_sha_other_account_survives_first_account_failure(delivery_case):
    from webapp.publications.connections import hold_connection, put_connection
    from webapp.publications.deliveries import (
        claim_due,
        claim_original,
        report_attempt,
        schedule_revision,
        start_attempt,
    )
    from webapp.publications.oauth import import_credential
    from webapp.publications.policies import set_policy
    from webapp.tests.test_publication_oauth import ProviderDouble
    from webapp.tests.test_publication_policies import policy_payload

    c = delivery_case
    a = c["a"]
    second = put_connection(
        c["url"],
        a["tenant"],
        a["owner"],
        {
            "platform": "facebook",
            "api_mode": "page",
            "remote_id": "page-99",
            "project_ids": [a["project"]["id"]],
        },
    )
    second = import_credential(
        c["url"],
        a["tenant"],
        a["owner"],
        second["id"],
        {"access_token": "fake-second"},
        c["now"],
        ProviderDouble(remote_id="page-99", expires_at=9999999999),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    policy = policy_payload(a["project"]["id"], a["brand"]["id"], a["connection"]["id"])
    policy["connection_ids"].append(second["id"])
    set_policy(c["url"], a["tenant"], a["owner"], 1, policy)
    token, _ = issue_grant(
        c["url"], a["tenant"], a["owner"], "reviewer", "own-codex", 2, c["now"] + 20000
    )
    c["principal"] = resolve_grant(c["url"], token, "reviewer", c["now"])
    token, _ = issue_grant(
        c["url"], a["tenant"], a["owner"], "worker", "two-accounts", 2, c["now"] + 20000
    )
    c["worker"] = resolve_grant(c["url"], token, "worker", c["now"])
    rows = [
        dict(
            source_delivery_id=dest,
            platform="facebook",
            normalized_destination="facebook:" + dest,
            image_sha256="a" * 64,
            state="published",
            receipt={"remote_id": "old-" + dest},
            original={"completed_at": "2020-01-01T00:00:00Z"},
        )
        for dest in ("page-42", "page-99")
    ]
    history(c, rows)
    for account in (a["connection"], second):
        c["revision"] = freeze(
            c["url"],
            a,
            campaign(c["url"], a),
            policy_version=2,
            connection_id=account["id"],
            scheduled_at=datetime.fromtimestamp(c["now"], UTC).isoformat(),
        )
        decision = evaluated(c)
        decision["policy_version"] = 2
        append_ai_decision(c["url"], c["principal"], decision, c["now"])
        assert (
            schedule_revision(c["url"], a["tenant"], c["revision"]["id"], c["now"])["state"]
            == "scheduled"
        )
    first = claim_due(c["url"], c["worker"], c["now"])
    claim_original(c["url"], c["app"].state.storage, c["worker"], first["claim_id"], c["now"])
    start_attempt(c["url"], c["worker"], first["claim_id"], first["contract_hash"], c["now"])
    report_attempt(c["url"], c["worker"], first["attempt_id"], "denied", result("failed"), c["now"])
    with db.connect(c["url"]) as con:
        hold_connection(con, a["tenant"], a["owner"], a["connection"]["id"], "provider_failure")
    second_claim = claim_due(c["url"], c["worker"], c["now"])
    assert second_claim and second_claim["delivery_id"] != first["delivery_id"]
    claim_original(
        c["url"], c["app"].state.storage, c["worker"], second_claim["claim_id"], c["now"]
    )
    assert start_attempt(
        c["url"], c["worker"], second_claim["claim_id"], second_claim["contract_hash"], c["now"]
    )["post_permitted"]


def test_wrong_vault_key_is_safe_block_without_fallback(delivery_case):
    from webapp.publications.deliveries import claim_credential

    c = delivery_case
    claim = claimed(c)
    with pytest.raises(Conflict, match="vault_unavailable"):
        claim_credential(c["url"], c["worker"], claim["claim_id"], c["now"], key=b"x" * 32)


def test_late_publication_report_holds_own_destination_until_remote_time_reconciled(delivery_case):
    from webapp.publications import deliveries
    from webapp.tests.media_helpers import image_bytes, upload

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    later = c["now"] + 86400
    deliveries.report_attempt(c["url"], c["worker"], claim["attempt_id"], "late", result(), later)
    # Nueva pieza, misma cuenta: no reutiliza SHA y revela exclusivamente el hold temporal.
    c["a"]["media"] = upload(
        c["a"]["client"], c["a"]["brief"]["id"], "second", image_bytes(color="blue")
    ).json()
    c["revision"] = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        scheduled_at=datetime.fromtimestamp(later, UTC).isoformat(),
    )
    append_ai_decision(c["url"], c["principal"], evaluated(c), c["now"])
    row = deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], later)
    assert "publication_day_unverified" in row["hold_reasons"]
    proven = result()
    proven["evidence"].update(
        published_at=datetime.fromtimestamp(c["now"], UTC).isoformat(),
        published_at_source="provider",
    )
    reconciled = deliveries.reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "remote-time",
        proven,
        confirmation(claim),
        later,
    )
    assert reconciled["state"] == "published"
    row = deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], later)
    assert row["state"] == "scheduled"
    # Retirada tardía conserva hora demostrada; jamás consume cuota por fecha de retirada.
    deliveries.reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "withdraw-late",
        result(),
        confirmation(claim),
        later,
        withdrawn=True,
    )
    assert (
        deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], later)[
            "state"
        ]
        == "scheduled"
    )


def test_one_attempt_with_known_remote_timestamp_counts_once_on_each_actual_day(delivery_case):
    from webapp.publications import deliveries
    from webapp.tests.media_helpers import image_bytes, upload

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    proven = result()
    proven["evidence"].update(
        published_at=datetime.fromtimestamp(c["now"], UTC).isoformat(),
        published_at_source="provider",
    )
    deliveries.report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "on-time", proven, c["now"]
    )
    c["a"]["media"] = upload(
        c["a"]["client"], c["a"]["brief"]["id"], "second", image_bytes(color="blue")
    ).json()
    later = c["now"] + 3600
    c["revision"] = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        scheduled_at=datetime.fromtimestamp(later, UTC).isoformat(),
    )
    append_ai_decision(c["url"], c["principal"], evaluated(c), c["now"])
    row = deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], later)
    assert "daily_quota_reached" not in row["hold_reasons"]


def time_proof(c):
    with db.connect(c["url"]) as con:
        row = con.execute(
            "SELECT * FROM publication_history WHERE tenant_id=? AND source_id=?",
            (c["a"]["tenant"], "legacy"),
        ).fetchone()
    receipt = {
        "source_id": "legacy",
        "source_delivery_id": row["source_delivery_id"],
        "item_hash": row["item_hash"],
        "source_sha256": "b" * 64,
        "normalized_destination": "facebook:page-42",
        "remote_id": "old-post",
        "published_at": "2020-01-01T10:00:00+0000",
        "published_at_source": "provider",
        "receipt_sha256": "e" * 64,
    }
    return row, {"confirmed": True, "state": "published", "receipt": receipt}


def unknown_history(c):
    history(
        c,
        [
            dict(
                source_delivery_id="old",
                platform="facebook",
                normalized_destination="facebook:page-42",
                image_sha256="a" * 64,
                state="published",
                receipt={"remote_id": "old-post"},
                original={"completed_at": None},
            )
        ],
    )


def test_verified_history_time_closes_hold_without_rewriting_import(delivery_case):
    from webapp.publications.deliveries import claim_due, schedule_revision
    from webapp.publications.ledger import append_event

    c = delivery_case
    unknown_history(c)
    assert (
        "history_time_unknown"
        in schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])[
            "hold_reasons"
        ]
    )
    original, proof = time_proof(c)
    append_event(
        c["url"], c["a"]["tenant"], original["attempt_id"], "verified-time", "reconciled", proof
    )
    assert (
        schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])["state"]
        == "scheduled"
    )
    assert claim_due(c["url"], c["worker"], c["now"]) is not None
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT * FROM publication_history WHERE tenant_id=? AND id=?",
                (c["a"]["tenant"], original["id"]),
            ).fetchone()
            == original
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "wrong"),
        ("source_delivery_id", "other"),
        ("item_hash", "f" * 64),
        ("source_sha256", "f" * 64),
        ("normalized_destination", "facebook:foreign"),
        ("remote_id", "queue-id"),
        ("published_at", "2020-01-01T10:00:00"),
        ("published_at_source", "received_at"),
        ("receipt_sha256", "bad"),
    ],
)
def test_historical_time_wrong_binding_stays_held(delivery_case, field, value):
    from webapp.publications.deliveries import schedule_revision
    from webapp.publications.ledger import append_event

    c = delivery_case
    unknown_history(c)
    row, proof = time_proof(c)
    proof["receipt"][field] = value
    append_event(c["url"], c["a"]["tenant"], row["attempt_id"], "wrong-time", "reconciled", proof)
    assert (
        "history_time_unknown"
        in schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])[
            "hold_reasons"
        ]
    )


def test_latest_invalid_historical_time_cannot_fall_back_to_previous_proof(delivery_case):
    from webapp.publications.deliveries import schedule_revision
    from webapp.publications.ledger import append_event

    c = delivery_case
    unknown_history(c)
    row, proof = time_proof(c)
    append_event(c["url"], c["a"]["tenant"], row["attempt_id"], "valid-time", "reconciled", proof)
    assert (
        schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])["state"]
        == "scheduled"
    )
    append_event(
        c["url"],
        c["a"]["tenant"],
        row["attempt_id"],
        "retracted-time",
        "reconciled",
        proof | {"confirmed": False},
    )
    assert (
        "history_time_unknown"
        in schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])[
            "hold_reasons"
        ]
    )


def test_reconciliation_credential_after_lease_is_bound_and_never_grants_post(delivery_case):
    from webapp.publications import deliveries

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    credential = deliveries.reconciliation_credential(
        c["url"], c["worker"], claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
    )
    assert credential == {
        "purpose": "reconcile_only",
        "post_permitted": False,
        "credential": {"access_token": "fake-token"},
    }
    with pytest.raises(PublicationError):
        deliveries.claim_credential(
            c["url"], c["worker"], claim["claim_id"], c["now"] + 7200, key=b"k" * 32
        )
    with db.connect(c["url"]) as con:
        rows = con.execute(
            "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=?",
            (c["a"]["tenant"], claim["attempt_id"]),
        ).fetchall()
        assert "fake-token" not in json.dumps(rows)
        assert (
            con.execute(
                "SELECT state FROM publication_deliveries WHERE tenant_id=?", (c["a"]["tenant"],)
            ).fetchone()["state"]
            == "attempt_started"
        )
    assert (
        deliveries.get_claim(c["url"], c["worker"], claim["claim_id"], c["now"] + 7200)[
            "post_permitted"
        ]
        is False
    )


@pytest.mark.parametrize(
    "change",
    [
        "revoke",
        "policy",
        "policy_expired",
        "account",
        "inactive",
        "scopes",
        "expired",
        "foreign_grant",
        "foreign_tenant",
    ],
)
def test_reconciliation_credentials_revalidate_current_authority(delivery_case, change):
    from webapp.publications import deliveries
    from webapp.publications.policies import set_policy

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    principal = c["worker"]
    if change == "revoke":
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], principal["grant_id"])
    elif change == "policy":
        set_policy(c["url"], c["a"]["tenant"], c["a"]["owner"], 1, {"enabled": False})
    elif change == "policy_expired":
        with db.connect(c["url"]) as con:
            con.execute(
                "UPDATE publication_policies SET expires_at=? WHERE tenant_id=?",
                (c["now"] + 1, c["a"]["tenant"]),
            )
    elif change == "foreign_tenant":
        principal = principal | {"tenant_id": c["b"]["tenant"]}
    elif change == "foreign_grant":
        token, _ = issue_grant(
            c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "different", 1, c["now"] + 20000
        )
        principal = resolve_grant(c["url"], token, "worker", c["now"])
    else:
        with db.connect(c["url"]) as con:
            if change == "account":
                con.execute(
                    "UPDATE publication_connections SET remote_id='foreign-account' WHERE tenant_id=?",
                    (c["a"]["tenant"],),
                )
            elif change == "inactive":
                con.execute(
                    "UPDATE publication_connections SET status='held' WHERE tenant_id=?",
                    (c["a"]["tenant"],),
                )
            elif change == "expired":
                con.execute(
                    "UPDATE publication_connections SET expires_at=? WHERE tenant_id=?",
                    (c["now"] + 1, c["a"]["tenant"]),
                )
            else:
                con.execute(
                    "UPDATE publication_connection_details SET scopes_json='[]' WHERE tenant_id=?",
                    (c["a"]["tenant"],),
                )
    with pytest.raises(PublicationError):
        deliveries.reconciliation_credential(
            c["url"], principal, claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
        )


def test_refreshed_same_account_credential_can_reconcile_existing_attempt(delivery_case):
    from webapp.publications import deliveries
    from webapp.publications.oauth import import_credential
    from webapp.tests.test_publication_oauth import ProviderDouble

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    import_credential(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        c["a"]["connection"]["id"],
        {"access_token": "refreshed-test-token"},
        c["now"] + 1,
        ProviderDouble(expires_at=9999999999),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    assert (
        deliveries.reconciliation_credential(
            c["url"], c["worker"], claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
        )["credential"]["access_token"]
        == "refreshed-test-token"
    )


def test_reconciliation_credential_http_private_closed_schema_and_current_grant(
    delivery_case, monkeypatch
):
    import base64
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from webapp.publications.deliveries import start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    c["app"].state.settings = replace(
        c["app"].state.settings, publication_vault_key=base64.b64encode(b"k" * 32).decode()
    )
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"] + 7200)
    path = (
        "/api/v1/publications/worker/attempts/" + claim["attempt_id"] + "/reconciliation-credential"
    )
    h = {"Authorization": "Bearer " + c["worker_token"]}
    with TestClient(c["app"], base_url="https://testserver") as client:
        assert client.post(path, headers=h, json={"claim_id": claim["claim_id"]}).status_code == 422
        r = client.post(path, headers=h, json={})
        assert r.status_code == 200
        assert r.json() == {
            "purpose": "reconcile_only",
            "post_permitted": False,
            "credential": {"access_token": "fake-token"},
        }
        assert r.headers["cache-control"] == "private, no-store"
        reports = path.removesuffix("reconciliation-credential") + "reports"
        assert (
            client.post(
                reports,
                headers=h,
                json={"event_key": "uncertain-http", "result": result("uncertain")},
            ).json()["state"]
            == "uncertain"
        )
        payload = {
            "event_key": "confirmed-http",
            "result": result(),
            "confirmation": confirmation(claim),
        }
        confirmed = client.post(reports, headers=h, json=payload)
        assert confirmed.status_code == 200 and confirmed.json()["state"] == "published"
        assert client.post(reports, headers=h, json=payload).json() == confirmed.json()

        assert (
            client.post(
                path, headers={"Authorization": "Bearer " + c["token"]}, json={}
            ).status_code
            == 403
        )
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
        assert client.post(path, headers=h, json={}).status_code == 403
    with TestClient(c["app"], base_url="http://testserver") as client:
        assert client.post(path, headers=h, json={}).status_code == 403


def test_reconciliation_credentials_preserve_uncertain_and_reject_terminal(delivery_case):
    from webapp.publications import deliveries

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    deliveries.report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "timeout", result("uncertain"), c["now"] + 1
    )
    assert (
        deliveries.reconciliation_credential(
            c["url"], c["worker"], claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
        )["post_permitted"]
        is False
    )
    assert (
        deliveries.get_claim(c["url"], c["worker"], claim["claim_id"], c["now"] + 7200)["state"]
        == "uncertain"
    )
    deliveries.reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "found",
        result(),
        confirmation(claim),
        c["now"] + 7200,
    )
    with pytest.raises(PublicationError):
        deliveries.reconciliation_credential(
            c["url"], c["worker"], claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"access_token": "fake-sensitive-token"},
        {
            "receipt": {
                "sha256": "e" * 64,
                "operation": "remote_lookup",
                "access_token": "fake-sensitive-token",
            }
        },
    ],
)
def test_confirmation_rejects_unrecognized_secret_bearing_fields(delivery_case, extra):
    from webapp.publications.deliveries import reconcile_attempt, start_attempt

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    with pytest.raises(PublicationError):
        reconcile_attempt(
            c["url"],
            c["a"]["tenant"],
            c["a"]["owner"],
            claim["attempt_id"],
            "invalid-confirmation",
            result(),
            confirmation(claim) | extra,
            c["now"],
        )
    with db.connect(c["url"]) as con:
        assert "fake-sensitive-token" not in json.dumps(
            con.execute(
                "SELECT payload_json FROM publication_events WHERE tenant_id=?", (c["a"]["tenant"],)
            ).fetchall()
        )


def uncertain_attempt(c):
    from webapp.publications import deliveries

    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    deliveries.report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "uncertain", result("uncertain"), c["now"] + 1
    )
    return claim


def test_worker_confirms_uncertain_remote_effect_idempotently(delivery_case):
    from webapp.publications import deliveries

    c = delivery_case
    claim = uncertain_attempt(c)
    args = (
        c["url"],
        c["worker"],
        claim["attempt_id"],
        "remote-confirmation",
        result(),
        c["now"] + 7200,
    )
    good = deliveries.report_attempt(*args, confirmation=confirmation(claim))
    assert good["state"] == "published"
    assert deliveries.report_attempt(*args, confirmation=confirmation(claim)) == good
    with pytest.raises(Conflict, match="event_idempotency_conflict"):
        deliveries.report_attempt(
            *args,
            confirmation=confirmation(claim)
            | {"receipt": {"sha256": "f" * 64, "operation": "remote_lookup"}},
        )
    assert deliveries.claim_due(c["url"], c["worker"], c["now"] + 7200) is None
    with pytest.raises(Conflict):
        deliveries.start_attempt(
            c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"] + 7200
        )


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "empty",
        "wrong_attempt",
        "wrong_account",
        "wrong_remote",
        "prior_remote",
        "revoked",
    ],
)
def test_worker_bad_confirmation_cannot_close_uncertain(delivery_case, bad):
    from webapp.publications import deliveries

    c = delivery_case
    claim = uncertain_attempt(c)
    proof = confirmation(claim)
    value = result()
    if bad == "missing":
        proof = None
    elif bad == "empty":
        proof = {"confirmed": True}
    elif bad == "wrong_attempt":
        proof["attempt_id"] = "other"
    elif bad == "wrong_account":
        proof["normalized_destination"] = "facebook:foreign"
    elif bad == "wrong_remote":
        proof["remote_id"] = "other"
    elif bad == "prior_remote":
        deliveries.report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "id-found",
            result("uncertain") | {"remote_id": "original-id"},
            c["now"] + 2,
        )
    else:
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
    with pytest.raises(PublicationError):
        deliveries.report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "remote-confirmation",
            value,
            c["now"] + 7200,
            confirmation=proof,
        )
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT state FROM publication_deliveries WHERE tenant_id=?", (c["a"]["tenant"],)
            ).fetchone()["state"]
            == "uncertain"
        )


def test_owner_worker_concurrent_confirmations_cannot_overwrite_terminal(delivery_case):
    from webapp.publications import deliveries

    c = delivery_case
    claim = uncertain_attempt(c)
    barrier = Barrier(2)

    def run(owner):
        barrier.wait()
        try:
            if owner:
                return deliveries.reconcile_attempt(
                    c["url"],
                    c["a"]["tenant"],
                    c["a"]["owner"],
                    claim["attempt_id"],
                    "owner-proof",
                    result(),
                    confirmation(claim),
                    c["now"] + 7200,
                )
            return deliveries.report_attempt(
                c["url"],
                c["worker"],
                claim["attempt_id"],
                "worker-proof",
                result("failed") | {"remote_id": "post-1"},
                c["now"] + 7200,
                confirmation=confirmation(claim),
            )
        except PublicationError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [True, False]))
    assert sum(isinstance(x, dict) for x in outcomes) == 1
    assert "terminal_result_conflict" in outcomes
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT count(*) AS n FROM publication_events WHERE tenant_id=? AND kind='reconciled'",
                (c["a"]["tenant"],),
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize(
    "evidence",
    [
        {"error": "GET https://graph.facebook.com/v1?access_token=FAKE_REVIEW_SECRET failed"},
        {"access token": "FAKE_REVIEW_SECRET"},
        {"receipt": {"message": "Bearer FAKE_REVIEW_SECRET"}},
        {"error_code": "FAKE_REVIEW_SECRET"},
        {"published_at": "2026-10-11T10:00:00Z FAKE_REVIEW_SECRET"},
        {"receipt_sha256": "FAKE_REVIEW_SECRET"},
    ],
)
def test_report_evidence_never_persists_arbitrary_sensitive_text(
    delivery_case, monkeypatch, evidence
):
    from fastapi.testclient import TestClient

    from webapp.publications import deliveries

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    with TestClient(c["app"], base_url="https://testserver") as client:
        response = client.post(
            "/api/v1/publications/worker/attempts/" + claim["attempt_id"] + "/reports",
            headers={"Authorization": "Bearer " + c["worker_token"]},
            json={
                "event_key": "unsafe-evidence",
                "result": result("uncertain") | {"evidence": evidence},
            },
        )
        assert response.status_code == 422
        assert "FAKE_REVIEW_SECRET" not in response.text
    with db.connect(c["url"]) as con:
        assert "FAKE_REVIEW_SECRET" not in json.dumps(
            con.execute(
                "SELECT payload_json FROM publication_events WHERE tenant_id=?", (c["a"]["tenant"],)
            ).fetchall()
        )
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=?", (c["a"]["tenant"],)
        ).fetchone()
        assert row["result_json"] is None
        assert row["state"] == "attempt_started"
    assert "FAKE_REVIEW_SECRET" not in json.dumps(
        deliveries.get_claim(c["url"], c["worker"], claim["claim_id"], c["now"])
    )
    assert "FAKE_REVIEW_SECRET" not in json.dumps(
        deliveries.list_calendar(c["url"], c["a"]["tenant"], c["a"]["owner"])
    )


@pytest.mark.parametrize("intermediate", ["uncertain", "held"])
def test_intermediate_report_cannot_replace_known_canonical_remote_id(delivery_case, intermediate):
    from webapp.publications import deliveries

    c = delivery_case
    claim = uncertain_attempt(c)
    known = result("uncertain") | {"remote_id": "canonical-A"}
    deliveries.report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "known-A", known, c["now"] + 2
    )
    with pytest.raises(Conflict, match="remote_receipt_mismatch"):
        deliveries.report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "replace-B",
            result(intermediate) | {"remote_id": "canonical-B"},
            c["now"] + 3,
        )
    with pytest.raises(Conflict, match="remote_receipt_mismatch"):
        deliveries.report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "confirm-B",
            result() | {"remote_id": "canonical-B"},
            c["now"] + 4,
            confirmation=confirmation(claim, "canonical-B"),
        )
    with db.connect(c["url"]) as con:
        row = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=?", (c["a"]["tenant"],)
        ).fetchone()
        assert json.loads(row["result_json"])["remote_id"] == "canonical-A"
        assert row["state"] == "uncertain"
        assert (
            con.execute(
                "SELECT count(*) AS n FROM publication_events WHERE tenant_id=? AND event_key IN ('report:replace-B','report:confirm-B')",
                (c["a"]["tenant"],),
            ).fetchone()["n"]
            == 0
        )
    good = deliveries.report_attempt(
        c["url"],
        c["worker"],
        claim["attempt_id"],
        "confirm-A",
        result() | {"remote_id": "canonical-A"},
        c["now"] + 5,
        confirmation=confirmation(claim, "canonical-A"),
    )
    assert good["state"] == "published"


@pytest.mark.parametrize(
    "extra",
    [
        {"http_status": True},
        {"http_status": 600},
        {"error_code": {"message": "secret"}},
        {
            "processing_kind": "facebook_upload",
            "processing_id": "https://graph.facebook.com?access_token=FAKE_REVIEW_SECRET",
        },
        {"processing_kind": "facebook_upload", "processing_id": "FAKE_REVIEW_SECRET"},
        {"processing_kind": "instagram_container", "processing_id": "123"},
        {"processing_id": "123"},
        {"published_at_source": "provider"},
    ],
)
def test_safe_evidence_rejects_invalid_typed_fields(delivery_case, extra):
    from webapp.publications import deliveries

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    with pytest.raises(PublicationError):
        deliveries.report_attempt(
            c["url"],
            c["worker"],
            claim["attempt_id"],
            "bad-fields",
            result("uncertain") | {"evidence": extra},
            c["now"],
        )
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT result_json FROM publication_deliveries WHERE tenant_id=?",
                (c["a"]["tenant"],),
            ).fetchone()["result_json"]
            is None
        )


def test_safe_evidence_preserves_receipt_time_and_separate_processing_id(delivery_case):
    from webapp.publications import deliveries

    c = delivery_case
    claim = prepared(c)
    deliveries.start_attempt(
        c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
    )
    safe = {
        "receipt_sha256": "d" * 64,
        "processing_kind": "facebook_upload",
        "processing_id": "123",
        "http_status": 202,
        "error_code": "processing_pending",
    }
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        claim["attempt_id"],
        "processing",
        result("uncertain") | {"remote_id": "canonical-A", "evidence": safe},
        c["now"],
    )
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        claim["attempt_id"],
        "processing-next",
        result("uncertain") | {"remote_id": None, "evidence": safe | {"processing_id": "456"}},
        c["now"] + 1,
    )
    stamp = datetime.fromtimestamp(c["now"], UTC).isoformat()
    evidence = {
        "receipt_sha256": "e" * 64,
        "published_at": stamp,
        "published_at_source": "provider",
        "http_status": 200,
    }
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        claim["attempt_id"],
        "published",
        result() | {"remote_id": "canonical-A", "evidence": evidence},
        c["now"] + 2,
        confirmation=confirmation(claim, "canonical-A"),
    )
    row = deliveries.get_claim(c["url"], c["worker"], claim["claim_id"], c["now"] + 2)
    assert row["result"]["remote_id"] == "canonical-A"
    assert row["result"]["evidence"] == evidence
    assert row["result"]["published_at_utc"] == c["now"]
    with db.connect(c["url"]) as con:
        event = con.execute(
            "SELECT payload_json FROM publication_events WHERE tenant_id=? AND event_key='report:processing-next'",
            (c["a"]["tenant"],),
        ).fetchone()
        assert json.loads(event["payload_json"])["result"]["evidence"] == safe | {
            "processing_id": "456"
        }
