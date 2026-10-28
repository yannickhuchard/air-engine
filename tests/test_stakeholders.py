from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from test_build_design import design, model, POLICY
from air import stakeholders, deliverables
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.core import BUILD_PROFILE, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.storage import Conflict

spec = importlib.util.spec_from_file_location('stakeholders_fixture', Path(__file__).resolve().parents[1] / 'fixtures/stakeholders/model.py')
recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)


@pytest.fixture
def participation(design, store):
    objects, user, token, settings, request = design
    added = recipe.additions(); combined = objects + added
    checked = validate_graph(combined, BUILD_PROFILE); assert checked['valid'], checked
    store.put_bundle(added, user['subject'])
    result = store.create_baseline({'meta': model.obj('Baseline', 'stakeholders', {})['meta'], 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in combined], 'parent_baselines': []}, user['subject'])
    p = {**exact(result['baseline']), 'digest': result['digest']}
    return combined, user, token, settings, p


def test_declared_participation_vacancy_and_unassessed_role(participation, store):
    _, user, _, _, p = participation
    before = store.counts(); r = stakeholders.query(store, user, POLICY, {'baseline': p})
    assert r['counts'] == {'INVOLVED': 1, 'TO_INVOLVE': 1, 'MISSING': 1, 'UNASSESSED': 1}
    vacant = next(e for e in r['entries'] if e['state'] == 'MISSING')
    assert not vacant['holders'] and vacant['staffing_action'] == 'RECRUIT' and vacant['reason'] and vacant['architecture_links']
    unresolved = next(e for e in r['entries'] if e['state'] == 'UNASSESSED')
    assert unresolved['staffing_action'] == 'ASSESS' and 'ASSIGNMENT_NOT_DOCUMENTED' in unresolved['gaps']
    architect = next(e for e in r['entries'] if e['state'] == 'INVOLVED')
    assert architect['raci'][0]['responsibility'] == 'A' and architect['responsibilities']
    assert not r['authorization_granted'] and not r['hiring_executed'] and store.counts() == before


@pytest.mark.parametrize('change', ['missing_holder', 'invented_holder', 'no_staffing', 'bad_date', 'self_link'])
def test_contradictory_participation_is_rejected(participation, change):
    objects, *_ = participation
    revised = deepcopy(objects)
    selected = next(o for o in revised if o['meta']['type'] == 'air.StakeholderParticipation' and o['body']['state'] == ('INVOLVED' if change == 'missing_holder' else 'MISSING'))
    b = selected['body']
    if change == 'missing_holder': b.pop('stakeholder')
    if change == 'invented_holder': b['stakeholder'] = model.ref('camille')
    if change == 'no_staffing': b['staffing_action'] = 'NONE'
    if change == 'bad_date': b['needed_by'] = '2026-02-31'
    if change == 'self_link': b['architecture_links'] = [exact(selected)]
    assert not validate_graph(revised, BUILD_PROFILE)['valid']


def test_software_actors_are_not_automatically_human_stakeholders(design, store):
    _, user, _, _, request = design
    r = stakeholders.query(store, user, POLICY, {'baseline': request['baseline']})
    assert not r['entries']  # Fixture has only a SOFTWARE actor.


def test_access_pins_api_mcp_and_safe_html(participation, store):
    _, user, token, settings, p = participation
    denied = AccessPolicy({'version': 'deny', 'subjects': {user['subject']: {'read': ['other.namespace']}}})
    with pytest.raises(Forbidden): stakeholders.query(store, user, denied, {'baseline': p})
    with pytest.raises(Conflict): stakeholders.query(store, user, POLICY, {'baseline': {**p, 'digest': 'sha256:' + '0' * 64}})
    from air.mcp_http import invoke
    user['policy'] = POLICY
    report = invoke(store, user, 'air_stakeholders_map', {'baseline': p}, settings)
    assert report == stakeholders.query(store, user, POLICY, {'baseline': p})
    with TestClient(create_app(settings)) as client:
        result = client.post('/v1/stakeholders/map', json={'baseline': p}, headers={'Authorization': 'Bearer ' + token['access_token']})
        assert result.status_code == 200 and result.json() == report
    altered = deepcopy(report); altered['entries'][0]['reason'] = '<script>alert(1)</script>'
    html = stakeholders.render(altered)
    assert '<script>' not in html and '&lt;script&gt;' in html and 'href="#stakeholder-' in html


def test_standard_deliverable_site_checklist_and_exact_sources(participation, store):
    _, user, _, _, p = participation
    pack = deliverables.compile_deliverables(store, user, POLICY, {'title': 'Parties prenantes fictives', 'baselines': [p]})
    files = {f['path']: f['content'] for f in pack['files']}
    d = pack['website']['dossiers'][0]; assert d['topics'] == 38
    assert 'livrables/38-stakeholders-map.md' in files
    page = files['livrables/site/' + d['stakeholders_map']]
    assert 'data-stakeholders-map' in page and 'stakeholder-map.js' in page and '<svg' in page
    assert '38-stakeholders-map.html' in files['livrables/site/' + d['path']]
    import csv, io
    rows = list(csv.reader(io.StringIO(files['livrables/site/' + d['path'].rsplit('/', 1)[0] + '/checklist.csv'].lstrip('\ufeff'))))
    staffing = [r for r in rows if r[0] == 'air.StakeholderParticipation']
    assert len(staffing) == 3 and any(r[4] == 'MISSING' and 'RECRUIT' in r[5] for r in staffing)
    assert any('diagram-38-stakeholders-map-' in name for name in files)
    prefix = 'livrables/site/' + d['path'].rsplit('/', 1)[0] + '/'
    progress = json.loads(files[prefix + 'questions.json'])
    q = next(q for q in progress['questions'] if q['id'] == '38')
    assert q['state'] == 'SOURCES_PRESENT' and not q['complete_or_approved']
    graph = json.loads(files[prefix + 'graph.json'])
    assert 'StakeholderParticipation' in json.dumps(graph)


def test_map_preserves_long_names_and_escapes_search_attributes(participation, store):
    _, user, _, _, p = participation
    report = stakeholders.query(store, user, POLICY, {'baseline': p})
    altered = deepcopy(report)
    title = 'Responsable des opérations et de la continuité des activités multi-sites avec les partenaires'
    altered['entries'][0]['role']['name'] = title
    altered['entries'][0]['reason'] = '\"><img src=x onerror=alert(1)>'
    html = stakeholders.render(altered)
    assert title in html and '<img' not in html and '&lt;img' in html
    assert 'data-stakeholder-search' in html and 'data-stakeholder-empty hidden' in html
    assert 'min-width:900px' not in html
