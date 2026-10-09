"""Exercise slow HTTP input and shared identity admission on a new disposable local SQLite service."""
import argparse
import http.client
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
import uuid

from air import __version__
from air.cli import bootstrap
from air.config import Settings, protect_directory, write_private
from air.parsing import MAX_BYTES
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def qualify(work_root):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for this isolated exercise')
    workspace = work_root.resolve()/('air-http-limits-'+uuid.uuid4().hex)
    protect_directory(workspace)
    home = workspace/'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        def credential(name, subject):
            path = home/(name+'.json')
            write_private(path, store.create_token(subject, 'editor'))
            return json.loads(path.read_text(encoding='utf-8'))['access_token']
        first, second = [credential('client-'+str(i), 'synthetic-client') for i in range(2)]
        other = credential('other-client', 'other-client')
        operator = json.loads((home/'credentials.json').read_text(encoding='utf-8'))['access_token']
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
        def request(path, token, payload=None):
            headers = {'Authorization':'Bearer '+token,'Content-Type':'application/json'}
            data = None if payload is None else json.dumps(payload).encode()
            req = Request('http://127.0.0.1:'+str(port)+path, headers=headers, data=data)
            try: response = build_opener(ProxyHandler({})).open(req, timeout=10)
            except HTTPError as exc: response = exc
            with response: return response.status, json.load(response)
        def begin(length, partial=b''):
            connection = socket.create_connection(('127.0.0.1',port),timeout=10)
            try:
                header = ('POST /v1/drafts HTTP/1.1\r\nHost: 127.0.0.1:'+str(port)+'\r\nAuthorization: Bearer '+first+
                          '\r\nContent-Type: application/json\r\nContent-Length: '+str(length)+'\r\nConnection: close\r\n\r\n')
                connection.sendall(header.encode()+partial)
                return connection
            except BaseException:
                connection.close();raise
        def finish(connection, expected):
            response = http.client.HTTPResponse(connection)
            try:
                response.begin()
                assert response.status == expected
                return json.loads(response.read(65537))
            finally: response.close()
        overrides = {'AIR_MAX_INFLIGHT':'8','AIR_MAX_INFLIGHT_PER_SUBJECT':'1','AIR_BODY_TIMEOUT_SECONDS':'5'}
        saved = {name:os.environ.get(name) for name in overrides}
        from install import start, stop
        started = False
        try:
            os.environ.update(overrides)
            start(Path(sys.executable), home, port, no_worker=True);started = True
            with begin(100, b'{') as slow:
                before = time.monotonic()
                while True:
                    status, response = request('/v1/capabilities', second)
                    if status == 429: break
                    assert status == 200 and time.monotonic()-before < 3, 'Slow request was not admitted'
                    time.sleep(.02)
                assert response == {'detail':{'code':'AIR_SUBJECT_BUSY'}}
                assert request('/v1/capabilities', other)[0] == 200
                assert request('/ready', other)[0] == 200
                assert finish(slow,408) == {'detail':{'code':'AIR_INPUT_TIMEOUT'}}
                elapsed = time.monotonic()-before
            assert store.counts()['revisions'] == 0
            with begin(MAX_BYTES+1) as oversized:
                assert finish(oversized,413) == {'detail':{'code':'AIR_INPUT_TOO_LARGE'}}
            assert store.counts()['revisions'] == 0
            example = json.loads((ROOT/'examples/scope.json').read_text(encoding='utf-8'))
            status, result = request('/v1/drafts', second, example)
            assert status == 201 and store.get(example['meta']['id'],1)['digest'] == result['digest']
            status, metrics = request('/v1/operations', operator)
            assert status == 200
            assert metrics['identity_admission']['rejected_busy'] >= 1
            assert metrics['input_limits']['rejections']['timeout'] == metrics['input_limits']['rejections']['too_large'] == 1
        finally:
            try:
                if started: stop(home)
            finally:
                for name,value in saved.items():
                    if value is None: os.environ.pop(name,None)
                    else: os.environ[name] = value
        return {'status':'PASS_SCOPED','version':__version__,'production_ready':False,
                'environment':{'os':platform.platform(),'python':platform.python_version()},
                'configuration':overrides,'transport':'REAL_LOOPBACK_HTTP',
                'checks':{'shared_identity_across_tokens':'PASS','other_identity_available':'PASS','probe_available':'PASS',
                          'partial_body_timeout':'PASS','oversized_declared_body':'PASS','partial_writes_absent':True,
                          'subsequent_deposit':'PASS','administrator_metrics':'PASS'},
                'observed_wait_seconds':round(elapsed,6),'server_stopped':True,
                'limitations':['No enterprise capacity/SLO claim','No distributed quotas or CPU/memory/job budgets','Native clients not qualified']}
    finally: store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try: report = qualify(args.work_root)
    except Exception as exc: report = {'status':'FAIL','error_type':type(exc).__name__,'production_ready':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps({'status':report['status'],'report':str(args.output)}))
    raise SystemExit(0 if report['status']=='PASS_SCOPED' else 1)
