"""Exercise only a newly created SQLite installation; never accept a business home or URL."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
import uuid

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from air import __version__
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings, protect_directory
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def sqlite_faults(home):
    store = Store(Settings.load(home).database_url)
    if not store.sqlite: raise ValueError('This fault exercise requires its isolated SQLite database')
    @event.listens_for(store.engine, 'checkout')
    def short_wait(connection, *_): connection.execute('PRAGMA busy_timeout=50')
    try:
        committed = store.record_once('ops-before-fault', 'ops.fixture', 'ops', 'fixture', {'value': 1})
        database = Path(store.engine.url.database)
        with sqlite3.connect(database) as locked:
            locked.execute('BEGIN IMMEDIATE')
            try:
                try: store.record_once('ops-locked', 'ops.fixture', 'ops', 'fixture', {'value': 2})
                except OperationalError as exc:
                    if exc.orig.sqlite_errorcode & 255 != sqlite3.SQLITE_BUSY: raise
                else: raise AssertionError('Write succeeded through SQLite write lock')
            finally: locked.rollback()
        assert store.get_record('ops-locked') is None
        store.record_once('ops-after-lock', 'ops.fixture', 'ops', 'fixture', {'value': 3})
        try:
            with store.write() as conn:
                pages = conn.exec_driver_sql('PRAGMA page_count').scalar_one()
                conn.exec_driver_sql('PRAGMA max_page_count=' + str(pages))
                store._record_once(conn, 'ops-full', 'ops.fixture', 'ops', 'fixture', {'synthetic': 'x' * 1048576})
        except OperationalError as exc:
            if exc.orig.sqlite_errorcode & 255 != sqlite3.SQLITE_FULL: raise
        else: raise AssertionError('SQLite capacity limit did not reject the write')
        finally:
            with store.engine.connect() as conn: conn.exec_driver_sql('PRAGMA max_page_count=2147483646')
        assert store.get_record('ops-full') is None
        assert store.get_record('ops-before-fault') == committed['record']
        store.record_once('ops-after-full', 'ops.fixture', 'ops', 'fixture', {'value': 4})
    finally: store.engine.dispose()
    # Abrupt process exit inside an open transaction, without Python finally/atexit handlers.
    code = """import os,sys
from air.config import Settings
from air.storage import Store
from pathlib import Path
s=Store(Settings.load(Path(sys.argv[1])).database_url)
with s.write() as c:
    s._record_once(c,'ops-uncommitted','ops.fixture','ops','fixture',{'value':5})
    os._exit(73)
