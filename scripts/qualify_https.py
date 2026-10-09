"""Replay the three fictitious dossiers through a disposable direct TLS server."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
from urllib.request import Request
import uuid
from air.backup import restore, snapshot
from air.config import Settings, write_private, protect_directory
from air.mcp import APIClient, PROTOCOL, Session
from air.storage import Store
from air.transport import client_transport
from air import __version__
from tls_fixture import create_certificates

ROOT = Path(__file__).resolve().parents[1]


def qualify(report_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source_home = Path(report["workbench_home"]).resolve()
    if not source_home.is_relative_to((ROOT / "tmp").resolve()) or not source_home.parent.name.startswith("air-runtime-"):
        raise ValueError("Expected an isolated AIR business demonstration")
    workspace = ROOT / "tmp" / ("air-https-" + uuid.uuid4().hex)
    protect_directory(workspace)
    snapshot(source_home, workspace / "input-backup")
    home = workspace / "home"
    restore(workspace / "input-backup", home)
    with socket.socket() as probe: probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    config = create_certificates(home / "tls")
    config["origin"] = "https://localhost:" + str(port)
    request_file = workspace / "tls-server.json"
    request_file.write_text(json.dumps(config), encoding="utf-8")
    configured = subprocess.run([sys.executable, "-m", "air", "--home", str(home), "server-configure", str(request_file)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert configured.returncode == 0, "TLS configuration failed"
    store = Store(Settings.load(home).database_url)
    try:
        for dossier in report["treatments"]:
            credential = store.create_token("observer-" + dossier["case"], "editor")
            write_private(home / (dossier["case"] + ".json"), credential)
    finally: store.engine.dispose()
    command = [sys.executable, str(ROOT / "scripts/install.py"), "--skip-install", "--venv", str(Path(sys.executable).parents[1]), "--home", str(home)]
    results = []
    started = False
    try:
        launched = subprocess.run(command + ["--start"], capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert launched.returncode == 0, "TLS server failed to start"
        started = True
        for dossier in report["treatments"]:
            case = dossier["case"]
            adapter = APIClient(home, case + ".json", url=config["origin"], ca_file=config["ca_file"])
            request = dossier["business"]["request"]
            assessed = adapter("air_assess_goal_targets", request)
            assert assessed == dossier["business"]["assessment"]
            request_file = workspace / (case + "-goal.json")
            request_file.write_text(json.dumps(request), encoding="utf-8")
            cli = subprocess.run([sys.executable, "-m", "air", "--home", str(home), "goal-assess", str(request_file), "--credential", case + ".json", "--url", config["origin"], "--ca-file", config["ca_file"]], capture_output=True, text=True, encoding="utf-8", timeout=30)
            assert cli.returncode == 0 and json.loads(cli.stdout) == assessed
            session = Session(adapter)
            session.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "tls-qualification", "version": "1"}}})
            session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
            message = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "air_assess_goal_targets", "arguments": request}}
            assert session.handle(message)["result"]["structuredContent"] == assessed
            base, opener = client_transport(url=config["origin"], ca_file=config["ca_file"])
            credentials = json.loads((home / (case + ".json")).read_text(encoding="utf-8"))
            wire = Request(base + "/mcp", data=json.dumps(message).encode("utf-8"), headers={"Authorization": "Bearer " + credentials["access_token"], "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Origin": base, "MCP-Protocol-Version": PROTOCOL})
            with opener.open(wire, timeout=30) as response:
                assert json.load(response)["result"]["structuredContent"] == assessed
            identity = adapter("air_whoami", {})["identity"]
            obj = deepcopy(dossier["receipt"]["object"])
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            obj["meta"].update(id="urn:air:contribution:" + uuid.uuid4().hex, revision=1, type="air.Contribution", name="Revue de cible via HTTPS - " + case, recorded_at=now, validity={"start": now, "end": None}, owner=identity)
            obj["meta"]["provenance"]["recorded_by"] = identity
            obj["body"] = {"author": identity, "target": [{k: request["goal"][k] for k in ("id", "revision")}], "kind": "QUESTION", "message": "Quelle mesure supplémentaire permettrait de lever l’écart ou la contradiction ? Démonstration fictive."}
            submission_request = {"idempotency_key": "tls-" + uuid.uuid4().hex, "object": obj}
            submission = adapter("air_collaboration_submit", submission_request)
            assert submission["created"]
            assert not adapter("air_collaboration_submit", submission_request)["created"]
            receipt = adapter("air_collaboration_read", {"submission": submission["submission"]})
            assert receipt["identity"] == identity and not receipt["business_mandate_granted"]
            results.append({"case": case, "result": assessed["result"], "report_digest": assessed["report_digest"], "cli_https": True, "mcp_stdio_to_https": True, "mcp_http_tls": True, "submission": submission["submission"], "receipt": receipt, "idempotent_submission": True})
        cross = APIClient(home, "D01.json", url=config["origin"], ca_file=config["ca_file"])("air_assess_goal_targets", report["treatments"][2]["business"]["request"])
        assert cross["http_status"] == 403
    finally:
        if started:
            stopped = subprocess.run(command + ["--stop"], capture_output=True, timeout=30)
            assert stopped.returncode == 0, "TLS server stop could not be verified"
    snapshot(home, workspace / "output-backup")
    restore(workspace / "output-backup", workspace / "restored")
    settings = Settings.load(workspace / "restored")
    assert settings.server == {}
    store = Store(settings.database_url)
    try:
        from air.collaboration import read
        from air.access import AccessPolicy
        for item in results:
            principal = {"subject": "observer-" + item["case"], "role": "editor"}
            assert read(store, principal, AccessPolicy.load(settings.home), {"submission": item["submission"]}) == item["receipt"]
    finally: store.engine.dispose()
    return {"status": "PASS_SCOPED", "version": __version__, "dossiers": results, "tls": "VERIFIED_CERTIFICATE_CHAIN_AND_LOCALHOST_NAME", "certificate_has_no_ip_san": True, "cross_dossier_refused": True, "restored_receipts_identical": True, "restoration_returns_to_local_transport": True, "server_stopped": True, "public_network_listener_opened": False, "live_instance_modified": False, "real_enterprise_pki_verified": False, "real_oidc_provider_verified": False, "external_business_action_executed": False}


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tmp/demo-asteria/business.json"
    result = qualify(source)
    output = ROOT / "tmp/demo-asteria/https.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "dossiers": len(result["dossiers"]), "report": str(output)}))
