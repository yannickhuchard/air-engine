from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import pytest
from air import collaboration
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.core import canonical, validate, COLLABORATION_PROFILE, RUNTIME_PROFILE
from air.foundation import exact, validate_graph, InvalidModel
from air.storage import Conflict, Store
from test_runtime_schema import runtime_objects


def setup_collaboration(store, tmp_path):
    plan, runtime, original = runtime_objects(store)
    store.put_bundle(runtime, 'fixture')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='collaboration-test')
    token = store.create_token('architect', 'editor')
    principal = store.authenticate(token['access_token'], True);principal['authorization']['instance_id'] = settings.instance_id
    uri = collaboration.whoami(principal, settings)['identity']
    meta = deepcopy(runtime[0]['meta']);meta['provenance']['recorded_by'] = uri
    contribution = {'meta': {**meta, 'id': 'urn:asteria:collaboration:sav:question', 'type': 'air.Contribution', 'name': 'ERP confirmation treatment'},
        'body': {'author': uri, 'target': [exact(runtime[0])], 'kind': 'QUESTION', 'message': 'Which treatment preserves pending claims?'}}
    decision = {'meta': {**deepcopy(meta), 'id': 'urn:asteria:collaboration:sav:decision', 'type': 'air.Decision', 'name': 'Preserve pending claims'},
        'body': {'question': 'How should missing ERP confirmation be handled?', 'alternatives': ['Queue a retry', 'Reject the claim'],
        'selection': 'Queue a retry', 'rationale': 'Preserve the claim until its status can be established', 'basis': [exact(runtime[0])],
        'authority': uri, 'consequences': ['Explicit pending state required'], 'revisit_conditions': ['ERP availability or workflow changes']}}
    return settings, principal, token, contribution, decision, original, runtime, plan


def submit(store, settings, principal, obj, key='submission'):
    return collaboration.submit(store, principal, AccessPolicy(), settings, {'idempotency_key': key, 'object': obj})


def test_collaboration_schema_and_canonical_choices(store, tmp_path):
    settings, principal, token, contribution, decision, original, runtime, plan = setup_collaboration(store, tmp_path)
    assert validate([contribution, decision])['profile'] == COLLABORATION_PROFILE
    objects = original + runtime + [contribution, decision]
    assert validate_graph(objects, COLLABORATION_PROFILE)['valid']
    assert not validate_graph(objects, RUNTIME_PROFILE)['valid']
    reordered = deepcopy(decision);reordered['body']['alternatives'].reverse()
    assert canonical(reordered) == canonical(decision)
    decision['body']['selection'] = 'Unlisted action'
    assert not validate(decision)['valid']
    decision['body']['selection'] = exact(runtime[0]);decision['body']['alternatives'].append(exact(runtime[0]))
    assert validate_graph(original + runtime + [decision], COLLABORATION_PROFILE)['valid']
    decision['body']['selection']['revision'] = 99
    assert not validate(decision)['valid']


def test_authenticated_submission_concurrency_idempotence_and_no_authority(store, tmp_path):
    settings, principal, token, contribution, decision, *_ = setup_collaboration(store, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(store, settings, principal, contribution), range(2)))
    assert sorted(r['created'] for r in results) == [False, True]
    assert results[0]['submission'] == results[1]['submission']
    result = collaboration.read(store, principal, AccessPolicy(), {'submission': results[0]['submission']})
    assert result['object'] == json.loads(canonical(contribution))
    assert result['authenticated_subject_at_submission'] == 'architect'
    assert result['qualification'] == 'DRAFT' and result['business_mandate_granted'] is False
    different = deepcopy(contribution);different['body']['message'] += ' Changed'
    with pytest.raises(Conflict): submit(store, settings, principal, different)
    new_token = store.create_token('architect', 'editor');new_principal = store.authenticate(new_token['access_token'], True)
    new_principal['authorization']['instance_id'] = settings.instance_id
    assert collaboration.whoami(principal, settings) == collaboration.whoami(new_principal, settings)
    assert not submit(store, settings, new_principal, contribution)['created']
    store.revoke_token(token['token_id'])
    with pytest.raises(Forbidden): submit(store, settings, principal, contribution)


