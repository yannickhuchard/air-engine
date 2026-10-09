import io
import json
import subprocess
import sys
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from air.api import create_app
from air.config import Settings
from air.mcp import APIClient, PROTOCOL, Session, TOOLS, serve


def message(method, params=None, request_id=1):
    result = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None: result["params"] = params
    return result


def initialize(session):
    result = session.handle(message("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}))
    assert result["result"]["protocolVersion"] == PROTOCOL
    assert session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_lifecycle_discovery_and_schema_errors():
    called = []
    session = Session(lambda name, args: called.append(name) or {"ok": True})
    assert session.handle(message("tools/list"))["error"]["code"] == -32000
    lenient = Session(lambda name, args: {"ok": True})
    lenient.handle({"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {"protocolVersion": "2026-07-28", "capabilities": {}, "clientInfo": {"name": "tunnel"}}})
    assert "result" in lenient.handle(message("tools/list")), "a relay that never forwards notifications/initialized still works"
    again = lenient.handle({"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "tunnel"}}})
    assert again["result"]["serverInfo"]["name"] == "air", "a second logical session over the same process is answered"
    fresh = Session(lambda name, args: {"ok": True})
    refused = fresh.handle({"jsonrpc": "2.0", "id": "d", "method": "server/discover", "params": {}})
    assert refused["error"]["code"] == -32601, "a 2026-07-28 client falls back to initialize on method-not-found"
    initialize(session)
    instructions = lenient.handle(message("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "x"}}, 11))["result"]["instructions"]
    assert "withhold" in instructions and "tools_refused" in instructions, "an adapter that refuses tools is not a stale catalogue"
    tools = session.handle(message("tools/list"))["result"]["tools"]
    assert len(tools) == len({t['name'] for t in tools})
    assert {t['name'] for t in tools} == set(TOOLS)
    assert {'air_reconstruct_temporal', 'air_convert_currency', 'air_receive_checkpoint',
            'air_read_checkpoint', 'air_preview_connector'} <= {t['name'] for t in tools}
    assert next(t for t in tools if t["name"] == "air_package_revoke")["annotations"]["destructiveHint"]
    for tool in tools: Draft202012Validator.check_schema(tool["inputSchema"])
    assert all(tool["inputSchema"]["type"] == "object" and "$schema" not in tool["inputSchema"] for tool in tools), "MCP requires object input schemas"
    assert session.handle(message("tools/call", {"name": "air_get", "arguments": {"id": "urn:test:x", "revision": 0}}))["error"]["code"] == -32602
    assert session.handle(message("tools/call", {"name": "air_approve"}))["error"]["code"] == -32602
    assert session.handle(message("resources/list"))["error"]["code"] == -32601
    assert not called
    result = session.handle(message("tools/call", {"name": "air_capabilities"}))["result"]
    assert not result["isError"] and result["structuredContent"] == {"ok": True}
    assert session.handle([])["error"]["code"] == -32600
    assert session.handle(message("ping", request_id=True))["error"]["code"] == -32600


def test_stdio_framing_and_oversize():
    incoming = b'{bad json}\n' + json.dumps(message("ping")).encode() + b'\n'
    output = io.StringIO()
    assert serve(io.BytesIO(incoming), output, None) == 0
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert rows[0]["error"]["code"] == -32700 and rows[1]["result"] == {}
    output = io.StringIO()
    assert serve(io.BytesIO(b'x' * (1024 * 1024 + 1)), output, None) == 2
    assert len(output.getvalue().splitlines()) == 1


def test_api_bridge_preserves_authentication_and_revocation(store, example, tmp_path):
    token = store.create_token("agent", "reader")
    (tmp_path / "agent.json").write_text(json.dumps(token), encoding="utf-8")
    adapter = APIClient(tmp_path, "agent.json", 8740)
    store.put(example, "architect")
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        # Execute the adapter's actual urllib request through the real API router.
        class Reply:
            def __init__(self, response): self.response = response
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return self.response.content[:size]
        class Opener:
            def open(self, req, timeout):
                from urllib.error import HTTPError
                from urllib.parse import urlsplit
                response = client.request(req.method, urlsplit(req.full_url).path, content=req.data, headers=dict(req.header_items()))
                if response.status_code >= 400: raise HTTPError(req.full_url, response.status_code, "Rejected", {}, None)
                return Reply(response)
        adapter.opener = Opener()
        session = Session(adapter);initialize(session)
        def call(name, args): return session.handle(message("tools/call", {"name": name, "arguments": args}))["result"]
        ref = {"id": example["meta"]["id"], "revision": 1}
        assert call("air_get", ref)["structuredContent"]["object"] == example
        denied = call("air_import_drafts", {"objects": [example]})
        assert denied["isError"] and denied["structuredContent"]["http_status"] == 403
        store.revoke_token(token["token_id"])
        assert call("air_get", ref)["structuredContent"]["http_status"] == 401
        assert token["access_token"] not in json.dumps(denied)
        # P07 native finding: an API outage must not read as a missing right, nor answer from a cached catalogue.
        replacement = store.create_token("agent", "reader")
        (tmp_path / "agent.json").write_text(json.dumps(replacement), encoding="utf-8")
        working = adapter.opener
        class Down:
            def open(self, req, timeout):
                from urllib.error import URLError
                raise URLError("connection refused")
        adapter.opener = Down()
        outage = call("air_get", ref)
        assert outage["isError"] and outage["structuredContent"]["error"] == "AIR_UNREACHABLE" and "object" not in outage["structuredContent"]
        assert session.handle(message("tools/list"))["result"]["tools"] == []
        adapter.opener = working
        assert call("air_get", ref)["structuredContent"]["object"] == example, "the same session recovers after the outage"


def test_actual_stdio_process_has_only_protocol_stdout(tmp_path):
    requests = [message("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}}),
                {"jsonrpc": "2.0", "method": "notifications/initialized"}, message("tools/list", request_id=2)]
    result = subprocess.run([sys.executable, "-m", "air.mcp", "--home", str(tmp_path)],
                            input="\n".join(json.dumps(r) for r in requests) + "\n", text=True,
                            encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode == 0 and result.stderr == ""
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    # No authenticated identity is available: discovery fails closed until reconnection.
    assert len(rows) == 2 and rows[1]['result']['tools'] == []


def test_streamable_http_shares_acl_and_requires_origin_protocol(store, example, tmp_path):
    token = store.create_token("agent", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))), base_url="http://127.0.0.1:8740") as client:
        init = message("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}})
        assert client.post("/mcp", json=init, headers=headers).json()["result"]["protocolVersion"] == PROTOCOL
        assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers).status_code == 202
        assert client.get("/mcp", headers=headers).status_code == 405
        result = client.post("/mcp", json=message("tools/call", {"name": "air_import_drafts", "arguments": {"objects": [example]}}), headers=headers).json()["result"]
        assert result["isError"] and result["structuredContent"]["http_status"] == 403
        assert store.counts()["revisions"] == 0
        assert client.post("/mcp", json=init, headers={**headers, "Origin": "https://attacker.example"}).status_code == 403
        assert client.post("/mcp", json=init, headers={**headers, "Host": "attacker.example"}).status_code == 403
        assert client.post("/mcp", json=init, headers={**headers, "MCP-Protocol-Version": "bad"}).status_code == 400
        assert client.post("/mcp", json=init, headers={**headers, "Accept": "application/json"}).status_code == 406
        assert client.post("/mcp", json=init).status_code == 401


def test_local_http_dispatch_names_every_declared_tool():
    import inspect
    from air import mcp_http
    source = inspect.getsource(mcp_http)
    assert [name for name in TOOLS if '"' + name + '"' not in source] == []
