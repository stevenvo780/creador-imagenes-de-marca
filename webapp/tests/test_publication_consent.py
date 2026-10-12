"""Consentimiento TikTok ligado a contenido, pruebas privadas y autoridad vigente."""

from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case,
    campaign_clients,
    delivery_case,
    isolated_db,
)

__all__ = ["campaign_case", "campaign_clients", "delivery_case", "isolated_db"]


def test_consent_requires_exact_tiktok_revision_and_owner(delivery_case):
    c = delivery_case
    path = f"/api/v1/publications/revisions/{c['revision']['id']}/consent"
    r = c["a"]["client"].get(path)
    assert r.status_code == 409
    assert r.json()["detail"] == "tiktok_revision_required"
    assert c["b"]["client"].get(path).status_code == 404


import base64
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from webapp import db
from webapp.publications import consent, deliveries
from webapp.publications.auth import issue_grant, resolve_grant
from webapp.publications.campaigns import create_campaign, freeze_revision
from webapp.publications.connections import put_connection
from webapp.publications.decisions import append_ai_decision
from webapp.publications.oauth import OAuthConfig, import_credential
from webapp.publications.policies import set_policy
from webapp.tests.test_publication_decisions import evaluated
from webapp.tests.test_publication_delivery_concurrency import history
from webapp.tests.test_publication_oauth import ProviderDouble
from webapp.tests.test_publication_policies import policy_payload


class TikTokDouble(ProviderDouble):
    def verify(self, flow, secrets, now):
        from dataclasses import replace

        return replace(super().verify(flow, secrets, now), evidence_hosts=("open.tiktokapis.com",))


class CreatorDouble:
    def _request(self, method, url, *, token):
        assert (
            method == "POST"
            and url == "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
        )
        assert token == "fake-token"
        return {
            "error": {"code": "ok"},
            "data": {
                "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"],
                "comment_disabled": True,
                "duet_disabled": False,
                "stitch_disabled": True,
                "private_secret": "never-public",
            },
        }


@pytest.fixture
def tiktok_case(campaign_case):
    url, (a, b), app = campaign_case
    now = int(time.time())
    account = put_connection(
        url,
        a["tenant"],
        a["owner"],
        {
            "platform": "tiktok",
            "api_mode": "oauth2",
            "remote_id": "creator-42",
            "project_ids": [a["project"]["id"]],
        },
    )
    account = import_credential(
        url,
        a["tenant"],
        a["owner"],
        account["id"],
        {"access_token": "fake-token"},
        now,
        TikTokDouble(
            remote_id="creator-42",
            scopes=["user.info.basic", "video.publish"],
            expires_at=now + 7200,
        ),
        key=b"k" * 32,
        key_id="test",
        dry_run=False,
    )
    a = dict(a, connection=account)
    set_policy(
        url,
        a["tenant"],
        a["owner"],
        1,
        policy_payload(a["project"]["id"], a["brand"]["id"], account["id"]),
    )
    campaign = create_campaign(
        url, a["tenant"], a["owner"], a["project"]["id"], a["brand"]["id"], "TikTok exacto"
    )
    args = dict(
        media_id=a["media"]["id"],
        caption="Pieza exacta",
        connection_id=account["id"],
        scheduled_at=datetime.fromtimestamp(now, UTC).isoformat(),
        policy_version=2,
        channel_metadata={
            "sources": ["https://example.test/manual"],
            "rights": "owned",
            "context": "Lanzamiento documentado",
            "privacy": "SELF_ONLY",
            "disable_comment": True,
            "disable_duet": False,
            "disable_stitch": True,
            "is_aigc": True,
            "commercial_content": False,
            "branded_content": False,
        },
    )
    revision = freeze_revision(url, a["tenant"], campaign["id"], **args)
    token, grant = issue_grant(url, a["tenant"], a["owner"], "reviewer", "own-codex", 2, now + 7200)
    wt, _wg = issue_grant(url, a["tenant"], a["owner"], "worker", "server2", 2, now + 7200)
    now = int(time.time())
    c = dict(
        url=url,
        a=a,
        b=b,
        app=app,
        now=now,
        revision=revision,
        campaign=campaign,
        args=args,
        token=token,
        grant=grant,
        principal=resolve_grant(url, token, "reviewer", now),
        worker_token=wt,
        worker=resolve_grant(url, wt, "worker", now),
    )
    from dataclasses import replace

    app.state.settings = replace(
        app.state.settings, publication_vault_key=base64.b64encode(b"k" * 32).decode()
    )
    app.state.publication_oauth_configs = {
        ("tiktok", "oauth2"): OAuthConfig(
            platform="tiktok",
            api_mode="oauth2",
            client_id="fake",
            client_secret="fake",
            redirect_uris=("https://testserver/api/v1/publications/oauth/callback",),
        )
    }
    app.state.publication_oauth_clients = {("tiktok", "oauth2"): CreatorDouble()}
    c["proof"] = {
        "proof_key": "proof:one",
        "contract_hash": revision["contract_hash"],
        "media_sha256": a["media"]["sha256"],
        "normalized_destination": "tiktok:creator-42",
        "connection_version": account["version"],
        "expires_at": now + 1800,
        "verified_domain_prefix": "https://own.example/api/v1/publications/delivery-media/",
        "domain_proof_ref": "domain:one",
        "domain_proof_sha256": "d" * 64,
        "provider_review_ref": "review:one",
        "provider_review_sha256": "e" * 64,
        "content_eligibility_ref": "content:one",
        "content_eligibility_sha256": "f" * 64,
        "public_audit_ref": None,
        "public_audit_sha256": None,
        "provenance_ref": "operator:checked",
    }
    return c


