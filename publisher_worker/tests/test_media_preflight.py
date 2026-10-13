"""Gate de medios antes del intento; errores acotados sin datos sensibles."""

import base64
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from publisher_worker.client import WorkerAPIError, WorkerClient, run_once
from publisher_worker.outbox import Outbox
from publisher_worker.tests.test_dispatch import FakeAdapter
from publisher_worker.tests.test_dispatch import dispatch_case as _dispatch_case
from webapp import db
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
    scheduled,
)

READINESS = "/api/v1/publications/worker/media-delivery-readiness"
campaign_case = _campaign_case
campaign_clients = _campaign_clients
delivery_case = _delivery_case
isolated_db = _isolated_db
dispatch_case = _dispatch_case


@pytest.mark.parametrize(
    ("enabled", "origin", "reason"),
    [
        (None, None, "media_delivery_release_gate"),
        ("0", "https://media.example", "media_delivery_release_gate"),
        ("1", None, "media_delivery_origin_required"),
        ("1", "http://media.example", "media_delivery_origin_required"),
        ("1", "https://user:PRIVATE@media.example", "media_delivery_origin_required"),
        ("1", "https://media.example/path", "media_delivery_origin_required"),
        ("1", "https://media.example?PRIVATE=1", "media_delivery_origin_required"),
        ("1", "https://media.example:444", "media_delivery_origin_required"),
        ("1", "https://media.example:invalid", "media_delivery_origin_required"),
        ("1", "https://media.example:443/", None),
    ],
)
def test_readiness_canonical_read_only(delivery_case, monkeypatch, enabled, origin, reason):
    c = delivery_case
    for key, value in (
        ("EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED", enabled),
        ("EIKON_PUBLICATION_MEDIA_ORIGIN", origin),
    ):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    with db.connect(c["url"]) as con:
        before = list(con.execute("SELECT * FROM publication_deliveries").fetchall())
        tickets = con.execute("SELECT COUNT(*) AS n FROM publication_media_tickets").fetchone()["n"]
    with TestClient(c["app"], base_url="https://testserver") as http:
        response = http.get(READINESS, headers={"Authorization": "Bearer " + c["worker_token"]})
    assert response.status_code == 200
    assert response.json() == {
        "ready": reason is None,
        "hold_reason": "unknown" if reason else None,
        "reason": reason,
    }
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "PRIVATE" not in response.text and "media.example" not in response.text
    with db.connect(c["url"]) as con:
        assert list(con.execute("SELECT * FROM publication_deliveries").fetchall()) == before
        assert (
            con.execute("SELECT COUNT(*) AS n FROM publication_media_tickets").fetchone()["n"]
            == tickets
        )


def test_readiness_requires_worker_and_https(delivery_case, monkeypatch):
    from webapp.publications.auth import revoke_grant

    c = delivery_case
    monkeypatch.setenv("EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED", "1")
    monkeypatch.setenv("EIKON_PUBLICATION_MEDIA_ORIGIN", "https://media.example")
    with TestClient(c["app"], base_url="http://testserver") as http:
        response = http.get(READINESS, headers={"Authorization": "Bearer " + c["worker_token"]})
        assert response.status_code == 403
        assert response.json() == {"detail": "https_required"}
    with TestClient(c["app"], base_url="https://testserver") as http:
        assert (
            http.get(
                READINESS, headers={"Authorization": "Bearer " + c["worker_token"]}
            ).status_code
            == 200
        )
        assert http.get(READINESS).status_code in {401, 403}
        assert (
            http.get(READINESS, headers={"Authorization": "Bearer " + c["token"]}).status_code
            == 403
        )
        revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], c["worker"]["grant_id"])
        assert (
            http.get(
                READINESS, headers={"Authorization": "Bearer " + c["worker_token"]}
            ).status_code
            == 403
        )


