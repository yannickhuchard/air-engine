from copy import deepcopy
import json
import pytest
from air import transformation_schema as rules, transformation_view as view
from air.core import validate, reference_slots, digest
from air.foundation import exact, validate_graph
from air.projections import snapshot
from test_delivery_032 import obj
from test_portfolio import two_projects, pinned, index_portfolio, contents, USER
from air.access import AccessPolicy, Forbidden


def work(example):
    scope = obj(example, 'Scope', 'scope', {'includes': [], 'excludes': [], 'boundary_description': 'Design scope'})
    source = obj(example, 'Source', 'evidence', {'kind': 'DOCUMENT', 'locator': 'https://example.org/evidence', 'source_revision': '1', 'captured_at': '2026-10-07T10:00:00Z', 'access_policy': 'Public reference', 'retention_policy': 'Keep citation'})
    decision = obj(example, 'Decision', 'decision', {'question': 'Consult suppliers?', 'alternatives': ['RFI then RFP', 'RFP'],
        'selection': 'RFI then RFP', 'rationale': 'Evidence first', 'basis': [exact(scope)], 'authority': 'urn:role:architect', 'consequences': ['Selection before purchase'], 'revisit_conditions': ['Scope change']})
    milestone = obj(example, 'Milestone', 'milestone', {'target_date': '2027-01-01', 'deliverables': [], 'depends_on': [], 'exit_criteria': ['Evidence collected']})
    p = obj(example, 'ArchitectureProject', 'project', {'code': 'delivery', 'scope_kind': 'ARCHITECTURE_DESIGN', 'purpose': 'Design delivery', 'scope': exact(scope),
        'owner': 'urn:role:architect', 'tasks': [{'id': 'urn:delivery:task', 'revision': 1}], 'depends_on': [], 'status': 'ACTIVE'})
    t = obj(example, 'ArchitectureTask', 'task', {'project': exact(p), 'purpose': 'Review design', 'owner': 'urn:role:reviewer', 'kind': 'REVIEW', 'status': 'BLOCKED', 'depends_on': [], 'deliverables': [exact(scope)], 'evidence': []})
    programme = obj(example, 'TransformationProgramme', 'programme', {'purpose': 'Local mobility', 'scope': exact(scope), 'owner': 'urn:role:sponsor', 'projects': [exact(p)], 'start': '2026-10-01', 'end': '2028-12-31', 'status': 'ACTIVE'})
    sourcing = obj(example, 'SourcingStrategy', 'sourcing', {'scope': exact(scope), 'decision': exact(decision), 'strategy': 'RFI_THEN_RFP', 'purpose': 'Select OEM',
        'owner': 'urn:role:architect', 'milestone': exact(milestone), 'criteria': ['Measured performance'], 'architecture_links': [exact(scope)], 'status': 'DRAFT', 'evidence': []})
    return [scope, source, decision, milestone, p, t, programme, sourcing]


def codes(objects):
    by_ref = {(o['meta']['id'], o['meta']['revision']): o for o in objects}
    return {code for o in objects for code, _ in rules.local_issues(o)} | {code for code, _, _ in rules.graph_issues(objects, by_ref)}


def exported(example, objects, revision=1):
    b = obj(example, 'Baseline', 'baseline', {'members': [], 'parent_baselines': []}, revision)
    return {'baseline': b, 'objects': objects, 'digest': digest(b)}


def test_new_schema_and_typed_reference_slots(example):
    objects = work(example)
    assert not codes(objects)
    for o in objects[4:]:
        assert validate(o)['valid'], validate(o)
    slots = list(reference_slots(objects[-1]))
    assert any(s == 'body/decision' and kinds == ['air.Decision'] for s, _, kinds in slots)
    broken = deepcopy(objects); broken[-1]['body']['decision'] = exact(broken[0])
    assert not validate_graph(broken)['valid']


def test_terminal_project_cannot_hide_active_or_unlisted_tasks(example):
    objects = work(example); p, t = objects[4:6]
    p['body'].update(status='COMPLETED', closure_decision=exact(objects[2]), closed_at='2026-10-07T10:00:00Z')
    assert 'AIR_PROJECT_ACTIVE_TASK' in codes(objects)
    p['body']['tasks'] = []
    assert 'AIR_PROJECT_TASK_MEMBERSHIP' in codes(objects)
    p['body']['tasks'] = [exact(t)]
    t['body'].update(status='DONE', closed_at='2026-10-07T10:00:00Z', evidence=[exact(objects[1])])
    assert not codes(objects)
    projection = view.project([exported(example, objects)])
    assert not projection['completion_attested'] and projection['declared_work_status'] == 'ACTIVE'


def test_closure_evidence_and_real_programme_dates_are_required(example):
    objects = work(example)
    objects[4]['body']['status'] = 'COMPLETED'
    objects[5]['body']['status'] = 'DONE'
    objects[6]['body']['start'] = '2026-02-31'
    assert {'AIR_WORK_CLOSURE', 'AIR_TASK_CLOSURE', 'AIR_PROGRAMME_PERIOD'} <= codes(objects)


def test_programme_and_finish_to_start_cannot_close_over_active_work(example):
    objects = work(example); programme = objects[6]
    programme['body'].update(status='COMPLETED', closure_decision=exact(objects[2]), closed_at='2026-10-07T10:00:00Z')
    assert 'AIR_PROGRAMME_ACTIVE_WORK' in codes(objects)
    other = deepcopy(objects[4]);other['meta']['id'] += '-other';other['body'].update(tasks=[], status='PLANNED')
    objects[4]['body']['depends_on'] = [{'project': exact(other), 'kind': 'FINISH_TO_START'}]
    assert 'AIR_PROJECT_DEPENDENCY' in codes(objects + [other])