def make_consent(c):
    a = c["a"]
    rid = c["revision"]["id"]
    base = f"/api/v1/publications/revisions/{rid}"
    c["proof_id"] = consent.import_provider_proof(
        c["url"], a["tenant"], a["owner"], rid, c["proof"], c["now"]
    )
    creator = a["client"].post(
        base + "/creator-info", json={"contract_hash": c["revision"]["contract_hash"]}
    )
    assert creator.status_code == 200, creator.text
    assert "never-public" not in creator.text
    body = {
        "contract_hash": c["revision"]["contract_hash"],
        "creator_id": creator.json()["creator_id"],
        "privacy_level": "SELF_ONLY",
        "disable_comment": True,
        "disable_duet": False,
        "disable_stitch": True,
        "brand_content_toggle": False,
        "brand_organic_toggle": False,
        "is_aigc": True,
        "music_acknowledged": True,
        "consent_confirmed": True,
    }
    response = a["client"].post(base + "/consent", json=body)
    assert response.status_code == 201, response.text
    c["receipt_id"] = response.json()["receipt_id"]
    c["consent_body"] = body
    return response.json()["consent"]


def prepare_tiktok(c):
    make_consent(c)
    append_ai_decision(c["url"], c["principal"], evaluated(c) | {"policy_version": 2}, c["now"])
    history(
        c,
        [
            {
                "source_delivery_id": "legacy-tiktok",
                "platform": "tiktok",
                "normalized_destination": "tiktok:creator-42",
                "image_sha256": "a" * 64,
                "state": "published",
                "receipt": {"remote_id": "old"},
                "original": {"completed_at": "2020-01-01T10:00:00Z"},
            }
        ],
    )
    d = deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])
    assert d["state"] == "scheduled", d
    claim = deliveries.claim_due(c["url"], c["worker"], c["now"])
    assert claim
    deliveries.claim_original(
        c["url"], c["app"].state.storage, c["worker"], claim["claim_id"], c["now"]
    )
    return claim


