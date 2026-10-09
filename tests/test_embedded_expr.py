"""Unit-aware predicates survive model storage and execute through domain services."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from air.access import AccessPolicy
from air.api import create_app
from air.config import Settings
from air.core import digest, validate
from air.foundation import exact, InvalidModel
from air.gates import validate_gate
from air.state_replay import replay
from air import readiness
from test_gates import gate_request
from test_state_replay import prepare
from test_delivery_032 import delivery, frozen, POLICY
from test_policy_check import prepare as prepare_policy, find
from air.policy_check import check_policy


def predicate(name='delay', version='0.2', target='ms'):
    return {'language': 'AIR-Expr', 'language_version': version, 'result_type': 'Boolean',
        'required_inputs': [{'name': name, 'type': 'Quantity[s]'}],
        'ast': {'op': 'lte', 'args': [
            {'op': 'convert', 'args': [{'ref': name}, {'literal': {'type': 'Text', 'value': target}}]},
            {'literal': {'type': 'Quantity[' + target + ']', 'value': '1500'}}]}}


def quantity(value='1.5', state=None):
    return {'type': 'Quantity[s]', **({'state': state} if state else {'value': value})}


@pytest.mark.parametrize('value,state,outcome', [
    ('1.5', None, 'TERMINAL_REACHED'), ('1.501', None, 'NO_TRANSITION'),
    (None, 'UNKNOWN', 'UNKNOWN'), (None, 'CONFLICTING', 'CONFLICTING')])
def test_unit_predicate_drives_state_replay_without_promoting_unknowns(store, example, value, state, outcome):
    def mutate(body): body['transitions'][0]['guard'] = predicate()
    machine, user, token, request = prepare(store, example, mutate, context={'delay': quantity(value, state)})
    before = store.counts()
    report = replay(store, user, AccessPolicy(), request)
    assert report['outcome'] == outcome
    assert report['engine'] == 'air.state-replay/0.35'
    assert report['expression_engines'] == ['air.expr/0.4']
    assert report['trace'][0]['guards'][0]['expression_engine'] == 'air.expr/0.4'
    assert replay(store, user, AccessPolicy(), request) == report
    assert store.counts() == before and not report['external_actions_executed']
    assert store.get(machine['meta']['id'], 1)['digest'] == digest(machine)


@pytest.mark.parametrize('version,target', [('0.1', 'ms'), ('0.2', 'kg'), ('0.3', 'ms')])
def test_invalid_embedded_language_or_dimension_is_rejected_at_write(store, example, version, target):
    def mutate(body): body['transitions'][0]['guard'] = predicate(version=version, target=target)
    with pytest.raises(InvalidModel): prepare(store, example, mutate)


def test_gate_reports_actual_mixed_language_engine_and_http_parity(store, gate_request, tmp_path):
    assert validate_gate(store, gate_request)['engine'] == 'air.expr/0.3'
    gate_request['rule_set']['rules'][0]['predicate'] = predicate('inputs.delay')
    gate_request['inputs'] = {'inputs.delay': quantity()}
    report = validate_gate(store, gate_request)
    assert report['engine'] == 'air.expr/0.4' and report['gate_decision'] == 'PASSED'
    assert report['results'][0]['applicability']['engine'] == 'air.expr/0.3'
    assert report['results'][0]['evaluation']['engine'] == 'air.expr/0.4'
    token = store.create_token('embedded-reader', 'reader')
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        response = client.post('/v1/validations', json=gate_request,
            headers={'Authorization': 'Bearer ' + token['access_token']})
        assert response.status_code == 200 and response.json() == report


def test_policy_preserves_uncertainty_and_engine_provenance(store, example):
    def mutate(objects): find(objects, 'Constraint')['body']['condition'] = predicate()
    _, user, _, request = prepare_policy(store, example, mutate)
    request['constraint_inputs'][0]['inputs'] = {'delay': quantity()}
    report = check_policy(store, user, AccessPolicy(), request)
    assert report['outcome'] == 'SATISFIED' and report['engine'] == 'air.policy-check/0.35'
    assert report['expression_engines'] == ['air.expr/0.3', 'air.expr/0.4']
    assert report['constraints'][0]['evaluation']['expression_engine'] == 'air.expr/0.4'
    request['constraint_inputs'][0]['inputs']['delay'] = quantity(state='UNKNOWN')
    report = check_policy(store, user, AccessPolicy(), request)
    assert report['outcome'] == 'UNKNOWN' and report['blocking_constraints'] == 1
    assert not report['authorization_granted'] and not report['waiver_applied']


def test_unit_guard_is_replayed_by_simulation(store, example, delivery):
    members, user, _, extra = delivery
    workflow, model, scenario = (deepcopy(extra[i]) for i in (0, 1, 3))
    for item in (workflow, model, scenario): item['meta']['id'] += '-units'
    workflow['body']['flows'][1]['guard'] = predicate()
    model['body']['workflow'] = exact(workflow)
    scenario['body'].update(workflow=exact(workflow), performance_model=exact(model), runs=5,
        classes=[{'name': 'within', 'weight': 1, 'context': {'delay': quantity(), 'score': {'type': 'Integer', 'value': 90}}}])
    additions = [workflow, model, scenario]
    store.put_bundle(additions, 'fixture')
    base = frozen(store, example, members + additions, 'urn:units:baseline')
    request = {'baseline': base, 'scenario': {**exact(scenario), 'digest': digest(scenario)}}
    report = readiness.simulate_scenario(store, user, POLICY, request)
    assert report['engine'] == 'air.scenario-simulation/0.35'
    assert report['expression_engines'] == ['air.expr/0.3', 'air.expr/0.4']
    assert report['population']['measured_runs'] == 5 and report['verdict'] == 'PASS'
    assert report == readiness.simulate_scenario(store, user, POLICY, request)


@pytest.mark.parametrize('kind,field', [('Inference', 'derivation'), ('BusinessRule', 'expression'),
    ('Constraint', 'condition'), ('Policy', 'applicability'), ('NavigationMap', 'guard')])
def test_other_embedded_sites_validate_unit_conversion_and_reject_wrong_dimensions(example, kind, field):
    ref = exact(example)
    bodies = {
        'Inference': {'conclusion': ref, 'premises': [{'id': 'urn:test:premise', 'revision': 1}], 'limitations': []},
        'BusinessRule': {'statement': 'Latency limit', 'applicability': 'All', 'authority': 'urn:test:owner', 'verification': [ref]},
        'Constraint': {'mode': 'hard', 'scope': ref, 'source': [ref], 'exception_policy': 'None', 'verification': [ref]},
        'Policy': {'intent': 'Latency', 'issuer': 'urn:test:owner', 'constraints': [ref], 'review_policy': 'Review'},
    }
    if kind == 'NavigationMap':
        body = {'application': ref, 'entry_screens': ['home'],
            'screens': [{'id': 'home', 'name': 'Home', 'kind': 'PAGE', 'purpose': 'Synthetic navigation'}],
            'transitions': [{'id': 'advance', 'source': 'home', 'target': 'home', 'trigger': 'click', 'guard': predicate()}]}
        target = body['transitions'][0]
    else:
        body = bodies[kind];target = body;target[field] = predicate()
    obj = {'meta': {**deepcopy(example['meta']), 'id': 'urn:units:' + kind, 'type': 'air.' + kind}, 'body': body}
    assert validate(obj)['valid'], validate(obj)
    target[field] = predicate(target='kg')
    assert not validate(obj)['valid']
