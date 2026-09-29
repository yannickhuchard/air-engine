from copy import deepcopy
import json
import pytest
from air.access import AccessPolicy, Forbidden
from air.business import assess
from air.config import Settings
from air.core import BUSINESS_PROFILE, COLLABORATION_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.storage import Store
from test_runtime_schema import runtime_objects


def business_objects(store):
    plan, runtime, original = runtime_objects(store)
    scope = store.get('urn:asteria:scope:sav', 1)['object']
    def obj(kind, suffix, body):
        meta = deepcopy(scope['meta']);meta.update(id='urn:asteria:business:sav:' + suffix, type='air.' + kind, name=kind + ' SAV')
        return {'meta': meta, 'body': body}
    metric = obj('Metric', 'metric', {'definition': 'ERP confirmation availability for the observed operation', 'unit': '1',
        'aggregation': 'Declared latest sample', 'population': 'Synthetic operation sample', 'window': 'PT300S', 'collection_method': 'Explicit synthetic observation'})
    goal = obj('Goal', 'goal', {'outcome': 'Make the confirmation state available for the observed operation', 'measures': [exact(metric)],
        'targets': [{'id': 'availability', 'metric': exact(metric), 'operator': 'EQ', 'value': {'type': 'Boolean', 'value': True}, 'unit': '1', 'context': exact(scope)}],
        'horizon': {'start': '2026-09-19T00:00:00Z', 'end': '2026-09-20T00:00:00Z'}})
    intent = obj('Intent', 'intent', {'desired_change': 'Improve claim handling', 'sponsor': scope['meta']['owner'], 'scope': exact(scope), 'goals': [exact(goal)]})
    concern = obj('Concern', 'concern', {'question': 'How is a missing confirmation handled?', 'scope': exact(scope), 'addressed_by': []})
    stakeholder = obj('Stakeholder', 'stakeholder', {'identity_or_group': scope['meta']['owner'], 'concerns': [exact(concern)], 'participation_role': 'Service owner'})
    function = next(o for o in original if o['meta']['type'] == 'air.Function')
    capability = obj('Capability', 'capability', {'ability': 'Process a service claim', 'outcomes': [exact(goal)], 'required_functions': [exact(function)], 'context': exact(scope), 'maturity_evidence': []})
    actor = next(o for o in original if o['meta']['type'] == 'air.Actor')
    contract = next(o for o in original if o['meta']['type'] == 'air.SemanticContract')
    service = obj('BusinessService', 'service', {'beneficiaries': [exact(actor)], 'value_proposition': 'Traceable claim status', 'capabilities': [exact(capability)], 'service_commitments': [exact(contract)]})
    product = obj('Product', 'product', {'offer': 'After-sales service', 'market_scope': exact(scope), 'services': [exact(service)], 'lifecycle_owner': scope['meta']['owner']})
    runtime[0]['body']['metric_or_signal'] = exact(metric)
    return plan, [metric, goal, intent, concern, stakeholder, capability, service, product], runtime, original


def setup_business(store, tmp_path):
    plan, objects, runtime, original = business_objects(store)
    store.put_bundle(objects + runtime, 'fixture')
    token = store.create_token('analyst', 'editor');principal = store.authenticate(token['access_token'], True)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='business-test')
    principal['authorization']['instance_id'] = settings.instance_id
    request = {'goal': {**exact(objects[1]), 'digest': digest(objects[1])}, 'as_of': '2026-09-19T10:06:00Z',
        'window': runtime[0]['body']['window'], 'max_age_seconds': 120,
        'bindings': [{'target': 'availability', 'observation': {**exact(runtime[0]), 'digest': digest(runtime[0])}}]}
    return settings, principal, token, request, objects, runtime, original, plan


def test_business_profile_closure_and_legacy_boundary(store, tmp_path):
    settings, principal, token, request, objects, runtime, original, plan = setup_business(store, tmp_path)
    all_objects = original + runtime + objects
    assert validate_graph(all_objects, BUSINESS_PROFILE)['valid']
    assert not validate_graph(all_objects, COLLABORATION_PROFILE)['valid']
    assert validate(runtime[0])['profile'] == BUSINESS_PROFILE
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta']);meta.update(id='urn:asteria:business:baseline:sav')
    baseline = store.create_baseline({'meta': meta, 'profile': BUSINESS_PROFILE, 'members': [exact(o) for o in all_objects],
        'parent_baselines': [{k: plan['demands'][0]['baseline'][k] for k in ('id', 'revision')}]}, 'fixture')
    assert baseline['validation']['valid'] and len(baseline['baseline']['body']['members']) == 35


def test_goal_target_units_identifiers_and_unknown_values(store):
    plan, objects, runtime, original = business_objects(store)
    goal = deepcopy(objects[1]);goal['body']['targets'].append(deepcopy(goal['body']['targets'][0]))
    assert not validate(goal)['valid']
    goal = deepcopy(objects[1]);goal['body']['targets'][0]['operator'] = 'LTE'
    assert not validate(goal)['valid']
    goal = deepcopy(objects[1]);goal['body']['targets'][0]['value'] = {'type': 'Quantity[second]', 'value': '300.00'}
    goal['body']['targets'][0].update(unit='second', operator='LTE')
    assert validate(goal)['valid']
    assert json.loads(canonical(goal))['body']['targets'][0]['value']['value'] == '300'
    assert not validate_graph(original + runtime + [goal] + [o for o in objects if o['meta']['type'] != 'air.Goal'], BUSINESS_PROFILE)['valid']
    goal['body']['targets'][0]['value'] = {'type': 'Quantity[second]', 'state': 'UNKNOWN'}
    assert validate(goal)['valid']
    goal['body']['targets'][0]['metric']['revision'] = 9
    assert not validate(goal)['valid']
    metric = deepcopy(objects[0]);metric['body']['window'] = 'PT31622401S'
    assert not validate(metric)['valid']
    concern = deepcopy(objects[3]);concern['body']['addressed_by'] = [exact(objects[0])]
    assert not validate_graph(original + runtime + [concern] + [o for o in objects if o['meta']['type'] != 'air.Concern'], BUSINESS_PROFILE)['valid']


