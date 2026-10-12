"""Proceso stdio real→HTTP→dos BD aisladas; modelo sintético, nunca aceptación nativa."""

import asyncio
import base64
import json
import socket
import sys
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
from webapp.publications.decisions import publication_eligibility
from webapp.publications.deliveries import claim_due, claim_original, start_attempt
from webapp.tests.media_helpers import image_bytes
from webapp.tests.test_publication_campaigns import campaign, freeze
from webapp.tests.test_publication_decisions import (
    campaign_case,
    campaign_clients,
    decision_case,
    isolated_db,
    receipt,
    response,
)
from webapp.tests.test_publication_delivery_concurrency import history
from webapp.tests.test_publication_inbox import counts, get, today_revision

__all__ = ["campaign_case", "campaign_clients", "decision_case", "isolated_db"]
ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def http_server(app):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", access_log=False, log_level="critical")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


def params(base, planner_token, reviewer_token, lowlevel):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=ROOT,
        env={
            "EIKON_BASE_URL": base,
            "EIKON_API_KEY": "",
            "EIKON_PUBLICATION_PLANNER_TOKEN": planner_token,
            "EIKON_PUBLICATION_REVIEWER_TOKEN": reviewer_token,
            "EIKON_MCP_LOWLEVEL": "1" if lowlevel else "0",
        },
    )


def text_result(result):
    return json.loads(next(item.text for item in result.content if item.type == "text"))


