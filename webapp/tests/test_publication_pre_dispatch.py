"""Dual-authority closure: original worker evidence plus current owner, no POST."""

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from publisher_worker.client import WorkerClient
from publisher_worker.outbox import Outbox
from publisher_worker.pre_dispatch import attest, sync_terminal_ack
from webapp import db
from webapp.publications import deliveries
from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
from webapp.publications.connections import put_connection
from webapp.publications.contracts import PublicationError, canonical_hash
from webapp.publications.decisions import append_ai_decision
from webapp.publications.media_delivery import issue_media_ticket, revoke_media_ticket
from webapp.publications.oauth import import_credential
from webapp.publications.oauth_providers import OfficialOAuthClient
from webapp.publications.policies import set_policy
from webapp.publications.pre_dispatch import close_before_dispatch
from webapp.tests.test_publication_campaigns import campaign, freeze
from webapp.tests.test_publication_decisions import evaluated
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case as _campaign_case,
)
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_clients as _campaign_clients,
)
from webapp.tests.test_publication_delivery_concurrency import (
    history,
)
from webapp.tests.test_publication_delivery_concurrency import (
    isolated_db as _isolated_db,
)
from webapp.tests.test_publication_instagram_refresh import (
    OLD_TOKEN,
    InstagramNetwork,
    RefreshDuringImport,
    config,
)
from webapp.tests.test_publication_policies import policy_payload

campaign_case = _campaign_case
campaign_clients = _campaign_clients
isolated_db = _isolated_db


