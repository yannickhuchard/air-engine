from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from air import behavior_search as behavior, evidence_impact as evidence, deliverables
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.core import BUILD_PROFILE, digest
from air.foundation import exact, InvalidModel
from air.storage import Conflict
from air.mcp import TOOLS
from air.tool_access import allowed_tools
from test_build_design import design, model  # noqa: F401
from test_state_replay import prepare, expression, literal, transition

POLICY = AccessPolicy()


def state_request(request, depth=2, trials=64):
    return {k: request[k] for k in ('baseline', 'machine', 'initial_context')} | {
        'alphabet': request['stimuli'], 'max_depth': depth, 'max_trials': trials}


def test_shortest_counterexample_replays_and_never_executes_effects(store, example):
    invariant = expression({'op': 'ne', 'args': [{'ref': 'air_state'}, {'literal': {'type': 'Text', 'value': 'READY'}}]}, [{'name': 'air_state', 'type': 'Text'}])
    _, user, _, request = prepare(store, example, lambda b: b.update(invariants=[invariant]))
    before = store.counts(), store.audit_log()
    search = state_request(request)
    report = behavior.search_states(store, user, POLICY, search)
    assert report['result'] == 'COUNTEREXAMPLE_FOUND' and report['domain_exhausted']
    witness = report['counterexamples'][0]
    assert witness['sequence'] == [0] and witness['report']['outcome'] == 'INVARIANT_VIOLATED'
    from air.state_replay import replay
    assert witness['report'] == replay(store, user, POLICY, witness['replay_request'])
    assert report == behavior.search_states(store, user, POLICY, search)
    assert not report['runtime_executed'] and not report['authorization_granted']
    assert (store.counts(), store.audit_log()) == before


@pytest.mark.parametrize('context,expected', [({}, 'INCONCLUSIVE'),
    ({'ready': {'type': 'Boolean', 'state': 'CONFLICTING'}}, 'INCONCLUSIVE'),
    ({'ready': {'type': 'Boolean', 'value': False}}, 'NO_COUNTEREXAMPLE_IN_DECLARED_DOMAIN')])
def test_unknown_and_expected_refusal_are_not_successful_proofs(store, example, context, expected):
    _, user, _, request = prepare(store, example, context=context)
    report = behavior.search_states(store, user, POLICY, state_request(request))
    assert report['result'] == expected and not report['counterexamples']


def test_known_true_guard_ambiguity_is_a_counterexample(store, example):
    _, user, _, request = prepare(store, example, lambda b: b['transitions'].append(transition('second')))
    report = behavior.search_states(store, user, POLICY, state_request(request))
    assert report['counterexamples'][0]['report']['outcome'] == 'CONFLICTING'


def test_budget_and_unexplored_invalid_context_are_explicit(store, example):
    _, user, _, request = prepare(store, example)
    search = state_request(request, 4, 1)
    report = behavior.search_states(store, user, POLICY, search)
    assert report['result'] == 'INCONCLUSIVE' and report['budget_exhausted']
    assert report['domain_size'] == 5 and report['trials_executed'] == 1
    search['alphabet'].append({'trigger': 'check', 'context': {'typo': {'type': 'Boolean', 'value': True}}})
    with pytest.raises(InvalidModel): behavior.search_states(store, user, POLICY, search)
    search = state_request(request); search['machine']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): behavior.search_states(store, user, POLICY, search)
    with pytest.raises(Forbidden): behavior.search_states(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), state_request(request))


def test_interface_bad_price_witness_expected_invalid_and_unknown(design, store):
    objects, user, _, _, req = design
    spec = next(o for o in objects if o['meta']['type'] == 'air.InterfaceSpecification')
    op = spec['body']['operations'][0]
    valid = next(e for e in op['examples'] if e['kind'] == 'EXCHANGE_VALID')
    bad = deepcopy(valid['response'])
    # Inspect the actual fixture's monetary field rather than mocking the verifier.
    bad['total_minor'] += 1
    invalid = next(e for e in op['examples'] if e['kind'] == 'REQUEST_INVALID')
    search = {**req, 'operation': op['name'], 'exchanges': [
        {'request': valid['request'], 'response': valid['response'], 'expected': 'PASS'},
        {'request': valid['request'], 'response': bad, 'expected': 'PASS'},
        {'request': invalid['request'], 'expected': 'FAIL'}]}
    report = behavior.search_interfaces(store, user, POLICY, search)
    assert report['result'] == 'COUNTEREXAMPLE_FOUND' and len(report['counterexamples']) == 1
    assert report['counterexamples'][0]['exchange']['response'] == bad
    assert report['trials'][2]['classification'] == 'EXPECTED'
    assert report == behavior.search_interfaces(store, user, POLICY, search)
    missing = {**req, 'operation': op['name'], 'exchanges': [{'request': valid['request'], 'expected': 'PASS'}]}
    assert behavior.search_interfaces(store, user, POLICY, missing)['result'] == 'INCONCLUSIVE'
    missing['exchanges'][0]['scope'] = 'REQUEST_ONLY'
    assert behavior.search_interfaces(store, user, POLICY, missing)['result'] == 'NO_COUNTEREXAMPLE_IN_DECLARED_DOMAIN'