@pytest.mark.parametrize("configuration", ["disabled", "missing_origin", "ready"])
def test_real_media_preflight_before_start(delivery_case, tmp_path, monkeypatch, configuration):
    c = delivery_case
    scheduled(c)
    c["app"].state.settings = replace(
        c["app"].state.settings, publication_vault_key=base64.b64encode(b"k" * 32).decode()
    )
    monkeypatch.setattr("webapp.api.publication_worker.time.time", lambda: c["now"])
    monkeypatch.setenv(
        "EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED", "1" if configuration != "disabled" else "0"
    )
    if configuration == "missing_origin":
        monkeypatch.delenv("EIKON_PUBLICATION_MEDIA_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("EIKON_PUBLICATION_MEDIA_ORIGIN", "https://media.example")
    with TestClient(c["app"], base_url="https://testserver") as http:
        client = WorkerClient(
            "https://testserver", c["worker_token"], tenant_id=c["a"]["tenant"], http=http
        )
        outbox = Outbox(tmp_path / "media.db", tenant_id=client.tenant_id)
        adapter = FakeAdapter()
        adapter.needs_delivery = True
        result = run_once(client, outbox, {"facebook": adapter}, c["now"])
        if configuration == "ready":
            assert result["results"][0]["state"] == "published", result
            assert adapter.post_count == 1
        else:
            expected = (
                "media_delivery_release_gate"
                if configuration == "disabled"
                else "media_delivery_origin_required"
            )
            assert result["results"] == [
                {"state": "held", "reason": expected, "hold_reason": "unknown"}
            ], result
            assert adapter.post_count == 0
            assert outbox.active() == []
            assert run_once(client, outbox, {"facebook": adapter}, c["now"])["state"] == "idle"
        with db.connect(c["url"]) as con:
            row = con.execute(
                "SELECT state,started_at FROM publication_deliveries WHERE tenant_id=?",
                (client.tenant_id,),
            ).fetchone()
            if configuration == "ready":
                assert row["state"] == "published" and row["started_at"] is not None
            else:
                assert row["state"] == "held" and row["started_at"] is None
                assert (
                    con.execute("SELECT COUNT(*) AS n FROM publication_media_tickets").fetchone()[
                        "n"
                    ]
                    == 0
                )


@pytest.mark.parametrize(
    ("failure", "code", "status"),
    [
        (409, "worker_api_http_error", 409),
        (httpx.ReadTimeout("PRIVATE"), "network_timeout", None),
        (httpx.ConnectError("PRIVATE"), "connection_error", None),
    ],
)
def test_worker_api_failure_is_bounded(failure, code, status):
    def handler(request):
        if isinstance(failure, int):
            return httpx.Response(failure, json={"detail": "PRIVATE", "access_token": "PRIVATE"})
        raise failure

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = WorkerClient("https://worker.example", "PRIVATE", tenant_id=7, http=http)
        with pytest.raises(WorkerAPIError) as raised:
            client.claim_due()
    assert raised.value.code == code
    assert raised.value.status == status
    assert "PRIVATE" not in str(raised.value) and "PRIVATE" not in repr(raised.value)


@pytest.mark.parametrize(
    "failure", [409, httpx.ReadTimeout("PRIVATE"), httpx.ConnectError("PRIVATE")]
)
def test_ticket_failure_after_start_stays_uncertain(dispatch_case, failure):
    client, outbox, adapters, now = dispatch_case
    adapter = adapters["facebook"]
    adapter.needs_delivery = True
    client.media_delivery_readiness = lambda: {"ready": True, "hold_reason": None, "reason": None}

    def handler(request):
        if isinstance(failure, int):
            return httpx.Response(failure, text="PRIVATE")
        raise failure

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        ticket_client = WorkerClient("https://worker.example", "PRIVATE", tenant_id=7, http=http)
        client.issue_ticket = ticket_client.issue_ticket
        result = run_once(client, outbox, adapters, now)["results"][0]
    assert client.start_count == 1 and adapter.post_count == 0
    assert result["state"] == "uncertain" and client.state == "uncertain"
    expected = (
        "status_unavailable"
        if isinstance(failure, int)
        else "network_timeout"
        if isinstance(failure, httpx.TimeoutException)
        else "connection_error"
    )
    assert result["evidence"]["error_code"] == expected
    if isinstance(failure, int):
        assert result["evidence"]["http_status"] == failure
    assert "PRIVATE" not in str(client.reports)
    run_once(client, outbox, adapters, now)
    assert client.start_count == 1 and adapter.post_count == 0


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            httpx.Response(409, text="PRIVATE"),
            {"state": "held", "reason": "worker_api_http_error", "http_status": 409},
        ),
        (
            httpx.Response(200, json={"ready": 1, "hold_reason": None, "reason": None}),
            {"state": "held", "reason": "status_unavailable"},
        ),
        (
            httpx.Response(200, json={"ready": True}),
            {"state": "held", "reason": "status_unavailable"},
        ),
        (
            httpx.Response(
                200, json={"ready": False, "hold_reason": "PRIVATE", "reason": "PRIVATE"}
            ),
            {"state": "held", "reason": "status_unavailable"},
        ),
        (
            httpx.Response(200, json={"ready": False, "hold_reason": "unknown", "reason": {}}),
            {"state": "held", "reason": "status_unavailable"},
        ),
        (
            httpx.Response(200, json={"ready": False, "hold_reason": "unknown", "reason": []}),
            {"state": "held", "reason": "status_unavailable"},
        ),
        (httpx.Response(200, json=[]), {"state": "held", "reason": "status_unavailable"}),
        (httpx.Response(200, text="PRIVATE"), {"state": "held", "reason": "status_unavailable"}),
    ],
)
def test_unavailable_or_invalid_readiness_never_starts(dispatch_case, response, expected):
    client, outbox, adapters, now = dispatch_case
    adapters["facebook"].needs_delivery = True
    with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as http:
        authority = WorkerClient("https://worker.example", "PRIVATE", tenant_id=7, http=http)
        client.media_delivery_readiness = authority.media_delivery_readiness
        result = run_once(client, outbox, adapters, now)
    assert result["results"] == [expected]
    assert client.start_count == 0 and adapters["facebook"].post_count == 0
    assert client.state == "held"
    assert "PRIVATE" not in str(result)