def test_goal_assessment_is_pure_and_scoped_to_declared_targets(store, tmp_path):
    settings, principal, token, request, *_ = setup_business(store, tmp_path)
    before = store.counts(), store.audit_log()
    result = assess(store, principal, AccessPolicy(), request)
    assert result['result'] == 'VIOLATED' and result['execution'] == 'EXECUTED'
    assert result['result_scope'] == 'DECLARED_TARGETS_ON_BOUND_OBSERVATIONS' and result['coverage'] == 'PARTIAL'
    assert not result['goal_outcome_verified'] and not result['business_verification_granted']
    assert result == assess(store, principal, AccessPolicy(), request)
    assert (store.counts(), store.audit_log()) == before
    stale = deepcopy(request);stale['max_age_seconds'] = 30
    assert assess(store, principal, AccessPolicy(), stale)['result'] == 'UNKNOWN'


def test_metric_binding_conflict_and_type_error_preserved(store, tmp_path):
    settings, principal, token, request, objects, runtime, *_ = setup_business(store, tmp_path)
    obs = deepcopy(runtime[0]);obs['meta']['revision'] = 2;obs['body']['value_or_artifact'] = {'type': 'Boolean', 'state': 'CONFLICTING'}
    store.put(obs, 'fixture');request['bindings'][0]['observation'] = {**exact(obs), 'digest': digest(obs)}
    assert assess(store, principal, AccessPolicy(), request)['result'] == 'CONFLICTING'
    obs['meta']['revision'] = 3;obs['body']['value_or_artifact'] = {'type': 'Text', 'value': 'true'}
    store.put(obs, 'fixture');request['bindings'][0]['observation'] = {**exact(obs), 'digest': digest(obs)}
    result = assess(store, principal, AccessPolicy(), request)
    assert result['execution'] == 'ERROR' and result['result'] == 'UNKNOWN'
    obs['meta']['revision'] = 4;obs['body']['metric_or_signal'] = 'Metric with a similar name'
    store.put(obs, 'fixture');request['bindings'][0]['observation'] = {**exact(obs), 'digest': digest(obs)}
    with pytest.raises(InvalidModel, match='exact target metric'): assess(store, principal, AccessPolicy(), request)


def test_goal_horizon_window_missing_binding_and_access_refused(store, tmp_path):
    settings, principal, token, request, *_ = setup_business(store, tmp_path)
    restricted = AccessPolicy({'version': 'limited', 'subjects': {'analyst': {'read': ['asteria.sav']}}})
    with pytest.raises(Forbidden): assess(store, principal, restricted, request)
    bad = deepcopy(request);bad['bindings'][0]['target'] = 'other'
    with pytest.raises(InvalidModel, match='Every explicit'): assess(store, principal, AccessPolicy(), bad)
    bad = deepcopy(request);bad['window']['start'] = '2026-09-19T10:01:00Z'
    with pytest.raises(InvalidModel, match='sample window'): assess(store, principal, AccessPolicy(), bad)
    bad = deepcopy(request);bad['window'] = {'start': '2026-09-20T10:00:00Z', 'end': '2026-09-20T10:05:00Z'};bad['as_of'] = '2026-09-20T10:06:00Z'
    with pytest.raises(InvalidModel, match='goal horizon'): assess(store, principal, AccessPolicy(), bad)


def test_thirty_two_targets_use_bounded_balanced_aggregation(store, tmp_path):
    settings, principal, token, request, objects, runtime, *_ = setup_business(store, tmp_path)
    goal = deepcopy(objects[1]);goal['meta']['revision'] = 2
    goal['body']['targets'] = [{**deepcopy(goal['body']['targets'][0]), 'id': 'target' + str(i)} for i in range(32)]
    goal['body']['targets'][0]['value'] = {'type': 'Boolean', 'state': 'UNKNOWN'}
    store.put(goal, 'fixture');request['goal'] = {**exact(goal), 'digest': digest(goal)}
    request['bindings'] = [{'target': target['id'], 'observation': request['bindings'][0]['observation']} for target in goal['body']['targets']]
    result = assess(store, principal, AccessPolicy(), request)
    assert result['execution'] == 'EXECUTED' and result['result'] == 'VIOLATED'
    assert len(result['targets']) == 32 and any(t['result'] == 'UNKNOWN' for t in result['targets'])


def test_business_goal_api_mcp_and_transfer_replay(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    from air.portability import export_registry, import_registry
    settings, principal, token, request, *_ = setup_business(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/goals/assess', headers=headers, json=request)
        assert response.status_code == 200
        assert client.post('/v1/goals/assess', headers=headers, json={**request, 'constant_inputs': {'threshold': {'type': 'Boolean', 'value': False}}}).status_code == 422
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_assess_goal_targets', 'arguments': request}},
            headers={**headers, 'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()['result']
        assert not result['isError'] and result['structuredContent'] == response.json()
        expected = response.json()
    bundle = tmp_path / 'business-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'business-import.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try: assert assess(imported, principal, AccessPolicy(), request) == expected
    finally: imported.engine.dispose()
