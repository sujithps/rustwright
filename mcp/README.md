# Rustwright MCP server

Exposes Rustwright browser automation as [Model Context Protocol](https://modelcontextprotocol.io)
tools, so MCP-compatible agents (Claude Code, Claude Desktop, others) can browse
with Rustwright instead of Playwright.

Tool names mirror the Playwright MCP server (`browser_navigate`,
`browser_snapshot`, `browser_click`, ...) so agents can switch without
re-learning the surface. `browser_snapshot` returns an accessibility-style
outline where interactive elements carry `[ref=eN]` handles; pass a ref (or a
raw CSS selector) to the action tools.

## Install

```bash
cd mcp
python -m venv .venv && .venv/bin/pip install -e .
```

Then either install the bundled Chromium:

```bash
.venv/bin/python -m rustwright install chromium
```

or point the server at an existing Chrome via `RUSTWRIGHT_MCP_CHANNEL=chrome`.

## Register with Claude Code

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  -- <source-checkout>/mcp/.venv/bin/rustwright-mcp
```

Or add to any MCP client config:

```json
{
  "mcpServers": {
    "rustwright": {
      "command": "<source-checkout>/mcp/.venv/bin/rustwright-mcp",
      "env": { "RUSTWRIGHT_MCP_CHANNEL": "chrome" }
    }
  }
}
```

## Tools

| Tool | Purpose |
|---|---|
| `browser_navigate(url)` | Open a URL, returns snapshot |
| `browser_snapshot()` | Outline of the page with `[ref=eN]` handles |
| `browser_click(target)` | Click a ref or CSS selector |
| `browser_type(target, text, submit?)` | Fill or type into an input |
| `browser_select_option(target, value)` | Select a dropdown option |
| `browser_hover(target)` | Hover an element |
| `browser_press_key(key)` | Press a keyboard key |
| `browser_navigate_back()` | History back |
| `browser_wait_for(text?, timeout_ms?)` | Wait for text or load state |
| `browser_get_text(selector?)` | Visible text of a selector |
| `browser_evaluate(expression)` | Run JavaScript in the page |
| `browser_take_screenshot(path?)` | Save a PNG, returns the path |
| `browser_close()` | End the browser session |

## Configuration

| Variable | Effect |
|---|---|
| `RUSTWRIGHT_MCP_HEADLESS` | `0` shows the browser window (default headless) |
| `RUSTWRIGHT_MCP_CHANNEL` | Chromium channel, e.g. `chrome`, `chrome-beta` |
| `RUSTWRIGHT_MCP_EXECUTABLE` | Explicit browser binary path (overrides channel) |

## Limitations

- Single page, single browser session per server process.
- Snapshot refs are regenerated on every snapshot; after a page mutation,
  take a new snapshot before acting on refs.
- Cross-origin iframes are not walked by the snapshot script yet.
