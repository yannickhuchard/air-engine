from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from sqlalchemy import select, func
from air import artifacts, view_capture
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.core import AUDIENCE_PROFILE, DATA_TYPES, digest, validate
from air.foundation import exact, InvalidModel
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict, artifact_blobs, service_records
from test_audience import prepare


def setup(store, tmp_path):
    user, source, viewpoint, objects = prepare(store, tmp_path)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='business-test')
    request = {'id': 'urn:asteria:view:sav', 'revision': 1, 'name': 'Captured business view',
        **source, 'idempotency_key': 'capture-sav'}
    return settings, user, request, objects


def test_view_capture_atomic_identity_artifacts_and_historical_replay(store, tmp_path, monkeypatch):
    settings, user, request, objects = setup(store, tmp_path)
    result = view_capture.capture(store, user, AccessPolicy(), settings, request)
    assert result['created'] and result['output']['source_context_required']
    obj = result['view']['object'];pin = {**exact(obj), 'digest': result['view']['digest']}
    assert obj['meta']['type'] == 'air.View' and validate(obj)['valid']
    from importlib import resources
    expected_components = {'air/' + path.name for path in resources.files('air').iterdir()
                           if path.name.endswith('.py') and path.is_file()}
    assert {item['name'] for item in obj['body']['generator']['components']} == expected_components
    assert 'air.View' not in DATA_TYPES and obj['body']['generator']['source_observation'] == 'MODULE_STARTUP'
    before = store.counts(), store.audit_log()
    def unavailable(*args): raise AssertionError('Historical capture must not call the current generator')
    monkeypatch.setattr(view_capture, 'compile_view', unavailable)
    replay = view_capture.capture(store, user, AccessPolicy(), settings, request)
    assert not replay.pop('created');assert replay == {k: v for k, v in result.items() if k != 'created'}
    assert view_capture.read(store, user, AccessPolicy(), {'view': pin}) == replay
    assert (store.counts(), store.audit_log()) == before
    assert artifacts.download(store, user, AccessPolicy(), {'artifact': result['output']['artifact']})[1].startswith(b'<!doctype html>')
    assert obj['body']['output']['media_type'] == 'text/html' and obj['body']['source_mapping']['media_type'] == 'application/json'
    with pytest.raises(InvalidModel): store.put(obj, 'forged')
    with pytest.raises(InvalidModel): store.put_bundle([obj], 'forged')
    with store.engine.connect() as conn:
        artifacts.verify_artifacts(store, conn);view_capture.verify_views(store, conn)


def test_view_capture_idempotency_and_concurrent_writers(store, tmp_path):
    settings, user, request, objects = setup(store, tmp_path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: view_capture.capture(store, user, AccessPolicy(), settings, request), range(3)))
    assert sum(r['created'] for r in results) == 1
    assert all(r['capture'] == results[0]['capture'] for r in results)
    with pytest.raises(Conflict): view_capture.capture(store, user, AccessPolicy(), settings, {**request, 'id': 'urn:other:view'})
    with pytest.raises(Conflict): view_capture.capture(store, user, AccessPolicy(), settings, {**request, 'idempotency_key': 'other'})
    with pytest.raises(Conflict): view_capture.capture(store, user, AccessPolicy(), settings, {**request, 'name': 'Changed title'})


def test_view_capture_rolls_back_all_artifacts_view_and_guards(store, tmp_path, monkeypatch):
    settings, user, request, objects = setup(store, tmp_path)
    counts = store.counts(), store.audit_log();original = store._record_once
    def fail(conn, identifier, kind, *args, **kwargs):
        if kind == 'view_capture': raise RuntimeError('injected receipt failure')
        return original(conn, identifier, kind, *args, **kwargs)
    monkeypatch.setattr(store, '_record_once', fail)
    with pytest.raises(RuntimeError): view_capture.capture(store, user, AccessPolicy(), settings, request)
    assert (store.counts(), store.audit_log()) == counts
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 0
        assert conn.scalar(select(func.count()).select_from(service_records).where(service_records.c.kind.in_(['artifact_manifest', 'artifact_context', 'view_capture', 'view_capture_key']))) == 0