@pytest.fixture
def pre_dispatch_case(campaign_case, tmp_path):
    url, (a, b), app = campaign_case
    now = int(time.time()) + 5
    account = put_connection(
        url,
        a["tenant"],
        a["owner"],
        {
            "platform": "instagram",
            "api_mode": "instagram_login",
            "remote_id": "ig-42",
            "project_ids": [a["project"]["id"]],
        },
    )
    official = OfficialOAuthClient(config(), httpx.MockTransport(InstagramNetwork()))
    try:
        account = import_credential(
            url,
            a["tenant"],
            a["owner"],
            account["id"],
            {"access_token": OLD_TOKEN},
            now - 5,
            RefreshDuringImport(official),
            key=b"k" * 32,
            key_id="test",
            dry_run=False,
        )
    finally:
        official.close()
    assert account["status"] == "active"
    set_policy(
        url,
        a["tenant"],
        a["owner"],
        1,
        policy_payload(a["project"]["id"], a["brand"]["id"], account["id"]),
    )
    jpeg = io.BytesIO()
    Image.new("RGB", (512, 512), "teal").save(jpeg, format="JPEG")
    response = a["client"].post(
        "/api/v1/media",
        headers={"Idempotency-Key": "pre-dispatch-jpeg"},
        data={"brief_id": a["brief"]["id"], "source": "codex", "provenance": '{"tool":"test"}'},
        files={"file": ("piece.jpeg", jpeg.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    revision = freeze(
        url,
        a,
        campaign(url, a),
        media_id=response.json()["id"],
        connection_id=account["id"],
        policy_version=2,
        scheduled_at=datetime.fromtimestamp(now, UTC).isoformat(),
    )
    reviewer_token, grant = issue_grant(
        url, a["tenant"], a["owner"], "reviewer", "own-codex", 2, now + 20000
    )
    case = dict(
        url=url,
        a=a,
        b=b,
        app=app,
        revision=revision,
        grant=grant,
        token=reviewer_token,
        principal=resolve_grant(url, reviewer_token, "reviewer", now),
        now=now,
    )
    append_ai_decision(url, case["principal"], evaluated(case) | {"policy_version": 2}, now)
    token, _ = issue_grant(
        url, a["tenant"], a["owner"], "worker", "original-worker", 2, now + 20000
    )
    case.update(worker_token=token, worker=resolve_grant(url, token, "worker", now))
    history(
        case,
        [
            {
                "source_delivery_id": "old-instagram",
                "platform": "instagram",
                "normalized_destination": "instagram:ig-42",
                "image_sha256": "b" * 64,
                "state": "published",
                "receipt": {"remote_id": "old-post"},
                "original": {"completed_at": "2020-01-01T10:00:00Z"},
            }
        ],
    )
    deliveries.schedule_revision(url, a["tenant"], revision["id"], now)
    claim = deliveries.claim_due(url, case["worker"], now)
    assert claim
    _, mime = deliveries.claim_original(
        url, app.state.storage, case["worker"], claim["claim_id"], now
    )
    assert mime == "image/jpeg"
    deliveries.start_attempt(url, case["worker"], claim["claim_id"], claim["contract_hash"], now)
    deliveries.report_attempt(
        url,
        case["worker"],
        claim["attempt_id"],
        "local-no-dispatch",
        {
            "state": "uncertain",
            "remote_id": None,
            "permalink": None,
            "evidence": {"error_code": "status_unavailable"},
        },
        now + 1,
    )
    box = Outbox(tmp_path / "worker-original.sqlite3", tenant_id=a["tenant"])
    assert box.reserve(claim, revision["snapshot"])
    assert box.stage(claim["attempt_id"], "reserved", "start_confirmed")
    quarantined = box.quarantine_before_dispatch(
        claim,
        contract_hash=claim["contract_hash"],
        media_sha256=revision["snapshot"]["media"]["sha256"],
        now=now + 2,
    )
    case.update(
        claim=claim, box=box, attestation_body=quarantined | {"event_key": "original:quarantine"}
    )
    return case


def worker_attest(case, body=None, token=None):
    with TestClient(case["app"], base_url="https://testserver") as client:
        return client.post(
            f"/api/v1/publications/worker/attempts/{case['claim']['attempt_id']}/pre-dispatch-attestations",
            headers={"Authorization": "Bearer " + (token or case["worker_token"])},
            json=body or case["attestation_body"],
        )


def close_body(case, attestation):
    status = deliveries.get_claim(
        case["url"], case["worker"], case["claim"]["claim_id"], case["now"] + 2
    )
    return {
        "event_key": "owner:close-before-dispatch",
        "attestation_id": attestation["attestation_id"],
        "manifest_sha256": attestation["manifest_sha256"],
        "expected_result_hash": canonical_hash(status["result"]),
        "qualification": {
            "kind": "operator_verified_original_worker",
            "schema_version": 1,
            "code_sha256": "c" * 64,
            "outbox_sha256": "d" * 64,
            "historical_config_sha256": "e" * 64,
            "process_exclusion_sha256": "f" * 64,
        },
    }


def owner_close(case, body, client=None):
    return (client or case["a"]["client"]).post(
        f"/api/v1/publications/attempts/{case['claim']['attempt_id']}/close-before-dispatch",
        json=body,
    )


def test_original_worker_and_owner_close_preserve_binding_and_block_all_retries(pre_dispatch_case):
    c = pre_dispatch_case
    response = worker_attest(c)
    assert response.status_code == 201, response.text
    attestation = response.json()
    body = close_body(c, attestation)
    with db.connect(c["url"]) as con:
        before = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=?",
            (c["a"]["tenant"], c["claim"]["attempt_id"]),
        ).fetchone()
        guard_count = con.execute(
            "SELECT COUNT(*) AS n FROM publication_media_guards WHERE tenant_id=?",
            (c["a"]["tenant"],),
        ).fetchone()["n"]
    closed = owner_close(c, body)
    assert closed.status_code == 200, closed.text
    assert (
        closed.json()["state"] == "failed" and closed.json()["reason"] == "failed_before_dispatch"
    )
    assert closed.json()["post_permitted"] is False
    assert owner_close(c, body).json() == closed.json()
    assert worker_attest(c).json() == attestation
    changed = body | {"qualification": body["qualification"] | {"code_sha256": "b" * 64}}
    assert owner_close(c, changed).status_code == 409
    status = deliveries.get_claim(c["url"], c["worker"], c["claim"]["claim_id"], c["now"] + 3)
    assert status["result"] == {
        "state": "failed",
        "remote_id": None,
        "permalink": None,
        "evidence": {"error_code": "failed_before_dispatch"},
    }
    c["box"].complete_pre_dispatch(c["claim"], status)
    assert deliveries.claim_due(c["url"], c["worker"], c["now"] + 4) is None
    with pytest.raises(PublicationError):
        deliveries.start_attempt(
            c["url"], c["worker"], c["claim"]["claim_id"], c["claim"]["contract_hash"], c["now"] + 4
        )
    with pytest.raises(PublicationError):
        issue_media_ticket(c["url"], c["worker"], c["claim"]["attempt_id"], c["now"] + 4)
    with db.connect(c["url"]) as con:
        after = con.execute(
            "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=?",
            (c["a"]["tenant"], c["claim"]["attempt_id"]),
        ).fetchone()
        for key in before:
            if key not in {"state", "result_json"}:
                assert after[key] == before[key]
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_media_guards WHERE tenant_id=?",
                (c["a"]["tenant"],),
            ).fetchone()["n"]
            == guard_count
        )
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='failed_before_dispatch'",
                (c["a"]["tenant"], c["claim"]["attempt_id"]),
            ).fetchone()["n"]
            == 1
        )


