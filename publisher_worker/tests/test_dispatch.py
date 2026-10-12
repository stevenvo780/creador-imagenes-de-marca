"""Despacho sin proveedores reales: autoridad, caída, aislamiento y persistencia."""

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

# Fixtures reales compartidos, sin monkeypatch de autorización/adaptadores productivos.
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case,
    campaign_clients,
    delivery_case,
    isolated_db,
)


class FakeClient:
    tenant_id = 7

    def __init__(self):
        self.content = b"exact approved bytes"
        self.claim = dict(
            claim_id="claim:1",
            attempt_id="attempt:1",
            delivery_id=1,
            contract_hash="",
            lease_until=1300,
        )
        self.snapshot = dict(
            tenant_id=7,
            media=dict(
                sha256=hashlib.sha256(self.content).hexdigest(),
                byte_size=len(self.content),
                mime="image/jpeg",
                kind="gallery_image",
            ),
            connection=dict(tenant_id=7, id=4, platform="facebook", remote_id="42"),
            destination="facebook:42",
            caption="Exacto",
            expires_at_utc=4600,
        )
        from webapp.publications.contracts import canonical_hash

        self.claim["contract_hash"] = canonical_hash(self.snapshot)
        self.start_attempt_response = {
            "confirmed": True,
            "post_permitted": True,
            "attempt_id": "attempt:1",
            "state": "attempt_started",
        }
        self.state = "reserved"
        self.start_count = 0
        self.reports = []
        self.claimed = False
        self.error = None
        self.report_error = False

    def claim_due(self):
        if self.claimed:
            return None
        self.claimed = True
        return self.claim.copy()

    def get_claim(self, claim):
        return dict(
            snapshot=self.snapshot,
            state=self.state,
            revision_id=9,
            normalized_destination="facebook:42",
            result=None,
            contract_hash=self.claim["contract_hash"],
            post_permitted=False,
        )

    def original(self, claim):
        return self.content

    def credential(self, claim):
        if self.error == "foreign_credential":
            raise PermissionError("credential of another tenant")
        return {"access_token": "PRIVATE_TOKEN"}

    def start_attempt(self, claim):
        self.start_count += 1
        if self.error in ("rejected_decision", "revoked_policy"):
            raise PermissionError(self.error)
        self.state = "attempt_started"
        if self.error == "start_timeout":
            raise TimeoutError("ACK lost")
        return self.start_attempt_response

    def report_attempt(self, claim, result, event_key, confirmation=None):
        if self.report_error:
            raise TimeoutError("report unavailable")
        self.reports.append((result, event_key, confirmation))
        self.state = result["state"]
        return {"state": self.state}

    def reconciliation_credential(self, claim):
        return dict(
            purpose="reconcile_only",
            post_permitted=False,
            credential={"access_token": "PRIVATE_TOKEN"},
        )

    def post_consent(self, claim):
        return None

    def hold_claim(self, claim, reason):
        if self.state == "attempt_started":
            raise PermissionError("attempt_already_started")
        self.state = "held"
        return {"state": "held", "hold_reasons": [reason]}


class FakeAdapter:
    needs_delivery = False
    minimum_delivery_seconds = 0

    def __init__(self):
        self.post_count = 0
        self.reconcile_count = 0
        self.failure = None

    def bind(self, journal):
        self.journal = journal
        return self

    def preflight(self, connection, variant, now):
        return {"state": "verified"}

    def publish(self, connection, variant, attempt_id):
        self.post_count += 1
        if self.failure:
            raise self.failure
        return dict(
            state="published",
            remote_id="42_99",
            permalink=None,
            evidence={"receipt_sha256": "a" * 64},
        )

    def reconcile(self, connection, result):
        self.reconcile_count += 1
        return dict(state="uncertain", remote_id=None, permalink=None, evidence={})


