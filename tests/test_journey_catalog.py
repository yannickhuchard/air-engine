from copy import deepcopy
import json
from air import journey_catalog, site_journeys, delivery_schema, business_paths, graph_explorer, site_progress
from air.core import reference_slots, digest
from air.deliverables import Graph
from air.foundation import exact
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def o(kind, name, body):
    return {'meta': {'id': 'urn:journey:' + name, 'revision': 1, 'type': 'air.' + kind,
                     'name': name, 'description': name, 'namespace': 'test.journey', 'lifecycle': 'DRAFT', 'validity': {}, 'provenance': {'source_refs': []}, 'context_refs': []}, 'body': body}


def sample():
    scope = o('Scope', 'scope', {'includes': [], 'excludes': []})
    actor = o('Actor', 'customer', {'kind': 'HUMAN', 'boundary': exact(scope), 'roles': []})
    fn = o('Function', 'receive', {'exceptions': [], 'satisfies': []})
    points = [o('UsagePoint', k.lower(), {'kind': k, 'purpose': 'Declared ' + k, 'status': 'PROPOSED',
                                         **({'location_description': 'City not selected'} if k == 'GEOGRAPHIC' else {})}) for k in journey_catalog.CONTEXTS]
    tp = o('Touchpoint', 'locker', {'purpose': 'Receive a parcel', 'usage_points': [exact(p) for p in points],
                                  'participants': [exact(actor)], 'architecture_links': [exact(fn)]})
    j = o('CustomerJourney', 'delivery', {'persona': exact(actor), 'goal': 'Receive parcel', 'steps': [
        {'id': 'receive', 'name': '<script>receive</script>', 'channel': 'IN_PERSON', 'touchpoint': 'Robot', 'touchpoint_ref': exact(tp)}]})
    cat = o('JourneyCatalog', 'catalog', {'scope': exact(scope), 'purpose': 'Pilot only', 'journeys': [exact(j)],
        'personas': [{'persona': exact(actor), 'coverage': 'REQUIRED', 'rationale': 'Recipient', 'required_contexts': list(journey_catalog.CONTEXTS)}]})
    return [scope, actor, fn, *points, tp, j, cat]


def test_exact_inventory_links_and_documentary_checks_do_not_approve():
    members = sample(); before = deepcopy(members); view = journey_catalog.project(Graph([{'objects': members}]))
    assert view['gaps'] == [] and all(c['status'] == 'MET' for c in view['checks'])
    assert members == before and not view['semantic_completeness_certified'] and not view['research_validated']
    assert view['personas'][0]['declared_contexts'] == sorted(journey_catalog.CONTEXTS)
    index = {(a['meta']['id'], a['meta']['revision']): a for a in members}
    for pin in view['sources']: assert digest(index[(pin['id'], pin['revision'])]) == pin['digest']
    st = view['journeys'][0]['steps'][0]; a = st['architecture_links'][0]
    source = index[(a['witness']['id'], a['witness']['revision'])]
    assert source['body']['architecture_links'][0] == {k:a['reference'][k] for k in ('id','revision')}
    html = site_journeys.focus(view['journeys'][0])
    assert '<script>receive</script>' not in html and '&lt;script&gt;receive' in html
    assert '/body/architecture_links/0' in html and 'Numérique' in html and 'Géographique' in html


def test_missing_persona_legacy_touchpoint_contexts_and_links_are_reported():
    members = sample(); members[-2]['body']['steps'][0].pop('touchpoint_ref')
    members.append(o('Actor', 'operator', {'kind':'HUMAN','boundary':exact(members[0]),'roles':[]}))
    view = journey_catalog.project(Graph([{'objects':members}]))
    assert {'TOUCHPOINT_UNTYPED','PERSONA_CONTEXT_MISSING','STEP_ARCHITECTURE_UNLINKED','PERSONA_NOT_CATALOGUED'} <= {g['code'] for g in view['gaps']}
    assert sum(c['status']=='MISSING' for c in view['checks']) == 4
    members[-2]['body']['personas'].append({'persona':exact(members[-1]),'coverage':'EXCLUDED','rationale':'Separate project','required_contexts':[]})
    assert 'PERSONA_NOT_CATALOGUED' not in {g['code'] for g in journey_catalog.project(Graph([{'objects':members}]))['gaps']}


def test_parent_cycles_and_unresolved_exact_revision_are_visible():
    members=sample();members[3]['body']['parent']=exact(members[4]);members[4]['body']['parent']=exact(members[3])
    view=journey_catalog.project(Graph([{'objects':members}]))
    assert any(g['code']=='USAGE_POINT_CYCLE' for g in view['gaps'])
    members[-2]['body']['steps'][0]['touchpoint_ref']['revision']=2
    view=journey_catalog.project(Graph([{'objects':members}]))
    assert any(g['code']=='UNRESOLVED_REFERENCE' for g in view['gaps'])


