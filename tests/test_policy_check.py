from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import GOVERNANCE_PROFILE, STATE_PROFILE, canonical, digest
from air.foundation import exact, validate_graph, InvalidModel
from air.policy_check import check_policy
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict


def expression(value=None):
    return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
        'ast': {'ref': 'confirmed'} if value is None else {'literal': {'type': 'Boolean', 'value': value}},
        'required_inputs': [{'name': 'confirmed', 'type': 'Boolean'}] if value is None else []}


def prepare(store, example, mutate=None):
    def obj(kind, name, body):
        meta = deepcopy(example['meta']);meta.update(id='urn:policy:' + name, type='air.' + kind, name=name)
        return {'meta': meta, 'body': body}
    ref = lambda name: {'id': 'urn:policy:' + name, 'revision': 1}
    source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': 'urn:fiction:policy', 'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'test', 'retention_policy': 'test'})
    constraint = obj('Constraint', 'constraint', {'mode': 'hard', 'scope': exact(example), 'condition': expression(), 'source': [exact(source)],
        'exception_policy': 'No exception without separate verified authority', 'verification': [ref('case')]})
    case = obj('VerificationCase', 'case', {'target': exact(constraint), 'method': 'TEST', 'inputs': [], 'oracle': 'Confirmed input required', 'acceptance': 'Explicit true', 'independence_basis': 'Separate reviewer'})
    control = obj('Control', 'control', {'objective': 'Independent confirmation', 'mechanism': 'Review evidence', 'scope': exact(example), 'owner': 'urn:person:owner', 'verification': [exact(case)], 'evidence_requirements': ['Signed review', 'Exact input']})
    decision = obj('Decision', 'decision', {'question': 'Permit exception?', 'alternatives': ['Decline', 'Propose'], 'selection': 'Propose', 'rationale': 'Draft only', 'basis': [exact(source)], 'authority': 'urn:person:owner', 'consequences': ['Needs review'], 'revisit_conditions': ['Expiry']})
    obligation = obj('Obligation', 'obligation', {'source_text': exact(source), 'interpretation': 'Confirmation required', 'applicability_decision': exact(decision), 'controls': [exact(control)], 'review_due': '2026-10-01T00:00:00Z'})
    risk = obj('Risk', 'risk', {'scenario': 'Unconfirmed action', 'causes': [exact(constraint)], 'consequences': ['Wrong action', 'Rework'], 'assessment_method': 'Qualitative declared', 'treatment': [exact(control), exact(decision)], 'residual_assessment': 'Unverified'})
    policy = obj('Policy', 'policy', {'intent': 'Require confirmation', 'issuer': 'urn:person:owner', 'applicability': expression(True), 'constraints': [exact(constraint)], 'review_policy': 'Independent review'})
    waiver = obj('Waiver', 'waiver', {'rule': exact(constraint), 'permitted_basis': 'Proposed only', 'scope': exact(example), 'expires_at': '2026-10-01T00:00:00Z', 'approval': exact(decision), 'compensating_controls': [exact(control)]})
    objects = [example, source, constraint, case, control, decision, obligation, risk, policy, waiver]
    if mutate: mutate(objects)
    store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:policy:baseline', type='air.Baseline')
    base = store.create_baseline({'meta': meta, 'profile': GOVERNANCE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    token = store.create_token('policy-reader', 'reader');user = store.authenticate(token['access_token'])
    pin = lambda o: {**exact(o), 'digest': digest(o)}
    request = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}, 'policy': pin(policy), 'as_of': '2026-09-20T12:00:00Z', 'applicability_inputs': {},
        'constraint_inputs': [{'constraint': pin(constraint), 'inputs': {'confirmed': {'type': 'Boolean', 'value': True}}}]}
    return objects, user, token, request


def find(objects, kind): return next(o for o in objects if o['meta']['type'] == 'air.' + kind)


def test_policy_is_pure_exact_and_does_not_grant_authority(store, example):
    objects, user, token, request = prepare(store, example);before = store.counts()
    result = check_policy(store, user, AccessPolicy(), request)
    assert result == check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'SATISFIED' and result['all_constraints_satisfied'] and result['blocking_constraints'] == 0
    assert not result['authorization_granted'] and not result['waiver_applied'] and store.counts() == before
    assert result['waivers'][0]['effectiveness'] == 'NOT_VERIFIED' and not result['waivers'][0]['applied']
    assert validate_graph(objects, GOVERNANCE_PROFILE)['valid'] and not validate_graph(objects, STATE_PROFILE)['valid']
    risk = find(objects, 'Risk');reordered = deepcopy(risk);reordered['body']['treatment'].reverse();reordered['body']['consequences'].reverse()
    assert canonical(risk) == canonical(reordered)


@pytest.mark.parametrize('value,outcome', [({'type': 'Boolean', 'value': False}, 'VIOLATED'), ({'type': 'Boolean', 'state': 'UNKNOWN'}, 'UNKNOWN'), ({'type': 'Boolean', 'state': 'CONFLICTING'}, 'CONFLICTING')])
def test_waiver_never_overrides_failed_or_unknown_hard_constraint(store, example, value, outcome):
    objects, user, token, request = prepare(store, example);request['constraint_inputs'][0]['inputs']['confirmed'] = value
    result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == outcome and result['blocking_constraints'] == 1
    assert not result['waiver_applied'] and not result['all_constraints_satisfied']


