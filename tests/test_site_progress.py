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
    assert 'completion-ribbon' in home
    assert home.index('completion-ribbon') < home.index('Les réponses dont vous avez besoin')
    assert len(progress['parts']) == 8
    ids = [q['id'] for p in progress['parts'] for q in p['questions']]
    assert sorted(ids) == sorted(q['id'] for q in reading['questions'])


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


def test_documentary_percentage_does_not_hide_unmet_controls_or_invent_work():
    reading = {'baseline': {'id':'urn:baseline:test','revision':1,'digest':'sha256:'+'a'*64},
        'gate': {'code':'NOT_READY','label':'Ouvert'},
        'questions':[{'id':'28','question':'Préparation','state':'CALCULATED','sources':[],
            'topic':'28-preparation-construction.html','missing_dimensions':[]}],
        'calculated_criteria':[{'code':'VERIFICATION','label':'Vérification','status':'NOT_MET','next_action':'Qualifier la preuve'}]}
    progress = site_progress.project(reading)
    block = next(b for b in progress['parts'] if b['id'] == 'verification')
    assert block['percent'] == 100 and block['remaining_controls']
    assert block['in_progress'] == 0 and progress['gate']['code'] == 'NOT_READY'
    assert next(b for b in progress['parts'] if b['id'] == 'data')['percent'] is None
    html = site_progress.ribbon(progress)
    assert '100 %' in html and 'Qualifier la preuve' in html and 'Non évalué' in html
    assert 'ne valent pas validation' in html


def test_work_is_linked_only_to_exact_deliverables_and_percent_is_not_effort():
    ref = {'id':'urn:requirement:test','revision':2,'digest':'sha256:'+'b'*64}
    q = {'id':'13','question':'Construction','state':'PARTIAL','sources':[{'reference':ref}],
        'topic':'13-construction.html','missing_dimensions':['Contrat']}
    task = {'reference':{'id':'urn:task:test','revision':1,'digest':'sha256:'+'c'*64},
        'name':'<script>Travail</script>','status':'IN_PROGRESS','owner':'Architecte',
        'purpose':'Compléter','deliverables':[{'id':ref['id'],'revision':2}]}
    stale = deepcopy(task);stale['reference']['id']='urn:task:stale';stale['deliverables'][0]['revision']=1
    reading = {'baseline':{'id':'urn:baseline:test','revision':1,'digest':'sha256:'+'a'*64},
        'gate':{'code':'NOT_READY','label':'Ouvert'},'questions':[q],'calculated_criteria':[],
        'design_tasks':[task,stale]}
    progress = site_progress.project(reading)
    block = next(b for b in progress['parts'] if b['id'] == 'verification')
    assert block['percent'] == 0 and block['in_progress'] == 1
    assert progress['unlinked_design_tasks'] == [stale]
    html = site_progress.ribbon(progress)
    assert '<script>Travail' not in html and '&lt;script&gt;Travail' in html
    assert 'En cours' in html and 'Contrat' in html
