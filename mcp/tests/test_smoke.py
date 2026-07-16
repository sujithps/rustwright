"""Smoke test for the Rustwright MCP server.

Speaks the real MCP stdio protocol against a local HTML fixture, so no
network access is required. Skips when no Chromium is available; set
RUSTWRIGHT_MCP_CHANNEL=chrome to use an installed Chrome.
"""

import asyncio
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "form.html"


def _server_command() -> list[str]:
    exe = shutil.which("rustwright-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "rustwright_mcp"]


async def _run_session(checks) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = _server_command()
    params = StdioServerParameters(
        command=command[0], args=command[1:], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await checks(session)


async def _call(session, name, **kwargs) -> str:
    result = await session.call_tool(name, kwargs)
    text = "\n".join(c.text for c in result.content if c.type == "text")
    if result.isError:
        if "Failed to launch chromium" in text:
            pytest.skip("no Chromium available for MCP smoke test")
        raise AssertionError(f"{name} failed: {text}")
    return text


def test_stdio_form_flow():
    async def checks(session):
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"browser_navigate", "browser_snapshot", "browser_click",
                "browser_type", "browser_close"} <= tools

        snap = await _call(session, "browser_navigate", url=FIXTURE.as_uri())
        assert snap.startswith("Page: Form Test")
        name_ref = re.search(r'textbox "Customer name"[^\[]*\[ref=(e\d+)\]', snap).group(1)
        size_ref = re.search(r'combobox "Size" \[ref=(e\d+)\]', snap).group(1)
        btn_ref = re.search(r'button "Place order"[^\[]*\[ref=(e\d+)\]', snap).group(1)

        await _call(session, "browser_type", target=name_ref, text="Rustwright Test")
        await _call(session, "browser_select_option", target=size_ref, value="Large")
        await _call(session, "browser_click", target=btn_ref)

        out = await _call(session, "browser_get_text", selector="#out")
        assert out == "name=Rustwright Test;size=l"

        title = await _call(session, "browser_evaluate", expression="() => document.title")
        assert title == "Form Test"

        assert await _call(session, "browser_close") == "Browser closed."

    asyncio.run(_run_session(checks))