@pytest.mark.parametrize("lowlevel", [False, True], ids=["fastmcp", "fallback"])
def test_stdio_daily_stock_disconnection_keeps_pending_held_and_worker_authorized(
    decision_case, tmp_path, lowlevel
):
    c = today_revision(decision_case)
    pt, _ = issue_grant(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        "planner",
        "own-planner",
        1,
        int(time.time()) + 600,
    )
    foreign = freeze(c["url"], c["b"], campaign(c["url"], c["b"]))
    history(c)
    with http_server(c["app"]) as base:

        async def exercise():
            with (tmp_path / "daily-stdio.log").open("w+") as errors:
                async with (
                    stdio_client(params(base, pt, c["token"], lowlevel), errlog=errors) as (
                        read,
                        write,
                    ),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    tools = {t.name: t for t in (await session.list_tools()).tools}
                    assert "eikon_get_publication_inbox" in tools
                    schema = (
                        getattr(tools["eikon_get_publication_inbox"], "inputSchema", None)
                        or tools["eikon_get_publication_inbox"].input_schema
                    )
                    assert schema["properties"]["stock_target"]["type"] == "integer"
                    assert schema["properties"]["stock_target"]["minimum"] == 1
                    assert schema["properties"]["stock_target"]["maximum"] == 100
                    for bad in (True, 1.5, "1", 0, 101):
                        invalid = await session.call_tool(
                            "eikon_get_publication_inbox", {"stock_target": bad}
                        )
                        assert (
                            getattr(invalid, "is_error", getattr(invalid, "isError", False))
                            or not text_result(invalid)["success"]
                        )
                    for bad in (True, 1, "bad"):
                        invalid = await session.call_tool(
                            "eikon_get_publication_inbox", {"history_cursor": bad}
                        )
                        assert (
                            getattr(invalid, "is_error", getattr(invalid, "isError", False))
                            or not text_result(invalid)["success"]
                        )
                    inbox = text_result(await session.call_tool("eikon_get_publication_inbox", {}))
                    assert (
                        inbox["success"] and inbox["inbox"]["accounts"][0]["authorized_stock"] == 0
                    )
                    assert inbox["inbox"]["accounts"][0]["deficit"] == 1
                    listing = text_result(
                        await session.call_tool("eikon_list_publication_candidates", {})
                    )
                    assert c["revision"]["id"] in [r["id"] for r in listing["candidates"]["items"]]
                    refused = text_result(
                        await session.call_tool(
                            "eikon_get_publication_candidate", {"revision_id": foreign["id"]}
                        )
                    )
                    assert not refused["success"] and refused["http_status"] == 404
                    snap = c["revision"]["snapshot"]
                    denied = text_result(
                        await session.call_tool(
                            "eikon_prepare_publication_candidate",
                            {
                                "campaign_id": snap["campaign_id"],
                                "media_id": snap["media"]["id"],
                                "caption": "Exact copy",
                                "connection_id": c["b"]["connection"]["id"],
                                "scheduled_at": "2090-01-01T00:00:00Z",
                                "policy_version": 1,
                                "channel_metadata": snap["channel_metadata"],
                            },
                        )
                    )
                    assert not denied["success"]
                    prepared = text_result(
                        await session.call_tool(
                            "eikon_prepare_publication_candidate",
                            {
                                "campaign_id": snap["campaign_id"],
                                "media_id": snap["media"]["id"],
                                "caption": snap["caption"],
                                "connection_id": c["a"]["connection"]["id"],
                                "scheduled_at": datetime.fromtimestamp(
                                    snap["scheduled_at_utc"], UTC
                                ).isoformat(),
                                "policy_version": 1,
                                "channel_metadata": snap["channel_metadata"],
                            },
                        )
                    )
                    assert prepared["success"]
                    c["revision"] = prepared["candidate"]
                    got = await session.call_tool(
                        "eikon_get_publication_candidate", {"revision_id": c["revision"]["id"]}
                    )
                    material = text_result(got)["candidate"]
                    assert (
                        base64.b64decode(next(x.data for x in got.content if x.type == "image"))
                        == image_bytes()
                    )
                    assert (
                        material["delivery"]["evidence"]["source_mode"] == "frozen_metadata_context"
                    )
                    answer = response()
                    evaluation = {
                        "revision_id": c["revision"]["id"],
                        "expected_contract_hash": c["revision"]["contract_hash"],
                        "policy_version": 1,
                        "material_hashes": material["material_hashes"],
                        "model_receipt": receipt(c, material, answer),
                        "response": answer,
                    }
                    approved = text_result(
                        await session.call_tool("eikon_submit_publication_evaluation", evaluation)
                    )
                    assert approved["success"]
                    delivery = approved["evaluation"]["delivery"]
                    assert (
                        delivery["state"] == "scheduled"
                        and delivery["revision_id"] == c["revision"]["id"]
                    )
                    repeated = text_result(
                        await session.call_tool("eikon_submit_publication_evaluation", evaluation)
                    )
                    assert (
                        repeated["evaluation"]["decision"]["id"]
                        == approved["evaluation"]["decision"]["id"]
                    )
                    assert repeated["evaluation"]["delivery"]["id"] == delivery["id"]
                    reread = text_result(
                        await session.call_tool(
                            "eikon_get_publication_candidate", {"revision_id": c["revision"]["id"]}
                        )
                    )
                    assert (
                        reread["candidate"]["eligibility"]["decision_id"]
                        == approved["evaluation"]["decision"]["id"]
                    )
                    assert (
                        reread["candidate"]["candidate"]["contract_hash"]
                        == c["revision"]["contract_hash"]
                    )
                    inbox = text_result(await session.call_tool("eikon_get_publication_inbox", {}))
                    assert inbox["inbox"]["accounts"][0]["authorized_stock"] == 1
                errors.seek(0)
                assert pt not in errors.read()
                errors.seek(0)
                assert c["token"] not in errors.read()

        asyncio.run(exercise())
    # MCP terminó. Un candidato nuevo no hereda evaluación de otro ni depende del cliente.
    pending = today_revision(c)
    before = counts(c)
    result = publication_eligibility(
        c["url"], c["a"]["tenant"], pending["revision"]["id"], int(time.time())
    )
    assert result["eligible"] is False and "ai_decision_required" in result["reasons"]
    assert counts(c) == before
    disconnected = get(c, {"Authorization": "Bearer " + pt}, stock_target=2).json()["accounts"][0]
    assert disconnected["authorized_stock"] == 1 and disconnected["deficit"] == 1
    pending_status = next(
        r
        for r in disconnected["pending_candidates"]
        if r["revision_id"] == pending["revision"]["id"]
    )
    assert pending_status["decision_id"] is None and not pending_status["eligible"]
    assert "ai_decision_required" in pending_status["reasons"]
    assert counts(c) == before
    wt, _ = issue_grant(
        c["url"], c["a"]["tenant"], c["a"]["owner"], "worker", "server2", 1, int(time.time()) + 600
    )
    now = int(time.time())
    worker = resolve_grant(c["url"], wt, "worker", now)
    claim = claim_due(c["url"], worker, now)
    assert claim and claim["contract_hash"] == c["revision"]["contract_hash"]
    content, mime = claim_original(c["url"], c["app"].state.storage, worker, claim["claim_id"], now)
    assert content == image_bytes() and mime == "image/png"
    assert start_attempt(c["url"], worker, claim["claim_id"], claim["contract_hash"], now)[
        "post_permitted"
    ]


@pytest.mark.parametrize("lowlevel", [False, True], ids=["fastmcp", "fallback"])
def test_stdio_inbox_roles_and_policy_invalidations_remain_visible(
    decision_case, tmp_path, lowlevel
):
    c = today_revision(decision_case)
    pt, grant = issue_grant(
        c["url"],
        c["a"]["tenant"],
        c["a"]["owner"],
        "planner",
        "own-planner",
        1,
        int(time.time()) + 600,
    )
    with http_server(c["app"]) as base:

        async def exercise():
            with (tmp_path / "roles-stdio.log").open("w+") as errors:
                async with (
                    stdio_client(params(base, pt, c["token"], lowlevel), errlog=errors) as (
                        read,
                        write,
                    ),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    initial = text_result(
                        await session.call_tool("eikon_get_publication_inbox", {})
                    )
                    assert initial["success"]
                    revoke_grant(c["url"], c["a"]["tenant"], c["a"]["owner"], grant["id"])
                    revoked = text_result(
                        await session.call_tool("eikon_get_publication_inbox", {})
                    )
                    assert not revoked["success"] and revoked["http_status"] == 403
                    # Reviewer sigue separado; no puede utilizar la credencial planner revocada.
                    listing = text_result(
                        await session.call_tool("eikon_list_publication_candidates", {})
                    )
                    assert listing["success"]
                    from webapp.publications.policies import set_policy
                    from webapp.tests.test_publication_policies import policy_payload

                    set_policy(
                        c["url"],
                        c["a"]["tenant"],
                        c["a"]["owner"],
                        1,
                        policy_payload(
                            c["a"]["project"]["id"],
                            c["a"]["brand"]["id"],
                            c["a"]["connection"]["id"],
                        ),
                    )
                    stale = text_result(
                        await session.call_tool("eikon_list_publication_candidates", {})
                    )
                    assert not stale["success"] and stale["http_status"] == 403
                async with (
                    stdio_client(params(base, c["token"], pt, lowlevel), errlog=errors) as (
                        read,
                        write,
                    ),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    wrong = text_result(await session.call_tool("eikon_get_publication_inbox", {}))
                    assert not wrong["success"] and wrong["error_code"] == "configuration_error"
                    wrong = text_result(
                        await session.call_tool("eikon_list_publication_candidates", {})
                    )
                    assert not wrong["success"] and wrong["error_code"] == "configuration_error"

        asyncio.run(exercise())
