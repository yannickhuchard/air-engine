"""Isolated ChatGPT tunnel bench; full protocol records stay private and unqualified.

This does not attach a tunnel or impersonate ChatGPT. Native app observations must
be correlated with these records before attributing any call to a client.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time
import uuid

from air.config import protect_directory, write_private
from air.mcp import APIClient, serve
from air.parsing import parse
from air.redaction import redact
from air.storage import Store
from p07_session_bench import HOME, act, bench_home, grants, policy, prepare, save, state


def prepare_chatgpt(root):
    prepare(root, 'codex')
    bench = state(root)
    home, settings = bench_home(root, bench)
    store = Store(settings.database_url)
    try:
        codex = {k: bench[k] for k in ('subject', 'token_id', 'credential', 'workspace')}
        token = store.create_token('p07-session-chatgpt', 'editor')
        write_private(home/'chatgpt.json', token)
        bench.update(client='chatgpt', subject=token['subject'], token_id=token['token_id'], credential='chatgpt.json')
        bench['clients'] = {'codex': codex}
        bench['chatgpt_tunnel_bench'] = True
        save(root, bench)
        policy(root, grants(bench), 'chatgpt-initial')
        return {'subject': bench['subject'], 'port': bench['port'], 'root': str(root),
                'pilot_modified': False, 'tunnel_connected': False}
    finally:
        store.engine.dispose()


def checked(root):
    bench = state(root)
    home, settings = bench_home(root, bench)
    if bench.get('chatgpt_tunnel_bench') is not True or bench['client'] != 'chatgpt' or bench['credential'] != 'chatgpt.json':
        raise ValueError('Only a dedicated ChatGPT synthetic bench may be recorded')
    return bench, home, settings


def mandate(root, grant):
    bench, home, _ = checked(root)
    original = json.loads((home/'access-policy.json').read_text(encoding='utf-8'))
    document = deepcopy(original)
    document['version'] = 'chatgpt-discovery-'+uuid.uuid4().hex
    subject = document['subjects'][bench['subject']]
    for action in ('admit', 'activate'):
        if grant: subject[action] = ['example.claims']
        else: subject.pop(action, None)
    policy(root, document, 'discovery-'+('grant' if grant else 'revoke'))
    bench['events'].append({'action': 'grant-discovery' if grant else 'revoke-discovery', 'at': time.time()})
    save(root, bench)
    return {'discovery_mandate': grant}


class Recorder:
    """Capture exact JSON messages after redaction, capped at 64 MiB per session."""
    def __init__(self, stream, credential):
        self.stream, self.credential, self.size = stream, credential, 0

    def record(self, direction, message):
        token = json.loads(self.credential.read_text(encoding='utf-8'))['access_token']
        entry = {'at': time.time(), 'direction': direction, 'message': redact(message, token)}
        encoded = (json.dumps(entry, ensure_ascii=False)+'\n').encode('utf-8')
        if self.size + len(encoded) > 64 * 1024 * 1024:
            raise ValueError('Private receipt budget exceeded')
        self.stream.write(encoded); self.stream.flush(); self.size += len(encoded)


class RecordedInput:
    def __init__(self, stream, recorder): self.stream, self.recorder = stream, recorder
    def readline(self, limit):
        line = self.stream.readline(limit)
        if line:
            try: message = parse(line)
            except ValueError: message = {'malformed_input': True}
            self.recorder.record('in', message)
        return line


class RecordedOutput:
    def __init__(self, stream, recorder): self.stream, self.recorder = stream, recorder
    def write(self, line):
        self.recorder.record('out', json.loads(line))
        return self.stream.write(line)
    def flush(self): self.stream.flush()


def record_server(root):
    bench, home, _ = checked(root)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    folder = root/'private-protocol'
    protect_directory(folder)
    path = folder/(uuid.uuid4().hex+'.jsonl')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(path, flags, 0o600), 'wb') as stream:
        recorder = Recorder(stream, home/bench['credential'])
        api = APIClient(home, bench['credential'], bench['port'])
        # auto discovers the current authority, and every call rechecks it.
        return serve(RecordedInput(sys.stdin.buffer, recorder), RecordedOutput(sys.stdout, recorder), api, access='auto')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('action', choices=['prepare', 'serve', 'grant-discovery', 'revoke-discovery',
        'start-server', 'stop-server', 'expire-token', 'rotate-token', 'restrict-policy', 'restore-policy', 'drain-jobs', 'inspect'])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == 'prepare': result = prepare_chatgpt(root)
    elif args.action == 'serve': raise SystemExit(record_server(root))
    elif args.action in ('grant-discovery', 'revoke-discovery'): result = mandate(root, args.action == 'grant-discovery')
    else:
        checked(root)
        result = act(root, args.action)
    print(json.dumps(result, ensure_ascii=False))
