"""Tranche 32, pilot pass 5: what modelling the health insurance pilot through the agent path taught the engine.

Each test reproduces a defect met while closing the pilot dossiers for the ready-to-build gate.
"""
from copy import deepcopy
import pytest
from air import agent, atelier, readiness
from air.access import AccessPolicy
from air.core import ARCHITECTURE_PROFILE, DELIVERY_PROFILE, validate
from air.foundation import InvalidModel, exact, validate_graph
from test_architecture import prepare as prepare_architecture, find
from test_delivery_032 import POLICY, delivery, frozen, obj  # noqa: F401  (fixture re-export)


def consumer_policy(user):
    return AccessPolicy({'version': 't', 'subjects': {user['subject']: {'read': ['*'], 'write': ['other.project']}}})


def test_a_first_reference_to_another_project_is_borrowed_and_judged_in_its_owner_baseline(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    owner_namespace = find(objects, 'Function')['meta']['namespace'];contract = find(objects, 'SemanticContract')
    meta = deepcopy(example['meta']);meta.update(id='urn:consumer:scope', namespace='other.project', name='Consumer scope')
    scope = {'meta': meta, 'body': {'includes': [], 'excludes': [], 'boundary_description': 'Consumer project'}}
    store.put_bundle([scope], 'consumer')
    meta = deepcopy(example['meta']);meta.update(id='urn:consumer:baseline', type='air.Baseline', namespace='other.project')
    base = store.create_baseline({'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(scope)], 'parent_baselines': []}, 'consumer')
    consumer = {**exact(base['baseline']), 'digest': base['digest']}
    draft = deepcopy(scope);draft['meta']['revision'] = 2;draft['body']['includes'] = [exact(contract)]
    policy = consumer_policy(user)
    prepared = agent.rebase_drafts(store, user, policy, None, {'base': consumer, 'objects': [draft]})
    assert prepared['candidate']['valid'], 'the contract and its closure are borrowed, not reported missing'
    assert any(a['id'] == contract['meta']['id'] for a in prepared['borrowed_added'])
    assert {a['namespace'] for a in prepared['borrowed_added']} == {owner_namespace}
    deposited = agent.deposit_prepared(store, user, policy, {'prepared_change': prepared['prepared_change']['id']})
    assert deposited['created'] == 1, 'borrowed revisions are pins: only the consumer scope is written'
    new = agent.freeze_prepared(store, user, policy, {'prepared_change': prepared['prepared_change']['id']})['baseline']
    gate = readiness.assess_readiness(store, user, policy, {'baseline': new})
    external = next(c for c in gate['criteria'] if c['code'] == 'EXTERNAL_DEPENDENCIES')
    owner = external['detail']['owners'][owner_namespace]
    assert owner['status'] == 'OWNER_BASELINE_FOUND' and owner['baseline']['id'] == request['baseline']['id']
    detail = external['detail']
    assert detail['raised_here'] >= detail['diagnostics'] and detail['open_sample']
    assert {r['owner_status'] for r in detail['open_sample']} == {'INCOMPLETE_IN_OWNER_BASELINE'}, 'only what the owner itself leaves open stays open'


def test_a_project_that_builds_nothing_is_not_judged_on_construction_planning_or_runtime(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    scope = find(objects, 'Scope')
    meta = deepcopy(example['meta']);meta.update(id='urn:kernel:baseline', type='air.Baseline', namespace=scope['meta']['namespace'])
    base = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(scope)], 'parent_baselines': []}, 'fixture')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': {**exact(base['baseline']), 'digest': base['digest']}})
    status = {c['code']: c['status'] for c in gate['criteria']}
    assert {status[c] for c in ('CONSTRUCTION_CHAIN', 'PLANNING', 'RUNTIME')} == {'NOT_APPLICABLE'}
    assert not {'CONSTRUCTION_CHAIN', 'PLANNING', 'RUNTIME'} & set(gate['blocking']) and 'INDEPENDENT_REVIEW' in gate['blocking']


def test_before_construction_only_design_cases_must_have_run_and_tests_must_be_planned(store, example, delivery):
    members, user, baseline, extra = delivery
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    verification = next(c for c in gate['criteria'] if c['code'] == 'VERIFICATION')['detail']
    assert verification['design_cases'] >= 1 and verification['build_acceptance_tests'] >= 1
    assert 'latency-case' in [c['name'] for c in verification['design_cases_open']], 'a simulation is design-time proof'
    assert all(c['method'] != 'TEST' for c in verification['design_cases_open']), 'a test is the acceptance of the build, not a design proof'
    assert gate['proof']['build_acceptance_tests'] == verification['build_acceptance_tests']


def test_a_population_class_enters_the_workflow_at_its_own_start_step(store, example, delivery):
    members, user, baseline, extra = delivery
    workflow, model, case, scenario = extra
    wrong = deepcopy(scenario);wrong['meta']['revision'] = 2
    wrong['body']['classes'][0]['start_step'] = 'assess'
    issues = validate_graph([o for o in members if o['meta']['id'] != scenario['meta']['id']] + [wrong], DELIVERY_PROFILE)['diagnostics']
    assert any(d['code'] == 'AIR_SCENARIO_START' for d in issues)
    named = deepcopy(scenario);named['meta']['revision'] = 2
    for cls in named['body']['classes']: cls['start_step'] = 'sense'
    store.put_bundle([named], 'fixture')
    pinned = frozen(store, example, [o for o in members if o['meta']['id'] != scenario['meta']['id']] + [named], 'urn:delivery:start-steps')
    from air.core import digest
    run = readiness.simulate_scenario(store, user, POLICY, {'baseline': pinned, 'scenario': {**exact(named), 'digest': digest(named)}})
    assert run['verdict'] in ('PASS', 'FAIL') and all(p.startswith('sense') for c in run['classes'] for p in c['paths'])


def test_an_identifier_of_token_length_is_not_mistaken_for_a_token():
    slug = 'fraud-response-derived_from-risk-assessment'
    assert len(slug) == 43
    atelier.no_secret([{'path': 'a.md', 'content': '`urn:air:x:relation:' + slug + '` r1'}])
    with pytest.raises(InvalidModel):
        atelier.no_secret([{'path': 'b.md', 'content': 'token ' + 'aB3' * 14 + 'Z'}])


def test_a_gap_accepted_by_a_draft_decision_waits_for_a_human_review(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    scope = find(objects, 'Scope')
    gap_meta = deepcopy(example['meta']);gap_meta.update(id='urn:gap:payments', type='air.ArchitectureGap', name='Payment interface')
    gap = {'meta': gap_meta, 'body': {'affected_scope': exact(scope), 'impact': 'Claims are paid by hand', 'missing_element_kind': 'Interface',
                                      'resolution_owner': 'urn:team:claims'}}
    decision_meta = deepcopy(example['meta']);decision_meta.update(id='urn:decision:payments', type='air.Decision', name='Pay from an export')
    decision = {'meta': decision_meta, 'body': {'question': 'How are claims paid?', 'alternatives': ['API', 'Export'], 'selection': 'Export',
        'rationale': 'Out of scope', 'basis': [exact(gap)], 'authority': 'urn:team:claims', 'consequences': ['Daily export'], 'revisit_conditions': ['API exists']}}
    store.put_bundle([gap, decision], 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:gaps:baseline', type='air.Baseline')
    base = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in objects + [gap, decision]], 'parent_baselines': []}, 'fixture')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': {**exact(base['baseline']), 'digest': base['digest']}})
    gaps = next(c for c in gate['criteria'] if c['code'] == 'GAPS')
    assert gaps['status'] == 'NOT_MET' and 'urn:gap:payments' not in [g['id'] for g in gaps['detail']['open']]
    pending = {g['id']: g['decisions'] for g in gaps['detail']['accepted_pending_review']}
    assert pending['urn:gap:payments'] == ['urn:decision:payments'], 'a draft decision is not an approval'
