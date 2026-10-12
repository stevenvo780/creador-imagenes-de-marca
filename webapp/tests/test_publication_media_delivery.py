"""Capacidad efímera exacta, nunca URL de galería ni credencial de red."""

import hashlib
import json

import pytest

from webapp import db
from webapp.publications.contracts import PublicationError
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_case as _campaign_case,
)
from webapp.tests.test_publication_delivery_concurrency import (
    campaign_clients as _campaign_clients,
)
from webapp.tests.test_publication_delivery_concurrency import (
    delivery_case as _delivery_case,
)
from webapp.tests.test_publication_delivery_concurrency import (
    isolated_db as _isolated_db,
)
from webapp.tests.test_publication_delivery_concurrency import (
    prepared,
)

campaign_case = _campaign_case
campaign_clients = _campaign_clients
isolated_db = _isolated_db
delivery_case = _delivery_case


def ticket_case(c):
    from webapp.publications.deliveries import start_attempt
    from webapp.publications.media_delivery import issue_media_ticket

    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    ticket = issue_media_ticket(
        c["url"], c["worker"], claim["attempt_id"], c["now"], ttl_seconds=120
    )
    return claim, ticket


def test_exact_ticket_is_hash_only_expiring_and_revocable(delivery_case):
    from webapp.publications.media_delivery import fetch_media_ticket, revoke_media_ticket

    c = delivery_case
    claim, ticket = ticket_case(c)
    content, mime = fetch_media_ticket(c["url"], c["app"].state.storage, ticket["ticket"], c["now"])
    assert hashlib.sha256(content).hexdigest() == c["revision"]["snapshot"]["media"]["sha256"]
    assert mime == "image/png"
    with db.connect(c["url"]) as con:
        row = con.execute(
            "SELECT * FROM publication_media_tickets WHERE tenant_id=?", (c["a"]["tenant"],)
        ).fetchone()
        assert ticket["ticket"] not in json.dumps(row)
        assert row["ticket_hash"] == hashlib.sha256(ticket["ticket"].encode()).hexdigest()
    with pytest.raises(PublicationError):
        fetch_media_ticket(c["url"], c["app"].state.storage, ticket["ticket"], ticket["expires_at"])
    revoke_media_ticket(c["url"], c["worker"], claim["attempt_id"], ticket["id"], c["now"])
    with pytest.raises(PublicationError):
        fetch_media_ticket(c["url"], c["app"].state.storage, ticket["ticket"], c["now"])


@pytest.mark.parametrize(
    "change", ["wrong_attempt", "wrong_tenant", "hash_change", "oversize", "revoke_grant"]
)
def test_ticket_wrong_binding_or_changed_original_fails_closed(delivery_case, change):
    from webapp.publications.auth import revoke_grant
    from webapp.publications.media_delivery import fetch_media_ticket, issue_media_ticket

    c = delivery_case
    claim, ticket = ticket_case(c)
    if change in ("hash_change", "oversize"):
        with db.connect(c["url"]) as con:
            row = con.execute(
                "SELECT original_key FROM media_assets WHERE tenant_id=? AND id=?",
                (c["a"]["tenant"], c["a"]["media"]["id"]),
            ).fetchone()
        c["app"].state.storage.save(
            c["a"]["tenant"],
            row["original_key"],
            b"changed" if change == "hash_change" else b"x" * (21 * 1024 * 1024),
        )
    elif change == "revoke_grant":
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
    else:
        principal = (
            c["worker"]
            if change == "wrong_attempt"
            else c["worker"] | {"tenant_id": c["b"]["tenant"]}
        )
        with pytest.raises(PublicationError):
            issue_media_ticket(
                c["url"],
                principal,
                "attempt:wrong" if change == "wrong_attempt" else claim["attempt_id"],
                c["now"],
            )
        return
    with pytest.raises(PublicationError):
        fetch_media_ticket(c["url"], c["app"].state.storage, ticket["ticket"], c["now"])


