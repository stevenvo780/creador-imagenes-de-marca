# Eikón MCP Server

A Model Context Protocol (MCP) server for the Eikón brand asset generation engine. Exposes brand management and asset generation as tools for Claude, Claude Code, Cursor, and other LLMs.

## What is this?

This server bridges LLMs to the Eikón REST API, allowing them to:
- **List brands** in the Eikón system
- **Create new brands** with custom palettes and typography
- **Explore logo variations** and select identities
- **Generate brand assets** (business cards, social headers, OG images, letterheads, etc.)
- **Browse generated asset galleries**

Think of it as giving Claude a toolbelt for brand design automation.

## Installation

### Prerequisites

- Python 3.9+
- Access to Eikón API (backend running at `https://eikon-633619052458.us-central1.run.app` or custom `EIKON_BASE_URL`)
- Valid `EIKON_API_KEY` for authentication

### Setup

1. Create a Python virtual environment:
   ```bash
   cd /workspace/Pinakotheke/eikon/mcp_server
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file (or set environment variables):
   ```bash
   cat > .env << 'EOF'
   EIKON_BASE_URL=https://eikon-633619052458.us-central1.run.app
   EIKON_API_KEY=your-api-key-here
   EOF
   chmod 600 .env
   ```

   **Get your API key:**
   - Endpoint: `POST /api/v1/auth/get-api-key`
   - Or contact your Eikón admin

4. Test the server (smoke test):
   ```bash
   python3 server.py --help
   # or
   python3 -c "from server import eikon_list_brands; import asyncio; print(asyncio.run(eikon_list_brands()))"
   ```

## Configuration in Claude Desktop or Code

### Claude Desktop (macOS/Windows/Linux)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or equivalent on your OS:

```json
{
  "mcpServers": {
    "eikon": {
      "command": "python3",
      "args": [
        "/workspace/Pinakotheke/eikon/mcp_server/server.py"
      ],
      "env": {
        "EIKON_BASE_URL": "https://eikon-633619052458.us-central1.run.app",
        "EIKON_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Claude Code

Add to `.claude/settings.json` in your project:

```json
{
  "mcpServers": {
    "eikon": {
      "command": "python3",
      "args": [
        "/workspace/Pinakotheke/eikon/mcp_server/server.py"
      ],
      "env": {
        "EIKON_BASE_URL": "https://eikon-633619052458.us-central1.run.app",
        "EIKON_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Cursor (VSCode-like)

Similar to Claude Code — add the config to `.cursor/settings.json` or your workspace MCP settings.

## Tools Available

### 1. `eikon_list_brands()`
List all brands in the system.

**Returns:**
```json
{
  "success": true,
  "brands": [
    {"id": "pinakotheke-kosmos", "name": "Kósmos", "has_fixed_identity": true},
    {"id": "prizma-iris", "name": "Iris", "has_fixed_identity": false}
  ],
  "count": 2
}
```

### 2. `eikon_create_brand(name, palette?, typography?, description?)`
Create a new brand.

**Arguments:**
- `name` (string, required): Brand name
- `palette` (JSON string, optional): Color palette (e.g., `{"primary": "#FF5733", "secondary": "#33FF57"}`)
- `typography` (JSON string, optional): Font config
- `description` (string, optional): Brand description

**Returns:**
```json
{
  "success": true,
  "brand": {"id": "brand-123", "name": "My Brand"},
  "message": "Brand 'My Brand' created successfully"
}
```

### 3. `eikon_logo_options(brand_id, count?)`
Get logo variation options for a brand.

**Arguments:**
- `brand_id` (string, required): Brand identifier
- `count` (integer, optional): Number of variations (default: all)

**Returns:**
```json
{
  "success": true,
  "logo_options": [
    {"style_id": "modern", "preview_url": "...", "seed": 42},
    {"style_id": "minimal", "preview_url": "...", "seed": 43}
  ],
  "count": 2
}
```

### 4. `eikon_set_identity(brand_id, logo_style, logo_seed?)`
Lock in a brand's logo and identity.

**Arguments:**
- `brand_id` (string, required): Brand identifier
- `logo_style` (string, required): Logo style ID (from `logo_options`)
- `logo_seed` (integer, optional): Seed for deterministic generation

**Returns:**
```json
{
  "success": true,
  "brand_id": "brand-123",
  "identity": {"logo_style": "modern", "logo_seed": 42},
  "message": "Brand identity set successfully"
}
```

### 5. `eikon_list_asset_types()`
List all available asset types with dimensions.

**Returns:**
```json
{
  "success": true,
  "asset_types": [
    {
      "id": "lockup_horizontal",
      "category": "logos",
      "width": 1200,
      "height": 400,
      "description": "Horizontal logo lockup for web"
    },
    {
      "id": "business_card",
      "category": "cards",
      "width": 1012,
      "height": 636,
      "description": "Standard business card"
    }
  ],
  "categories": ["logos", "cards", "og", "stationery", "banners"]
}
```

### 6. `eikon_generate_asset(brand_id, asset_type, content)`
Generate a brand asset (image).

**Arguments:**
- `brand_id` (string, required): Brand identifier
- `asset_type` (string, required): Asset type ID (e.g., `lockup_horizontal`, `business_card`)
- `content` (JSON string, required): Content dict with optional fields:
  - `titulo` (title)
  - `subtitulo` (subtitle)
  - `copy` (body text)
  - `url` (website URL)
  - `image_url` (background image)
  - Other fields per asset type

**Example:**
```json
{
  "brand_id": "pinakotheke-kosmos",
  "asset_type": "business_card",
  "content": "{\"titulo\": \"Dr. Jane Smith\", \"copy\": \"Cosmologist\", \"url\": \"https://example.com\"}"
}
```

**Returns:**
```json
{
  "success": true,
  "asset": {
    "type": "business_card",
    "image_url": "https://eikon.../output/business_card_123.png",
    "download_url": "https://eikon.../download/123"
  },
  "message": "Asset generated successfully"
}
```

### 7. `eikon_gallery(brand_id?)`
List all generated assets.

**Arguments:**
- `brand_id` (string, optional): Filter by brand ID

**Returns:**
```json
{
  "success": true,
  "assets": [
    {
      "id": "asset-1",
      "brand_id": "pinakotheke-kosmos",
      "asset_type": "lockup_horizontal",
      "image_url": "...",
      "created_at": "2026-07-03T14:22:00Z"
    }
  ],
  "count": 42
}
```

## Example Usage

### In Claude Desktop (Chat)

```
You: Can you create a brand called "TechNova" and generate a business card for it?

Claude will:
1. Call eikon_create_brand("TechNova", ...)
2. Call eikon_logo_options("technova", 3)
3. Ask which logo you prefer
4. Call eikon_set_identity("technova", "modern", 42)
5. Call eikon_generate_asset("technova", "business_card", {...})
6. Return the generated image URL or base64
```

### In Code/Prompt (Programmatic)

```python
# Pseudocode showing how an agent might use this
brand_id = await eikon_create_brand("MyBrand")
options = await eikon_logo_options(brand_id, count=5)
# User picks option 2
await eikon_set_identity(brand_id, logo_style=options[2]["style_id"])
assets = []
for asset_type in ["lockup_horizontal", "business_card", "og_general"]:
    asset = await eikon_generate_asset(brand_id, asset_type, {
        "titulo": "My Brand",
        "url": "https://mybrand.com"
    })
    assets.append(asset)
```

## Architecture

- **`server.py`**: Main MCP server using FastMCP or mcp SDK (stdio transport)
- **`requirements.txt`**: Dependencies (mcp, httpx, python-dotenv)
- **`.env`**: Environment configuration (git-ignored)

The server runs as a subprocess and communicates with the client (Claude, etc.) via stdio (JSON-RPC 2.0).

## Troubleshooting

### "Connection refused" / "Cannot reach backend"
- Verify `EIKON_BASE_URL` is correct and the backend is running
- Check network connectivity: `curl -H "Authorization: Bearer $EIKON_API_KEY" $EIKON_BASE_URL/api/v1/brands`

### "Unauthorized" (401)
- Check `EIKON_API_KEY` is valid
- Verify it's passed in the `Authorization: Bearer` header

### "Tool not found"
- Ensure the MCP server is registered in Claude Desktop/Code config
- Restart the client after adding the config
- Check logs: `tail -f ~/.claude/logs` or similar

### venv activation fails
```bash
python3 -m venv venv --upgrade-deps
source venv/bin/activate
```

## Development

### Running tests
```bash
# Smoke test (requires backend running)
python3 -m pytest tests/ -v

# Or manually:
python3 -c "
from server import eikon_list_brands
import asyncio
result = asyncio.run(eikon_list_brands())
print(result)
"
```

### Code quality
```bash
# Format
black server.py

# Lint
ruff check server.py
ruff check server.py --fix

# Type check
mypy server.py
```

## Security

- **Never commit `.env`** — it contains `EIKON_API_KEY`
- Use environment variables in production, not files
- Rotate API keys regularly
- MCP server is local-only (stdio) — no network listener exposed

## License

Part of Eikón / Pinakotheke ecosystem. See parent repo for license.

## Support

For issues or feature requests:
- Check Eikón backend logs: `gcloud logging read "..."`
- Review API responses for error codes
- File an issue in the Pinakotheke repo

---

**Last updated:** 2026-07-05
