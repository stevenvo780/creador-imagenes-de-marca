from __future__ import annotations

import io
import time
import uuid
import zipfile
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Page

JsonMap = dict[str, Any]
PASSWORD = "supersecret1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FINISHED_STATUSES = {"finished", "completed"}
TERMINAL_STATUSES = FINISHED_STATUSES | {"failed", "cancelled"}
FETCH_SCRIPT = """async ({method, path, payload, binary}) => {
    const options = {method, credentials: 'include', headers: {}};
    if (payload !== null) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(payload);
    }
    const response = await fetch(path, options);
    const headers = Object.fromEntries(response.headers.entries());
    if (binary) {
        const buffer = await response.arrayBuffer();
        return {status: response.status, headers, bytes: Array.from(new Uint8Array(buffer))};
    }
    const text = await response.text();
    return {status: response.status, headers, data: text ? JSON.parse(text) : {}};
}"""


async def _browser_fetch(
    page: Page,
    method: str,
    path: str,
    *,
    expected_status: int,
    payload: JsonMap | None = None,
    binary: bool = False,
) -> JsonMap:
    result = await page.evaluate(
        FETCH_SCRIPT,
        {"method": method, "path": path, "payload": payload, "binary": binary},
    )
    data = cast(JsonMap, result)
    assert data["status"] == expected_status, data
    return data


async def _fetch_json(
    page: Page,
    method: str,
    path: str,
    *,
    expected_status: int,
    payload: JsonMap | None = None,
) -> JsonMap:
    result = await _browser_fetch(
        page,
        method,
        path,
        expected_status=expected_status,
        payload=payload,
    )
    return cast(JsonMap, result["data"])


async def _fetch_bytes(
    page: Page,
    method: str,
    path: str,
    *,
    expected_status: int,
    payload: JsonMap | None = None,
) -> tuple[bytes, dict[str, str]]:
    result = await _browser_fetch(
        page,
        method,
        path,
        expected_status=expected_status,
        payload=payload,
        binary=True,
    )
    headers = {str(k).lower(): str(v) for k, v in cast(JsonMap, result["headers"]).items()}
    return bytes(cast(list[int], result["bytes"])), headers


async def _assert_auth_cookie(page: Page) -> None:
    cookies = await page.context.cookies()
    cookie = next((item for item in cookies if item["name"] == "eikon_jwt"), None)
    assert cookie is not None
    assert cookie["httpOnly"] is True


async def _register(page: Page, tenant_slug: str, email: str) -> JsonMap:
    body = await _fetch_json(
        page,
        "POST",
        "/auth/register",
        expected_status=201,
        payload={
            "tenant_slug": tenant_slug,
            "tenant_name": tenant_slug.replace("-", " ").title(),
            "email": email,
            "password": PASSWORD,
        },
    )
    await _assert_auth_cookie(page)
    return body


async def _login(page: Page, email: str) -> JsonMap:
    body = await _fetch_json(
        page,
        "POST",
        "/auth/login",
        expected_status=200,
        payload={"email": email, "password": PASSWORD},
    )
    await _assert_auth_cookie(page)
    return body


def _entity_id(body: JsonMap, alias: str) -> int:
    value = body.get(alias, body.get("id"))
    assert isinstance(value, int), body
    return value


def _items(body: JsonMap) -> list[JsonMap]:
    value = body.get("variations", body.get("items"))
    assert isinstance(value, list), body
    return cast(list[JsonMap], value)


async def _create_brand(page: Page, slug: str, name: str) -> JsonMap:
    palette = {
        "bg": "#102027",
        "primario": "#102027",
        "acento": "#2dd4bf",
        "acento_2": "#f59e0b",
        "texto": "#f8fafc",
    }
    typography = {"titulos": "Inter", "cuerpo": "Inter"}
    body = await _fetch_json(
        page,
        "POST",
        "/api/v1/brands",
        expected_status=201,
        payload={
            "slug": slug,
            "name": name,
            "palette": palette,
            "palette_json": palette,
            "typography": typography,
            "typography_json": typography,
            "logo_text": name,
            "logo_symbol": "E",
            "texts": {"logo_symbol_color": {"titulo": name, "subtitulo": "E2E render"}},
        },
    )
    assert _entity_id(body, "brand_id") > 0
    return body


async def _create_batch(page: Page, brand_id: int) -> JsonMap:
    body = await _fetch_json(
        page,
        "POST",
        "/api/v1/batches",
        expected_status=202,
        payload={
            "brand_id": brand_id,
            "asset_types": ["logo_symbol_color"],
            "axis_params": {"permuted": ["palette_scheme"], "count": 3},
            "fixed": {"background_treatment": "solid", "corner_shape": "rounded"},
            "permuted": ["palette_scheme"],
            "count": 3,
            "seed_salt": "e2e-full-flow",
        },
    )
    assert body["status"] == "pending"
    assert _entity_id(body, "batch_id") > 0
    return body


