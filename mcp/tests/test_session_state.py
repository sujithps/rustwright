"""Tests for browser_session_state and the confined output-read path.

Three layers:
  * FilePolicy.read_output adversarial cases (symlink, traversal, cap, missing).
  * _apply_storage_state input validation and restore behavior, with fakes.
  * A real cross-session round trip: save cookies + localStorage in one server
    process, then restore them in a second process sharing the output dir.
"""

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from rustwright_mcp.filepolicy import FilePolicy, FilePolicyError
from rustwright_mcp import server
from test_smoke import _call, _run_session, _result_section


# --- FilePolicy.read_output ------------------------------------------------


def test_read_output_reads_confined_file(tmp_path):
    root = tmp_path / "output"
    policy = FilePolicy(output_root=root)
    target = root / "state.json"
    target.write_text('{"ok": true}', encoding="utf-8")

    assert policy.read_output("state.json") == b'{"ok": true}'
    # An absolute path already inside the root is accepted too.
    assert policy.read_output(str(target)) == b'{"ok": true}'


def test_read_output_missing_file(tmp_path):
    policy = FilePolicy(output_root=tmp_path / "output")
    with pytest.raises(FilePolicyError, match="does not exist"):
        policy.read_output("nope.json")


def test_read_output_rejects_symlink(tmp_path):
    root = tmp_path / "output"
    policy = FilePolicy(output_root=root)
    secret = tmp_path / "secret.json"
    secret.write_text("secret", encoding="utf-8")
    link = root / "link.json"
    link.symlink_to(secret)

    with pytest.raises(FilePolicyError, match="must not be a symlink"):
        policy.read_output("link.json")


def test_read_output_rejects_traversal(tmp_path):
    root = tmp_path / "output"
    policy = FilePolicy(output_root=root)
    outside = tmp_path / "outside.json"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(FilePolicyError, match="confined to"):
        policy.read_output("../outside.json")
    with pytest.raises(FilePolicyError, match="confined to"):
        policy.read_output(str(outside))


def test_read_output_enforces_byte_cap(tmp_path):
    root = tmp_path / "output"
    policy = FilePolicy(output_root=root, max_file_bytes=16, max_total_bytes=1024)
    (root / "big.json").write_bytes(b"x" * 17)

    with pytest.raises(FilePolicyError, match="per-file cap"):
        policy.read_output("big.json")


# --- _apply_storage_state --------------------------------------------------


class _FakeContext:
    def __init__(self):
        self.cleared = False
        self.added_cookies = None
        self.init_scripts = []

    def clear_cookies(self):
        self.cleared = True

    def add_cookies(self, cookies):
        self.added_cookies = cookies

    def add_init_script(self, script=None, *, path=None):
        self.init_scripts.append(script)


class _FakePage:
    def __init__(self, origin):
        self._origin = origin
        self.applied = []

    def evaluate(self, expression, arg=None):
        if "location.origin" in expression:
            return self._origin
        self.applied.append((expression, arg))
        return None


def test_apply_storage_state_rejects_non_object():
    with pytest.raises(ValueError, match="must be a JSON object"):
        server._apply_storage_state(_FakeContext(), _FakePage(None), ["nope"])


def test_apply_storage_state_rejects_non_array_members():
    with pytest.raises(ValueError, match="must be arrays"):
        server._apply_storage_state(
            _FakeContext(), _FakePage(None), {"cookies": {}, "origins": []}
        )


def test_apply_storage_state_restores_cookies_and_current_origin():
    context = _FakeContext()
    page = _FakePage("https://example.com")
    state = {
        "cookies": [{"name": "sid", "value": "1", "domain": "example.com", "path": "/"}],
        "origins": [
            {"origin": "https://example.com", "localStorage": [{"name": "t", "value": "v"}]},
            {"origin": "https://other.test", "localStorage": [{"name": "x", "value": "y"}]},
        ],
    }

    cookie_count, origin_count, applied_now = server._apply_storage_state(
        context, page, state
    )

    assert (cookie_count, origin_count, applied_now) == (1, 2, "https://example.com")
    assert context.cleared is True
    assert context.added_cookies == state["cookies"]
    # Both origins get an init script; the current origin is applied immediately.
    assert len(context.init_scripts) == 2
    assert len(page.applied) == 1
    assert page.applied[0][1] == [{"name": "t", "value": "v"}]


def test_apply_storage_state_skips_when_no_current_origin():
    context = _FakeContext()
    page = _FakePage(None)
    state = {
        "cookies": [],
        "origins": [
            {"origin": "https://example.com", "localStorage": [{"name": "t", "value": "v"}]},
        ],
    }

    cookie_count, origin_count, applied_now = server._apply_storage_state(
        context, page, state
    )

    assert (cookie_count, origin_count, applied_now) == (0, 1, None)
    assert context.cleared is True
    assert context.added_cookies is None  # no cookies to add
    assert len(context.init_scripts) == 1
    assert page.applied == []  # nothing applied without a matching current origin


# --- cross-session round trip ---------------------------------------------


class _StateHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - required name
        body = b"<!doctype html><html><body><h1>State Fixture</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence server logging
        pass


@pytest.fixture(scope="module")
def http_origin():
    server_obj = ThreadingHTTPServer(("127.0.0.1", 0), _StateHandler)
    thread = threading.Thread(target=server_obj.serve_forever, daemon=True)
    thread.start()
    host, port = server_obj.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server_obj.shutdown()
        server_obj.server_close()


def test_session_state_round_trip_across_processes(tmp_path, http_origin):
    output_dir = tmp_path / "mcp-output"
    output_dir.mkdir()
    env = {
        "RUSTWRIGHT_MCP_OUTPUT_DIR": str(output_dir),
    }
    channel = os.environ.get("RUSTWRIGHT_MCP_CHANNEL")
    if channel:
        env["RUSTWRIGHT_MCP_CHANNEL"] = channel

    # Session 1: seed a cookie + localStorage, then save the state.
    async def save_session(session):
        await _call(session, "browser_navigate", url=f"{http_origin}/")
        await _call(
            session,
            "browser_evaluate",
            function=(
                "() => { document.cookie = 'sid=abc123; path=/'; "
                "localStorage.setItem('token', 'secret-token'); }"
            ),
        )
        result = await _call(
            session, "browser_session_state", action="save", path="state.json"
        )
        assert "Saved session state" in result
        assert "1 cookies" in result

    asyncio.run(_run_session(save_session, env))

    assert (output_dir / "state.json").exists()
    saved = json.loads((output_dir / "state.json").read_text())
    assert any(c["name"] == "sid" for c in saved["cookies"])

    # Session 2: a fresh server process, same output dir. Load, then verify
    # the cookie and localStorage were restored on the target origin.
    async def load_session(session):
        loaded = await _call(
            session, "browser_session_state", action="load", path="state.json"
        )
        assert "Restored 1 cookies" in _result_section(loaded)
        await _call(session, "browser_navigate", url=f"{http_origin}/")
        state = await _call(
            session,
            "browser_evaluate",
            function=(
                "() => 'cookie=' + document.cookie + "
                "' token=' + localStorage.getItem('token')"
            ),
        )
        # Assert on the raw response text so the check does not depend on the
        # exact response-envelope formatting.
        assert "sid=abc123" in state, state
        assert "secret-token" in state, state

    asyncio.run(_run_session(load_session, env))
