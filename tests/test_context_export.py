from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from air import context_export
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import FOUNDATION_PROFILE, digest
from air.foundation import exact, InvalidModel
from air.storage import Conflict


@pytest.fixture
def export_case(store, example, tmp_path):
    dependency = deepcopy(example)
    dependency['meta'].update(id='urn:export:dependency', namespace='shared', classification={'level': 'CONFIDENTIAL'})
    root = deepcopy(example)
    root['meta'].update(id='urn:export:root', namespace='project', classification={'level': 'INTERNAL'})
    root['body']['includes'] = [exact(dependency)]
    unused = deepcopy(example); unused['meta'].update(id='urn:export:unused', namespace='project')
    store.put_bundle([root, dependency, unused], 'fixture')
    meta = deepcopy(root['meta']); meta.update(id='urn:export:baseline', type='air.Baseline')
    frozen = store.create_baseline({'meta': meta, 'profile': FOUNDATION_PROFILE,
        'members': [exact(o) for o in (root, dependency, unused)], 'parent_baselines': []}, 'fixture')
    token = store.create_token('export-reader', 'reader')
    user = store.authenticate(token['access_token'], True)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='export-test')
    user['authorization']['instance_id'] = settings.instance_id
    grant = {'id': 'approved-model', 'purposes': ['architecture-design'],
        'classifications': ['INTERNAL', 'CONFIDENTIAL'],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}
    document = {'version': 'export-1', 'subjects': {user['subject']: {'read': ['project', 'shared'],
        'export_context': ['project', 'shared'], 'context_destinations': [grant]}}}
    (tmp_path / 'access-policy.json').write_text(json.dumps(document))
    request = {'baseline': {**exact(frozen['baseline']), 'digest': frozen['digest']},
        'roots': [{**exact(root), 'digest': digest(root)}], 'destination': 'approved-model',
        'purpose': 'architecture-design', 'idempotency_key': 'export'}
    return request, document, user, token, settings


def test_export_is_minimized_retained_idempotent_and_never_transfers(store, export_case):
    request, document, user, _, settings = export_case
    policy = AccessPolicy(document)
    result = context_export.prepare(store, user, policy, request, settings)
    assert {o['meta']['id'] for o in result['content']['objects']} == {'urn:export:root', 'urn:export:dependency'}
    assert not result['external_transfer_executed'] and not result['unmanaged_client_reads_controlled']
    assert store.get_record(result['receipt']['id'])['actor'] == user['subject']
    assert result == context_export.prepare(store, user, policy, request, settings)
    changed = {**request, 'purpose': 'other'}
    with pytest.raises(Forbidden): context_export.prepare(store, user, policy, changed, settings)
    dependency = next(o for o in result['content']['objects'] if o['meta']['id'] == 'urn:export:dependency')
    with pytest.raises(Conflict):
        context_export.prepare(store, user, policy, {**request, 'roots': [{**exact(dependency), 'digest': digest(dependency)}]}, None)


@pytest.mark.parametrize('restriction', ['classification', 'namespace', 'destination', 'expiry', 'read'])
def test_read_permission_cannot_bypass_destination_or_dependency_restrictions(store, export_case, restriction):
    request, document, user, _, _ = export_case
    subject = document['subjects'][user['subject']]
    if restriction == 'classification': subject['context_destinations'][0]['classifications'] = ['INTERNAL']
    elif restriction == 'namespace': subject['export_context'] = ['project']
    elif restriction == 'destination': subject['context_destinations'] = []
    elif restriction == 'expiry': subject['context_destinations'][0]['expires_at'] = '2020-01-01T00:00:00Z'
    else: subject['read'] = ['project']
    before = store.counts()
    with pytest.raises(Forbidden): context_export.prepare(store, user, AccessPolicy(document), request)
    assert store.counts() == before
    with pytest.raises(Forbidden): context_export.prepare(store, user, AccessPolicy(), request)


def test_http_export_rechecks_policy_and_pins(store, export_case):
    from air.mcp import TOOLS
    request, document, user, token, settings = export_case
    assert TOOLS['air_prepare_context_export'][3] == '/v1/context-exports/prepare'
    with TestClient(create_app(settings, run_worker=False)) as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        assert client.post('/v1/context-exports/prepare', headers=headers, json=request).status_code == 200
        bad = deepcopy(request); bad['roots'][0]['digest'] = 'sha256:' + '0' * 64
        assert client.post('/v1/context-exports/prepare', headers=headers, json=bad).status_code >= 400
        document['subjects'][user['subject']]['export_context'] = []
        (settings.home / 'access-policy.json').write_text(json.dumps(document))
        assert client.post('/v1/context-exports/prepare', headers=headers, json=request).status_code == 403
