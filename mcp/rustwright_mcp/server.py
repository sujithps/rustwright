"""MCP server exposing Rustwright browser automation over stdio.

Tool names mirror the Playwright MCP server so agents can switch between
the two without re-learning the surface. Element targeting uses refs from
``browser_snapshot`` (``e1``, ``e2``, ...) or raw CSS selectors.

Environment variables:
    RUSTWRIGHT_MCP_HEADLESS    "0" to show the browser window (default headless)
    RUSTWRIGHT_MCP_CHANNEL     chromium channel, e.g. "chrome" (default: bundled chromium)
    RUSTWRIGHT_MCP_EXECUTABLE  explicit browser executable path (overrides channel)
"""

from __future__ import annotations

import functools
import os
import tempfile
import threading
from typing import Optional

from mcp.server.fastmcp import FastMCP

from rustwright_mcp.snapshot import SNAPSHOT_JS

mcp = FastMCP("rustwright")

_session: dict = {}
# FastMCP executes sync tools on a thread pool; the browser session is
# shared state, so tool bodies are serialized.
_lock = threading.Lock()


def _serialized(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _lock:
            return fn(*args, **kwargs)

    return wrapper

SNAPSHOT_CHAR_LIMIT = 30_000


def _page():
    if "page" in _session:
        try:
            # The user may have closed a headed window; detect a dead
            # session and relaunch instead of failing every call.
            _session["page"].evaluate("() => 1")
        except Exception:
            _teardown()
    if "page" not in _session:
        from rustwright.sync_api import sync_playwright

        headless = os.environ.get("RUSTWRIGHT_MCP_HEADLESS", "1") != "0"
        launch_kwargs: dict = {"headless": headless}
        executable = os.environ.get("RUSTWRIGHT_MCP_EXECUTABLE")
        channel = os.environ.get("RUSTWRIGHT_MCP_CHANNEL")
        if executable:
            launch_kwargs["executable_path"] = executable
        elif channel:
            launch_kwargs["channel"] = channel
        pw = sync_playwright().start()
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        _session.update(pw=pw, browser=browser, page=page, snapshot_taken=False)
    return _session["page"]


def _snapshot(page) -> str:
    try:
        # An action may have triggered a navigation; settle before reading the DOM.
        page.wait_for_load_state(timeout=10_000)
    except Exception:
        pass
    outline = page.evaluate(SNAPSHOT_JS)
    _session["snapshot_taken"] = True
    header = f"Page: {page.title()}\nURL: {page.url}\n\n"
    body = outline[:SNAPSHOT_CHAR_LIMIT]
    if len(outline) > SNAPSHOT_CHAR_LIMIT:
        body += "\n- … (snapshot truncated, use browser_get_text for full content)"
    return header + body


def _teardown() -> None:
    for close in (
        lambda: _session["browser"].close(),
        lambda: _session["pw"].stop(),
    ):
        try:
            close()
        except Exception:
            pass
    _session.clear()


def _resolve(target: str) -> str:
    """Map a snapshot ref like ``e12`` to its attribute selector; pass CSS through.

    Refs fail fast when absent from the live DOM (stale snapshot) instead of
    hitting the full action timeout.
    """
    if target and target[0] == "e" and target[1:].isdigit():
        if not _session.get("snapshot_taken"):
            raise ValueError(
                "No snapshot taken on this page yet; call browser_snapshot first"
            )
        selector = f'[data-mcp-ref="{target}"]'
        if _session["page"].query_selector(selector) is None:
            raise ValueError(
                f"Ref {target} is not on the current page (stale snapshot); "
                "call browser_snapshot and use a fresh ref"
            )
        return selector
    return target


@mcp.tool()
@_serialized
def browser_navigate(url: str) -> str:
    """Navigate to a URL. Returns the page snapshot with element refs."""
    page = _page()
    page.goto(url)
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_snapshot() -> str:
    """Accessibility-style outline of the current page. Interactive elements
    carry [ref=eN] handles usable with browser_click / browser_type."""
    return _snapshot(_page())


@mcp.tool()
@_serialized
def browser_click(target: str, double_click: bool = False) -> str:
    """Click an element. `target` is a ref from the snapshot (e.g. "e12") or a
    CSS selector. Returns a fresh snapshot."""
    page = _page()
    selector = _resolve(target)
    if double_click:
        page.dblclick(selector)
    else:
        page.click(selector)
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_type(target: str, text: str, submit: bool = False, clear: bool = True) -> str:
    """Type into an input. `target` is a snapshot ref or CSS selector. Set
    submit=True to press Enter afterwards. Returns a fresh snapshot."""
    page = _page()
    selector = _resolve(target)
    if clear:
        page.fill(selector, text)
    else:
        page.type(selector, text)
    if submit:
        page.press(selector, "Enter")
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_select_option(target: str, value: str) -> str:
    """Select an option in a <select> element by value or visible label."""
    page = _page()
    selector = _resolve(target)
    try:
        page.select_option(selector, value=value)
    except Exception:
        page.select_option(selector, label=value)
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_hover(target: str) -> str:
    """Hover over an element identified by snapshot ref or CSS selector."""
    page = _page()
    page.hover(_resolve(target))
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_press_key(key: str) -> str:
    """Press a keyboard key (e.g. "Enter", "Escape", "ArrowDown") on the page."""
    page = _page()
    page.keyboard.press(key)
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_navigate_back() -> str:
    """Go back in browser history. Returns a fresh snapshot."""
    page = _page()
    page.go_back()
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_wait_for(text: Optional[str] = None, timeout_ms: float = 10_000) -> str:
    """Wait for text to appear on the page (or for load state when no text
    is given), then return a snapshot."""
    page = _page()
    if text:
        page.wait_for_selector(f"text={text}", timeout=timeout_ms)
    else:
        page.wait_for_load_state(timeout=timeout_ms)
    return _snapshot(page)


@mcp.tool()
@_serialized
def browser_get_text(selector: str = "body", max_chars: int = 20_000) -> str:
    """Visible text content of a CSS selector (defaults to the whole page)."""
    return _page().inner_text(selector)[:max_chars]


@mcp.tool()
@_serialized
def browser_evaluate(expression: str) -> str:
    """Run JavaScript in the page. Use an arrow function, e.g.
    "() => document.title". Returns the JSON-ish result as a string."""
    return str(_page().evaluate(expression))


@mcp.tool()
@_serialized
def browser_take_screenshot(path: Optional[str] = None, full_page: bool = False) -> str:
    """Save a PNG screenshot and return its file path. Writes to a temporary
    file when no path is given."""
    if path is None:
        fd, path = tempfile.mkstemp(prefix="rustwright-mcp-", suffix=".png")
        os.close(fd)
    _page().screenshot(path=path, full_page=full_page)
    return path


@mcp.tool()
@_serialized
def browser_close() -> str:
    """Close the browser. The next tool call starts a fresh session."""
    if "browser" in _session:
        _teardown()
        return "Browser closed."
    return "No browser session was open."


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