def test_exact_consent_http_worker_matches_reviewed_dto_and_starts(tiktok_case):
    from publisher_worker.adapters.tiktok import PostConsent

    c = tiktok_case
    claim = prepare_tiktok(c)
    with TestClient(c["app"], base_url="https://testserver") as worker:
        headers = {"Authorization": "Bearer " + c["worker_token"]}
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}"
        response = worker.get(path + "/post-consent", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["privacy_level"] == "SELF_ONLY" and result["public_audit_ref"] is None
        assert PostConsent.from_server(
            result,
            tenant_id=c["a"]["tenant"],
            revision_id=c["revision"]["id"],
            contract_hash=c["revision"]["contract_hash"],
            destination="tiktok:creator-42",
            media_sha256=c["a"]["media"]["sha256"],
            now=c["now"],
        )
        started = worker.post(
            path + "/start", headers=headers, json={"contract_hash": claim["contract_hash"]}
        )
        assert started.status_code == 200 and started.json()["post_permitted"] is True, started.text
        assert (
            worker.post(
                path + "/start", headers=headers, json={"contract_hash": claim["contract_hash"]}
            ).status_code
            == 409
        )


@pytest.mark.parametrize(
    "mutation",
    ["revoke", "proof_revoke", "expiry", "owner", "hash", "connection", "media", "new_revision"],
)
def test_get_consent_cannot_authorize_start_after_authority_changes(
    tiktok_case, mutation, monkeypatch
):
    c = tiktok_case
    claim = prepare_tiktok(c)
    a = c["a"]
    with TestClient(c["app"], base_url="https://testserver") as worker:
        headers = {"Authorization": "Bearer " + c["worker_token"]}
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}"
        assert worker.get(path + "/post-consent", headers=headers).status_code == 200
        if mutation == "revoke":
            assert (
                a["client"].delete(f"/api/v1/publications/consents/{c['receipt_id']}").status_code
                == 204
            )
        elif mutation == "proof_revoke":
            consent.revoke(c["url"], a["tenant"], a["owner"], "proof", c["proof_id"])
        elif mutation == "expiry":
            monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"] + 301)
        elif mutation == "owner":
            with db.connect(c["url"]) as con:
                con.execute(
                    "UPDATE users SET role='member' WHERE tenant_id=? AND id=?",
                    (a["tenant"], a["owner"]),
                )
        elif mutation == "connection":
            with db.connect(c["url"]) as con:
                con.execute(
                    "UPDATE publication_connections SET version=version+1 WHERE tenant_id=? AND id=?",
                    (a["tenant"], a["connection"]["id"]),
                )
        elif mutation == "media":
            with db.connect(c["url"]) as con:
                con.execute(
                    "UPDATE media_assets SET status='rejected' WHERE tenant_id=? AND id=?",
                    (a["tenant"], a["media"]["id"]),
                )
        elif mutation == "new_revision":
            new = freeze_revision(
                c["url"],
                a["tenant"],
                c["campaign"]["id"],
                **(c["args"] | {"caption": "Otra pieza"}),
            )
            assert (
                a["client"]
                .get(f"/api/v1/publications/revisions/{new['id']}/consent")
                .json()["consent"]
                is None
            )
        response = worker.post(
            path + "/start",
            headers=headers,
            json={"contract_hash": "0" * 64 if mutation == "hash" else claim["contract_hash"]},
        )
        assert response.status_code in (403, 409), response.text
        with db.connect(c["url"]) as con:
            assert (
                con.execute(
                    "SELECT started_at FROM publication_deliveries WHERE tenant_id=? AND id=?",
                    (a["tenant"], claim["delivery_id"]),
                ).fetchone()["started_at"]
                is None
            )


def test_missing_proof_planner_flags_foreign_and_privacy_mismatch_hold(tiktok_case):
    c = tiktok_case
    a = c["a"]
    rid = c["revision"]["id"]
    base = f"/api/v1/publications/revisions/{rid}"
    assert a["client"].get(base + "/consent").json()["consent"] is None
    assert c["b"]["client"].get(base + "/consent").status_code == 404
    assert (
        c["b"]["client"]
        .post(base + "/creator-info", json={"contract_hash": c["revision"]["contract_hash"]})
        .status_code
        == 404
    )
    creator = (
        a["client"]
        .post(base + "/creator-info", json={"contract_hash": c["revision"]["contract_hash"]})
        .json()
    )
    body = {
        "contract_hash": c["revision"]["contract_hash"],
        "creator_id": creator["creator_id"],
        "privacy_level": "SELF_ONLY",
        "disable_comment": True,
        "disable_duet": False,
        "disable_stitch": True,
        "brand_content_toggle": False,
        "brand_organic_toggle": False,
        "is_aigc": True,
        "music_acknowledged": True,
        "consent_confirmed": True,
    }
    assert a["client"].post(base + "/consent", json=body).status_code == 409
    assert (
        a["client"].post(base + "/consent", json=body | {"domain_verified": True}).status_code
        == 422
    )
    make_consent(c)
    for change in (
        {"privacy_level": "PUBLIC_TO_EVERYONE"},
        {"contract_hash": "f" * 64},
        {"brand_organic_toggle": True},
    ):
        assert (
            a["client"].post(base + "/consent", json=c["consent_body"] | change).status_code == 409
        )
    assert (
        a["client"]
        .post(base + "/consent", json=c["consent_body"] | {"disable_comment": False})
        .status_code
        == 409
    )
    assert (
        c["b"]["client"].delete(f"/api/v1/publications/consents/{c['receipt_id']}").status_code
        == 404
    )


