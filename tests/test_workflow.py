from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import WORKFLOW_PROFILE, ORGANIZATION_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.workflow import inspect_workflow, structure
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict
from test_business import setup_business
from test_organization import models


def prepare(store, tmp_path):
    settings, user, token, request, business, runtime, original, plan = setup_business(store, tmp_path)
    scope = next(o for o in original if o['meta']['type'] == 'air.Scope' and o['meta']['namespace'] != 'asteria.shared')
    org = models(scope)[1:]
    function = next(o for o in original if o['meta']['type'] == 'air.Function')
    actor = next(o for o in original if o['meta']['type'] == 'air.Actor')
    service = next(o for o in business if o['meta']['type'] == 'air.BusinessService')
    case = next(o for o in original if o['meta']['type'] == 'air.VerificationCase')
    def obj(kind, suffix, body):
        meta = deepcopy(scope['meta']);meta.update(id='urn:workflow:' + suffix, type='air.' + kind, name=suffix)
        return {'meta': meta, 'body': body}
    workflow = obj('Workflow', 'sav', {'steps': [
        {'binding': 'air.workflow-step/0.22', 'id': 'prepare', 'name': 'Prepare', 'function': exact(function), 'participants': [exact(actor)]},
        {'binding': 'air.workflow-step/0.22', 'id': 'review', 'name': 'Review', 'function': exact(function), 'participants': [exact(org[-1])]}],
        'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'to-review', 'source': 'prepare', 'target': 'review', 'condition': 'Preparation complete'}],
        'start_steps': ['prepare'], 'termination_policy': 'Reviewed proposal recorded', 'compensations': []})
    operating = obj('OperatingModel', 'operating', {'services': [exact(service)], 'responsibility_map': [exact(org[1]), exact(org[3])],
        'workflows': [exact(workflow)], 'resource_policies': [exact(org[0])]})
    org[3]['body']['operating_model'] = exact(operating)
    rule = obj('BusinessRule', 'rule', {'statement': 'ERP confirmation is required', 'applicability': 'Before confirmation', 'authority': 'urn:person:owner',
        'verification': [exact(case)], 'expression': {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': {'literal': {'type': 'Boolean', 'value': True}}}})
    objects = original + runtime + business + org + [workflow, operating, rule]
    store.put_bundle(org + [workflow, operating, rule], 'fixture')
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta']);meta['id'] = 'urn:workflow:baseline'
    base = store.create_baseline({'meta': meta, 'profile': WORKFLOW_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    return objects, workflow, operating, rule, user, {'baseline': {**exact(base['baseline']), 'digest': base['digest']}}


def test_workflow_report_is_pure_and_exact(store, tmp_path):
    objects, workflow, operating, rule, user, request = prepare(store, tmp_path)
    before = store.counts();result = inspect_workflow(store, user, AccessPolicy(), request)
    assert result == inspect_workflow(store, user, AccessPolicy(), request)
    assert result['workflows'][0]['structure']['reachable_steps_ignoring_conditions'] == ['prepare', 'review']
    assert not result['workflows'][0]['structure']['cycle_detected']
    assert not result['rules_evaluated'] and not result['functions_executed'] and not result['authorization_granted']
    assert result['business_rules'][0]['verification_execution'] == 'NOT_EXECUTED'
    assert store.counts() == before
    assert validate_graph(objects, WORKFLOW_PROFILE)['valid']
    assert not validate_graph(objects, ORGANIZATION_PROFILE)['valid']
    wrong = deepcopy(request);wrong['baseline']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): inspect_workflow(store, user, AccessPolicy(), wrong)


@pytest.mark.parametrize('fault', ['duplicate-step', 'duplicate-flow', 'start-absent', 'target-absent', 'wrong-function', 'wrong-participant'])
def test_workflow_invalid_references(store, tmp_path, fault):
    objects, workflow, operating, rule, user, request = prepare(store, tmp_path)
    bad = deepcopy(objects);workflow = next(o for o in bad if o['meta']['type'] == 'air.Workflow')
    body = workflow['body']
    if fault == 'duplicate-step': body['steps'].append(deepcopy(body['steps'][0]))
    if fault == 'duplicate-flow': body['flows'].append(deepcopy(body['flows'][0]))
    if fault == 'start-absent': body['start_steps'] = ['absent']
    if fault == 'target-absent': body['flows'][0]['target'] = 'absent'
    if fault == 'wrong-function': body['steps'][0]['function'] = exact(operating)
    if fault == 'wrong-participant': body['steps'][0]['participants'] = [exact(rule)]
    assert not validate_graph(bad, WORKFLOW_PROFILE)['valid']


def test_workflow_cycles_and_unreachable_are_disclosed():
    body = {'steps': [{'id': s} for s in ['a', 'b', 'c', 'd']], 'start_steps': ['a'],
            'flows': [{'source': 'a', 'target': 'b'}, {'source': 'b', 'target': 'a'}, {'source': 'c', 'target': 'd'}]}
    result = structure(body)
    assert result['cycle_detected'] and result['unreachable_steps'] == ['c', 'd']
    assert result['terminal_steps'] == ['d'] and not result['termination_verified'] and not result['conditions_evaluated']


def test_workflow_canonical_and_business_rule_expression_closure(store, tmp_path):
    objects, workflow, operating, rule, user, request = prepare(store, tmp_path)
    changed = deepcopy(workflow);changed['body']['steps'].reverse()
    assert canonical(changed) == canonical(workflow)
    bad = deepcopy(objects);rule = next(o for o in bad if o['meta']['type'] == 'air.BusinessRule')
    literal = {'literal': {'type': 'Reference', 'value': {'id': 'urn:missing:scope', 'revision': 1}}}
    rule['body']['expression']['ast'] = {'op': 'eq', 'args': [literal, deepcopy(literal)]}
    assert validate(rule)['valid']
    assert not validate_graph(bad, WORKFLOW_PROFILE)['valid']
    rule['body']['expression']['result_type'] = 'Text'
    assert not validate(rule)['valid']


def test_workflow_namespace_access_and_transfer(store, tmp_path):
    objects, workflow, operating, rule, user, request = prepare(store, tmp_path)
    with pytest.raises(Forbidden): inspect_workflow(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)
    bundle = tmp_path / 'workflow-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert inspect_workflow(target, user, AccessPolicy(), request) == inspect_workflow(store, user, AccessPolicy(), request)
    finally: target.engine.dispose()


def test_workflow_api_mcp(store, tmp_path):
    objects, workflow, operating, rule, user, request = prepare(store, tmp_path)
    token = store.create_token(user['subject'], 'reader')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/workflow/inspect', json=request, headers=auth)
        assert response.status_code == 200
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_inspect_workflow', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert result.status_code == 200 and result.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/workflow/inspect', json=request).status_code == 401
