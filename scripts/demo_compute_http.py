"""Replay planning and illustrative experiments through the real CLI/HTTP binding."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air.cli import bootstrap
from air.config import Settings
from air.storage import Store
from demo_planning import prepare
from demo_experiments import read, request_for
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    if os.environ.get("AIR_DATABASE_URL"): raise ValueError("Isolated computation rehearsal requires local SQLite")
    workspace = ROOT / "tmp" / ("air-compute-" + uuid.uuid4().hex)
    home = workspace / "home"
    bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        planning = prepare(store)
        experiments = [request_for(store, case) for case in read("manifest.json")["dossiers"]]
    finally: store.engine.dispose()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    start(Path(sys.executable), home, port)
    reports = []
    def execute(name, request, expected):
        file = workspace / (name + "-" + uuid.uuid4().hex + ".json")
        file.write_text(json.dumps(request), encoding="utf-8")
        result = subprocess.run([sys.executable, "-m", "air", "--home", str(home), name, str(file), "--port", str(port)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert result.returncode == expected, "Unexpected CLI exit status for " + name
        return json.loads(result.stdout)
    try:
        initial = execute("plan", planning, 1)
        assert initial["proposed"]["total_shortfall_FTE_weeks"] == "4"
        variant_request = deepcopy(planning);variant_request["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
        variant = execute("plan", variant_request, 0)
        assert variant == execute("plan", variant_request, 0)
        for i, request in enumerate(experiments):
            result = execute("simulate", request, 1 if i == 2 else 0)
            assert result == execute("simulate", request, 1 if i == 2 else 0)
            reports.append(result)
        return {"status": "PASS_SCOPED", "binding": "real CLI/HTTP", "initial": initial, "variant": variant,
                "experiments": reports, "replay_identical": True, "external_effects": False, "live_instance_modified": False}
    finally: stop(home)


if __name__ == "__main__":
    result = rehearse()
    output = ROOT / "tmp/demo-asteria/compute-http.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(output)}))
