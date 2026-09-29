"""Replay four Asteria calculations after a real worker exit and server restart."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from air import __version__
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings
from air.jobs import get_job
from air.mcp import APIClient, PROTOCOL, Session
from air.storage import Store, SCHEMA_VERSION
from demo_planning import prepare
from demo_experiments import read, request_for
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Isolated job demo requires default SQLite')
    workspace = ROOT / 'tmp' / ('air-jobs-' + uuid.uuid4().hex)
    home = workspace / 'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        planning = prepare(store)
        experiments = [request_for(store, case) for case in read('manifest.json')['dossiers']]
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    def execute(command, body):
        file = workspace / (command + '-' + uuid.uuid4().hex + '.json')
        file.write_text(json.dumps(body), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(file), '--port', str(port)],
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert result.returncode == 0, 'Unexpected CLI result for ' + command
        return json.loads(result.stdout)
    start(Path(sys.executable), home, port, no_worker=True)
    queued = []
    try:
        requests = [('portfolio', 'plan', planning)] + [('D0' + str(i + 1), 'simulate', value) for i, value in enumerate(experiments)]
        for label, operation, args in requests:
            request = {'idempotency_key': label, 'operation': operation, 'arguments': args}
            job = execute('job-submit', request)
            assert not execute('job-submit', request)['created']
            queued.append({'case': label, 'job': job['job']})
        cancelled = execute('job-submit', {'idempotency_key': 'cancel-before-start', 'operation': 'plan', 'arguments': planning})
        assert execute('job-cancel', {'job': cancelled['job']})['status'] == 'CANCELLED'
    finally: stop(home)
    # A separate worker commits a one-second lease and exits abruptly, without
    # calculating or publishing a result. No projection is modified by the demo.
    marker = workspace / 'crashed-claim.json'
    code = "import os,json,sys;from pathlib import Path;from air.config import Settings;from air.storage import Store;from air import jobs;jobs.LEASE_SECONDS=1;s=Store(Settings.load(Path(sys.argv[1])).database_url);a=jobs.claim(s,'crashed-demo-worker');Path(sys.argv[2]).write_text(json.dumps({'job_id':a['job']['id'],'attempt':a['attempt']}));os._exit(17)"
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    crashed = subprocess.run([sys.executable, '-c', code, str(home), str(marker)], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, **options)
    assert crashed.returncode == 17
    abandoned = json.loads(marker.read_text())
    start(Path(sys.executable), home, port)
    reports = []
    try:
        deadline = time.monotonic() + 45
        for queued_job in queued:
            while True:
                report = execute('job-read', {'job': queued_job['job']})
                if report['status'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'): break
                assert time.monotonic() < deadline, 'Worker did not finish within the rehearsal budget'
                time.sleep(.2)
            assert report['status'] == 'SUCCEEDED'
            if report['job']['id'] == abandoned['job_id']: assert report['attempt'] == 2
            reports.append({'case': queued_job['case'], 'report': report})
        assert [r['report']['result']['outcome']['result'] for r in reports] == ['VIOLATED', 'SATISFIED', 'SATISFIED', 'CONFLICTING']
        assert execute('job-read', {'job': cancelled['job']})['status'] == 'CANCELLED'
        session = Session(APIClient(home, 'credentials.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'jobs-replay', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        replay = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_get_job', 'arguments': {'job': queued[-1]['job']}}})['result']
        assert not replay['isError'] and replay['structuredContent'] == reports[-1]['report']
    finally: stop(home)
    snapshot(home, workspace / 'backup')
    restored_home = workspace / 'restored'
    recovery = restore(workspace / 'backup', restored_home)
    recovered = Store(Settings.load(restored_home).database_url)
    try:
        for item in reports:
            historical = get_job(recovered, {'subject': 'local-admin', 'role': 'admin'}, AccessPolicy(), {'job': item['report']['job']})
            assert historical == item['report']
    finally: recovered.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'schema': SCHEMA_VERSION, 'reports': reports,
        'cancelled': cancelled['job'], 'abrupt_worker_exit': 17, 'lease_recovered': abandoned,
        'server_restarted': True, 'restored_results_identical': True, 'recovery': recovery,
        'external_effects': False, 'live_instance_modified': False, 'business_authorization_granted': False}


if __name__ == '__main__':
    result = rehearse()
    output = ROOT / 'tmp/demo-asteria/jobs.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'report': str(output), 'calculations': len(result['reports'])}))