def test_processing_ticket_survives_lease_window_and_uncertain_but_has_absolute_horizon(
    delivery_case,
):
    from webapp.publications.deliveries import reconcile_attempt, report_attempt, start_attempt
    from webapp.publications.media_delivery import fetch_media_ticket, issue_media_ticket
    from webapp.tests.test_publication_delivery_concurrency import confirmation, result

    c = delivery_case
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    ticket = issue_media_ticket(c["url"], c["worker"], claim["attempt_id"], c["now"])
    assert ticket["expires_at"] == c["now"] + 3900
    report_attempt(
        c["url"], c["worker"], claim["attempt_id"], "processing", result("uncertain"), c["now"] + 10
    )
    content, _ = fetch_media_ticket(
        c["url"], c["app"].state.storage, ticket["ticket"], c["now"] + 3601
    )
    assert content
    renewed = issue_media_ticket(c["url"], c["worker"], claim["attempt_id"], c["now"] + 3601)
    assert renewed["expires_at"] == ticket["expires_at"]
    with pytest.raises(PublicationError):
        fetch_media_ticket(c["url"], c["app"].state.storage, ticket["ticket"], c["now"] + 3900)
    with pytest.raises(PublicationError):
        issue_media_ticket(c["url"], c["worker"], claim["attempt_id"], c["now"] + 3900)
    reconcile_attempt(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        claim["attempt_id"],
        "terminal",
        result(),
        confirmation(claim),
        c["now"] + 3700,
    )
    with pytest.raises(PublicationError):
        fetch_media_ticket(c["url"], c["app"].state.storage, renewed["ticket"], c["now"] + 3701)


def test_capability_api_https_exact_stream_no_range_and_access_log_redaction(
    delivery_case, monkeypatch
):
    import logging

    from fastapi.testclient import TestClient

    from webapp.api.publication_worker import CapabilityAccessFilter

    c = delivery_case
    claim, _ = ticket_case(c)
    monkeypatch.setenv("EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED", "1")
    monkeypatch.setenv("EIKON_PUBLICATION_MEDIA_ORIGIN", "https://public.example.test")
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    with TestClient(c["app"], base_url="https://testserver") as client:
        h = {"Authorization": "Bearer " + c["worker_token"]}
        ticket = client.post(
            "/api/v1/publications/worker/attempts/" + claim["attempt_id"] + "/media-ticket",
            headers=h,
            json={},
        ).json()
        assert ticket["url"].startswith("https://public.example.test/")
        from urllib.parse import urlsplit

        path = urlsplit(ticket["url"]).path
        token = path.rsplit("/", 1)[-1]
        r = client.get(path)
        assert r.status_code == 200 and len(r.content) == int(r.headers["content-length"])
        assert hashlib.sha256(r.content).hexdigest() == ticket["media_sha256"]
        assert r.headers["cache-control"] == "private, no-store"
        assert client.get(path, headers={"Range": "bytes=0-9"}).status_code == 416
        assert client.head(path).status_code == 405
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            "",
            0,
            '%s - "%s %s HTTP/%s" %d',
            ("addr", "GET", path, "1.1", 200),
            None,
        )
        CapabilityAccessFilter().filter(record)
        assert token not in record.getMessage()
    with TestClient(c["app"], base_url="http://testserver") as client:
        assert client.get(path).status_code == 403


def test_original_and_worker_requests_require_https(delivery_case):
    from fastapi.testclient import TestClient

    c = delivery_case
    claim = prepared(c)
    with TestClient(c["app"], base_url="http://testserver") as client:
        r = client.get(
            "/api/v1/publications/worker/claims/" + claim["claim_id"] + "/original",
            headers={"Authorization": "Bearer " + c["worker_token"]},
        )
        assert r.status_code == 403


def test_gcs_reader_requests_bounded_exact_range_without_public_url():
    from webapp.publications.media_delivery import read_original
    from webapp.storage_backend.gcs import GCSStorage

    content = b"private original bytes"
    frozen = {
        "kind": "gallery_image",
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    row = frozen | {"original_key": "media/real.png"}
    calls = []

    class Blob:
        def download_as_bytes(self, **kwargs):
            calls.append(kwargs)
            return content

    class Bucket:
        def blob(self, name):
            assert name == "tenants/17/media/real.png"
            return Blob()

    storage = GCSStorage.__new__(GCSStorage)
    storage.bucket_name = "test-private"
    storage._bucket = Bucket()
    assert read_original(storage, 17, frozen, row) == content
    assert calls == [{"start": 0, "end": len(content), "timeout": 20}]


def test_ticket_advertises_no_lifetime_beyond_bound_grant(delivery_case):
    from webapp.publications.auth import issue_grant, resolve_grant
    from webapp.publications.deliveries import start_attempt
    from webapp.publications.media_delivery import issue_media_ticket

    c = delivery_case
    token, _ = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "short-worker", 1, c["now"] + 60
    )
    c["worker"] = resolve_grant(c["url"], token, "worker", c["now"])
    claim = prepared(c)
    start_attempt(c["url"], c["worker"], claim["claim_id"], claim["contract_hash"], c["now"])
    assert (
        issue_media_ticket(c["url"], c["worker"], claim["attempt_id"], c["now"])["expires_at"]
        == c["now"] + 60
    )
