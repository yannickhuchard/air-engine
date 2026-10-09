"""Tranche 33: acceptance scenarios walked on the design, compliance received as input, AI-assisted estimates and roadmaps."""
import json
from decimal import Decimal
from air import acceptance, delivery_calc, presentation, readiness
from air.core import DELIVERY_PROFILE, validate
from air.foundation import exact, validate_graph
from test_architecture import find
from test_deliverables_032 import pack
from test_delivery_032 import POLICY, delivery, expression, frozen, obj  # noqa: F401  (fixture re-export)


def scenarios(example, members, added):
    actor = find(members, 'Actor');contract = find(members, 'SemanticContract');function = find(members, 'Function')
    navigation = next(o for o in added if o['meta']['type'] == 'air.NavigationMap')
    design = obj(example, 'VerificationCase', 'walk-case', {'target': exact(function), 'method': 'ANALYSIS', 'inputs': [],
        'oracle': 'Every step reachable', 'acceptance': 'Walk verdict PASS', 'independence_basis': 'Deterministic walk'})
    submit = obj(example, 'AcceptanceScenario', 'scenario-submit', {'navigation': exact(navigation), 'persona': exact(actor), 'goal': 'Submit a claim',
        'suites': ['REGRESSION', 'ACCEPTANCE'], 'priority': 'CRITICAL', 'preconditions': ['The member is signed in'], 'design_case': exact(design),
        'steps': [{'id': 's1', 'screen': 'home', 'action': 'Open the portal', 'expected': 'Home shown'},
                  {'id': 's2', 'screen': 'claim-form', 'action': 'Send the claim', 'via': 'start', 'operation': {'contract': exact(contract), 'name': 'Submit'},
                   'expected': 'Claim accepted'}]})
    back = obj(example, 'AcceptanceScenario', 'scenario-back', {'navigation': exact(navigation), 'persona': exact(actor), 'goal': 'Go back home',
        'suites': ['ACCEPTANCE'], 'priority': 'LOW',
        'steps': [{'id': 's1', 'screen': 'home', 'action': 'Open', 'expected': 'Home'}, {'id': 's2', 'screen': 'claim-form', 'action': 'Start', 'expected': 'Form'},
                  {'id': 's3', 'screen': 'home', 'action': 'Cancel', 'expected': 'Home again'}]})
    return design, submit, back


