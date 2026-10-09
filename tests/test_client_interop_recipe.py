"""Local recipes must stay isolated and cannot certify native/human acceptance."""
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def recipes(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return (importlib.import_module("qualify_client_interop"),
            importlib.import_module("qualify_native_design"))


@pytest.mark.parametrize("index", [0, 1])
def test_external_database_rejected_before_creating_workspace(tmp_path, monkeypatch, recipes, index):
    monkeypatch.setenv("AIR_DATABASE_URL", "sqlite:///existing-business.db")
    root = tmp_path / "unused"
    args = (root,) if index == 0 else (root, "codex")
    with pytest.raises(ValueError, match="Unset AIR_DATABASE_URL"):
        recipes[index].qualify(*args)
    assert not root.exists()


def test_real_process_exchange_expiry_and_recovery(tmp_path, monkeypatch, recipes):
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    report = recipes[0].qualify(tmp_path)
    assert report["status"] == "PASS_SCOPED"
    assert all(report["checks"].values())
    assert report["checks"]["conflict_refused_atomically"]
    assert report["checks"]["expiry_refuses_cached_reference"]
    assert report["checks"]["outage_never_returns_cached_data"]
    assert report["checks"]["network_recovery_same_process"]
    assert report["independent_registries"] == 2
    assert report["physical_devices"] == 1
    assert report["servers_stopped"] and report["adapters_stopped"]
    assert not any(report[key] for key in (
        "native_clients_qualified", "human_review_performed", "p07_received", "production_ready"))
