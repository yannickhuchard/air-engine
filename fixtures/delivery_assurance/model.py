"""Fictional feature recipe: My Help and My Health are labels, not a real project audit."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from air.foundation import exact, validate_graph
from air.core import BUILD_PROFILE

spec = importlib.util.spec_from_file_location('build_reference', Path(__file__).resolve().parents[1] / 'build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
NAMESPACE = model.NAMESPACE


def objects(schema_artifacts, ci_report, subject):
    objects = deepcopy(model.objects(schema_artifacts))
    user = {'subject': subject}
    extras = [model.obj('Environment', 'test-environment', {'stage': 'BUILD_TEST', 'purpose': 'Reference only', 'hosting': 'Local isolated fixture'}),
        model.obj('OperationalEvidence', 'ci', {'case': model.ref('case'), 'kind': 'CI_CD', 'result': 'PASS',
            'executed_at': '2026-10-18T12:00:00Z', 'executor': user['subject'], 'environment': model.ref('test-environment'),
            'report': ci_report, 'summary': 'Fictional recorded fixture, not an actual CI execution', 'metrics': [],
            'run_url': 'https://ci.example.invalid/runs/1', 'source_revision': 'fictional-source-1'})]
    chain = ['requirement', 'control', 'request-schema', 'quote-contract', 'case', 'ci']
    for i, (source, target) in enumerate(zip(chain, chain[1:])):
        extras.append(model.obj('TraceabilityLink', 'trace-' + str(i), {'source': model.ref(source), 'target': model.ref(target), 'rationale': 'Explicit fictional trace witness'}))
    members = [model.ref(x) for x in chain] + [exact(o) for o in extras if o['meta']['type'] == 'air.TraceabilityLink']
    for name, deps in [('common', []), ('my-help', [model.ref('common')])]:
        extras.append(model.obj('ScopeGate', name, {'scope': model.ref('scope'), 'purpose': name,
            'requirements': [model.ref('requirement')], 'members': members, 'depends_on': deps,
            'review_required': False, 'verification_policy': 'RECORDED_TESTS'}))
    other = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Requirement'))
    other['meta']['id'] = model.ref('health-requirement')['id']; other['meta']['name'] = 'My Health uncovered requirement'; extras.append(other)
    extras.append(model.obj('ScopeGate', 'my-health', {'scope': model.ref('scope'), 'purpose': 'My Health',
        'requirements': [exact(other)], 'members': [exact(other)], 'depends_on': [model.ref('common')],
        'review_required': False, 'verification_policy': 'RECORDED_TESTS'}))
    project = model.obj('ArchitectureProject', 'project', {'code': 'delivery', 'scope_kind': 'ARCHITECTURE_DESIGN', 'purpose': 'Fictional design tracking',
        'scope': model.ref('scope'), 'owner': user['subject'], 'tasks': [model.ref('task')], 'depends_on': [], 'status': 'ACTIVE'})
    task = model.obj('ArchitectureTask', 'task', {'project': model.ref('project'), 'purpose': 'Track the actual design work', 'owner': user['subject'],
        'team': 'urn:team:platform', 'members': [], 'kind': 'MODELLING', 'status': 'IN_PROGRESS', 'depends_on': [], 'deliverables': [], 'evidence': [],
        'start': '2026-10-12', 'due': '2026-10-16', 'blockers': [model.ref('health-requirement')], 'blocker_reason': 'Health design unanswered'})
    extras += [project, task]; objects += extras
    checked = validate_graph(objects, BUILD_PROFILE); assert checked['valid'], checked
    return objects
