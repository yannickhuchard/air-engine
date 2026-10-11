"""Isolated finite-design counterexamples and evidence impact through CLI and MCP."""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from air import __version__, artifacts, deliverables, evidence_impact
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files
from air.cli import bootstrap
from air.config import Settings
from air.core import BUILD_PROFILE, STATE_PROFILE, reference_slots
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_demo', ROOT / 'fixtures/build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated SQLite demo')
    output.mkdir(parents=True, exist_ok=False)
    home = output / '.air'; bootstrap(home); settings = Settings.load(home); store = Store(settings.database_url)
    credential = json.loads((home / 'credentials.json').read_text(encoding='utf-8'))
    user = store.authenticate(credential['access_token'], True); user['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy(); server = None; log = None
    env = dict(os.environ); env['PYTHONUTF8'] = '1'; env.pop('AIR_DATABASE_URL', None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        descriptors = {n: artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
            'media_type': 'application/json', 'idempotency_key': n}, (model.ROOT / (n + '.schema.json')).read_bytes())['artifact_reference'] for n in ('request', 'response')}
        objects = model.objects(descriptors); store.put_bundle(objects, user['subject'])
        def freeze(objects, name, revision=1, parents=None, profile=BUILD_PROFILE):
            meta = model.obj('Baseline', name, {})['meta']; meta['revision'] = revision
            frozen = store.create_baseline({'meta': meta, 'profile': profile,
                'members': [exact(o) for o in objects], 'parent_baselines': parents or []}, user['subject'])
            return {**exact(frozen['baseline']), 'digest': frozen['digest']}
        origin = freeze(objects, 'baseline')
        # Transition proposes a state prohibited by an explicit invariant. Effects stay declarative.
        state_expr = model.expression(model.call('ne', model.var('air_state'), model.lit('Text', 'MOVING')),
            [{'name': 'air_state', 'type': 'Text'}])
        machine = model.obj('StateMachine', 'machine', {'initial_state': 'STOPPED', 'states': [
            {'binding': 'air.state-spec/0.24', 'id': n, 'name': n, 'terminal': n == 'MOVING'} for n in ('STOPPED', 'MOVING')],
            'invariants': [state_expr], 'transitions': [{'binding': 'air.transition/0.24', 'id': 'depart', 'source': 'STOPPED',
                'target': 'MOVING', 'trigger': 'go', 'guard': model.expression(model.lit('Boolean', True), []),
                'effects': [{'kind': 'HUMAN_ACTION', 'description': 'Declared departure; never performed by AIR'}]}]})
        scope = next(o for o in objects if o['meta']['type'] == 'air.Scope')
        store.put(machine, user['subject']); state_pin = freeze([scope, machine], 'states', profile=STATE_PROFILE)
        changed = deepcopy(objects); changed_case = next(o for o in changed if o['meta']['type'] == 'air.VerificationCase')
        changed_case['meta']['revision'] = 2; changed_case['body']['oracle'] += ' Revoir les limites avec le fournisseur.'
        again = True
        while again:
            again = False; revisions = {o['meta']['id']: o['meta']['revision'] for o in changed}
            for obj in changed:
                for _, ref, _ in reference_slots(obj):
                    if ref['id'] in revisions and ref['revision'] != revisions[ref['id']]:
                        ref['revision'] = revisions[ref['id']]; obj['meta']['revision'] = 2; again = True
        store.put_bundle(changed, user['subject']); current = freeze(changed, 'baseline', 2, [exact(store.get(origin['id'], 1)['object'])])
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
                if server.poll() is not None or time.monotonic() > deadline: raise RuntimeError('Isolated API did not start')
                time.sleep(.1)
        requests = []
        def cli(command, request):
            path = output / ('request-' + command + '.json'); path.write_text(json.dumps(request), encoding='utf-8')
            run = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(path), '--port', str(port)],
                capture_output=True, text=True, encoding='utf-8', env=env, timeout=180, creationflags=flags)
            if run.returncode: raise RuntimeError('CLI failed: ' + command)
            result = json.loads(run.stdout); requests.append((command, request, result)); return result
        search = {'baseline': state_pin, 'machine': evidence_impact.pin(machine), 'initial_context': {},
            'alphabet': [{'trigger': 'go', 'context': {}}], 'max_depth': 2, 'max_trials': 64}
        state_report = cli('behavior-states', search)
        assert state_report['counterexamples'][0]['sequence'] == [0]
        assert state_report['counterexamples'][0]['report']['outcome'] == 'INVARIANT_VIOLATED'
        interface = {'baseline': origin, 'specification': evidence_impact.pin(model.specification()), 'operation': 'Quote',
            'exchanges': [{'request': {'quantity': 2}, 'response': {'quantity': 2, 'total_minor': 251, 'currency': 'EUR'}, 'expected': 'PASS'},
                {'request': {'quantity': 0}, 'expected': 'FAIL'}, {'request': {'quantity': 2}, 'expected': 'PASS'}]}
        contract_report = cli('behavior-interfaces', interface)
        assert len(contract_report['counterexamples']) == 1 and len(contract_report['inconclusive']) == 1
        impact_report = cli('evidence-impact', {'before': origin, 'after': current})
        assert impact_report['summary']['IMPACTED'] > 0 and not impact_report['proofs_automatically_carried']
        client = APIClient(home, 'credentials.json', port=port); session = Session(client)
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'AIR local recipe', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        names = dict(zip(('behavior-states', 'behavior-interfaces', 'evidence-impact'),
            ('air_search_state_counterexamples', 'air_search_interface_counterexamples', 'air_assess_evidence_impact')))
        for i, (command, request, expected) in enumerate(requests):
            answer = session.handle({'jsonrpc': '2.0', 'id': i + 2, 'method': 'tools/call', 'params': {'name': names[command], 'arguments': request}})
            observed = json.loads(answer['result']['content'][0]['text'])
            assert observed == expected
        pack = deliverables.compile_deliverables(store, user, policy, {'title': 'Contre-exemples et évolution du design',
            'baselines': [current], 'website': True, 'content': 'FULL'})
        apply_files(output / 'workspace', pack['files'], plan_files(output / 'workspace', pack['files']))
        result = {'version': __version__, 'status': 'PASS_SCOPED', 'scope': 'Fictional design inputs, no runtime or independent opinion',
            'cli_commands': [r[0] for r in requests], 'mcp_equal_to_cli': True,
            'state_counterexamples': len(state_report['counterexamples']), 'state_report_digest': state_report['report_digest'],
            'interface_counterexamples': len(contract_report['counterexamples']), 'interface_unknowns': len(contract_report['inconclusive']),
            'impact_summary': impact_report['summary'], 'impact_report_digest': impact_report['report_digest'],
            'site_files': len(pack['files']), 'runtime_executed': False, 'authorization_granted': False}
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
