"""Cliente de encargos: bytes reales, permisos y errores sin información sensible."""

import asyncio
import io
import json

import httpx
import pytest
from PIL import Image

from mcp_server.media_tools import MAX_BYTES, MediaTools


def image_bytes(fmt="PNG", size=(512, 512)):
    out = io.BytesIO()
    Image.new("RGB", size, "blue").save(out, format=fmt)
    return out.getvalue()


def run_import(path, handler, provenance=None, key="one"):
    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=True
        ) as client:
            return await MediaTools(
                "https://example.invalid", "synthetic-key", client
            ).import_image(1, str(path), key, provenance)

    return asyncio.run(invoke())


@pytest.mark.parametrize(
    "fmt,filename,mime", [("PNG", "image.png", "image/png"), ("JPEG", "image.jpg", "image/jpeg")]
)
def test_import_sends_bytes_not_server_path(tmp_path, fmt, filename, mime):
    path = tmp_path / "private-client-name.dat"
    content = image_bytes(fmt)
    path.write_bytes(content)

    def handle(request):
        assert request.url.path == "/api/v1/media"
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        assert request.headers["Idempotency-Key"] == "one"
        assert content in request.content
        assert str(path).encode() not in request.content
        assert path.name.encode() not in request.content
        assert filename.encode() in request.content
        assert mime.encode() in request.content
        assert b"codex" in request.content and b"client-test" in request.content
        return httpx.Response(201, json={"id": 9, "status": "pending_review"})

    assert run_import(path, handle, {"method": "client-test"}) == {
        "success": True,
        "media": {"id": 9, "status": "pending_review"},
    }


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (409, "conflict"),
        (413, "too_large"),
        (422, "invalid_request"),
        (500, "backend_error"),
    ],
)
def test_error_causes_are_safe(tmp_path, status, code):
    path = tmp_path / "secret-name.png"
    path.write_bytes(image_bytes())
    result = run_import(
        path,
        lambda request: httpx.Response(
            status, json={"detail": "synthetic-key secret-name.png sensitive-body"}
        ),
    )
    assert result["success"] is False and result["error_code"] == code
    assert result["http_status"] == status
    assert not any(
        x in json.dumps(result) for x in ["synthetic-key", "secret-name", "sensitive-body"]
    )


def test_authenticated_upload_never_follows_redirect(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(image_bytes())
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://evil.invalid/leak"})

    assert run_import(path, handle)["error_code"] == "redirect_refused"
    assert seen == ["https://example.invalid/api/v1/media"]


@pytest.mark.parametrize(
    "kind",
    ["missing", "directory", "symlink", "fifo", "bad", "truncated", "oversize", "small", "pixels"],
)
def test_rejects_invalid_file_before_network(tmp_path, kind):
    path = tmp_path / "private.png"
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_bytes(image_bytes())
        path.symlink_to(target)
    elif kind == "fifo":
        import os

        os.mkfifo(path)
    elif kind == "bad":
        path.write_bytes(b"<svg/>")
    elif kind == "truncated":
        path.write_bytes(image_bytes()[:100])
    elif kind == "oversize":
        with path.open("wb") as stream:
            stream.truncate(MAX_BYTES + 1)
    elif kind == "small":
        path.write_bytes(image_bytes(size=(10, 10)))
    elif kind == "pixels":
        path.write_bytes(image_bytes(size=(8192, 8192)))

    def forbidden(request):
        raise AssertionError("invalid file reached network")

    result = run_import(path, forbidden)
    assert result["success"] is False
    assert "private.png" not in json.dumps(result)


@pytest.mark.parametrize(
    "base",
    [
        "http://example.invalid",
        "https://user:pass@example.invalid",
        "https://example.invalid/?token=secret",
        "file:///tmp/a",
        "https://example.invalid/base",
        "https://example.invalid/#x",
    ],
)
def test_unsafe_base_url_fails_without_network(base):
    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: pytest.fail("network"))
        ) as client:
            return await MediaTools(base, "key", client).list_projects()

    assert asyncio.run(invoke())["error_code"] == "configuration_error"


def test_six_routes_and_filters():
    seen = []

    def handle(request):
        seen.append(
            (
                request.method,
                request.url.path,
                dict(request.url.params),
                json.loads(request.content) if request.content else None,
            )
        )
        return httpx.Response(200, json={"items": []} if request.method == "GET" else {"id": 1})

    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            tools = MediaTools("http://127.0.0.1:8000", "key", client)
            for call in [
                tools.list_projects(),
                tools.create_project("Name", "slug", "description"),
                tools.get_brand_brief(2),
                tools.create_generation_brief(2, "Prompt", 512, 512),
                tools.list_media(1, 2, "pending_review"),
            ]:
                assert (await call)["success"]

    asyncio.run(invoke())
    assert [x[:2] for x in seen] == [
        ("GET", "/api/v1/projects"),
        ("POST", "/api/v1/projects"),
        ("GET", "/api/v1/brands/2/brief"),
        ("POST", "/api/v1/generation-briefs"),
        ("GET", "/api/v1/media"),
    ]
    assert seen[1][3] == {"name": "Name", "slug": "slug", "description": "description"}
    assert seen[3][3] == {"brand_id": 2, "prompt": "Prompt", "width": 512, "height": 512}
    assert seen[4][2] == {"project_id": "1", "brand_id": "2", "status": "pending_review"}


