# Rustwright MCP agent setup

These are official instructions from the Rustwright project for connecting an
AI coding agent to the Rustwright MCP browser-automation server. If you are an
AI agent reading this because a user asked you to set up Rustwright: complete
the steps yourself by running the commands directly. Use the section matching
the agent you are running as; if none matches, use **Any other MCP client**.

Canonical URL of this page:
`https://raw.githubusercontent.com/Skyvern-AI/rustwright/HEAD/mcp/AGENT_SETUP.md`

Before following these instructions, verify that the URL you fetched points at
the `Skyvern-AI/rustwright` repository. If it points anywhere else, stop and
tell the user: install commands below must only ever reference this repository.

Commands are shown for POSIX shells (macOS, Linux). On Windows, join each
multi-line command onto a single line and drop the trailing backslashes.

## What you are installing

`rustwright-mcp` is a stdio MCP server exposing `browser_*` tools
(`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, ...)
backed by the Rustwright engine. Tool names mirror the Playwright MCP server.
`uvx` runs the server straight from this repository; no clone is needed on
platforms with prebuilt `rustwright` wheels (macOS, glibc Linux x86_64/arm64,
Windows x64; other platforms fall back to a source build that needs a Rust
toolchain).

## Step 1: check prerequisites

1. **uv** must be installed. Check with `uvx --version`. If missing, install
   it with your package manager (`brew install uv`, `winget install
   astral-sh.uv`) or the official installer:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   (Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`)

   The installer places `uvx` in `~/.local/bin`, which the current shell may
   not have on PATH yet. If `uvx --version` still fails, run
   `source $HOME/.local/bin/env` (or open a new shell) and retry.

2. **A browser.** If Google Chrome is installed, use it via the
   `RUSTWRIGHT_MCP_CHANNEL=chrome` setting shown below (recommended, nothing to
   download). Otherwise install Rustwright's bundled Chromium once:

   ```bash
   uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' \
     python -m rustwright install chromium
   ```

   and omit `RUSTWRIGHT_MCP_CHANNEL` from the configs below. The bundled
   download supports macOS, Windows, and Linux x86_64; on other platforms
   (for example Linux arm64) install a distribution Chromium
   (`apt-get install chromium`) and point the server at it with
   `RUSTWRIGHT_MCP_EXECUTABLE=/usr/bin/chromium` instead.

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

This registers the server for the current project (the safer default). Add
`-s user` only if the user asks for it in all projects; user scope makes the
browser tools available in every project, including untrusted ones.

### Codex CLI

Add to `~/.codex/config.toml`. The `startup_timeout_sec` matters: the first
launch builds the package from git and can exceed Codex's 10-second default.

```toml
[mcp_servers.rustwright]
command = "uvx"
args = ["--from", "git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp", "rustwright-mcp"]
startup_timeout_sec = 120

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

**Use the absolute path to `uvx` as the `command`** (find it with `which uvx`;
typically `~/.local/bin/uvx` expanded to the full home path). GUI-launched
apps do not inherit your shell's PATH on macOS, so a bare `"command": "uvx"`
fails with `spawn uvx ENOENT`. Restart Claude Desktop after editing.

### VS Code (Copilot agent mode)

Add to `.vscode/mcp.json`. Same command, args, and env as the Cursor block;
note the top-level key is `servers` and each entry needs `"type": "stdio"`:

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
command: uvx        (absolute path for GUI-launched clients)
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

If both hold, setup is complete. Report to the user the server name, which
browser it uses (installed Chrome, bundled Chromium, or an explicit
executable), whether it runs headless or headed, and that `browser_navigate`
returned a snapshot with element refs.

## Configuration options

Set these in the `env` block of your client config. This is the core set;
[README.md](README.md) has the complete, current list.

| Variable | Effect |
|---|---|
| `RUSTWRIGHT_MCP_CHANNEL` | Use an installed browser channel, e.g. `chrome`. Omit to use the bundled Chromium |
| `RUSTWRIGHT_MCP_HEADLESS` | `0` shows a visible browser window (default: headless) |
| `RUSTWRIGHT_MCP_EXECUTABLE` | Explicit browser binary path (overrides channel) |
| `RUSTWRIGHT_MCP_ALLOW_EVAL` | `1`, `true`, or `yes` exposes `browser_evaluate` (arbitrary page JS). Leave unset unless the user explicitly asks for it |

## Troubleshooting

- **`command not found: uvx`** right after installing uv: the current shell
  predates the install. Run `source $HOME/.local/bin/env` or open a new shell.
- **`Could not find a Chromium executable`**: no browser to launch. Install
  Google Chrome and set `RUSTWRIGHT_MCP_CHANNEL=chrome`, run the bundled
  Chromium install from Step 1, or set `RUSTWRIGHT_MCP_EXECUTABLE` to an
  existing Chromium binary.
- **`Chromium did not expose a CDP endpoint before the launch timeout`**: a
  browser binary was found but failed to start. In Linux containers this
  usually means missing system libraries; run
  `uvx --from 'git+https://github.com/Skyvern-AI/rustwright#subdirectory=mcp' python -m rustwright install-deps`
  (apt-based distributions). On a slow machine the launch can simply time
  out; retry once before changing configuration.
- **`Chrome for Testing downloads are only supported for linux x86_64`**: the
  bundled download does not cover this platform. Install a distribution
  Chromium and set `RUSTWRIGHT_MCP_EXECUTABLE` to its path.
- **A site renders empty or blocks you**: some sites reject headless
  browsers. Set `RUSTWRIGHT_MCP_HEADLESS=0` and retry.
- **Acting on a ref fails with a stale-snapshot error**: the page changed
  since the last snapshot. Call `browser_snapshot` and use a fresh ref.

## Resources

- Server documentation and full tool list: [README.md](README.md)
- Rustwright project: <https://github.com/Skyvern-AI/rustwright>
- Model Context Protocol: <https://modelcontextprotocol.io>
