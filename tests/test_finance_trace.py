from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import pytest
from air import delivery_schema, financial_view, traceability_sankey
from air.core import digest
from air.deliverables import Graph
from air.expr import artifact_digest
from air.foundation import exact
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def model(kind, name, body, revision=1):
    from air.construction_schema import MANY
    body = deepcopy(body)
    for field in MANY.get('air.' + kind, {}): body.setdefault(field, [])
    if kind == 'ArchitectureBlock':
        for field in ('provided_contracts', 'required_contracts', 'owned_state', 'responsibilities'): body.setdefault(field, [])
    return {'meta': {'id': 'urn:test:' + name, 'revision': revision, 'type': 'air.' + kind, 'name': name, 'description': name, 'provenance': {'source_refs': []}}, 'body': body}


def graph(objects): return Graph([{'objects': objects}])


def cost(name='robot', value='180000', **extra):
    source = model('Source', 'budget-source', {})
    return model('CostItem', name, {'nature': 'CAPEX', 'category': 'OTHER', 'amount': {'value': value, 'currency': 'EUR'},
        'start': '2026-11', 'recurrence': 'ONCE', 'basis': 'Reference estimate, no quote', 'confidence': 'LOW',
        'calculation': {'parts': [{'label': 'Robot', 'quantity': '6', 'unit': 'robot', 'unit_price': '30000', 'explanation': 'Six units; transport and spares are separate'}],
            'sources': [exact(source)], 'evidence_status': 'ASSUMPTION'}, **extra})


def test_calculations_reconcile_exactly_and_are_context_independent():
    c = cost(); source = model('Source', 'budget-source', {})
    good = financial_view.project(graph([c, source]))
    assert good['rows'][0]['parts'][0]['subtotal'] == '180000'
    assert good['rows'][0]['sources'][0]['digest'] == digest(source)
    with localcontext() as ctx:
        ctx.prec = 3
        assert financial_view.project(graph([c, source])) == good
    assert not list(delivery_schema.local_issues(c))
    c['body']['calculation']['parts'][0]['quantity'] = '5'
    assert 'AIR_COST_CALCULATION' in {code for code, _ in delivery_schema.local_issues(c)}


def test_default_is_exactly_36_months_but_explicit_horizon_wins():
    c = cost(value='1000', recurrence='MONTHLY', nature='OPEX')
    del c['body']['calculation']
    view = financial_view.project(graph([c]))
    assert view['rows'][0]['period_end'] == '2029-10'
    assert Decimal(view['rows'][0]['period_total']) == 36000
    assert view['rows'][0]['horizon_assumed'] and view['missing']['calculations'] == 1
    c['body']['end'] = '2027-04'
    assert Decimal(financial_view.project(graph([c]))['rows'][0]['period_total']) == 6000
    usd = deepcopy(c);usd['meta']['id'] += ':usd';usd['body']['amount']['currency'] = 'USD'
    assert len(financial_view.project(graph([c, usd]))['totals']) == 2


def test_reference_approval_is_not_funding_and_vat_is_not_cost():
    c = cost(); src = model('Source', 'budget-source', {})
    p = model('FinancialPlan', 'plan', {'start':'2026-11','end':'2027-04','cost_items':[exact(c)],
        'programme_envelope': {'value':'200000','currency':'EUR'}, 'vat_bridge': {'value':'40000','currency':'EUR'},
        'reference_status':'APPROVED_REFERENCE', 'approval_source':exact(src), 'funding_status':'UNCONFIRMED','sources':[exact(src)],'basis':'Scope'})
    v = financial_view.project(graph([c, src, p]))['plans'][0]
    assert Decimal(v['calculated_cost']) == 180000 and Decimal(v['headroom']) == 20000
    assert Decimal(v['treasury_envelope']) == 240000 and v['funding_status'] == 'UNCONFIRMED'
    del p['body']['approval_source']
    assert 'AIR_FINANCE_APPROVAL' in {c for c, _ in delivery_schema.local_issues(p)}
    c['body']['amount']['currency'] = 'USD'
    assert 'AIR_FINANCE_CURRENCY' in {c for c, _, _ in delivery_schema.graph_issues([p,c,src], graph([p,c,src]).by_ref)}


