"""Paginación real stdio -> HTTP -> BD por ambas implementaciones MCP."""

import asyncio
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from webapp.tests.media_helpers import brand, brief, image_bytes, project, upload
from webapp.tests.test_media_permissions import permission_db_clients as _permission_db_clients
from webapp.tests.test_projects import isolated_db as _isolated_db

isolated_db = _isolated_db
permission_db_clients = _permission_db_clients
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("lowlevel", [False, True], ids=["highlevel", "fallback"])
def test_stdio_two_pages_filters_and_tenant_isolation(permission_db_clients, tmp_path, lowlevel):
    owner, foreign, _ = permission_db_clients
    projects = [project(owner, f"campaign-{i}") for i in range(51)]
    foreign_project = project(foreign, "foreign")
    own_brand = brand(owner, projects[0]["id"], "official")
    foreign_brand = brand(foreign, foreign_project["id"], "foreign")
    own_brief = brief(owner, own_brand["id"])
    other_brief = brief(foreign, foreign_brand["id"])
    content = image_bytes()
    media = []
    for i in range(51):
        result = upload(owner, own_brief["id"], f"pagination-{i}", content)
        assert result.status_code == 201
        media.append(result.json())
    other_media = upload(foreign, other_brief["id"], "foreign", content)
    assert other_media.status_code == 201
    key = owner.post(
        "/api/v1/auth/api-keys",
        json={"name": "pagination", "scopes": ["projects:read", "media:read"]},
    ).json()["key"]
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(owner.app, log_level="critical", access_log=False, lifespan="off")
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
                cwd=ROOT,
                env={
                    "EIKON_BASE_URL": base,
                    "EIKON_API_KEY": key,
                    "EIKON_MCP_LOWLEVEL": "1" if lowlevel else "0",
                },
            )
            with (tmp_path / "mcp-pagination-stderr.log").open("w+") as log:
                async with (
                    stdio_client(params, errlog=log) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    assert {
                        "eikon_list_publication_candidates",
                        "eikon_get_publication_candidate",
                        "eikon_submit_publication_evaluation",
                        "eikon_prepare_publication_candidate",
                        "eikon_import_publication_video",
                    } <= set(tools)
                    assert len(tools) == 28
                    assert "eikon_get_publication_inbox" in tools
                    for resource, expected, filters in [
                        ("projects", projects, {}),
                        (
                            "media",
                            media,
                            {
                                "project_id": projects[0]["id"],
                                "brand_id": own_brand["id"],
                                "status": "pending_review",
                            },
                        ),
                    ]:
                        name = f"eikon_list_{resource}"
                        tool = tools[name]
                        schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", None))
                        assert "cursor" not in schema.get("required", [])
                        assert "limit" not in schema.get("required", [])
                        for field, low, high in [("cursor", 0, 2**63 - 1), ("limit", 1, 100)]:
                            integer = next(
                                v
                                for v in schema["properties"][field]["anyOf"]
                                if v.get("type") == "integer"
                            )
                            assert integer["minimum"] == low and integer["maximum"] == high

                        async def call(tool_name=name, result_resource=resource, **args):
                            result = await session.call_tool(tool_name, args)
                            assert not getattr(
                                result, "is_error", getattr(result, "isError", False)
                            )
                            parsed = json.loads(result.content[0].text)
                            assert parsed["success"], parsed
                            return parsed[result_resource]

                        page1 = await call(**filters)  # Compatibilidad sin nuevos argumentos.
                        page2 = await call(**filters, cursor=page1["next_cursor"], limit=50)
                        assert len(page1["items"]) == 50 and len(page2["items"]) == 1
                        first_ids = {x["id"] for x in page1["items"]}
                        second_ids = {x["id"] for x in page2["items"]}
                        assert first_ids.isdisjoint(second_ids)
                        assert first_ids | second_ids == {x["id"] for x in expected}
                        assert page2["next_cursor"] is None
                        assert (await call(**filters, cursor=0, limit=1))["items"][0][
                            "id"
                        ] in first_ids
                        assert (
                            await call(**filters, cursor=max(first_ids | second_ids), limit=100)
                        )["items"] == []
                        for bad in (
                            {"cursor": True},
                            {"limit": False},
                            {"cursor": "1"},
                            {"limit": 101},
                        ):
                            result = await session.call_tool(name, {**filters, **bad})
                            if not getattr(result, "is_error", getattr(result, "isError", False)):
                                assert (
                                    json.loads(result.content[0].text)["error_code"]
                                    == "invalid_request"
                                )
                        if resource == "media":
                            assert (await call(project_id=foreign_project["id"]))["items"] == []
                            assert (await call(brand_id=foreign_brand["id"]))["items"] == []
                            assert (await call(status="approved"))["items"] == []
                log.seek(0)
                assert key not in log.read()

        asyncio.run(exercise())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