def test_private_proof_import_exact_replay_rejects_conflicts_expired_foreign(tiktok_case):
    from webapp.publications.contracts import PublicationError

    c = tiktok_case
    a = c["a"]
    args = (c["url"], a["tenant"], a["owner"], c["revision"]["id"])
    first = consent.import_provider_proof(*args, c["proof"], c["now"])
    assert consent.import_provider_proof(*args, c["proof"], c["now"]) == first
    for change in (
        {"media_sha256": "0" * 64},
        {"domain_proof_sha256": "0" * 64},
        {"expires_at": c["now"]},
        {"verified_domain_prefix": "https://bad.test/?secret=x"},
        {"public_audit_ref": "audit:fake"},
    ):
        with pytest.raises(PublicationError):
            consent.import_provider_proof(*args, c["proof"] | change, c["now"])
    with pytest.raises(PublicationError):
        consent.import_provider_proof(
            c["url"], c["b"]["tenant"], c["b"]["owner"], c["revision"]["id"], c["proof"], c["now"]
        )
    consent.revoke(c["url"], a["tenant"], a["owner"], "proof", first)
    with pytest.raises(PublicationError):
        consent.import_provider_proof(*args, c["proof"], c["now"])


def test_revoke_and_start_serialize_under_same_tenant_lock(tiktok_case):
    c = tiktok_case
    claim = prepare_tiktok(c)
    with TestClient(c["app"], base_url="https://testserver") as client:
        pinned = client.get(
            f"/api/v1/publications/worker/claims/{claim['claim_id']}/post-consent",
            headers={"Authorization": "Bearer " + c["worker_token"]},
        )
        assert pinned.status_code == 200 and pinned.json()
    barrier = Barrier(2)

    def call(start):
        with TestClient(c["app"], base_url="https://testserver") as client:
            barrier.wait()
            if start:
                return client.post(
                    f"/api/v1/publications/worker/claims/{claim['claim_id']}/start",
                    headers={"Authorization": "Bearer " + c["worker_token"]},
                    json={"contract_hash": claim["contract_hash"]},
                ).status_code
            client.cookies.update(c["a"]["client"].cookies)
            return client.delete(f"/api/v1/publications/consents/{c['receipt_id']}").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, [False, True]))
    assert results[0] == 204 and results[1] in (200, 409)
    # Después de la revocación completada nunca aparece otro permiso de inicio.
    with TestClient(c["app"], base_url="https://testserver") as client:
        assert (
            client.post(
                f"/api/v1/publications/worker/claims/{claim['claim_id']}/start",
                headers={"Authorization": "Bearer " + c["worker_token"]},
                json={"contract_hash": claim["contract_hash"]},
            ).status_code
            == 409
        )


def test_claim_pins_exact_receipt_before_start_and_never_switches_to_new_receipt(tiktok_case):
    c = tiktok_case
    claim = prepare_tiktok(c)
    with TestClient(c["app"], base_url="https://testserver") as worker:
        headers = {"Authorization": "Bearer " + c["worker_token"]}
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}"
        first = worker.get(path + "/post-consent", headers=headers)
        assert first.status_code == 200
        assert worker.get(path + "/post-consent", headers=headers).json() == first.json()
        rotated = c["a"]["client"].post(
            f"/api/v1/publications/revisions/{c['revision']['id']}/consent",
            json=c["consent_body"],
        )
        assert rotated.status_code == 201
        started = worker.post(
            path + "/start", headers=headers, json={"contract_hash": claim["contract_hash"]}
        )
        assert started.status_code == 409
        reread = worker.get(path + "/post-consent", headers=headers)
        assert reread.status_code == 409 or reread.json() is None


