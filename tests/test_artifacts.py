import base64
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, inspect
from fastapi.testclient import TestClient
from air import artifacts
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.backup import checksum
from air.config import Settings
from air.foundation import InvalidModel
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict, artifact_blobs, artifact_chunks, service_records, metadata, versions


def setup(store, tmp_path):
    token = store.create_token('uploader', 'editor')
    principal = store.authenticate(token['access_token'], True)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test')
    principal['authorization']['instance_id'] = settings.instance_id
    return settings, principal, token, AccessPolicy(), {'idempotency_key': 'sample', 'namespace': 'asteria.sav', 'media_type': 'application/octet-stream'}


def test_artifact_chunked_idempotence_and_deduplication(store, tmp_path):
    settings, user, token, policy, request = setup(store, tmp_path)
    data = bytes(range(256)) * 2048 + b'end'
    first = artifacts.put(store, user, policy, settings, request, data)
    assert first['created'] and not first['evidence_qualified']
    assert not artifacts.put(store, user, policy, settings, request, data)['created']
    second = artifacts.put(store, user, policy, settings, {**request, 'namespace': 'asteria.iam'}, data)
    assert second['artifact'] != first['artifact'] and second['content_digest'] == first['content_digest']
    lookup = {'artifact': first['artifact']}
    assert artifacts.download(store, user, policy, lookup)[1] == data
    with pytest.raises(InvalidModel, match='512 KiB'): artifacts.read_base64(store, user, policy, lookup)
    with pytest.raises(Conflict): artifacts.put(store, user, policy, settings, request, b'changed')
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 1
        assert conn.scalar(select(func.count()).select_from(artifact_chunks)) == 3
        artifacts.verify_artifacts(store, conn)
    restricted = AccessPolicy({'version': 'scoped', 'subjects': {'uploader': {'read': ['asteria.sav']}}})
    with pytest.raises(Forbidden): artifacts.download(store, user, restricted, {'artifact': second['artifact']})


def test_artifact_atomic_rollback_and_concurrent_replay(store, tmp_path, monkeypatch):
    settings, user, token, policy, request = setup(store, tmp_path)
    original = store._record_once
    def fail(*args, **kwargs): raise RuntimeError('injected receipt failure')
    monkeypatch.setattr(store, '_record_once', fail)
    with pytest.raises(RuntimeError): artifacts.put(store, user, policy, settings, request, b'atomic')
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 0
        assert conn.scalar(select(func.count()).select_from(artifact_chunks)) == 0
    monkeypatch.setattr(store, '_record_once', original)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: artifacts.put(store, user, policy, settings, request, b'atomic'), range(3)))
    assert sum(r['created'] for r in results) == 1
    assert all(r['artifact'] == results[0]['artifact'] for r in results)


def test_artifact_rechecks_identity_and_policy(store, tmp_path):
    settings, user, token, policy, request = setup(store, tmp_path)
    (tmp_path / 'access-policy.json').write_text(json.dumps({'version': 'deny', 'subjects': {}}), encoding='utf-8')
    with pytest.raises(Forbidden): artifacts.put(store, user, policy, settings, request, b'policy')
    (tmp_path / 'access-policy.json').unlink()
    store.revoke_token(token['token_id'])
    with pytest.raises(Forbidden): artifacts.put(store, user, policy, settings, request, b'token')


@pytest.mark.parametrize('size', [0, artifacts.MAX_SIZE + 1])
def test_artifact_binary_bounds(store, tmp_path, size):
    settings, user, token, policy, request = setup(store, tmp_path)
    with pytest.raises(InvalidModel): artifacts.put(store, user, policy, settings, request, b'x' * size)