@pytest.mark.parametrize('revoke', ['policy', 'token'])
def test_view_capture_rechecks_authorization_after_compilation(store, tmp_path, monkeypatch, revoke):
    settings, user, request, objects = setup(store, tmp_path)
    original = view_capture.compile_view
    def changed(*args):
        result = original(*args)
        if revoke == 'policy': (tmp_path / 'access-policy.json').write_text(json.dumps({'version': 'deny', 'subjects': {}}), encoding='utf-8')
        else: store.revoke_token(user['authorization']['token_id'])
        return result
    monkeypatch.setattr(view_capture, 'compile_view', changed)
    with pytest.raises(Forbidden): view_capture.capture(store, user, AccessPolicy(), settings, request)
    with store.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 0


def test_captured_bytes_require_the_entire_source_context(store, tmp_path):
    settings, user, request, objects = setup(store, tmp_path)
    extra = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Scope'))
    extra['meta'].update(id='urn:asteria:shared:context', namespace='asteria.shared')
    store.put(extra, 'fixture')
    source = store.export_baseline(request['baseline']);meta = deepcopy(source['baseline']['meta']);meta['revision'] = 2
    base = store.create_baseline({'meta': meta, 'profile': AUDIENCE_PROFILE, 'members': [exact(o) for o in objects + [extra]], 'parent_baselines': [exact(source['baseline'])]}, 'fixture')
    request['baseline'] = {**exact(base['baseline']), 'digest': base['digest']}
    result = view_capture.capture(store, user, AccessPolicy(), settings, request)
    actor = {'subject': 'reader', 'role': 'reader'}
    namespace = result['view']['object']['meta']['namespace']
    policy = AccessPolicy({'version': 'restricted', 'subjects': {'reader': {'read': [namespace]}}})
    lookup = {'artifact': result['output']['artifact']}
    with pytest.raises(Forbidden): artifacts.describe(store, actor, policy, lookup)
    with pytest.raises(Forbidden): artifacts.download(store, actor, policy, lookup)
    allowed = AccessPolicy({'version': 'allowed', 'subjects': {'reader': {'read': [namespace, 'asteria.shared']}}})
    assert artifacts.download(store, actor, allowed, lookup)[1].startswith(b'<!doctype html>')


def test_captured_artifacts_fail_closed_when_context_guard_is_missing(store, tmp_path):
    settings, user, request, objects = setup(store, tmp_path)
    result = view_capture.capture(store, user, AccessPolicy(), settings, request)
    with store.write() as conn:
        conn.execute(service_records.delete().where(service_records.c.id == artifacts.context_guard_id(result['output']['artifact']['id'])))
    with pytest.raises(InvalidModel, match='context'): artifacts.download(store, user, AccessPolicy(), {'artifact': result['output']['artifact']})
    with store.engine.connect() as conn:
        with pytest.raises(InvalidModel): artifacts.verify_artifacts(store, conn)
        with pytest.raises(InvalidModel): view_capture.verify_views(store, conn)


def test_view_capture_registry_transfer_preserves_products_and_guards(store, tmp_path):
    settings, user, request, objects = setup(store, tmp_path)
    result = view_capture.capture(store, user, AccessPolicy(), settings, request)
    pin = {**exact(result['view']['object']), 'digest': result['view']['digest']}
    bundle = tmp_path / 'capture-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'restored.db').as_posix();import_registry(bundle, url)
    target = Store(url)
    try:
        restored = view_capture.read(target, user, AccessPolicy(), {'view': pin})
        assert restored == {k: v for k, v in result.items() if k != 'created'}
        assert artifacts.download(target, user, AccessPolicy(), {'artifact': result['output']['artifact']})[1] == artifacts.download(store, user, AccessPolicy(), {'artifact': result['output']['artifact']})[1]
    finally: target.engine.dispose()


