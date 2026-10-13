"""Original outbox quarantine closes mutation seams before an owner can close."""

import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from publisher_worker.client import WorkerAPIError, WorkerClient
from publisher_worker.outbox import Outbox
from publisher_worker.pre_dispatch import attest, read_private_worker_grant, sync_terminal_ack
from webapp.publications.contracts import canonical_hash


@pytest.fixture
def original_box(tmp_path):
    snapshot = {
        "tenant_id": 17,
        "media": {"kind": "gallery_image", "mime": "image/jpeg", "sha256": "a" * 64},
        "connection": {"tenant_id": 17, "platform": "instagram"},
        "destination": "instagram:42",
    }
    claim = {
        "attempt_id": "attempt:original",
        "claim_id": "claim:original",
        "delivery_id": 4,
        "lease_until": 1000,
        "contract_hash": canonical_hash(snapshot),
    }
    box = Outbox(tmp_path / "original.sqlite3", tenant_id=17)
    assert box.reserve(claim, snapshot)
    assert box.stage(claim["attempt_id"], "reserved", "start_confirmed")
    box.queue_report(
        claim["attempt_id"],
        {
            "state": "uncertain",
            "remote_id": None,
            "permalink": None,
            "evidence": {"error_code": "status_unavailable"},
        },
    )
    return box, claim, snapshot


def quarantine(case, **overrides):
    box, claim, _ = case
    return box.quarantine_before_dispatch(
        claim,
        contract_hash=overrides.get("contract_hash", claim["contract_hash"]),
        media_sha256=overrides.get("media_sha256", "a" * 64),
        now=2000,
    )