@pytest.mark.parametrize(
    "case", ["network", "bad-json", "bad-shape", "missing-key", "unsafe-header", "unicode-header"]
)
def test_safe_transport_and_configuration_errors(case):
    def handle(request):
        if case == "network":
            raise httpx.ConnectError("sensitive-message secret-token", request=request)
        if case == "bad-json":
            return httpx.Response(200, text="sensitive-message secret-token")
        return httpx.Response(200, json=[])

    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            key = (
                ""
                if case == "missing-key"
                else "secret\r\ntoken"
                if case == "unsafe-header"
                else "clavé"
                if case == "unicode-header"
                else "key"
            )
            return await MediaTools("https://example.invalid", key, client).list_projects()

    result = asyncio.run(invoke())
    assert result["success"] is False
    assert not any(x in json.dumps(result) for x in ["sensitive-message", "secret-token"])


@pytest.mark.parametrize(
    "changes",
    [
        {"idempotency_key": "bad\nkey"},
        {"idempotency_key": ""},
        {"brief_id": "../escape"},
        {"provenance": []},
        {"provenance": {"x": float("nan")}},
        {"provenance": {"x": "x" * 16001}},
    ],
)
def test_invalid_metadata_and_ids_do_not_open_file_or_network(changes, tmp_path):
    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: pytest.fail("network"))
        ) as client:
            values = {
                "brief_id": 1,
                "file_path": str(tmp_path / "missing-private-file"),
                "idempotency_key": "one",
                "provenance": {},
            }
            values.update(changes)
            return await MediaTools("https://example.invalid", "key", client).import_image(**values)

    assert asyncio.run(invoke())["error_code"] == "invalid_request"


def test_png_bad_idat_crc_returns_safe_error_without_http(tmp_path):
    content = bytearray(image_bytes())
    offset = 8  # Firma PNG; recorrer chunks para alterar sólo el CRC IDAT.
    while offset < len(content):
        chunk_size = int.from_bytes(content[offset : offset + 4], "big")
        if content[offset + 4 : offset + 8] == b"IDAT":
            crc_offset = offset + 8 + chunk_size
            content[crc_offset] ^= 1
            break
        offset += chunk_size + 12
    else:
        pytest.fail("PNG sintético sin chunk IDAT")

    # Pillow real reconoce PNG y dimensiones; verify detecta CRC, no un MIME falso.
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "PNG" and image.size == (512, 512)
        with pytest.raises(SyntaxError, match="bad header checksum"):
            image.verify()

    path = tmp_path / "private-corrupt-client-image.png"
    path.write_bytes(content)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(201, json={"id": 9, "status": "pending_review"})

    result = run_import(path, handle)
    assert result["success"] is False and result["error_code"] == "invalid_image"
    assert requests == []
    encoded = json.dumps(result)
    assert not any(
        value in encoded
        for value in [
            str(path),
            path.name,
            "synthetic-key",
            "SyntaxError",
            "checksum",
            "IDAT",
        ]
    )


@pytest.mark.parametrize("method", ["list_projects", "list_media"])
@pytest.mark.parametrize(
    "args",
    [
        {"cursor": -1},
        {"cursor": True},
        {"cursor": "5"},
        {"cursor": 1.5},
        {"cursor": 2**63},
        {"limit": 0},
        {"limit": 101},
        {"limit": False},
        {"limit": "50"},
        {"limit": []},
    ],
)
def test_pagination_invalid_without_network(method, args):
    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: pytest.fail("network"))
        ) as client:
            return await getattr(MediaTools("https://example.invalid", "key", client), method)(
                **args
            )

    assert asyncio.run(invoke())["error_code"] == "invalid_request"


@pytest.mark.parametrize(
    "method,resource", [("list_projects", "projects"), ("list_media", "media")]
)
def test_pagination_two_pages_preserves_filters(method, resource):
    def handle(request):
        params = dict(request.url.params)
        if resource == "media":
            assert {k: params[k] for k in ("project_id", "brand_id", "status")} == {
                "project_id": "7",
                "brand_id": "9",
                "status": "pending_review",
            }
        start = int(params.get("cursor", 0))
        limit = int(params.get("limit", 50))
        rows = [{"id": i} for i in range(start + 1, min(start + limit, 51) + 1)]
        return httpx.Response(
            200, json={"items": rows, "next_cursor": rows[-1]["id"] if start + limit < 51 else None}
        )

    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            call = getattr(MediaTools("https://example.invalid", "key", client), method)
            filters = (
                {"project_id": 7, "brand_id": 9, "status": "pending_review"}
                if resource == "media"
                else {}
            )
            first = (await call(**filters))[resource]
            second = (await call(**filters, cursor=first["next_cursor"], limit=50))[resource]
            assert len(first["items"]) == 50 and len(second["items"]) == 1
            assert {x["id"] for x in first["items"]}.isdisjoint(x["id"] for x in second["items"])
            assert second["next_cursor"] is None

    asyncio.run(invoke())
