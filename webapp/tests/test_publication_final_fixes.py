"""Regresiones finales con datos sintéticos y PostgreSQL/SQLite aislados."""

import time
from contextlib import suppress
from copy import deepcopy

import pytest

from webapp import db
from webapp.publications.campaigns import get_revision
from webapp.publications.contracts import Conflict, InvalidInput, NotFound, canonical_hash
from webapp.publications.decisions import publication_eligibility
from webapp.publications.deliveries import claim_due, get_claim, schedule_revision, start_attempt
from webapp.tests.test_publication_campaigns import campaign, freeze
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case,
    campaign_clients,
    delivery_case,
    isolated_db,
    parallel,
    prepared,
    scheduled,
)
from webapp.tests.test_publication_history import evidence, item, publication_db

__all__ = ["campaign_case", "campaign_clients", "delivery_case", "isolated_db", "publication_db"]


def edit(c, **changes):
    a = c["revision"]
    return freeze(
        c["url"],
        c["a"],
        {"id": a["campaign_id"]},
        supersedes_revision_id=a["id"],
        supersedes_contract_hash=a["contract_hash"],
        caption="Corrección",
        **changes,
    )


@pytest.mark.parametrize("reserved", [False, True])
def test_edit_invalidates_exact_predecessor_before_start(delivery_case, reserved):
    c = delivery_case
    claim = prepared(c) if reserved else None
    if not reserved:
        scheduled(c)
    a = c["revision"]
    independent = freeze(c["url"], c["a"], {"id": a["campaign_id"]})
    b = edit(c)
    assert b["id"] != a["id"]
    assert get_revision(c["url"], c["a"]["tenant"], a["id"])["frozen_json"] == a["frozen_json"]
    assert (
        "revision_superseded"
        in publication_eligibility(c["url"], c["a"]["tenant"], a["id"], c["now"])["reasons"]
    )
    assert (
        "revision_superseded"
        not in get_revision(c["url"], c["a"]["tenant"], independent["id"])["eligibility_reasons"]
    )
    assert not publication_eligibility(c["url"], c["a"]["tenant"], b["id"], c["now"])["eligible"]
    retained = schedule_revision(c["url"], c["a"]["tenant"], a["id"], c["now"])
    assert retained["state"] == "held"
    assert "revision_superseded" in retained["hold_reasons"]
    assert claim_due(c["url"], c["worker"], c["now"]) is None
    if claim:
        with pytest.raises(Conflict):
            start_attempt(
                c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
            )
    from webapp.publications.inbox import _stock_projection

    with db.connect(c["url"]) as con:
        _, held, stock = _stock_projection(con, c["a"]["tenant"], [a], c["now"], [])
    assert stock == [] and "revision_superseded" in held[0]["reasons"]


def test_edit_started_preserves_readback_and_no_second_start(delivery_case):
    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    edit(c)
    status = get_claim(c["url"], c["worker"], claim["claim_id"], c["now"] + 7200)
    assert status["state"] == "attempt_started" and status["post_permitted"] is False
    assert claim_due(c["url"], c["worker"], c["now"] + 7200) is None
    with pytest.raises(Conflict, match="attempt_already_started"):
        start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    from webapp.publications.deliveries import reconcile_attempt, reconciliation_credential
    from webapp.publications.ledger import seen_media
    from webapp.tests.test_publication_delivery_concurrency import confirmation, result

    recovered = reconciliation_credential(
        c["url"], c["worker"], claim["attempt_id"], c["now"] + 7200, key=b"k" * 32
    )
    assert recovered["purpose"] == "reconcile_only" and recovered["post_permitted"] is False
    reconciled = reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "lookup",
        result(),
        confirmation(claim),
        c["now"] + 7200,
    )
    assert reconciled["state"] == "published"
    assert claim_due(c["url"], c["worker"], c["now"] + 7200) is None
    assert seen_media(
        c["url"],
        c["a"]["tenant"],
        c["revision"]["snapshot"]["destination"],
        c["revision"]["snapshot"]["media"]["sha256"],
    )


