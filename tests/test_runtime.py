from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import pytest
from air import runtime
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.core import digest
from air.foundation import InvalidModel
from air.storage import Conflict
from test_runtime_schema import runtime_objects


def setup_runtime(store, tmp_path):
    plan, objects, original = runtime_objects(store)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='runtime-test')
    token = store.create_token('observer', 'editor')
    principal = store.authenticate(token['access_token'], True);principal['authorization']['instance_id'] = settings.instance_id
    source = deepcopy(store.get(plan['pools'][0]['source']['id'], 1)['object'])
    source['meta']['id'] = 'urn:asteria:runtime:source:sample'
    source['body'].update(kind='TELEMETRY', locator='urn:asteria:synthetic:sample', captured_at='2026-09-19T10:05:00Z')
    stored = store.put(source, 'observer')
    pin = {k: stored[k] for k in ('id', 'revision', 'digest')}
    objects[0]['meta']['provenance']['source_refs'] = [{k: pin[k] for k in ('id', 'revision')}]
    request = {'idempotency_key': 'observation', 'source': pin, 'observations': [objects[0]]}
    return settings, principal, request, token


def comparison(store, observation):
    body = observation['body']
    scope = body['instance_or_scope']; expected = scope
    return {'scope': {**scope, 'digest': store.get(scope['id'], scope['revision'])['digest']},
        'expected': {**expected, 'digest': store.get(expected['id'], expected['revision'])['digest']},
        'as_of': '2026-09-19T10:06:00Z', 'window': body['window'], 'max_age_seconds': 60,
        'bindings': [{'input': 'available', 'observation': {'id': observation['meta']['id'], 'revision': 1, 'digest': digest(observation)}}],
        'method': {'basis': 'DECLARED_MAPPING', 'rationale': 'Explicit synthetic mapping: ERP availability is expected to be true.',
            'expression': {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
                'required_inputs': [{'name': 'available', 'type': 'Boolean'}], 'ast': {'ref': 'available'}}}}


def test_ingestion_concurrent_idempotence_and_pure_comparison(store, tmp_path):
    settings, principal, request, _ = setup_runtime(store, tmp_path);policy = AccessPolicy()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: runtime.ingest(store, principal, policy, settings, request), range(2)))
    assert sorted(r['created'] for r in receipts) == [False, True]
    args = comparison(store, request['observations'][0]);before = store.counts(), store.audit_log()
    result = runtime.compare(store, principal, policy, args)
    assert result['result'] == 'VIOLATED' and result['coverage'] == 'PARTIAL'
    assert not result['business_verification_granted'] and not result['automatic_model_change']
    assert result == runtime.compare(store, principal, policy, args)
    assert (store.counts(), store.audit_log()) == before


def test_unknown_stale_artifact_and_constant_mapping_do_not_pass(store, tmp_path):
    settings, principal, request, _ = setup_runtime(store, tmp_path);policy = AccessPolicy()
    request['observations'][0]['body']['value_or_artifact'] = {'type': 'Boolean', 'state': 'CONFLICTING'}
    runtime.ingest(store, principal, policy, settings, request)
    args = comparison(store, request['observations'][0])
    assert runtime.compare(store, principal, policy, args)['result'] == 'CONFLICTING'
    args['max_age_seconds'] = 59
    report = runtime.compare(store, principal, policy, args)
    assert report['result'] == 'UNKNOWN' and report['diagnostics'][0]['code'] == 'OBSERVATION_STALE'
    args['method']['expression']['ast'] = {'literal': {'type': 'Boolean', 'value': True}}
    with pytest.raises(InvalidModel, match='actually reference'): runtime.compare(store, principal, policy, args)
    artifact = deepcopy(request);artifact['idempotency_key'] = 'artifact'
    observation = artifact['observations'][0];observation['meta']['id'] += '-artifact'
    observation['body']['value_or_artifact'] = {'locator': 'urn:sha256:' + '0' * 64, 'media_type': 'application/json', 'size': 1,
        'digest': {'algorithm': 'sha256', 'value': '0' * 64}, 'access_policy': 'Same scope', 'retention_policy': 'Retain with observation'}
    runtime.ingest(store, principal, policy, settings, artifact)
    result = runtime.compare(store, principal, policy, comparison(store, observation))
    assert result['result'] == 'UNKNOWN' and any(d['code'] == 'ARTIFACT_NOT_INTERPRETED' for d in result['diagnostics'])



