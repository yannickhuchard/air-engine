import io
import json
import os
from pathlib import Path

import pytest

from air.backup import snapshot, restore, validate_backup
from air import backup_crypto as crypt
from air.cli import bootstrap, main
from air.config import Settings
from air.storage import Store


@pytest.fixture
def encrypted_fixture(tmp_path, example):
    home = tmp_path/'home'
    bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try: saved = store.put(example, 'operator')
    finally: store.engine.dispose()
    snapshot(home, tmp_path/'backup')
    key = Path(crypt.create_key(tmp_path/'keys')['key_file'])
    crypt.encrypt(tmp_path/'backup', tmp_path/'encrypted', key)
    return home, key, saved


def test_encrypted_roundtrip_streaming_restores_digest_and_revokes_identity(tmp_path, encrypted_fixture, example, monkeypatch):
    home, key, saved = encrypted_fixture
    monkeypatch.setattr(crypt, 'BLOCK', 127)
    crypt.encrypt(tmp_path/'backup', tmp_path/'second', key)
    assert (tmp_path/'second/snapshot.airenc').read_bytes() != (tmp_path/'encrypted/snapshot.airenc').read_bytes()
    assert [p.name for p in (tmp_path/'second').iterdir()] == ['snapshot.airenc']
    assert crypt.decrypt(tmp_path/'second', tmp_path/'decrypted', key)['authenticated']
    restore(tmp_path/'decrypted', tmp_path/'restored')
    store = Store(Settings.load(tmp_path/'restored').database_url)
    try:
        assert store.get(example['meta']['id'], 1)['digest'] == saved['digest']
        token = json.loads((home/'credentials.json').read_text(encoding='utf-8'))['access_token']
        assert not store.authenticate(token)
    finally: store.engine.dispose()


@pytest.mark.parametrize('damage', ['wrong_key','header','ciphertext','tag','truncate','append'])
def test_authentication_failure_never_parses_or_publishes(tmp_path, encrypted_fixture, monkeypatch, damage):
    _, key, _ = encrypted_fixture
    path = tmp_path/'encrypted/snapshot.airenc'
    data = bytearray(path.read_bytes())
    if damage == 'wrong_key': key = crypt.create_key(tmp_path/'wrong-key')['key_file']
    elif damage == 'header': data[len(crypt.MAGIC)] ^= 1
    elif damage == 'ciphertext': data[crypt.HEADER_SIZE+10] ^= 1
    elif damage == 'tag': data[-1] ^= 1
    elif damage == 'truncate': data = data[:-3]
    else: data.extend(b'extra')
    path.write_bytes(data)
    def forbidden(*_): pytest.fail('Unauthenticated content was parsed')
    monkeypatch.setattr(crypt, 'unpack_authenticated', forbidden)
    with pytest.raises(ValueError): crypt.decrypt(tmp_path/'encrypted', tmp_path/'invalid', key)
    assert not (tmp_path/'invalid').exists()
    assert all(not list(p.iterdir()) for p in tmp_path.glob('invalid.pending-*'))


@pytest.mark.parametrize('damage', ['traversal','duplicate','oversize','boolean_size'])
def test_authenticated_catalog_is_bounded_and_paths_are_fixed(tmp_path, damage):
    entries = [{'name':name, 'bytes':0, 'sha256':'0'*64} for name in sorted(crypt.MANDATORY)]
    if damage == 'traversal': entries[0]['name'] = '../escape'
    elif damage == 'duplicate': entries[0]['name'] = entries[1]['name']
    elif damage == 'oversize': entries[0]['bytes'] = crypt.MAX_BYTES + 1
    else: entries[0]['bytes'] = True
    payload = json.dumps({'format':'air.backup-payload/1','files':entries}).encode()
    with pytest.raises(ValueError): crypt.unpack_authenticated(io.BytesIO(len(payload).to_bytes(4,'big')+payload), tmp_path)
    assert not list(tmp_path.iterdir())


def test_key_generation_is_exclusive_and_cli_never_outputs_secret(tmp_path, capsys):
    main(['backup-keygen', str(tmp_path/'keys')])
    output = capsys.readouterr().out
    key = (tmp_path/'keys/backup.key').read_bytes()
    assert len(crypt.read_key(tmp_path/'keys/backup.key')) == 32
    assert key.hex() not in output and json.loads(output)['key_contents_displayed'] is False
    with pytest.raises(FileExistsError): crypt.create_key(tmp_path/'keys')
    assert (tmp_path/'keys/backup.key').read_bytes() == key


def test_key_rejects_shared_permissions_and_wrong_size(tmp_path):
    path = Path(crypt.create_key(tmp_path/'keys')['key_file'])
    path.write_bytes(b'short')
    with pytest.raises(ValueError, match='32 bytes'): crypt.read_key(path)
    shared = tmp_path/'shared.key';shared.write_bytes(os.urandom(32))
    if os.name != 'nt': shared.chmod(0o644)
    else:
        import subprocess
        # The PostgreSQL qualifier protects its whole workspace. Make this synthetic key
        # explicitly shared instead of assuming inherited permissions are permissive.
        subprocess.run(['icacls', str(shared), '/grant', '*S-1-1-0:R'], check=True, capture_output=True)
    with pytest.raises(ValueError, match='permissions|private'): crypt.read_key(shared)


def test_existing_destination_and_key_inside_backup_are_refused(tmp_path, encrypted_fixture):
    _, key, _ = encrypted_fixture
    original = (tmp_path/'encrypted/snapshot.airenc').read_bytes()
    with pytest.raises(ValueError, match='new destination'): crypt.encrypt(tmp_path/'backup', tmp_path/'encrypted', key)
    assert (tmp_path/'encrypted/snapshot.airenc').read_bytes() == original
    embedded = crypt.create_key(tmp_path/'backup/keys')['key_file']
    with pytest.raises(ValueError, match='outside'): crypt.encrypt(tmp_path/'backup', tmp_path/'other', embedded)


def test_backup_manifest_refuses_unknown_file_names_before_reading(tmp_path):
    manifest = {'format':'air.sqlite-backup/1', 'schema':6, 'files':{'../escape':'sha256:'+'0'*64}}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='manifest'): validate_backup(tmp_path)
