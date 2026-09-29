from copy import deepcopy
import json
from pathlib import Path
import pytest
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings
from air.storage import Store


def test_restore_preserves_revisions_audit_and_revokes_old_tokens(tmp_path, example):
    home = tmp_path / "source"
    bootstrap(home)
    config = Settings.load(home)
    store = Store(config.database_url)
    original = store.put(example, "architect")
    old = json.loads((home / "credentials.json").read_text(encoding="utf-8"))
    # WAL writes are included by sqlite3.backup, without stopping the source.
    backup = tmp_path / "snapshot"
    snapshot(home, backup)
    store.engine.dispose()
    assert not (backup / "credentials.json").exists()
    destination = tmp_path / "restored"
    result = restore(backup, destination)
    restored = Store(Settings.load(destination).database_url)
    try:
        assert restored.get(example["meta"]["id"], 1)["digest"] == original["digest"]
        assert restored.author({"id": example["meta"]["id"], "revision": 1}) == "architect"
        assert not restored.authenticate(old["access_token"])
        fresh = json.loads((destination / "credentials.json").read_text(encoding="utf-8"))
        assert restored.authenticate(fresh["access_token"])["role"] == "admin"
        assert Settings.load(destination).instance_id != config.instance_id
        assert result["old_tokens_revoked"]
    finally: restored.engine.dispose()
    with pytest.raises(ValueError): restore(backup, destination)
    with (backup / "air.db").open("ab") as stream: stream.write(b"corruption")
    with pytest.raises(ValueError): restore(backup, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_restore_invalidates_review_policy_and_refuses_external_override(tmp_path, monkeypatch):
    home = tmp_path / "source";bootstrap(home)
    (home / "access-policy.json").write_text(json.dumps({"version": "1", "subjects": {"reviewer": {"review": ["domain"]}}}), encoding="utf-8")
    backup = tmp_path / "backup";snapshot(home, backup)
    monkeypatch.setenv("AIR_DATABASE_URL", "sqlite:///elsewhere.db")
    with pytest.raises(ValueError): restore(backup, tmp_path / "wrong")
    monkeypatch.delenv("AIR_DATABASE_URL")
    restore(backup, tmp_path / "restored")
    policy = json.loads((tmp_path / "restored/access-policy.json").read_text(encoding="utf-8"))
    assert policy["version"].startswith("restore-")
    assert policy["subjects"]["reviewer"]["review"] == ["domain"]