def test_attestation_digest_and_original_grant_are_authority_bound(pre_dispatch_case):
    c = pre_dispatch_case
    changed = c["attestation_body"] | {"manifest_sha256": "b" * 64}
    assert worker_attest(c, changed).status_code in {409, 422}
    token, _ = issue_grant(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        "worker",
        "replacement-worker",
        2,
        c["now"] + 1000,
    )
    assert worker_attest(c, token=token).status_code in {403, 404, 409}
    assert worker_attest(c).status_code == 201
    mutated = c["attestation_body"]["manifest"] | {"claim_id": "claim:other"}
    assert (
        worker_attest(
            c,
            c["attestation_body"]
            | {"manifest": mutated, "manifest_sha256": canonical_hash(mutated)},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("historical", ["revoked", "expired"])
def test_any_historical_api_ticket_blocks_owner_close(pre_dispatch_case, historical):
    c = pre_dispatch_case
    attestation = worker_attest(c)
    assert attestation.status_code == 201, attestation.text
    body = close_body(c, attestation.json())
    ticket = issue_media_ticket(
        c["url"], c["worker"], c["claim"]["attempt_id"], c["now"] + 2, ttl_seconds=1
    )
    if historical == "revoked":
        revoke_media_ticket(
            c["url"], c["worker"], c["claim"]["attempt_id"], ticket["id"], c["now"] + 2
        )
        response = owner_close(c, body)
        assert response.status_code == 409, response.text
    else:
        assert ticket["expires_at"] < c["now"] + 4
        with pytest.raises(PublicationError) as error:
            close_before_dispatch(
                c["url"],
                c["a"]["tenant"],
                c["a"]["owner"],
                c["claim"]["attempt_id"],
                body,
                c["now"] + 4,
            )
        assert error.value.code == "pre_dispatch_historical_ticket_exists"
    assert (
        deliveries.get_claim(c["url"], c["worker"], c["claim"]["claim_id"], c["now"] + 3)["state"]
        == "uncertain"
    )


def test_historical_remote_receipt_blocks_even_without_current_remote_id(pre_dispatch_case):
    c = pre_dispatch_case
    # This is a real validated uncertain report; receipt proves possible remote work.
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        c["claim"]["attempt_id"],
        "remote-evidence",
        {
            "state": "uncertain",
            "remote_id": None,
            "permalink": None,
            "evidence": {"receipt_sha256": "a" * 64},
        },
        c["now"] + 2,
    )
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        c["claim"]["attempt_id"],
        "empty-later",
        {
            "state": "uncertain",
            "remote_id": None,
            "permalink": None,
            "evidence": {},
        },
        c["now"] + 3,
    )
    response = worker_attest(c)
    assert response.status_code == 409, response.text


@pytest.mark.parametrize("source", ["current_result", "historical_event"])
@pytest.mark.parametrize("gate", ["attestation", "owner_closure"])
def test_lone_publication_timestamp_blocks_pre_dispatch(pre_dispatch_case, source, gate):
    from webapp.publications.ledger import append_event

    c = pre_dispatch_case
    body = close_body(c, worker_attest(c).json()) if gate == "owner_closure" else None
    stamp = {"published_at_utc": c["now"]}
    if source == "current_result":
        # Legacy/corrupt stored data must fail closed even without a receipt.
        with db.connect(c["url"]) as con:
            con.execute(
                "UPDATE publication_deliveries SET result_json=? WHERE tenant_id=? AND attempt_id=?",
                (json.dumps(stamp), c["a"]["tenant"], c["claim"]["attempt_id"]),
            )
    else:
        append_event(
            c["url"],
            c["a"]["tenant"],
            c["claim"]["attempt_id"],
            "historical:publication-timestamp",
            "historical_provider_result",
            stamp,
        )
    response = owner_close(c, body) if gate == "owner_closure" else worker_attest(c)
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "pre_dispatch_remote_evidence_exists"
    with db.connect(c["url"]) as con:
        row = con.execute(
            "SELECT state,started_at FROM publication_deliveries WHERE tenant_id=? AND attempt_id=?",
            (c["a"]["tenant"], c["claim"]["attempt_id"]),
        ).fetchone()
        assert row == {"state": "uncertain", "started_at": c["now"]}