def test_forged_author_hidden_source_and_read_revocation_refused(store, tmp_path):
    settings, principal, token, contribution, decision, *_ = setup_collaboration(store, tmp_path)
    forged = deepcopy(contribution);forged['body']['author'] = 'urn:air:identity:someone-else'
    with pytest.raises(Forbidden): submit(store, settings, principal, forged)
    forged = deepcopy(contribution);forged['meta']['provenance']['recorded_by'] = 'urn:air:identity:someone-else'
    with pytest.raises(Forbidden): submit(store, settings, principal, forged)
    limited = AccessPolicy({'version': 'limited', 'subjects': {'architect': {'write': ['asteria.sav'], 'read': ['asteria.sav']}}})
    with pytest.raises(Forbidden): collaboration.submit(store, principal, limited, settings, {'idempotency_key': 'hidden', 'object': contribution})
    result = submit(store, settings, principal, decision)
    with pytest.raises(Forbidden): collaboration.read(store, principal, limited, {'submission': result['submission']})
    forged = dict(result['submission'], digest='sha256:' + '0' * 64)
    with pytest.raises(Conflict): collaboration.read(store, principal, AccessPolicy(), {'submission': forged})


def test_submission_receipt_failure_rolls_back_object_and_audit(store, tmp_path, monkeypatch):
    settings, principal, token, contribution, decision, *_ = setup_collaboration(store, tmp_path)
    before = store.counts(), store.audit_log()
    def fail(*args, **kwargs): raise Conflict('injected receipt failure')
    monkeypatch.setattr(store, '_record_once', fail)
    with pytest.raises(Conflict): submit(store, settings, principal, contribution)
    assert store.get(contribution['meta']['id'], 1) is None
    assert (store.counts(), store.audit_log()) == before


def test_treatment_closes_new_baseline_preserving_runtime_history(store, tmp_path):
    settings, principal, token, contribution, decision, original, runtime, plan = setup_collaboration(store, tmp_path)
    submit(store, settings, principal, contribution, 'question')
    submit(store, settings, principal, decision, 'decision')
    resolved = deepcopy(contribution);resolved['meta']['revision'] = 2
    resolved['body'].update(kind='RESOLUTION', resolution=exact(decision))
    submit(store, settings, principal, resolved, 'resolution')
    drift = deepcopy(runtime[1]);drift['meta']['revision'] = 2;drift['body']['treatment'] = exact(decision)
    incident = deepcopy(runtime[2]);incident['meta']['revision'] = 2;incident['body']['learning'] = [exact(drift)]
    store.put_bundle([drift, incident], 'architect')
    objects = original + [runtime[0], drift, incident, resolved, decision]
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta'])
    meta.update(id='urn:asteria:collaboration:baseline:sav', name='Treatment design snapshot')
    result = store.create_baseline({'meta': meta, 'profile': COLLABORATION_PROFILE, 'members': [exact(o) for o in objects],
        'parent_baselines': [{k: plan['demands'][0]['baseline'][k] for k in ('id', 'revision')}]}, 'architect')
    assert result['validation']['valid']
    assert 'treatment' not in store.get(runtime[1]['meta']['id'], 1)['object']['body']
    wrong = deepcopy(drift);wrong['body']['treatment'] = exact(runtime[0])
    assert not validate_graph(original + [runtime[0], wrong, incident, resolved, decision], COLLABORATION_PROFILE)['valid']


def test_collaboration_api_mcp_and_identity_binding(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, principal, token, contribution, decision, *_ = setup_collaboration(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        expected_identity = collaboration.whoami({**principal, 'policy': AccessPolicy.load(tmp_path)}, settings)
        assert client.get('/v1/identity', headers=headers).json() == expected_identity
        assert expected_identity['actions'] == ['read', 'write']
        response = client.post('/v1/collaboration/submissions', headers=headers, json={'idempotency_key': 'api', 'object': decision})
        assert response.status_code == 200
        args = {'submission': response.json()['submission']}
        expected = client.post('/v1/collaboration/read', headers=headers, json=args).json()
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_collaboration_read', 'arguments': args}},
            headers={**headers, 'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()['result']
        assert not result['isError'] and result['structuredContent'] == expected
        assert client.post('/v1/collaboration/submissions', headers=headers, json={'idempotency_key': 'forged', 'object': decision, 'approved': True}).status_code == 422
        reader = store.create_token('reader', 'reader')
        assert client.post('/v1/collaboration/submissions', headers={'Authorization': 'Bearer ' + reader['access_token']}, json={'idempotency_key': 'reader', 'object': decision}).status_code == 403


def test_submission_transfer_and_instance_identity_isolation(store, tmp_path):
    from air.portability import export_registry, import_registry
    settings, principal, token, contribution, decision, *_ = setup_collaboration(store, tmp_path)
    result = submit(store, settings, principal, decision)
    args = {'submission': result['submission']};expected = collaboration.read(store, principal, AccessPolicy(), args)
    other = Settings(tmp_path / 'other', settings.database_url, instance_id='other-instance')
    assert collaboration.whoami(principal, settings)['identity'] != collaboration.whoami(principal, other)['identity']
    bundle = tmp_path / 'collaboration-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'collaboration-import.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try: assert collaboration.read(imported, principal, AccessPolicy(), args) == expected
    finally: imported.engine.dispose()