def trace_model():
    req = model('Requirement','delivery',{'kind':'FUNCTIONAL'})
    quality = model('QualityRequirement','privacy',{})
    missing = model('Requirement','untraced',{'kind':'FUNCTIONAL'})
    f = model('Function','function',{'satisfies':[exact(req)]})
    b = model('ArchitectureBlock','block',{'functions':[exact(f)]})
    u = model('ConstructionUnit','unit',{'realizes':[exact(f)],'justified_by':[exact(req)],'outputs':[
        {'name':'Operating guide','kind':'DOCUMENT','description':'Training guide'},
        {'name':'Launch campaign','kind':'MARKETING_CAMPAIGN','description':'Prepared campaign'}]})
    env = model('Environment','prod',{'stage':'PRODUCTION'})
    runtime = model('RuntimeComponent','service',{'realizes':[exact(b), exact(u)],'environment':exact(env)})
    mapping = model('ComplianceMapping','privacy-map',{'subject':exact(quality),'status':'PLANNED','implemented_by':[exact(b)]})
    return [req,quality,missing,f,b,u,env,runtime,mapping]


def test_sankey_traces_functions_nfr_deliverables_and_future_production_without_inference():
    objects = trace_model();v = traceability_sankey.project(graph(objects))
    assert v['requirements'] == 3 and not v['business_execution_performed']
    assert {'DOCUMENT','MARKETING_CAMPAIGN','RuntimeComponent','NON_FUNCTIONAL','GAP'} <= {n['kind'] for n in v['nodes']}
    privacy_paths = [p for p in v['paths'] if any(e['source']['id'].endswith('privacy-map') for e in p['evidence'])]
    assert privacy_paths and any(e['status'] == 'PLANNED' for p in privacy_paths for e in p['evidence'])
    assert any(g['reason'] == 'ARCHITECTURE_BLOCK_MISSING' for g in v['gaps'])
    nodes = {n['id']:n for n in v['nodes']}
    for reqid in {p['nodes'][0] for p in v['paths']}:
        assert sum(Fraction(**p['weight']) for p in v['paths'] if p['nodes'][0] == reqid) == 1
    for node in v['nodes']:
        if node['layer'] not in (1,2): continue
        incoming = sum(Fraction(**l['value']) for l in v['links'] if l['target'] == node['id'])
        outgoing = sum(Fraction(**l['value']) for l in v['links'] if l['source'] == node['id'])
        assert incoming == outgoing
    for path in v['paths']:
        for ev in path['evidence']:
            obj = graph(objects).get(ev['source']); cursor = obj
            for field in ev['field'].split('/'): cursor = cursor[int(field)] if isinstance(cursor,list) else cursor[field]
            assert cursor == ev['target'] and ev['source_digest'] == digest(obj)
    assert traceability_sankey.project(graph(list(reversed(objects)))) == v


def test_same_name_wrong_revision_and_not_applicable_are_not_silent_links():
    objects = trace_model();objects[4]['body']['functions'][0]['revision'] = 2
    objects[5]['body']['realizes'][0]['revision'] = 2
    objects[8]['body']['status'] = 'NOT_APPLICABLE';objects[8]['body']['implemented_by'] = []
    v = traceability_sankey.project(graph(objects))
    assert len(v['exclusions']) == 1
    # Unit justified_by remains an explicit alternative through the runtime's co-realization.
    objects[7]['body']['realizes'] = []
    v = traceability_sankey.project(graph(objects))
    assert all(n['kind'] not in ('ArchitectureBlock','RuntimeComponent') for n in v['nodes'])


def test_unrelated_function_in_same_block_does_not_become_requirement_delivery():
    objects = trace_model(); other = model('Function','other-function',{'satisfies':[exact(objects[2])]})
    objects[4]['body']['functions'].append(exact(other))
    unrelated = model('ConstructionUnit','unrelated-unit',{'realizes':[exact(other)],'justified_by':[exact(objects[2])],
        'outputs':[{'name':'Unrelated output','kind':'DOCUMENT','description':'Different requirement'}]})
    view = traceability_sankey.project(graph(objects + [other,unrelated]))
    node_map = {n['id']:n for n in view['nodes']}
    for path in view['paths']:
        if node_map[path['nodes'][0]]['name'] == 'delivery':
            assert all(node_map[n]['name'] != 'Unrelated output' for n in path['nodes'])


def test_standard_pages_exact_json_digest_and_offline_inventory(compiled):
    report, request, _ = compiled;files = {f['path']:f['content'] for f in report['files']}
    d = report['website']['dossiers'][0]
    for field in ('finance','traceability','finance_data','traceability_data'):
        assert 'livrables/site/' + d[field] in files
    for field in ('finance_data','traceability_data'):
        data = json.loads(files['livrables/site/' + d[field]])
        assert data['baseline'] == request['baselines'][0]
        assert data['projection_digest'] == artifact_digest({k:v for k,v in data.items() if k != 'projection_digest'})
    home = files['livrables/site/' + d['path']]
    assert home.index('Dimension financière') < home.index('project-progress')
    assert 'Explorer le Sankey' in home
    assert 'Dimension financière' in files['livrables/site/index.html']
    assert 'Une unité par exigence' in files['livrables/site/' + d['traceability']]
