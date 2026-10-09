"""Explicit policy diagnostics for fictional SAV, workshop and IAM dossiers."""
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
from air.core import GOVERNANCE_PROFILE, digest
from air.policy_check import check_policy
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/state-replay.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-policy-' + uuid.uuid4().hex)
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
            scope = domain['body']['scope'];owner = 'urn:asteria:governance-owner:' + code.lower()
            def obj(kind, suffix, body):
                meta = deepcopy(domain['meta']);meta.update(id='urn:asteria:governance:' + code.lower() + ':' + suffix, type='air.' + kind, revision=1, name=case['title'] + ' - ' + suffix)
                return {'meta': meta, 'body': body}
            ref = lambda suffix: {'id': 'urn:asteria:governance:' + code.lower() + ':' + suffix, 'revision': 1}
            def expr(ast, inputs=None): return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': ast, 'required_inputs': inputs or []}
            if code == 'D02':
                name = 'measurement_age';typ = 'Quantity[second]';ast = {'op': 'lte', 'args': [{'ref': name}, {'literal': {'type': typ, 'value': '300'}}]}
                good = {'type': typ, 'value': '120'};bad = {'type': typ, 'value': '540'};expected = 'VIOLATED'
            else:
                name = 'erp_confirmed' if code == 'D01' else 'identity_consistent';typ = 'Boolean';ast = {'ref': name}
                good = {'type': typ, 'value': True};expected = 'UNKNOWN' if code == 'D01' else 'CONFLICTING';bad = {'type': typ, 'state': expected}
            source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': 'urn:asteria:fictional-procedure:' + code.lower(), 'captured_at': '2026-09-20T00:00:00Z',
                'access_policy': 'Équipe du dossier fictif', 'retention_policy': 'Conserver les versions pour la démonstration'})
            constraint = obj('Constraint', 'constraint', {'mode': 'hard', 'scope': scope, 'condition': expr(ast, [{'name': name, 'type': typ}]),
                'source': [exact(source)], 'exception_policy': 'Une déclaration de dérogation ne suffit pas ; mandat et vérification distincts requis', 'verification': [ref('constraint-case')]})
            control = obj('Control', 'control', {'objective': 'Prévenir une action à partir d’une entrée non fiable', 'mechanism': 'Revue indépendante de l’entrée et de sa provenance',
                'scope': scope, 'owner': owner, 'verification': [ref('control-case')], 'evidence_requirements': ['Provenance exacte', 'Revue indépendante à jour']})
            cases = [obj('VerificationCase', suffix, {'target': exact(target), 'method': 'REVIEW', 'inputs': [], 'oracle': 'Contrôle indépendant établi',
                'acceptance': 'Preuves et mandat valides', 'independence_basis': 'Autre acteur habilité ; réception non exécutée dans cette démonstration'})
                for suffix, target in [('constraint-case', constraint), ('control-case', control)]]
            decision = obj('Decision', 'decision', {'question': 'Proposer une dérogation temporaire ?', 'alternatives': ['Refuser', 'Proposer pour revue'], 'selection': 'Proposer pour revue',
                'rationale': 'Exercice fictif ; aucun mandat effectif établi', 'basis': [exact(source)], 'authority': owner,
                'consequences': ['Les contrôles bloquants restent applicables'], 'revisit_conditions': ['Revue indépendante ou échéance atteinte']})
            applicability = obj('Decision', 'applicability', {'question': 'La procédure concerne-t-elle ce dossier ?', 'alternatives': ['Applicable', 'Non applicable'], 'selection': 'Applicable',
                'rationale': 'Périmètre fictif explicitement couvert', 'basis': [exact(source)], 'authority': owner, 'consequences': ['Contrôles requis'], 'revisit_conditions': ['Changement de périmètre']})
            obligation = obj('Obligation', 'obligation', {'source_text': exact(source), 'interpretation': 'Exiger une entrée qualifiée avant l’action proposée',
                'applicability_decision': exact(applicability), 'controls': [exact(control)], 'review_due': '2026-10-20T00:00:00Z'})
            policy = obj('Policy', 'policy', {'intent': 'Maîtriser les entrées de ' + case['title'], 'issuer': owner,
                'applicability': expr({'literal': {'type': 'Boolean', 'value': True}}), 'constraints': [exact(constraint)], 'review_policy': 'Revue indépendante de chaque changement'})
            risk = obj('Risk', 'risk', {'scenario': 'Déclencher une action sur une entrée manquante, périmée ou contradictoire', 'causes': [exact(constraint)],
                'consequences': ['Action incorrecte', 'Reprise manuelle'], 'assessment_method': 'Analyse qualitative déclarée', 'treatment': [exact(control)], 'residual_assessment': 'À qualifier par une revue réelle'})
            waiver = obj('Waiver', 'waiver', {'rule': exact(constraint), 'permitted_basis': 'Proposition fictive pour instruction', 'scope': scope, 'expires_at': '2026-10-20T00:00:00Z',
                'approval': exact(decision), 'compensating_controls': [exact(control)]})
            additions = [source, constraint, control, *cases, decision, applicability, obligation, policy, risk, waiver]
            imported = client('air_import_drafts', {'objects': additions});assert 'error' not in imported, imported
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:governance-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': GOVERNANCE_PROFILE, 'members': [exact(o) for o in objects + additions], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base, base
            assert len(base['baseline']['body']['members']) == 80
            pin = {**exact(base['baseline']), 'digest': base['digest']};runs = []
            for label, value, outcome in [('nominal', good, 'SATISFIED'), ('exception-with-declared-waiver', bad, expected)]:
                request = {'baseline': pin, 'policy': {**exact(policy), 'digest': digest(policy)}, 'as_of': '2026-10-06T12:00:00Z', 'applicability_inputs': {},
                    'constraint_inputs': [{'constraint': {**exact(constraint), 'digest': digest(constraint)}, 'inputs': {name: value}}]}
                result = client('air_check_policy', request);assert 'error' not in result, result
                assert result['outcome'] == outcome and result['blocking_constraints'] == (0 if label == 'nominal' else 1), result
                assert not result['waiver_applied'] and not result['authorization_granted'] and not result['business_verification_granted']
                assert len(result['waivers']) == 1 and not result['waivers'][0]['applied']
                request_file = workspace / (code + '-' + label + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
                cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'policy-check', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
                assert cli.returncode == 0, cli.stderr
                assert json.loads(cli.stdout) == result
                session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'policy-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_check_policy', 'arguments': request}})['result']['structuredContent'] == result
                runs.append({'case': label, 'expected': {'outcome': outcome}, 'request': request, 'report': result})
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': pin, 'scenarios': runs})
        denied = APIClient(home, 'observer-D01.json', port)('air_check_policy', reports[2]['scenarios'][0]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            for validation in case['scenarios']:
                assert check_policy(store, actor, AccessPolicy.load(settings.home), validation['request']) == validation['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': GOVERNANCE_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_diagnostics_identical': True, 'prior_baselines_preserved': True,
        'business_scenarios_executed': False, 'external_actions_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/policies.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
