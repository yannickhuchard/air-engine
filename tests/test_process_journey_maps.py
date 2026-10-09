from copy import deepcopy
import json
from xml.etree import ElementTree as ET
import pytest
from air import process_diagrams, journey_catalog, journey_map, delivery_schema
from air.core import digest, reference_slots, validate
from air.deliverables import Graph
from air.foundation import exact
from test_journey_catalog import sample, o


def test_bundled_bpmn_files_retain_their_declared_upstream_bytes():
    import hashlib
    from importlib import resources
    assets = resources.files('air').joinpath('assets')
    provenance = json.loads(assets.joinpath('bpmn-provenance.json').read_text(encoding='utf-8'))
    for name, expected in provenance['files'].items():
        assert hashlib.sha256(assets.joinpath(name).read_bytes()).hexdigest() == expected, name
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def workflow():
    members = sample(); actor = members[1]; fn = members[2]
    w = o('Workflow', 'branch-loop', {'steps': [{'id': s, 'name': s, 'binding': 'air.workflow-step/0.35',
        'function': exact(fn), 'participants': [exact(actor)], 'join': 'ALL' if s == 'finish' else 'ANY'} for s in ('enter','check','repair','finish')],
        'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'f'+str(i), 'source': a, 'target': b, 'condition': c}
            for i,(a,b,c) in enumerate([('enter','check','submitted'),('check','repair','bad'),('repair','check','retry'),('check','finish','good'),('enter','finish','cancel')])],
        'start_steps': ['enter'], 'termination_policy': 'Documented design only', 'compensations': [exact(fn)]})
    return members + [w], w


def test_bpmn_keeps_cycles_branches_and_exact_witness_without_executable_claim():
    members, w = workflow(); before = deepcopy(members); p = process_diagrams.project(Graph([{'objects':members}]),w)
    assert p == process_diagrams.project(Graph([{'objects':list(reversed(members))}]),w)
    assert members == before and p['cycles'] == [['check','repair']]
    assert not p['executable'] and p['reference']['digest'] == digest(w)
    assert 'enter vers check : <strong>submitted' in process_diagrams.focus(p)
    assert 'check vers repair : <strong>bad' in process_diagrams.focus(p)
    xml = ET.fromstring(process_diagrams.bpmn(p)); ns = process_diagrams.NS
    assert xml.find('bpmn:process', ns).get('isExecutable') == 'false'
    assert len(xml.findall('.//bpmn:task',ns)) == 4
    assert xml.findall('.//bpmn:inclusiveGateway',ns) and xml.findall('.//bpmn:parallelGateway',ns)
    original = [e for e in p['edges'] if e['selector']]
    assert len(original) == len(w['body']['flows'])
    for e in original:
        index = int(e['selector'].rsplit('/',1)[-1]); assert e['name'] == w['body']['flows'][index]['condition']
        assert e['witness'] == p['reference']
    ids = [el.get('id') for el in xml.iter() if el.get('id')]
    assert len(ids)==len(set(ids))
    for n in p['nodes']:
        assert 0 <= n['x'] < n['x']+n['width'] <= p['width']
        assert 0 <= n['y'] < n['y']+n['height'] <= p['height']
    for a in p['nodes']:
        for b in p['nodes']:
            if a['id'] >= b['id']: continue
            assert a['x']+a['width'] <= b['x'] or b['x']+b['width'] <= a['x'] or a['y']+a['height'] <= b['y'] or b['y']+b['height'] <= a['y']


def test_map_emotions_missing_score_and_mixed_provenance_are_not_interpolated():
    members = sample(); j = members[-2]
    j['body']['steps'] *= 1
    base = j['body']['steps'][0]
    j['body']['steps'] = [{**deepcopy(base),'id':str(i),'name':'step '+str(i), **({'emotion': value} if value else {})}
        for i,value in enumerate([{'status':'HYPOTHESIS','label':'Worry','score':2,'rationale':'Design assumption'},None,
            {'status':'OBSERVED','label':'Relief','score':4,'rationale':'Source statement','evidence':[exact(members[2])]},
            {'status':'HYPOTHESIS','label':'Confidence','score':5,'rationale':'To discuss'}])]
    # Projection does not pretend these deliberately unvalidated fixture sources are certified.
    row = journey_catalog.project(Graph([{'objects':members}]))['journeys'][0]
    html = journey_map.render(row,True); curve = journey_map.curve(row)
    assert 'Émotion inconnue' in html and 'Aucun score attribué' in html
    assert 'Hypothèse à discuter' in html and 'Observation déclarée' in html
    assert '<path d="M 120' not in curve  # no interpolation over missing or mixed provenance
    assert 'Systèmes et blocs reliés' in html and 'Service visible' in html and 'Actions internes' in html
    assert '<script>receive</script>' not in html
    assert 'scope="row"' in html and 'scope="col"' in html and 'journey-mobile' in html


def test_observed_emotion_requires_evidence_and_unknown_cannot_have_neutral_score(example):
    base = sample()[-2]; j = obj(example,'CustomerJourney','rich-journey',deepcopy(base['body']))
    s=j['body']['steps'][0];s['phase']='Prepare';s['action']='Collect parcel';s['thoughts']=['Will I find it?']
    s['emotion']={'status':'UNKNOWN','score':3}
    assert 'AIR_JOURNEY_EMOTION_UNKNOWN' in {code for code,_ in delivery_schema.local_issues(j)}
    s['emotion']={'status':'OBSERVED','label':'Concern','rationale':'Interview'}
    assert 'AIR_JOURNEY_EMOTION_EVIDENCE' in {code for code,_ in delivery_schema.local_issues(j)}
    s['emotion']['evidence']=[{'id':'urn:research:interview','revision':1}]
    assert validate(j)['valid'], validate(j)
    slots=list(reference_slots(j));assert any('/emotion/evidence' in field and targets==['air.Source','air.Assertion'] for field,_,targets in slots)


def test_compiled_site_has_complete_bpmn_layout_map_and_offline_notices(compiled):
    report,_,_=compiled; files={f['path']:f['content'] for f in report['files']};d=report['website']['dossiers'][0]
    root='livrables/site/'+d['path'].rsplit('/',1)[0]+'/'
    assert root+'processes.html' in files
    xmls=[p for p in files if p.startswith(root) and p.endswith('.bpmn')]
    assert len(xmls)==d['process_count'] and xmls
    for filename in xmls:
        assert ET.fromstring(files[filename]).find('bpmn:process',process_diagrams.NS).get('isExecutable')=='false'
        page=files[filename[:-5]+'.html']; assert 'process-fallback' in page and 'bpmn-data' in page
    assert 'bpmn-js-18.16.0.js' in files['livrables/site/assets/process.js'] or 'BpmnJS' in files['livrables/site/assets/process.js']
    assert 'watermark' in files['livrables/site/assets/bpmn-LICENSE.txt']
    assert 'Customer Journey Map' in files[root+'03-parcours-clients.html']
    assert 'process-diagram' in files[root+'04-processus-metier.html']
    assert '<pre class="mermaid">' not in files[root+'04-processus-metier.html']
