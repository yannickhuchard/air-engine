from copy import deepcopy
import pytest
from air import effort_calibration
from air.core import digest
from air.foundation import exact, InvalidModel
from test_build_design import model, exported, design  # noqa: F401


def sample():
    unit = model.obj('ConstructionUnit', 'unit', {'realizes': [model.ref('quote')], 'work_kind': 'SOFTWARE',
        'outputs': [{'name': 'quote implementation', 'kind': 'CODE', 'description': 'Fictional construction output'}],
        'acceptance': [model.ref('acceptance')], 'justified_by': [model.ref('requirement')],
        'resource_demand': [], 'estimate': model.ref('estimate-provider')})
    estimate = model.obj('DeliveryEstimate', 'delivery-estimate', {'unit': exact(unit), 'plan': model.ref('agentic-plan'),
        'activities': [{'activity': 'CODE', 'effort_pd': '10', 'ai_applicable': True, 'ai_effort_pd': '5', 'rationale': 'Illustrative forecast'},
                       {'activity': 'REVIEW', 'effort_pd': '2', 'ai_applicable': False, 'rationale': 'Human review'}],
        'team': {'workers': 1, 'ai_seats': 1}, 'confidence': 'LOW', 'basis': 'Fictional estimate'})
    pin = lambda o: {**exact(o), 'digest': digest(o)}
    base = {'unit': pin(unit), 'estimate': pin(estimate), 'person_days': '4', 'review_person_days': '0',
        'rework_person_days': '1', 'ai_used': True, 'started_at': '2026-10-01T00:00:00Z',
        'finished_at': '2026-10-02T00:00:00Z', 'source_record': 'urn:fictional:timesheet:1'}
    rows = [{**base, 'id': 'code', 'activity': 'CODE'},
            {**base, 'id': 'review', 'activity': 'REVIEW', 'person_days': '3', 'review_person_days': '3', 'rework_person_days': '0'}]
    return exported([unit, estimate]), {'format': 'air.effort-observations/1', 'observations': rows}


def test_review_and_rework_are_included_and_ai_effect_is_not_inferred():
    e, observations = sample()
    result = effort_calibration.project(e, observations, '2026-10-03T00:00:00Z')
    row = result['results'][0]
    assert row['actual_person_days'] == '7' and row['planned_ai_person_days'] == '7'
    assert row['review_person_days'] == '3' and row['rework_person_days'] == '1'
    assert row['forecast_ratio'] == '1' and row['comparison_state'] == 'COMPARABLE_RECORDED_EFFORT'
    assert not result['ai_productivity_gain_causally_established'] and not result['source_authenticity_verified']


def test_partial_and_mixed_work_cannot_claim_a_comparable_ratio():
    e, observations = sample()
    observations['observations'][0]['ai_used'] = False
    row = effort_calibration.project(e, observations, '2026-10-03T00:00:00Z')['results'][0]
    assert row['comparison_state'] == 'MIXED_USAGE' and row['forecast_ratio'] is None
    observations['observations'].pop()
    row = effort_calibration.project(e, observations, '2026-10-03T00:00:00Z')['results'][0]
    assert row['comparison_state'] == 'PARTIAL' and row['missing_activities'] == ['REVIEW'] and row['forecast_ratio'] is None


@pytest.mark.parametrize('fault', ['duplicate', 'revision', 'future', 'totals', 'wrong-unit'])
def test_inconsistent_actuals_are_rejected(fault):
    e, observations = sample(); row = observations['observations'][0]
    if fault == 'duplicate': observations['observations'].append(deepcopy(row))
    elif fault == 'revision': row['estimate']['digest'] = 'sha256:' + '0' * 64
    elif fault == 'future': row['finished_at'] = '2027-01-01T00:00:00Z'
    elif fault == 'totals': row['review_person_days'] = '10'
    else: e['objects'][1]['body']['unit']['id'] = 'urn:wrong:unit'
    with pytest.raises(InvalidModel): effort_calibration.project(e, observations, '2026-10-03T00:00:00Z')


def test_http_calibration_reads_retained_observations_and_rechecks_their_namespace(store, design):
    import json
    from fastapi.testclient import TestClient
    from air import artifacts
    from air.access import AccessPolicy
    from air.api import create_app
    from air.core import BUILD_PROFILE

    objects, user, token, settings, base = design
    unit = next(o for o in objects if o['meta']['id'] == model.ref('provider-unit')['id'])
    sample_export, observations = sample()
    estimate = sample_export['objects'][1]
    estimate['body']['unit'] = exact(unit)
    plan = model.obj('AgenticToolPlan', 'agentic-plan', {'vendor': 'Fictional provider',
        'product': 'Fictional assistant', 'plan': 'Isolated fixture',
        'price': {'value': '0', 'currency': 'EUR'}, 'per': 'SEAT_MONTH',
        'data_policy': 'Synthetic test data only', 'status': 'ASSESS'})
    store.put_bundle([estimate, plan], user['subject'])
    meta = deepcopy(store.get(base['baseline']['id'], base['baseline']['revision'])['object']['meta'])
    meta['revision'] += 1
    frozen = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in [*objects, estimate, plan]],
        'parent_baselines': [exact(store.get(base['baseline']['id'], base['baseline']['revision'])['object'])]}, user['subject'])
    pin = lambda o: {**exact(o), 'digest': digest(o)}
    for row in observations['observations']:
        row.update(unit=pin(unit), estimate=pin(estimate))
    retained = artifacts.put(store, user, AccessPolicy(), settings, {'namespace': 'effort-records',
        'media_type': 'application/json', 'idempotency_key': 'actuals'}, json.dumps(observations).encode())
    request = {'baseline': pin(frozen['baseline']), 'observations': retained['artifact'],
        'as_of': '2026-10-03T00:00:00Z'}
    with TestClient(create_app(settings, run_worker=False)) as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/effort/calibrate', headers=headers, json=request)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['results'][0]['actual_person_days'] == '7'
        assert not result['registry_written'] and not result['source_authenticity_verified']
        (settings.home / 'access-policy.json').write_text(json.dumps({'version': 'deny-effort',
            'subjects': {user['subject']: {'read': [model.NAMESPACE]}}}))
        assert client.post('/v1/effort/calibrate', headers=headers, json=request).status_code == 403
