"""Tokens por rol y entrega multimodal real por stdio, con modelo doble explícito."""

import asyncio
import base64
import hashlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from webapp.publications.contracts import canonical_hash
from webapp.tests.media_helpers import image_bytes
from webapp.tests.test_publication_campaigns import campaign_case as _campaign_case
from webapp.tests.test_publication_campaigns import campaign_clients as _campaign_clients
from webapp.tests.test_publication_campaigns import isolated_db as _isolated_db
from webapp.tests.test_publication_decisions import decision_case as _decision_case
from webapp.tests.test_publication_decisions import response

campaign_clients = _campaign_clients
campaign_case = _campaign_case
isolated_db = _isolated_db
decision_case = _decision_case


def test_missing_role_tokens_never_fallback_to_legacy(monkeypatch):
    monkeypatch.setenv("EIKON_API_KEY", "legacy-key")
    from mcp_server.publication_tools import PublicationTools

    requests = []

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: requests.append(r) or httpx.Response(200, json={})
            )
        ) as client:
            tools = PublicationTools("http://localhost", "", "", client)
            assert not (await tools.list_candidates())["success"]
            assert not (await tools.prepare_candidate(1, {}))["success"]

    asyncio.run(run())
    assert not requests


def test_role_tokens_and_redirects_are_isolated():
    from mcp_server.publication_tools import PublicationTools

    seen = []

    def handle(request):
        seen.append((request.url.path, request.headers["authorization"]))
        return httpx.Response(302, headers={"Location": "https://foreign.test"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            tools = PublicationTools(
                "http://localhost", "eikon_pub_planner_test", "eikon_pub_reviewer_test", client
            )
            assert (await tools.list_candidates())["error_code"] == "redirect_refused"
            assert (await tools.prepare_candidate(1, {}))["error_code"] == "redirect_refused"

    asyncio.run(run())
    assert seen == [
        ("/api/v1/publications/reviewer/candidates", "Bearer eikon_pub_reviewer_test"),
        ("/api/v1/publications/planner/campaigns/1/revisions", "Bearer eikon_pub_planner_test"),
    ]


def test_video_import_refuses_symlink_fifo_oversize_and_wrong_extension(tmp_path):
    from mcp_server.publication_tools import PublicationTools

    p = tmp_path / "clip.mp4"
    p.write_bytes(b"video")
    link = tmp_path / "link.mp4"
    link.symlink_to(p)
    fifo = tmp_path / "fifo.mp4"
    os.mkfifo(fifo)
    huge = tmp_path / "huge.mp4"
    with huge.open("wb") as f:
        f.truncate(32 * 1024 * 1024 + 1)
    wrong = tmp_path / "secret.txt"
    wrong.write_bytes(b"secret")
    for path in (link, fifo, huge, wrong):
        with pytest.raises((OSError, ValueError)):
            PublicationTools._read_video(str(path))


@pytest.mark.parametrize("lowlevel", [False, True], ids=["fastmcp", "fallback"])
def test_stdio_reviewer_receives_image_records_decision_and_reads_same_hash(
    decision_case, tmp_path, lowlevel
):
    c = decision_case
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(c["app"], lifespan="off", access_log=False, log_level="critical")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started

        async def exercise():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=Path(__file__).resolve().parents[2],
                env={
                    "EIKON_BASE_URL": base,
                    "EIKON_PUBLICATION_REVIEWER_TOKEN": c["token"],
                    "EIKON_MCP_LOWLEVEL": "1" if lowlevel else "0",
                },
            )
            with (tmp_path / "publication-stdio.log").open("w+") as errlog:
                async with (
                    stdio_client(params, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    names = {t.name for t in (await session.list_tools()).tools}
                    assert {
                        "eikon_list_publication_candidates",
                        "eikon_get_publication_candidate",
                        "eikon_submit_publication_evaluation",
                        "eikon_prepare_publication_candidate",
                        "eikon_import_publication_video",
                    } <= names
                    listing = await session.call_tool(
                        "eikon_list_publication_candidates", {"cursor": 0, "limit": 1}
                    )
                    assert (
                        json.loads(listing.content[0].text)["candidates"]["items"][0]["id"]
                        == c["revision"]["id"]
                    )
                    got = await session.call_tool(
                        "eikon_get_publication_candidate", {"revision_id": c["revision"]["id"]}
                    )
                    text = next(item.text for item in got.content if item.type == "text")
                    material = json.loads(text)["candidate"]
                    images = [item for item in got.content if item.type == "image"]
                    assert len(images) == 1 and base64.b64decode(images[0].data) == image_bytes()
                    answer = response()
                    receipt = {
                        "delivery_id": material["delivery"]["id"],
                        "request_id": material["delivery"]["request_id"],
                        "provider": "test-double",
                        "model": "fixture-model",
                        "subject": "own-codex",
                        "contract_hash": c["revision"]["contract_hash"],
                        "material_hashes": material["material_hashes"],
                        "response_hash": canonical_hash(answer),
                        "review_mode": material["delivery"]["review_mode"],
                        "evidence": material["delivery"]["evidence"],
                        "attestation": "client_reported",
                    }
                    submitted = await session.call_tool(
                        "eikon_submit_publication_evaluation",
                        {
                            "revision_id": c["revision"]["id"],
                            "expected_contract_hash": c["revision"]["contract_hash"],
                            "policy_version": 1,
                            "material_hashes": material["material_hashes"],
                            "model_receipt": receipt,
                            "response": answer,
                        },
                    )
                    result = json.loads(submitted.content[0].text)
                    assert result["success"] and result["evaluation"]["eligibility"]["eligible"]
                    again = await session.call_tool(
                        "eikon_get_publication_candidate", {"revision_id": c["revision"]["id"]}
                    )
                    reread = json.loads(
                        next(item.text for item in again.content if item.type == "text")
                    )["candidate"]
                    assert reread["candidate"]["contract_hash"] == c["revision"]["contract_hash"]
                    assert (
                        reread["eligibility"]["decision_id"]
                        == result["evaluation"]["decision"]["id"]
                    )
                errlog.seek(0)
                assert c["token"] not in errlog.read()

        asyncio.run(exercise())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


@pytest.mark.parametrize("lowlevel", [False, True], ids=["fastmcp", "fallback"])
def test_stdio_candidate_two_pngs_are_native_without_base64_text(campaign_case, tmp_path, lowlevel):
    from datetime import UTC, datetime

    from webapp import brand_briefs
    from webapp.publications.auth import issue_grant
    from webapp.tests.media_helpers import brief, upload
    from webapp.tests.test_publication_campaigns import campaign, freeze

    url, (a, _), app = campaign_case
    piece, logo = image_bytes(), image_bytes(64, 64, "red")
    expected_hashes = [hashlib.sha256(raw).hexdigest() for raw in (piece, logo)]
    saved = brand_briefs.save_reference_logo(
        url, a["tenant"], a["brand"]["id"], logo, app.state.storage
    )
    job = brief(a["client"], a["brand"]["id"])
    uploaded = upload(a["client"], job["id"], "piece-with-reference", piece)
    assert uploaded.status_code == 201
    a = {**a, "brief": job, "media": uploaded.json()}
    revision = freeze(
        url,
        a,
        campaign(url, a),
        scheduled_at=datetime.fromtimestamp(time.time() + 3600, UTC).isoformat(),
    )
    token, _ = issue_grant(
        url, a["tenant"], a["owner"], "reviewer", "own-codex", 1, int(time.time()) + 600
    )
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

        async def exercise():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=Path(__file__).resolve().parents[2],
                env={
                    "EIKON_BASE_URL": base,
                    "EIKON_API_KEY": "",
                    "EIKON_PUBLICATION_REVIEWER_TOKEN": token,
                    "EIKON_MCP_LOWLEVEL": "1" if lowlevel else "0",
                },
            )
            with (tmp_path / "two-png-stdio.log").open("w+") as errlog:
                async with (
                    stdio_client(params, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    got = await session.call_tool(
                        "eikon_get_publication_candidate", {"revision_id": revision["id"]}
                    )
                    assert [block.type for block in got.content] == ["text", "image", "image"]
                    assert (
                        getattr(got, "structured_content", getattr(got, "structuredContent", None))
                        is None
                    )
                    text = got.content[0].text
                    envelope = json.loads(text)
                    assert set(envelope) == {"success", "candidate"} and envelope["success"]
                    material = envelope["candidate"]
                    assert material["candidate"]["contract_hash"] == revision["contract_hash"]
                    assert material["reference_original"] == {
                        "mime_type": "image/png",
                        "sha256": saved["sha256"],
                    }
                    assert [m["sha256"] for m in material["delivered_materials"]] == expected_hashes
                    assert all("data" not in m for m in material["delivered_materials"])
                    assert material["material_hashes"]["media_sha256"] == expected_hashes[0]
                    evidence = material["delivery"]["evidence"]
                    assert evidence["reference_original_sha256"] == expected_hashes[1]
                    assert evidence["reference_render_sha256"] == expected_hashes[1]
                    for block, original, expected in zip(
                        got.content[1:], (piece, logo), expected_hashes, strict=True
                    ):
                        decoded = base64.b64decode(block.data)
                        assert decoded == original and hashlib.sha256(decoded).hexdigest() == expected
                        assert block.data not in text
                        assert (
                            getattr(block, "mime_type", getattr(block, "mimeType", None))
                            == "image/png"
                        )
                errlog.seek(0)
                assert token not in errlog.read()

        asyncio.run(exercise())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


def test_planner_private_video_import_and_prepare_cannot_decide(campaign_case, tmp_path):
    import subprocess
    from datetime import UTC, datetime

    from mcp_server.publication_tools import PublicationTools
    from webapp.publications.auth import issue_grant
    from webapp.tests.media_helpers import brief
    from webapp.tests.test_publication_campaigns import campaign

    url, (a, _), app = campaign_case
    grant, _ = issue_grant(
        url, a["tenant"], a["owner"], "planner", "own-planner", 1, int(time.time()) + 600
    )
    job = brief(a["client"], a["brand"]["id"], 320, 256)
    p = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=teal:s=320x256:r=10",
            "-t",
            "0.4",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(p),
        ],
        timeout=15,
        check=True,
    )
    c = campaign(url, a)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            tools = PublicationTools("http://localhost", grant, grant, client)
            imported = await tools.import_video(job["id"], str(p), "private-planner-mp4", "owned")
            assert imported["success"] and imported["media"]["media_kind"] == "publication_video"
            payload = {
                "media_kind": "publication_video",
                "media_id": imported["media"]["id"],
                "caption": "Video final",
                "connection_id": a["connection"]["id"],
                "scheduled_at": datetime.fromtimestamp(time.time() + 3600, UTC).isoformat(),
                "policy_version": 1,
                "channel_metadata": {"rights": "owned", "sources": ["https://example.test/manual"]},
            }
            prepared = await tools.prepare_candidate(c["id"], payload)
            assert (
                prepared["success"]
                and prepared["candidate"]["snapshot"]["media"]["sha256"]
                == imported["media"]["sha256"]
            )
            assert not (
                await tools.submit_evaluation(
                    prepared["candidate"]["id"],
                    prepared["candidate"]["contract_hash"],
                    1,
                    {},
                    {},
                    {},
                )
            )["success"]

    asyncio.run(exercise())
