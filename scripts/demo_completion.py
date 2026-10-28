"""Isolated architecture completion through CLI and MCP, without fabricated qualification."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from air import __version__, artifacts, completion, deliverables
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import BUILD_PROFILE
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('completion_fixture', ROOT / 'fixtures/build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output.resolve()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for this isolated SQLite recipe')
    output.mkdir(parents=True, exist_ok=False)
    home = output / '.air'; bootstrap(home); settings = Settings.load(home); store = Store(settings.database_url)
    credential = json.loads((home / 'credentials.json').read_text(encoding='utf-8'))
    user = store.authenticate(credential['access_token'], True); user['authorization']['instance_id'] = settings.instance_id
    # This is an explicitly authorized fictional test installation, never a real user's policy.
    document = {'version': 'fictional-completion-recipe', 'subjects': {user['subject']: {
        'read': [model.NAMESPACE], 'write': [model.NAMESPACE], 'authorize_design': [model.NAMESPACE]}}}
    write_private(home / 'access-policy.json', document); policy = AccessPolicy(document)
    server = None; log = None
    env = dict(os.environ); env['PYTHONUTF8'] = '1'; env.pop('AIR_DATABASE_URL', None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        descriptors = {n: artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
            'media_type': 'application/json', 'idempotency_key': n}, (model.ROOT / (n + '.schema.json')).read_bytes())['artifact_reference'] for n in ('request', 'response')}
        objects = model.objects(descriptors); store.put_bundle(objects, user['subject'])
        origin = store.create_baseline({'meta': model.obj('Baseline', 'baseline', {})['meta'], 'profile': BUILD_PROFILE,
            'members': [exact(o) for o in objects], 'parent_baselines': []}, user['subject'])
        pin = completion.pin(origin['baseline'])
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log = (output / 'server.log').open('w', encoding='utf-8')
        server = subprocess.Popen([sys.executable, '-m', 'air', '--home', str(home), 'serve', '--port', str(port)],
            stdout=log, stderr=log, env=env, creationflags=flags)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response: assert json.load(response)['status'] == 'ok'
                break
            except Exception:
                if server.poll() is not None or time.monotonic() > deadline: raise RuntimeError('Isolated API failed to start')
                time.sleep(.1)
        session = Session(APIClient(home, 'credentials.json', port=port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL,
            'capabilities': {}, 'clientInfo': {'name': 'Completion protocol recipe', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        calls = []
        def invoke(command, name, request):
            path = output / ('request-' + str(len(calls)) + '.json'); path.write_text(json.dumps(request), encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(path), '--port', str(port)],
                capture_output=True, text=True, encoding='utf-8', timeout=180, env=env, creationflags=flags)
            if result.returncode: raise RuntimeError(command + ' failed: ' + result.stderr[-1000:] + result.stdout[-1000:])
            expected = json.loads(result.stdout)
            answer = session.handle({'jsonrpc': '2.0', 'id': len(calls) + 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': request}})
            observed = json.loads(answer['result']['content'][0]['text'])
            if command == 'completion-create':
                assert expected['created'] and not observed['created']
                assert {k: v for k, v in observed.items() if k != 'created'} == {k: v for k, v in expected.items() if k != 'created'}
            else: assert observed == expected, (command, observed)
            calls.append(command); return expected
        run = invoke('completion-create', 'air_create_completion_run', {'idempotency_key': 'recipe', 'baseline': pin,
            'scope': completion.pin(next(o for o in objects if o['meta']['type'] == 'air.Scope')),
            'objectives': [completion.pin(next(o for o in objects if o['meta']['type'] == 'air.Requirement'))], 'purpose': 'Fictional quote design completion'})['run']
        def read(): return invoke('completion-read', 'air_read_completion_run', {'run': run})
        def cmd(key): return {'run': run, 'checkpoint': read()['checkpoint'], 'idempotency_key': key}
        invoke('completion-authorize', 'air_authorize_completion_run', {**cmd('mandate'), 'mandate': {
            'executors': [user['subject']], 'allowed_types': completion.TYPES, 'max_cycles': 3, 'max_objects': 1000,
            'max_no_progress': 3, 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')},
            'rationale': 'Explicit authorization for isolated fictional technical recipe only.'})
        obj = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Function'))
        obj['meta']['revision'] += 1; obj['meta']['description'] = 'Detailed quote mechanism for builders.'
        prepared = invoke('drafts-rebase', 'air_rebase_drafts', {'base': pin, 'objects': [obj], 'include_bundle': False})['prepared_change']['id']
        invoke('completion-advance', 'air_advance_completion_run', {**cmd('save-proposal'), 'action': 'CHECKPOINT',
            'prepared_change': prepared, 'summary': 'Retain the candidate before resuming from another session.'})
        assert read()['pending_change'] == prepared
        candidate = invoke('completion-read', 'air_read_completion_run', {'run': run, 'prepared_change': prepared})
        assert candidate['candidate']['automatic_apply_eligible']
        applied = invoke('completion-apply', 'air_apply_completion_run', {**cmd('apply'), 'prepared_change': prepared,
            'name': 'Builder explanation', 'description': 'Clarify an authorized technical mechanism.'})
        assert applied['baseline']['revision'] == 2
        invoke('completion-advance', 'air_advance_completion_run', {**cmd('question'), 'action': 'ESCALATE', 'summary': 'Request a real qualification.',
            'question': {'id': 'review', 'kind': 'QUALIFICATION', 'question': 'Who will provide the actual independent review?',
                'references': [completion.pin(next(o for o in completion.snapshot(completion.ScopedStore(store, user, policy), applied['baseline'])['objects'] if o['meta']['type'] == 'air.Scope'))]}})
        invoke('completion-stop', 'air_stop_completion_run', {**cmd('pause'), 'state': 'PAUSED', 'rationale': 'End this recipe at a safe checkpoint.'})
        final = read(); assert final['execution_state'] == 'PAUSED' and final['outcome'] != 'READY_TO_BUILD'
        pack = deliverables.compile_deliverables(store, user, policy, {'title': 'Architecture completion recipe', 'baselines': [applied['baseline']], 'content': 'FULL'})
        apply_files(output / 'workspace', pack['files'], plan_files(output / 'workspace', pack['files']))
        result = {'version': __version__, 'result': 'PASS_SCOPED', 'cli_mcp_equal': True, 'commands': calls,
            'run': run, 'checkpoint': final['checkpoint'], 'baseline': final['baseline'], 'cycles': final['cycles'],
            'outcome': final['outcome'], 'execution_state': final['execution_state'],
            'blocking': final['evaluation']['readiness']['blocking'], 'native_clients_qualified': False,
            'independent_review_inferred': False, 'business_runtime_executed': False, 'model_kept_running': False}
        (output / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result))
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=10)
        if log: log.close()
        store.engine.dispose()


if __name__ == '__main__': main()
