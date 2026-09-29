from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import ORGANIZATION_PROFILE, AUDIENCE_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.organization import inspect_organization
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict


def models(example):
    scope = deepcopy(example)
    def obj(kind, name, body):
        meta = deepcopy(scope['meta']);meta.update(type='air.' + kind, id='urn:org:' + name, name=name)
        return {'meta': meta, 'body': body}
    authority = obj('AuthorityScope', 'authority', {'principal': 'urn:person:architect', 'scope': exact(scope),
        'allowed_decisions': ['Propose architecture', 'Review constraints'], 'limits': ['No admission mandate'], 'delegations': [], 'separation_rules': ['Independent review']})
    role = obj('Role', 'architect', {'responsibilities': ['Model interfaces', 'Record constraints'],
        'required_competencies': [{'binding': 'air.skill-requirement/0.21', 'competency': 'Architecture', 'minimum_level': 'Practitioner', 'assessment_method': 'Peer review'}], 'authority': exact(authority)})
    parent = obj('OrganizationUnit', 'company', {'mandate': 'Coordinate architecture', 'roles': []})
    unit = obj('OrganizationUnit', 'team', {'mandate': 'SAV architecture', 'parent': exact(parent), 'roles': [exact(role)]})
    domain = obj('Domain', 'domain', {'purpose': 'Service delivery', 'scope': exact(scope), 'authority': exact(authority)})
    actor = obj('Actor', 'actor', {'kind': 'HUMAN', 'roles': [exact(role)], 'boundary': exact(scope)})
    return [scope, authority, role, parent, unit, domain, actor]


def prepare(store, example):
    objects = models(example);store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:org:baseline', type='air.Baseline')
    baseline = store.create_baseline({'meta': meta, 'profile': ORGANIZATION_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    token = store.create_token('org-reader', 'reader');user = store.authenticate(token['access_token'])
    return objects, {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}}, user, token


def test_organization_exact_graph_and_pure_report(store, example):
    objects, request, user, token = prepare(store, example)
    before = store.counts()
    report = inspect_organization(store, user, AccessPolicy(), request)
    assert report == inspect_organization(store, user, AccessPolicy(), request)
    assert len(report['units']) == 2 and len(report['roles']) == len(report['actors']) == len(report['domains']) == len(report['authorities']) == 1
    assert report['declarations_only'] and not report['authorization_granted'] and not report['policy_updated']
    assert report['actors'][0]['declared']['roles'] == [exact(objects[2])]
    assert store.counts() == before
    assert validate_graph(objects, ORGANIZATION_PROFILE)['valid']
    assert not validate_graph(objects, AUDIENCE_PROFILE)['valid']
    changed = deepcopy(request);changed['baseline']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): inspect_organization(store, user, AccessPolicy(), changed)


@pytest.mark.parametrize('fault', ['cycle', 'self-parent', 'wrong-role-type', 'scope-mismatch', 'missing-parent'])
def test_organization_graph_failures(example, fault):
    objects = models(example)
    if fault == 'cycle': objects[3]['body']['parent'] = exact(objects[4])
    if fault == 'self-parent': objects[4]['body']['parent'] = exact(objects[4])
    if fault == 'wrong-role-type': objects[-1]['body']['roles'] = [exact(objects[1])]
    if fault == 'scope-mismatch': objects[5]['body']['scope'] = {'id': 'urn:other:scope', 'revision': 1}
    if fault == 'missing-parent': objects[4]['body']['parent']['revision'] = 2
    assert not validate_graph(objects, ORGANIZATION_PROFILE)['valid']


def test_organization_canonical_sets_and_unsupported_bindings(example):
    objects = models(example); equivalent = deepcopy(objects)
    equivalent[1]['body']['allowed_decisions'].reverse();equivalent[2]['body']['responsibilities'].reverse()
    assert [canonical(o) for o in objects] == [canonical(o) for o in equivalent]
    for index, field, value in [(1, 'delegations', [{'principal': 'urn:person:other'}]), (1, 'limits', []), (2, 'responsibilities', [])]:
        wrong = deepcopy(objects[index]);wrong['body'][field] = value
        assert not validate(wrong)['valid']
    wrong_graph = deepcopy(objects);wrong_graph[4]['body']['operating_model'] = exact(objects[0])
    assert not validate_graph(wrong_graph)['valid']
    wrong = deepcopy(objects[2]);wrong['body']['required_competencies'][0]['binding'] = 'unknown'
    assert not validate(wrong)['valid']


def test_organization_cross_namespace_closure(store, example):
    objects = models(example);objects[3]['meta']['namespace'] = 'company.shared'
    store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:org:scoped', type='air.Baseline')
    baseline = store.create_baseline({'meta': meta, 'profile': ORGANIZATION_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    token = store.create_token('reader', 'reader');user = store.authenticate(token['access_token'])
    policy = AccessPolicy({'version': 'limited', 'subjects': {'reader': {'read': [example['meta']['namespace']]}}})
    with pytest.raises(Forbidden): inspect_organization(store, user, policy, {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}})


def test_organization_transfer(store, example, tmp_path):
    objects, request, user, token = prepare(store, example)
    bundle = tmp_path / 'transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url)
    target = Store(url)
    try:
        assert target.export_baseline(request['baseline']) == store.export_baseline(request['baseline'])
    finally: target.engine.dispose()


def test_organization_api_and_mcp(store, example, tmp_path):
    objects, request, user, token = prepare(store, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        result = client.post('/v1/organization/inspect', json=request, headers=headers)
        assert result.status_code == 200
        mcp_headers = {**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'}
        response = client.post('/mcp', headers=mcp_headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_inspect_organization', 'arguments': request}})
        assert response.status_code == 200
        assert json.loads(response.json()['result']['content'][0]['text']) == result.json()
        assert client.post('/v1/organization/inspect', json=request).status_code == 401
