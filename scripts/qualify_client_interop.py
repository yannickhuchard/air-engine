"""Real CLI/API/stdio interoperation on two disposable local installations.

This is a protocol qualification, not ChatGPT/Claude/Codex native acceptance.
No existing home, external database or approval bypass is accepted.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import socket
import subprocess
import sys
import threading
import time
import uuid
from sqlalchemy import update
from air import __version__
from air.cli import bootstrap
from air.config import Settings, protect_directory, write_private
from air.foundation import exact
from air.mcp import APIClient, PROTOCOL
from air.storage import Store, tokens
from demo_projections import read
from install import start, stop


class Stdio:
    """Keep a real adapter process alive across API/credential interruptions."""
    def __init__(self, home, port, stderr):
        self.sequence=0;self.messages=queue.Queue()
        self.error_stream=stderr.open('x',encoding='utf-8')
        self.process=subprocess.Popen([sys.executable,'-m','air.mcp','--home',str(home),
            '--credential','actor.json','--port',str(port)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=self.error_stream,text=True,encoding='utf-8',bufsize=1)
        def drain():
            for line in self.process.stdout: self.messages.put(line)
            self.messages.put(None)
        self.reader=threading.Thread(target=drain,daemon=True);self.reader.start()
        try:
            self.request('initialize',{'protocolVersion':PROTOCOL,'capabilities':{},
                'clientInfo':{'name':'air-protocol-qualification','version':'1'}})
        except BaseException:
            self.close();raise

    def request(self, method, params=None):
        self.sequence+=1
        message={'jsonrpc':'2.0','id':self.sequence,'method':method}
        if params is not None: message['params']=params
        self.process.stdin.write(json.dumps(message)+'\n');self.process.stdin.flush()
        line=self.messages.get(timeout=30)
        if line is None: raise RuntimeError('Adapter exited without a response')
        result=json.loads(line)
        if result.get('id')!=self.sequence: raise RuntimeError('Adapter response does not match request')
        return result

    def call(self,name,args):
        result=self.request('tools/call',{'name':name,'arguments':args})
        if 'error' in result: return {'rpc_error':result['error']['code']}
        return result['result']['structuredContent']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.process.stdout.close();self.error_stream.close()


def replace_private(path,value):
    pending=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
    write_private(pending,value);os.replace(pending,path)


def qualify(work_root):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for isolated qualification')
    root=work_root.resolve()/('air-interop-'+uuid.uuid4().hex);protect_directory(root)
    homes=[root/'author',root/'recipient'];settings=[];stores=[];ports=[];sessions=[];active=set()
    checks={};observations=[]
    def receive(name,condition):
        checks[name]=bool(condition)
        if not condition: raise AssertionError('Interop check failed: '+name)
    def cli(home,port,*args):
        result=subprocess.run([sys.executable,'-m','air','--home',str(home),str(args[0]),'--credential','actor.json',
                               '--port',str(port),*map(str,args[1:])],capture_output=True,text=True,encoding='utf-8',timeout=60)
        if result.returncode: raise RuntimeError('Fixture CLI operation failed')
        return json.loads(result.stdout)
    case=read('manifest.json')['dossiers'][0]
    objects=read(case['construction']);baseline_request=read(case['construction_baseline_request'])
    namespaces=sorted({o['meta']['namespace'] for o in objects})
    credentials=[];policies=[]
    try:
        for index,home in enumerate(homes):
            bootstrap(home);setting=Settings.load(home);settings.append(setting)
            store=Store(setting.database_url);stores.append(store)
            credential=store.create_token('interop-'+str(index),'editor');credentials.append(credential)
            write_private(home/'actor.json',credential)
            policy={'version':'interop','subjects':{credential['subject']:{'read':namespaces,'write':namespaces}}}
            policies.append(policy);write_private(home/'access-policy.json',policy)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            ports.append(port);start(Path(sys.executable),home,port,no_worker=True);active.add(index)
            sessions.append(Stdio(home,port,root/('stdio-'+str(index)+'.stderr')))
        api=APIClient(homes[0],'actor.json',ports[0]);source,peer=sessions
        receive('independent_installations',settings[0].instance_id!=settings[1].instance_id)
        receive('individual_identities',source.call('air_whoami',{})['identity']!=peer.call('air_whoami',{})['identity'])
        imported=api('air_import_drafts',{'objects':objects})
        receive('source_imported',len(imported.get('objects',[]))==len(objects))
        baseline=api('air_freeze_baseline',baseline_request)
        pin=exact(baseline['baseline'])
        exported=api('air_export_baseline',pin)
        receive('cli_api_mcp_export_equal',exported==source.call('air_export_baseline',pin)==cli(homes[0],ports[0],'baseline-export',pin['id'],pin['revision']))
        # Only public architecture data are transferred, never registry identities,
        # credentials, service state or review authority. This is an explicit copy.
        transfer=root/'exchange.json';write_private(transfer,{'objects':exported['objects'],'baseline_request':baseline_request,
            'baseline_digest':exported['digest'],'dependency_lock':exported['dependency_lock']})
        copied=json.loads(transfer.read_text(encoding='utf-8'))
        receive('exchange_excludes_credentials',all(t['access_token'] not in transfer.read_text(encoding='utf-8') for t in credentials))
        receive('recipient_imported',len(peer.call('air_import_drafts',{'objects':copied['objects']}).get('objects',[]))==len(objects))
        reconstructed=peer.call('air_freeze_baseline',copied['baseline_request'])
        receive('baseline_digest_preserved',reconstructed.get('digest')==copied['baseline_digest'])
        received=peer.call('air_export_baseline',pin)
        receive('dependency_lock_and_members_preserved',received==exported)
        repeat=peer.call('air_import_drafts',{'objects':copied['objects']})
        receive('repeat_import_idempotent',all(not row['created'] for row in repeat['objects']))
        changed=deepcopy(objects[0]);changed['meta']['description']='Conflicting content at the same immutable revision'
        fresh=deepcopy(objects[0]);fresh['meta']['id']='urn:000:interop:must-rollback'
        before=stores[1].counts()
        conflict=peer.call('air_import_drafts',{'objects':[fresh,changed]})
        receive('conflict_refused_atomically',conflict.get('http_status')==409 and before==stores[1].counts())
        changed['meta']['revision']+=1
        receive('recipient_variant_created',peer.call('air_import_drafts',{'objects':[changed]})['objects'][0]['created'])
        receive('no_implicit_synchronization',source.call('air_get',exact(changed)).get('http_status')==404)
        invalid=deepcopy(objects[0]);invalid['meta']['revision']=0
        request={'objects':[invalid]};validation=api('air_validate_drafts',request)
        file=root/'invalid.json';write_private(file,request)
        receive('cli_api_mcp_diagnostics_equal',validation==source.call('air_validate_drafts',request)==cli(homes[0],ports[0],'drafts-validate',file))
        pid=source.process.pid
        # Expire only this fixture token; preserve the same adapter process.
        with stores[0].write() as conn:
            conn.execute(update(tokens).where(tokens.c.id==credentials[0]['token_id']).values(expires_at=int(time.time())-1))
        receive('expiry_removes_catalogue',source.request('tools/list')['result']['tools']==[])
        receive('expiry_refuses_cached_reference',source.call('air_export_baseline',pin).get('http_status')==401)
        replacement=stores[0].create_token(credentials[0]['subject'],'editor')
        replace_private(homes[0]/'actor.json',replacement)
        receive('rotation_same_process_recovers',source.process.pid==pid and source.call('air_export_baseline',pin)==exported)
        write_private(homes[0]/'expired.json',credentials[0])
        receive('old_credential_stays_refused',APIClient(homes[0],'expired.json',ports[0])('air_whoami',{}).get('http_status')==401)
        replace_private(homes[0]/'access-policy.json',{'version':'revoked','subjects':{}})
        receive('policy_revocation_refuses_cached_reference',source.call('air_export_baseline',pin).get('http_status')==403)
        replace_private(homes[0]/'access-policy.json',policies[0])
        receive('policy_restoration_recovers',source.call('air_export_baseline',pin)==exported)
        stop(homes[0]);active.remove(0)
        receive('outage_removes_catalogue',source.request('tools/list')['result']['tools']==[])
        unavailable=source.call('air_export_baseline',pin)
        receive('outage_never_returns_cached_data','error' in unavailable and 'objects' not in unavailable)
        start(Path(sys.executable),homes[0],ports[0],no_worker=True);active.add(0)
        receive('network_recovery_same_process',source.process.pid==pid and source.call('air_export_baseline',pin)==exported)
        forged=source.call('air_get',{**exact(objects[0]),'actor':'admin'})
        receive('forged_identity_refused',forged.get('rpc_error')==-32602)
        observations=[{'baseline_digest':exported['digest'],'exchange_sha256':hashlib.sha256(transfer.read_bytes()).hexdigest(),
                       'member_count':len(exported['objects']),'namespace_count':len(namespaces)}]
    finally:
        try:
            for session in sessions:session.close()
        finally:
            try:
                for index in sorted(active):stop(homes[index])
            finally:
                for store in stores:store.engine.dispose()
    return {'format':'air.client-interop/1','version':__version__,'status':'PASS_SCOPED',
            'execution_kind':'PROTOCOL_PROCESS','environment':{'os':platform.platform(),'python':platform.python_version(),'database':'SQLite'},
            'checks':checks,'observations':observations,'servers_stopped':True,'adapters_stopped':True,
            'physical_devices':1,'independent_registries':2,'native_clients_qualified':False,'human_review_performed':False,
            'p07_received':False,'production_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=qualify(args.work_root)
    args.output.parent.mkdir(parents=True,exist_ok=True);write_private(args.output,report)
    print(json.dumps({'status':report['status'],'checks':len(report['checks']),'p07_received':False}))
