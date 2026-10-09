from copy import deepcopy
import json
import re
import pytest
from air import deliverables, temporal_site
from air.core import digest
from air.expr import artifact_digest
from air.foundation import InvalidModel, TooLarge, exact
from air.access import AccessPolicy, Forbidden
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401
from test_architecture_site import contents, Links


def comparison(before, after):
    return {'title': 'Deux designs choisis', 'before': temporal_site.pin(before), 'after': temporal_site.pin(after)}


def test_comparison_keeps_field_changes_and_exact_sources_without_writes(store, compiled):
    _, request, _ = compiled;before = store.export_baseline(request['baselines'][0]);after = deepcopy(before)
    entity = next(o for o in after['objects'] if o['meta']['type'] == 'air.DataEntity')
    entity['meta']['revision'] += 1;entity['body']['attributes'][0]['required'] = False
    after['baseline']['meta']['revision'] += 1;after['digest'] = digest(after['baseline'])
    counts = store.counts();req = [comparison(before, after)]
    result = temporal_site.project([before, after], req)
    change = next(c for c in result['comparisons'][0]['objects'] if c['id'] == entity['meta']['id'])
    assert change['status'] == 'CONTENT'
    assert any(f['path'].endswith('/required') and f['before'] is True and f['after'] is False for f in change['fields'])
    assert change['after'][0]['reference']['digest'] == digest(entity)
    assert change['before'][0]['reference']['revision'] + 1 == change['after'][0]['reference']['revision']
    assert result == temporal_site.project([before, after], req) and store.counts() == counts
    assert artifact_digest({k:v for k,v in result.items() if k != 'report_digest'}) == result['report_digest']
    assert not result['registry_knowledge_history_available'] and not result['filtered_view_is_closed_baseline']
    assert result['semantic_compatibility'] == 'NOT_EXECUTED'


def test_multiple_revisions_are_not_collapsed_or_paired_arbitrarily(store, compiled):
    _, request, _ = compiled;before = store.export_baseline(request['baselines'][0]);after = deepcopy(before)
    old = after['objects'][0];new = deepcopy(old);new['meta']['revision'] += 1
    after['objects'].append(new)
    result = temporal_site.compare(before, after, 'Révisions coexistantes')
    changed = next(c for c in result['objects'] if c['id'] == old['meta']['id'])
    assert changed['status'] == 'MULTIPLE_REVISIONS' and len(changed['after']) == 2 and not changed['fields']
    assert temporal_site.compare(after, after, 'Identique')['summary']['UNCHANGED'] == len({o['meta']['id'] for o in after['objects']})


def test_add_remove_and_revision_metadata_reference_changes_are_distinct(store, compiled):
    _, request, _ = compiled;before = store.export_baseline(request['baselines'][0]);after = deepcopy(before)
    removed = after['objects'].pop(0)
    added = deepcopy(removed);added['meta']['id'] += ':new';after['objects'].append(added)
    revision = after['objects'][0];revision['meta']['revision'] += 1
    metadata = after['objects'][1];metadata['meta']['description'] += ' après revue'
    from air.core import reference_slots
    reference = next(o for o in after['objects'][2:] if list(reference_slots(o)))
    slot = next(iter(reference_slots(reference)))[1];slot['revision'] += 1
    statuses = {c['id']: c['status'] for c in temporal_site.compare(before, after, 'Changes')['objects']}
    assert statuses[removed['meta']['id']] == 'REMOVED' and statuses[added['meta']['id']] == 'ADDED'
    assert statuses[revision['meta']['id']] == 'REVISION_ONLY'
    assert statuses[metadata['meta']['id']] == 'METADATA_ONLY'
    assert statuses[reference['meta']['id']] == 'REFERENCE_ONLY'