@pytest.fixture
def dispatch_case(tmp_path):
    from publisher_worker.outbox import Outbox

    return (
        FakeClient(),
        Outbox(tmp_path / "outbox.sqlite3", tenant_id=7),
        {"facebook": FakeAdapter()},
        1000,
    )


def test_unconfirmed_start_never_posts(dispatch_case):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    client.start_attempt_response = {"confirmed": False}
    run_once(client, outbox, adapters, now)
    assert sum(a.post_count for a in adapters.values()) == 0


@pytest.mark.parametrize("failure", ["rejected_decision", "revoked_policy", "foreign_credential"])
def test_authority_failure_never_posts(dispatch_case, failure):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    client.error = failure
    run_once(client, outbox, adapters, now)
    assert adapters["facebook"].post_count == 0


def test_changed_bytes_and_no_stock(dispatch_case):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    client.content = b"different"
    run_once(client, outbox, adapters, now)
    run_once(client, outbox, adapters, now)
    assert client.start_count == adapters["facebook"].post_count == 0


def test_ack_loss_and_restart_never_posts(dispatch_case):
    from publisher_worker.client import run_once
    from publisher_worker.outbox import Outbox

    client, outbox, adapters, now = dispatch_case
    client.error = "start_timeout"
    run_once(client, outbox, adapters, now)
    restarted = Outbox(outbox.path, tenant_id=7)
    run_once(client, restarted, adapters, now + 600)
    assert client.start_count == 1
    assert adapters["facebook"].post_count == 0


def test_timeout_after_post_is_durable_and_never_reposted(dispatch_case):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    adapters["facebook"].failure = TimeoutError("https://secret?access_token=PRIVATE_TOKEN")
    run_once(client, outbox, adapters, now)
    run_once(client, outbox, adapters, now + 600)
    assert adapters["facebook"].post_count == 1
    assert client.reports[0][0]["state"] == "uncertain"
    assert "PRIVATE_TOKEN" not in outbox.path.read_bytes().decode(errors="ignore")


def test_report_replay_does_not_republish(dispatch_case):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    client.report_error = True
    run_once(client, outbox, adapters, now)
    client.report_error = False
    run_once(client, outbox, adapters, now + 600)
    assert adapters["facebook"].post_count == 1
    assert client.reports[-1][0]["state"] == "published"


def test_outbox_tenant_and_concurrent_phase_guard(tmp_path):
    from publisher_worker.outbox import Outbox

    box = Outbox(tmp_path / "box.db", tenant_id=7)
    box.reserve(dict(attempt_id="a", claim_id="c"), {"tenant_id": 7})
    with pytest.raises(ValueError):
        Outbox(box.path, tenant_id=8)

    def phase(_):
        return box.journal("a").begin("publish")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(phase, range(2))) == [False, True]


def test_failure_x_does_not_stop_facebook(dispatch_case):
    from publisher_worker.client import run_once
    from webapp.publications.contracts import canonical_hash

    client, outbox, adapters, now = dispatch_case
    facebook_claim, facebook_snapshot = client.claim.copy(), client.snapshot.copy()
    x_snapshot = client.snapshot | {
        "connection": dict(tenant_id=7, id=6, platform="x", remote_id="66"),
        "destination": "x:66",
    }
    x_claim = client.claim | {
        "attempt_id": "x-attempt",
        "claim_id": "x-claim",
        "contract_hash": canonical_hash(x_snapshot),
    }
    claims = [(x_claim, x_snapshot), (facebook_claim, facebook_snapshot)]

    def next_claim():
        if not claims:
            return None
        client.claim, client.snapshot = claims.pop(0)
        client.state = "reserved"
        return client.claim

    client.claim_due = next_claim
    x_adapter = FakeAdapter()
    x_adapter.preflight = lambda *_: {"state": "blocked_by_budget"}
    adapters["x"] = x_adapter
    results = run_once(client, outbox, adapters, now)
    assert len(results["results"]) == 2
    assert x_adapter.post_count == 0 and adapters["facebook"].post_count == 1