@pytest.mark.parametrize("flag", ["disable_comment", "disable_duet", "disable_stitch", "is_aigc"])
def test_flags_require_new_revision_and_ai_http(tiktok_case, flag):
    c = tiktok_case
    make_consent(c)
    a = c["a"]
    old = c["revision"]
    base = f"/api/v1/publications/revisions/{old['id']}"
    append_ai_decision(
        c["url"], c["principal"], evaluated(c) | {"policy_version": 2}, int(time.time())
    )
    changed = not c["args"]["channel_metadata"][flag]
    assert (
        a["client"].post(base + "/consent", json=c["consent_body"] | {flag: changed}).status_code
        == 409
    )
    new = a["client"].post(
        f"/api/v1/publications/campaigns/{c['campaign']['id']}/revisions",
        json=c["args"] | {"channel_metadata": c["args"]["channel_metadata"] | {flag: changed}},
    )
    assert new.status_code == 201, new.text
    r = new.json()
    assert r["id"] != old["id"] and r["contract_hash"] != old["contract_hash"]
    overview = a["client"].get("/api/v1/publications/campaigns").json()
    revisions = overview["items"][0]["revisions"]
    assert revisions[0]["decision"] is None and revisions[1]["decision"]["outcome"] == "approve"
    assert a["client"].get(base).json()["contract_hash"] == old["contract_hash"]
    assert a["client"].get(base + "/consent").status_code == 409
    assert (
        a["client"]
        .post(f"/api/v1/publications/revisions/{r['id']}/consent", json=c["consent_body"])
        .status_code
        == 409
    )


def test_legacy_flags_missing_preserve_snapshot_and_hold(tiktok_case):
    import json

    from webapp.publications.contracts import canonical_hash, canonical_json

    c = tiktok_case
    a = c["a"]
    old = c["revision"]
    legacy = json.loads(old["frozen_json"])
    for flag in ("disable_comment", "disable_duet", "disable_stitch", "is_aigc"):
        legacy["channel_metadata"].pop(flag)
    with db.connect(c["url"]) as con:
        con.execute(
            "INSERT INTO publication_revisions(tenant_id,campaign_id,media_kind,gallery_image_id,connection_id,policy_version,scheduled_at_utc,contract_hash,frozen_json,created_at) SELECT tenant_id,campaign_id,media_kind,gallery_image_id,connection_id,policy_version,scheduled_at_utc,?,?,created_at FROM publication_revisions WHERE tenant_id=? AND id=?",
            (canonical_hash(legacy), canonical_json(legacy), a["tenant"], old["id"]),
        )
        rid = db.get_last_insert_id(c["url"], con, "publication_revisions")
    r = a["client"].get(f"/api/v1/publications/revisions/{rid}").json()
    assert r["snapshot"] == legacy and r["contract_hash"] == canonical_hash(legacy)
    assert "needs_platform_consent" in r["eligibility_reasons"]


