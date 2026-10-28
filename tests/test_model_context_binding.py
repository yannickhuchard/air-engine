from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from air import artifacts, context_export
from air.access import AccessPolicy, Forbidden, ScopedStore
from air.api import create_app
from air.core import digest
from air.foundation import exact
from test_context_export import export_case  # noqa: F401


def bound(c):
    request, document, user, token, settings = c
    subject = document['subjects'][user['subject']]
    subject['model_context'] = {'destination': request['destination'], 'purpose': request['purpose']}
    subject['context_destinations'][0]['classifications'] = ['PUBLIC', 'INTERNAL']
    (settings.home / 'access-policy.json').write_text(json.dumps(document))
    return request, document, user, token, settings


def test_model_identity_cannot_read_restricted_dependencies_through_regular_object_or_view_routes(store, export_case):
    request, document, user, token, settings = bound(export_case)
    policy = AccessPolicy(document)
    with pytest.raises(Forbidden): ScopedStore(store, user, policy).get('urn:export:root', 1)
    assert ScopedStore(store, user, policy).get('urn:export:unused', 1)
    with TestClient(create_app(settings, run_worker=False)) as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        assert client.get('/v1/objects/urn:export:root/revisions/1', headers=headers).status_code == 403
        result = client.post('/v1/deliverables/compile', headers=headers,
            json={'title': 'Must not disclose', 'baselines': [request['baseline']]})
        assert result.status_code == 403


def test_explicit_selection_can_export_allowed_objects_from_a_mixed_baseline(store, export_case):
    request, document, user, _, settings = bound(export_case)
    unused = store.get('urn:export:unused', 1)['object']
    request['roots'] = [{**exact(unused), 'digest': digest(unused)}]
    result = context_export.prepare(store, user, AccessPolicy(document), request, settings)
    assert [o['meta']['id'] for o in result['content']['objects']] == ['urn:export:unused']
    with pytest.raises(Forbidden):
        context_export.prepare(store, user, AccessPolicy(document), {**request, 'destination': 'another-model'}, settings)


def test_unclassified_legacy_artifacts_default_to_restricted_for_model_credentials(store, export_case):
    _, document, user, _, settings = bound(export_case)
    token = store.create_token('fixture-uploader', 'admin')
    admin = store.authenticate(token['access_token'], True); admin['authorization']['instance_id'] = settings.instance_id
    document['subjects'][admin['subject']] = {'read': ['*'], 'write': ['*']}
    (settings.home / 'access-policy.json').write_text(json.dumps(document))
    policy = AccessPolicy(document)
    old = artifacts.put(store, admin, policy, settings, {'namespace': 'project', 'media_type': 'text/plain',
        'idempotency_key': 'unclassified'}, b'Unclassified bytes stay protected')
    public = artifacts.put(store, admin, policy, settings, {'namespace': 'project', 'media_type': 'text/plain',
        'idempotency_key': 'classified', 'classification': {'level': 'PUBLIC'}}, b'Approved public context')
    with pytest.raises(Forbidden): artifacts.download(store, user, policy, {'artifact': old['artifact']})
    assert artifacts.download(store, user, policy, {'artifact': public['artifact']})[1] == b'Approved public context'


def test_expired_model_destination_and_read_only_namespace_grant_fail_closed(export_case):
    _, document, user, _, _ = bound(export_case)
    subject = document['subjects'][user['subject']]
    subject['export_context'] = []
    assert not AccessPolicy(document).allows(user, 'read', 'project')
    subject['export_context'] = ['project']; subject['context_destinations'][0]['expires_at'] = '2020-01-01T00:00:00Z'
    assert not AccessPolicy(document).allows(user, 'read', 'project')
