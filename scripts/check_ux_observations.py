"""Validate anonymized formative-study observations; never infer participant execution."""
import argparse
import json
from pathlib import Path
from air.core import record, TEXT
from air.foundation import check_schema, InvalidModel
from air.projections import SNAPSHOT

ROLES = ['EXECUTIVE', 'BUSINESS', 'IT', 'ENTERPRISE_ARCHITECT', 'SOLUTION_ARCHITECT', 'BUILDER']
TASKS = ['ORIENT', 'TRACE_MECHANISM', 'REVIEW_EVIDENCE', 'PREPARE_BUILD', 'SEND_QUESTION', 'RESUME', 'MOBILE_OFFLINE']
TASK = record({'task': {'enum': TASKS},
    'outcome': {'enum': ['UNASSISTED', 'ASSISTED', 'FAILED', 'NOT_EXECUTED']},
    'elapsed_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 7200},
    'evidence_understood': {'type': 'boolean'},
    'errors': {'type': 'array', 'uniqueItems': True, 'maxItems': 6, 'items': {'enum':
        ['WRONG_DOSSIER', 'DISCLOSURE', 'UNAUTHORIZED_WRITE', 'FALSE_EVIDENCE_ACCEPTANCE', 'NAVIGATION', 'OTHER']}}})
SESSION = record({'participant_id': {'type': 'string', 'pattern': '^p-[a-z0-9]{3,32}$'}, 'wave': {'enum': [1, 2]},
    'roles': {'type': 'array', 'minItems': 1, 'maxItems': 6, 'uniqueItems': True, 'items': {'enum': ROLES}},
    'baseline': SNAPSHOT, 'client_surface': {**TEXT, 'maxLength': 128}, 'client_version': {**TEXT, 'maxLength': 128},
    'synthetic': {'type': 'boolean'}, 'observed_by_human_declared': {'type': 'boolean'},
    'tasks': {'type': 'array', 'maxItems': 7, 'items': TASK}})
SCHEMA = record({'format': {'const': 'air.ux-observations/1'}, 'study_id': {**TEXT, 'maxLength': 128},
    'sessions': {'type': 'array', 'maxItems': 128, 'items': SESSION}})


def assess(document):
    check_schema(document, SCHEMA)
    seen = set(); observed = []; blockers = []
    for session in document['sessions']:
        identity = (session['participant_id'], session['wave'])
        if identity in seen: raise InvalidModel('Duplicate participant/wave session')
        seen.add(identity)
        tasks = [t['task'] for t in session['tasks']]
        if len(tasks) != len(set(tasks)): raise InvalidModel('Duplicate observed task')
        if session['synthetic'] or not session['observed_by_human_declared'] or not any(t['outcome'] != 'NOT_EXECUTED' for t in session['tasks']): continue
        observed.append(session)
        for task in session['tasks']:
            if task['outcome'] == 'NOT_EXECUTED': continue
            critical = set(task['errors']) & {'WRONG_DOSSIER', 'DISCLOSURE', 'UNAUTHORIZED_WRITE', 'FALSE_EVIDENCE_ACCEPTANCE'}
            if critical or not task['evidence_understood'] or task['outcome'] == 'FAILED':
                blockers.append({'participant_id': session['participant_id'], 'wave': session['wave'], 'task': task['task'],
                    'reason': sorted(critical) or ['TASK_FAILED' if task['outcome'] == 'FAILED' else 'EVIDENCE_MISUNDERSTOOD']})
    participants = {s['participant_id'] for s in observed}; roles = {r for s in observed for r in s['roles']}
    covered = {t['task'] for s in observed for t in s['tasks'] if t['outcome'] != 'NOT_EXECUTED'}
    complete = len(participants) >= 16 and {s['wave'] for s in observed} == {1, 2} and set(ROLES) <= roles and set(TASKS) <= covered
    state = 'NOT_EXECUTED' if not observed else 'CHANGES_REQUIRED' if blockers else 'READY_FOR_HUMAN_REVIEW' if complete else 'PARTIAL'
    return {'format': 'air.ux-observation-check/1', 'status': state, 'participants': len(participants),
        'observed_sessions': len(observed), 'excluded_synthetic_or_unobserved_sessions': len(document['sessions']) - len(observed),
        'missing_roles': sorted(set(ROLES) - roles), 'missing_tasks': sorted(set(TASKS) - covered), 'blockers': blockers,
        'declared_observation_authenticity_verified': False, 'human_acceptance_granted': False,
        'native_client_reception_inferred': False, 'wcag_certification_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('observations', type=Path)
    args = parser.parse_args(); report = assess(json.loads(args.observations.read_text(encoding='utf-8')))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'READY_FOR_HUMAN_REVIEW' else 2)
