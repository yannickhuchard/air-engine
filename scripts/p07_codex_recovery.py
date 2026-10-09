"""Native Codex recovery in one app-server thread on the isolated P07 bench."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid

from sqlalchemy import update
from air.config import protect_directory, write_private
from air.native_evidence import calls
from air.storage import Store, tokens
from install import start, stop
from p07_session_bench import bench_home, policy, state


def observed_calls(rows):
    observed = []
    for row in rows:
        completed = calls('codex', [row])
        if completed:
            observed.extend(completed)
            continue
        # A coded adapter outage is an observed error response, never a success.
        # It has no HTTP status because the API was unreachable.
        params = row.get('params') if isinstance(row, dict) else None
        item = params.get('item') if isinstance(params, dict) else None
        if not isinstance(item, dict) or row.get('method') != 'item/completed': continue
        result = item.get('result')
        payload = result.get('structuredContent') if isinstance(result, dict) else None
        if (item.get('type') == 'mcpToolCall' and item.get('server') == 'air'
                and item.get('status') == 'failed' and item.get('error') is None
                and isinstance(payload, dict) and payload.get('error') == 'AIR_UNREACHABLE'):
            observed.append({'tool': item.get('tool'), 'arguments': item.get('arguments'), 'result': payload})
    return observed


def evaluate(root, output):
    """Recompute from completed native turns, including adapter error responses."""
    bench = state(root)
    bench_home(root, bench)
    rows = [json.loads(line) for line in (output/'native.jsonl').read_text(encoding='utf-8').splitlines()]
    blocks = []; current = None; threads = set()
    for row in rows:
        if row.get('method') == 'turn/started':
            if current is not None: raise ValueError('Overlapping native turns')
            current = []; threads.add(row['params']['threadId'])
        if current is not None: current.append(row)
        if row.get('method') == 'turn/completed' and current is not None:
            blocks.append(observed_calls(current)); current = None
    phases = ('connected', 'restricted', 'expired', 'rotated', 'offline', 'recovered')
    if len(blocks) != len(phases) or current is not None: raise ValueError('Incomplete native turn sequence')
    stages = dict(zip(phases, blocks))
    ref = {k: bench['fixtures']['scope'][k] for k in ('id', 'revision')}
    def value(phase, tool):
        return next((c['result'] for c in stages[phase] if c['tool'] == tool), {})
    checks = {'same_native_thread': len(threads) == 1,
              'all_calls_observed': all([(c['tool'], c['arguments']) for c in stage] == [('air_whoami', {}), ('air_get', ref)] for stage in stages.values()),
              'policy_refusal': value('restricted', 'air_get').get('http_status') == 403,
              'expiry_refusal': value('expired', 'air_get').get('http_status') == 401,
              'outage_reported': value('offline', 'air_get').get('error') == 'AIR_UNREACHABLE',
              'digest_preserved': all(value(p, 'air_get').get('digest') == bench['fixtures']['scope']['digest'] for p in ('connected', 'rotated', 'recovered')),
              'identity_preserved': all(value(p, 'air_whoami').get('subject') == bench['clients']['codex']['subject'] for p in ('connected', 'rotated', 'recovered'))}
    return {'format': 'air.native-codex-recovery/1', 'status': 'PASS_SCOPED' if all(checks.values()) else 'INCOMPLETE',
            'checks': checks, 'transcript_sha256': hashlib.sha256((output/'native.jsonl').read_bytes()).hexdigest(), 'p07_received': False}


class NativeSession:
    def __init__(self, workspace, home, credential, port, output):
        self.output = output
        protect_directory(output)
        self.rows = []
        self.pending = queue.Queue()
        self.log = (output/'native.jsonl').open('x', encoding='utf-8')
        executable = shutil.which('codex')
        args = ['-m', 'air.mcp', '--home', str(home), '--credential', credential, '--port', str(port)]
        command = [executable, 'app-server', '--stdio',
                   '-c', 'mcp_servers.air.command='+json.dumps(sys.executable),
                   '-c', 'mcp_servers.air.args='+json.dumps(args),
                   '-c', 'mcp_servers.air.enabled_tools=["air_whoami", "air_get"]',
                   '-c', 'mcp_servers.air.required=true']
        self.process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
        def reader():
            for line in self.process.stdout:
                self.log.write(line); self.log.flush()
                try:
                    value = json.loads(line)
                    self.rows.append(value); self.pending.put(value)
                except ValueError: pass
            self.pending.put(None)
        self.reader = threading.Thread(target=reader, daemon=True); self.reader.start()
        try:
            self.initialize(workspace)
        except BaseException:
            self.close()
            raise

    def initialize(self, workspace):
        self.send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'air_recovery_receipt', 'version': '1'},
                    'capabilities': {'experimentalApi': True}}})
        self.receive(1)
        self.send({'method': 'initialized', 'params': {}})
        self.send({'id': 2, 'method': 'thread/start', 'params': {'cwd': str(workspace), 'ephemeral': True,
                    'sandbox': 'read-only', 'approvalPolicy': 'on-request'}})
        self.thread = self.receive(2)['thread']['id']
        self.next_id = 3

    def send(self, value):
        self.process.stdin.write(json.dumps(value)+'\n'); self.process.stdin.flush()

    def receive(self, identifier=None):
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            row = self.pending.get(timeout=max(.1, deadline-time.monotonic()))
            if row is None: raise RuntimeError('Native process closed')
            if 'id' in row and 'method' in row:
                write_private(self.output/('unanswered-'+str(row['id'])+'.json'), row)
                raise RuntimeError('Unexpected native approval; not granted')
            if identifier is not None and row.get('id') == identifier:
                if 'error' in row: raise RuntimeError(str(row['error']))
                return row['result']
            if identifier is None and row.get('method') == 'turn/completed': return row
        raise TimeoutError('Native turn timed out')

    def read(self, ref, phase):
        offset = len(self.rows)
        prompt = ('Synthetic AIR recovery receipt, phase '+phase+'. Discover local air MCP tools using native search if necessary. '
                  'Call air_whoami with {}, then air_get with '+json.dumps(ref)+'. '
                  'Make both actual calls even when a previous call is refused. Continue after expected errors. '
                  'Do not answer from history or cache. Do not use shell, files, other connectors or subagents. '
                  'No writes and no settings changes. Report the returned error if the service is unavailable.')
        identifier = self.next_id; self.next_id += 1
        self.send({'id': identifier, 'method': 'turn/start', 'params': {'threadId': self.thread,
                   'input': [{'type': 'text', 'text': prompt, 'text_elements': []}]}})
        self.receive(identifier); self.receive()
        observed = observed_calls(self.rows[offset:])
        write_private(self.output/(phase+'.json'), {'phase': phase, 'calls': observed})
        print(json.dumps({'phase': phase, 'tools': [c['tool'] for c in observed]}), flush=True)
        return observed

    def close(self):
        try: self.process.stdin.close()
        except OSError: pass
        try: self.process.wait(timeout=10)
        except subprocess.TimeoutExpired: self.process.terminate(); self.process.wait(timeout=10)
        self.reader.join(timeout=5); self.log.close()


def run(root, output):
    bench = state(root); home, settings = bench_home(root, bench)
    client = bench['clients']['codex']
    if output.exists(): raise ValueError('Choose new receipt directory')
    original = json.loads((home/'access-policy.json').read_text(encoding='utf-8'))
    store = Store(settings.database_url)
    ref = {k: bench['fixtures']['scope'][k] for k in ('id', 'revision')}
    session = None; stages = {}; stopped = False; rotated = False
    try:
        session = NativeSession(Path(client['workspace']), home, client['credential'], bench['port'], output)
        stages['connected'] = session.read(ref, 'connected')
        restricted = deepcopy(original)
        restricted['version'] = 'codex-recovery-restricted'
        restricted['subjects'][client['subject']]['read'] = []
        policy(root, restricted, 'codex-recovery-restrict')
        stages['restricted'] = session.read(ref, 'restricted')
        policy(root, original, 'codex-recovery-restore')
        with store.write() as conn:
            conn.execute(update(tokens).where(tokens.c.id == client['token_id']).values(expires_at=int(time.time())-1))
        stages['expired'] = session.read(ref, 'expired')
        replacement = store.create_token(client['subject'], 'editor')
        pending = home/('replacement-'+uuid.uuid4().hex+'.json'); write_private(pending, replacement)
        os.replace(pending, home/client['credential']); rotated = True
        from p07_session_bench import save
        bench['clients']['codex']['token_id'] = replacement['token_id']; save(root, bench)
        stages['rotated'] = session.read(ref, 'rotated')
        stop(home); stopped = True
        stages['offline'] = session.read(ref, 'offline')
        start(Path(sys.executable), home, bench['port'], no_worker=True); stopped = False
        stages['recovered'] = session.read(ref, 'recovered')
    finally:
        try:
            policy(root, original, 'codex-recovery-final-policy')
            if stopped: start(Path(sys.executable), home, bench['port'], no_worker=True)
            # If interrupted before rotation, do not leave the fixture identity expired.
            if not rotated:
                with store.write() as conn:
                    conn.execute(update(tokens).where(tokens.c.id == client['token_id']).values(expires_at=int(time.time())+86400))
        finally:
            if session: session.close()
            store.engine.dispose()
    report = evaluate(root, output)
    write_private(output/'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recheck', action='store_true')
    args = parser.parse_args()
    if args.recheck:
        result = evaluate(args.root.resolve(), args.output.resolve())
        write_private(args.output/'rechecked-report.json', result)
    else: result = run(args.root.resolve(), args.output.resolve())
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS_SCOPED' else 2)