def test_soft_violation_is_reported_without_hard_block(store, example):
    objects, user, token, request = prepare(store, example, lambda objects: find(objects, 'Constraint')['body'].update(mode='soft'))
    request['constraint_inputs'][0]['inputs']['confirmed']['value'] = False
    result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'VIOLATED' and result['blocking_constraints'] == 0 and not result['all_constraints_satisfied']


@pytest.mark.parametrize('applicability,expected', [(False, 'NOT_APPLICABLE'), ('Manual applicability review', 'UNKNOWN')])
def test_applicability_prevents_condition_execution(store, example, applicability, expected):
    def mutate(objects): find(objects, 'Policy')['body']['applicability'] = expression(False) if applicability is False else applicability
    objects, user, token, request = prepare(store, example, mutate)
    result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == expected and result['constraints'][0]['evaluation']['execution'] == 'NOT_EXECUTED'
    assert result['blocking_constraints'] == (0 if expected == 'NOT_APPLICABLE' else 1)


def test_textual_constraint_requires_review(store, example):
    objects, user, token, request = prepare(store, example, lambda objects: find(objects, 'Constraint')['body'].update(condition='Review the evidence'))
    request['constraint_inputs'] = []
    result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'UNKNOWN' and result['constraints'][0]['evaluation']['reason'] == 'TEXT_REQUIRES_REVIEW'


def test_declared_validity_and_expiry_are_half_open(store, example):
    def mutate(objects): find(objects, 'Constraint')['meta']['validity']['end'] = '2026-10-01T00:00:00Z'
    objects, user, token, request = prepare(store, example, mutate)
    request['as_of'] = '2026-10-01T00:00:00Z';result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'UNKNOWN' and result['constraints'][0]['validity'] == 'EXPIRED' and result['waivers'][0]['expired']
    request['as_of'] = '2026-09-30T23:59:59Z';result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'SATISFIED' and not result['waivers'][0]['expired']


@pytest.mark.parametrize('kind,field,target', [('Constraint','verification','Source'), ('Control','scope','Decision'), ('Obligation','source_text','Constraint'), ('Policy','constraints','Control'), ('Risk','treatment','Source'), ('Waiver','approval','Control')])
def test_governance_reference_types_are_closed(store, example, kind, field, target):
    objects, user, token, request = prepare(store, example)
    broken = deepcopy(objects);subject = find(broken, kind);ref = exact(find(broken, target))
    subject['body'][field] = [ref] if isinstance(subject['body'][field], list) else ref
    assert not validate_graph(broken, GOVERNANCE_PROFILE)['valid']


def test_request_must_pin_policy_constraints_and_valid_inputs(store, example):
    objects, user, token, request = prepare(store, example)
    wrong = deepcopy(request);wrong['policy']['digest'] = 'sha256:' + '0'*64
    with pytest.raises(Conflict): check_policy(store, user, AccessPolicy(), wrong)
    wrong = deepcopy(request);wrong['constraint_inputs'].append(deepcopy(wrong['constraint_inputs'][0]))
    with pytest.raises(InvalidModel): check_policy(store, user, AccessPolicy(), wrong)
    wrong = deepcopy(request);wrong['constraint_inputs'][0]['inputs']['typo'] = {'type': 'Boolean', 'value': True}
    with pytest.raises(InvalidModel): check_policy(store, user, AccessPolicy(), wrong)
    with pytest.raises(Forbidden): check_policy(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)


def test_policy_shared_budget_blocks_incomplete_evaluation(store, example):
    predicate = {'literal': {'type': 'Boolean', 'value': True}}
    for _ in range(9): predicate = {'op': 'and', 'args': [deepcopy(predicate), deepcopy(predicate)]}
    condition = expression(True);condition['ast'] = {'op': 'every', 'over': {'literal': {'type': 'Collection[Integer]', 'value': [{'type': 'Integer', 'value': 1} for _ in range(64)]}}, 'predicate': predicate}
    def mutate(objects): find(objects, 'Constraint')['body']['condition'] = condition
    objects, user, token, request = prepare(store, example, mutate);request['constraint_inputs'] = []
    result = check_policy(store, user, AccessPolicy(), request)
    assert result['outcome'] == 'UNKNOWN' and result['cost']['steps'] == 50000 and result['blocking_constraints'] == 1
    assert result['constraints'][0]['evaluation']['execution'] == 'BUDGET_EXCEEDED'


def test_policy_transfer_preserves_result(store, example, tmp_path):
    objects, user, token, request = prepare(store, example);expected = check_policy(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'policy-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert check_policy(target, user, AccessPolicy(), request) == expected
    finally: target.engine.dispose()


def test_policy_api_mcp_and_auth(store, example, tmp_path):
    objects, user, token, request = prepare(store, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/policies/check', json=request, headers=auth)
        assert response.status_code == 200 and response.json()['outcome'] == 'SATISFIED'
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_check_policy', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.status_code == 200 and mcp.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/policies/check', json=request).status_code == 401