def test_artifact_base64_and_manifest_pin(store, tmp_path):
    settings, user, token, policy, request = setup(store, tmp_path)
    for value in ('!', 'eA==\n', base64.b64encode(b'x' * (artifacts.JSON_MAX_SIZE + 1)).decode()):
        with pytest.raises(InvalidModel): artifacts.import_base64(store, user, policy, settings, {**request, 'content_base64': value})
    result = artifacts.import_base64(store, user, policy, settings, {**request, 'content_base64': 'eA=='})
    assert artifacts.read_base64(store, user, policy, {'artifact': result['artifact']})['content_base64'] == 'eA=='
    with pytest.raises(Conflict): artifacts.describe(store, user, policy, {'artifact': {**result['artifact'], 'digest': 'sha256:' + '0' * 64}})
    with pytest.raises(InvalidModel): artifacts.put(store, user, policy, settings, {**request, 'media_type': 'text/html; charset=utf-8'}, b'x')


@pytest.mark.parametrize('damage', ['bytes', 'gap', 'orphan'])
def test_artifact_integrity_rejects_corruption(store, tmp_path, damage):
    settings, user, token, policy, request = setup(store, tmp_path)
    result = artifacts.put(store, user, policy, settings, request, b'original')
    with store.write() as conn:
        if damage == 'bytes': conn.execute(artifact_chunks.update().values(payload=b'altered!'))
        elif damage == 'gap': conn.execute(artifact_chunks.delete())
        else: conn.execute(service_records.delete().where(service_records.c.kind == 'artifact_manifest'))
    with store.engine.connect() as conn:
        with pytest.raises(InvalidModel): artifacts.verify_artifacts(store, conn)
    if damage != 'orphan':
        with pytest.raises(InvalidModel): artifacts.download(store, user, policy, {'artifact': result['artifact']})


def test_artifact_transfer_roundtrip_and_semantic_tampering(store, tmp_path):
    settings, user, token, policy, request = setup(store, tmp_path)
    data = bytes(range(256)) * 1100
    result = artifacts.put(store, user, policy, settings, request, data)
    bundle = tmp_path / 'transfer';export_registry(store, bundle)
    target_url = 'sqlite:///' + (tmp_path / 'target.db').as_posix()
    import_registry(bundle, target_url)
    target = Store(target_url)
    try:
        assert artifacts.download(target, user, policy, {'artifact': result['artifact']})[1] == data
        assert not target.authenticate(token['access_token'])
    finally: target.engine.dispose()
    file = bundle / 'artifact_chunk.jsonl'
    rows = [json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()]
    rows[0]['payload']['base64'] = base64.b64encode(b'z' * artifacts.CHUNK_SIZE).decode()
    file.write_text(''.join(json.dumps(row) + chr(10) for row in rows), encoding='utf-8')
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    manifest['tables']['artifact_chunk'].update(bytes=file.stat().st_size, digest=checksum(file))
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    bad_url = 'sqlite:///' + (tmp_path / 'bad.db').as_posix()
    with pytest.raises(InvalidModel, match='checksum'): import_registry(bundle, bad_url)
    target = Store(bad_url)
    try: assert inspect(target.engine).get_table_names() == []
    finally: target.engine.dispose()


def test_artifact_sqlite_to_selected_backend(store, tmp_path):
    source = Store('sqlite:///' + (tmp_path / 'source.db').as_posix())
    try:
        source.migrate();settings, user, token, policy, request = setup(source, tmp_path)
        data = b'\x00\xffportable' * 32768
        result = artifacts.put(source, user, policy, settings, request, data)
        bundle = tmp_path / 'transfer';export_registry(source, bundle)
        metadata.drop_all(store.engine)
        import_registry(bundle, store.engine.url.render_as_string(hide_password=False))
        assert artifacts.download(store, user, policy, {'artifact': result['artifact']})[1] == data
    finally: source.engine.dispose()


