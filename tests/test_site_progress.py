from copy import deepcopy
import json
from air import site_progress
from air.expr import artifact_digest
from test_architecture_site import contents
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_site_progress_tracks_pinned_sources_and_calculated_gates(compiled):
    report, _, _ = compiled
    files = contents(report)
    dossier = report['website']['dossiers'][0]
    progress = json.loads(files['livrables/site/' + dossier['progress']])
    reading = json.loads(files['livrables/site/' + dossier['questions_data']])
    assert progress['baseline'] == dossier['baseline']
    assert progress == site_progress.project(reading, json.loads(files['livrables/site/' + dossier['journeys_data']]))
    assert not progress['semantic_completeness_certified']
    assert not progress['business_execution_performed']
    assert progress['met_criteria'] == sum(c['status'] == 'MET' for c in reading['calculated_criteria'])
    assert all(not t['approved'] for t in progress['tasks'])
    assert progress['projection_digest'] == artifact_digest({k:v for k,v in progress.items() if k != 'projection_digest'})
    root = files['livrables/site/index.html']
    home = files['livrables/site/' + dossier['path']]
    assert 'Kanban du dossier' in root and 'Kanban du dossier' in home
    assert dossier['progress'] in root and 'progress.json' in home


def test_missing_partial_and_unmet_are_never_done_and_html_is_escaped():
    reading = {'baseline': {'id':'urn:baseline:test','revision':1,'digest':'sha256:'+'a'*64},
               'gate': {'code':'NOT_READY','label':'Revue ouverte'},
               'questions': [{'id':'01','question':'<script>danger</script>','state':'NOT_DOCUMENTED','sources':[], 'topic':'topic.html','missing_dimensions':[]},
                             {'id':'06','question':'Équipe','state':'PARTIAL','sources':[{'reference':{'id':'urn:source:test','revision':1,'digest':'sha256:'+'b'*64}}],'topic':'team.html','missing_dimensions':['RACI']}],
               'calculated_criteria':[{'code':'REVIEW','label':'Revue','status':'NOT_MET','next_action':'<img onerror=x>'}]}
    before = site_progress.project(reading)
    assert [t['column'] for t in before['tasks']] == ['TODO','PARTIAL','VALIDATE']
    html = site_progress.section(before)
    assert '<script>danger' not in html and '&lt;script&gt;' in html
    assert '<img onerror' not in html
    after = deepcopy(reading);after['baseline']['revision'] = 2
    after['questions'][0]['state'] = 'SOURCES_PRESENT'
    after['questions'][0]['sources'] = after['questions'][1]['sources']
    current = site_progress.project(after)
    assert current['tasks'][0]['column'] == 'DOCUMENTED'
    assert current['projection_digest'] != before['projection_digest']
    assert current['tasks'][-1]['column'] == 'VALIDATE'


def test_open_questions_are_deduplicated_and_resolved_questions_leave_backlog():
    source = {'reference':{'id':'urn:question:test','revision':1,'digest':'sha256:'+'b'*64},'type':'air.Unknown',
              'name':'Choisir une commune','declared_state':'OPEN','resolution_owner':'urn:role:legal',
              'statements':[{'text':'Quelle permission de circulation ?'}]}
    q = {'id':'12','question':'Hypothèses','state':'SOURCES_PRESENT','sources':[source],'topic':'topic.html','missing_dimensions':[]}
    reading = {'baseline':{'id':'urn:baseline:test','revision':1,'digest':'sha256:'+'a'*64},'gate':{'code':'NOT_READY','label':'Ouvert'},
               'questions':[q,deepcopy(q)],'calculated_criteria':[]}
    progress = site_progress.project(reading)
    pending = [t for t in progress['tasks'] if t['kind']=='DECLARED_OPEN_QUESTION']
    assert len(pending)==1 and pending[0]['sources']==[source['reference']]
    assert 'objects.html#' in pending[0]['href']
    for entry in reading['questions']: entry['sources'][0]['declared_state']='RESOLVED'
    assert not any(t['kind']=='DECLARED_OPEN_QUESTION' for t in site_progress.project(reading)['tasks'])