@pytest.mark.parametrize('damage', ['mapping', 'active_html'])
def test_capture_rejects_inconsistent_generator_output_atomically(store, tmp_path, monkeypatch, damage):
    import hashlib
    settings, user, request, objects = setup(store, tmp_path)
    original = view_capture.compile_view;before = store.counts(), store.audit_log()
    def broken(*args):
        result = original(*args)
        if damage == 'mapping': result['source_mapping'][0]['object']['digest'] = 'sha256:' + '0' * 64
        else:
            result['content'] += '<script>window.bad=true</script>'
            result['content_digest'] = 'sha256:' + hashlib.sha256(result['content'].encode()).hexdigest()
        return result
    monkeypatch.setattr(view_capture, 'compile_view', broken)
    with pytest.raises(InvalidModel): view_capture.capture(store, user, AccessPolicy(), settings, request)
    assert (store.counts(), store.audit_log()) == before
    with store.engine.connect() as conn: assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 0


def test_view_capture_api_and_mcp_managed_writes(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    settings, user, request, objects = setup(store, tmp_path)
    token = store.create_token(user['subject'], 'editor');auth = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        assert client.post('/v1/views/capture', json=request).status_code == 401
        response = client.post('/v1/views/capture', json=request, headers=auth)
        assert response.status_code == 200, response.text
        result = response.json();assert result['created']
        pin = {**exact(result['view']['object']), 'digest': result['view']['digest']}
        assert client.post('/v1/drafts', json=result['view']['object'], headers=auth).status_code == 422
        replay = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_read_captured_view', 'arguments': {'view': pin}}}, headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert replay.status_code == 200 and replay.json()['result']['structuredContent'] == {k: v for k, v in result.items() if k != 'created'}


def test_view_capture_sqlite_backup_restore_preserves_history(tmp_path):
    from air.backup import snapshot, restore
    home = tmp_path / 'home';home.mkdir()
    (home / 'config.json').write_text(json.dumps({'config_version': 1, 'instance_id': 'business-test', 'auth': {'mode': 'local'}}), encoding='utf-8')
    settings = Settings.load(home);source = Store(settings.database_url)
    try:
        source.migrate();settings, user, request, objects = setup(source, home)
        old_token = source.create_token('historical-reader', 'reader')
        result = view_capture.capture(source, user, AccessPolicy(), settings, request)
        pin = {**exact(result['view']['object']), 'digest': result['view']['digest']}
        snapshot(home, tmp_path / 'backup')
    finally: source.engine.dispose()
    restore(tmp_path / 'backup', tmp_path / 'restored')
    restored_settings = Settings.load(tmp_path / 'restored');target = Store(restored_settings.database_url)
    try:
        assert restored_settings.instance_id != settings.instance_id
        assert not target.authenticate(old_token['access_token'])
        assert view_capture.read(target, user, AccessPolicy(), {'view': pin}) == {k: v for k, v in result.items() if k != 'created'}
    finally: target.engine.dispose()


def test_captured_sqlite_products_import_into_selected_backend(store, tmp_path):
    from air.storage import metadata
    source = Store('sqlite:///' + (tmp_path / 'source.db').as_posix())
    try:
        source.migrate();settings, user, request, objects = setup(source, tmp_path)
        result = view_capture.capture(source, user, AccessPolicy(), settings, request)
        pin = {**exact(result['view']['object']), 'digest': result['view']['digest']}
        bundle = tmp_path / 'source-transfer';export_registry(source, bundle)
        metadata.drop_all(store.engine)
        import_registry(bundle, store.engine.url.render_as_string(hide_password=False))
        assert view_capture.read(store, user, AccessPolicy(), {'view': pin}) == {k: v for k, v in result.items() if k != 'created'}
    finally: source.engine.dispose()
