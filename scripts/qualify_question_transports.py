"""Exercise real loopback HTTP and stdio MCP on a fresh fictional Asteria demo.

Uses Python alone. This is protocol reception, not native assistant reception or
participant research. Credentials stay in an owned protected demo home and are
revoked in finally; architecture objects and baselines are never changed.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from air.client_contract import catalogue, compare
from air.config import Settings, write_private
from air.mcp import PROTOCOL
from air.storage import Store
from install import start, stop

ROOT = Path(__file__).resolve().parents[1]


def message(method, params=None, request_id=1):
    value = {'jsonrpc': '2.0', 'id': request_id, 'method': method}
    if params is not None:
        value['params'] = params
    return value


def call(name, arguments, request_id):
    return message('tools/call', {'name': name, 'arguments': arguments}, request_id)


def initialize():
    return message('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
        'clientInfo': {'name': 'air-local-transport-reception', 'version': '1'}})


def result(response):
    if 'error' in response:
        raise AssertionError('Unexpected MCP protocol error')
    value = response['result']
    if value.get('isError'):
        raise AssertionError('Unexpected AIR refusal')
    return value.get('structuredContent', value)


def stdio(home, credential, port, messages):
    # The credential file name, never its bytes, is passed to the adapter.
    command = [sys.executable, '-m', 'air.mcp', '--home', str(home),
               '--credential', credential, '--port', str(port), '--access', 'auto']
    run = subprocess.run(command, input=''.join(json.dumps(m) + '\n' for m in messages),
        capture_output=True, text=True, encoding='utf-8', timeout=120, cwd=ROOT,
        env=dict(os.environ, PYTHONUTF8='1'))
    if run.returncode:
        raise AssertionError('Owned stdio adapter failed; raw output remains unpublished')
    responses = [json.loads(line) for line in run.stdout.splitlines()]
    if [r['id'] for r in responses] != [m['id'] for m in messages]:
        raise AssertionError('MCP responses do not match the requested sequence')
    return responses


def qualify(demo_file):
    if os.environ.get('AIR_DATABASE_URL'):
        raise ValueError('Unset AIR_DATABASE_URL for isolated reception')
    run = demo_file.resolve().parent
    if not run.is_relative_to((ROOT / 'tmp').resolve()):
        raise ValueError('Reception must use a workspace tmp demo')
    demo = json.loads(demo_file.read_text(encoding='utf-8'))
    site = Path(demo['entrypoint']).resolve().parent
    homes = list(run.glob('registry-*'))
    if not site.is_relative_to(run) or len(homes) != 1 or homes[0].is_symlink():
        raise ValueError('Use a fresh isolated demo with one owned registry')
    home = homes[0].resolve()
    if not home.is_relative_to(run):
        raise ValueError('Registry is outside the demo')
    dossiers = demo['site']['dossiers']
    if len(dossiers) != 3 or {d['namespace'] for d in dossiers} != {
            'asteria.sav', 'asteria.atelier', 'asteria.identites'}:
        raise ValueError('Only the three fictional Asteria dossiers are supported')
    owned_files = ['config.json', 'access-policy.json', 'server.json',
                   'transport-reader-0.json', 'transport-reader-1.json', 'transport-reader-2.json']
    if any((home / name).exists() for name in owned_files) or (run / 'transport-report.json').exists():
        raise ValueError('Reception never replaces an existing configuration or receipt')
    config = {'config_version': 1, 'database_backend': 'sqlite',
              'instance_id': str(uuid.uuid4()), 'auth': {'mode': 'local'}}
    write_private(home / 'config.json', config)
    settings = Settings.load(home)
    store = Store(settings.database_url)
    store.check_version()
    before = store.counts()
    tokens, checks, started = [], [], False
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    opener = build_opener(ProxyHandler({}))

    def http(body, token=None):
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL}
        if token:
            headers['Authorization'] = 'Bearer ' + token['access_token']
        request = Request(f'http://127.0.0.1:{port}/mcp', data=json.dumps(body).encode(), headers=headers)
        try:
            with opener.open(request, timeout=120) as reply:
                return reply.status, json.loads(reply.read(16 * 1024 * 1024))
        except HTTPError as exc:
            if exc.code != 401:
                raise AssertionError('Unexpected MCP HTTP status') from None
            return exc.code, None

    try:
        subjects = {}
        for i, d in enumerate(dossiers):
            token = store.create_token('transport-reception:' + d['namespace'], 'reader')
            tokens.append(token)
            write_private(home / f'transport-reader-{i}.json', token)
            subjects[token['subject']] = {'read': [d['namespace'], 'asteria.shared']}
        write_private(home / 'access-policy.json', {'version': 'ux-transport-reception/1', 'subjects': subjects})
        start(Path(sys.executable), home, port, no_worker=True)
        started = True
        assert http(initialize())[0] == 401
        for i, (d, token) in enumerate(zip(dossiers, tokens)):
            folder = (site / d['path']).resolve().parent
            if not folder.is_relative_to(site):
                raise ValueError('Dossier is outside its site')
            files = sorted(folder.glob('question-*.json'))
            if len(files) != 37:
                raise ValueError('Each dossier must contain 37 generated capsules')
            requests = [json.loads(file.read_text(encoding='utf-8')) for file in files]
            sequence = [initialize(), message('tools/list', request_id=2),
                        call('air_whoami', {}, 3),
                        call('air_get', {k: d['baseline'][k] for k in ('id', 'revision')}, 4)]
            sequence += [call('air_resume_question', request, 10 + j) for j, request in enumerate(requests)]
            stdio_first = stdio(home, f'transport-reader-{i}.json', port, sequence)
            identity = result(stdio_first[2])['identity']
            observed = result(stdio_first[3])
            assert observed['digest'] == d['baseline']['digest']
            comparison = compare({'tools': [{k: t[k] for k in ('name', 'inputSchema')}
                for t in result(stdio_first[1])['tools']], 'expected_baseline': d['baseline'],
                'observed_baseline': {'id': observed['object']['meta']['id'],
                    'revision': observed['object']['meta']['revision'], 'digest': observed['digest']}}, 'read')
            # Auto discovery includes owned calculation jobs for a reader. The
            # fixed read profile intentionally omits them. Preserve that genuine
            # difference instead of treating every role/profile count as a cache.
            assert comparison['baseline_context'] == 'MATCH'
            assert not comparison['missing_tools'] and not comparison['different_schemas']
            assert comparison['extra_tools'] == ['air_cancel_job', 'air_submit_job']
            supported = {t['name']: t['inputSchema'] for t in catalogue('all')}
            assert all(t['inputSchema'] == supported[t['name']]
                       for t in result(stdio_first[1])['tools'])
            for body, expected in zip(sequence, stdio_first):
                status, actual = http(body, token)
                assert status == 200 and actual == expected
            receipts = [result(r)['receipt'] for r in stdio_first[4:]]
            resumed = [initialize()] + [call('air_resume_question', {**request, 'previous_receipt': receipt}, 10 + j)
                for j, (request, receipt) in enumerate(zip(requests, receipts))]
            stdio_second = stdio(home, f'transport-reader-{i}.json', port, resumed)
            for j, (body, response) in enumerate(zip(resumed[1:], stdio_second[1:])):
                assert result(response) == result(stdio_first[4 + j])
                assert http(body, token)[1] == response
                assert receipts[j]['identity'] == identity and receipts[j]['baseline'] == d['baseline']
            refusals = []
            for other in dossiers:
                if other['namespace'] != d['namespace']:
                    refusals.append(call('air_get', {k: other['baseline'][k] for k in ('id', 'revision')}, 100 + len(refusals)))
            changed_identity = deepcopy(receipts[0]);changed_identity['identity'] = 'urn:air:identity:another-fixture'
            refusals.append(call('air_resume_question', {**requests[0], 'previous_receipt': changed_identity}, 102))
            tampered = deepcopy(requests[0]);tampered['capsule']['question']['text'] += ' changed'
            refusals.append(call('air_resume_question', tampered, 103))
            refused = stdio(home, f'transport-reader-{i}.json', port, [initialize()] + refusals)[1:]
            for body, response in zip(refusals, refused):
                actual = http(body, token)[1]
                assert response['result']['isError'] and actual['result']['isError']
                # The API deliberately omits exception prose for Forbidden;
                # direct HTTP MCP may retain it. Verify refusal semantics.
                left, right = (r['result']['structuredContent'] for r in (response, actual))
                assert (left['error'], left['http_status']) == (right['error'], right['http_status'])
            assert all(r['result']['structuredContent']['http_status'] == 403 for r in refused[:2])
            checks.append({'namespace': d['namespace'], 'baseline': d['baseline'], 'capsules': len(files),
                'catalogue': comparison, 'observed_auto_tools': len(result(stdio_first[1])['tools']),
                'auto_profile_difference': 'OWNED_CALCULATION_JOBS_ALLOWED_BY_READ_ACTION',
                'all_observed_schemas_match_current_supported_tools': True,
                'fresh_stdio_resumptions': len(receipts),
                'http_stdio_results_identical': True, 'cross_namespace_reads_refused': 2,
                'refusal_codes_and_statuses_match': True,
                'changed_identity_and_tampered_capsule_refused': True})
        assert store.counts() == before
    finally:
        try:
            if started:
                stop(home)
        finally:
            for token in tokens:
                store.revoke_token(token['token_id'])
                assert store.authenticate(token['access_token']) is None
            store.engine.dispose()
    report = {'format': 'air.question-transport-reception/1', 'status': 'PASS_SCOPED',
        'transports': ['REAL_LOOPBACK_HTTP_MCP', 'REAL_STDIO_ADAPTER_TO_HTTP_API'],
        'protocol': PROTOCOL, 'unauthenticated_http_refused': True,
        'architecture_revisions_written': False, 'test_credentials_revoked': True,
        'owned_server_stopped': True, 'native_assistant_exercised': False,
        'participant_sessions': 0, 'checks': checks}
    (run / 'transport-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', type=Path)
    report = qualify(parser.parse_args().demo)
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}))
