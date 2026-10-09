#!/usr/bin/env python3
"""
Eikón MCP Server — Exposes brand asset generation tools via Model Context Protocol.

This server bridges Claude/LLMs to the Eikón backend API for creating and managing
brand identities and generating marketing assets via asynchronous batch rendering.

Environment Variables:
- EIKON_BASE_URL (default: https://eikon-633619052458.us-central1.run.app)
- EIKON_API_KEY (required for Authorization header)

Tools exposed:
- eikon_list_brands() → list of brands with IDs and metadata
- eikon_create_brand(name, palette?, ...) → new brand created (validated palette)
- eikon_logo_options(brand_id, count?) → logo variations
- eikon_set_identity(brand_id, logo_style, logo_seed) → set brand identity
- eikon_list_asset_types() → available asset types grouped by category
- eikon_generate_asset(brand_id, asset_type, content?) → async batch generation (polling)
- eikon_generate_and_get(brand_id, asset_type, content?) → full end-to-end: batch → poll → download → return URL
- eikon_gallery(brand_id?) → list of generated assets with URLs
"""

import asyncio
import base64
import importlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, cast

import httpx
from dotenv import load_dotenv
from pydantic import Field

try:
    # Import dinámico: las dos generaciones del SDK tienen módulos distintos.
    FastMCP: Any = importlib.import_module("mcp.server").MCPServer
except (ImportError, AttributeError):
    try:
        FastMCP = importlib.import_module("mcp.server.fastmcp").FastMCP
    except (ImportError, AttributeError):
        FastMCP = None

USE_FASTMCP = FastMCP is not None and os.getenv("EIKON_MCP_LOWLEVEL") != "1"
media_module = importlib.import_module(
    f"{__package__}.media_tools" if __package__ else "media_tools"
)
MediaTools = media_module.MediaTools
failure = media_module.failure

# La firma compartida publica límites y evita coerción bool/string en FastMCP.
Cursor = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
PageLimit = Annotated[int, Field(strict=True, ge=1, le=100)]

# Configuration
load_dotenv()
EIKON_BASE_URL = os.getenv("EIKON_BASE_URL", "https://eikon-633619052458.us-central1.run.app")
EIKON_API_KEY = os.getenv("EIKON_API_KEY", "")

# Valid palette keys accepted by the API
VALID_PALETTE_KEYS = {
    "accent",
    "accent_2",
    "acento",
    "acento_2",
    "background",
    "bg",
    "primario",
    "primary",
    "secondary",
    "text",
    "texto",
}


def get_headers() -> dict[str, str]:
    """Return authorization headers for Eikón API."""
    return {
        "Authorization": f"Bearer {EIKON_API_KEY}",
        "Content-Type": "application/json",
    }


async def eikon_list_brands() -> dict[str, Any]:
    """
    List all brands in the Eikón system.

    Returns a dictionary with brand ID, name, and whether they have a fixed identity.
    The API returns {"items": [...]}, so we extract the items list.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/brands",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            # API response format: {"items": [...]}"
            brands = data.get("items", []) if isinstance(data, dict) else data
            return {
                "success": True,
                "brands": brands,
                "count": len(brands) if isinstance(brands, list) else 0,
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to list brands: {e!s}",
            }


async def eikon_create_brand(
    name: str,
    palette: dict[str, str] | None = None,
    typography: dict[str, Any] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Create a new brand in the Eikón system.

    Args:
        name: Brand name (required)
        palette: Color palette dict (optional). Only these keys are accepted:
                 accent, accent_2, acento, acento_2, background, bg, primario, primary, secondary, text, texto.
                 Invalid keys will be filtered out.
        typography: Typography configuration (optional)
        description: Brand description (optional)

    Returns brand creation result with new brand ID.
    Raises 422 if palette has invalid keys (after filtering, should be valid).
    """
    async with httpx.AsyncClient() as client:
        payload: dict[str, Any] = {
            "name": name,
        }

        # Validate and filter palette
        if palette:
            filtered_palette = {k: v for k, v in palette.items() if k in VALID_PALETTE_KEYS}
            if filtered_palette:
                payload["palette"] = filtered_palette
            # Log warning if any keys were filtered out
            invalid_keys = set(palette.keys()) - VALID_PALETTE_KEYS
            if invalid_keys:
                return {
                    "success": False,
                    "error": f"Invalid palette keys: {invalid_keys}. Valid keys: {VALID_PALETTE_KEYS}",
                }

        if typography:
            payload["typography"] = typography
        if description:
            payload["description"] = description

        try:
            response = await client.post(
                f"{EIKON_BASE_URL}/api/v1/brands",
                json=payload,
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "brand": result,
                "message": f"Brand '{name}' created successfully",
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to create brand: {e!s}",
            }


