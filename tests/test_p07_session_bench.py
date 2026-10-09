"""The attended-session bench stays isolated, and evidence reads only completed client calls."""
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def bench(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("p07_session_bench"), importlib.import_module("p07_session_evidence")


def fake_bench(root, home):
    root.mkdir(parents=True, exist_ok=True)
    (root / "bench.json").write_text(json.dumps({"home": str(home), "events": []}), encoding="utf-8")


def test_act_refuses_external_database_before_opening_a_store(tmp_path, monkeypatch, bench):
    module, _ = bench
    root = tmp_path / "bench"; home = root / module.HOME; home.mkdir(parents=True)
    (home / "config.json").write_text("{}", encoding="utf-8")
    fake_bench(root, home)
    monkeypatch.setenv("AIR_DATABASE_URL", "sqlite:///business.db")
    monkeypatch.setattr(module, "Store", lambda *a, **k: pytest.fail("a Store was opened"))
    with pytest.raises(ValueError, match="Unset AIR_DATABASE_URL"):
        module.act(root, "inspect")


def test_act_refuses_a_home_outside_the_bench(tmp_path, monkeypatch, bench):
    module, _ = bench
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    elsewhere = tmp_path / "user" / ".air"; elsewhere.mkdir(parents=True)
    (elsewhere / "config.json").write_text("{}", encoding="utf-8")
    root = tmp_path / "bench"
    fake_bench(root, elsewhere)
    monkeypatch.setattr(module, "Store", lambda *a, **k: pytest.fail("a Store was opened"))
    with pytest.raises(ValueError, match="private .air-p07 directory"):
        module.act(root, "revoke-token")


def test_prepare_refuses_existing_root_and_external_database(tmp_path, monkeypatch, bench):
    module, _ = bench
    monkeypatch.setenv("AIR_DATABASE_URL", "sqlite:///business.db")
    with pytest.raises(ValueError, match="Unset AIR_DATABASE_URL"):
        module.prepare(tmp_path / "new", "claude-code")
    monkeypatch.delenv("AIR_DATABASE_URL")
    (tmp_path / "used").mkdir()
    with pytest.raises(ValueError, match="already exists"):
        module.prepare(tmp_path / "used", "claude-code")


def test_act_refuses_database_redirect_in_local_configuration(tmp_path, monkeypatch, bench):
    module, _ = bench
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    root = tmp_path / "bench"; home = root / module.HOME; home.mkdir(parents=True)
    (home / "config.json").write_text(json.dumps({"config_version": 1, "instance_id": "fixture",
        "database_url": "sqlite:///business.db"}), encoding="utf-8")
    fake_bench(root, home)
    monkeypatch.setattr(module, "Store", lambda *a, **k: pytest.fail("a Store was opened"))
    with pytest.raises(ValueError, match="own SQLite registry"):
        module.act(root, "revoke-token")


@pytest.mark.parametrize("target", ["home", "database"])
def test_act_refuses_symlink_to_another_installation(tmp_path, monkeypatch, bench, target):
    module, _ = bench
    monkeypatch.delenv("AIR_DATABASE_URL", raising=False)
    root = tmp_path / "bench"; root.mkdir()
    elsewhere = tmp_path / "elsewhere"; elsewhere.mkdir()
    home = root / module.HOME
    try:
        if target == "home":
            home.symlink_to(elsewhere, target_is_directory=True)
        else:
            home.mkdir()
            external_db = elsewhere / "air.db"; external_db.write_bytes(b"preserve")
            (home / "air.db").symlink_to(external_db)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this host")
    (home / "config.json").write_text(json.dumps({"config_version": 1, "instance_id": "fixture"}), encoding="utf-8")
    fake_bench(root, home)
    monkeypatch.setattr(module, "Store", lambda *a, **k: pytest.fail("a Store was opened"))
    with pytest.raises(ValueError):
        module.act(root, "revoke-token")


def row(kind, stamp, item):
    return {"type": kind, "timestamp": stamp, "message": {"content": [item]}}


def test_phases_split_completed_calls_by_operator_gesture(bench):
    _, evidence = bench
    rows = [row("assistant", "2026-09-27T12:00:01Z", {"type": "tool_use", "id": "a", "name": "mcp__air__air_whoami", "input": {}}),
            row("user", "2026-09-27T12:00:02Z", {"type": "tool_result", "tool_use_id": "a", "content": '{"subject": "s"}'}),
            row("assistant", "2026-09-27T12:00:11Z", {"type": "tool_use", "id": "b", "name": "mcp__air__air_get", "input": {"id": "urn:x", "revision": 1}}),
            row("user", "2026-09-27T12:00:12Z", {"type": "tool_result", "tool_use_id": "b", "is_error": True,
                                                "content": '{"error": "AIR_UNAUTHENTICATED", "http_status": 401}'}),
            # Model prose claiming a result is not a call.
            row("assistant", "2026-09-27T12:00:13Z", {"type": "text", "text": "air_get returned the object"})]
    events = [{"action": "expire-token", "at": evidence.epoch("2026-09-27T12:00:10Z")}]
    split = evidence.phases(rows, events, evidence.epoch("2026-09-27T12:00:00Z"))
    assert [c["tool"] for c in split["connected"]] == ["air_whoami"]
    expired = next(v for k, v in split.items() if k.startswith("expire-token"))
    assert expired == [{"tool": "air_get", "arguments": {"id": "urn:x", "revision": 1},
                        "result": {"error": "AIR_UNAUTHENTICATED", "http_status": 401}}]
