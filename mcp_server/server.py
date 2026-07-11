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

import json
import os
import asyncio
import time
import base64
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
    USE_FASTMCP = True
except ImportError:
    from mcp.server import Server
    from mcp.types import (
        TextContent,
        Tool,
    )
    USE_FASTMCP = False

import httpx
from dotenv import load_dotenv

# Configuration
load_dotenv()
EIKON_BASE_URL = os.getenv(
    "EIKON_BASE_URL",
    "https://eikon-633619052458.us-central1.run.app"
)
EIKON_API_KEY = os.getenv("EIKON_API_KEY", "")

# Valid palette keys accepted by the API
VALID_PALETTE_KEYS = {
    'accent', 'accent_2',
    'acento', 'acento_2',
    'background', 'bg',
    'primario', 'primary',
    'secondary',
    'text', 'texto'
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
        payload = {
            "name": name,
        }

        # Validate and filter palette
        if palette:
            filtered_palette = {
                k: v for k, v in palette.items()
                if k in VALID_PALETTE_KEYS
            }
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
        payload = {
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


async def eikon_generate_and_get(
    brand_id: str,
    asset_type: str,
    content: dict[str, Any] | None = None,
    poll_timeout_seconds: int = 120,
    poll_interval_seconds: int = 3,
) -> dict[str, Any]:
    """
    Generate a brand asset end-to-end: create batch → poll for completion → fetch variations → download image.

    This is the convenience function for agents: one call does everything and returns the image URL + base64.

    Args:
        brand_id: Brand identifier (required, must be int or valid string)
        asset_type: Asset type ID (e.g., 'lockup_horizontal', 'ig_post', 'business_card')
        content: Content dict with optional fields (titulo, subtitulo, copy, etc.). Defaults to empty dict.
        poll_timeout_seconds: Max seconds to wait for batch completion (default 120)
        poll_interval_seconds: Seconds between polls (default 3)

    Returns:
        On success: {
            "success": true,
            "batch_id": <int>,
            "variation_id": <int>,
            "image_url": "<absolute_url>",
            "image_base64": "<base64_png>",
            "asset_type": "<type>",
            "message": "..."
        }
        On failure: {"success": false, "error": "..."}
    """
    async with httpx.AsyncClient() as client:
        # Convert brand_id to int
        try:
            brand_id_int = int(brand_id)
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": f"Invalid brand_id: {brand_id}. Must be an integer.",
            }

        # Step 1: Create batch
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
            batch_id = batch.get("id")

            if not batch_id:
                return {
                    "success": False,
                    "error": f"Failed to get batch ID from response: {batch}",
                }

        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to create batch: {e!s}",
            }

        # Step 2: Poll for completion
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > poll_timeout_seconds:
                return {
                    "success": False,
                    "error": f"Batch {batch_id} did not complete within {poll_timeout_seconds}s. Last status: running",
                }

            try:
                response = await client.get(
                    f"{EIKON_BASE_URL}/api/v1/batches/{batch_id}",
                    headers=get_headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                batch_status = response.json()
                status = batch_status.get("status")

                if status == "completed":
                    break
                elif status == "failed":
                    return {
                        "success": False,
                        "error": f"Batch {batch_id} failed: {batch_status}",
                    }
                else:
                    # Status is "pending" or "running"; wait and retry
                    await asyncio.sleep(poll_interval_seconds)

            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": f"Failed to poll batch {batch_id}: {e!s}",
                }

        # Step 3: Fetch variations
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/batches/{batch_id}/variations",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            variations_data = response.json()

            # Extract variations list (API returns {"variations": [...], "items": [...]})
            variations = variations_data.get("variations", [])
            if not variations:
                variations = variations_data.get("items", [])

            if not variations:
                return {
                    "success": False,
                    "error": f"No variations found in batch {batch_id}",
                }

            variation = variations[0]
            variation_id = variation.get("id")
            file_url = variation.get("file_url")

            if not variation_id or not file_url:
                return {
                    "success": False,
                    "error": f"Invalid variation data: {variation}",
                }

        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to fetch variations: {e!s}",
            }

        # Step 4: Download image file
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}{file_url}",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            image_bytes = response.content

            # Encode to base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Construct absolute URL
            image_url = f"{EIKON_BASE_URL}{file_url}"

            return {
                "success": True,
                "batch_id": batch_id,
                "variation_id": variation_id,
                "image_url": image_url,
                "image_base64": image_base64,
                "asset_type": asset_type,
                "message": f"Asset generated successfully. Variation {variation_id} from batch {batch_id}.",
            }

        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to download image: {e!s}",
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


