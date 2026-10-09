"""Isolated P06 workstation qualification. No business home or external service is accepted."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler
import uuid

from air import __version__
from air.backup import snapshot,restore,validate_backup
from air.cli import bootstrap
from air.config import Settings,protect_directory,write_private
from air.operations_acceptance import CATEGORIES
from air.operations_reception import check
from air.storage import Store
from air.workstation import inspect
from install import start,stop
from qualify_capacity import qualify as capacity_qualify, FIXTURE
from qualify_operations import qualify as recovery_qualify

ROOT = Path(__file__).resolve().parents[1]


def source_fingerprint():
    value = hashlib.sha256()
    for path in sorted((ROOT/'src/air').rglob('*')):
        if path.suffix in ('.py','.json') and '__pycache__' not in path.parts:
            value.update(path.relative_to(ROOT).as_posix().encode()+b'\0'+path.read_bytes())
    return value.hexdigest()


def qualify_local(work_root):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for isolated qualification')
    workspace = work_root.resolve()/('air-workstation-'+uuid.uuid4().hex)
    protect_directory(workspace)
    home = workspace/'source';bootstrap(home)
    settings = Settings.load(home);store = Store(settings.database_url)
    obj = json.loads((ROOT/'examples/scope.json').read_text(encoding='utf-8'))
    token = json.loads((home/'credentials.json').read_text(encoding='utf-8'))['access_token']
    viewer = store.create_token('workstation-reader','reader')['access_token'];store.engine.dispose()
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));port = sock.getsockname()[1]
    def request(method,path,credential=None,body=None):
        headers = {'Content-Type':'application/json'}
        if credential: headers['Authorization'] = 'Bearer '+credential
        req = Request('http://127.0.0.1:'+str(port)+path,method=method,headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
        try:
            with build_opener(ProxyHandler({})).open(req,timeout=30) as response:
                return response.status,json.load(response)
        except HTTPError as exc:
            return exc.code,json.loads(exc.read(1048576))
    active = None
    checks = {}
    try:
        start(Path(sys.executable),home,port,no_worker=True);active = home
        first_inspection = inspect(home)
        checks.update(first_inspection['checks'])
        checks['anonymous_access_refused'] = request('GET','/v1/capabilities')[0] == 401
        checks['wrong_token_refused'] = request('GET','/v1/capabilities','invalid-workstation-token')[0] == 401
        checks['read_only_write_refused'] = request('POST','/v1/drafts',viewer,obj)[0] == 403
        status,stored = request('POST','/v1/drafts',token,obj)
        assert status == 201
        diagnostic = request('GET','/v1/operations',token)[1]
        checks['diagnostics_no_credentials'] = all(secret not in json.dumps(diagnostic) for secret in (token,viewer))
        stop(home);active = None
        snapshot(home,workspace/'snapshot')
        # Deliberately simulate unavailable source and lost post-snapshot work.
        # This is NOT a physical second device or a power-loss exercise.
        later = deepcopy(obj);later['meta']['id'] = 'urn:air:workstation:after-snapshot'
        start(Path(sys.executable),home,port,no_worker=True);active = home
        assert request('POST','/v1/drafts',token,later)[0] == 201
        stop(home);active = None
        copied = workspace/'recovery-media';protect_directory(copied)
        for path in (workspace/'snapshot').iterdir(): shutil.copyfile(path,copied/path.name)
        validate_backup(copied)
        archived = workspace/'source-unavailable'
        # Both exact targets are newly-created direct children of our private workspace.
        assert home.resolve().parent == archived.resolve().parent == workspace.resolve()
        home.rename(archived)
        begin = time.perf_counter()
        restored = workspace/'restored';receipt = restore(copied,restored)
        restore_seconds = time.perf_counter()-begin
        checks['restore_without_source'] = not home.exists() and receipt['status']=='PASS'
        checks['restored_identity_rotated'] = receipt['old_tokens_revoked'] is True and Settings.load(restored).instance_id != settings.instance_id
        new_token = json.loads((restored/'credentials.json').read_text(encoding='utf-8'))['access_token']
        start(Path(sys.executable),restored,port,no_worker=True);active = restored
        code,value = request('GET','/v1/objects/'+obj['meta']['id']+'/revisions/1',new_token)
        checks['restore_digests_equal'] = code==200 and value['digest']==stored['digest']
        checks['restored_identity_rotated'] &= request('GET','/v1/capabilities',token)[0] == 401
        checks['post_snapshot_change_absent'] = request('GET','/v1/objects/'+later['meta']['id']+'/revisions/1',new_token)[0] == 404
        checks['restored_service_usable'] = inspect(restored)['status']=='PASS' and request('POST','/v1/drafts',new_token,later)[0] == 201
    finally:
        if active: stop(active)
    checks['server_stopped'] = True
    return {'format':'air.workstation-qualification/1','version':__version__,
            'source_sha256':source_fingerprint(),'status':'PASS_SCOPED' if all(checks.values()) else 'FAIL',
            'environment':{'os':platform.platform(),'python':platform.python_version(),'database':'SQLite'},
            'checks':checks,'restore_seconds':round(restore_seconds,6),'physical_device_loss_tested':False,
            'backup_extra_required':False,'production_ready':False,'independent_operator':False}


def qualify(work_root,output,cycles=10):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for isolated qualification')
    if not 1 <= cycles <= 100: raise ValueError('Cycles must be 1..100')
    output = output.resolve()
    output.mkdir(parents=True,exist_ok=False);protect_directory(output)
    def save(name,value):
        path = output/(name+'.json');write_private(path,value)
        return {'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    fixtures = hashlib.sha256()
    for path in sorted(FIXTURE.rglob('*.json')):
        fixtures.update(path.relative_to(FIXTURE).as_posix().encode()+b'\0'+path.read_bytes())
    # Written before any workload. Reference product targets, never group commitments.
    targets = {'format':'air.operations-targets/1','version':__version__,'fixtures_sha256':fixtures.hexdigest(),
        'environment':{'os':platform.platform(),'python':platform.python_version(),'database':'SQLite'},
        'workload_minimum':{'concurrency':4,'revisions':69,'jobs':cycles*3,'artifact_bytes_each':65536,'elapsed_seconds':1},
        'latency_p95_seconds':{k:30 if k=='job_execute' else 10 for k in CATEGORIES},
        'max_server_peak_rss_bytes':536870912,'max_child_peak_rss_bytes':268435456,'rto_seconds':30}
    inputs = {'targets':save('targets',targets)}
    inputs['workstation'] = save('workstation',qualify_local(work_root))
    inputs['recovery'] = save('recovery',recovery_qualify(work_root))
    inputs['capacity'] = save('capacity',capacity_qualify(work_root,cycles=cycles,concurrency=4))
    dossier = {'format':'air.p06-workstation/1','profile':'LOCAL_ARCHITECT_WORKSTATION',
        'version':__version__,'source_sha256':source_fingerprint(),'inputs':inputs,
        'data_policy':{'backup_method':'Explicit consistent SQLite snapshot; encryption available as an optional extra',
          'recovery_procedure':'docs/lot-poste-local.md','retention_reference':'docs/lot-poste-local.md',
          'support_reference':'SECURITY.md','source_audit':'RETAINED_NO_AUTOMATIC_PURGE',
          'loss_window':'SINCE_LAST_SUCCESSFUL_BACKUP','physical_device_loss_tested':False}}
    save('dossier',dossier)
    result = check(output/'dossier.json');save('result',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=10)
    args = parser.parse_args()
    try:
        result = qualify(args.work_root,args.output,args.cycles)
        print(json.dumps({'status':result['status'],'issues':result['issues'],'report':str(args.output/'result.json')}))
        raise SystemExit(0 if result['technical_checks_passed'] else 2)
    except Exception as exc:
        print(json.dumps({'status':'FAIL','error_type':type(exc).__name__}))
        raise SystemExit(1)
