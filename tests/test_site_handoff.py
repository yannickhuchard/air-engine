from copy import deepcopy
import json
from pathlib import PurePosixPath
import pytest
from air import site_handoff, site_handoff_html, deliverables
from air.core import digest, schema
from air.foundation import TooLarge
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def item(kind, name, body, revision=1, namespace='project'):
    # Projection edge cases can omit semantic content, while the canonicalizer
    # still requires the metamodel's array fields and source provenance.
    defaults = {k: [] for k, v in schema('air.' + kind)['properties']['body'].get('properties', {}).items() if v.get('type') == 'array'}
    return {'meta': {'id': 'urn:test:' + name, 'revision': revision, 'type': 'air.' + kind,
                     'namespace': namespace, 'name': name, 'description': 'Design ' + name,
                     'lifecycle': 'DRAFT', 'owner': 'urn:owner:same-team', 'provenance': {'source_refs': []}}, 'body': {**defaults, **body}}


def ref(o): return {'id': o['meta']['id'], 'revision': o['meta']['revision']}
def exported(objects):
    return {'baseline': {'meta': {'id': 'urn:baseline:handoff', 'revision': 1, 'namespace': 'project'}},
            'digest': 'sha256:' + '1' * 64, 'objects': objects}
def packet(model, target): return next(p for p in model['packets'] if p['target']['id'] == target['meta']['id'])