def test_artifact_schema_five_upgrade_preserves_registry(store, example):
    saved = store.put(example, 'owner');token = store.create_token('operator', 'editor')
    artifact_chunks.drop(store.engine);artifact_blobs.drop(store.engine)
    with store.write() as conn: conn.execute(versions.update().values(version=5))
    store.migrate();store.check_version()
    assert store.get(example['meta']['id'], 1)['digest'] == saved['digest']
    assert store.authenticate(token['access_token'])
    with store.engine.connect() as conn: artifacts.verify_artifacts(store, conn)


def test_artifact_api_binary_json_permissions_and_mcp(store, tmp_path):
    settings, user, token, policy, request = setup(store, tmp_path)
    auth = {'Authorization': 'Bearer ' + token['access_token']}
    raw = {**auth, 'Content-Type': 'application/octet-stream', 'X-AIR-Namespace': request['namespace'], 'Idempotency-Key': 'api'}
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        assert client.post('/v1/artifacts/upload', content=b'x').status_code == 401
        reader = store.create_token('reader', 'reader')
        assert client.post('/v1/artifacts/upload', content=b'x', headers={**raw, 'Authorization': 'Bearer ' + reader['access_token']}).status_code == 403
        response = client.post('/v1/artifacts/upload', content=b'\x00\xffAPI', headers=raw)
        assert response.status_code in (200, 201), response.text
        result = response.json();lookup = {'artifact': result['artifact']}
        downloaded = client.post('/v1/artifacts/download', json=lookup, headers=auth)
        assert downloaded.content == b'\x00\xffAPI'
        assert downloaded.headers['x-content-type-options'] == 'nosniff'
        assert downloaded.headers['content-disposition'].startswith('attachment;')
        assert downloaded.headers['x-air-content-sha256'] == result['content_digest'].split(':')[1]
        assert client.post('/v1/artifacts/import', json={**request, 'content_base64': 'eA=='}, headers=auth).status_code in (200, 201)
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_read_artifact', 'arguments': lookup}}, headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.status_code == 200, mcp.text
        payload = mcp.json()['result']
        assert not payload.get('isError'), payload
        assert json.loads(payload['content'][0]['text'])['content_base64'] == base64.b64encode(downloaded.content).decode()


def test_artifact_restore_rejects_semantically_corrupt_backup(tmp_path):
    from air.backup import snapshot, restore
    home = tmp_path / 'source';home.mkdir()
    (home / 'config.json').write_text(json.dumps({'config_version': 1, 'instance_id': 'backup-artifact', 'auth': {'mode': 'local'}}), encoding='utf-8')
    settings = Settings.load(home);store = Store(settings.database_url)
    try:
        store.migrate();_, user, token, policy, request = setup(store, home)
        user['authorization']['instance_id'] = settings.instance_id
        artifacts.put(store, user, policy, settings, request, b'original')
        with store.write() as conn: conn.execute(artifact_chunks.update().values(payload=b'altered!'))
    finally: store.engine.dispose()
    snapshot(home, tmp_path / 'backup')
    target = tmp_path / 'restored'
    with pytest.raises(InvalidModel, match='checksum'): restore(tmp_path / 'backup', target)
    assert not target.exists()


def test_schema_five_transfer_without_artifacts(store, example, tmp_path):
    from air.storage import ARTIFACT_TABLES
    store.put(example, 'owner');bundle = tmp_path / 'old-transfer';export_registry(store, bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'));manifest['schema'] = 5
    for table in ARTIFACT_TABLES: manifest['tables'].pop(table.name)
    file = bundle / 'schema_version.jsonl';file.write_text(json.dumps({'id': 1, 'version': 5}) + chr(10), encoding='utf-8')
    manifest['tables']['schema_version'].update(bytes=file.stat().st_size, digest=checksum(file))
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    url = 'sqlite:///' + (tmp_path / 'upgraded.db').as_posix();result = import_registry(bundle, url)
    target = Store(url)
    try:
        assert result['source_schema'] == 5 and result['schema'] == 6
        assert target.get(example['meta']['id'], 1)['digest'] == store.get(example['meta']['id'], 1)['digest']
    finally: target.engine.dispose()