def test_process_lock_and_report_evidence_redaction(dispatch_case):
    from publisher_worker.client import run_once

    client, outbox, adapters, now = dispatch_case
    with outbox.exclusive() as acquired:
        assert acquired
        assert run_once(client, outbox, adapters, now)["state"] == "busy"
    adapters["facebook"].publish = lambda *_: dict(
        state="uncertain",
        remote_id=None,
        permalink=None,
        evidence={"error": "https://secret?access_token=PRIVATE_TOKEN"},
    )
    run_once(client, outbox, adapters, now)
    assert "PRIVATE_TOKEN" not in str(client.reports)


def test_ticket_lifetime_exact_binding_and_revocation(dispatch_case):
    from publisher_worker.media_delivery import MediaDelivery

    client, outbox, _adapters, now = dispatch_case
    outbox.reserve(client.claim, client.snapshot)
    ticket = dict(
        id=1,
        attempt_id="attempt:1",
        media_sha256=client.snapshot["media"]["sha256"],
        expires_at=4600,
        url="https://eikon.example/api/v1/publications/delivery-media/OPAQUE",
    )
    client.issue_ticket = lambda _: ticket
    revoked = []
    client.revoke_ticket = lambda a, t: revoked.append((a, t))
    delivery = MediaDelivery(client, outbox)
    with pytest.raises(ValueError, match="lifetime"):
        delivery.issue(client.claim, ticket["media_sha256"], now=now, minimum_seconds=3660)
    assert revoked == [("attempt:1", 1)]
    assert "OPAQUE" not in outbox.path.read_bytes().decode(errors="ignore")


def test_real_worker_http_contracts_both_engines(delivery_case, tmp_path, monkeypatch):
    import base64
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from publisher_worker.client import WorkerClient, run_once
    from publisher_worker.outbox import Outbox
    from webapp import db
    from webapp.tests.test_publication_delivery_concurrency import scheduled

    c = delivery_case
    c["app"].state.settings = replace(
        c["app"].state.settings, publication_vault_key=base64.urlsafe_b64encode(b"k" * 32).decode()
    )
    scheduled(c)
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    with TestClient(c["app"], base_url="https://testserver") as http:
        client = WorkerClient(
            "https://testserver", c["worker_token"], tenant_id=c["a"]["tenant"], http=http
        )
        outbox = Outbox(tmp_path / "real.db", tenant_id=client.tenant_id)
        adapter = FakeAdapter()
        result = run_once(client, outbox, {"facebook": adapter}, c["now"])
        assert result["results"][0]["state"] == "published", result
        assert adapter.post_count == 1
        run_once(client, outbox, {"facebook": adapter}, c["now"] + 600)
        assert adapter.post_count == 1
        with db.connect(c["url"]) as con:
            assert (
                con.execute(
                    "SELECT state FROM publication_deliveries WHERE tenant_id=?",
                    (client.tenant_id,),
                ).fetchone()["state"]
                == "published"
            )


def test_real_preflight_hold_visible_no_repeat_claim(delivery_case, tmp_path, monkeypatch):
    import base64
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from publisher_worker.client import WorkerClient, run_once
    from publisher_worker.outbox import Outbox
    from webapp.publications.deliveries import list_calendar
    from webapp.tests.test_publication_delivery_concurrency import scheduled

    c = delivery_case
    scheduled(c)
    c["app"].state.settings = replace(
        c["app"].state.settings, publication_vault_key=base64.b64encode(b"k" * 32).decode()
    )
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    with TestClient(c["app"], base_url="https://testserver") as http:
        client = WorkerClient(
            "https://testserver", c["worker_token"], tenant_id=c["a"]["tenant"], http=http
        )
        box = Outbox(tmp_path / "held.db", tenant_id=client.tenant_id)
        adapter = FakeAdapter()
        adapter.preflight = lambda *_: {"state": "unsupported_media"}
        results = run_once(client, box, {"facebook": adapter}, c["now"])
        assert results["results"] == [{"state": "held", "reason": "unsupported_media"}]
        assert run_once(client, box, {"facebook": adapter}, c["now"])["state"] == "idle"
        assert adapter.post_count == 0
        rows = list_calendar(c["url"], c["a"]["tenant"], c["a"]["owner"])
        assert rows["items"][0]["hold_reasons"] == ["unsupported_media"]


