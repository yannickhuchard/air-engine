"""Native typed proposal and fresh-session resumption; no full P07 acceptance."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.cli import bootstrap
from air.config import Settings,protect_directory,write_private
from air.core import FOUNDATION_PROFILE,digest
from air.foundation import exact,resolved
from air.ide_adapter import compile_adapter
from air.storage import Store
from install import start,stop
from qualify_native_clients import invoke

ROOT=Path(__file__).resolve().parents[1]


def qualify(work_root,client):
    if os.environ.get('AIR_DATABASE_URL'):raise ValueError('Unset AIR_DATABASE_URL for isolated qualification')
    root=work_root.resolve()/('air-native-design-'+uuid.uuid4().hex);protect_directory(root)
    home=root/'home';bootstrap(home);store=Store(Settings.load(home).database_url)
    scope=json.loads((ROOT/'examples/scope.json').read_text(encoding='utf-8'))
    store.put(scope,'synthetic-fixture')
    actor=store.create_token('native-design-author','editor');write_private(home/'actor.json',actor)
    write_private(home/'access-policy.json',{'version':'design-native','subjects':{actor['subject']:{'read':['example.claims'],'write':['example.claims']}}})
    meta=deepcopy(scope['meta']);meta.update(id='urn:p07:design:baseline',type='air.Baseline')
    base=store.create_baseline({'meta':meta,'profile':FOUNDATION_PROFILE,'members':[exact(scope)],'parent_baselines':[]},'synthetic-fixture')
    variant=deepcopy(scope);variant['meta']['revision']=2;variant['meta']['description']='Native proposed design revision'
    change_meta=deepcopy(meta);change_meta.update(id='urn:p07:design:change',type='air.ChangeSet')
    change={'meta':change_meta,'body':{'base':exact(base['baseline']),
        'operations':[{'op':'REPLACE','before':resolved(scope),'after':resolved(variant)}],
        'rationale':'Synthetic design proposal tested through a native client.',
        'expected_revisions':base['baseline']['body']['members'],'approvals':[]}}
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    folder=root/client;protect_directory(folder)
    adapter=compile_adapter(store,None,AccessPolicy(),{'client':client,'workspace':{'name':'P07 design','organization':'Asteria'},
        'access':'contribute','server':{'interpreter':sys.executable,'home':str(home),'credential':'actor.json','port':port}})
    for item in adapter['files']:
        path=folder/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(item['content'],encoding='utf-8')
    stages={};checks={};active=False
    def step(name,arguments):return {'tool':name,'arguments':arguments}
    def get(stage,tool):return next((c['result'] for c in reversed(stage['calls']) if c['tool']==tool),{})
    try:
        start(Path(sys.executable),home,port,no_worker=True);active=True
        proposed=invoke(client,folder,adapter['server_command'],[step('air_import_drafts',{'objects':[variant]}),
            step('air_propose_change',change),step('air_propose_change',change)])
        stages['propose']=proposed
        if proposed['status']=='CALLS_COMPLETED':
            value=get(proposed,'air_propose_change')
            checks['typed_change_persisted']=store.get(change['meta']['id'],1)['digest']==digest(change)
            checks['proposal_not_approval']=value.get('approved') is False and value.get('published') is False
            checks['replay_idempotent']=value['change']['created'] is False
            checks['base_and_target_pinned']=store.get(change['meta']['id'],1)['object']['body']['base']==exact(base['baseline']) and value['target']['baseline']['body']['parent_baselines']==[exact(base['baseline'])]
            target=exact(value['target']['baseline'])
            resumed=invoke(client,folder,adapter['server_command'],[step('air_get',exact(change)),step('air_export_baseline',target)])
            stages['fresh_session']=resumed
            checks['resumed_change_digest']=get(resumed,'air_get').get('digest')==digest(change)
            checks['resumed_target_digest']=get(resumed,'air_export_baseline').get('digest')==value['target']['digest']
            checks['original_revision_immutable']=store.get(scope['meta']['id'],1)['digest']==digest(scope)
    finally:
        try:
            if active:stop(home)
        finally:store.engine.dispose()
    return {'format':'air.native-design-exercise/1','version':__version__,'client':client,
        'status':'PASS_SCOPED' if checks and all(checks.values()) and all(
            stage['status']=='CALLS_COMPLETED' for stage in stages.values()) else 'INCOMPLETE',
        'stages':{name:{k:v for k,v in stage.items() if k!='calls'} for name,stage in stages.items()},
        'checks':checks,'server_stopped':True,'p07_received':False,'full_ide_suite_received':False,
        'human_review_performed':False,'production_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--client',choices=['codex','claude-code'],required=True)
    args=parser.parse_args();result=qualify(args.work_root,args.client)
    args.output.parent.mkdir(parents=True,exist_ok=True);write_private(args.output,result)
    print(json.dumps({'status':result['status'],'p07_received':False}))
    raise SystemExit(0 if result['status']=='PASS_SCOPED' else 2)
