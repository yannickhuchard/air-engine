import json
from pathlib import Path
import runpy
import socket
import ssl
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request
import pytest
from fastapi.testclient import TestClient
from air.api import create_app
from air.cli import bootstrap, main
from air.config import Settings
from air.mcp import APIClient, PROTOCOL
from air.transport import ServerBinding, client_transport, origin
from conftest import ROOT


@pytest.mark.parametrize("url", ["http://example.org", "http://192.0.2.1:8740", "https://u:p@example.org", "https://example.org/api", "https://example.org?x", "https://example.org#x", "https://example.org:0", "https://example.org:65536", "https://example.org:", "https://example.org%2f", "https://bad_name.example", "https://example.org\n", "file:///tmp/x"])
def test_origin_rejects_ambiguous_or_unencrypted_destinations(url):
    with pytest.raises(ValueError): origin(url)


def test_origin_canonicalization_and_default_client():
    assert origin("https://AIR.EXAMPLE:443/") == "https://air.example"
    assert origin("https://[::1]:8740") == "https://[::1]:8740"
    assert client_transport()[0] == "http://127.0.0.1:8740"
    with pytest.raises(ValueError): client_transport(ca_file="unused.pem")
    with pytest.raises(ValueError): ServerBinding.load(ROOT, {"host": "0.0.0.0"})
    with pytest.raises(ValueError): ServerBinding.load(ROOT, [], 8740)


def tls_config(folder, port):
    pytest.importorskip("cryptography")
    config = runpy.run_path(str(ROOT / "scripts/tls_fixture.py"))["create_certificates"](folder)
    config["origin"] = "https://localhost:" + str(port)
    return config


def test_tls_binding_requires_matching_material_and_explicit_port(tmp_path):
    config = tls_config(tmp_path, 9876)
    binding = ServerBinding.load(tmp_path, config)
    binding.validate_tls()
    assert binding.host == "127.0.0.1" and binding.port == 9876
    with pytest.raises(ValueError): ServerBinding.load(tmp_path, config, 8740)
    with pytest.raises(ValueError): ServerBinding.load(tmp_path, {**config, "origin": "http://localhost:9876"})
    with pytest.raises(ValueError): ServerBinding.load(tmp_path, {**config, "proxy_headers": True})
    with pytest.raises(ssl.SSLError): ServerBinding.load(tmp_path, {**config, "tls_key_file": config["ca_file"]}).validate_tls()


def test_tls_http_and_mcp_origin_checks(store, tmp_path):
    config = tls_config(tmp_path, 9876)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), server=config)
    token = store.create_token("agent", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    with TestClient(create_app(settings, run_worker=False), base_url=config["origin"]) as client:
        assert client.get("/v1/identity", headers=headers).status_code == 200
        assert client.get("/v1/identity").status_code == 401
        for extra in ({"Host": "evil.invalid:9876"}, {"Host": "localhost:9876/"}, {"Origin": "null"}, {"Origin": "https://evil.invalid"}):
            assert client.get("/health", headers=extra).status_code == 403
        assert client.get("/health", headers=[("Host", "localhost:9876"), ("Host", "evil.invalid")]).status_code == 403
        assert client.get("http://localhost:9876/health", headers={"X-Forwarded-Proto": "https"}).status_code == 403
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "air_whoami", "arguments": {}}}
        result = client.post("/mcp", json=body, headers={**headers, "Origin": config["origin"], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL})
        assert result.status_code == 200 and not result.json()["result"]["isError"]