def test_reference_slots_feed_architecture_graph_and_business_path():
    members=sample();exported={'objects':members}; j=members[-2]
    slots=list(reference_slots(j))
    assert any(ref==exact(members[-3]) and 'touchpoint_ref' in field for field,ref,targets in slots)
    path=business_paths.project_path(exported,exact(j))
    assert {'air.Touchpoint','air.UsagePoint'} <= {n['type'] for n in path['context_graph']['nodes']}
    assert not path['business_execution_performed']
    assert graph_explorer.family('air.Touchpoint')=='business'
    duplicate=deepcopy(members[-1]);duplicate['body']['personas']*=2
    assert 'AIR_JOURNEY_PERSONA_DUPLICATE' in {code for code,_ in delivery_schema.local_issues(duplicate)}


def test_every_compiled_dossier_has_catalog_focus_and_separate_checklist(compiled):
    report,_,_=compiled; files={f['path']:f['content'] for f in report['files']}; d=report['website']['dossiers'][0]
    view=json.loads(files['livrables/site/'+d['journeys_data']])
    assert any(g['code']=='CATALOG_MISSING' for g in view['gaps'])
    assert 'Parcours clients et intervenants' in files['livrables/site/'+d['journeys']]
    progress=json.loads(files['livrables/site/'+d['progress']])
    assert len([t for t in progress['tasks'] if t['kind']=='JOURNEY_DOCUMENTARY_COVERAGE'])==5
    assert progress['total_criteria']==12
    assert not any(t['approved'] for t in progress['tasks'])
    for j in view['journeys']:
        focus='livrables/site/'+d['journeys'].rsplit('/',1)[0]+'/journey-'+site_journeys.anchor(j['reference'])+'.html'
        assert focus in files


def test_new_types_validate_with_real_metadata_and_reject_bad_coverage(example):
    from air.core import validate
    from air.foundation import validate_graph
    members=sample()
    typed=[obj(example, x['meta']['type'].removeprefix('air.'), x['meta']['id'].rsplit(':',1)[-1], x['body']) for x in members if x['meta']['type'] in ('air.JourneyCatalog','air.Touchpoint','air.UsagePoint')]
    for x in typed: assert validate(x)['valid'], validate(x)
    broken=deepcopy(typed[-1]);broken['body']['personas'][0]['coverage']='APPROVED'
    assert not validate(broken)['valid']


def test_external_participants_and_duplicate_rosters_cannot_silently_pass():
    members=sample();external=o('Actor','external',{'kind':'HUMAN','boundary':{'id':'urn:other:scope','revision':1},'roles':[]})
    members.append(external);members[-4]['body']['participants'].append(exact(external))
    view=journey_catalog.project(Graph([{'objects':members}]))
    assert any(g['code']=='PARTICIPANT_NOT_CATALOGUED' for g in view['gaps'])
    duplicate=deepcopy(members[-2]);duplicate['meta']['id']='urn:journey:second-catalog';members.append(duplicate)
    view=journey_catalog.project(Graph([{'objects':members}]))
    assert any(g['code']=='PERSONA_MULTIPLE_CATALOGS' for g in view['gaps'])
    assert next(c for c in view['checks'] if c['code']=='CATALOG')['status']=='MISSING'


def test_historical_simulation_inputs_allow_only_separate_journey_document_changes():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path('scripts').resolve()))
    import pytest
    retained_inputs = pytest.importorskip(
        'prepare_robot_delivery_acceptance',
        reason='Private ProxiBot acceptance helper is outside the public engine snapshot',
    ).retained_inputs
    before=sample();after=deepcopy(before);after[-2]['body']['goal']='New narrative'
    valid, changes=retained_inputs(before,after)
    assert valid and len(changes)==1 and changes[0]['scope']=='NON_SIMULATION_JOURNEY_DOCUMENT'
    after[2]['body']['exceptions']=[{'id':'urn:failure:changed','revision':1}]
    assert not retained_inputs(before,after)[0]
    assert not retained_inputs(before,after[1:])[0]


def test_readiness_budget_counts_exact_inputs_and_still_rejects_oversized_model(monkeypatch):
    import pytest
    from air import readiness
    from air.foundation import InvalidModel
    members=sample()
    exported={'baseline':members[0], 'objects':members, 'dependency_lock':['a'*10000]*120}
    monkeypatch.setattr(readiness, 'snapshot', lambda *args: exported)
    actual,index=readiness._members(None,{},None,{})
    assert actual is exported and len(index)==len(members)
    oversized=deepcopy(members[-1]);oversized['body']['purpose']='a'*1100000
    exported['objects'].append(oversized)
    with pytest.raises(InvalidModel,match='simulation budget'): readiness._members(None,{},None,{})


def test_full_site_mcp_deadline_is_bounded_without_changing_ordinary_tools(tmp_path):
    from air.mcp import APIClient
    (tmp_path/'actor.json').write_text(json.dumps({'access_token':'fake-test-token'}),encoding='utf-8')
    observed=[]
    class Reply:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,size): return b'{}'
    class Opener:
        def open(self,req,timeout): observed.append(timeout);return Reply()
    client=APIClient(tmp_path,'actor.json');client.opener=Opener()
    assert client('air_compile_deliverables',{})=={}
    assert client('air_whoami',{})=={}
    assert observed==[600,120]
