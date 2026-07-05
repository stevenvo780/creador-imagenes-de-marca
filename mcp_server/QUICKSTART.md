# Eikón MCP Server — Quick Start

## 1. First-time setup (5 min)

```bash
cd /workspace/Pinakotheke/eikon/mcp_server

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
cp .env.example .env
nano .env  # Edit with your EIKON_API_KEY
```

## 2. Test the server locally

```bash
# Activate venv
source venv/bin/activate

# Run smoke test
python3 << 'EOF'
from server import eikon_list_brands
import asyncio
result = asyncio.run(eikon_list_brands())
print(result)
EOF
```

Expected output (if backend is running):
```json
{
  "success": true,
  "brands": [...],
  "count": N
}
```

Or (if backend is not available):
```json
{
  "success": false,
  "error": "Failed to list brands: ..."
}
```

## 3. Configure in Claude Desktop

Edit `~/.config/Claude/claude_desktop_config.json` (Linux) or equivalent:

```json
{
  "mcpServers": {
    "eikon": {
      "command": "python3",
      "args": ["/workspace/Pinakotheke/eikon/mcp_server/server.py"],
      "env": {
        "EIKON_BASE_URL": "https://eikon-633619052458.us-central1.run.app",
        "EIKON_API_KEY": "your-key-here"
      }
    }
  }
}
```

Then restart Claude Desktop.

## 4. Try in Claude

Once configured, you should see `eikon` tools available. Example prompt:

```
I want to create a brand called "TechCorp" and generate business cards for it.

Steps:
1. Create the brand
2. Show me available logo styles
3. Set one as the identity
4. Generate a business card asset
```

Claude will use the eikon tools to accomplish this.

## 5. Verify tools are available

In Claude Desktop or Claude Code, you should see these tools listed:
- `eikon_list_brands`
- `eikon_create_brand`
- `eikon_logo_options`
- `eikon_set_identity`
- `eikon_list_asset_types`
- `eikon_generate_asset`
- `eikon_gallery`

## Troubleshooting

### "Command not found: python3"
Use full path: `/usr/bin/python3` or set `PATH` correctly.

### "ModuleNotFoundError: mcp"
Ensure you activated the venv:
```bash
source /workspace/Pinakotheke/eikon/mcp_server/venv/bin/activate
```

### "Connection refused" when calling tools
Backend may not be running. Check:
```bash
curl -H "Authorization: Bearer $EIKON_API_KEY" \
  https://eikon-633619052458.us-central1.run.app/api/v1/brands
```

### Tools don't appear in Claude
1. Restart Claude Desktop completely
2. Check config file syntax (valid JSON)
3. Verify venv path exists
4. Check logs: `tail -f ~/.claude/logs` or similar

## File Structure

```
mcp_server/
├── server.py              # Main MCP server (FastMCP)
├── requirements.txt       # Python dependencies
├── .env.example           # Config template (COPY to .env)
├── .env                   # Your config (git-ignored, never commit)
├── README.md              # Full documentation
├── QUICKSTART.md          # This file
└── venv/                  # Python virtual environment (git-ignored)
```

## Next Steps

1. **Create a brand**: Ask Claude to create a new brand with colors
2. **Generate assets**: Request business cards, social headers, OG images
3. **View gallery**: Ask Claude to list all generated assets for a brand
4. **Set identity**: Lock in a logo style and seed for consistency

## Security Reminder

- ⚠️ Never commit `.env` file (contains API key)
- ⚠️ Rotate keys regularly
- ⚠️ MCP server is local-only (stdio transport, no network exposure)

---

**Need help?** Check `README.md` for full documentation or the parent Eikón project.