@pytest.mark.parametrize(
    ("body", "complete"),
    [
        ({"status_code": "FINISHED"}, True),
        ({"status_code": "PUBLISHED"}, True),
        ({"status_code": "IN_PROGRESS"}, False),
        ({"status_code": "UNKNOWN"}, False),
        ({}, False),
        ({"status_code": "ERROR"}, False),
        ({"status_code": "EXPIRED"}, False),
        ({"error": {"code": 190}}, False),
    ],
)
def test_instagram_restart_revokes_only_completed_container(tmp_path, body, complete):
    from publisher_worker.adapters.instagram import InstagramAdapter
    from publisher_worker.client import run_once
    from publisher_worker.outbox import Outbox
    from publisher_worker.tests.test_adapters import Response, Transport, account
    from webapp.publications.contracts import canonical_hash

    client = FakeClient()
    client.snapshot["connection"] = account("instagram", "instagram_login")
    client.snapshot["connection"].pop("credential")
    client.snapshot["destination"] = "instagram:42"
    client.claim["contract_hash"] = canonical_hash(client.snapshot)
    client.state, client.claimed = "uncertain", True
    path = tmp_path / "restart.db"
    box = Outbox(path, tenant_id=7)
    box.reserve(client.claim, client.snapshot)
    attempt = client.claim["attempt_id"]
    for old, new in [
        ("reserved", "start_requested"),
        ("start_requested", "start_confirmed"),
        ("start_confirmed", "dispatching"),
    ]:
        assert box.stage(attempt, old, new)
    journal = box.journal(attempt)
    assert journal.begin("container")
    journal.complete("container", {"id": "100", "receipt_sha256": "a" * 64})
    box.record_ticket(
        attempt, {"id": 1, "media_sha256": client.snapshot["media"]["sha256"], "expires_at": 4600}
    )
    revoked = []
    client.revoke_ticket = lambda claim, ticket: revoked.append((claim, ticket))
    transport = Transport([Response(body)])
    adapter = InstagramAdapter(transport, graph_version="v26.0")
    reopened = Outbox(path, tenant_id=7)
    run_once(client, reopened, {"instagram": adapter}, 1600)
    assert client.reports[-1][0]["state"] == "uncertain"
    assert client.reports[-1][0]["remote_id"] is None
    assert client.reports[-1][2] is None
    assert client.start_count == 0
    assert [c[0] for c in transport.calls] == ["GET"]
    assert bool(revoked) is complete
    assert bool(reopened.tickets()) is not complete
    assert bool(reopened.journal(attempt).read("container_processed")) is complete


