# Rustwright MCP agent setup

These are official instructions from the Rustwright project for connecting an
AI coding agent to the Rustwright MCP browser-automation server. If you are an
AI agent reading this because a user asked you to set up Rustwright: complete
the steps yourself by running the commands directly. Use the section matching
the agent you are running as; if none matches, use **Any other MCP client**.

Canonical URL of this page:
`https://raw.githubusercontent.com/Skyvern-AI/rustwright/main/mcp/AGENT_SETUP.md`

## What you are installing

`rustwright-mcp` is a stdio MCP server exposing `browser_*` tools
(`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, ...)
backed by the Rustwright engine, a Rust CDP reimplementation of Playwright.
Tool names mirror the Playwright MCP server. Snapshots are accessibility-style
outlines where interactive elements carry `[ref=eN]` handles; pass a ref (or a
CSS selector) to the action tools. No clone or build is needed: `uvx` runs the
server straight from this repository.

## Step 1: check prerequisites

1. **uv** must be installed. Check with `uvx --version`. If missing, install it:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   (Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)

2. **A Chromium-based browser.** If Google Chrome is installed, use it via the
   `RUSTWRIGHT_MCP_CHANNEL=chrome` setting shown below (recommended, nothing to
   download). Otherwise install Rustwright's bundled Chromium once:

   ```bash
   uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' \
     python -m rustwright install chromium
   ```

   and omit `RUSTWRIGHT_MCP_CHANNEL` from the configs below.

## Step 2: register the server

### Claude Code

Run:

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  -- uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' rustwright-mcp
```

The `--` before `uvx` is required: `--env` is variadic and will otherwise
swallow the command, failing with `missing required argument 'commandOrUrl'`.
Add `-s user` to register for all projects instead of the current one.

### Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.rustwright]
command = "uvx"
args = ["--from", "git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp", "rustwright-mcp"]

[mcp_servers.rustwright.env]
RUSTWRIGHT_MCP_CHANNEL = "chrome"
```

### Cursor

Add to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project):

```json
{
  "mcpServers": {
    "rustwright": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp", "rustwright-mcp"],
      "env": { "RUSTWRIGHT_MCP_CHANNEL": "chrome" }
    }
  }
}
```

### Claude Desktop

Add the same `mcpServers` entry as the Cursor block above to:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Then restart Claude Desktop.

### VS Code (Copilot agent mode)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "rustwright": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp", "rustwright-mcp"],
      "env": { "RUSTWRIGHT_MCP_CHANNEL": "chrome" }
    }
  }
}
```

### Any other MCP client

The server speaks MCP over stdio. Configure your client to run:

```
command: uvx
args:    --from git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp rustwright-mcp
env:     RUSTWRIGHT_MCP_CHANNEL=chrome
```

## Step 3: verify

After registering (restart the client if it does not hot-reload MCP config),
confirm the connection:

1. The client should list tools named `browser_navigate`, `browser_snapshot`,
   `browser_click`, and more from a server called `rustwright`.
2. Call `browser_navigate` with `url: "https://example.com"`. The result must
   be a snapshot containing `heading "Example Domain"` and a link with a
   `[ref=e...]` handle.

If both hold, setup is complete. Report to the user:

```
Rustwright MCP setup complete
- server: rustwright (stdio via uvx)
- browser: <chrome | bundled chromium>, headless
- verified: browser_navigate returned a snapshot with element refs
```

## Configuration options

Set these in the `env` block of your client config:

| Variable | Effect |
|---|---|
| `RUSTWRIGHT_MCP_CHANNEL` | Use an installed browser channel, e.g. `chrome`. Omit to use the bundled Chromium |
| `RUSTWRIGHT_MCP_HEADLESS` | `0` shows a visible browser window (default: headless) |
| `RUSTWRIGHT_MCP_EXECUTABLE` | Explicit browser binary path (overrides channel) |
| `RUSTWRIGHT_MCP_ALLOW_EVAL` | `1` exposes `browser_evaluate` (arbitrary page JS; off by default) |

## Troubleshooting

- **`missing required argument 'commandOrUrl'`** (Claude Code): you omitted
  the `--` separator before `uvx`. Re-run the exact command from Step 2.
- **`Failed to launch chromium: Chromium did not expose a CDP endpoint`**:
  no usable browser. Either install Google Chrome and keep
  `RUSTWRIGHT_MCP_CHANNEL=chrome`, or run the bundled-Chromium install from
  Step 1 and remove the channel variable. On very slow machines the 30-second
  launch timeout itself can be the cause; retry once before changing config.
- **A site renders empty or blocks you**: some sites reject headless browsers.
  Set `RUSTWRIGHT_MCP_HEADLESS=0` and retry.
- **Acting on a ref fails with a stale-snapshot error**: the page changed
  since the last snapshot. Call `browser_snapshot` and use a fresh ref.

## Resources

- Server documentation and full tool list: [mcp/README.md](README.md)
- Rustwright project: <https://github.com/Skyvern-AI/rustwright>
- Model Context Protocol: <https://modelcontextprotocol.io>