def test_observation_batch_rolls_back_on_conflicting_revision(store, tmp_path):
    settings, principal, request, _ = setup_runtime(store, tmp_path)
    existing = deepcopy(request['observations'][0]);existing['meta']['id'] += '-existing'
    store.put(existing, 'observer')
    conflicting = deepcopy(existing);conflicting['body']['value_or_artifact']['value'] = True
    request['observations'].append(conflicting);before = store.counts(), store.audit_log()
    with pytest.raises(Conflict): runtime.ingest(store, principal, AccessPolicy(), settings, request)
    assert (store.counts(), store.audit_log()) == before


def test_runtime_http_mcp_scope_and_forged_qualification(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, principal, request, token = setup_runtime(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/runtime/observations', json=request, headers=headers)
        assert response.status_code == 200 and response.json()['qualification'] == 'DRAFT'
        assert client.post('/v1/runtime/observations', json={**request, 'qualified': True}, headers=headers).status_code == 422
        args = comparison(store, request['observations'][0])
        expected = client.post('/v1/runtime/comparisons', json=args, headers=headers).json()
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_runtime_compare', 'arguments': args}},
            headers={**headers, 'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()['result']
        assert not result['isError'] and result['structuredContent'] == expected
        (tmp_path / 'access-policy.json').write_text(json.dumps({'version': 'restricted', 'subjects': {'observer': {'read': ['asteria.shared']}}}), encoding='utf-8')
        assert client.post('/v1/runtime/comparisons', json=args, headers=headers).status_code == 403


def test_observation_future_window_and_wrong_value_type_are_rejected(store, tmp_path):
    settings, principal, request, _ = setup_runtime(store, tmp_path)
    request['observations'][0]['body']['window'] = {'start': '9999-01-01T00:00:00Z', 'end': '9999-01-02T00:00:00Z'}
    with pytest.raises(InvalidModel, match='future'): runtime.ingest(store, principal, AccessPolicy(), settings, request)
    request['observations'][0]['body']['window'] = {'start': '2026-09-19T10:00:00Z', 'end': '2026-09-19T10:05:00Z'}
    request['observations'][0]['body']['value_or_artifact'] = {'type': 'Text', 'value': 'false'}
    runtime.ingest(store, principal, AccessPolicy(), settings, request)
    report = runtime.compare(store, principal, AccessPolicy(), comparison(store, request['observations'][0]))
    assert report['execution'] == 'ERROR' and report['result'] == 'UNKNOWN'


def test_ingestion_transfer_preserves_typed_observations(store, tmp_path):
    from air.portability import export_registry, import_registry
    from air.storage import Store
    settings, principal, request, _ = setup_runtime(store, tmp_path)
    runtime.ingest(store, principal, AccessPolicy(), settings, request)
    args = comparison(store, request['observations'][0]);expected = runtime.compare(store, principal, AccessPolicy(), args)
    bundle = tmp_path / 'runtime-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'runtime-import.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try: assert runtime.compare(imported, principal, AccessPolicy(), args) == expected
    finally: imported.engine.dispose()


def test_ingestion_import_witness_requires_its_subject_revision(store, tmp_path):
    from sqlalchemy import delete
    from air.storage import revisions
    settings, principal, request, _ = setup_runtime(store, tmp_path)
    runtime.ingest(store, principal, AccessPolicy(), settings, request)
    subject = request['observations'][0]['body']['instance_or_scope']
    with store.write() as conn:
        conn.execute(delete(revisions).where(revisions.c.id == subject['id'], revisions.c.revision == subject['revision']))
        with pytest.raises(InvalidModel, match='Required revision'):
            runtime.verify_ingestions(store, conn)