async def eikon_logo_options(
    brand_id: str,
    count: int | None = None,
) -> dict[str, Any]:
    """
    Get logo variation options for a brand.

    Args:
        brand_id: Brand identifier (required)
        count: Number of variations to return (default: all available)

    Returns list of logo variations with preview URLs.
    """
    async with httpx.AsyncClient() as client:
        params = {}
        if count:
            params["count"] = count

        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/brands/{brand_id}/logo-options",
                headers=get_headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            options = response.json()
            return {
                "success": True,
                "logo_options": options,
                "count": len(options) if isinstance(options, list) else 0,
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to get logo options: {e!s}",
            }


async def eikon_set_identity(
    brand_id: str,
    logo_style: str,
    logo_seed: int | None = None,
) -> dict[str, Any]:
    """
    Set the fixed identity for a brand (logo style and seed).

    Args:
        brand_id: Brand identifier (required)
        logo_style: Logo style identifier (required)
        logo_seed: Seed for logo generation (optional)

    Returns confirmation of identity set.
    """
    async with httpx.AsyncClient() as client:
        payload: dict[str, Any] = {
            "logo_style": logo_style,
        }
        if logo_seed is not None:
            payload["logo_seed"] = logo_seed

        try:
            response = await client.post(
                f"{EIKON_BASE_URL}/api/v1/brands/{brand_id}/set-identity",
                json=payload,
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "brand_id": brand_id,
                "identity": result,
                "message": "Brand identity set successfully",
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to set brand identity: {e!s}",
            }