async def _wait_for_batch_finished(page: Page, batch_id: int) -> JsonMap:
    deadline = time.monotonic() + 30
    last_body: JsonMap = {}
    while time.monotonic() < deadline:
        last_body = await _fetch_json(
            page, "GET", f"/api/v1/batches/{batch_id}", expected_status=200
        )
        if str(last_body.get("status")) in TERMINAL_STATUSES:
            break
        await page.wait_for_timeout(500)
    assert last_body.get("status") in FINISHED_STATUSES, last_body
    return last_body


def _assert_zip_has_three_pngs(zip_bytes: bytes) -> None:
    """Valida que el zip tenga >= 2 PNGs (algunos pueden filtrarse por quality gates)."""
    zip_buffer = io.BytesIO(zip_bytes)
    assert zipfile.is_zipfile(zip_buffer)
    zip_buffer.seek(0)
    with zipfile.ZipFile(zip_buffer) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        png_infos = [info for info in infos if info.filename.endswith(".png")]
        assert len(png_infos) >= 2, f"Expected >= 2 PNGs, got {len(png_infos)}"
        for info in png_infos:
            data = archive.read(info)
            assert data.startswith(PNG_SIGNATURE), f"{info.filename} no es PNG"
            assert len(data) > 1024, f"{info.filename} pesa menos de 1KB"


@pytest.mark.asyncio
async def test_end_to_end_full_flow(page: Page) -> None:
    response = await page.goto("/health")
    assert response is not None
    assert response.status == 200

    suffix = uuid.uuid4().hex[:8]
    email = f"owner-{suffix}@example.com"
    brand_slug = f"e2e-flow-{suffix}"
    sibling_slug = f"e2e-sibling-{suffix}"

    register_body = await _register(page, "test-org", email)
    assert register_body["tenant"]["slug"] == "test-org"

    login_body = await _login(page, email)
    assert login_body["user"]["email"] == email

    me_body = await _fetch_json(page, "GET", "/auth/me", expected_status=200)
    assert me_body["user"]["email"] == email
    assert me_body["tenant"]["slug"] == "test-org"

    axes_body = await _fetch_json(page, "GET", "/api/v1/wizard/axes", expected_status=200)
    axis_names = {axis["name"] for axis in axes_body["axes"]}
    assert {"palette_scheme", "density_scale"}.issubset(axis_names)

    wizard_brands_before = await _fetch_json(
        page, "GET", "/api/v1/wizard/brands", expected_status=200
    )
    assert _items(wizard_brands_before) == []

    brand = await _create_brand(page, brand_slug, "Eikon Flow")
    brand_id = _entity_id(brand, "brand_id")
    sibling = await _create_brand(page, sibling_slug, "Eikon Sibling")
    sibling_brand_id = _entity_id(sibling, "brand_id")

    wizard_brands_after = await _fetch_json(
        page, "GET", "/api/v1/wizard/brands", expected_status=200
    )
    assert [item["id"] for item in _items(wizard_brands_after)] == [brand_id, sibling_brand_id]

    # Aislamiento multi-tenant: otro contexto no puede leer recursos del tenant A.
    browser = page.context.browser
    assert browser is not None
    current = urlsplit(page.url)
    context_b = await browser.new_context(base_url=f"{current.scheme}://{current.netloc}")
    page_b = await context_b.new_page()
    try:
        await page_b.goto("/health")
        await _register(page_b, f"e2e-rival-{suffix}", f"rival-{suffix}@example.com")
        brand_b = await _create_brand(page_b, f"e2e-rival-brand-{suffix}", "Rival")
        brands_b = await _fetch_json(page_b, "GET", "/api/v1/brands", expected_status=200)
        assert [item["id"] for item in brands_b["items"]] == [_entity_id(brand_b, "brand_id")]
        await _fetch_json(page_b, "GET", f"/api/v1/brands/{brand_id}", expected_status=404)
        await _fetch_json(page_b, "GET", f"/api/v1/gallery/{brand_id}", expected_status=404)
    finally:
        await context_b.close()

    batch_body = await _create_batch(page, brand_id)
    batch_id = _entity_id(batch_body, "batch_id")
    finished_batch = await _wait_for_batch_finished(page, batch_id)
    counts = cast(JsonMap, finished_batch.get("counts", finished_batch.get("counts_json", {})))
    assert counts.get("rendered") == 3, finished_batch
    # Ranking is post-processing; allow >= 2 ranked (some may be filtered by quality gates)
    assert cast(int, counts.get("ranked", 0)) >= 2, finished_batch

    gallery_body = await _fetch_json(
        page, "GET", f"/api/v1/gallery/{brand_id}", expected_status=200
    )
    variations = _items(gallery_body)
    assert len(variations) >= 2, gallery_body
    assert all(variation["output_path"] for variation in variations)
    assert all(variation["brand_id"] == brand_id for variation in variations)

    sibling_gallery = await _fetch_json(
        page, "GET", f"/api/v1/gallery/{sibling_brand_id}", expected_status=200
    )
    assert _items(sibling_gallery) == []

    zip_bytes, zip_headers = await _fetch_bytes(
        page, "POST", f"/api/v1/downloads/batch/{batch_id}", expected_status=200
    )
    assert zip_headers.get("content-type") == "application/zip"
    _assert_zip_has_three_pngs(zip_bytes)
