"""Receive contextual omissions and two independent fictional HTTP prototypes.

All registry and server state is isolated in a fresh output directory. Nothing
is deployed and no external business system or supplier is contacted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from air import __version__, artifacts, completeness, interface_contracts, deliverables
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files
from air.cli import bootstrap
from air.config import Settings
from air.core import BUILD_PROFILE, digest
from air.foundation import exact
from air.storage import Store

spec = importlib.util.spec_from_file_location('build_fixture', ROOT / 'fixtures/build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)


def command(args, **kwargs):
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding='utf-8', timeout=120, **kwargs)
    if result.returncode: raise RuntimeError('Prototype/CLI command failed: ' + result.stderr[-800:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    if os.environ.get('AIR_DATABASE_URL'):
        raise ValueError('Run this isolated SQLite demonstration without AIR_DATABASE_URL')
    output.mkdir(parents=True, exist_ok=False)
    home = output / '.air'; bootstrap(home)
    settings = Settings.load(home); store = Store(settings.database_url)
    credential = json.loads((home / 'credentials.json').read_text(encoding='utf-8'))
    user = store.authenticate(credential['access_token'], True); user['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy(); processes = []
    environment = dict(os.environ); environment['PYTHONUTF8'] = '1'
    # Keep the fixture on SQLite regardless of an optional developer test URL.
    environment.pop('AIR_DATABASE_URL', None)
    try:
        descriptors = {name: artifacts.put(store, user, policy, settings,
            {'namespace': model.NAMESPACE, 'media_type': 'application/json', 'idempotency_key': name},
            (model.ROOT / (name + '.schema.json')).read_bytes())['artifact_reference'] for name in ('request', 'response')}
        objects = model.objects(descriptors); store.put_bundle(objects, user['subject'])
        baseline = store.create_baseline({'meta': model.obj('Baseline', 'baseline', {})['meta'], 'profile': BUILD_PROFILE,
            'members': [exact(o) for o in objects], 'parent_baselines': []}, user['subject'])
        pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
        specification = model.specification()
        request = {'baseline': pin, 'specification': {**exact(specification), 'digest': digest(specification)}}
        before = store.counts()
        context = completeness.assess(store, user, policy, {'baseline': pin})
        suite = interface_contracts.compile_suite(store, user, policy, request)
        assert suite['result'] == 'PASS_DESIGN_EXAMPLES'
        gap = deepcopy(objects[-2]); gap['body']['profiles'] = ['PHYSICAL_SYSTEM', 'REGULATED_ACTIVITY']
        preview = completeness.project({'baseline': baseline['baseline'], 'digest': baseline['digest'], 'objects': [gap]})
        expected_missing = {'PHYSICAL_SYSTEM.EQUIPMENT', 'REGULATED_ACTIVITY.OBLIGATIONS', 'COMMON.BUDGET'}
        assert expected_missing <= {c['id'] for c in preview['checks'] if c['status'] == 'NOT_DOCUMENTED'}
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        provider = subprocess.Popen([sys.executable, str(model.ROOT / 'provider.py'), '--http'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', env=environment, creationflags=flags)
        processes.append(provider)
        with ThreadPoolExecutor(max_workers=1) as executor:
            try: first = executor.submit(provider.stdout.readline).result(timeout=10)
            except TimeoutError:
                provider.terminate(); provider.wait(timeout=10)
                raise RuntimeError('Prototype startup timed out') from None
        url = 'http://127.0.0.1:' + str(json.loads(first)['port'])
        inputs = [{'quantity': q, 'key': 'quote-' + str(q)} for q in range(1, 101)] + [
            {'quantity': 2, 'key': 'quote-2'}, {'quantity': 3, 'key': 'quote-2'},
            {'quantity': 0, 'key': 'invalid-zero'}, {'quantity': 101, 'key': 'invalid-high'},
            {'quantity': True, 'key': 'invalid-bool'}, {'quantity': '2', 'key': 'invalid-text'}]
        exchanged = command([str(model.ROOT / 'consumer.py'), '--http-url', url], input=''.join(json.dumps(i) + '\n' for i in inputs), env=environment)
        exchanges = [json.loads(line) for line in exchanged.splitlines()]
        assert len(exchanges) == len(inputs)
        for i, exchange in enumerate(exchanges):
            expected = 200 if i <= 100 else 409 if i == 101 else 422
            assert exchange['response']['status'] == expected
            if expected == 200:
                assert exchange['interpretation']['accepted']
                assert interface_contracts.verify_exchange(specification['body'], 'Quote', exchange['request']['body'], exchange['response']['body'])['result'] == 'PASS'
            elif expected == 422:
                assert interface_contracts.verify_exchange(specification['body'], 'Quote', exchange['request']['body'])['result'] == 'FAIL'
        assert exchanges[1]['response'] == exchanges[100]['response']
        # Exercise the actual CLI adapter and application, on this isolated registry.
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log = (output / 'private-server.log').open('wb')
        server = subprocess.Popen([sys.executable, '-m', 'air', '--home', str(home), 'serve', '--port', str(port), '--no-worker'],
            stdout=log, stderr=log, env=environment, creationflags=flags)
        processes.append(server)
        deadline = time.monotonic() + 60
        while True:
            try:
                with urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=1) as health: assert health.status == 200
                break
            except OSError:
                if server.poll() is not None: raise RuntimeError('Isolated AIR server exited before health check')
                if time.monotonic() > deadline: raise RuntimeError('Isolated AIR server did not start')
                time.sleep(.1)
                time.sleep(.1)
        (output / 'suite-request.json').write_text(json.dumps(request), encoding='utf-8')
        (output / 'context-request.json').write_text(json.dumps({'baseline': pin}), encoding='utf-8')
        args = ['-m', 'air', '--home', str(home)]
        raw = command([*args, 'interface-suite', str(output / 'suite-request.json'), '--workspace', str(output / 'contract'), '--apply', '--port', str(port)], env=environment)
        cli = json.loads(raw); assert cli['result'] == 'PASS_DESIGN_EXAMPLES'
        command([str(output / 'contract/verify.py')], env=environment)
        cli_context = json.loads(command([*args, 'completeness-assess', str(output / 'context-request.json'), '--port', str(port)], env=environment))
        assert cli_context == context
        verify_request = {**request, 'operation': 'Quote', 'request': {'quantity': 2}, 'response': {'quantity': 2, 'total_minor': 251, 'currency': 'EUR'}}
        (output / 'exchange-request.json').write_text(json.dumps(verify_request), encoding='utf-8')
        verified = json.loads(command([*args, 'interface-verify', str(output / 'exchange-request.json'), '--port', str(port)], env=environment))
        assert verified['result'] == 'FAIL'
        site = deliverables.compile_deliverables(store, user, policy, {'baselines': [pin], 'title': 'Asteria : contrats de référence', 'content': 'FULL'})
        apply_files(output / 'project', site['files'], plan_files(output / 'project', site['files']))
        assert store.counts() == before
        report = {'status': 'PASS_SCOPED', 'version': __version__, 'baseline': pin, 'specification': request['specification'],
            'contract_examples': suite['result'], 'http_exchanges': len(exchanges), 'valid_exchanges': 101,
            'invalid_requests_rejected': 4, 'duplicate_replay': True, 'different_payload_key_conflict': True,
            'counterexample_detected': True, 'context_absent_dimensions_detected': sorted(expected_missing),
            'cli_suite_applied_and_verified': True, 'cli_context_matches_service': True, 'cli_counterexample_detected': True,
            'source_digests': {name: 'sha256:' + hashlib.sha256((model.ROOT / name).read_bytes()).hexdigest() for name in ('provider.py', 'consumer.py', 'request.schema.json', 'response.schema.json')},
            'site_files': len(site['files']), 'site_dossier': site['website']['dossiers'][0], 'registry_unchanged_by_checks': True,
            'scope': 'INDEPENDENT_FICTIONAL_PROTOTYPES_AND_DECLARED_DESIGN', 'real_teams_validated': False,
            'business_service_deployed': False, 'security_window_concurrency_timing_verified': False, 'ci_executed': False}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    finally:
        for process in reversed(processes):
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        store.engine.dispose()
        if 'log' in locals(): log.close()
    print(json.dumps({'status': report['status'], 'http_exchanges': report['http_exchanges'], 'site_files': report['site_files']}))


if __name__ == '__main__': main()