def test_a_scenario_walks_the_navigation_graph_and_measures_coverage(example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    report = acceptance.walk(members + added + [design, submit, back], None, owned_only=False)
    verdicts = {r['name']: r for r in report['scenarios']}
    assert verdicts['scenario-submit']['verdict'] == 'PASS' and verdicts['scenario-submit']['covered_transitions'] == ['start']
    assert verdicts['scenario-back']['verdict'] == 'FAIL' and 'No transition leads from claim-form to home' in verdicts['scenario-back']['findings'][0]['issue']
    coverage = report['coverage'][0]
    assert coverage['screens_covered'] == 2 and coverage['transitions_uncovered'] == [] and coverage['operations_uncovered'] == []
    assert coverage['dead_ends'] == ['claim-form'], 'a wizard step with no way out is a dead end'
    assert [r['name'] for r in report['regression_suite']] == ['scenario-submit'] and report['summary'] == {'scenarios': 2, 'pass': 1, 'fail': 1, 'inconclusive': 0}
    assert report['journeys'][0]['not_exercised'] == [], 'the journey operation is exercised by a scenario'


def test_guards_are_decided_on_the_scenario_context(example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    navigation = next(o for o in added if o['meta']['type'] == 'air.NavigationMap')
    navigation['body']['transitions'][0]['guard'] = expression('gte', 'score', 50)
    index = {(o['meta']['id'], o['meta']['revision']): o for o in members + added}
    assert acceptance.walk_scenario(submit, index)['verdict'] == 'INCONCLUSIVE', 'no context: the guard is undecided'
    submit['body']['context'] = {'score': {'type': 'Integer', 'value': 10}}
    assert acceptance.walk_scenario(submit, index)['verdict'] == 'FAIL'
    submit['body']['context'] = {'score': {'type': 'Integer', 'value': 70}}
    assert acceptance.walk_scenario(submit, index)['verdict'] == 'PASS'


def test_the_walk_of_a_baseline_drafts_analysis_runs_and_writes_nothing(store, example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    store.put_bundle(added + [design, submit, back], 'fixture')
    pinned = frozen(store, example, members + added + [design, submit, back], 'urn:delivery:walk')
    report = acceptance.walk_baseline(store, user, POLICY, {'baseline': pinned})
    assert report['registry_written'] is False and len(report['verification_runs']) == 1 and report['summary']['fail'] == 1
    run = report['verification_runs'][0]
    assert run['meta']['id'].endswith(':walk') and run['meta']['type'] == 'air.VerificationRun'
    assert run['body']['method'] == 'ANALYSIS' and run['body']['result'] == 'PASS' and run['body']['case'] == exact(design)
    assert not validate([run])['diagnostics']


def test_scenario_steps_must_exist_on_the_map(example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    lost = json.loads(json.dumps(submit));lost['body']['steps'][1]['screen'] = 'nowhere'
    graph = validate_graph(members + added + [design, lost], DELIVERY_PROFILE)['diagnostics']
    assert any(d['code'] == 'AIR_SCENARIO_SCREEN' and 'nowhere' in d['message'] for d in graph)
    twice = json.loads(json.dumps(submit));twice['body']['steps'][1]['id'] = 's1'
    assert 'AIR_SCENARIO_STEP' in {d['code'] for d in validate([twice])['diagnostics']}


def delivery_plan(example):
    unit = obj(example, 'ConstructionUnit', 'unit', {})  # only its identity and name are read by the calculator
    plan = obj(example, 'AgenticToolPlan', 'agentic-ide', {'vendor': 'Vendor', 'product': 'Agentic IDE', 'plan': 'Team',
        'price': {'value': '40', 'currency': 'EUR'}, 'per': 'SEAT_MONTH', 'data_policy': 'No training on customer code', 'status': 'TRIAL'})
    estimate = obj(example, 'DeliveryEstimate', 'estimate', {'unit': exact(unit), 'plan': exact(plan), 'team': {'workers': 2, 'ai_seats': 2},
        'confidence': 'MEDIUM', 'basis': 'Comparable services',
        'activities': [{'activity': 'CODE', 'effort_pd': '60', 'ai_applicable': True, 'ai_effort_pd': '30', 'rationale': 'Agents write the adapters'},
                       {'activity': 'UNIT_TEST', 'effort_pd': '20', 'ai_applicable': True, 'ai_effort_pd': '10', 'rationale': 'Generated tests, reviewed'},
                       {'activity': 'REVIEW', 'effort_pd': '20', 'ai_applicable': False, 'rationale': 'Human review stays whole'}]})

    def phases(ai):
        switch = '2027-03-01' if ai else '2027-04-01'
        return [{'id': 'build', 'name': 'Build', 'objective': 'Build the unit', 'start': '2027-01-04', 'end': switch, 'units': [exact(unit)], 'team_size': 2},
                {'id': 'pilot', 'name': 'Pilot', 'objective': 'Pilot', 'start': switch, 'end': '2027-05-03', 'depends_on': ['build'], 'team_size': 2},
                {'id': 'docs', 'name': 'Docs', 'objective': 'Document', 'start': '2027-01-04', 'end': '2027-02-01', 'team_size': 1}]
    rate = {'value': '700', 'currency': 'EUR'}
    manual = obj(example, 'Roadmap', 'roadmap-manual', {'strategy': 'Sequential, no AI', 'uses_ai': False, 'day_rate': rate,
        'phases': phases(False), 'status': 'PROPOSED', 'rationale': 'Reference'})
    agentic = obj(example, 'Roadmap', 'roadmap-ai', {'strategy': 'Agentic', 'uses_ai': True, 'plan': exact(plan), 'day_rate': rate,
        'phases': phases(True), 'status': 'RECOMMENDED', 'rationale': 'Shorter at a small subscription cost'})
    return unit, plan, estimate, manual, agentic


def test_the_ai_estimate_shows_the_delta_and_the_subscription_cost(example):
    unit, plan, estimate, manual, agentic = delivery_plan(example)
    assert not validate([plan, estimate, manual, agentic])['diagnostics']
    by_id = {o['meta']['id']: o for o in [unit, plan, estimate, manual, agentic]}
    [row] = delivery_calc.estimates(list(by_id.values()), by_id)
    assert (row['without_ai_pd'], row['with_ai_pd'], row['delta_pd']) == (Decimal(100), Decimal(60), Decimal(40)) and row['delta_ratio'] == Decimal('0.4')
    assert row['months_with_ai'] == Decimal('1.5') and row['subscription'] == Decimal(120), '40 € × 2 seats × 1.5 months'
    rows = {r['name']: r for r in delivery_calc.roadmaps(list(by_id.values()), by_id, [row])}
    assert rows['roadmap-manual']['effort_pd'] == 100 and rows['roadmap-ai']['effort_pd'] == 60
    assert rows['roadmap-manual']['labour_cost'] == 70000 and rows['roadmap-ai']['labour_cost'] == 42000 and rows['roadmap-manual']['subscription'] == 0
    assert rows['roadmap-ai']['critical_path'] == ['build', 'pilot'] and rows['roadmap-ai']['subscription'] > 0 and rows['roadmap-ai']['peak_team'] == 2
    assert rows['roadmap-ai']['months'] == rows['roadmap-manual']['months'], 'same end date; the AI roadmap frees the pilot earlier'


def test_estimates_and_roadmaps_are_checked(example):
    unit, plan, estimate, manual, agentic = delivery_plan(example)
    worse = json.loads(json.dumps(estimate));worse['body']['activities'][0]['ai_effort_pd'] = '90'
    missing = json.loads(json.dumps(estimate));del missing['body']['activities'][0]['ai_effort_pd']
    early = json.loads(json.dumps(agentic));early['body']['phases'][1]['start'] = '2027-02-01'
    blind = json.loads(json.dumps(agentic));del blind['body']['plan']
    codes = lambda o: {d['code'] for d in validate([o])['diagnostics']}
    assert 'AIR_ESTIMATE_AI' in codes(worse) and 'AIR_ESTIMATE_AI' in codes(missing)
    assert 'AIR_ROADMAP_DEPENDENCY' in codes(early) and 'AIR_ROADMAP_AI' in codes(blind)


def test_every_control_must_be_implemented_before_building(store, example, delivery):
    members, user, baseline, extra = delivery
    control = find(members, 'Control');provider = next(o for o in members if o['meta']['name'] == 'provider')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    compliance = next(c for c in gate['criteria'] if c['code'] == 'COMPLIANCE')
    assert compliance['status'] == 'NOT_MET' and [u['name'] for u in compliance['detail']['unmapped']] == ['control'] and 'COMPLIANCE' in gate['blocking']
    unjustified = obj(example, 'ComplianceMapping', 'mapping', {'subject': exact(control), 'status': 'NOT_APPLICABLE', 'mechanism': 'Out of scope'})
    assert 'AIR_COMPLIANCE_JUSTIFICATION' in {d['code'] for d in validate([unjustified])['diagnostics']}
    mapping = obj(example, 'ComplianceMapping', 'mapping', {'subject': exact(control), 'status': 'PLANNED', 'mechanism': 'Review step in the pipeline',
                                                            'implemented_by': [exact(provider)], 'verification': control['body']['verification']})
    store.put_bundle([mapping], 'fixture')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': frozen(store, example, members + [mapping], 'urn:delivery:mapped')})
    assert next(c for c in gate['criteria'] if c['code'] == 'COMPLIANCE')['status'] == 'MET'
    [row] = delivery_calc.compliance(members + [mapping], {o['meta']['id']: o for o in members})
    assert row['status'] == 'PLANNED' and row['implementers'] == [('ArchitectureBlock', 'provider')]


def test_requirements_received_from_a_kernel_are_mapped_like_owned_controls(example, delivery):
    members, user, baseline, extra = delivery
    quality = obj(example, 'QualityRequirement', 'nfr-latency', {'category': 'PERFORMANCE', 'statement': 'Claims are acknowledged within 2 s',
        'priority': 'MUST', 'verification_method': 'SIMULATION', 'target': {'operator': 'LTE', 'value': {'type': 'Integer', 'value': 2000}, 'unit': 'ms'}})
    quality['meta']['namespace'] = 'kernel'
    assert not validate([quality])['diagnostics']
    rows = delivery_calc.compliance(members, {o['meta']['id']: o for o in members}, inputs=[quality])
    assert {r['name']: r['status'] for r in rows} == {'control': 'UNMAPPED', 'nfr-latency': 'UNMAPPED'}


def test_the_presentation_is_bilingual_and_cites_its_sources(store, example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);design, submit, back = scenarios(example, members, added)
    store.put_bundle(added + [design, submit, back], 'fixture')
    pinned = frozen(store, example, members + added + [design, submit, back], 'urn:delivery:deck')
    request = {'title': 'Plateforme de remboursement', 'title_en': 'Claims platform', 'baselines': [pinned], 'content': 'HTML'}
    report = presentation.compile_presentation(store, user, POLICY, request)
    page = report['html']
    assert report['languages'] == ['fr', 'en'] and report['outline'][1]['section'] == 'Synthèse' and report['registry_written'] is False
    assert page.count('<main class="deck"') == 2 and 'Management summary' in page and 'Synthèse' in page
    assert 'Claims platform' in page and 'Plateforme de remboursement' in page
    assert page.count('<section class="slide') == 2 * report['slides']
    assert report == presentation.compile_presentation(store, user, POLICY, request), 'the deck is deterministic'
    outline = presentation.compile_presentation(store, user, POLICY, {**request, 'content': 'OUTLINE'})
    assert 'html' not in outline and outline['page_digest'] == report['page_digest']
    english = presentation.compile_presentation(store, user, POLICY, {**request, 'language': 'en', 'content': 'OUTLINE'})
    assert english['outline'][1]['section'] == 'Management summary' and english['page_digest'] != report['page_digest']


def test_numbers_follow_the_language():
    assert presentation.n(Decimal('1234567.5'), 1, 'fr') == '1 234 567,5' and presentation.n(Decimal('1234567.5'), 1, 'en') == '1,234,567.5'
    assert presentation.keur(Decimal('2500000'), 'en') == '2.50 M€' and presentation.keur(Decimal('45000'), 'fr') == '45 k€'


def test_audiences_keep_the_slides_they_decide_on(store, example, delivery):
    members, user, baseline, extra = delivery
    request = {'title': 'Plateforme', 'baselines': [baseline]}
    full = presentation.compile_presentation(store, user, POLICY, request)
    sponsor = presentation.compile_presentation(store, user, POLICY, {**request, 'audience': 'SPONSOR'})
    keys = [s['key'] for s in sponsor['outline']]
    assert keys[:2] == ['cover', 'summary'] and keys[-1] == 'decision' and sponsor['slides'] < full['slides'] and full['audience'] == 'CONTRACT'
    titles = ' '.join(s['title'] for s in full['outline'])
    assert 'fraude' not in titles and 'remboursement' not in titles, 'no title carries words that are not in the model'


def test_portable_skills_follow_the_open_standard_and_export_everywhere(tmp_path):
    import zipfile
    from air import skills
    shipped = {s['name']: s for s in skills.bundled()}
    assert set(shipped) == {'air-architecte', 'air-presentation', 'air-branding', 'architecture-story'}
    assert 'JourneyCatalog' in dict(shipped['air-architecte']['files'])['SKILL.md']
    assert all(len(s['description']) <= 1024 for s in shipped.values())
    plan = skills.export(tmp_path / 'repo', 'agents', apply=True)
    assert (tmp_path / 'repo/.agents/skills/air-presentation/references/storyline.md').is_file() and {p['action'] for p in plan['plan']} == {'CREATE'}
    assert {p['action'] for p in skills.export(tmp_path / 'repo', 'agents')['plan']} == {'UNCHANGED'}
    skills.export(tmp_path / 'zips', 'chatgpt', apply=True)
    first = (tmp_path / 'zips/air-presentation.zip').read_bytes()
    assert zipfile.ZipFile(tmp_path / 'zips/air-presentation.zip').namelist()[-1] == 'air-presentation/SKILL.md' or \
        'air-presentation/SKILL.md' in zipfile.ZipFile(tmp_path / 'zips/air-presentation.zip').namelist()
    assert skills.archive(shipped['air-presentation']) == first, 'the archive is reproducible'
    try:
        skills.check('Bad_Name', '---\nname: Bad_Name\ndescription: x\n---\n')
    except ValueError as exc:
        assert 'lowercase' in str(exc)
    else:
        raise AssertionError('an invalid skill name is refused')


def test_roadmaps_are_compared_per_project_against_their_reference(example):
    unit, plan, estimate, manual, agentic = delivery_plan(example)
    other = json.loads(json.dumps(agentic));other['meta']['namespace'] = 'other';other['meta']['id'] = 'urn:delivery:other-roadmap'
    by_id = {o['meta']['id']: o for o in [unit, plan, estimate, manual, agentic, other]}
    rows = delivery_calc.roadmaps(list(by_id.values()), by_id, delivery_calc.estimates(list(by_id.values()), by_id))
    mine = {r['name']: r for r in rows if r['namespace'] == example['meta']['namespace']}
    assert mine['roadmap-ai']['reference'] == 'roadmap-manual' and mine['roadmap-ai']['delta_cost'] < 0 and mine['roadmap-manual']['delta_months'] is None
    foreign = next(r for r in rows if r['namespace'] == 'other')
    assert foreign['reference'] is None, 'a project is never compared with another project reference'
    chosen = delivery_calc.chosen_by_project(rows)
    assert set(chosen) == {example['meta']['namespace'], 'other'} and all(r['status'] == 'RECOMMENDED' for r in chosen.values())
