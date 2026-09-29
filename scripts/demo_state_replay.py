"""Illustrative state replays for fictional SAV, workshop and IAM dossiers."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.core import STATE_PROFILE, digest
from air.state_replay import replay
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/data.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-state-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]

    reports = [];start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            objects = old['objects'];domain = next(o for o in objects if o['meta']['type'] == 'air.Domain')
            def expr(ast, inputs):
                return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': ast, 'required_inputs': [{'name': name, 'type': typ} for name, typ in inputs]}
            def lit(typ, value): return {'literal': {'type': typ, 'value': value}}
            if code == 'D02':
                name = 'measurement_age';typ = 'Quantity[second]'
                condition = {'op': 'lte', 'args': [{'ref': name}, lit(typ, '300')]}
                good = {'type': typ, 'value': '120'};bad = {'type': typ, 'value': '540'}
                exception_outcome, exception_state = 'INPUT_EXHAUSTED', 'WAITING'
            else:
                name = 'erp_confirmed' if code == 'D01' else 'identity_consistent';typ = 'Boolean'
                condition = {'ref': name};good = {'type': typ, 'value': True}
                bad = {'type': typ, 'state': 'UNKNOWN' if code == 'D01' else 'CONFLICTING'}
                exception_outcome, exception_state = ('UNKNOWN' if code == 'D01' else 'CONFLICTING'), 'PENDING'
            guard = expr(condition, [(name, typ)])
            negated = expr({'op': 'not', 'args': [deepcopy(condition)]}, [(name, typ)])
            invariant = expr({'op': 'or', 'args': [{'op': 'ne', 'args': [{'ref': 'air_state'}, lit('Text', 'READY')]}, {'ref': 'independent_review'}]}, [('air_state', 'Text'), ('independent_review', 'Boolean')])
            transitions = []
            for source in ('PENDING', 'WAITING'):
                for target, predicate in [('READY', guard), ('WAITING', negated)]:
                    transitions.append({'binding': 'air.transition/0.24', 'id': source.lower() + '_to_' + target.lower(), 'source': source, 'target': target,
                        'trigger': 'check', 'guard': deepcopy(predicate), 'effects': [{'kind': 'HUMAN_ACTION', 'description': 'Revue indépendante proposée ; aucune action ERP, machine ou IAM exécutée'}]})
            meta = deepcopy(domain['meta']);meta.update(id='urn:asteria:state-machine:' + code.lower(), type='air.StateMachine', revision=1, name='Contrôle illustratif — ' + case['title'])
            machine = {'meta': meta, 'body': {'states': [{'binding': 'air.state-spec/0.24', 'id': name, 'name': name, 'terminal': name == 'READY'} for name in ('PENDING', 'WAITING', 'READY')],
                'initial_state': 'PENDING', 'transitions': transitions, 'invariants': [invariant]}}
            imported = client('air_import_drafts', {'objects': [machine]});assert 'error' not in imported, imported
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:state-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': STATE_PROFILE, 'members': [exact(o) for o in objects + [machine]], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base, base
            assert len(base['baseline']['body']['members']) == 69
            pin = {**exact(base['baseline']), 'digest': base['digest']};runs = []
            scenarios = [('nominal', good, True, 'TERMINAL_REACHED', 'READY'), ('exception', bad, True, exception_outcome, exception_state), ('review-refused', good, False, 'INVARIANT_VIOLATED', 'PENDING')]
            for label, value, reviewed, outcome, final_state in scenarios:
                request = {'baseline': pin, 'machine': {**exact(machine), 'digest': digest(machine)}, 'initial_context': {},
                    'stimuli': [{'trigger': 'check', 'context': {name: value, 'independent_review': {'type': 'Boolean', 'value': reviewed}}}]}
                result = client('air_replay_state_machine', request);assert 'error' not in result, result
                assert result['outcome'] == outcome and result['final_state'] == final_state, result
                assert not result['external_actions_executed'] and not result['business_verification_granted'] and not result['authorization_granted']
                if label == 'review-refused':
                    assert result['trace'][0]['proposed_target'] == 'READY' and not result['trace'][0]['transition_applied']
                request_file = workspace / (code + '-' + label + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
                cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'state-replay', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
                assert cli.returncode == 0, cli.stderr
                assert json.loads(cli.stdout) == result
                session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'state-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_replay_state_machine', 'arguments': request}})['result']['structuredContent'] == result
                runs.append({'case': label, 'expected': {'outcome': outcome, 'final_state': final_state}, 'request': request, 'report': result})
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': pin, 'scenarios': runs})
        denied = APIClient(home, 'observer-D01.json', port)('air_replay_state_machine', reports[2]['scenarios'][0]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            for validation in case['scenarios']:
                assert replay(store, actor, AccessPolicy.load(settings.home), validation['request']) == validation['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': STATE_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_replays_identical': True, 'prior_baselines_preserved': True,
        'business_scenarios_executed': False, 'external_actions_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/state-replay.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
