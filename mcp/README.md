# Rustwright MCP server

Exposes Rustwright browser automation as [Model Context Protocol](https://modelcontextprotocol.io)
tools, so MCP-compatible agents (Claude Code, Claude Desktop, others) can browse
with Rustwright instead of Playwright.

Tool names mirror the Playwright MCP server (`browser_navigate`,
`browser_snapshot`, `browser_click`, ...) so agents can switch without
re-learning the surface. `browser_snapshot` returns an accessibility-style
outline where interactive elements carry `[ref=eN]` handles; pass a ref (or a
raw CSS selector) to the action tools.

## Quick start (no clone needed)

With [uv](https://docs.astral.sh/uv/) installed, register the server with
Claude Code in one command — `uvx` fetches and runs it straight from GitHub:

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  -- uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' rustwright-mcp
```

Note the `--` before the command: `--env` is variadic, so without the
separator it swallows the command and `claude mcp add` fails with
`missing required argument 'commandOrUrl'`.

Or add to any MCP client config (Claude Desktop, Cursor, etc.):

```json
{
  "mcpServers": {
    "rustwright": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp",
        "rustwright-mcp"
      ],
      "env": { "RUSTWRIGHT_MCP_CHANNEL": "chrome" }
    }
  }
}
```

`RUSTWRIGHT_MCP_CHANNEL=chrome` uses your installed Google Chrome. Drop it
to use rustwright's bundled Chromium instead (install once with
`uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' python -m rustwright install chromium`).

Without uv, install into a plain venv from git:

```bash
python3 -m venv ~/.rustwright-mcp
~/.rustwright-mcp/bin/pip install 'rustwright-mcp @ git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp'
```

## Install from a source checkout

```bash
cd mcp
python3 -m venv .venv && .venv/bin/pip install -e .
```

Then either install the bundled Chromium
(`.venv/bin/python -m rustwright install chromium`) or use
`RUSTWRIGHT_MCP_CHANNEL=chrome`.

## Register with Claude Code (installed binary)

Use the **absolute path** to the `rustwright-mcp` binary — the server is
spawned from arbitrary working directories, so relative paths break:

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  -- "$HOME/.rustwright-mcp/bin/rustwright-mcp"
```

Example with a source checkout at `~/code/rustwright`:

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  -- "$HOME/code/rustwright/mcp/.venv/bin/rustwright-mcp"
```

Verify with `claude mcp list` — the entry should show `✔ Connected`.

## Example session

What an agent sees. `browser_navigate` returns a snapshot; interactive
elements carry `[ref=eN]` handles that later calls act on:

```
> browser_navigate(url="https://example.com")
Page: Example Domain
URL: https://example.com/

- heading "Example Domain" [level=1]
- text: This domain is for use in documentation examples...
- link "Learn more" [href=https://iana.org/domains/example] [ref=e1]

> browser_click(target="e1")
Page: Example Domains
URL: https://www.iana.org/help/example-domains
...

> browser_get_text(selector="h1")
Example Domains
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

### Headless vs headed

The browser runs **headless** by default: no window, suited to CI and
background agents. Set `RUSTWRIGHT_MCP_HEADLESS=0` to run **headed** with a
visible browser window — useful for watching the agent work, debugging
selectors, and for sites whose bot detection blocks headless sessions:

```bash
claude mcp add rustwright \
  --env RUSTWRIGHT_MCP_CHANNEL=chrome \
  --env RUSTWRIGHT_MCP_HEADLESS=0 \
  -- uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' rustwright-mcp
```

The mode is fixed for the lifetime of the server process; to switch, change
the env var and restart the MCP server (in Claude Code: re-add the server or
restart the session).

## Limitations

- Single page, single browser session per server process.
- Snapshot refs are regenerated on every snapshot; after a page mutation,
  take a new snapshot before acting on refs. Stale refs fail fast with a
  message asking for a fresh snapshot.
- The snapshot script does not walk iframes (any origin) or shadow DOM;
  iframes appear as `- iframe "..." (content not captured)` markers. Use
  `browser_evaluate` to reach into same-origin frames if needed.