def test_owner_tenant_auth_and_original_grant_revalidated_at_close(pre_dispatch_case):
    c = pre_dispatch_case
    attestation = worker_attest(c)
    assert attestation.status_code == 201, attestation.text
    body = close_body(c, attestation.json())
    assert owner_close(c, body, c["b"]["client"]).status_code in {403, 404}
    with TestClient(c["app"]) as anonymous:
        assert owner_close(c, {}, anonymous).status_code in {401, 403}
    revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
    assert owner_close(c, body).status_code == 403


def test_ticket_and_close_serialized_only_one_path_wins(pre_dispatch_case):
    c = pre_dispatch_case
    attestation = worker_attest(c)
    assert attestation.status_code == 201, attestation.text
    body = close_body(c, attestation.json())
    barrier = Barrier(2)

    def ticket():
        barrier.wait()
        try:
            issue_media_ticket(c["url"], c["worker"], c["claim"]["attempt_id"], c["now"] + 2)
            return True
        except PublicationError:
            return False

    def close():
        barrier.wait()
        try:
            close_before_dispatch(
                c["url"],
                c["a"]["tenant"],
                c["a"]["owner"],
                c["claim"]["attempt_id"],
                body,
                c["now"] + 2,
            )
            return True
        except PublicationError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.submit(ticket), pool.submit(close)
        assert left.result() != right.result()


def test_closure_event_failure_rolls_back_cas_and_can_be_replayed(pre_dispatch_case, monkeypatch):
    from webapp.publications import pre_dispatch

    c = pre_dispatch_case
    attestation = worker_attest(c).json()
    body = close_body(c, attestation)
    previous = deliveries.get_claim(c["url"], c["worker"], c["claim"]["claim_id"], c["now"] + 2)
    event = pre_dispatch._event

    def fail(con, row, key, kind, payload, now):
        if kind == "failed_before_dispatch":
            raise RuntimeError("append_failure")
        return event(con, row, key, kind, payload, now)

    with monkeypatch.context() as patch:
        patch.setattr(pre_dispatch, "_event", fail)
        with pytest.raises(RuntimeError, match="append_failure"):
            close_before_dispatch(
                c["url"],
                c["a"]["tenant"],
                c["a"]["owner"],
                c["claim"]["attempt_id"],
                body,
                c["now"] + 3,
            )
    current = deliveries.get_claim(c["url"], c["worker"], c["claim"]["claim_id"], c["now"] + 3)
    assert current["state"] == "uncertain" and current["result"] == previous["result"]
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='failed_before_dispatch'",
                (c["a"]["tenant"], c["claim"]["attempt_id"]),
            ).fetchone()["n"]
            == 0
        )
    assert owner_close(c, body).status_code == 200


def test_result_drift_and_unqualified_digest_rejected_without_closure(pre_dispatch_case):
    c = pre_dispatch_case
    body = close_body(c, worker_attest(c).json())
    assert (
        owner_close(
            c,
            body
            | {
                "qualification": body["qualification"]
                | {"raw_evidence": "synthetic-private-content"}
            },
        ).status_code
        == 422
    )
    assert (
        owner_close(
            c,
            body
            | {"qualification": body["qualification"] | {"process_exclusion_sha256": "unverified"}},
        ).status_code
        == 422
    )
    assert owner_close(c, body | {"manifest_sha256": "b" * 64}).status_code == 409
    deliveries.report_attempt(
        c["url"],
        c["worker"],
        c["claim"]["attempt_id"],
        "new-local-state",
        {"state": "uncertain", "remote_id": None, "permalink": None, "evidence": {}},
        c["now"] + 3,
    )
    response = owner_close(c, body)
    assert (
        response.status_code == 409 and response.json()["detail"] == "pre_dispatch_result_changed"
    )