"""
    result = subprocess.run([sys.executable, '-c', code, str(home)], capture_output=True, timeout=30)
    assert result.returncode == 73, 'Crash child did not reach the controlled fault point'
    reopened = Store(Settings.load(home).database_url)
    try:
        assert reopened.get_record('ops-uncommitted') is None
        assert reopened.get_record('ops-before-fault') == committed['record']
        reopened.record_once('ops-after-crash', 'ops.fixture', 'ops', 'fixture', {'value': 6})
        with reopened.engine.connect() as conn: assert conn.exec_driver_sql('PRAGMA quick_check').all() == [('ok',)]
    finally: reopened.engine.dispose()
    return {'write_lock': 'PASS', 'sqlite_full_page_quota': 'PASS', 'abrupt_transaction_exit': 'PASS',
            'committed_data_preserved': True, 'partial_writes_absent': True, 'subsequent_writes': 'PASS',
            'physical_disk_full': 'NOT_EXECUTED', 'host_power_loss': 'NOT_EXECUTED'}


def qualify(work_root, count=24, concurrency=4):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for this isolated exercise')
    if not 1 <= count <= 10000 or not 1 <= concurrency <= 32: raise ValueError('Invalid bounded workload')
    workspace = work_root.resolve() / ('air-operations-' + uuid.uuid4().hex)
    protect_directory(workspace)
    home = workspace/'home';bootstrap(home)
    example = json.loads((ROOT/'examples/scope.json').read_text(encoding='utf-8'))
    faults = sqlite_faults(home)
    from install import start, stop
    with socket.socket() as port_probe:
        port_probe.bind(('127.0.0.1', 0));port = port_probe.getsockname()[1]
    token = json.loads((home/'credentials.json').read_text(encoding='utf-8'))['access_token']
    def request(method, path, body=None):
        opener = build_opener(ProxyHandler({}))
        req = Request('http://127.0.0.1:' + str(port) + path,
                      data=json.dumps(body).encode() if body is not None else None, method=method,
                      headers={'Authorization':'Bearer ' + token, 'Content-Type':'application/json'})
        before = time.perf_counter()
        try:
            with opener.open(req, timeout=60) as response: value, status = json.load(response), response.status
        except HTTPError as exc:
            raise RuntimeError('Operational workload HTTP failure: ' + str(exc.code)) from None
        return value, status, time.perf_counter()-before
    def cycle(index):
        obj = deepcopy(example);obj['meta']['id'] = 'urn:air:operations:scope:' + str(index)
        first, status, a = request('POST', '/v1/drafts', obj)
        again, repeated, b = request('POST', '/v1/drafts', obj)
        read, _, c = request('GET', '/v1/objects/' + obj['meta']['id'] + '/revisions/1')
        assert status == 201 and repeated == 200 and first['digest'] == again['digest'] == read['digest']
        return {'id':obj['meta']['id'], 'digest':first['digest'], 'seconds':[a,b,c]}
    started = False
    try:
        start(Path(sys.executable), home, port, no_worker=True);started = True
        before = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool: samples = list(pool.map(cycle, range(count)))
        duration = time.perf_counter()-before
        metrics, _, _ = request('GET', '/v1/operations')
    finally:
        if started: stop(home)
    ordered = sorted(v for sample in samples for v in sample['seconds'])
    latency = {str(p): round(ordered[math.ceil(len(ordered)*p/100)-1],6) for p in (50,95,99)}
    before = time.perf_counter();snapshot(home, workspace/'backup');backup_seconds = time.perf_counter()-before
    from air.backup_crypto import create_key, encrypt, decrypt
    key_file = create_key(workspace/'keys')['key_file']
    encrypt(workspace/'backup', workspace/'encrypted', key_file)
    decrypt(workspace/'encrypted', workspace/'decrypted', key_file)
    before = time.perf_counter();recovery = restore(workspace/'decrypted', workspace/'restored');restoration_seconds = time.perf_counter()-before
    restored = Store(Settings.load(workspace/'restored').database_url)
    try:
        assert all(restored.get(sample['id'],1)['digest'] == sample['digest'] for sample in samples)
        assert not restored.authenticate(token)
        assert restored.get_record('ops-before-fault') is not None
    finally: restored.engine.dispose()
    canonical = json.dumps([{'id':s['id'],'digest':s['digest']} for s in samples], sort_keys=True).encode()
    return {'status':'PASS_SCOPED', 'version':__version__, 'schema':recovery['schema'],
            'environment':{'os':platform.platform(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version},
            'workload':{'fixture_sha256':hashlib.sha256((ROOT/'examples/scope.json').read_bytes()).hexdigest(),
                        'kind':'SYNTHETIC_HTTP_CREATE_IDEMPOTENT_REPLAY_READ', 'objects':count,
                        'concurrency':concurrency,'requests':count*3,'seconds':round(duration,6),
                        'latency_seconds_percentiles':latency,'digests_sha256':hashlib.sha256(canonical).hexdigest()},
            'faults':faults, 'metrics':metrics, 'server_stopped':True,
            'recovery':{'backup_seconds':round(backup_seconds,6),'restore_seconds':round(restoration_seconds,6),
                        'encrypted_roundtrip':'PASS', 'key_included':False,
                        'all_workload_digests_equal':True,'old_identity_revoked':True},
            'enterprise_slo':'NOT_EVALUATED','production_ready':False,
            'not_executed':['Representative group workload','CPU/memory profiling','Physical ENOSPC','Host power loss','PostgreSQL failover','Independent operator acceptance']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=24)
    parser.add_argument('--concurrency', type=int, default=4)
    args = parser.parse_args()
    try: report = qualify(args.work_root,args.count,args.concurrency)
    except Exception as exc:
        # Private workspace retains diagnostics/data; never echo a token or driver error.
        report = {'status':'FAIL','error_type':type(exc).__name__,'production_ready':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps({'status':report['status'],'report':str(args.output)}))
    raise SystemExit(0 if report['status']=='PASS_SCOPED' else 1)
