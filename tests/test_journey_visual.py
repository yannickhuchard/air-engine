from copy import deepcopy
from xml.etree import ElementTree as ET
from air import journey_catalog, journey_visual
from air.deliverables import Graph
from test_journey_catalog import sample
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def projected(): return journey_catalog.project(Graph([{'objects':sample()}]))['journeys'][0]


def test_svg_remains_exact_safe_complete_and_never_fabricates_unknown_mood():
    j=projected(); before=deepcopy(j)
    j['steps'][0]['name']='<script>alert("x")</script> client'
    source=deepcopy(j);svg=journey_visual.svg(j)
    tree=ET.fromstring(svg);ns={'s':'http://www.w3.org/2000/svg'}
    assert len(tree.findall('s:a',ns))==len(j['steps'])
    assert all(a.find('s:rect',ns).get('pointer-events')=='all' for a in tree.findall('s:a',ns))
    assert 'Émotion non renseignée' in svg and 'Score non attribué' in svg
    assert 'class="jv-face"' not in svg and 'class="jv-mood-line ' not in svg
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    assert j==source and source!=before
    html=journey_visual.figure(j)
    assert 'data-jv-toolbar hidden' in html and 'data-jv-action="tour"' in html
    assert 'Exporter le diagramme SVG' in html and source['steps'][0]['selector'] in html
    assert 'jv-step-detail' in html and 'Pensées et attentes' in html and 'Émotions et mood' in html
    assert html==journey_visual.figure(j)


def test_mood_segments_do_not_bridge_unknowns_or_different_evidence_statuses():
    j=projected();template=deepcopy(j['steps'][0])
    moods=[{'status':'HYPOTHESIS','score':2,'label':'Question','rationale':'To discuss'},
      {'status':'HYPOTHESIS','score':4,'label':'Confidence','rationale':'To discuss'},
      {'status':'UNKNOWN'}, {'status':'OBSERVED','score':5,'label':'Relief','rationale':'Evidence','evidence':[]},
      {'status':'HYPOTHESIS','score':3,'label':'Wait','rationale':'To discuss'}]
    j['steps']=[{**deepcopy(template),'id':str(i),'name':'Étape '+str(i),'emotion':m} for i,m in enumerate(moods)]
    svg=journey_visual.svg(j)
    assert svg.count('class="jv-mood-line jv-mood-part')==1
    assert svg.count('class="jv-face"')==4 and 'Observation déclarée' in svg
    profile={'colors':{'header':'#123456','link':'#345678'},'fonts':{'body':'Arial'}}
    themed=journey_visual.svg(j,profile,'journey-map-test.html')
    assert '--header:#123456' in themed and '--blue:#345678' in themed
    assert 'font-family:&quot;Arial&quot;' in themed and 'href="journey-map-test.html#jv-' in themed
    ET.fromstring(themed)


def test_pack_has_dedicated_interactive_page_portable_svg_and_exact_json(compiled):
    report,_,_=compiled;files={f['path']:f['content'] for f in report['files']}
    root='livrables/site/'+report['website']['dossiers'][0]['path'].rsplit('/',1)[0]+'/'
    pages=[p for p in files if p.startswith(root+'journey-map-') and p.endswith('.html')]
    assert pages
    catalog=__import__('json').loads(files[root+'journeys.json'])
    for j in catalog['journeys']:
        name=root+'journey-map-'+journey_visual.anchor(j)
        data=__import__('json').loads(files[name+'.json'])
        assert data['journey']==j and data['baseline']==catalog['baseline']
        assert not data['research_validated'] and not data['business_execution_performed']
        ET.fromstring(files[name+'.svg'])
        assert 'assets/journey.js' in files[name+'.html'] and 'assets/journey.css' in files[name+'.html']
        assert 'data-journey-visual' in files[root+'journey-'+journey_visual.anchor(j)+'.html']
    assert files['livrables/site/assets/journey.js'] and files['livrables/site/assets/journey.css']
