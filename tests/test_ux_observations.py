from copy import deepcopy
import pytest
from air.foundation import InvalidModel
from scripts.check_ux_observations import assess, ROLES, TASKS


def document():
    return {'format': 'air.ux-observations/1', 'study_id': 'fictional-checker-test', 'sessions': []}


def session():
    return {'participant_id': 'p-001', 'wave': 1, 'roles': ROLES,
        'baseline': {'id': 'urn:fixture:baseline', 'revision': 1, 'digest': 'sha256:' + '0' * 64},
        'client_surface': 'fictional test surface', 'client_version': 'test', 'synthetic': True,
        'observed_by_human_declared': False, 'tasks': [{'task': t, 'outcome': 'UNASSISTED',
            'elapsed_seconds': 10, 'evidence_understood': True, 'errors': []} for t in TASKS]}


def test_empty_and_synthetic_sessions_never_count_as_human_results():
    d = document(); assert assess(d)['status'] == 'NOT_EXECUTED'
    d['sessions'] = [session()]
    r = assess(d); assert r['status'] == 'NOT_EXECUTED' and r['participants'] == 0
    assert not r['human_acceptance_granted']


def test_declared_observation_errors_block_review_and_are_not_certified():
    d = document(); s = session(); s.update(synthetic=False, observed_by_human_declared=True)
    s['tasks'][0]['errors'] = ['FALSE_EVIDENCE_ACCEPTANCE']; d['sessions'] = [s]
    r = assess(d); assert r['status'] == 'CHANGES_REQUIRED' and r['blockers']
    assert not r['declared_observation_authenticity_verified']
    d['sessions'].append(deepcopy(s))
    with pytest.raises(InvalidModel, match='Duplicate'): assess(d)
