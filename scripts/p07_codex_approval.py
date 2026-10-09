"""Attended Codex app-server cancellation on the isolated P07 bench.

Only a human/operator response file answers a native approval request. Unknown
requests are retained, never granted automatically. No approval bypass is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from air.config import protect_directory, write_private
from air.mcp import APIClient
from air.native_evidence import calls
from p07_session_bench import bench_home, state


def run(root, output, job_file=None):
    bench = state(root)
    home, _ = bench_home(root, bench)
    if output.exists():
        raise ValueError('Choose a new evidence directory')
    protect_directory(output)
    client = bench['clients']['codex']
    api = APIClient(home, client['credential'], bench['port'])
    if job_file is not None:
        candidate = root/job_file
        if Path(job_file).name != job_file or candidate.is_symlink():
            raise ValueError('Job receipt must be a regular JSON file directly inside the isolated bench')
        job = json.loads(candidate.read_text(encoding='utf-8'))
        if api('air_get_job', {'job': job.get('job')}).get('status') != 'QUEUED':
            raise ValueError('Native submitted job is not queued in this bench')
    else:
        job = api('air_submit_job', {'idempotency_key': 'attended-cancel-'+output.name,
                                   'operation': 'plan', 'arguments': bench['planning_arguments']})
    if 'job' not in job:
        raise ValueError('Cannot prepare synthetic job')
    write_private(output/'fixture.json', {'job': job['job']})
    executable = shutil.which('codex')
    stream = (output/'native.jsonl').open('w', encoding='utf-8')
    process = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=client['workspace'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding='utf-8', env=dict(os.environ, PYTHONUTF8='1'))
    pending = queue.Queue()
    def reader():
        for line in process.stdout:
            stream.write(line); stream.flush()
            try: pending.put(json.loads(line))
            except ValueError: pass
        pending.put(None)
    thread = threading.Thread(target=reader, daemon=True); thread.start()
    def send(value):
        process.stdin.write(json.dumps(value)+'\n'); process.stdin.flush()
    def receive(identifier=None, done=False):
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            item = pending.get(timeout=max(0.1, deadline-time.monotonic()))
            if item is None: raise RuntimeError('Native session closed')
            if 'id' in item and 'method' in item:
                write_private(output/'pending.json', item)
                print(json.dumps({'approval_pending': item['method'], 'request': str(output/'pending.json')}), flush=True)
                response = output/'response.json'
                while not response.exists() and time.monotonic() < deadline: time.sleep(0.2)
                if not response.exists(): raise TimeoutError('Approval not answered')
                result = json.loads(response.read_text(encoding='utf-8'))
                response.rename(output/('response-'+str(item['id'])+'.json'))
                (output/'pending.json').rename(output/('request-'+str(item['id'])+'.json'))
                send({'id': item['id'], 'result': result})
            if identifier is not None and item.get('id') == identifier:
                if 'error' in item: raise RuntimeError('Native request failed: '+str(item['error']))
                return item['result']
            if done and item.get('method') == 'turn/completed': return item
        raise TimeoutError('Native session timed out')
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'air_p07_attended', 'version': '1'},
                                                        'capabilities': {'experimentalApi': True}}})
        receive(1); send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'thread/start', 'params': {'cwd': client['workspace'], 'ephemeral': True,
                                                         'sandbox': 'read-only', 'approvalPolicy': 'on-request'}})
        identity = receive(2)['thread']['id']
        prompt = ('Native AIR acceptance on synthetic data. Discover local air MCP tools via tool search if needed. '
                  'Call air_cancel_job with '+json.dumps({'job': job['job']})+' twice sequentially, then air_get_job with the same arguments. '
                  'The operator will answer the approval interactively. Do not use shell, other connectors or files. '
                  'No other job may be changed. Do not bypass approvals.')
        send({'id': 3, 'method': 'turn/start', 'params': {'threadId': identity,
              'input': [{'type': 'text', 'text': prompt, 'text_elements': []}]}})
        receive(3); receive(done=True)
        value = api('air_get_job', {'job': job['job']})
        rows = [json.loads(line) for line in (output/'native.jsonl').read_text(encoding='utf-8').splitlines()]
        observed = calls('codex', rows)
        checks = {'native_calls': [c['tool'] for c in observed] == ['air_cancel_job', 'air_cancel_job', 'air_get_job'],
                  'exact_job': all(c['arguments'] == {'job': job['job']} for c in observed),
                  'native_cancelled': bool(observed) and all(c['result'].get('status') == 'CANCELLED' for c in observed),
                  'registry_cancelled': value.get('status') == 'CANCELLED',
                  'idempotent': len(observed) == 3 and observed[0]['result'].get('changed') is True
                                and observed[1]['result'].get('changed') is False,
                  'approval_answered': bool(list(output.glob('request-*.json'))) and bool(list(output.glob('response-*.json')))}
        result = {'status': 'PASS_SCOPED' if all(checks.values()) else 'INCOMPLETE', 'checks': checks,
                  'job': job['job'], 'final_job_status': value.get('status'),
                  'approval_requests': len(list(output.glob('request-*.json'))), 'human_operator': False,
                  'scope': 'Native approval routed to Codex operator; not independent human acceptance',
                  'transcript_sha256': hashlib.sha256((output/'native.jsonl').read_bytes()).hexdigest(), 'p07_received': False}
        write_private(output/'report.json', result)
        return result
    finally:
        process.stdin.close()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=10)
        thread.join(timeout=5); stream.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--job-file', help='Existing native-submission JSON filename within the isolated bench')
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output.resolve(), args.job_file)
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS_SCOPED' else 2)