def test_edit_concurrency_and_bindings(delivery_case):
    c = delivery_case
    results = parallel(lambda: edit(c))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert "revision_superseded" in results
    a = c["revision"]
    with pytest.raises(Conflict, match="revision_campaign_mismatch"):
        freeze(
            c["url"],
            c["a"],
            campaign(c["url"], c["a"]),
            supersedes_revision_id=a["id"],
            supersedes_contract_hash=a["contract_hash"],
        )
    with pytest.raises(NotFound):
        freeze(
            c["url"],
            c["b"],
            campaign(c["url"], c["b"]),
            supersedes_revision_id=a["id"],
            supersedes_contract_hash=a["contract_hash"],
        )
    with pytest.raises(Conflict, match="contract_changed"):
        freeze(
            c["url"],
            c["a"],
            {"id": a["campaign_id"]},
            supersedes_revision_id=a["id"],
            supersedes_contract_hash="f" * 64,
        )


def test_campaign_100_total_revisions_concurrent_limit(campaign_case):
    url, (a, _), _app = campaign_case
    group = campaign(url, a)
    first = freeze(url, a, group)
    head = freeze(
        url,
        a,
        group,
        supersedes_revision_id=first["id"],
        supersedes_contract_hash=first["contract_hash"],
    )
    for _ in range(97):
        freeze(url, a, group)
    results = parallel(lambda: freeze(url, a, group))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert "campaign_revision_limit" in results
    with pytest.raises(Conflict, match="campaign_revision_limit"):
        freeze(url, a, group)
    with pytest.raises(Conflict, match="campaign_revision_limit"):
        freeze(
            url,
            a,
            group,
            supersedes_revision_id=head["id"],
            supersedes_contract_hash=head["contract_hash"],
        )
    assert (
        "revision_superseded"
        not in get_revision(url, a["tenant"], head["id"])["eligibility_reasons"]
    )
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_revision_supersessions WHERE tenant_id=?",
                (a["tenant"],),
            ).fetchone()["n"]
            == 1
        )
    from webapp.publications.views import campaigns

    rows = campaigns(url, a["tenant"], a["owner"])["items"]
    assert len(rows[0]["revisions"]) == 100
    assert freeze(url, a, campaign(url, a))["id"]


def empty_evidence(tenant, destination="facebook:7"):
    proof = evidence({"inventory": []})
    receipt = dict(
        tenant_id=tenant,
        normalized_destination=destination,
        observed_at=int(time.time()) - 60,
        provenance="operator:inventory-audit",
        coverage=[{"source_id": "inventory", "source_sha256": "b" * 64}],
        item_count=0,
    )
    proof["empty_inventory_receipts"] = [receipt]
    proof["cut_manifest"]["empty_inventories"] = [
        {"evidence": receipt, "evidence_sha256": canonical_hash(receipt)}
    ]
    return proof


def test_empty_inventory_explicit_scoped_idempotent_and_new_history_holds(publication_db):
    from webapp.publications.ledger import history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    proof = empty_evidence(tenant)
    result = import_history(url, tenant, "inventory", [], proof)
    assert import_history(url, tenant, "inventory", [], proof) == result
    assert history_ready(url, tenant, "facebook:7")
    assert not history_ready(url, tenant, "facebook:alias")
    assert not history_ready(url, tenant, "facebook:8")
    assert not history_ready(url, owners[1][0], "facebook:7")
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_media_guards").fetchall() == []
    other = item(destination="facebook:8")
    import_history(url, tenant, "other", [other], evidence({"other": [other]}, "other-cut"))
    assert history_ready(url, tenant, "facebook:7") and history_ready(url, tenant, "facebook:8")
    import_history(
        url, tenant, "late", [item()], {"source_sha256": "d" * 64, "receipt_sha256": "e" * 64}
    )
    assert not history_ready(url, tenant, "facebook:7")
    with pytest.raises((Conflict, InvalidInput)):
        changed = deepcopy(proof)
        changed["cut_manifest"]["empty_inventories"][0]["evidence"]["provenance"] = "different"
        import_history(url, tenant, "inventory", [], changed)


