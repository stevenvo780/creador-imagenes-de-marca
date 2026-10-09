"""Pruebas del flujo MCP end-to-end sin llamadas de red."""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Callable
from typing import Any

import pytest

if importlib.util.find_spec("mcp") is None:
    mcp_module = types.ModuleType("mcp")
    mcp_module.__path__ = []  # type: ignore[attr-defined]
    server_module = types.ModuleType("mcp.server")
    server_module.__path__ = []  # type: ignore[attr-defined]
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    class FakeFastMCP:
        def __init__(self, _name: str) -> None:
            pass

        def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return lambda function: function

    fastmcp_module.FastMCP = FakeFastMCP  # type: ignore[attr-defined]
    sys.modules.update(
        {
            "mcp": mcp_module,
            "mcp.server": server_module,
            "mcp.server.fastmcp": fastmcp_module,
        }
    )

from mcp_server import server


class FakeResponse:
    def __init__(self, data: Any = None, content: bytes = b"") -> None:
        self._data = data
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._data


class FakeClient:
    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        assert url.endswith("/api/v1/batches")
        assert kwargs["json"]["brand_id"] == 12
        return FakeResponse({"id": 7})

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        del kwargs
        if url.endswith("/api/v1/batches/7"):
            return FakeResponse({"status": "completed"})
        if url.endswith("/api/v1/batches/7/variations"):
            return FakeResponse({"items": [{"id": 9, "file_url": "/files/a.png"}]})
        if url.endswith("/files/a.png"):
            return FakeResponse(content=b"PNG")
        raise AssertionError(f"URL inesperada: {url}")


@pytest.mark.asyncio
async def test_generate_and_get_completes_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)

    result = await server.eikon_generate_and_get("12", "isotipo")

    assert result == {
        "success": True,
        "batch_id": 7,
        "variation_id": 9,
        "image_url": f"{server.EIKON_BASE_URL}/files/a.png",
        "image_base64": "UE5H",
        "asset_type": "isotipo",
        "message": "Asset generated successfully. Variation 9 from batch 7.",
    }


@pytest.mark.asyncio
async def test_generate_and_get_rejects_invalid_brand_id() -> None:
    result = await server.eikon_generate_and_get("not-an-id", "isotipo")

    assert result["success"] is False
    assert "Invalid brand_id" in result["error"]
