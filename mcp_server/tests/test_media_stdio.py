"""Recibo real: subproceso MCP stdio -> HTTP -> SQLite/Postgres sintéticos."""

import asyncio
import hashlib
import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from webapp import db
from webapp.app import create_app
from webapp.config import Settings
from webapp.storage import create_api_key
from webapp.tests.media_helpers import brand, image_bytes, project
from webapp.tests.test_projects import isolated_db as _isolated_db

isolated_db = _isolated_db
ROOT = Path(__file__).resolve().parents[2]
CANONICAL = {
    "eikon_list_brands",
    "eikon_create_brand",
    "eikon_logo_options",
    "eikon_set_identity",
    "eikon_list_asset_types",
    "eikon_generate_asset",
    "eikon_generate_and_get",
    "eikon_gallery",
    "eikon_list_projects",
    "eikon_create_project",
    "eikon_get_brand_brief",
    "eikon_create_generation_brief",
    "eikon_import_image",
    "eikon_list_media",
}


@pytest.mark.parametrize("lowlevel", [False, True], ids=["highlevel", "fallback"])
def test_stdio_authenticated_flow_and_revocation(isolated_db, tmp_path, monkeypatch, lowlevel):
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(
        data_root=tmp_path,
        db_url=str(isolated_db),
        jwt_secret="synthetic-only-test-secret-length-48-characters",
    )
    app = create_app(settings, output_root=tmp_path / "output")
    owner, foreign = TestClient(app), TestClient(app)
    server = None
    thread = None
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{listener.getsockname()[1]}"
    try:
        for client, slug in [(owner, "alpha"), (foreign, "beta")]:
            assert (
                client.post(
                    "/auth/register",
                    json={
                        "tenant_slug": slug,
                        "tenant_name": slug,
                        "email": slug + "@example.test",
                        "password": "synthetic-password-123",
                    },
                ).status_code
                == 201
            )
        own_project = project(owner, "campaign")
        own_brand = brand(owner, own_project["id"], "official")
        other_brand = brand(foreign, project(foreign, "foreign")["id"], "foreign")
        key_data = owner.post(
            "/api/v1/auth/api-keys",
            json={
                "name": "synthetic-mcp",
                "scopes": [
                    "projects:read",
                    "projects:write",
                    "brands:read",
                    "briefs:write",
                    "media:read",
                    "media:write",
                ],
            },
        ).json()
        key = key_data["key"]
        tenant = owner.get("/auth/me").json()["tenant"]["id"]
        legacy, _ = create_api_key(isolated_db, tenant)
        path = tmp_path / "client-private-image.png"
        content = image_bytes()
        path.write_bytes(content)
        config = uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        assert app.state.worker is None

        async def exercise():
            env = {
                "EIKON_BASE_URL": base,
                "EIKON_API_KEY": key,
                "EIKON_MCP_LOWLEVEL": "1" if lowlevel else "0",
            }
            params = StdioServerParameters(
                command=sys.executable, args=["-m", "mcp_server.server"], env=env, cwd=ROOT
            )
            with (tmp_path / "mcp-stderr.log").open("w+") as errlog:
                async with (
                    stdio_client(params, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    names = {tool.name for tool in tools}
                    assert names >= CANONICAL
                    assert {
                        "eikon_list_publication_candidates",
                        "eikon_get_publication_candidate",
                        "eikon_submit_publication_evaluation",
                        "eikon_prepare_publication_candidate",
                        "eikon_import_publication_video",
                    } <= names
                    assert len(names) == 27  # 22 anteriores y 5 de publicaciones.

                    async def call(tool_name, **arguments):
                        result = await session.call_tool(tool_name, arguments)
                        assert not getattr(result, "is_error", getattr(result, "isError", False))
                        return json.loads(result.content[0].text)

                    listed = await call("eikon_list_projects")
                    assert listed["success"] and listed["projects"]["items"] == [own_project]
                    created = await call(
                        "eikon_create_project", name="MCP project", slug="mcp-created"
                    )
                    assert created["success"]
                    kit = await call("eikon_get_brand_brief", brand_id=own_brand["id"])
                    assert kit["success"]
                    assert (await call("eikon_get_brand_brief", brand_id=other_brand["id"]))[
                        "http_status"
                    ] == 404
                    brief = await call(
                        "eikon_create_generation_brief",
                        brand_id=own_brand["id"],
                        prompt="Synthetic MCP prompt",
                        width=512,
                        height=512,
                    )
                    assert brief["success"]
                    upload_args = {
                        "brief_id": brief["brief"]["id"],
                        "file_path": str(path),
                        "idempotency_key": "stdio-one",
                        "provenance": {"tool": "synthetic-client"},
                    }
                    asset = await call("eikon_import_image", **upload_args)
                    assert asset["success"] and asset["media"]["status"] == "pending_review"
                    assert asset["media"]["sha256"] == hashlib.sha256(content).hexdigest()
                    assert asset["media"]["source"] == "codex"
                    assert await call("eikon_import_image", **upload_args) == asset
                    media = await call(
                        "eikon_list_media",
                        project_id=own_project["id"],
                        brand_id=own_brand["id"],
                        status="pending_review",
                    )
                    assert media["success"] and len(media["media"]["items"]) == 1
                    assert (await call("eikon_list_brands"))["success"]
                    denied = await call(
                        "eikon_set_identity",
                        brand_id=str(own_brand["id"]),
                        logo_style="pack_brand_form",
                    )
                    assert denied["success"] is False
                    async with httpx.AsyncClient(base_url=base) as remote:
                        headers = {"Authorization": f"Bearer {key}"}
                        assert (
                            await remote.post(
                                f"/api/v1/media/{asset['media']['id']}/reviews",
                                headers=headers,
                                json={},
                            )
                        ).status_code == 403
                        assert (
                            await remote.get("/api/v1/auth/api-keys", headers=headers)
                        ).status_code == 403
                        assert (
                            await remote.get(
                                "/api/v1/projects", headers={"Authorization": f"Bearer {legacy}"}
                            )
                        ).status_code == 403
                        assert (
                            await remote.get(
                                "/api/v1/brands", headers={"Authorization": f"Bearer {legacy}"}
                            )
                        ).status_code == 200
                        downloaded = await remote.get(
                            asset["media"]["download_url"], headers=headers
                        )
                        assert downloaded.status_code == 200 and downloaded.content == content
                    with db.connect(isolated_db) as con:
                        con.execute(
                            "UPDATE api_keys SET expires_at = 0 WHERE id = ?", (key_data["id"],)
                        )
                    expired = await call("eikon_list_projects")
                    assert expired["http_status"] == 401 and expired["success"] is False
                    with db.connect(isolated_db) as con:
                        con.execute(
                            "UPDATE api_keys SET expires_at = ? WHERE id = ?",
                            (int(time.time()) + 3600, key_data["id"]),
                        )
                    assert (
                        owner.delete(f"/api/v1/auth/api-keys/{key_data['id']}").status_code == 204
                    )
                    revoked = await call("eikon_list_projects")
                    assert revoked["http_status"] == 401 and revoked["error_code"] == "unauthorized"
                    assert key not in json.dumps(revoked) and str(path) not in json.dumps(revoked)
                errlog.seek(0)
                assert key not in errlog.read()

        asyncio.run(exercise())
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
            assert not thread.is_alive()
        listener.close()
        owner.close()
        foreign.close()