@pytest.mark.parametrize("bad", ["absent", "hash", "tenant", "coverage", "receipt"])
def test_empty_inventory_requires_bound_evidence(publication_db, bad):
    from webapp.publications.ledger import history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    proof = empty_evidence(tenant)
    entry = proof["cut_manifest"]["empty_inventories"][0]
    if bad == "absent":
        del proof["cut_manifest"]["empty_inventories"]
    if bad == "hash":
        entry["evidence_sha256"] = "f" * 64
    if bad in ("tenant", "coverage"):
        entry["evidence"]["tenant_id" if bad == "tenant" else "coverage"] = (
            owners[1][0] if bad == "tenant" else []
        )
        entry["evidence_sha256"] = canonical_hash(entry["evidence"])
    if bad == "receipt":
        del proof["empty_inventory_receipts"]
    with suppress(InvalidInput, Conflict):
        import_history(url, tenant, "inventory", [], proof)
    assert not history_ready(url, tenant, "facebook:7")


@pytest.mark.parametrize("video", [False, True])
@pytest.mark.parametrize("negative", [None, "scope", "proof", "consent"])
def test_verified_tiktok_oauth_reaches_exact_format(publication_db, tmp_path, video, negative):
    import io
    from dataclasses import replace

    from PIL import Image

    from publisher_worker.adapters.tiktok import PostConsent, TikTokAdapter
    from publisher_worker.outbox import Outbox
    from publisher_worker.tests.test_adapters import Response, Transport, consent, variant
    from webapp.publications.connections import put_connection
    from webapp.publications.oauth import VerifiedAccount, import_credential

    url, owners, payloads = publication_db
    tenant, owner = owners[0]
    conn = put_connection(
        url,
        tenant,
        owner,
        dict(
            platform="tiktok",
            api_mode="oauth2",
            remote_id="42",
            project_ids=payloads[0]["project_ids"],
        ),
    )
    now = int(time.time())

    class Provider:
        def verify(self, flow, credential, at):
            account = VerifiedAccount(
                remote_id="42",
                name="Creator",
                scopes=("user.info.basic", "video.publish"),
                expires_at=now + 7200,
                expiry_state="known",
                evidence_hosts=("open.tiktokapis.com",),
                credential=credential,
            )
            return replace(account, scopes=("user.info.basic",)) if negative == "scope" else account

    stored = import_credential(
        url,
        tenant,
        owner,
        conn["id"],
        {"access_token": "synthetic-token"},
        now,
        Provider(),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    stored["credential"] = {"access_token": "synthetic-token"}
    item = variant("video/mp4" if video else "image/jpeg")
    item["tenant_id"] = tenant
    if video:
        # Media vídeo válido pertenece a suite de formatos; aquí se conserva su rechazo independiente.
        item["content"] = b"invalid-video"
    else:
        content = io.BytesIO()
        Image.new("RGB", (400, 400), "white").save(content, format="JPEG")
        item["content"] = content.getvalue()
    dto = consent(now).payload | {"tenant_id": tenant}
    if negative == "proof":
        dto["domain_proof_ref"] = ""
    item["post_consent"] = PostConsent.from_server(
        dto,
        tenant_id=tenant,
        revision_id=9,
        contract_hash="b" * 64,
        destination="tiktok:42",
        media_sha256="a" * 64,
        now=now,
    )
    if negative == "consent":
        item.pop("post_consent")
    transport = Transport(
        [
            Response(
                {"error": {"code": "ok"}, "data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE"]}}
            ),
            Response({"error": {"code": "ok"}, "data": {"publish_id": "v_pub_test"}}),
            Response({"error": {"code": "ok"}, "data": {"status": "PROCESSING_UPLOAD"}}),
        ]
    )
    box = Outbox(tmp_path / "outbox.db", tenant_id=tenant)
    box.reserve({"attempt_id": "a", "claim_id": "c"}, {"tenant_id": tenant})
    adapter = TikTokAdapter(transport, clock=lambda: now).bind(box.journal("a"))
    state = adapter.preflight(stored, item, now)["state"]
    if negative in ("proof", "consent"):
        assert state == "requires_post_consent" and not transport.calls
    elif negative == "scope":
        assert stored["status"] != "active" and state == "requires_auth" and not transport.calls
    elif video:
        assert stored["capabilities"]["video"] is True
        assert state == "unsupported_media" and not transport.calls
    else:
        assert state == "verified"
        result = adapter.publish(stored, item, "a")
        assert result["state"] == "uncertain"
        payload = transport.calls[1][2]["json"]
        assert payload["media_type"] == "PHOTO" and payload["post_mode"] == "DIRECT_POST"


