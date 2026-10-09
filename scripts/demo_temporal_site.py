"""Compare two explicitly fictional designs for each of three Asteria solutions.

Uses a fresh protected SQLite registry, retains the original nine unexecuted
business tests, and never changes the live AIR instance or executes the designs.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from air import artifacts, temporal_site
from air.access import AccessPolicy
from air.api import create_app
from air.atelier import apply_files, plan_files, previous_generation
from air.config import Settings, protect_directory
from air.core import DELIVERY_PROFILE, reference_slots
from air.deliverables import compile_deliverables
from air.foundation import exact
from air.mcp import PROTOCOL
from air.storage import Store
from demo_architecture_site import extend, read
from demo_business_paths import augment

ROOT = Path(__file__).resolve().parents[1]


def future_design(code, members, store, user, policy, settings):
    updated = deepcopy(members);stem = 'urn:asteria:site:' + code.lower() + ':'
    by_id = {o['meta']['id']:o for o in updated}
    changed = {stem + name for name in ('entity', 'schema', 'table', 'decision')}
    for a in by_id[stem+'entity']['body']['attributes']:
        if a['name'] == 'related_id': a['required'] = True
    for c in by_id[stem+'table']['body']['columns']:
        if c['name'] == 'related_id': c['nullable'] = False
    raw = json.dumps({'type':'object','additionalProperties':False,'properties':{'id':{'type':'string'},
        'occurred_at':{'type':'string','format':'date-time'},'status':{'type':'string'},'related_id':{'type':'string'}},
        'required':['id','occurred_at','status','related_id']}).encode()
    art = artifacts.put(store,user,policy,settings,{'namespace':by_id[stem+'schema']['meta']['namespace'],
        'idempotency_key':'future-schema-'+code,'media_type':'application/json'},raw)
    by_id[stem+'schema']['body']['artifact'] = art['artifact_reference']
    by_id[stem+'decision']['body']['consequences'].append('Cible fictive : rendre la référence liée obligatoire ; migration et coexistence à concevoir avant réalisation.')
    # Propagate only exact reference revisions. No acceptance/execution status is
    # changed, and no missing reference is invented to make the gate green.
    while True:
        consumers = {o['meta']['id'] for o in updated if any(r['id'] in changed for _,r,_ in reference_slots(o))}
        expanded = changed | consumers
        if expanded == changed: break
        changed = expanded
    for o in updated:
        if o['meta']['id'] in changed:
            o['meta']['revision'] += 1;o['meta']['recorded_at'] = '2026-10-03T00:00:00Z'
            o['meta']['validity'] = {'start':'2027-04-01T00:00:00Z','end':None}
        for _,ref,_ in reference_slots(o):
            if ref['id'] in changed: ref['revision'] += 1
    prototype = deepcopy(by_id[stem+'entity']['meta']);prototype.update(id=stem+'migration-milestone',type='air.Milestone',revision=1,
        name='Revue de migration avant mise en œuvre',description='Jalon fictif prévu, sans migration exécutée.',
        validity={'start':'2027-04-01T00:00:00Z','end':'2027-07-01T00:00:00Z'})
    updated.append({'meta':prototype,'body':{'target_date':'2027-06-15','exit_criteria':['Plan de migration et retour arrière revus'],
        'deliverables':[exact(by_id[stem+'database'])],'depends_on':[]}})
    return updated


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'tmp/temporal-site-20261003');args=parser.parse_args()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated SQLite demo')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    home=output/('registry-'+uuid.uuid4().hex);protect_directory(home)
    settings=Settings(home,'sqlite:///'+(home/'air.db').as_posix(),instance_id='temporal-site-demo')
    store=Store(settings.database_url);store.migrate();policy=AccessPolicy()
    token=store.create_token('temporal-site-author','admin');user=store.authenticate(token['access_token'],True)
    user['authorization']['instance_id']=settings.instance_id
    pins=[];comparisons=[]
    try:
        for case in read('manifest.json')['dossiers']:
            members=augment(case['id'],extend(case,read(case['construction']),store,user,policy,settings),store,user,policy,settings)
            store.put_bundle(members,'fictional-design')
            meta=deepcopy(read(case['construction_baseline_request'])['meta']);meta.update(id='urn:asteria:temporal-baseline:'+case['id'].lower(),name=case['title']+' - design A')
            a=store.create_baseline({'meta':meta,'profile':DELIVERY_PROFILE,'members':[exact(o) for o in members],'parent_baselines':[]},'fictional-design')
            before={**exact(a['baseline']),'digest':a['digest']}
            future=future_design(case['id'],members,store,user,policy,settings);store.put_bundle(future,'fictional-design')
            meta=deepcopy(meta);meta.update(revision=2,name=case['title']+' - cible proposée B',recorded_at='2026-10-03T00:00:00Z')
            b=store.create_baseline({'meta':meta,'profile':DELIVERY_PROFILE,'members':[exact(o) for o in future],'parent_baselines':[exact(a['baseline'])]},'fictional-design')
            after={**exact(b['baseline']),'digest':b['digest']};pins.extend([before,after])
            comparisons.append({'title':case['title']+' : design A / cible proposée B','before':before,'after':after})
        request={'title':'Asteria - changements des designs et calendrier prévu','baselines':pins,'comparisons':comparisons}
        counts=store.counts();pack=compile_deliverables(store,user,policy,request)
        assert pack['file_set_digest']==compile_deliverables(store,user,policy,request)['file_set_digest']
        query={**request,'content':'DIGESTS'};headers={'Authorization':'Bearer '+token['access_token']}
        with TestClient(create_app(settings,run_worker=False),base_url='http://127.0.0.1') as client:
            response=client.post('/v1/deliverables/compile',json=query,headers=headers);assert response.status_code==200
            assert response.json()['file_set_digest']==pack['file_set_digest']
            mcp=client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'air_compile_deliverables','arguments':query}},
                headers={**headers,'Accept':'application/json, text/event-stream','MCP-Protocol-Version':PROTOCOL}).json()['result']
            assert not mcp['isError'] and mcp['structuredContent']['file_set_digest']==pack['file_set_digest']
            assert client.post('/v1/deliverables/compile',json=query).status_code==401
        assert counts==store.counts()
        workspace=output/'project';workspace.mkdir(exist_ok=True)
        plan=plan_files(workspace,pack['files'],previous_generation(workspace,pack['files']));assert not any(x['action']=='CONFLICT' for x in plan)
        apply_files(workspace,pack['files'],plan)
        assert all(x['action']=='UNCHANGED' for x in plan_files(workspace,pack['files'],previous_generation(workspace,pack['files'])))
        timeline=json.loads(next(f['content'] for f in pack['files'] if f['path'].endswith('/site/timeline.json')))
        for c in timeline['comparisons']:
            assert c['summary']['ADDED']>=1 and c['summary']['CONTENT']>=4 and c['semantic_compatibility']=='NOT_EXECUTED'
        report={'status':'PASS_SCOPED','scope':'Three fictional solutions, two pinned designs each; no business execution',
            'site':pack['website'],'entrypoint':str(workspace/pack['website']['entrypoint']),'file_set_digest':pack['file_set_digest'],
            'gates':pack['gates'],'solutions':3,'states':6,'comparisons':[{'title':c['title'],'summary':c['summary'],'comparison_digest':c['comparison_digest']} for c in timeline['comparisons']],
            'temporal_report_digest':timeline['report_digest'],'http_mcp_parity':True,'deterministic':True,'registry_unchanged_by_queries':True,
            'sqlite':True,'business_tests_executed':0,'original_business_tests_not_executed':9,'ci_run':False}
        (output/'site-demo.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':report['status'],'solutions':3,'states':6,'comparisons':3,'entrypoint':report['entrypoint']}))
    finally: store.engine.dispose()


if __name__=='__main__': main()