def test_declared_imagegen_provenance_cannot_omit_aigc(tiktok_case):
    c = tiktok_case
    a = c["a"]
    c["revision"] = freeze_revision(
        c["url"],
        a["tenant"],
        c["campaign"]["id"],
        **(c["args"] | {"channel_metadata": c["args"]["channel_metadata"] | {"is_aigc": False}}),
    )
    c["proof"]["contract_hash"] = c["revision"]["contract_hash"]
    consent.import_provider_proof(
        c["url"], a["tenant"], a["owner"], c["revision"]["id"], c["proof"]
    )
    creator = (
        a["client"]
        .post(
            f"/api/v1/publications/revisions/{c['revision']['id']}/creator-info",
            json={"contract_hash": c["revision"]["contract_hash"]},
        )
        .json()
    )
    response = a["client"].post(
        f"/api/v1/publications/revisions/{c['revision']['id']}/consent",
        json={
            "contract_hash": c["revision"]["contract_hash"],
            "creator_id": creator["creator_id"],
            "privacy_level": "SELF_ONLY",
            "disable_comment": True,
            "disable_duet": False,
            "disable_stitch": True,
            "is_aigc": False,
            "brand_organic_toggle": False,
            "brand_content_toggle": False,
            "music_acknowledged": True,
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 409 and response.json()["detail"] == "aigc_disclosure_required"


def test_concurrent_get_pins_once_and_wrong_grant_cannot_read(tiktok_case):
    c = tiktok_case
    claim = prepare_tiktok(c)
    barrier = Barrier(2)

    def get(_):
        with TestClient(c["app"], base_url="https://testserver") as client:
            barrier.wait()
            return client.get(
                f"/api/v1/publications/worker/claims/{claim['claim_id']}/post-consent",
                headers={"Authorization": "Bearer " + c["worker_token"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(get, [0, 1]))
    assert all(r.status_code == 200 and r.json() for r in responses)
    assert responses[0].json() == responses[1].json()
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) n FROM publication_claim_consents WHERE tenant_id=? AND claim_id=?",
                (c["a"]["tenant"], claim["claim_id"]),
            ).fetchone()["n"]
            == 1
        )
    with TestClient(c["app"], base_url="https://testserver") as client:
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}/post-consent"
        assert (
            client.get(path, headers={"Authorization": "Bearer " + c["token"]}).status_code == 403
        )
        assert c["a"]["client"].get(path).status_code == 403


def test_claim_start_requires_prior_receipt_read(tiktok_case):
    c = tiktok_case
    claim = prepare_tiktok(c)
    with TestClient(c["app"], base_url="https://testserver") as client:
        response = client.post(
            f"/api/v1/publications/worker/claims/{claim['claim_id']}/start",
            headers={"Authorization": "Bearer " + c["worker_token"]},
            json={"contract_hash": claim["contract_hash"]},
        )
        assert response.status_code == 409


def test_creator_read_rechecks_binding_after_network_and_never_persists_stale(tiktok_case):
    c = tiktok_case
    a = c["a"]

    class ChangedCreator(CreatorDouble):
        def _request(self, *args, **kwargs):
            with db.connect(c["url"]) as con:
                con.execute(
                    "UPDATE publication_connections SET version=version+1 WHERE tenant_id=? AND id=?",
                    (a["tenant"], a["connection"]["id"]),
                )
            return super()._request(*args, **kwargs)

    c["app"].state.publication_oauth_clients[("tiktok", "oauth2")] = ChangedCreator()
    response = a["client"].post(
        f"/api/v1/publications/revisions/{c['revision']['id']}/creator-info",
        json={"contract_hash": c["revision"]["contract_hash"]},
    )
    assert response.status_code == 409
    with db.connect(c["url"]) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) n FROM publication_creator_receipts WHERE tenant_id=?",
                (a["tenant"],),
            ).fetchone()["n"]
            == 0
        )


def test_proof_expiry_before_lease_and_public_audit_are_real_holds(tiktok_case, monkeypatch):
    c = tiktok_case
    c["proof"]["expires_at"] = c["now"] + 20
    claim = prepare_tiktok(c)
    with TestClient(c["app"], base_url="https://testserver") as worker:
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}"
        headers = {"Authorization": "Bearer " + c["worker_token"]}
        assert worker.get(path + "/post-consent", headers=headers).json()
        monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"] + 21)
        assert worker.get(path + "/post-consent", headers=headers).json() is None
        assert (
            worker.post(
                path + "/start", headers=headers, json={"contract_hash": claim["contract_hash"]}
            ).status_code
            == 409
        )


def test_public_privacy_without_audit_is_not_authorized(tiktok_case):
    c = tiktok_case
    a = c["a"]
    c["args"]["channel_metadata"]["privacy"] = "PUBLIC_TO_EVERYONE"
    c["revision"] = freeze_revision(c["url"], a["tenant"], c["campaign"]["id"], **c["args"])
    c["proof"]["contract_hash"] = c["revision"]["contract_hash"]
    consent.import_provider_proof(
        c["url"], a["tenant"], a["owner"], c["revision"]["id"], c["proof"]
    )
    creator = (
        a["client"]
        .post(
            f"/api/v1/publications/revisions/{c['revision']['id']}/creator-info",
            json={"contract_hash": c["revision"]["contract_hash"]},
        )
        .json()
    )
    result = a["client"].post(
        f"/api/v1/publications/revisions/{c['revision']['id']}/consent",
        json={
            "contract_hash": c["revision"]["contract_hash"],
            "creator_id": creator["creator_id"],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_comment": True,
            "disable_duet": False,
            "disable_stitch": True,
            "is_aigc": True,
            "brand_organic_toggle": False,
            "brand_content_toggle": False,
            "music_acknowledged": True,
            "consent_confirmed": True,
        },
    )
    assert result.status_code == 409 and result.json()["detail"] == "needs_platform_audit"


