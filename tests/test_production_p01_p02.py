"""Production audit counterexamples: authority, declared proof, units, population and money."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from air import readiness, delivery_calc, presentation
from air.access import AccessPolicy
from air.core import digest, validate
from air.deliverables import Graph, d_ai_estimate
from air.foundation import InvalidModel, exact
from air.reviews import create_review, revoke_review
from test_architecture import find
from test_delivery_032 import delivery, frozen, obj, POLICY
from test_acceptance_033 import delivery_plan


def criteria(store, user, policy, baseline):
    report = readiness.assess_readiness(store, user, policy, {'baseline': baseline})
    return {c['code']: c for c in report['criteria']}


def review_context(example, user, baseline, members):
    reviewer = {'subject': 'production-reviewer', 'role': 'editor'}
    policy = AccessPolicy({'version': 'p01', 'subjects': {
        user['subject']: {'read': ['*']},
        reviewer['subject']: {'read': ['*'], 'review': [example['meta']['namespace']]}}})
    source = find(members, 'Source')
    request = {'idempotency_key': 'p01-accept', 'baseline': baseline, 'target': baseline,
        'outcome': 'ACCEPTED', 'rationale': 'Independent synthetic review, no runtime execution.',
        'evidence': [{**exact(source), 'digest': digest(source)}],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}
    return reviewer, policy, request


@pytest.mark.parametrize('change', ['accepted', 'rejected', 'revoked', 'expired', 'policy', 'mandate', 'other_baseline'])
def test_only_current_effective_acceptance_closes_review(store, example, delivery, monkeypatch, change):
    members, user, baseline, _ = delivery
    gaps = [o for o in members if o['meta']['type'] == 'air.ArchitectureGap']
    decision = obj(example, 'Decision', 'accept-gaps', {'question': 'Accept these gaps?',
        'alternatives': ['Repair', 'Accept'], 'selection': 'Accept', 'rationale': 'Synthetic trade-off',
        'basis': [exact(g) for g in gaps], 'authority': 'urn:team:architecture',
        'consequences': ['Follow up'], 'revisit_conditions': ['Next release']})
    store.put(decision, 'fixture');members = members + [decision]
    baseline = frozen(store, example, members, 'urn:production:reviewed-decisions')
    reviewer, policy, request = review_context(example, user, baseline, members)
    if change == 'rejected': request['outcome'] = 'REJECTED'
    if change == 'other_baseline':
        other = frozen(store, example, members, 'urn:production:other-baseline')
        request.update(baseline=other, target=other)
    receipt = create_review(store, reviewer, policy, request)['record']['id']
    if change == 'revoked': revoke_review(store, reviewer, policy, {'review_id': receipt, 'rationale': 'Withdrawn'})
    if change == 'expired':
        class Future(datetime):
            @classmethod
            def now(cls, tz=None): return datetime.now(tz) + timedelta(days=2)
        monkeypatch.setattr('air.reviews.datetime', Future)
    if change in ('policy', 'mandate'):
        changed = deepcopy(policy.document)
        if change == 'policy': changed['version'] = 'p01-new'
        else: changed['subjects'][reviewer['subject']]['review'] = []
        policy = AccessPolicy(changed)
    report = criteria(store, user, policy, baseline)
    result = report['INDEPENDENT_REVIEW']
    assert result['status'] == ('MET' if change == 'accepted' else 'NOT_MET')
    assert bool(report['GAPS']['detail']['accepted_pending_review']) == (change != 'accepted')


def test_rejection_vetoes_acceptance_until_explicitly_revoked(store, example, delivery):
    members, user, baseline, _ = delivery
    reviewer, policy, request = review_context(example, user, baseline, members)
    create_review(store, reviewer, policy, request)
    rejected = create_review(store, reviewer, policy, {**request, 'idempotency_key': 'reject', 'outcome': 'REJECTED'})['record']['id']
    result = criteria(store, user, policy, baseline)['INDEPENDENT_REVIEW']
    assert result['status'] == 'NOT_MET' and len(result['detail']['rejections']) == 1
    revoke_review(store, reviewer, policy, {'review_id': rejected, 'rationale': 'Objection resolved explicitly'})
    assert criteria(store, user, policy, baseline)['INDEPENDENT_REVIEW']['status'] == 'MET'
    with pytest.raises(InvalidModel, match='budget exceeded'):
        store.reviews_of(baseline['id'], example['meta']['namespace'], limit=1)


def test_unreadable_review_never_silently_discards_a_rejection(store, example, delivery, monkeypatch):
    from air.access import Forbidden
    from air import reviews
    members, user, baseline, _ = delivery
    reviewer, policy, request = review_context(example, user, baseline, members)
    create_review(store, reviewer, policy, request)
    rejected = create_review(store, reviewer, policy, {**request, 'idempotency_key': 'reject', 'outcome': 'REJECTED'})['record']['id']
    original = reviews.read_review
    def guarded(store, principal, policy, receipt):
        if receipt == rejected: raise Forbidden('Private evidence must not leak')
        return original(store, principal, policy, receipt)
    monkeypatch.setattr(reviews, 'read_review', guarded)
    result = criteria(store, user, policy, baseline)['INDEPENDENT_REVIEW']
    assert result['status'] == 'NOT_MET' and result['detail']['review_unavailable']
    assert 'Private evidence' not in json.dumps(result)


def test_all_declared_proof_levels_stay_unverified_even_after_baseline_acceptance(store, example, delivery):
    members, user, _, _ = delivery
    additions = []
    for method, proof in [('ANALYSIS', 'ANALYSIS'), ('INSPECTION', 'INSPECTION'), ('REVIEW', 'REVIEW'),
                          ('SIMULATION', 'CALIBRATED_SIMULATION'), ('TEST', 'EXECUTED_TEST')]:
        case = obj(example, 'VerificationCase', 'claimed-' + method, {'target': exact(find(members, 'Function')),
            'method': method, 'inputs': [], 'oracle': 'Independent assessment required', 'acceptance': 'Evidence',
            'independence_basis': 'Must be qualified'})
        run = obj(example, 'VerificationRun', 'claim-' + method, {'case': exact(case), 'method': method,
            'result': 'PASS', 'proof_level': proof, 'executed_at': '2026-09-25T00:00:00Z',
            'executor': 'urn:untrusted:executor', 'summary': 'Self-declared success'})
        if method in ('TEST', 'SIMULATION'):
            # An existing, readable artifact is not necessarily a report proving this case.
            run['body']['report'] = find(members, 'DataSchema')['body']['artifact']
        if method == 'SIMULATION': run['body']['scenario'] = exact(find(members, 'SimulationScenario'))
        assert validate(run)['valid'], validate(run)['diagnostics']
        additions += [case, run]
    store.put_bundle(additions, user['subject'])
    pinned = frozen(store, example, members + additions, 'urn:production:claims')
    reviewer, policy, request = review_context(example, user, pinned, members)
    create_review(store, reviewer, policy, request)
    report = readiness.assess_readiness(store, user, policy, {'baseline': pinned})
    verification = next(c for c in report['criteria'] if c['code'] == 'VERIFICATION')
    claimed = [c for c in verification['detail']['cases_detail'] if c['name'].startswith('claimed-')]
    assert len(claimed) == 5 and all(c['status'] == 'PASS_UNVERIFIED' for c in claimed)
    assert verification['status'] == 'NOT_MET' and report['proof']['verified_cases'] == 0
    assert report['proof']['unverified_passes'] == 5 and report['proof']['qualified_design_cases'] == 0


def observation(value='100', unit='Quantity[ms]', label='latency p95'):
    return {'meta': {'id': 'urn:production:observation', 'revision': 1, 'type': 'air.RuntimeObservation', 'name': label},
            'body': {'metric_or_signal': label, 'value_or_artifact': {'type': unit, 'value': value}}}


def calibrate(obs, refs=None, model_value=100):
    return readiness.calibration({'step': {'step': 'step', 'distribution': {'kind': 'FIXED', 'value': model_value},
        'calibrated_from': refs or [exact(obs)]}}, {('urn:production:observation', 1): obs})['step']


@pytest.mark.parametrize('value,unit', [('100', 'Quantity[requests]'), ('100', 'Integer'), ('100', ''),
    ('-1', 'Quantity[ms]'), ('NaN', 'Quantity[ms]'), ('Infinity', 'Quantity[s]'), ('1e309', 'Quantity[ms]'),
    ('1e308', 'Quantity[s]'), (True, 'Quantity[ms]')])
def test_non_duration_or_invalid_number_cannot_calibrate(value, unit):
    result = calibrate(observation(value, unit))
    assert not result['calibrated'] and result['observations'][0]['status'] == 'NOT_A_DURATION_STATISTIC'
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('value,unit', [('100', 'Quantity[ms]'), ('0.1', 'Quantity[s]')])
def test_duration_conversion_and_all_cited_observations_must_be_usable(value, unit):
    obs = observation(value, unit)
    assert calibrate(obs)['calibrated']
    mixed = calibrate(obs, [exact(obs), {'id': 'urn:absent', 'revision': 1}])
    assert not mixed['calibrated']
    assert mixed['observations'][1]['status'] == 'ABSENT_FROM_BASELINE'


def test_ambiguous_statistics_unknown_values_and_zero_are_explicit():
    assert not calibrate(observation(label='p50 p95'))['calibrated']
    obs = observation();obs['body']['value_or_artifact']['state'] = 'UNKNOWN'
    assert not calibrate(obs)['calibrated']
    assert calibrate(observation('0'), model_value=0)['calibrated']
    disagree = calibrate(observation('0'))
    assert not disagree['calibrated'] and disagree['observations'][0]['deviation'] is None
    json.dumps(disagree, allow_nan=False)


@pytest.mark.parametrize('fault', ['unknown_guard', 'missing_duration', 'no_measure', 'wrong_units', 'rounding'])
def test_simulation_reports_incomplete_population_and_wrong_units(store, example, delivery, monkeypatch, fault):
    members, user, _, extra = delivery
    scenario = deepcopy(extra[3]);scenario['meta']['id'] = 'urn:production:scenario'
    additions = []
    if fault == 'unknown_guard':
        scenario['body']['classes'][0]['context'] = {'score': {'type': 'Integer', 'state': 'UNKNOWN'}}
    elif fault == 'no_measure':
        scenario['body']['classes'] = [scenario['body']['classes'][0]]
    elif fault == 'rounding':
        scenario['body']['target']['max_ms'] = 1000
        monkeypatch.setattr(readiness, '_sample', lambda rng, distribution: 333.34)
    else:
        model = deepcopy(extra[1]);model['meta']['id'] = 'urn:production:model'
        if fault == 'missing_duration': model['body']['steps'] = model['body']['steps'][1:]
        else:
            scope = exact(find(members, 'Scope'))
            obs = obj(example, 'RuntimeObservation', 'requests', {'instance_or_scope': scope,
                'metric_or_signal': 'throughput p95', 'window': {'start': '2026-09-24T00:00:00Z', 'end': '2026-09-25T00:00:00Z'},
                'value_or_artifact': {'type': 'Quantity[requests]', 'value': '100'},
                'coverage': {'scope': scope, 'included': [scope], 'excluded': [], 'completeness': 'PARTIAL',
                             'limitations': ['Request counts, not durations']}})
            obs['meta']['provenance']['source_refs'] = [exact(find(members, 'Source'))]
            for step in model['body']['steps']:
                step.update(distribution={'kind': 'FIXED', 'value': 100}, calibrated_from=[exact(obs)])
            assert validate(obs)['valid']
            additions.append(obs)
        additions.append(model);scenario['body']['performance_model'] = exact(model)
    additions.append(scenario)
    store.put_bundle(additions, 'fixture')
    pinned = frozen(store, example, members + additions, 'urn:production:simulation')
    request = {'baseline': pinned, 'scenario': {**exact(scenario), 'digest': digest(scenario)}}
    result = readiness.simulate_scenario(store, user, POLICY, request)
    assert result == readiness.simulate_scenario(store, user, POLICY, request)
    population = result['population']
    assert population['requested_runs'] == population['measured_runs'] + population['excluded_runs'] == 2000
    if fault == 'wrong_units':
        assert result['model_qualification'] == 'DECLARED' and not result['calibrated_steps']
    elif fault == 'rounding':
        assert result['verdict'] == 'FAIL' and result['observed_at_target_percentile'] > 1000
        assert result['latency_ms']['p95'] == 1000, 'display rounding must not turn a failing result into PASS'
    else:
        assert result['verdict'] == 'INCONCLUSIVE' and result['inconclusive_reasons']
        if fault != 'no_measure': assert result['conditional_verdict'] == 'PASS'
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('fault', ['subscription', 'reference'])
def test_incompatible_roadmap_currencies_are_rejected(example, fault):
    objects = list(delivery_plan(example))
    if fault == 'subscription': objects[1]['body']['price']['currency'] = 'USD'
    else: objects[3]['body']['day_rate'] = {'value': '700', 'currency': 'USD'}
    by_id = {o['meta']['id']: o for o in objects}
    with pytest.raises(InvalidModel, match='Mixed currencies'):
        delivery_calc.roadmaps(objects, by_id, delivery_calc.estimates(objects, by_id))


def test_usd_is_preserved_and_mixed_estimate_and_deck_totals_are_rejected(example):
    objects = list(delivery_plan(example))
    objects[1]['body']['price']['currency'] = 'USD'
    for o in objects[3:]: o['body']['day_rate']['currency'] = 'USD'
    graph = Graph([{'objects': objects}])
    figures = presentation.figures(graph, [])
    assert figures['currency'] == 'USD' and figures['maps'][1]['labour_cost'] == Decimal(42000)
    assert 'USD' in presentation.keur(Decimal(42000), currency=figures['currency'])
    assert '€' not in presentation.keur(Decimal(42000), currency=figures['currency'])
    euro_plan = deepcopy(objects[1]);euro_plan['meta']['id'] += '-eur';euro_plan['body']['price']['currency'] = 'EUR'
    other = deepcopy(objects[2]);other['meta']['id'] += '-eur';other['body']['plan'] = exact(euro_plan)
    mixed = Graph([{'objects': objects + [euro_plan, other]}])
    with pytest.raises(InvalidModel, match='Mixed currencies'): d_ai_estimate(mixed)
    with pytest.raises(InvalidModel, match='Mixed currencies'): presentation.figures(mixed, [])


def test_deck_never_promotes_declared_calibration_to_behavioural_proof(store, example, delivery):
    members, user, baseline, _ = delivery
    gates = [readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})]
    for result in ('PASS', 'FAIL', 'INCONCLUSIVE'):
        run = obj(example, 'VerificationRun', 'claimed-simulation', {'method': 'SIMULATION', 'result': result,
            'proof_level': 'CALIBRATED_SIMULATION'})
        graph = Graph([{'objects': members + [run]}])
        for lang in ('fr', 'en'):
            slides = presentation.storyline(graph, gates, {'title': 'Declared results', 'baselines': [baseline]}, lang)
            events = next(s for s in slides if s['key'] == 'events')
            text = json.dumps(events, ensure_ascii=False)
            assert 'Response times are demonstrated' not in text and 'Les temps de réponse sont démontrés' not in text
            assert 'confirmed by measurements' not in text and 'confirmée par des mesures' not in text
            assert ('déclar' if lang == 'fr' else 'declar') in text