def test_authenticated_clients_never_follow_redirects(tmp_path, capsys):
    received = []
    class Target(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            received.append(self.headers.get("Authorization"))
            self.send_response(200);self.end_headers();self.wfile.write(b'{}')
    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:" + str(target.server_port) + "/stolen")
            self.end_headers()
    redirect = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    workers = [threading.Thread(target=s.serve_forever, daemon=True) for s in (target, redirect)]
    for worker in workers: worker.start()
    (tmp_path / "credentials.json").write_text(json.dumps({"access_token": "test-only-sentinel"}), encoding="utf-8")
    try:
        result = APIClient(tmp_path, "credentials.json", redirect.server_port)("air_whoami", {})
        assert result["error"] == "AIR_API_REJECTED" and result["http_status"] == 302 and "message" not in result, "a redirect body is never relayed"
        assert main(["--home", str(tmp_path), "whoami", "--port", str(redirect.server_port)]) == 1
        assert received == []
        captured = capsys.readouterr()
        assert "test-only-sentinel" not in captured.out + captured.err
    finally:
        for server in (target, redirect): server.shutdown();server.server_close()
        for worker in workers: worker.join(timeout=5)


def test_real_tls_install_clients_stop_and_local_recovery(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    home = tmp_path / "home"
    bootstrap(home)
    credentials = (home / "credentials.json").read_bytes()
    with socket.socket() as probe: probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    config = tls_config(home / "tls", port)
    request = tmp_path / "server.json"
    request.write_text(json.dumps(config), encoding="utf-8")
    assert main(["--home", str(home), "server-configure", str(request)]) == 0
    command = [sys.executable, str(ROOT / "scripts/install.py"), "--skip-install", "--venv", str(Path(sys.executable).parents[1]), "--home", str(home)]
    stopped = False
    try:
        started = subprocess.run(command + ["--start"], capture_output=True, text=True, timeout=60)
        assert started.returncode == 0, "TLS installer failed"
        binding = ServerBinding.load(home, config)
        assert binding.health()["instance_id"] == Settings.load(home).instance_id
        adapter = APIClient(home, "credentials.json", url=config["origin"], ca_file=config["ca_file"])
        assert adapter("air_whoami", {})["identity"].startswith("urn:air:identity:")
        assert main(["--home", str(home), "whoami", "--url", config["origin"], "--ca-file", config["ca_file"]]) == 0
        with pytest.raises(URLError): APIClient(home, "credentials.json", url=config["origin"])("air_whoami", {})
        with pytest.raises(URLError): APIClient(home, "credentials.json", url="https://127.0.0.1:" + str(port), ca_file=config["ca_file"])("air_whoami", {})
        assert main(["--home", str(home), "server-configure", str(request)]) == 1
        repeated = subprocess.run(command + ["--start"], capture_output=True, text=True, timeout=60)
        assert repeated.returncode == 0 and (home / "credentials.json").read_bytes() == credentials
        state = (home / "server.json").read_bytes()
        bad = json.loads(state);bad["instance_id"] = "unrelated"
        (home / "server.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            refused = subprocess.run(command + ["--stop"], capture_output=True, text=True, timeout=30)
            assert refused.returncode != 0 and binding.health()["service"] == "air"
        finally: (home / "server.json").write_bytes(state)
        # Stop uses the saved, verified endpoint, even if deployment config changes.
        changed = json.loads((home / "config.json").read_text(encoding="utf-8"))
        changed["server"]["origin"] = "https://unresolvable.invalid:" + str(port)
        (home / "config.json").write_text(json.dumps(changed), encoding="utf-8")
        result = subprocess.run(command + ["--stop"], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0;stopped = True
        from air.backup import snapshot, restore
        backup = tmp_path / "backup"
        snapshot(home, backup)
        restore(backup, tmp_path / "restored")
        assert Settings.load(tmp_path / "restored").server == {}
        captured = capsys.readouterr()
        secret = json.loads(credentials)["access_token"]
        assert secret not in captured.out + captured.err + started.stdout + repeated.stdout
    finally:
        if not stopped and (home / "server.json").exists():
            subprocess.run(command + ["--stop"], capture_output=True, timeout=30)


def test_failed_tls_start_stops_only_its_own_process_tree(tmp_path, monkeypatch):
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    home = tmp_path / "home"
    bootstrap(home)
    with socket.socket() as probe: probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    config = tls_config(home / "tls", port)
    config["origin"] = "https://wrong-name.invalid:" + str(port)
    document = json.loads((home / "config.json").read_text(encoding="utf-8"))
    document["server"] = config
    (home / "config.json").write_text(json.dumps(document), encoding="utf-8")
    command = [sys.executable, str(ROOT / "scripts/install.py"), "--skip-install", "--venv", str(Path(sys.executable).parents[1]), "--home", str(home), "--start"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and not (home / "server.json").exists()
    with socket.socket() as probe: assert probe.connect_ex(("127.0.0.1", port)) != 0


def test_tls_and_signed_oidc_are_independent_options(store, tmp_path, monkeypatch):
    jwt = pytest.importorskip("jwt")
    from cryptography.hazmat.primitives.asymmetric import rsa
    from types import SimpleNamespace
    import time
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt.PyJWKClient, "get_signing_key_from_jwt", lambda self, token: SimpleNamespace(key=key.public_key()))
    config = tls_config(tmp_path, 9876)
    oidc = {"issuer": "https://id.example.org", "audience": "air-api", "jwks_url": "https://id.example.org/keys", "subjects": {"architect": "editor"}}
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), "oidc", oidc, "tls-test", config)
    token = jwt.encode({"iss": oidc["issuer"], "aud": oidc["audience"], "sub": "architect", "iat": int(time.time()) - 1, "exp": int(time.time()) + 60}, key, algorithm="RS256")
    local = store.create_token("architect", "editor")
    with TestClient(create_app(settings, run_worker=False), base_url=config["origin"]) as client:
        assert client.get("/v1/identity", headers={"Authorization": "Bearer " + token}).status_code == 200
        assert client.get("/v1/identity", headers={"Authorization": "Bearer " + local["access_token"]}).status_code == 401