def test_validity_is_canonical_microsecond_utc_and_planned_dates_are_not_execution(store, compiled):
    _, request, _ = compiled;e = deepcopy(store.export_baseline(request['baselines'][0]))
    source = e['objects'][0];source['meta']['validity'] = {'start': '2027-01-01T01:00:00.000001+01:00', 'end': '2027-01-01T00:00:00.000002Z'}
    milestone = next(o for o in e['objects'] if o['meta']['type'] == 'air.Milestone')
    milestone['body']['target_date'] = '2027-02-30'  # DAY's regex alone admits it; do not draw March 2.
    roadmap = {'meta':{**deepcopy(milestone['meta']), 'id':'urn:fiction:roadmap:temporal', 'type':'air.Roadmap'},
               'body':{'strategy':'Phases déclarées','uses_ai':False,'status':'PROPOSED','rationale':'Revue avant réalisation',
                       'phases':[{'id':'prepare','name':'Préparer','objective':'Réviser le plan','start':'2027-06-01','end':'2027-06-30','team_size':2},
                                 {'id':'reversed','name':'Intervalle à corriger','objective':'Pas de correction silencieuse','start':'2027-06-01','end':'2027-05-01','team_size':2}]}}
    e['objects'].append(roadmap)
    result = temporal_site.project([e], []);state = result['snapshots'][0]
    period = next(o for o in state['objects'] if o['reference']['id'] == source['meta']['id'])
    assert period['valid_start'] == '2027-01-01T00:00:00.000001Z'
    assert period['valid_end'] == '2027-01-01T00:00:00.000002Z'
    assert state['gaps'][0]['code'] == 'INVALID_PLANNED_DATE'
    assert all(p['planned_only'] for p in state['plans']) and any(not p['dates_valid'] for p in state['plans'])
    phases = [p for p in state['plans'] if p['source']['id'] == roadmap['meta']['id']]
    assert len(phases) == 2 and any(p['dates_valid'] and p['declared'] == roadmap['body']['phases'][0] for p in phases)
    assert len(state['gaps']) == 2 and any(p['selector'] == '/body/phases/1' and not p['dates_valid'] for p in phases)


def test_endpoint_and_projection_limits_are_explicit(store, compiled):
    _, request, _ = compiled;e = store.export_baseline(request['baselines'][0]);c = comparison(e, e)
    c['after']['digest'] = 'sha256:' + '0'*64
    with pytest.raises(InvalidModel): temporal_site.project([e], [c])
    with pytest.raises(TooLarge): temporal_site.project([{**e, 'objects': [e['objects'][0]] * 1001}], [])


def test_static_comparison_uses_authorized_exact_baselines_and_escapes_model_text(store, example):
    source = obj(example, 'Source', 'time-source', {'kind':'DOCUMENT','locator':'urn:fiction:source','captured_at':'2026-09-19T00:00:00Z','access_policy':'test','retention_policy':'test'})
    newer = deepcopy(source);newer['meta']['revision'] = 2;newer['meta']['description'] = '</script><img src=https://bad.invalid/x onerror=alert(1)>'
    store.put_bundle([source,newer], 'fictional')
    pins = [frozen(store, example, [source], 'urn:baseline:time-a'), frozen(store, example, [newer], 'urn:baseline:time-b')]
    with pytest.raises(InvalidModel) as ambiguity:
        frozen(store, example, [source,newer], 'urn:baseline:time-both')
    assert any(d['code']=='AIR_BASELINE_VERSION_AMBIGUOUS' for d in ambiguity.value.report['diagnostics'])
    req = {'title':'Dates','baselines':pins,'comparisons':[{'title':'A puis B','before':pins[0],'after':pins[1]}]}
    user = {'subject':'local-admin','role':'admin'};counts = store.counts()
    report = deliverables.compile_deliverables(store,user,POLICY,req);files = contents(report)
    model = json.loads(files['livrables/site/timeline.json']);page = files['livrables/site/timeline.html']
    assert model['comparisons'][0]['summary']['METADATA_ONLY'] == 1
    assert report['website']['temporal']['comparisons'] == 1 and counts == store.counts()
    embedded = json.loads(re.search(r'<script type="application/json" id="air-temporal">(.*?)</script>', page, re.S).group(1))
    assert embedded['temporal'] == model
    from air.architecture_site import anchor
    for i,o in enumerate((source,newer)):
        definitions=files['livrables/site/'+report['website']['dossiers'][i]['path'].rsplit('/',1)[0]+'/objects.html']
        assert 'id="'+anchor(o)+'"' in definitions
    assert '</script><img' not in page and '<img src=https://bad.invalid' not in page
    parsed = Links();parsed.feed(page);assert not any(h.startswith(('http:','https:','javascript:')) for h in parsed.targets)
    bad = deepcopy(req);bad['comparisons'][0]['before'] = {**bad['comparisons'][0]['before'], 'digest':'sha256:'+'0'*64}
    with pytest.raises(InvalidModel): deliverables.compile_deliverables(store,user,POLICY,bad)
    with pytest.raises(InvalidModel): deliverables.compile_deliverables(store,user,POLICY,{**req,'website':False})
    with pytest.raises(Forbidden): deliverables.compile_deliverables(store,{'subject':'outsider','role':'reader'},AccessPolicy({'version':'restricted','subjects':{'outsider':{'read':['elsewhere']}}}),req)