def test_scheduled_consent_outlives_creator_freshness_but_stale_preflight_cannot_reconsent(
    tiktok_case, monkeypatch
):
    c = tiktok_case
    c["args"]["scheduled_at"] = datetime.fromtimestamp(c["now"] + 600, UTC).isoformat()
    c["revision"] = freeze_revision(c["url"], c["a"]["tenant"], c["campaign"]["id"], **c["args"])
    c["proof"]["contract_hash"] = c["revision"]["contract_hash"]
    issued = make_consent(c)
    append_ai_decision(c["url"], c["principal"], evaluated(c) | {"policy_version": 2}, c["now"])
    history(
        c,
        [
            {
                "source_delivery_id": "legacy-tiktok",
                "platform": "tiktok",
                "normalized_destination": "tiktok:creator-42",
                "image_sha256": "a" * 64,
                "state": "published",
                "receipt": {"remote_id": "old"},
                "original": {"completed_at": "2020-01-01T10:00:00Z"},
            }
        ],
    )
    assert (
        deliveries.schedule_revision(c["url"], c["a"]["tenant"], c["revision"]["id"], c["now"])[
            "state"
        ]
        == "scheduled"
    )
    later = c["now"] + 601
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: later)
    stale = c["a"]["client"].post(
        f"/api/v1/publications/revisions/{c['revision']['id']}/consent", json=c["consent_body"]
    )
    assert stale.status_code == 409
    claim = deliveries.claim_due(c["url"], c["worker"], later)
    assert claim, "Fresh owner consent must remain authority at the scheduled time"
    deliveries.claim_original(
        c["url"], c["app"].state.storage, c["worker"], claim["claim_id"], later
    )
    with TestClient(c["app"], base_url="https://testserver") as worker:
        headers = {"Authorization": "Bearer " + c["worker_token"]}
        path = f"/api/v1/publications/worker/claims/{claim['claim_id']}"
        got = worker.get(path + "/post-consent", headers=headers)
        assert got.status_code == 200 and got.json() == issued
        started = worker.post(
            path + "/start", headers=headers, json={"contract_hash": claim["contract_hash"]}
        )
        assert started.status_code == 200 and started.json()["post_permitted"] is True, started.text


@pytest.mark.parametrize("changed", ["privacy", "comment", "duet", "stitch"])
def test_worker_refreshes_creator_options_and_holds_incompatible_current_response(
    tmp_path, changed
):
    import io

    from PIL import Image

    from publisher_worker.adapters.tiktok import PostConsent, TikTokAdapter
    from publisher_worker.tests.test_adapters import (
        Response,
        Transport,
        account,
        journal,
        variant,
    )
    from publisher_worker.tests.test_adapters import (
        consent as worker_consent,
    )

    current = {"privacy_level_options": ["PUBLIC_TO_EVERYONE"]}
    payload = worker_consent().payload
    if changed == "privacy":
        current["privacy_level_options"] = ["SELF_ONLY"]
    else:
        current[changed + "_disabled"] = True
        payload = payload | {"disable_" + changed: False}
    transport = Transport([Response({"error": {"code": "ok"}, "data": current})])
    adapter = TikTokAdapter(transport, clock=lambda: 1000).bind(journal(tmp_path))
    item = variant()
    encoded = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(encoded, format="JPEG")
    item["content"] = encoded.getvalue()
    item["post_consent"] = PostConsent(payload)
    assert adapter.preflight(account("tiktok", "oauth2"), item, 1000) == {
        "state": "requires_post_consent"
    }
    assert len(transport.calls) == 1
    assert transport.calls[0][1].endswith("/creator_info/query/")
    assert adapter.journal.read("init") is None