def test_closure_keeps_daily_usage_and_same_sha_blocks_new_revision(pre_dispatch_case):
    c = pre_dispatch_case
    body = close_body(c, worker_attest(c).json())
    assert owner_close(c, body).status_code == 200
    snapshot = c["revision"]["snapshot"]
    with db.connect(c["url"]) as con:
        count, stamps, _ = deliveries._destination_usage(
            con,
            c["a"]["tenant"],
            snapshot["destination"],
            snapshot["policy_timezone"],
            snapshot["scheduled_local_date"],
            c["now"] + 3,
        )
    assert count == 1 and c["now"] in stamps
    c["revision"] = freeze(
        c["url"],
        c["a"],
        campaign(c["url"], c["a"]),
        caption="Nueva descripción conserva la imagen",
        media_id=snapshot["media"]["id"],
        connection_id=snapshot["connection"]["id"],
        policy_version=2,
        scheduled_at=datetime.fromtimestamp(c["now"] + 3, UTC).isoformat(),
    )
    append_ai_decision(c["url"], c["principal"], evaluated(c) | {"policy_version": 2}, c["now"] + 3)
    row = deliveries.schedule_revision(
        c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"] + 3
    )
    assert row["state"] == "held" and "media_already_attempted" in row["hold_reasons"]
    assert deliveries.claim_due(c["url"], c["worker"], c["now"] + 3) is None


def test_helper_real_authenticated_api_attestation_then_owner_then_get_ack(pre_dispatch_case):
    c = pre_dispatch_case
    paths = []
    with TestClient(c["app"], base_url="https://testserver") as bridge:

        def handle(request):
            paths.append((request.method, request.url.path))
            response = bridge.request(
                request.method,
                str(request.url),
                headers=dict(request.headers),
                content=request.content,
            )
            return httpx.Response(
                response.status_code, content=response.content, headers=response.headers
            )

        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            worker = WorkerClient(
                "https://testserver", c["worker_token"], tenant_id=c["a"]["tenant"], http=http
            )
            receipt = attest(
                c["box"],
                worker,
                c["claim"],
                contract_hash=c["claim"]["contract_hash"],
                media_sha256=c["revision"]["snapshot"]["media"]["sha256"],
                now=c["now"] + 2,
            )
            with pytest.raises(ValueError):
                sync_terminal_ack(c["box"], worker, c["claim"])
            assert owner_close(c, close_body(c, receipt)).status_code == 200
            assert sync_terminal_ack(c["box"], worker, c["claim"])["terminal_ack_read"] is True
    assert paths[0][0] == "POST" and paths[0][1].endswith("/pre-dispatch-attestations")
    assert len(paths) == 3 and all(
        method == "GET" and "/claims/" in path for method, path in paths[1:]
    )
    with c["box"].connect() as con:
        assert con.execute("SELECT done FROM attempts").fetchone() == (1,)


@pytest.mark.parametrize("invalid", ["duplicate", "oversize"])
def test_attestation_json_caps_and_ambiguity_rejected(pre_dispatch_case, invalid):
    c = pre_dispatch_case
    raw = json.dumps(c["attestation_body"])
    raw = (
        raw[:-1] + ',"event_key":"original:quarantine"}'
        if invalid == "duplicate"
        else '{"raw":"' + "x" * 16385 + '"}'
    )
    with TestClient(c["app"], base_url="https://testserver") as worker:
        response = worker.post(
            f"/api/v1/publications/worker/attempts/{c['claim']['attempt_id']}/pre-dispatch-attestations",
            headers={
                "Authorization": "Bearer " + c["worker_token"],
                "Content-Type": "application/json",
            },
            content=raw,
        )
    assert response.status_code == 422
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='pre_dispatch_attested'",
                (c["a"]["tenant"], c["claim"]["attempt_id"]),
            ).fetchone()["n"]
            == 0
        )


def test_worker_attestation_auth_is_scoped_and_owner_cannot_use_worker_grant(pre_dispatch_case):
    c = pre_dispatch_case
    worker_path = (
        f"/api/v1/publications/worker/attempts/{c['claim']['attempt_id']}/pre-dispatch-attestations"
    )
    with TestClient(c["app"], base_url="http://testserver") as insecure:
        assert (
            insecure.post(
                worker_path,
                headers={"Authorization": "Bearer " + c["worker_token"]},
                json=c["attestation_body"],
            ).status_code
            == 403
        )
    assert worker_attest(c, token=c["token"]).status_code in {401, 403}
    assert c["a"]["client"].post(worker_path, json=c["attestation_body"]).status_code in {401, 403}
    body = close_body(c, worker_attest(c).json())
    with TestClient(c["app"], base_url="https://testserver") as worker:
        response = worker.post(
            f"/api/v1/publications/attempts/{c['claim']['attempt_id']}/close-before-dispatch",
            headers={"Authorization": "Bearer " + c["worker_token"]},
            json=body,
        )
    assert response.status_code in {401, 403}
