import json
import os
from pathlib import Path
import sys

import pytest

from air.cli import bootstrap,main
from air.config import Settings
from air.storage import Store
from air.workstation import inspect


def test_private_default_home_is_checked_without_exposing_credentials(tmp_path,capsys):
    home = tmp_path/'home';bootstrap(home)
    token = json.loads((home/'credentials.json').read_text())['access_token']
    assert main(['--home',str(home),'workstation-check']) == 0
    result = json.loads(capsys.readouterr().out)
    assert all(result['checks'].values())
    assert token not in json.dumps(result) and str(home) not in json.dumps(result)
    assert not result['runtime_listener_verified'] and not result['backup_recency_verified']


def test_missing_home_is_not_created(tmp_path):
    home = tmp_path/'absent'
    assert inspect(home)['status'] == 'FAILED'
    assert not home.exists()


def test_revoked_credential_never_passes(tmp_path):
    home = tmp_path/'home';bootstrap(home)
    settings = Settings.load(home);store = Store(settings.database_url)
    try: store.revoke_token(json.loads((home/'credentials.json').read_text())['token_id'])
    finally: store.engine.dispose()
    assert not inspect(home)['checks']['credential_valid']


def test_wrong_backend_does_not_connect_or_load_token(tmp_path,monkeypatch):
    home = tmp_path/'home';bootstrap(home)
    monkeypatch.setenv('AIR_DATABASE_URL','postgresql+psycopg://example.invalid/unused')
    result = inspect(home)
    assert not result['checks']['sqlite_in_private_home']
    assert not result['checks']['credential_valid']


def test_unprotected_home_refuses_to_read_configuration(tmp_path,monkeypatch):
    import air.workstation as workstation
    home = tmp_path/'home';bootstrap(home)
    monkeypatch.setattr(workstation,'private_paths',lambda _:False)
    monkeypatch.setattr(Settings,'load',lambda _:pytest.fail('Must not read private config before checking permissions'))
    assert inspect(home)['status']=='FAILED'


def test_shared_credential_permissions_are_rejected(tmp_path):
    import subprocess
    home = tmp_path/'home';bootstrap(home);credential = home/'credentials.json'
    if os.name == 'nt':
        subprocess.run(['icacls',str(credential),'/grant','*S-1-1-0:R'],capture_output=True,check=True)
    else: credential.chmod(0o644)
    try: assert not inspect(home)['checks']['private_storage']
    finally:
        if os.name == 'nt': subprocess.run(['icacls',str(credential),'/remove:g','*S-1-1-0'],capture_output=True,check=True)
        else: credential.chmod(0o600)


def test_malformed_token_cannot_pass(tmp_path):
    home = tmp_path/'home';bootstrap(home)
    (home/'credentials.json').write_text('{"access_token":true}')
    assert not inspect(home)['checks']['credential_valid']


def test_real_http_restore_when_source_home_unavailable(tmp_path):
    scripts = str(Path(__file__).resolve().parents[1]/'scripts')
    sys.path.insert(0,scripts)
    try:
        from qualify_workstation import qualify_local
        result = qualify_local(tmp_path)
    finally: sys.path.remove(scripts)
    assert result['status']=='PASS_SCOPED',result['checks']
    assert result['checks']['restore_without_source'] and result['checks']['post_snapshot_change_absent']
    assert not result['physical_device_loss_tested'] and not result['independent_operator']
