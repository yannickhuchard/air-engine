from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import STATE_PROFILE, DATA_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.portability import export_registry, import_registry
from air.state_replay import replay
from air.storage import Store, Conflict


def literal(value=True): return {'literal': {'type': 'Boolean', 'value': value}}
def expression(ast=None, inputs=None):
    return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': ast or literal(), 'required_inputs': inputs or []}
def guard(name='ready'):
    return expression({'ref': name}, [{'name': name, 'type': 'Boolean'}])
def state(name, terminal=False): return {'binding': 'air.state-spec/0.24', 'id': name, 'name': name, 'terminal': terminal}
def transition(name='advance', source='WAITING', target='READY', condition=None):
    return {'binding': 'air.transition/0.24', 'id': name, 'source': source, 'target': target, 'trigger': 'check', 'guard': condition or guard(),
            'effects': [{'kind': 'HUMAN_ACTION', 'description': 'Declared review; never executed by replay'}]}


def prepare(store, example, mutate=None, context=None, stimuli=None):
    meta = deepcopy(example['meta']);meta.update(id='urn:state:machine', type='air.StateMachine', name='Illustrative review')
    machine = {'meta': meta, 'body': {'states': [state('WAITING'), state('READY', True)], 'initial_state': 'WAITING',
        'transitions': [transition()], 'invariants': []}}
    if mutate: mutate(machine['body'])
    objects = [example, machine];store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:state:baseline', type='air.Baseline')
    baseline = store.create_baseline({'meta': meta, 'profile': STATE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    token = store.create_token('state-reader', 'reader');user = store.authenticate(token['access_token'])
    request = {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}, 'machine': {**exact(machine), 'digest': digest(machine)}, 'initial_context': {},
               'stimuli': stimuli if stimuli is not None else [{'trigger': 'check', 'context': {'ready': {'type': 'Boolean', 'value': True}} if context is None else context}]}
    return machine, user, token, request


def test_state_replay_is_pure_and_terminal(store, example):
    machine, user, token, request = prepare(store, example)
    before = store.counts();result = replay(store, user, AccessPolicy(), request)
    assert result == replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'TERMINAL_REACHED' and result['final_state'] == 'READY'
    assert result['trace'][0]['transition_applied'] and result['trace'][0]['state_changed']
    assert result['trace'][0]['declared_effects_count'] == 1 and not result['external_actions_executed']
    assert not result['business_verification_granted'] and not result['authorization_granted']
    assert result['regime'] == 'ILLUSTRATIVE' and store.counts() == before
    assert not validate_graph([example, machine], DATA_PROFILE)['valid']
    reversed_states = deepcopy(machine);reversed_states['body']['states'].reverse()
    assert canonical(reversed_states) == canonical(machine)


@pytest.mark.parametrize('context, outcome', [({}, 'UNKNOWN'), ({'ready': {'type': 'Boolean', 'state': 'CONFLICTING'}}, 'CONFLICTING'), ({'ready': {'type': 'Boolean', 'value': False}}, 'NO_TRANSITION')])
def test_state_unknown_conflicting_and_false_do_not_advance(store, example, context, outcome):
    machine, user, token, request = prepare(store, example, context=context)
    result = replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == outcome and result['final_state'] == 'WAITING'
    assert not result['trace'][0]['transition_applied']


@pytest.mark.parametrize('other, expected', [('unknown', 'UNKNOWN'), ('true', 'CONFLICTING'), ('conflicting', 'CONFLICTING')])
def test_state_multiple_candidates_never_choose_arbitrarily(store, example, other, expected):
    def mutate(body): body['transitions'].append(transition('alternative', condition=guard('other')))
    values = {'ready': {'type': 'Boolean', 'value': True}}
    if other == 'true': values['other'] = {'type': 'Boolean', 'value': True}
    if other == 'conflicting': values['other'] = {'type': 'Boolean', 'state': 'CONFLICTING'}
    machine, user, token, request = prepare(store, example, mutate, values)
    result = replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == expected and result['final_state'] == 'WAITING'


def test_two_true_guards_remain_conflicting_even_with_an_unknown(store, example):
    def mutate(body): body['transitions'].extend([transition('also_ready'), transition('unknown', condition=guard('other'))])
    machine, user, token, request = prepare(store, example, mutate)
    assert replay(store, user, AccessPolicy(), request)['outcome'] == 'CONFLICTING'


def test_post_invariant_failure_keeps_the_previous_state(store, example):
    invariant = expression({'op': 'ne', 'args': [{'ref': 'air_state'}, {'literal': {'type': 'Text', 'value': 'READY'}}]}, [{'name': 'air_state', 'type': 'Text'}])
    def mutate(body): body['invariants'] = [invariant]
    machine, user, token, request = prepare(store, example, mutate)
    result = replay(store, user, AccessPolicy(), request);frame = result['trace'][0]
    assert result['outcome'] == 'INVARIANT_VIOLATED' and result['final_state'] == 'WAITING'
    assert frame['proposed_target'] == 'READY' and frame['target'] == 'WAITING' and not frame['transition_applied']


def test_initial_invariant_failure_does_not_accept_a_terminal_state(store, example):
    def mutate(body): body.update(states=[state('DONE', True)], initial_state='DONE', transitions=[], invariants=[expression(literal(False))])
    machine, user, token, request = prepare(store, example, mutate, stimuli=[])
    result = replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'INVARIANT_VIOLATED' and not result['terminal_state_reached'] and not result['trace']


@pytest.mark.parametrize('fault', ['initial', 'target', 'duplicate_state', 'duplicate_transition', 'terminal_exit', 'reserved_type'])
def test_state_model_rejects_invalid_local_contracts(store, example, fault):
    def mutate(body):
        if fault == 'initial': body['initial_state'] = 'ABSENT'
        if fault == 'target': body['transitions'][0]['target'] = 'ABSENT'
        if fault == 'duplicate_state': body['states'].append(deepcopy(body['states'][0]))
        if fault == 'duplicate_transition': body['transitions'].append(deepcopy(body['transitions'][0]))
        if fault == 'terminal_exit': body['transitions'][0]['source'] = 'READY'
        if fault == 'reserved_type': body['transitions'][0]['guard'] = guard('air_state')
    with pytest.raises(InvalidModel): prepare(store, example, mutate)


def test_state_context_reserved_unknown_and_wrong_type_are_refused(store, example):
    machine, user, token, request = prepare(store, example)
    for supplied in [{'air_state': {'type': 'Text', 'value': 'READY'}}, {'typo': {'type': 'Boolean', 'value': True}}, {'ready': {'type': 'Text', 'value': 'yes'}}]:
        wrong = deepcopy(request);wrong['stimuli'][0]['context'] = supplied
        with pytest.raises(InvalidModel): replay(store, user, AccessPolicy(), wrong)
    wrong = deepcopy(request);wrong['machine']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): replay(store, user, AccessPolicy(), wrong)
    with pytest.raises(Forbidden): replay(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)


