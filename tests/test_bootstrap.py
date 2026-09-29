import json
from pathlib import Path
import subprocess
import sys
from air.cli import bootstrap, main
from air.config import Settings
from air.storage import Store
from conftest import ROOT


def test_bootstrap_idempotency_and_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    home = tmp_path / "air"
    result = bootstrap(home)
    first = (home / "credentials.json").read_bytes()
    assert result["database"] == "sqlite"
    assert bootstrap(home)["status"] == "ready"
    assert (home / "credentials.json").read_bytes() == first
    assert main(["--home", str(home), "doctor"]) == 0
    assert main(["validate", str(ROOT / "examples/scope.json")]) == 0
    assert main(["--home", str(home), "token-create", "--subject", "guest", "--name", "guest.json"]) == 0
    assert main(["--home", str(home), "token-create", "--subject", "guest", "--name", "../bad.json"]) == 1
    token = json.loads(first)["access_token"]
    captured = capsys.readouterr()
    assert token not in captured.out + captured.err


def test_real_installer_idempotency(tmp_path, monkeypatch):
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    home = tmp_path / "installed"
    command = [sys.executable, str(ROOT / "scripts/install.py"), "--skip-install", "--venv", str(Path(sys.executable).parents[1]), "--home", str(home)]
    first = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stderr
    credential = (home / "credentials.json").read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert second.returncode == 0, second.stderr
    assert credential == (home / "credentials.json").read_bytes()
    assert json.loads(credential)["access_token"] not in first.stdout + second.stdout
