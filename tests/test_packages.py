from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import digest
from air.foundation import exact, InvalidModel
from air.packages import prepare_package, publish_package, read_package, revoke_package, identifier
from air.storage import Conflict, service_records
from test_construction import construction, prepare, get


def context(store, objects):
    base, ref = prepare(store, objects)
    function = get(objects, 'Function')
    principal = {'subject': 'publisher', 'role': 'editor'}
    policy = AccessPolicy({'version': '1', 'subjects': {'publisher': {'read': ['*'], 'publish': ['*']}, 'reader': {'read': ['*']}}})
    request = {'idempotency_key': 'stage-1', 'package_id': 'urn:asteria:package:sav', 'version': 1,
        'baseline': ref['baseline'], 'exports': [{**exact(function), 'digest': digest(function)}], 'imports': [],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")}
    return principal, policy, request


def publish(store, principal, policy, request):
    stage = prepare_package(store, principal, policy, request)
    return publish_package(store, principal, policy, {'idempotency_key': 'commit-' + request['idempotency_key'], 'preparation': stage['preparation']})


def test_preparation_invisible_atomic_publication_and_exact_replay(store, construction):
    principal, policy, request = context(store, construction)
    stage = prepare_package(store, principal, policy, request)
    assert not stage['published']
    with store.engine.connect() as conn:
        assert not conn.execute(select(service_records).where(service_records.c.kind == 'package_publication')).all()
    reader = {'subject': 'reader', 'role': 'reader'}
    with pytest.raises(InvalidModel): read_package(store, reader, policy, {'publication': stage['preparation'], 'purpose': 'HISTORICAL'})
    command = {'idempotency_key': 'commit', 'preparation': stage['preparation']}
    result = publish_package(store, principal, policy, command)
    assert result['published'] and not result['authorization_granted']
    replay = publish_package(store, principal, policy, command)
    assert replay['publication'] == result['publication'] and not replay['created']
    view = read_package(store, reader, policy, {'publication': result['publication'], 'purpose': 'NEW_USE'})
    assert view['manifest']['exports'] == request['exports'] and view['new_use_allowed']
    assert view['manifest']['evidence_class'] == 'DESIGN_DRAFT'
    assert not view['remote_signature_verified']
    corrupted = deepcopy(result['publication']);corrupted['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): read_package(store, reader, policy, {'publication': corrupted, 'purpose': 'HISTORICAL'})


def test_failure_before_event_rolls_back_manifest_and_retry(store, construction, monkeypatch):
    principal, policy, request = context(store, construction)
    stage = prepare_package(store, principal, policy, request)
    command = {'idempotency_key': 'commit', 'preparation': stage['preparation']}
    original = store._record_once
    def fail(conn, record_id, kind, scope, actor, payload):
        if kind == 'package_event': raise RuntimeError('simulated process failure before commit')
        return original(conn, record_id, kind, scope, actor, payload)
    monkeypatch.setattr(store, '_record_once', fail)
    with pytest.raises(RuntimeError): publish_package(store, principal, policy, command)
    assert store.get_record(identifier('package', request['package_id'], 1)) is None
    assert not any(a['action'] == 'package_publication.recorded' for a in store.audit_log())
    monkeypatch.setattr(store, '_record_once', original)
    assert publish_package(store, principal, policy, command)['created']


def test_concurrent_commit_creates_one_manifest_and_event(store, construction):
    principal, policy, request = context(store, construction)
    stage = prepare_package(store, principal, policy, request)
    command = {'idempotency_key': 'commit', 'preparation': stage['preparation']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish_package(store, principal, policy, command), range(2)))
    assert sum(r['created'] for r in results) == 1
    assert results[0]['publication'] == results[1]['publication']
    with store.engine.connect() as conn:
        assert len(conn.execute(select(service_records).where(service_records.c.kind == 'package_event')).all()) == 1


def test_revocation_preserves_history_blocks_new_import_and_recursive_composition(store, construction):
    principal, policy, request = context(store, construction)
    first = publish(store, principal, policy, request)
    recursive = deepcopy(request);recursive.update(idempotency_key='recursive', version=2, imports=[first['publication']])
    with pytest.raises(InvalidModel, match='Recursive'): prepare_package(store, principal, policy, recursive)
    consumer = deepcopy(request);consumer.update(idempotency_key='consumer', package_id='urn:asteria:package:program', imports=[first['publication']])
    stage = prepare_package(store, principal, policy, consumer)
    revoke_package(store, principal, policy, {'publication': first['publication'], 'rationale': 'Synthetic withdrawal'})
    historic = read_package(store, principal, policy, {'publication': first['publication'], 'purpose': 'HISTORICAL'})
    assert not historic['new_use_allowed'] and historic['manifest']['baseline'] == request['baseline']
    with pytest.raises(InvalidModel, match='new use'): publish_package(store, principal, policy, {'idempotency_key': 'consumer', 'preparation': stage['preparation']})
    with pytest.raises(InvalidModel, match='new use'): read_package(store, principal, policy, {'publication': first['publication'], 'purpose': 'NEW_USE'})


def test_publish_permissions_policy_expiry_and_malformed_exports(store, construction, monkeypatch):
    principal, policy, request = context(store, construction)
    with pytest.raises(Forbidden): prepare_package(store, principal, AccessPolicy(), request)
    restricted = deepcopy(policy.document);restricted['subjects']['publisher']['publish'] = ['asteria.sav']
    with pytest.raises(Forbidden): prepare_package(store, principal, AccessPolicy(restricted), request)
    wrong = deepcopy(request);wrong['exports'][0]['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(InvalidModel): prepare_package(store, principal, policy, wrong)
    stage = prepare_package(store, principal, policy, request)
    changed = deepcopy(policy.document);changed['version'] = '2'
    command = {'idempotency_key': 'commit', 'preparation': stage['preparation']}
    with pytest.raises(InvalidModel, match='policy changed'): publish_package(store, principal, AccessPolicy(changed), command)
    class Future(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.now(timezone.utc) + timedelta(days=8)
    monkeypatch.setattr('air.packages.datetime', Future)
    with pytest.raises(InvalidModel, match='expired'): publish_package(store, principal, policy, command)


def test_package_api_uses_authenticated_publisher_and_closure_access(store, construction, tmp_path):
    principal, policy, request = context(store, construction)
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    token = store.create_token('publisher', 'editor')
    reader = store.create_token('reader', 'reader')
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post('/v1/packages/prepare', json=request).status_code == 401
        stage = client.post('/v1/packages/prepare', json=request, headers=headers)
        assert stage.status_code == 200
        command = {'idempotency_key': 'commit', 'preparation': stage.json()['preparation']}
        assert client.post('/v1/packages/publish', json=command, headers={'Authorization': 'Bearer ' + reader['access_token']}).status_code == 403
        published = client.post('/v1/packages/publish', json=command, headers=headers)
        assert published.status_code == 200
        body = {'publication': published.json()['publication'], 'purpose': 'HISTORICAL'}
        restricted = deepcopy(policy.document);restricted['subjects']['reader']['read'] = ['asteria.sav']
        (tmp_path / 'access-policy.json').write_text(json.dumps(restricted), encoding='utf-8')
        assert client.post('/v1/packages/read', json=body, headers={'Authorization': 'Bearer ' + reader['access_token']}).status_code == 403
        wrong = deepcopy(command);wrong['approved'] = True
        assert client.post('/v1/packages/publish', json=wrong, headers=headers).status_code == 422


def test_version_and_idempotency_conflicts_never_replace_publication(store, construction):
    principal, policy, request = context(store, construction)
    first = publish(store, principal, policy, request)
    changed = deepcopy(request);changed['idempotency_key'] = 'second-stage';changed['exports'] = [changed['baseline']]
    with pytest.raises(InvalidModel): prepare_package(store, principal, policy, changed)
    changed['exports'] = request['exports'];changed['imports'] = []
    stage = prepare_package(store, principal, policy, changed)
    with pytest.raises(Conflict):
        publish_package(store, principal, policy, {'idempotency_key': 'commit-stage-1', 'preparation': stage['preparation']})
    current = read_package(store, principal, policy, {'publication': first['publication'], 'purpose': 'NEW_USE'})
    assert current['manifest']['exports'] == request['exports']
    policy2 = deepcopy(policy.document);policy2['version'] = '2'
    historical = read_package(store, principal, AccessPolicy(policy2), {'publication': first['publication'], 'purpose': 'HISTORICAL'})
    assert not historical['new_use_allowed']
    with pytest.raises(InvalidModel): read_package(store, principal, AccessPolicy(policy2), {'publication': first['publication'], 'purpose': 'NEW_USE'})
