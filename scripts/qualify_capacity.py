"""Mixed Asteria reference workload in a new private SQLite home; no enterprise SLO claim."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
import sys
import threading
import time
from urllib.request import Request,build_opener,ProxyHandler
import uuid
from air import __version__
from air.cli import bootstrap
from air.config import Settings,protect_directory,write_private
from air.storage import Store
from air import jobs
from air.monitor import probe
from air.audit_archive import export as audit_export,verify as audit_verify
from air.resource_usage import process_usage
from air.job_budget import profile as job_profile
from demo_projections import read,ref,FIXTURE
from demo_experiments import request_for
from demo_planning import prepare
from install import start,stop


def qualify(work_root,cycles=3,concurrency=2,artifact_bytes=65536):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for this isolated exercise')
    if not 1 <= cycles <= 100 or not 1 <= concurrency <= 16 or not 1 <= artifact_bytes <= 262144:
        raise ValueError('Invalid bounded workload')
    workspace = work_root.resolve()/('air-capacity-'+uuid.uuid4().hex);protect_directory(workspace)
    home = workspace/'home';bootstrap(home);settings = Settings.load(home);store = Store(settings.database_url)
    samples = {};lock = threading.Lock()
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));port = sock.getsockname()[1]
    def request(category,path,body=None,actor=0):
        token = json.loads((home/('load-'+str(actor)+'.json')).read_text(encoding='utf-8'))['access_token']
        req = Request('http://127.0.0.1:'+str(port)+path,data=json.dumps(body).encode() if body is not None else None,
                      headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        before = time.perf_counter()
        with build_opener(ProxyHandler({})).open(req,timeout=60) as response: value = json.load(response)
        with lock: samples.setdefault(category,[]).append(time.perf_counter()-before)
        return value
    started = False
    try:
        for actor in range(concurrency): write_private(home/('load-'+str(actor)+'.json'),store.create_token('load-'+str(actor),'admin'))
        start(Path(sys.executable),home,port,no_worker=True);started = True
        before = time.perf_counter();metrics_before = request('metrics','/v1/operations')
        bases = []
        for case in read('manifest.json')['dossiers']:
            imported = request('import','/v1/draft-bundles',read(case['construction']))
            assert imported['objects']
            base = request('baseline','/v1/baselines',read(case['construction_baseline_request']))
            assert base['created'];bases.append(ref(base))
        # These builders repeat exact immutable deposits to construct illustrative model inputs.
        simulations = [request_for(store,case) for case in read('manifest.json')['dossiers']]
        planning = prepare(store)
        def cycle(index):
            actor = index % concurrency
            case = index % 3
            view = request('query','/v1/views',{'baseline':bases[case]},actor)
            assert view
            result = request('simulate','/v1/experiments',simulations[case],actor)
            assert result['result'] == ('CONFLICTING' if case == 2 else 'SATISFIED')
            result = request('plan','/v1/plans',planning,actor)
            assert result['result'] == 'VIOLATED'
            data = (str(index)+':').encode().ljust(artifact_bytes,b'x')[:artifact_bytes]
            artifact = request('artifact_write','/v1/artifacts/import',{'idempotency_key':'load-'+str(index),
                'namespace':'asteria.sav','media_type':'application/octet-stream','content_base64':base64.b64encode(data).decode()},actor)
            downloaded = request('artifact_read','/v1/artifacts/read',{'artifact':artifact['artifact']},actor)
            assert base64.b64decode(downloaded['content_base64']) == data
            job = request('job_submit','/v1/jobs',{'idempotency_key':'load-'+str(index),'operation':'plan','arguments':planning},actor)
            return actor,job['job']
        with ThreadPoolExecutor(max_workers=concurrency) as pool: submitted = list(pool.map(cycle,range(cycles*3)))
        worker_before = process_usage()
        for actor,job in submitted:
            begin = time.perf_counter();result = jobs.run_next(store,settings)
            samples.setdefault('job_execute',[]).append(time.perf_counter()-begin)
            assert result['status'] == 'SUCCEEDED'
        for actor,job in submitted:
            result = request('job_read','/v1/jobs/read',{'job':job},actor)
            assert result['status'] == 'SUCCEEDED' and result['result']['outcome']['result'] == 'VIOLATED'
        metrics = request('metrics','/v1/operations');monitor = probe(home)
        assert monitor['status'] == 'PASS'
        elapsed = time.perf_counter()-before;worker_after = process_usage()
        archive = audit_export(home,workspace/'audit','2099-01-01T00:00:00Z')
        assert audit_verify(workspace/'audit')['sha256'] == archive['sha256']
        revisions = store.counts()['revisions']
    finally:
        store.engine.dispose()
        if started: stop(home)
    latency = {}
    for category,values in samples.items():
        ordered = sorted(values)
        latency[category] = {'samples':len(values),'seconds_total':round(sum(values),6),
            'seconds_max':round(max(values),6),
            'seconds_p95':round(ordered[math.ceil(len(values)*.95)-1],6)}
    fixture_hash = hashlib.sha256()
    for path in sorted(FIXTURE.rglob('*.json')):
        fixture_hash.update(path.relative_to(FIXTURE).as_posix().encode()+b'\0'+path.read_bytes())
    return {'format':'air.capacity/1','status':'PASS_SCOPED','version':__version__,
        'environment':{'os':platform.platform(),'python':platform.python_version(),'database':'SQLite'},
        'workload':{'kind':'ASTERIA_MIXED_REFERENCE','enterprise_representative':False,
                    'fixtures_sha256':fixture_hash.hexdigest(),'dossiers':3,'revisions':revisions,
                    'cycles_per_dossier':cycles,'concurrency':concurrency,'jobs':len(submitted),
                    'artifact_bytes_each':artifact_bytes,'elapsed_seconds':round(elapsed,6)},
        'latency':latency,'server_resources':metrics['resources'],
        'server_cpu_delta_seconds':round(metrics['resources']['cpu_seconds']-metrics_before['resources']['cpu_seconds'],6),
        'supervisor_resources':worker_after,
        'supervisor_cpu_delta_seconds':round(worker_after['cpu_seconds']-worker_before['cpu_seconds'],6),
        'child_resources':job_profile(),
        'monitor':monitor,'audit_archive':archive,'server_stopped':True,
        'enterprise_slo':'NOT_EVALUATED','production_ready':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=3)
    parser.add_argument('--concurrency',type=int,default=2)
    parser.add_argument('--artifact-bytes',type=int,default=65536)
    args = parser.parse_args()
    try: result = qualify(args.work_root,args.cycles,args.concurrency,args.artifact_bytes)
    except Exception as exc: result = {'status':'FAIL','error_type':type(exc).__name__,'production_ready':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'report':str(args.output)}))
    raise SystemExit(0 if result['status']=='PASS_SCOPED' else 1)