async def eikon_list_asset_types() -> dict[str, Any]:
    """
    List all available asset types with their dimensions, grouped by family.

    Uses the wizard endpoint which provides better structure for UI:
    families with (id, label, description) and nested types (name, label, width, height).

    Falls back to legacy endpoint if needed.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Try wizard endpoint first (better structure)
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/wizard/asset-types",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Extract families and flatten to a list for easier consumption
            families = data.get("families", [])
            all_types = []
            for family in families:
                for asset_type in family.get("types", []):
                    asset_type["family_id"] = family.get("id")
                    asset_type["family_label"] = family.get("label")
                    all_types.append(asset_type)

            return {
                "success": True,
                "families": families,
                "asset_types": all_types,
                "count": len(all_types),
            }
        except httpx.HTTPError:
            # Fallback: use legacy endpoint
            try:
                response = await client.get(
                    f"{EIKON_BASE_URL}/api/v1/asset-types",
                    headers=get_headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                asset_types = data.get("asset_types", [])
                return {
                    "success": True,
                    "asset_types": asset_types,
                    "count": len(asset_types),
                }
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": f"Failed to list asset types: {e!s}",
                }


async def eikon_generate_asset(
    brand_id: str,
    asset_type: str,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a brand asset asynchronously via batch API (polling required).

    This creates a batch render job and returns the batch ID + status.
    The agent should poll the batch until status == "completed", then fetch variations.

    Args:
        brand_id: Brand identifier (required, must be int or valid string)
        asset_type: Asset type ID (e.g., 'lockup_horizontal', 'ig_post', 'business_card')
        content: Content dict with optional fields (titulo, subtitulo, copy, etc.). Defaults to empty dict.

    Returns batch creation result with batch_id and status for polling.
    """
    async with httpx.AsyncClient() as client:
        # Convert brand_id to int if it's a string
        try:
            brand_id_int = int(brand_id)
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": f"Invalid brand_id: {brand_id}. Must be an integer.",
            }

        payload = {
            "brand_id": brand_id_int,
            "asset_types": [asset_type],
            "count": 1,
            "render_mode": "server",
        }
        if content:
            payload["content"] = content

        try:
            response = await client.post(
                f"{EIKON_BASE_URL}/api/v1/batches",
                json=payload,
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            batch = response.json()

            return {
                "success": True,
                "batch_id": batch.get("id"),
                "status": batch.get("status"),
                "brand_id": batch.get("brand_id"),
                "message": f"Batch {batch.get('id')} created. Status: {batch.get('status')}. Poll /api/v1/batches/{batch.get('id')} for completion.",
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to create batch: {e!s}",
            }


class EikonRequestError(RuntimeError):
    """Error controlado al coordinar una generación remota."""


async def _create_asset_batch(
    client: httpx.AsyncClient,
    brand_id: int,
    asset_type: str,
    content: dict[str, Any] | None,
) -> int | str:
    payload: dict[str, Any] = {
        "brand_id": brand_id,
        "asset_types": [asset_type],
        "count": 1,
        "render_mode": "server",
    }
    if content:
        payload["content"] = content

    try:
        response = await client.post(
            f"{EIKON_BASE_URL}/api/v1/batches",
            json=payload,
            headers=get_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EikonRequestError(f"Failed to create batch: {exc!s}") from exc

    batch = response.json()
    batch_id = batch.get("id") if isinstance(batch, dict) else None
    if not isinstance(batch_id, (int, str)) or not str(batch_id):
        raise EikonRequestError(f"Failed to get batch ID from response: {batch}")
    return batch_id


async def _wait_for_batch(
    client: httpx.AsyncClient,
    batch_id: int | str,
    timeout_seconds: int,
    interval_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status = "pending"

    while time.monotonic() <= deadline:
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/batches/{batch_id}",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EikonRequestError(f"Failed to poll batch {batch_id}: {exc!s}") from exc

        batch_status = response.json()
        last_status = (
            str(batch_status.get("status", "unknown"))
            if isinstance(batch_status, dict)
            else "unknown"
        )
        if last_status == "completed":
            return
        if last_status == "failed":
            raise EikonRequestError(f"Batch {batch_id} failed: {batch_status}")
        await asyncio.sleep(interval_seconds)

    raise EikonRequestError(
        f"Batch {batch_id} did not complete within {timeout_seconds}s. Last status: {last_status}"
    )


async def _get_first_variation(
    client: httpx.AsyncClient,
    batch_id: int | str,
) -> tuple[int | str, str]:
    try:
        response = await client.get(
            f"{EIKON_BASE_URL}/api/v1/batches/{batch_id}/variations",
            headers=get_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EikonRequestError(f"Failed to fetch variations: {exc!s}") from exc

    data = response.json()
    variations = data.get("variations") or data.get("items") if isinstance(data, dict) else None
    if not isinstance(variations, list) or not variations:
        raise EikonRequestError(f"No variations found in batch {batch_id}")

    variation = variations[0]
    if not isinstance(variation, dict):
        raise EikonRequestError(f"Invalid variation data: {variation}")
    variation_id = variation.get("id")
    file_url = variation.get("file_url")
    if (
        not isinstance(variation_id, (int, str))
        or not str(variation_id)
        or not isinstance(file_url, str)
        or not file_url
    ):
        raise EikonRequestError(f"Invalid variation data: {variation}")
    return variation_id, file_url


async def _download_image(
    client: httpx.AsyncClient,
    file_url: str,
) -> tuple[str, str]:
    try:
        response = await client.get(
            f"{EIKON_BASE_URL}{file_url}",
            headers=get_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EikonRequestError(f"Failed to download image: {exc!s}") from exc

    image_url = f"{EIKON_BASE_URL}{file_url}"
    image_base64 = base64.b64encode(response.content).decode("utf-8")
    return image_url, image_base64


async def eikon_generate_and_get(
    brand_id: str,
    asset_type: str,
    content: dict[str, Any] | None = None,
    poll_timeout_seconds: int = 120,
    poll_interval_seconds: int = 3,
) -> dict[str, Any]:
    """Genera un asset end-to-end y devuelve URL y contenido base64."""
    try:
        brand_id_int = int(brand_id)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": f"Invalid brand_id: {brand_id}. Must be an integer.",
        }

    async with httpx.AsyncClient() as client:
        try:
            batch_id = await _create_asset_batch(
                client,
                brand_id_int,
                asset_type,
                content,
            )
            await _wait_for_batch(
                client,
                batch_id,
                poll_timeout_seconds,
                poll_interval_seconds,
            )
            variation_id, file_url = await _get_first_variation(client, batch_id)
            image_url, image_base64 = await _download_image(client, file_url)
        except EikonRequestError as exc:
            return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "batch_id": batch_id,
        "variation_id": variation_id,
        "image_url": image_url,
        "image_base64": image_base64,
        "asset_type": asset_type,
        "message": (
            f"Asset generated successfully. Variation {variation_id} from batch {batch_id}."
        ),
    }


async def eikon_gallery(
    brand_id: str | None = None,
) -> dict[str, Any]:
    """
    List all generated assets (gallery).

    Args:
        brand_id: Optional brand ID to filter by. If omitted, returns all assets.

    Returns list of generated assets with metadata and download URLs.
    """
    async with httpx.AsyncClient() as client:
        endpoint = (
            f"{EIKON_BASE_URL}/api/v1/brands/{brand_id}/gallery"
            if brand_id
            else f"{EIKON_BASE_URL}/api/v1/gallery"
        )

        try:
            response = await client.get(
                endpoint,
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            assets = response.json()

            asset_list = assets if isinstance(assets, list) else []
            return {
                "success": True,
                "assets": assets,
                "count": len(asset_list),
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to fetch gallery: {e!s}",
            }


async def eikon_list_projects(
    cursor: Cursor | None = None, limit: PageLimit | None = None
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).list_projects(cursor, limit)


async def eikon_create_project(name: str, slug: str, description: str = "") -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).create_project(
            name, slug, description
        )


async def eikon_get_brand_brief(brand_id: int) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).get_brand_brief(brand_id)


async def eikon_create_generation_brief(
    brand_id: int, prompt: str, width: int, height: int
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).create_generation_brief(
            brand_id, prompt, width, height
        )


async def eikon_import_image(
    brief_id: int, file_path: str, idempotency_key: str, provenance: dict[str, Any] | None = None
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).import_image(
            brief_id, file_path, idempotency_key, provenance
        )


async def eikon_list_media(
    project_id: int | None = None,
    brand_id: int | None = None,
    status: str | None = None,
    cursor: Cursor | None = None,
    limit: PageLimit | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await MediaTools(EIKON_BASE_URL, EIKON_API_KEY, client).list_media(
            project_id, brand_id, status, cursor, limit
        )


async def eikon_list_brands_tool() -> str:
    """List all brands in the Eikón system (id, name, has_fixed_identity)."""
    result = await eikon_list_brands()
    return json.dumps(result, indent=2)


async def eikon_create_brand_tool(
    name: str,
    palette: str | None = None,
    typography: str | None = None,
    description: str | None = None,
) -> str:
    """Create a new brand. Palette and typography are JSON strings."""
    palette_dict = json.loads(palette) if palette else None
    typography_dict = json.loads(typography) if typography else None
    result = await eikon_create_brand(
        name=name,
        palette=palette_dict,
        typography=typography_dict,
        description=description,
    )
    return json.dumps(result, indent=2)


async def eikon_logo_options_tool(
    brand_id: str,
    count: int | None = None,
) -> str:
    """Get logo variation options for a brand."""
    result = await eikon_logo_options(brand_id, count)
    return json.dumps(result, indent=2)


async def eikon_set_identity_tool(
    brand_id: str,
    logo_style: str,
    logo_seed: int | None = None,
) -> str:
    """Set the fixed identity (logo style and seed) for a brand."""
    result = await eikon_set_identity(brand_id, logo_style, logo_seed)
    return json.dumps(result, indent=2)


async def eikon_list_asset_types_tool() -> str:
    """List all available asset types with dimensions (redes/web/anuncios/impresión)."""
    result = await eikon_list_asset_types()
    return json.dumps(result, indent=2)


async def eikon_generate_asset_tool(
    brand_id: str,
    asset_type: str,
    content: str | None = None,
) -> str:
    """Generate a brand asset via async batch API. Returns batch_id for polling. Content is optional JSON string."""
    content_dict = json.loads(content) if content else None
    result = await eikon_generate_asset(brand_id, asset_type, content_dict)
    return json.dumps(result, indent=2)


async def eikon_generate_and_get_tool(
    brand_id: str,
    asset_type: str,
    content: str | None = None,
) -> str:
    """Generate a brand asset end-to-end (batch → poll → download → return URL + base64). One call does it all."""
    content_dict = json.loads(content) if content else None
    result = await eikon_generate_and_get(brand_id, asset_type, content_dict)
    return json.dumps(result, indent=2)


async def eikon_gallery_tool(brand_id: str | None = None) -> str:
    """List all generated assets (gallery). Optionally filter by brand_id."""
    result = await eikon_gallery(brand_id)
    return json.dumps(result, indent=2)


async def eikon_list_projects_tool(
    cursor: Cursor | None = None, limit: PageLimit | None = None
) -> str:
    """Lista proyectos privados con projects:read."""
    return json.dumps(await eikon_list_projects(cursor, limit))


async def eikon_create_project_tool(name: str, slug: str, description: str = "") -> str:
    """Crea un proyecto con projects:write."""
    return json.dumps(await eikon_create_project(name, slug, description))


async def eikon_get_brand_brief_tool(brand_id: int) -> str:
    """Obtiene el kit de marca y referencias originales con brands:read."""
    return json.dumps(await eikon_get_brand_brief(brand_id))


async def eikon_create_generation_brief_tool(
    brand_id: int, prompt: str, width: int, height: int
) -> str:
    """Crea un encargo inmutable con briefs:write; genera la imagen en el cliente."""
    return json.dumps(await eikon_create_generation_brief(brand_id, prompt, width, height))


async def eikon_import_image_tool(
    brief_id: int, file_path: str, idempotency_key: str, provenance: dict[str, Any] | None = None
) -> str:
    """Lee un PNG/JPEG explícito en el equipo del cliente MCP y sube bytes con media:write. Requiere revisión humana."""
    return json.dumps(await eikon_import_image(brief_id, file_path, idempotency_key, provenance))


async def eikon_list_media_tool(
    project_id: int | None = None,
    brand_id: int | None = None,
    status: str | None = None,
    cursor: Cursor | None = None,
    limit: PageLimit | None = None,
) -> str:
    """Lista medios privados y estado efectivo con media:read; descarga autenticada."""
    return json.dumps(await eikon_list_media(project_id, brand_id, status, cursor, limit))


# Un registro compartido evita divergencias entre alto nivel y fallback.
_OLD_HANDLERS: list[Callable[..., Awaitable[str]]] = [
    eikon_list_brands_tool,
    eikon_create_brand_tool,
    eikon_logo_options_tool,
    eikon_set_identity_tool,
    eikon_list_asset_types_tool,
    eikon_generate_asset_tool,
    eikon_generate_and_get_tool,
    eikon_gallery_tool,
]
_NEW_HANDLERS: list[Callable[..., Awaitable[str]]] = [
    eikon_list_projects_tool,
    eikon_create_project_tool,
    eikon_get_brand_brief_tool,
    eikon_create_generation_brief_tool,
    eikon_import_image_tool,
    eikon_list_media_tool,
]
_HANDLERS = {
    function.__name__.removesuffix("_tool"): function for function in _OLD_HANDLERS + _NEW_HANDLERS
}
# FastMCP anterior publicaba también estos nombres; preservar sus clientes.
_HANDLERS.update({function.__name__: function for function in _OLD_HANDLERS})


if USE_FASTMCP:
    mcp = FastMCP("Eikón")
    for tool_name, handler in _HANDLERS.items():
        mcp.tool(name=tool_name)(handler)
else:
    import inspect

    from mcp.server import Server
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
    from pydantic import create_model

    async def list_tools() -> list[Any]:
        result = []
        for name, function in _HANDLERS.items():
            fields: dict[str, Any] = {
                param.name: (
                    param.annotation,
                    ... if param.default is inspect.Parameter.empty else param.default,
                )
                for param in inspect.signature(function).parameters.values()
            }
            schema = create_model(name + "Arguments", **fields).model_json_schema()
            # SDK v2 usa snake_case; v1 conserva inputSchema.
            schema_key = "input_schema" if "input_schema" in Tool.model_fields else "inputSchema"
            result.append(
                Tool(name=name, description=function.__doc__ or name, **{schema_key: schema})
            )
        return result

    async def call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
        handler = _HANDLERS.get(name)
        if handler is None:
            result = json.dumps(failure("unknown_tool", "Herramienta desconocida."))
        else:
            try:
                result = await handler(**arguments)
            except (ValueError, TypeError, KeyError):
                result = json.dumps(failure("invalid_request", "Argumentos inválidos."))
        return [TextContent(type="text", text=result)]

    if hasattr(Server, "list_tools"):
        server = Server("Eikón")
        cast(Any, server).list_tools()(list_tools)
        cast(Any, server).call_tool()(call_tool)
    else:

        async def _on_list_tools(context: Any, params: Any) -> Any:
            return ListToolsResult(tools=await list_tools())

        async def _on_call_tool(context: Any, params: Any) -> Any:
            return CallToolResult(content=await call_tool(params.name, params.arguments or {}))

        server = Server("Eikón", on_list_tools=_on_list_tools, on_call_tool=_on_call_tool)


if __name__ == "__main__":
    if USE_FASTMCP:
        mcp.run()
    else:

        async def main() -> None:
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        asyncio.run(main())