def next_baseline(store, objects, req, revision=2):
    store.put_bundle(objects, 'architect')
    meta = deepcopy(model.obj('Baseline', 'baseline', {})['meta']); meta['revision'] = revision
    result = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(o) for o in objects],
        'parent_baselines': [{k: req['baseline'][k] for k in ('id', 'revision')}]}, 'architect')
    return {**exact(result['baseline']), 'digest': result['digest']}


def test_targeted_impact_and_no_automatic_approval_carry(design, store):
    objects, user, _, _, req = design
    before = req['baseline']; changed = deepcopy(objects)
    # New unrelated role preserves case dependencies.
    changed.append(model.obj('Role', 'unrelated-role', {'responsibilities': ['Communications'], 'required_competencies': []}))
    after = next_baseline(store, changed, req)
    report = evidence.compare(store, user, POLICY, {'before': before, 'after': after})
    case = next(e for e in report['evidence'] if e['type'] == 'air.VerificationCase')
    assert case['status'] == 'NO_DECLARED_IMPACT' and case['applicability'] == 'REQUALIFICATION_REQUIRED'
    assert not report['proofs_automatically_carried'] and not report['historical_records_modified']
    assert report == evidence.compare(store, user, POLICY, {'before': before, 'after': after})
    same = evidence.compare(store, user, POLICY, {'before': before, 'after': before})
    assert all(e['applicability'] == 'SAME_BASELINE_NOT_REQUALIFIED' for e in same['evidence'])
    # Change an oracle on the case itself; the case now has a concrete invalidation witness.
    updated = deepcopy(changed)
    old_case = next(o for o in updated if o['meta']['type'] == 'air.VerificationCase')
    old_pin = evidence.pin(old_case)
    old_case['meta']['revision'] = 2; old_case['body']['oracle'] = 'New oracle requires inspection.'
    # Update all exact references to the revised case, preserving graph closure.
    from air.core import reference_slots
    again = True
    while again:
        again = False
        revisions = {o['meta']['id']: o['meta']['revision'] for o in updated}
        for obj in updated:
            for _, ref, _ in reference_slots(obj):
                if ref['id'] in revisions and ref['revision'] != revisions[ref['id']]:
                    ref['revision'] = revisions[ref['id']]; obj['meta']['revision'] = 2; again = True
    after2 = next_baseline(store, updated, req, 3)
    impact = evidence.compare(store, user, POLICY, {'before': before, 'after': after2, 'targets': [old_pin]})
    assert impact['evidence'][0]['status'] == 'IMPACTED'
    assert any(w['dependency'] == old_pin for w in impact['evidence'][0]['changed_dependencies'])
    assert any(w['path'] for w in impact['evidence'][0]['changed_dependencies'])


def test_rights_digest_selection_and_site(design, store):
    objects, user, token, settings, req = design
    after = next_baseline(store, objects, req)
    request = {'before': req['baseline'], 'after': after}
    with pytest.raises(Forbidden): evidence.compare(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)
    wrong = deepcopy(request); wrong['after']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): evidence.compare(store, user, POLICY, wrong)
    wrong = {**request, 'targets': [req['specification']]}
    with pytest.raises(InvalidModel): evidence.compare(store, user, POLICY, wrong)
    client = TestClient(create_app(settings, store))
    response = client.post('/v1/evidence/impact', json=request, headers={'Authorization': 'Bearer ' + token['access_token']})
    assert response.status_code == 200 and response.json() == evidence.compare(store, user, POLICY, request)
    pack = deliverables.compile_deliverables(store, user, POLICY, {'title': 'Réception D', 'baselines': [after], 'content': 'FULL', 'website': True})
    html = next(f['content'] for f in pack['files'] if f['path'].endswith('/verification.html'))
    data = json.loads(next(f['content'] for f in pack['files'] if f['path'].endswith('/verification-impact.json')))
    assert 'Vérifications et changements' in html and 'aucun avis' in html.lower()
    assert data['comparisons'][0]['before'] == req['baseline']
    assert '\u2014' not in html


def test_mcp_inventory_and_read_permissions():
    names = ['air_search_state_counterexamples', 'air_search_interface_counterexamples', 'air_assess_evidence_impact']
    from air.ide_adapter import READ_ONLY
    for name in names:
        assert TOOLS[name][4] and name in READ_ONLY and name in allowed_tools(['read'])
