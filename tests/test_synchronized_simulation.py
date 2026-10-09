from copy import deepcopy

import pytest

from air import readiness
from air.core import digest
from air.foundation import exact, InvalidModel
from test_delivery_032 import delivery, frozen, POLICY


def diamond(store, example, delivery, join='ALL', closed_branch=False, start_bypass=False):
    members, user, _, extra = delivery
    workflow, model, scenario = (deepcopy(extra[i]) for i in (0, 1, 3))
    for item in (workflow, model, scenario): item['meta']['id'] += '-diamond'
    steps = workflow['body']['steps']
    ids = ['start', 'fast', 'slow', 'finish']
    for step, sid in zip(steps, ids):
        step.update(id=sid, binding='air.workflow-step/0.35', join=join if sid == 'finish' else 'ANY')
    workflow['body']['start_steps'] = ['start']
    if start_bypass: workflow['body']['start_steps'].append('finish')
    workflow['body']['flows'] = [{'binding': 'air.workflow-flow/0.32', 'id': fid,
        'source': source, 'target': target, 'condition': 'Synthetic parallel path'}
        for fid, source, target in [('a', 'start', 'fast'), ('b', 'start', 'slow'),
                                    ('c', 'fast', 'finish'), ('d', 'slow', 'finish')]]
    if closed_branch:
        workflow['body']['flows'][1]['guard'] = {'language': 'AIR-Expr', 'language_version': '0.1',
            'result_type': 'Boolean', 'ast': {'literal': {'type': 'Boolean', 'value': False}}}
    model['body'].update(workflow=exact(workflow), steps=[{'step': sid, 'distribution': {'kind': 'FIXED', 'value': ms}}
        for sid, ms in zip(ids, [10, 20, 70, 5])])
    scenario['body'].update(workflow=exact(workflow), performance_model=exact(model),
        measure={'from_step': 'start', 'to_step': 'finish'}, runs=10,
        classes=[{'name': 'parallel', 'weight': 1, 'context': {}, **({'start_step': 'finish'} if start_bypass else {})}])
    additions = [workflow, model, scenario]
    store.put_bundle(additions, 'fixture')
    base = frozen(store, example, members + additions, 'urn:diamond:baseline')
    return user, {'baseline': base, 'scenario': {**exact(scenario), 'digest': digest(scenario)}}


@pytest.mark.parametrize('join,oracle', [('ALL', 85), ('ANY', 35)])
def test_parallel_latency_uses_declared_synchronization(store, example, delivery, join, oracle):
    user, request = diamond(store, example, delivery, join)
    result = readiness.simulate_scenario(store, user, POLICY, request)
    # Independent arithmetic: start + max/min(20,70) + finish.
    assert result['latency_ms']['p95'] == oracle
    assert result['engine'] == 'air.scenario-simulation/0.35'
    assert result['synchronizations']['blocked'] == []
    assert not result['external_effects']
    assert result == readiness.simulate_scenario(store, user, POLICY, request)


def test_untaken_branch_does_not_silently_release_all_join(store, example, delivery):
    user, request = diamond(store, example, delivery, closed_branch=True)
    result = readiness.simulate_scenario(store, user, POLICY, request)
    assert result['verdict'] == 'INCONCLUSIVE'
    assert result['population']['measured_runs'] == 0
    assert result['synchronizations']['blocked'] == [{'class': 'parallel', 'step': 'finish', 'runs': 10}]


def test_start_override_cannot_bypass_synchronization(store, example, delivery):
    user, request = diamond(store, example, delivery, start_bypass=True)
    with pytest.raises(InvalidModel, match='incoming flows'):
        readiness.simulate_scenario(store, user, POLICY, request)
