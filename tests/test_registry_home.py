import json
import pytest
from air.access import AccessPolicy
from air.cli import bootstrap, main
from air.config import Settings
from air.portability import export_registry, import_home
from air.storage import Store


def test_cli_transfer_to_new_home_preserves_policy_and_issues_new_identity(tmp_path, example, capsys):
    source = tmp_path / 'source';bootstrap(source)
    settings = Settings.load(source)
    store = Store(settings.database_url)
    old = json.loads((source / 'credentials.json').read_text())
    policy = {'version': '1', 'subjects': {'local-admin': {'read': ['*'], 'write': ['*']}, 'reviewer': {'review': ['domain']}}}
    (source / 'access-policy.json').write_text(json.dumps(policy))
    try:
        original = store.put(example, 'architect')
        bundle = tmp_path / 'bundle'
        assert main(['--home', str(source), 'registry-export', str(bundle)]) == 0
        target = tmp_path / 'target'
        assert main(['--home', str(target), 'registry-import', str(bundle)]) == 0
        restored = Store(Settings.load(target).database_url)
        try:
            assert restored.get(example['meta']['id'], 1)['digest'] == original['digest']
            assert not restored.authenticate(old['access_token'])
            fresh = json.loads((target / 'credentials.json').read_text())
            assert restored.authenticate(fresh['access_token'])['subject'] == 'local-admin'
            assert fresh['access_token'] not in capsys.readouterr().out
            assert Settings.load(target).instance_id != settings.instance_id
            restored_policy = AccessPolicy.load(target)
            assert restored_policy.document['subjects'] == policy['subjects']
            assert restored_policy.document['version'].startswith('import-')
            assert main(['--home', str(target), 'doctor']) == 0
        finally: restored.engine.dispose()
        assert store.authenticate(old['access_token'])
        with pytest.raises(ValueError, match='new AIR home'): import_home(bundle, target)
    finally: store.engine.dispose()


def test_import_refuses_environment_ambiguity_and_missing_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('AIR_DATABASE_URL', 'postgresql+psycopg://unused')
    with pytest.raises(ValueError, match='Unset AIR_DATABASE_URL'):
        import_home(tmp_path / 'bundle', tmp_path / 'target')
    monkeypatch.delenv('AIR_DATABASE_URL')
    monkeypatch.delenv('AIR_TARGET_DATABASE_URL', raising=False)
    assert main(['--home', str(tmp_path / 'target'), 'registry-import', str(tmp_path / 'bundle'), '--target-database-env', 'AIR_TARGET_DATABASE_URL']) == 1
    assert not (tmp_path / 'target').exists()


def test_postgres_home_never_silently_falls_back_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv('AIR_DATABASE_URL', raising=False)
    config = {'config_version': 1, 'instance_id': 'synthetic', 'database_backend': 'postgresql'}
    (tmp_path / 'config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError, match='required'): Settings.load(tmp_path)
    monkeypatch.setenv('AIR_DATABASE_URL', 'sqlite:///unintended.db')
    with pytest.raises(ValueError, match='differs'): Settings.load(tmp_path)
    monkeypatch.setenv('AIR_DATABASE_URL', 'postgresql+psycopg://localhost/test')
    assert Settings.load(tmp_path).database_url.startswith('postgresql')