def test_superseded_evaluation_and_migration_are_immutable(delivery_case):
    from webapp.publications.decisions import append_ai_decision
    from webapp.publications.migrations import migrate_publications
    from webapp.tests.test_publication_decisions import evaluated

    c = delivery_case
    payload = evaluated(c)
    edit(c)
    with pytest.raises(Conflict):
        append_ai_decision(c["url"], c["principal"], payload, c["now"])
    migrate_publications(c["url"])
    with db.connect(c["url"]) as con:
        rows = con.execute(
            "SELECT * FROM publication_revision_supersessions WHERE tenant_id=?",
            (c["a"]["tenant"],),
        ).fetchall()
    assert len(rows) == 1 and rows[0]["predecessor_hash"] == c["revision"]["contract_hash"]
    for command in ("DELETE FROM", "UPDATE"):
        with (
            pytest.raises(Exception, match=r"immutable_supersession|immutable_revision"),
            db.connect(c["url"]) as con,
        ):
            sql = (
                "DELETE FROM publication_revision_supersessions"
                if command == "DELETE FROM"
                else "UPDATE publication_revision_supersessions SET predecessor_hash='changed'"
            )
            con.execute(sql + " WHERE tenant_id=?", (c["a"]["tenant"],))


def test_empty_inventory_source_receipt_cannot_be_replaced(publication_db):
    from webapp.publications.ledger import import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    proof = empty_evidence(tenant)
    import_history(url, tenant, "inventory", [], proof)
    proof.pop("cut_manifest")
    proof["empty_inventory_receipts"][0]["provenance"] = "different"
    with pytest.raises(Conflict, match="history_source_conflict"):
        import_history(url, tenant, "inventory", [], proof)


def test_empty_inventory_preserves_unknown_and_unreconciled_holds(publication_db):
    from webapp.publications.ledger import append_event, history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    import_history(url, tenant, "inventory", [], empty_evidence(tenant))
    unknown = item(destination=None, platform="facebook", state="uncertain")
    imported = import_history(
        url, tenant, "new", [unknown], evidence({"new": [unknown]}, "new-cut")
    )
    assert not history_ready(url, tenant, "facebook:7")
    append_event(
        url,
        tenant,
        imported["items"][0]["attempt_id"],
        "reconciled",
        "reconciled",
        {"confirmed": True, "state": "failed", "receipt": {"lookup": "verified"}},
    )
    assert not history_ready(url, tenant, "facebook:7")


def test_edit_start_race_preserves_winning_order(delivery_case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    c = delivery_case
    claim = prepared(c)
    barrier = Barrier(2)

    def run(start):
        barrier.wait()
        if not start:
            return edit(c)
        try:
            return start_attempt(
                c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"]
            )
        except Conflict as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        started, edited = list(pool.map(run, (True, False)))
    assert edited["id"] != c["revision"]["id"]
    status = get_claim(c["url"], c["worker"], claim["claim_id"], c["now"])
    if isinstance(started, dict):
        assert started["post_permitted"] and status["state"] == "attempt_started"
    else:
        assert status["state"] == "held"
    assert status["post_permitted"] is False
    assert claim_due(c["url"], c["worker"], c["now"] + 7200) is None
