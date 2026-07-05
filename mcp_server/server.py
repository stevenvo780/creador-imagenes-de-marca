#!/usr/bin/env python3
"""
Eikón MCP Server — Exposes brand asset generation tools via Model Context Protocol.

This server bridges Claude/LLMs to the Eikón backend API for creating and managing
brand identities and generating marketing assets.

Environment Variables:
- EIKON_BASE_URL (default: https://eikon-633619052458.us-central1.run.app)
- EIKON_API_KEY (required for Authorization header)

Tools exposed:
- eikon_list_brands() → list of brands
- eikon_create_brand(name, palette?, ...) → new brand created
- eikon_logo_options(brand_id, count?) → logo variations
- eikon_set_identity(brand_id, logo_style, logo_seed) → set brand identity
- eikon_list_asset_types() → available asset types with dimensions
- eikon_generate_asset(brand_id, asset_type, content) → generates image (base64 or URL)
- eikon_gallery(brand_id?) → list of generated assets
"""

import json
import os
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
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/brands",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            brands = response.json()
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
        palette: Color palette dict (optional)
        typography: Typography configuration (optional)
        description: Brand description (optional)

    Returns brand creation result with new brand ID.
    """
    async with httpx.AsyncClient() as client:
        payload = {
            "name": name,
        }
        if palette:
            payload["palette"] = palette
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
    List all available asset types with their dimensions.

    Returns asset types grouped by category (logos, cards, og, stationery, banners).
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{EIKON_BASE_URL}/api/v1/asset-types",
                headers=get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            asset_types = response.json()
            return {
                "success": True,
                "asset_types": asset_types,
                "categories": list(set(
                    at.get("category", "other")
                    for at in (asset_types if isinstance(asset_types, list) else [])
                )),
            }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to list asset types: {e!s}",
            }


async def eikon_generate_asset(
    brand_id: str,
    asset_type: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate a brand asset (image).

    Args:
        brand_id: Brand identifier (required)
        asset_type: Asset type ID (e.g., 'lockup_horizontal', 'business_card')
        content: Content dict with optional fields:
            - titulo (title)
            - subtitulo (subtitle)
            - copy (body text)
            - url (URL)
            - image_url (background image URL)
            - custom fields per asset type

    Returns the generated image as base64-encoded PNG or download URL.
    """
    async with httpx.AsyncClient() as client:
        payload = {
            "asset_type": asset_type,
            "content": content,
        }

        try:
            response = await client.post(
                f"{EIKON_BASE_URL}/api/v1/brands/{brand_id}/generate",
                json=payload,
                headers=get_headers(),
                timeout=60.0,  # Generation may take longer
            )
            response.raise_for_status()
            result = response.json()

            # If result contains image_url, return as URL; if base64, keep as-is
            if isinstance(result, dict) and "image_url" in result:
                return {
                    "success": True,
                    "asset": {
                        "type": asset_type,
                        "image_url": result["image_url"],
                        "download_url": result.get("download_url"),
                    },
                    "message": "Asset generated successfully",
                }
            elif isinstance(result, dict) and "image_base64" in result:
                return {
                    "success": True,
                    "asset": {
                        "type": asset_type,
                        "image_base64": result["image_base64"],
                    },
                    "message": "Asset generated successfully",
                }
            else:
                return {
                    "success": True,
                    "asset": result,
                    "message": "Asset generated successfully",
                }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": f"Failed to generate asset: {e!s}",
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
        content: str,
    ) -> str:
        """Generate a brand asset (image). Content is a JSON string with titulo, subtitulo, copy, url, etc."""
        content_dict = json.loads(content)
        result = await eikon_generate_asset(brand_id, asset_type, content_dict)
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
                description="Generate a brand asset (image). Content should include titulo, subtitulo, copy, url, etc.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier"},
                        "asset_type": {"type": "string", "description": "Asset type ID (e.g., lockup_horizontal, business_card)"},
                        "content": {"type": "string", "description": "Content as JSON string (titulo, subtitulo, copy, url, etc.)"},
                    },
                    "required": ["brand_id", "asset_type", "content"],
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
            content = json.loads(arguments["content"])
            result = await eikon_generate_asset(
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