def test_compiled_handoff_preserves_pins_sources_and_focus_diagrams(compiled):
    report, request, _ = compiled
    files = {f['path']: f['content'] for f in report['files']}
    dossier = report['website']['dossiers'][0]
    root = 'livrables/site/' + str(PurePosixPath(dossier['path']).parent) + '/'
    model = json.loads(files[root + 'handoff.json'])
    assert model['baseline'] == request['baselines'][0]
    objects = json.loads(files['livrables/architecture-model.json'])['snapshots'][0]['objects']
    exact = {(o['meta']['id'], o['meta']['revision']): o for o in objects}
    assert model['packets'] and model['teams']
    for source in model['sources']:
        original = exact[site_handoff.key(source['reference'])]
        assert source['body'] == original['body'] and source['reference']['digest'] == digest(original)
    for p in model['packets']:
        path = site_handoff_html.focus_path(p['target'])
        assert root + path in files and root + 'diagram-' + path in files
        for link in p['links']:
            original = exact[site_handoff.key(link['source'])]
            value = original
            for part in link['selector'].strip('/').split('/'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert value == link['target']
        assert not p['complete_or_approved']
    assert not model['business_execution_performed'] and not model['audience_is_access_control']


def test_required_contract_is_not_the_consumers_construction_unit():
    needed = item('SemanticContract', 'required', {'operations': []})
    unit = item('ConstructionUnit', 'provider-work', {'realizes': [ref(needed)]})
    block = item('ArchitectureBlock', 'consumer', {'functions': [], 'provided_contracts': [], 'required_contracts': [ref(needed)]})
    model = site_handoff.project(exported([block, needed, unit]), {'result': 'NOT_READY'})
    p = packet(model, block)
    assert not any(r['id'] == ref(unit)['id'] for r in p['sections']['design'])
    assert 'CONSTRUCTION_UNIT' in {g['code'] for g in p['gaps']}


def test_raci_without_subject_and_owner_do_not_assign_all_components():
    block = item('ArchitectureBlock', 'block', {'functions': []})
    role = item('Role', 'engineer', {'responsibilities': ['Design']})
    team = item('OrganizationUnit', 'team', {'roles': [ref(role)], 'mandate': 'Engineering'})
    raci = item('RaciAssignment', 'general', {'activity': 'Deliver', 'phase': 'DELIVERY', 'role': ref(role), 'responsibility': 'R'})
    model = site_handoff.project(exported([block, role, team, raci]), {'result': 'NOT_READY'})
    assert packet(model, block)['sections']['responsibilities'] == []
    assert model['teams'][0]['foci'] == []
    assert len(model['teams'][0]['unscoped_assignments']) == 1
    assert not model['unscoped_responsibilities_are_component_assignments']


def test_exact_revision_controls_raci_tests_and_associations():
    old = item('Function', 'function', {'satisfies': []})
    new = item('Function', 'function', {'satisfies': []}, revision=2)
    block = item('ArchitectureBlock', 'block', {'functions': [ref(old)]})
    role = item('Role', 'role', {'responsibilities': ['Design']})
    raci = item('RaciAssignment', 'wrong-revision', {'activity': 'Deliver', 'phase': 'DELIVERY', 'role': ref(role), 'responsibility': 'R', 'subject': ref(new)})
    case = item('VerificationCase', 'new-case', {'target': ref(new), 'method': 'TEST', 'oracle': 'New revision only'})
    objects = [old, new, block, role, raci, case]
    model = site_handoff.project(exported(objects), {'result': 'NOT_READY'})
    p = packet(model, block)
    assert not p['sections']['responsibilities'] and not p['sections']['verification']
    assert ref(old) in p['scope'] and ref(new) not in p['scope']
    assert site_handoff.project(exported(list(reversed(objects))), {'result': 'NOT_READY'}) == model


def test_oracle_does_not_become_an_executed_test_and_run_keeps_proof_level():
    block = item('ArchitectureBlock', 'block', {'functions': []})
    case = item('VerificationCase', 'case', {'target': ref(block), 'method': 'SIMULATION', 'oracle': 'Expected result'})
    export = exported([block, case]); before = deepcopy(export)
    model = site_handoff.project(export, {'result': 'NOT_READY'})
    assert export == before and 'RUNS' in {g['code'] for g in packet(model, block)['gaps']}
    run = item('VerificationRun', 'run', {'case': ref(case), 'result': 'PASS', 'method': 'SIMULATION',
                                       'proof_level': 'DECLARED_MODEL_SIMULATION', 'summary': 'Model only'})
    model = site_handoff.project(exported([block, case, run]), {'result': 'NOT_READY'})
    assert next(s for s in model['sources'] if s['type'] == 'air.VerificationRun')['body']['proof_level'] == 'DECLARED_MODEL_SIMULATION'
    assert model['gate']['code'] == 'NOT_READY' and not packet(model, block)['complete_or_approved']


def test_unresolved_refs_teams_without_roles_and_active_text_remain_visible_data():
    block = item('ArchitectureBlock', '<script>bad()</script>', {'functions': [{'id': 'urn:missing:fn', 'revision': 9}]})
    team = item('OrganizationUnit', 'empty-team', {'roles': [], 'mandate': 'No inferred role'})
    model = site_handoff.project(exported([block, team]), {'result': 'NOT_READY'})
    p = packet(model, block)
    assert p['unresolved'] == [{'id': 'urn:missing:fn', 'revision': 9}]
    assert 'UNRESOLVED_REFERENCE' in {g['code'] for g in p['gaps']}
    graph = deliverables.Graph([exported([block, team])])
    pages = site_handoff_html.pages(model, graph, lambda code, *args, **kwargs: '<pre>' + site_handoff_html.H(code) + '</pre>')
    assert all('<script>bad()' not in body for _, _, body in pages)
    assert any('&lt;script&gt;bad()' in body for _, _, body in pages)
    assert model['teams'][0]['assignments'] == []


def test_bound_and_foreign_namespace_do_not_create_an_unbounded_handoff():
    foreign = item('ArchitectureBlock', 'foreign', {'functions': []}, namespace='other')
    assert not site_handoff.project(exported([foreign]), {'result': 'NOT_READY'})['packets']
    with pytest.raises(TooLarge):
        site_handoff.project(exported([item('ArchitectureBlock', str(i), {'functions': []}) for i in range(129)]), {'result': 'NOT_READY'})