def test_state_call_budget_is_global_and_rolls_back_incomplete_transition(store, example):
    def mutate(body): body.update(states=[state('A'), state('B')], initial_state='A',
        transitions=[transition('to_b', 'A', 'B', expression()), transition('to_a', 'B', 'A', expression())], invariants=[expression(), expression()])
    machine, user, token, request = prepare(store, example, mutate, stimuli=[{'trigger': 'check', 'context': {}} for _ in range(128)])
    result = replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'BUDGET_EXCEEDED' and result['cost']['expression_calls'] == 512
    assert not result['trace'][-1]['transition_applied'] and result['trace'][-1]['source'] == result['final_state']
    assert 0 < result['stimuli_consumed'] < 128


def test_state_step_budget_is_global(store, example):
    predicate = literal()
    for _ in range(9): predicate = {'op': 'and', 'args': [deepcopy(predicate), deepcopy(predicate)]}
    ast = {'op': 'every', 'over': {'literal': {'type': 'Collection[Integer]', 'value': [{'type': 'Integer', 'value': 1} for _ in range(64)]}}, 'predicate': predicate}
    def mutate(body): body['transitions'][0]['guard'] = expression(ast)
    machine, user, token, request = prepare(store, example, mutate, context={})
    result = replay(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'BUDGET_EXCEEDED' and result['cost']['steps'] == 50000
    assert result['final_state'] == 'WAITING' and not result['trace'][0]['transition_applied']


def test_self_transition_is_applied_without_claiming_state_change(store, example):
    def mutate(body): body['transitions'][0]['target'] = 'WAITING'
    machine, user, token, request = prepare(store, example, mutate)
    result = replay(store, user, AccessPolicy(), request)
    assert result['trace'][0]['transition_applied'] and not result['trace'][0]['state_changed']
    assert result['stimuli_consumed'] == 1 and result['outcome'] == 'INPUT_EXHAUSTED'


def test_state_transfer_preserves_replay(store, example, tmp_path):
    machine, user, token, request = prepare(store, example)
    expected = replay(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'state-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert replay(target, user, AccessPolicy(), request) == expected
    finally: target.engine.dispose()


def test_state_api_and_mcp(store, example, tmp_path):
    machine, user, token, request = prepare(store, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/states/replay', json=request, headers=auth)
        assert response.status_code == 200 and response.json()['outcome'] == 'TERMINAL_REACHED'
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_replay_state_machine', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert result.status_code == 200 and result.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/states/replay', json=request).status_code == 401


def test_replay_starts_from_a_declared_state_and_continues_past_refusals(store, example):
    """A negative property ("only from X") needs one replay, not one per state (pilot findings F18 and pass 4)."""
    no = {'ready': {'type': 'Boolean', 'value': False}};yes = {'ready': {'type': 'Boolean', 'value': True}}
    machine, user, token, request = prepare(store, example, stimuli=[{'trigger': 'check', 'context': no}, {'trigger': 'check', 'context': yes},
                                                                     {'trigger': 'check', 'context': yes}])
    result = replay(store, user, AccessPolicy(), {**request, 'continue_on_refusal': True})
    assert [f['outcome'] for f in result['trace']] == ['NO_TRANSITION', 'TRANSITION_APPLIED', 'TERMINAL_STATE']
    assert result['stimuli_refused'] == 2 and result['final_state'] == 'READY' and result['trigger_sources'] == {'check': ['WAITING']}
    started = replay(store, user, AccessPolicy(), {**request, 'start_state': 'READY'})
    assert started['started_from'] == 'DECLARED_START_STATE' and started['outcome'] == 'TERMINAL_STATE'
    with pytest.raises(InvalidModel):
        replay(store, user, AccessPolicy(), {**request, 'start_state': 'NOWHERE'})
