from copy import deepcopy
import pytest
from air import completeness
from air.core import BUILD_PROFILE, validate
from air.foundation import exact, validate_graph
from test_build_design import design, model, exported  # noqa: F401


def assured(objects):
    objects = deepcopy(objects)
    scope = exact(next(o for o in objects if o['meta']['type'] == 'air.Scope'))
    requirement = next(o for o in objects if o['meta']['type'] == 'air.Requirement')
    original = next(o for o in objects if o['meta']['type'] == 'air.VerificationCase')
    metric = model.obj('Metric', 'business-metric', {'definition': 'Correct quotes per sample', 'unit': '1',
        'aggregation': 'count', 'population': 'Fictional quote sample', 'collection_method': 'Declared acceptance sample'})
    goal = model.obj('Goal', 'business-outcome', {'outcome': 'Deliver correct quotes', 'measures': [exact(metric)],
        'targets': [{'id': 'correct-quotes', 'metric': exact(metric), 'operator': 'GTE',
            'value': {'type': 'Decimal', 'state': 'KNOWN', 'value': '100'}, 'unit': '1', 'context': scope}]})
    quality = model.obj('QualityRequirement', 'quality', {'category': 'PERFORMANCE', 'statement': 'Bounded quote response',
        'priority': 'MUST', 'target': {'operator': 'LTE', 'value': {'type': 'Integer', 'state': 'KNOWN', 'value': 200}, 'unit': 'ms'},
        'scope': scope, 'source': 'Fictional sponsor target', 'verification_method': 'ANALYSIS'})
    def case(name, target, oracle):
        body = {**deepcopy(original['body']), 'target': target, 'method': 'ANALYSIS', 'oracle': oracle}
        return model.obj('VerificationCase', name, body)
    failure = case('failure', original['body']['target'], 'Reject a quantity outside 1 to 100')
    recovery = case('recovery', original['body']['target'], 'Recover a valid quote after a rejected request')
    quality_case = case('quality-case', exact(quality), 'Compare declared duration to 200 ms; measurements remain future work')
    lifecycle = [case(k.lower(), original['body']['target'], 'Review the declared ' + k.lower() + ' plan and its assumptions')
                 for k in ('MIGRATION', 'ROLLBACK', 'RETIREMENT')]
    context = next(o for o in objects if o['meta']['type'] == 'air.DossierContext')
    context['body']['assurance_plan'] = {
        'requirements': [{'requirement': exact(requirement), 'goal': exact(goal), 'happy': exact(original),
                          'failure': exact(failure), 'recovery': exact(recovery), 'rationale': 'Explicit quote outcomes'}],
        'quality': [{'requirement': exact(quality), 'case': exact(quality_case)}],
        'lifecycle': [{'kind': kind, 'case': exact(c), 'rationale': 'Explicit future lifecycle design review'}
                      for kind, c in zip(('MIGRATION', 'ROLLBACK', 'RETIREMENT'), lifecycle)]}
    return objects + [metric, goal, quality, failure, recovery, quality_case, *lifecycle], context


def rows(objects):
    return [r for r in completeness.project(exported(objects))['checks'] if r['id'].startswith('ASSURANCE.')]


def test_opt_in_plan_is_typed_and_does_not_change_existing_dossiers(design):
    objects = design[0]
    assert not rows(objects)
    updated, _ = assured(objects)
    assert validate(updated)['valid'], validate(updated)
    assert validate_graph(updated, BUILD_PROFILE)['valid'], validate_graph(updated, BUILD_PROFILE)
    checks = rows(updated)
    assert len(checks) == 5 and all(r['status'] == 'DOCUMENTED' for r in checks)
    report = completeness.project(exported(updated))
    assert not report['design_verified'] and not report['ready_to_build']


@pytest.mark.parametrize('gap,expected', [
    ('failure', 'DISTINCT_HAPPY_FAILURE_RECOVERY_CASES_REQUIRED'),
    ('target', 'MEASURABLE_QUALITY_TARGET_REQUIRED'),
    ('quality-case', 'QUALITY_CASE_MUST_TARGET_REQUIREMENT'),
    ('retirement', 'ONE_LIFECYCLE_CASE_REQUIRED'),
    ('mapping', 'ONE_REQUIREMENT_COVERAGE_REQUIRED'),
    ('unknown-goal', 'MEASURABLE_BUSINESS_OUTCOME_REQUIRED'),
])
def test_populated_documents_do_not_hide_missing_coverage(design, gap, expected):
    objects, context = assured(design[0]); plan = context['body']['assurance_plan']
    if gap == 'failure': plan['requirements'][0]['failure'] = plan['requirements'][0]['happy']
    elif gap == 'target': next(o for o in objects if o['meta']['type'] == 'air.QualityRequirement')['body'].pop('target')
    elif gap == 'quality-case': plan['quality'][0]['case'] = plan['requirements'][0]['happy']
    elif gap == 'retirement': plan['lifecycle'].pop()
    elif gap == 'unknown-goal':
        next(o for o in objects if o['meta']['type'] == 'air.Goal')['body']['targets'][0]['value'] = {'type': 'Decimal', 'state': 'UNKNOWN'}
    else: plan['requirements'] = []
    assert any(expected in r['issues'] and r['status'] == 'PARTIAL' for r in rows(objects))
