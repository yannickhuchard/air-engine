"""Submit the browser-generated drafts to their isolated AIR demo and restore receipts."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.collaboration import read
from air.config import Settings
from air.core import canonical
from air.mcp import APIClient
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def verify():
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('This recipe uses isolated SQLite only')
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tmp/demo-asteria/workbench.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    browser = json.loads(report_path.with_name(report_path.stem + '-browser.json').read_text(encoding='utf-8'))
    assert report['version'] == browser['version'] == __version__ and browser['status'] == 'PASS'
    home = Path(report['workbench_home']).resolve()
    assert home.is_relative_to((ROOT / 'tmp').resolve()) and home.parent.name.startswith('air-runtime-') and home.name == 'home'
    cases = {r['case']: r for r in report['treatments']};assert set(cases) == {'D01', 'D02', 'D03'}
    assert {r['case'] for r in browser['results']} == set(cases)
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    received = []
    start(Path(sys.executable), home, port, no_worker=True)
    try:
        for result in browser['results']:
            case = cases[result['case']]
            assert case['workbench']['content_digest'] == result['source_content_digest']
            prepared = Path(result['prepared_submission']).resolve()
            assert prepared.is_relative_to((ROOT / 'tmp').resolve()) and prepared.parent.name.startswith('workbench-browser-')
            request = json.loads(prepared.read_text(encoding='utf-8'))
            target = case['knowledge']['conflict'] if case.get('knowledge') else (case['business']['goal'] if case.get('business') else case['decision']['object'])
            assert request['object']['body']['target'] == [{k: target[k] for k in ('id', 'revision')}]
            credential = 'observer-' + case['case'] + '.json'
            command = [sys.executable, '-m', 'air', '--home', str(home), 'collaboration-submit', str(prepared), '--credential', credential, '--port', str(port)]
            first = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert first.returncode == 0, 'Browser contribution was not accepted'
            submission = json.loads(first.stdout)
            again = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert again.returncode == 0
            replay = json.loads(again.stdout)
            assert not replay['created'] and replay['submission'] == submission['submission']
            value = APIClient(home, credential, port)('air_collaboration_read', {'submission': submission['submission']})
            assert canonical(value['object']) == canonical(request['object']) and value['business_mandate_granted'] is False
            received.append({'case': case['case'], 'submission': submission['submission'], 'receipt': value, 'idempotent_replay': True})
    finally: stop(home)
    backup = home.parent / ('browser-backup-' + uuid.uuid4().hex);target = home.parent / ('browser-restored-' + uuid.uuid4().hex)
    snapshot(home, backup);recovery = restore(backup, target)
    store = Store(Settings.load(target).database_url)
    try:
        for result in received:
            assert read(store, {'subject': 'local-admin', 'role': 'admin'}, AccessPolicy(), {'submission': result['submission']}) == result['receipt']
    finally: store.engine.dispose()
    return {'status': 'PASS', 'version': __version__, 'dossiers': received, 'browser_prepared_drafts_submitted_by_cli': True,
        'restored_receipts_identical': True, 'recovery': recovery, 'live_instance_modified': False, 'business_authority_granted': False}


if __name__ == '__main__':
    proof = verify();source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tmp/demo-asteria/workbench.json'
    output = source.with_name(source.stem + '-contributions.json')
    output.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': proof['status'], 'dossiers': len(proof['dossiers']), 'report': str(output)}))
