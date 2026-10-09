from copy import deepcopy
import json
from pathlib import PurePosixPath
from air import deliverables, site_questions
from air.core import digest
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_six_role_routes_preserve_pins_sources_and_all_topics(compiled):
    report, request, _ = compiled
    files = {f['path']: f['content'] for f in report['files']}
    dossier = report['website']['dossiers'][0]
    root = 'livrables/site/' + str(PurePosixPath(dossier['path']).parent) + '/'
    reading = json.loads(files[root + 'questions.json'])
    assert reading['baseline'] == request['baselines'][0]
    assert len(reading['questions']) == len(deliverables.CATALOGUE) == 37
    assert len(reading['roles']) == 6
    assert not reading['audience_is_access_control']
    objects = json.loads(files['livrables/architecture-model.json'])['snapshots'][0]['objects']
    exact = {(o['meta']['id'], o['meta']['revision']): o for o in objects}
    for q in reading['questions']:
        assert root + q['topic'] in files
        assert not q['complete_or_approved']
        for source in q['sources']:
            pin = source['reference']
            assert digest(exact[(pin['id'], pin['revision'])]) == pin['digest']
            for statement in source['statements']:
                assert statement['text'] == exact[(pin['id'], pin['revision'])]['body'][statement['field']]
    assert set().union(*(set(r['questions']) for r in reading['roles'])) == {q['id'] for q in reading['questions']}
    for role in reading['roles']:
        text = files[root + 'role-' + role['id'] + '.html']
        assert 'id="question-search"' in text and 'ne filtrent pas les données' in text
        assert request['baselines'][0]['id'] in text
        assert 'aria-current="page" href="role-' + role['id'] + '.html"' in text


def test_no_budget_is_not_zero_and_gate_without_runs_is_still_calculated(store, compiled):
    report, request, user = compiled
    from air.readiness import assess_readiness
    full_gate = assess_readiness(store, user, POLICY, {'baseline': request['baselines'][0]})
    exported = store.export_baseline(request['baselines'][0])
    exported = deepcopy(exported)
    exported['objects'] = [o for o in exported['objects'] if o['meta']['type'] not in ('air.CostItem', 'air.VerificationRun', 'air.RaciAssignment')]
    g = deliverables.Graph([exported])
    gate = {'result': 'NOT_READY', 'criteria': []}
    before = deepcopy(exported)
    reading = site_questions.project(exported, gate, deliverables.build_topics(g, [full_gate], request),
                                     __import__('air.architecture_site', fromlist=['QUESTIONS']).QUESTIONS)
    assert exported == before
    questions = {q['id']: q for q in reading['questions']}
    assert questions['17']['state'] == 'NOT_DOCUMENTED'
    assert questions['17']['missing_dimensions'] == ['Postes de coûts CAPEX et OPEX', 'Enveloppe, horizon et statut de financement']
    assert questions['28']['state'] == 'CALCULATED'
    assert not questions['28']['sources']
    assert 'Responsabilités RACI de réalisation' in questions['06']['missing_dimensions']


def test_gate_reason_keeps_its_actual_meaning_and_unknown_reasons():
    assert site_questions.GATE_LABELS['READY_TO_BUILD'] == 'Critères de préparation satisfaits dans leur portée'
    assert 'qualité' in deliverables._detail({'detail': {'reason': 'No control or quality requirement applies to this project'}})
    assert 'rien à construire' not in deliverables._detail({'detail': {'reason': 'No control or quality requirement applies to this project'}})
    assert deliverables._detail({'detail': {'reason': 'Future explicit reason'}}) == 'Future explicit reason'
    assert deliverables.table(['Empty'], []) == ['Aucun élément déclaré.']
