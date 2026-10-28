"""Fictional scoped delivery recipe over real local HTTP, CLI and MCP. No CI runs."""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from air import __version__, artifacts, deliverables, portable_session
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import BUILD_PROFILE
from air.foundation import exact
from air.mcp import Session, APIClient, PROTOCOL
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assurance_recipe', ROOT / 'fixtures/delivery_assurance/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stakeholders', action='store_true', help='Include the fictional stakeholder map recipe')
    args = parser.parse_args(); output = args.output.resolve()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for this isolated demonstration')
    output.mkdir(parents=True, exist_ok=False)
    home = output / '.air'; bootstrap(home); settings = Settings.load(home); store = Store(settings.database_url)
    c = store.create_token('urn:identity:delivery-demo:architect', 'admin')
    write_private(home / 'demonstration.json', c)
    user = store.authenticate(c['access_token'], True); user['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy.load(home); server = None; log = None
    env = dict(os.environ); env['PYTHONUTF8'] = '1'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        descriptors = {n: artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
            'media_type': 'application/json', 'idempotency_key': n}, (model.model.ROOT / (n + '.schema.json')).read_bytes())['artifact_reference'] for n in ('request', 'response')}
        ci = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE, 'media_type': 'application/json', 'idempotency_key': 'fixture-ci'},
            b'{"fixture":true,"result":"PASS","not_an_actual_pipeline_run":true}')['artifact_reference']
        objects = model.objects(descriptors, ci, user['subject'])
        if args.stakeholders:
            spec = importlib.util.spec_from_file_location('stakeholder_recipe', ROOT / 'fixtures/stakeholders/model.py')
            people = importlib.util.module_from_spec(spec); spec.loader.exec_module(people)
            objects += people.additions()
        store.put_bundle(objects, user['subject'])
        b = store.create_baseline({'meta': model.model.obj('Baseline', 'assurance-baseline', {})['meta'], 'profile': BUILD_PROFILE,
            'members': [exact(o) for o in objects], 'parent_baselines': []}, user['subject'])
        p = {**exact(b['baseline']), 'digest': b['digest']}
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log = (output / 'server.log').open('w', encoding='utf-8')
        server = subprocess.Popen([sys.executable, '-m', 'air', '--home', str(home), 'serve', '--port', str(port)], stdout=log, stderr=log, env=env, creationflags=flags)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as r: assert json.load(r)['status'] == 'ok'
                break
            except Exception:
                if server.poll() is not None or time.monotonic() > deadline: raise RuntimeError('Isolated API failed to start')
                time.sleep(.1)
        session = Session(APIClient(home, 'demonstration.json', port=port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'Scoped delivery recipe', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        calls = []
        def call(command, name, request, extra=()):
            f = output / ('request-' + str(len(calls)) + '.json'); f.write_text(json.dumps(request), encoding='utf-8')
            cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(f), '--port', str(port), '--credential', 'demonstration.json', *extra],
                capture_output=True, text=True, encoding='utf-8', timeout=180, env=env, creationflags=flags)
            if cli.returncode: raise RuntimeError(command + ': ' + cli.stderr[-800:])
            cli_result = json.loads(cli.stdout)
            result = session.handle({'jsonrpc': '2.0', 'id': len(calls) + 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': request}})
            observed = json.loads(result['result']['content'][0]['text'])
            if 'error' in observed: raise RuntimeError(str(observed))
            if command == 'checklist-export':
                assert Path(cli_result['output']).read_bytes() == base64.b64decode(observed['content_base64'])
            elif command != 'session-export': assert cli_result == observed
            (output / ('result-' + str(len(calls)) + '.json')).write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding='utf-8')
            calls.append({'cli': command, 'mcp': name, 'request_file': f.name, 'cli_mcp_equal': True})
            return observed
        g = call('scope-gates', 'air_assess_scope_gates', {'baseline': p})
        states = {r['name']: r['result'] for r in g['gates']}
        assert states == {'common': 'PASS_SCOPED_GATE', 'my-help': 'PASS_SCOPED_GATE', 'my-health': 'BLOCKED'}
        stakeholder_map = call('stakeholders-map', 'air_stakeholders_map', {'baseline': p}) if args.stakeholders else None
        coverage = call('traceability-coverage', 'air_traceability_coverage', {'baseline': p})
        assert coverage['totals']['covered'] == 1
        work = call('delivery-dashboard', 'air_delivery_dashboard', {'baselines': [p], 'as_of': '2026-10-19', 'team': 'urn:team:platform', 'week': '2026-W42', 'late': True, 'blocked': True})
        assert work['total_matching'] == 1
        for fmt in ('CSV', 'XLSX'):
            call('checklist-export', 'air_export_checklist', {'baseline': p, 'as_of': '2026-10-19', 'format': fmt}, ['--output', str(output / ('checklist.' + fmt.lower()))])
        portable = call('session-export', 'air_export_portable_session', {'baseline': p}, ['--workspace', str(output / 'portable'), '--apply'])
        s = json.loads((output / 'portable/session.json').read_text(encoding='utf-8'))
        checked = subprocess.run([sys.executable, '-m', 'air', 'session-check', str(output / 'portable/session.json')], capture_output=True, text=True, encoding='utf-8', env=env)
        assert checked.returncode == 0 and json.loads(checked.stdout)['readiness'] == 'UNKNOWN'
        assert len(s['attachments']) == 3
        pack = deliverables.compile_deliverables(store, user, policy, {'title': 'Projet d’architecture : recette de livraison fictive', 'baselines': [p], 'content': 'FULL'})
        workspace = output / 'workspace'
        apply_files(workspace, pack['files'], plan_files(workspace, pack['files']))
        result = {'engine_version': __version__, 'result': 'PASS_SCOPED', 'fictional_recipe': True,
            'baseline': p, 'gates': states, 'coverage': coverage['totals'], 'filtered_tasks': work['total_matching'], 'stakeholders': stakeholder_map['counts'] if stakeholder_map else None,
            'commands': calls, 'portable_artifacts': len(s['attachments']), 'offline_validation': json.loads(checked.stdout),
            'business_runtime_executed': False, 'ci_executed': False, 'native_chatgpt_qualified': False,
            'independent_review_inferred': False, 'real_dossier_audit_performed': False}
        (output / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=10)
        if log: log.close()
        store.engine.dispose()


if __name__ == '__main__': main()