@pytest.mark.parametrize("interrupted_receipt", [False, True])
def test_instagram_completion_survives_crash_before_ticket_revocation(
    tmp_path, interrupted_receipt
):
    from publisher_worker.adapters.instagram import InstagramAdapter
    from publisher_worker.client import run_once
    from publisher_worker.outbox import Outbox
    from publisher_worker.tests.test_adapters import Response, Transport, account
    from webapp.publications.contracts import canonical_hash

    client = FakeClient()
    client.snapshot["connection"] = account("instagram", "instagram_login")
    client.snapshot["connection"].pop("credential")
    client.snapshot["destination"] = "instagram:42"
    client.claim["contract_hash"] = canonical_hash(client.snapshot)
    client.state, client.claimed = "uncertain", True
    path = tmp_path / "crash.db"
    box = Outbox(path, tenant_id=7)
    box.reserve(client.claim, client.snapshot)
    attempt = client.claim["attempt_id"]
    journal = box.journal(attempt)
    assert journal.begin("container")
    journal.complete("container", {"id": "100", "receipt_sha256": "a" * 64})
    if interrupted_receipt:
        assert journal.begin("container_processed")
    box.record_ticket(
        attempt, {"id": 1, "media_sha256": client.snapshot["media"]["sha256"], "expires_at": 4600}
    )
    transport = Transport([Response({"status_code": "FINISHED"}), TimeoutError()])
    adapter = InstagramAdapter(transport, graph_version="v26.0").bind(journal)
    connection = client.snapshot["connection"] | {"credential": client.credential(client.claim)}
    # Caída después de persistir el estado, antes de informar/revocar.
    result = adapter.reconcile(connection, {"remote_id": None})
    assert result["state"] == "uncertain"
    revoked = []
    client.revoke_ticket = lambda claim, ticket: revoked.append((claim, ticket))
    reopened = Outbox(path, tenant_id=7)
    run_once(
        client, reopened, {"instagram": InstagramAdapter(transport, graph_version="v26.0")}, 1600
    )
    assert revoked == [(attempt, 1)]
    assert reopened.tickets() == []
    assert client.start_count == 0
    assert client.reports[-1][0]["state"] == "uncertain"
    assert [c[0] for c in transport.calls] == ["GET", "GET"]


__all__ = ["campaign_case", "campaign_clients", "delivery_case", "isolated_db"]


def test_facebook_feed_video_durable_restart_confirms_without_new_start_or_post(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter
    from publisher_worker.client import run_once
    from publisher_worker.outbox import Outbox
    from publisher_worker.tests.test_adapters import Response, Transport, account, feed_video_post
    from webapp.publications.contracts import canonical_hash

    client = FakeClient()
    client.snapshot["connection"] = account()
    client.snapshot["connection"].pop("credential")
    client.claim["contract_hash"] = canonical_hash(client.snapshot)
    client.state, client.claimed = "uncertain", True
    path = tmp_path / "restart.db"
    box = Outbox(path, tenant_id=7)
    box.reserve(client.claim, client.snapshot)
    attempt = client.claim["attempt_id"]
    phase = box.journal(attempt)
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})
    transport = Transport([Response({"data": [feed_video_post()]})])
    reopened = Outbox(path, tenant_id=7)
    run_once(
        client, reopened, {"facebook": FacebookAdapter(transport, graph_version="v26.0")}, 1600
    )
    result, _, confirmation = client.reports[-1]
    assert result["state"] == "published" and result["remote_id"] == "42_99"
    assert confirmation["remote_id"] == "42_99"
    assert confirmation["normalized_destination"] == "facebook:42"
    assert confirmation["attempt_id"] == attempt
    assert confirmation["receipt"]["operation"] == "remote_lookup"
    run_once(
        client, reopened, {"facebook": FacebookAdapter(transport, graph_version="v26.0")}, 1700
    )
    assert client.start_count == 0
    assert [c[0] for c in transport.calls] == ["GET"]
    assert reopened.active() == []


def test_facebook_feed_video_revoked_recovery_authority_never_reads_provider(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter
    from publisher_worker.client import run_once
    from publisher_worker.outbox import Outbox
    from publisher_worker.tests.test_adapters import Transport

    client = FakeClient()
    client.state, client.claimed = "uncertain", True
    box = Outbox(tmp_path / "revoked.db", tenant_id=7)
    box.reserve(client.claim, client.snapshot)
    phase = box.journal(client.claim["attempt_id"])
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})

    def revoked(claim):
        raise PermissionError("grant_revoked")

    client.reconciliation_credential = revoked
    transport = Transport([])
    run_once(client, box, {"facebook": FacebookAdapter(transport, graph_version="v26.0")}, 1600)
    assert client.start_count == 0 and transport.calls == []
    assert box.active()