# Initialize MCP Server
if USE_FASTMCP:
    mcp = FastMCP("Eikón")

    @mcp.tool()
    async def eikon_list_brands_tool() -> str:
        """List all brands in the Eikón system (id, name, has_fixed_identity)."""
        result = await eikon_list_brands()
        return json.dumps(result, indent=2)

    @mcp.tool()
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

    @mcp.tool()
    async def eikon_logo_options_tool(
        brand_id: str,
        count: int | None = None,
    ) -> str:
        """Get logo variation options for a brand."""
        result = await eikon_logo_options(brand_id, count)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def eikon_set_identity_tool(
        brand_id: str,
        logo_style: str,
        logo_seed: int | None = None,
    ) -> str:
        """Set the fixed identity (logo style and seed) for a brand."""
        result = await eikon_set_identity(brand_id, logo_style, logo_seed)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def eikon_list_asset_types_tool() -> str:
        """List all available asset types with dimensions (redes/web/anuncios/impresión)."""
        result = await eikon_list_asset_types()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def eikon_generate_asset_tool(
        brand_id: str,
        asset_type: str,
        content: str | None = None,
    ) -> str:
        """Generate a brand asset via async batch API. Returns batch_id for polling. Content is optional JSON string."""
        content_dict = json.loads(content) if content else None
        result = await eikon_generate_asset(brand_id, asset_type, content_dict)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def eikon_generate_and_get_tool(
        brand_id: str,
        asset_type: str,
        content: str | None = None,
    ) -> str:
        """Generate a brand asset end-to-end (batch → poll → download → return URL + base64). One call does it all."""
        content_dict = json.loads(content) if content else None
        result = await eikon_generate_and_get(brand_id, asset_type, content_dict)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def eikon_gallery_tool(brand_id: str | None = None) -> str:
        """List all generated assets (gallery). Optionally filter by brand_id."""
        result = await eikon_gallery(brand_id)
        return json.dumps(result, indent=2)

else:
    # Fallback: use mcp.Server directly (if FastMCP not available)
    server = Server("Eikón")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="eikon_list_brands",
                description="List all brands in the Eikón system (id, name, has_fixed_identity)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="eikon_create_brand",
                description="Create a new brand",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Brand name"},
                        "palette": {"type": "string", "description": "Color palette (JSON string)"},
                        "typography": {"type": "string", "description": "Typography config (JSON string)"},
                        "description": {"type": "string", "description": "Brand description"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="eikon_logo_options",
                description="Get logo variation options for a brand",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier"},
                        "count": {"type": "integer", "description": "Number of variations to return"},
                    },
                    "required": ["brand_id"],
                },
            ),
            Tool(
                name="eikon_set_identity",
                description="Set the fixed identity (logo style and seed) for a brand",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier"},
                        "logo_style": {"type": "string", "description": "Logo style ID"},
                        "logo_seed": {"type": "integer", "description": "Logo generation seed"},
                    },
                    "required": ["brand_id", "logo_style"],
                },
            ),
            Tool(
                name="eikon_list_asset_types",
                description="List all available asset types with dimensions (redes/web/anuncios/impresión)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="eikon_generate_asset",
                description="Generate a brand asset via async batch API. Returns batch_id for polling. Use eikon_generate_and_get for one-call convenience.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier (int or string)"},
                        "asset_type": {"type": "string", "description": "Asset type ID (e.g., lockup_horizontal, ig_post, business_card)"},
                        "content": {"type": "string", "description": "Content as JSON string (titulo, subtitulo, copy, url, etc., optional)"},
                    },
                    "required": ["brand_id", "asset_type"],
                },
            ),
            Tool(
                name="eikon_generate_and_get",
                description="Generate a brand asset end-to-end: batch → poll → download → return image URL + base64. One call completes the full cycle.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier (int or string)"},
                        "asset_type": {"type": "string", "description": "Asset type ID (e.g., lockup_horizontal, ig_post, business_card)"},
                        "content": {"type": "string", "description": "Content as JSON string (titulo, subtitulo, copy, url, etc., optional)"},
                    },
                    "required": ["brand_id", "asset_type"],
                },
            ),
            Tool(
                name="eikon_gallery",
                description="List all generated assets (gallery). Optionally filter by brand_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand ID (optional)"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "eikon_list_brands":
            result = await eikon_list_brands()
        elif name == "eikon_create_brand":
            palette = json.loads(arguments.get("palette", "{}")) if arguments.get("palette") else None
            typography = json.loads(arguments.get("typography", "{}")) if arguments.get("typography") else None
            result = await eikon_create_brand(
                name=arguments["name"],
                palette=palette,
                typography=typography,
                description=arguments.get("description"),
            )
        elif name == "eikon_logo_options":
            result = await eikon_logo_options(
                brand_id=arguments["brand_id"],
                count=arguments.get("count"),
            )
        elif name == "eikon_set_identity":
            result = await eikon_set_identity(
                brand_id=arguments["brand_id"],
                logo_style=arguments["logo_style"],
                logo_seed=arguments.get("logo_seed"),
            )
        elif name == "eikon_list_asset_types":
            result = await eikon_list_asset_types()
        elif name == "eikon_generate_asset":
            content = json.loads(arguments.get("content", "{}")) if arguments.get("content") else None
            result = await eikon_generate_asset(
                brand_id=arguments["brand_id"],
                asset_type=arguments["asset_type"],
                content=content,
            )
        elif name == "eikon_generate_and_get":
            content = json.loads(arguments.get("content", "{}")) if arguments.get("content") else None
            result = await eikon_generate_and_get(
                brand_id=arguments["brand_id"],
                asset_type=arguments["asset_type"],
                content=content,
            )
        elif name == "eikon_gallery":
            result = await eikon_gallery(
                brand_id=arguments.get("brand_id"),
            )
        else:
            return TextContent(type="text", text=f"Unknown tool: {name}")

        return TextContent(type="text", text=json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio

    if USE_FASTMCP:
        # FastMCP runs via CLI
        mcp.run()
    else:
        # Standard mcp.Server with stdio transport
        import logging
        logging.basicConfig(level=logging.INFO)

        async def main():
            from mcp.server.stdio import stdio_server
            async with stdio_server(server) as streams:
                await streams.wait_closed()

        asyncio.run(main())
