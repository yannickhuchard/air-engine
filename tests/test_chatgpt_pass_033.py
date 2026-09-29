"""Pass 7 with ChatGPT (tranche 33): what an assistant needs before a steering committee, without rebuilding it from raw objects."""
import json
from air import agent, delivery_calc, presentation, readiness
from air.core import validate
from air.foundation import exact
from test_acceptance_033 import delivery_plan, scenarios
from test_architecture import find
from test_deliverables_032 import pack
from test_delivery_032 import POLICY, delivery, frozen, obj  # noqa: F401  (fixture re-export)


def test_the_guide_summarises_scenarios_compliance_estimate_and_roadmaps(store, example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    unit, plan, estimate, manual, agentic = delivery_plan(example)
    control = find(members, 'Control');provider = next(o for o in members if o['meta']['name'] == 'provider')
    mapping = obj(example, 'ComplianceMapping', 'mapping', {'subject': exact(control), 'status': 'PLANNED', 'mechanism': 'Review step',
                                                            'implemented_by': [exact(provider)]})
    new = added + [design, submit, back, mapping]
    store.put_bundle(new, 'fixture')
    pinned = frozen(store, example, members + new, 'urn:delivery:guided')
    report = agent.guide(store, user, POLICY, {'baseline': pinned})
    d = report['delivery']
    assert d['scenarios']['scenarios'] == 2 and d['scenarios']['fail'] == 1 and d['scenarios']['not_passing'][0]['name'] == 'scenario-back'
    assert d['compliance']['status'] == 'MET' and '34-matrice-conformite' in d['deliverables']
    assert 'air_walk_scenarios' in [s['tool'] for s in report['next_steps']]
    deliver = agent.guide(store, user, POLICY, {'baseline': pinned, 'intent': 'DELIVER'})
    assert 'air_compile_presentation' in [s['tool'] for s in deliver['next_steps']]


def test_a_requirement_not_applicable_here_names_the_project_that_implements_it(example, delivery):
    members, user, baseline, extra = delivery
    control = find(members, 'Control');decision = obj(example, 'Decision', 'allocation', {})
    mapping = obj(example, 'ComplianceMapping', 'mapping', {'subject': exact(control), 'status': 'NOT_APPLICABLE', 'mechanism': 'Implemented by the fraud project',
                                                            'decision': exact(decision), 'delegated_to': 'health.fraud'})
    assert not validate([mapping])['diagnostics']
    [row] = delivery_calc.compliance(members + [mapping], {o['meta']['id']: o for o in members})
    assert row['delegated'] == {example['meta']['namespace']: ['health.fraud']} and not row['delegation_confirmed']
    wrong = json.loads(json.dumps(mapping));wrong['body']['status'] = 'PLANNED';wrong['body']['implemented_by'] = [exact(control)]
    assert 'AIR_COMPLIANCE_DELEGATION' in {d['code'] for d in validate([wrong])['diagnostics']}


def test_the_gate_counts_borrowed_objects_that_their_owner_revised_since(store, example, delivery):
    members, user, baseline, extra = delivery
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    behind = next(c for c in gate['criteria'] if c['code'] == 'EXTERNAL_DEPENDENCIES')['detail']['behind_latest']
    assert behind == {'count': 0, 'namespaces': [], 'sample': []}


def test_the_deck_says_target_date_and_names_what_blocks_each_project(store, example, delivery):
    members, user, baseline, extra = delivery
    request = {'title': 'Plateforme', 'baselines': [baseline], 'language': 'en'}
    outline = presentation.compile_presentation(store, user, POLICY, request)['outline']
    gate = next(s for s in outline if s['key'] == 'gate')['title']
    assert 'on average' not in gate and gate.startswith('Before work starts, the design must') and 'each action is identified' in gate
    assert all('Deliverable by' not in s['title'] for s in outline)


def two_projects(example):
    from test_acceptance_033 import delivery_plan
    unit, plan, estimate, manual, agentic = delivery_plan(example)
    other = json.loads(json.dumps(agentic));other['meta'].update(namespace='other', id='urn:delivery:other-roadmap', name='other-plan')
    other['body']['status'] = 'RECOMMENDED'
    for ph in other['body']['phases']: ph['start'], ph['end'] = {'build': ('2027-01-04', '2027-02-26'), 'pilot': ('2027-03-01', '2027-06-30'), 'docs': ('2027-01-04', '2027-02-01')}[ph['id']]
    return unit, plan, estimate, manual, agentic, other


def test_a_phase_can_wait_for_a_phase_of_another_project(example):
    from air.delivery_schema import graph_issues
    unit, plan, estimate, manual, agentic, other = two_projects(example)
    wait = lambda phase, kind='FINISH_TO_START': {'roadmap': exact(other), 'phase': phase, 'kind': kind}
    agentic['body']['phases'][1]['external_depends_on'] = [wait('build')]          # pilot starts 2027-03-01, other build ends 2027-02-26: holds
    assert not validate([agentic])['diagnostics']
    index = lambda objs: {(o['meta']['id'], o['meta']['revision']): o for o in objs}
    assert not [i for i in graph_issues([agentic, other], index([agentic, other])) if i[0] == 'AIR_ROADMAP_EXTERNAL']
    agentic['body']['phases'][1]['external_depends_on'] = [wait('pilot')]          # other pilot ends 2027-06-30: too early
    issues = [i for i in graph_issues([agentic, other], index([agentic, other])) if i[0] == 'AIR_ROADMAP_EXTERNAL']
    assert issues and 'FINISH_TO_START' in issues[0][2]
    agentic['body']['phases'][1]['external_depends_on'] = [wait('pilot', 'START_TO_START')]    # both start on 2027-03-01: holds
    assert not [i for i in graph_issues([agentic, other], index([agentic, other])) if i[0] == 'AIR_ROADMAP_EXTERNAL']
    agentic['body']['phases'][1]['external_depends_on'] = [wait('pilot', 'FINISH_TO_FINISH')]   # ends 2027-05-03, before 2027-06-30
    assert [i for i in graph_issues([agentic, other], index([agentic, other])) if i[0] == 'AIR_ROADMAP_EXTERNAL']


def test_the_programme_critical_path_crosses_projects_and_flags_an_unchosen_roadmap(example):
    unit, plan, estimate, manual, agentic, other = two_projects(example)
    agentic['body']['phases'][1]['external_depends_on'] = [{'roadmap': exact(other), 'phase': 'build'}]
    objs = [unit, plan, estimate, manual, agentic, other];by_id = {o['meta']['id']: o for o in objs}
    rows = delivery_calc.roadmaps(objs, by_id, delivery_calc.estimates(objs, by_id))
    prog = delivery_calc.programme(rows)
    assert [d['satisfied'] for d in prog['dependencies']] == [True] and not prog['issues']
    assert prog['end'] == '2027-06-30' and prog['critical_path'][-1] == {'namespace': 'other', 'phase': 'pilot', 'name': 'Pilot', 'start': '2027-03-01', 'end': '2027-06-30'}
    other['body']['phases'][1]['end'] = '2027-04-30'                                   # now the home project ends last, through the other project's build
    agentic['body']['phases'][1]['depends_on'] = []
    rows = delivery_calc.roadmaps(objs, by_id, delivery_calc.estimates(objs, by_id))
    path = [(c['namespace'], c['phase']) for c in delivery_calc.programme(rows)['critical_path']]
    assert path == [('other', 'build'), (example['meta']['namespace'], 'pilot')]
    other['body']['status'] = 'REJECTED'
    rows = delivery_calc.roadmaps(objs, by_id, delivery_calc.estimates(objs, by_id))
    assert [i['code'] for i in delivery_calc.programme(rows)['issues']] == ['NOT_THE_CHOSEN_ROADMAP']


def test_a_requirement_carried_by_infrastructure_only_names_an_accountable_role(example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members)
    control = find(members, 'Control');database = next(o for o in added if o['meta']['name'] == 'database')
    sre = next(o for o in added if o['meta']['name'] == 'sre');provider = next(o for o in members if o['meta']['name'] == 'provider')
    infra = obj(example, 'ComplianceMapping', 'infra', {'subject': exact(control), 'status': 'PLANNED', 'mechanism': 'Encrypted store', 'implemented_by': [exact(database)]})
    by_id = {o['meta']['id']: o for o in members + added}
    [row] = delivery_calc.compliance(members + added + [infra], by_id)
    assert row['scope'] == 'TECHNICAL' and row['ownership'][example['meta']['namespace']] == {'scope': 'TECHNICAL', 'accountable': []}
    infra['body']['accountable'] = exact(sre);infra['body']['implemented_by'].append(exact(provider))
    assert not validate([infra])['diagnostics']
    [row] = delivery_calc.compliance(members + added + [infra], by_id)
    assert row['ownership'][example['meta']['namespace']] == {'scope': 'BOTH', 'accountable': ['sre']}


def test_a_control_only_in_the_closure_of_borrowed_objects_is_not_an_obligation(store, example, delivery):
    members, user, baseline, extra = delivery
    control = find(members, 'Control');provider = next(o for o in members if o['meta']['name'] == 'provider')
    foreign = json.loads(json.dumps(control));foreign['meta'].update(id='urn:delivery:foreign-control', namespace='other', name='foreign')
    mapping = obj(example, 'ComplianceMapping', 'mapping', {'subject': exact(control), 'status': 'PLANNED', 'mechanism': 'Review step',
                                                            'implemented_by': [exact(provider)]})
    store.put_bundle([foreign, mapping], 'fixture')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': frozen(store, example, members + [foreign, mapping], 'urn:delivery:foreign')})
    compliance = next(c for c in gate['criteria'] if c['code'] == 'COMPLIANCE')
    assert compliance['status'] == 'MET' and compliance['detail']['subjects'] == 1, 'the foreign control is cited by no object of this project'