def test_cancelled_is_not_a_completed_prerequisite_and_cycles_are_rejected(example):
    objects = work(example); task = objects[5]
    other = deepcopy(task);other['meta']['id'] += '-other'
    other['body'].update(status='CANCELLED', closed_at='2026-10-07T10:00:00Z', evidence=[exact(objects[1])], depends_on=[exact(task)])
    task['body'].update(status='DONE', closed_at='2026-10-07T10:00:00Z', evidence=[exact(objects[1])], depends_on=[exact(other)])
    objects[4]['body']['tasks'].append(exact(other))
    assert {'AIR_TASK_DEPENDENCY', 'AIR_WORK_DEPENDENCY_CYCLE'} <= codes(objects + [other])


def test_sourcing_requires_scope_basis_supplier_and_launch_evidence(example):
    objects = work(example); s = objects[-1]['body']
    s['status'] = 'SELECTED'
    assert {'AIR_SOURCING_EVIDENCE', 'AIR_SOURCING_SELECTION'} <= codes(objects)
    s.update(status='LAUNCHED', strategy='NO_CONSULTATION', evidence=[exact(objects[1])])
    objects[2]['body']['basis'] = []
    assert {'AIR_SOURCING_STRATEGY', 'AIR_SOURCING_DECISION_SCOPE'} <= codes(objects)


def test_global_graph_preserves_versions_witnesses_and_safe_reading(example):
    objects = work(example); first = exported(example, objects)
    v = view.project([first]); assert v['totals']['active_tasks'] == 1
    assert any(e['relation'] == 'CONTAINS_TASK' and e['selector'] == '/body/tasks/0' for e in v['edges'])
    newer = deepcopy(first);newer['baseline']['meta']['revision'] = 2;newer['digest'] = digest(newer['baseline'])
    newer['objects'][4]['meta']['revision'] = 2
    combined = view.project([first, newer])
    assert any(g['code'] == 'WORK_REVISION_DIVERGENCE' for g in combined['gaps'])
    assert view.project([newer, first]) == combined
    assert len([n for n in combined['nodes'] if n['type'] == 'air.ArchitectureProject']) == 2
    v['nodes'][0]['name'] = '<script>alert(1)</script>' + chr(0x2014)
    html = view.html(v, standalone=True)
    assert '<script>' not in html and '&lt;script&gt;' in html and chr(0x2014) not in html
    assert 'transformation.json' in html and not v['federation_implemented']


def test_portfolio_graph_obeys_namespace_access_and_does_not_write(store, example):
    _, pins = two_projects(store, example)
    before = store.counts()
    report = index_portfolio(store, USER, AccessPolicy(), pinned(pins))
    graph = json.loads(contents(report)['transformation.json'])
    assert graph['result'] == 'NOT_DOCUMENTED' and store.counts() == before
    policy = AccessPolicy({'version': 'only-sav', 'subjects': {'portfolio-architect': {'read': ['asteria.sav', 'asteria.shared']}}})
    with pytest.raises(Forbidden): index_portfolio(store, USER, policy, pinned(pins))


def test_query_paginates_and_filters_after_authorizing_every_pin(store, example, tmp_path):
    from air.api import create_app
    from air.config import Settings
    from fastapi.testclient import TestClient
    from air.mcp import TOOLS, published_schema
    _, pins = two_projects(store, example)
    request = {'baselines': list(pins.values()), 'statuses': ['BLOCKED'], 'limit': 1}
    result = view.query(store, USER, AccessPolicy(), request)
    assert result['nodes'] == [] and result['total_matching'] == 0
    assert not result['registry_written'] and result['totals_scope'] == 'ALL_AUTHORIZED_PINS_BEFORE_FILTERS'
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    token = store.create_token(USER['subject'], 'editor'); headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        response = client.post('/v1/transformations/query', json=request, headers=headers)
        assert response.status_code == 200 and response.json() == result
        assert client.post('/v1/transformations/query', json=request).status_code == 401
        reply = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_query_transformation', 'arguments': request}},
            headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert reply.json()['result']['structuredContent'] == result
    assert TOOLS['air_query_transformation'][4] is True
    from jsonschema import Draft202012Validator
    Draft202012Validator(published_schema(TOOLS['air_query_transformation'][1])).validate(request)
    policy = AccessPolicy({'version': 'only-sav', 'subjects': {'portfolio-architect': {'read': ['asteria.sav', 'asteria.shared']}}})
    with pytest.raises(Forbidden): view.query(store, USER, policy, request)


def test_query_has_real_nonempty_pagination_and_exact_status_filter(store, example):
    from air.core import DELIVERY_PROFILE
    from test_portfolio import freeze
    objects = work(example)
    assert validate(objects)['valid']
    store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:delivery:closed-work', type='air.Baseline')
    frozen = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    pin = {**exact(frozen['baseline']), 'digest': frozen['digest']}
    first = view.query(store, USER, AccessPolicy(), {'baselines': [pin], 'limit': 1})
    second = view.query(store, USER, AccessPolicy(), {'baselines': [pin], 'limit': 1, 'offset': first['next_offset']})
    assert first['total_matching'] == 4 and first['nodes'][0]['id'] != second['nodes'][0]['id']
    blocked = view.query(store, USER, AccessPolicy(), {'baselines': [pin], 'statuses': ['BLOCKED']})
    assert len(blocked['nodes']) == blocked['total_matching'] == 1 and blocked['nodes'][0]['type'] == 'air.ArchitectureTask'
