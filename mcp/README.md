# embed-mcp

A small [Model Context Protocol](https://modelcontextprotocol.io) server that
exposes an [EMBEd](../README.md) vault as tools for any MCP-aware LLM client
(Claude Desktop, Claude Code, etc.).

It is a thin proxy: each MCP tool makes an HTTP call against a running EMBEd
backend (default `http://localhost:8000`).

## Tools

| Tool              | Calls                  | Returns                                                          |
|-------------------|------------------------|------------------------------------------------------------------|
| `list_vaults`     | `GET  /api/stores`     | `{name, file_count, description, has_api_key}` per vault         |
| `search_vault`    | `POST /api/search`     | `{text, source_file, similarity, modality, file_url, page_numbers?}` |
| `embed_into_vault`| `POST /api/embed`      | `{doc_id, chunk_count, vault}`                                   |
| `health`          | `GET  /api/health`     | Backend health JSON                                              |

## Install

```bash
# editable install into an existing Python env
pip install -e mcp/

# or, run via uvx without installing
uvx --from /absolute/path/to/EMBEd/mcp embed-mcp
```

The server runs over stdio (standard for MCP). Start it manually with:

```bash
embed-mcp
```

## Configure API keys

`embed-mcp` reads per-vault API keys from a JSON file at:

```
$HOME/.config/embed-mcp/keys.json
```

Shape:

```json
{
  "admin":    "sk-embed-ADMIN-KEY",
  "smoketest": "sk-embed-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "research-notes": "sk-embed-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
}
```

Create it the first time:

```bash
mkdir -p "$HOME/.config/embed-mcp"
cat > "$HOME/.config/embed-mcp/keys.json" <<'EOF'
{
  "smoketest": "sk-embed-REPLACE-ME"
}
EOF
chmod 600 "$HOME/.config/embed-mcp/keys.json"
```

Each EMBEd vault gets a single-use API key returned by `POST /api/stores`. Save
that key into `keys.json` under the vault name. The optional `"admin"` entry
unlocks admin-only tools like `list_vaults` when the backend has
`ADMIN_API_KEY` set.

### Environment overrides

| Variable          | Default                                  |
|-------------------|------------------------------------------|
| `EMBED_BASE_URL`  | `http://localhost:8000`                  |
| `EMBED_TIMEOUT`   | `30` (seconds)                           |
| `EMBED_MCP_KEYS`  | `$HOME/.config/embed-mcp/keys.json`      |

## Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
and add an entry under `mcpServers`:

```json
{
  "mcpServers": {
    "embed": {
      "command": "uvx",
      "args": ["--from", "/absolute/path/to/EMBEd/mcp", "embed-mcp"],
      "env": {
        "EMBED_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

Or, if you `pip install -e mcp/` into a specific Python:

```json
{
  "mcpServers": {
    "embed": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "embed_mcp.server"]
    }
  }
}
```

Restart Claude Desktop to pick up the change.

## Wire into Claude Code

Easiest:

```bash
claude mcp add embed -- uvx --from /absolute/path/to/EMBEd/mcp embed-mcp
```

Or commit `.claude/mcp.json` to your repo:

```json
{
  "mcpServers": {
    "embed": {
      "command": "uvx",
      "args": ["--from", "/absolute/path/to/EMBEd/mcp", "embed-mcp"]
    }
  }
}
```

## Verify

Run the integration test from the repo root with a backend already up:

```bash
python test_integration.py
```

It exercises curl, python, and MCP paths end-to-end against a fresh
test vault.