def test_quarantine_preserves_previous_report_and_seals_original_attempt(original_box):
    box, claim, _ = original_box
    before = box.active()[0]
    attestation = quarantine(original_box)
    assert attestation["manifest"]["tenant_id"] == 17
    assert attestation["manifest"]["attempt_id"] == "attempt:original"
    assert attestation["manifest"]["phase_count"] == 0
    assert attestation["manifest"]["local_ticket_count"] == 0
    assert (
        hashlib.sha256(
            json.dumps(attestation["manifest"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == attestation["manifest_sha256"]
    )
    assert box.active() == []
    assert box.stage(claim["attempt_id"], "quarantined_before_dispatch", "dispatching") is False
    assert box.journal(claim["attempt_id"]).begin("instagram:create") is False
    box.finish_local(claim["attempt_id"])
    box.reported(claim["attempt_id"], True)
    with box.connect() as con:
        row = con.execute("SELECT stage,pending,result,done FROM attempts").fetchone()
    assert row[0] == "quarantined_before_dispatch" and row[3] == 0
    assert json.loads(row[1]) == before["pending"] and json.loads(row[2]) == before["result"]
    assert quarantine(original_box) == attestation


def test_phase_without_receipt_still_blocks_quarantine(original_box):
    box, claim, _ = original_box
    assert box.journal(claim["attempt_id"]).begin("instagram:create")
    assert box.journal(claim["attempt_id"]).read("instagram:create") is None
    with pytest.raises(ValueError):
        quarantine(original_box)
    assert len(box.active()) == 1


def test_revoked_expired_local_ticket_still_blocks_quarantine(original_box):
    box, claim, _ = original_box
    box.record_ticket(claim["attempt_id"], {"id": 3, "media_sha256": "a" * 64, "expires_at": 1})
    box.revoked(claim["attempt_id"], 3)
    with pytest.raises(ValueError):
        quarantine(original_box)


@pytest.mark.parametrize("field", ["contract_hash", "media_sha256"])
def test_binding_mismatch_does_not_quarantine(original_box, field):
    with pytest.raises(ValueError):
        quarantine(original_box, **{field: "b" * 64})
    assert len(original_box[0].active()) == 1


def test_foreign_tenant_cannot_open_original_outbox(original_box):
    with pytest.raises(ValueError, match="outbox_tenant_mismatch"):
        Outbox(original_box[0].path, tenant_id=18)


def test_phase_and_quarantine_race_never_both_win(original_box):
    box, claim, _ = original_box
    barrier = Barrier(2)

    def begin():
        barrier.wait()
        return box.journal(claim["attempt_id"]).begin("instagram:create")

    def seal():
        barrier.wait()
        try:
            quarantine(original_box)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        phase, sealed = pool.submit(begin), pool.submit(seal)
        assert phase.result() != sealed.result()


def test_terminal_ack_required_and_original_snapshot_bound(original_box):
    box, claim, snapshot = original_box
    manifest = quarantine(original_box)
    result = {
        "state": "failed",
        "remote_id": None,
        "permalink": None,
        "evidence": {"error_code": "failed_before_dispatch"},
    }
    status = {
        "state": "failed",
        "attempt_id": claim["attempt_id"],
        "post_permitted": False,
        "contract_hash": claim["contract_hash"],
        "snapshot": snapshot,
        "result": result,
    }
    for changed in [
        {"state": "uncertain"},
        {"post_permitted": True},
        {"attempt_id": "attempt:other"},
        {"contract_hash": "b" * 64},
    ]:
        with pytest.raises(ValueError):
            box.complete_pre_dispatch(claim, status | changed)
    box.complete_pre_dispatch(claim, status)
    box.complete_pre_dispatch(claim, status)
    with box.connect() as con:
        assert con.execute("SELECT done FROM attempts").fetchone() == (1,)
        assert con.execute("SELECT COUNT(*) FROM pre_dispatch_acknowledgements").fetchone() == (1,)
        assert con.execute("SELECT manifest_sha256 FROM pre_dispatch_manifests").fetchone() == (
            manifest["manifest_sha256"],
        )


def test_outbox_exclusion_and_failed_manifest_insert_leave_attempt_unchanged(original_box):
    box, claim, _ = original_box
    with box.exclusive() as held:
        assert held
        with pytest.raises(ValueError, match="outbox_worker_active"):
            quarantine(original_box)
    with box.connect() as con:
        con.execute(
            "CREATE TRIGGER failed_seal BEFORE INSERT ON pre_dispatch_manifests BEGIN SELECT RAISE(ABORT,'disk_failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="disk_failure"):
        quarantine(original_box)
    with box.connect() as con:
        assert con.execute(
            "SELECT stage,done FROM attempts WHERE attempt=?", (claim["attempt_id"],)
        ).fetchone() == ("start_confirmed", 0)
        assert con.execute("SELECT COUNT(*) FROM pre_dispatch_manifests").fetchone() == (0,)


def test_quarantine_immutable_and_database_dispatch_guards(original_box):
    box, claim, _ = original_box
    quarantine(original_box)
    for query in (
        "UPDATE pre_dispatch_manifests SET manifest='{}'",
        "DELETE FROM pre_dispatch_manifests",
        "UPDATE attempts SET done=1",
        "UPDATE attempts SET stage='dispatching'",
        "INSERT INTO phases VALUES ('attempt:original','instagram:create',NULL)",
        "INSERT INTO tickets VALUES ('attempt:original',10,'a',1000,0)",
    ):
        with pytest.raises(sqlite3.IntegrityError), box.connect() as con:
            con.execute(query)
    assert not box.journal(claim["attempt_id"]).begin("instagram:create")


@pytest.mark.parametrize(
    "invalid",
    ["public", "symlink", "hardlink", "whitespace", "owner", "empty", "large", "prefix_only"],
)
def test_worker_grant_requires_private_scoped_regular_file(tmp_path, invalid):
    token = tmp_path / "grant"
    token.write_text("eikon_pub_worker_synthetic-test-token")
    token.chmod(0o600)
    if invalid == "public":
        token.chmod(0o644)
    elif invalid == "symlink":
        link = tmp_path / "link"
        link.symlink_to(token)
        token = link
    elif invalid == "hardlink":
        os.link(token, tmp_path / "link")
    elif invalid == "whitespace":
        token.write_text("eikon_pub_worker_synthetic-test-token\n")
    elif invalid == "owner":
        token.write_text("eikon_pub_owner_synthetic-test-token")
    elif invalid == "empty":
        token.write_text("")
    elif invalid == "large":
        token.write_text("eikon_pub_worker_" + "x" * 16385)
    elif invalid == "prefix_only":
        token.write_text("eikon_pub_worker_")
    with pytest.raises((ValueError, OSError)):
        read_private_worker_grant(token)


def test_helper_only_attests_then_reads_authenticated_terminal_ack(original_box):
    box, claim, snapshot = original_box
    paths = []
    sealed = quarantine(original_box)
    receipt = dict(
        attestation_id=1,
        attempt_id=claim["attempt_id"],
        tenant_id=17,
        manifest_sha256=sealed["manifest_sha256"],
        worker_grant_id=3,
        post_permitted=False,
        state="attested_before_dispatch",
        attested_at=2000,
    )
    status = dict(
        state="failed",
        attempt_id=claim["attempt_id"],
        post_permitted=False,
        contract_hash=claim["contract_hash"],
        snapshot=snapshot,
        result={
            "state": "failed",
            "remote_id": None,
            "permalink": None,
            "evidence": {"error_code": "failed_before_dispatch"},
        },
    )

    def handle(request):
        assert request.headers["Authorization"] == "Bearer eikon_pub_worker_synthetic-test-token"
        paths.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.url.path.endswith("/pre-dispatch-attestations")
            assert json.loads(request.content)["manifest_sha256"] == sealed["manifest_sha256"]
            return httpx.Response(201, json=receipt)
        assert request.method == "GET" and "/claims/" in request.url.path
        return httpx.Response(200, json=status)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        client = WorkerClient(
            "https://example.test", "eikon_pub_worker_synthetic-test-token", tenant_id=17, http=http
        )
        assert (
            attest(
                box,
                client,
                claim,
                contract_hash=claim["contract_hash"],
                media_sha256="a" * 64,
                now=2000,
            )
            == receipt
        )
        with box.connect() as con:
            assert con.execute("SELECT done FROM attempts").fetchone() == (0,)
        assert sync_terminal_ack(box, client, claim)["terminal_ack_read"] is True
    assert len(paths) == 2
    with box.connect() as con:
        assert con.execute("SELECT done FROM attempts").fetchone() == (1,)


def test_attestation_transport_failure_preserves_quarantine_without_retry(original_box):
    box, claim, _ = original_box
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        client = WorkerClient(
            "https://example.test", "eikon_pub_worker_synthetic-test-token", tenant_id=17, http=http
        )
        with pytest.raises(WorkerAPIError):
            attest(
                box,
                client,
                claim,
                contract_hash=claim["contract_hash"],
                media_sha256="a" * 64,
                now=2000,
            )
    assert len(calls) == 1 and box.active() == []
    with box.connect() as con:
        assert con.execute("SELECT done FROM attempts").fetchone() == (0,)


@pytest.mark.parametrize("mode", [0o600, 0o640])
def test_private_worker_grant_selected_permissions_accepted(tmp_path, mode):
    path = tmp_path / "grant"
    path.write_text("eikon_pub_worker_synthetic-test-token")
    path.chmod(mode)
    assert read_private_worker_grant(path) == "eikon_pub_worker_synthetic-test-token"


def test_cli_failure_is_safe_and_leaves_original_attempt_quarantined(
    original_box, tmp_path, monkeypatch, capsys
):
    import sys

    from publisher_worker import pre_dispatch

    box, claim, _ = original_box
    token = tmp_path / "grant"
    token.write_text("eikon_pub_worker_synthetic-test-token")
    token.chmod(0o600)
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(503, text="synthetic-private-error-body")

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        monkeypatch.setattr(
            pre_dispatch, "WorkerClient", lambda *a, **k: WorkerClient(*a, **k, http=http)
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "pre_dispatch",
                "attest",
                "--outbox",
                str(box.path),
                "--tenant-id",
                "17",
                "--attempt-id",
                claim["attempt_id"],
                "--contract-hash",
                claim["contract_hash"],
                "--media-sha256",
                "a" * 64,
                "--token-file",
                str(token),
                "--origin",
                "https://example.test",
            ],
        )
        assert pre_dispatch.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {"state": "held", "reason": "pre_dispatch_operation_failed"}
    assert not output.err and "synthetic" not in output.out
    assert (
        len(calls) == 1
        and calls[0][0] == "POST"
        and calls[0][1].endswith("/pre-dispatch-attestations")
    )
    assert box.active() == []
