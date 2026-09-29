"""Declared operating workflows on the three fictional organizational dossiers."""
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
from air.core import WORKFLOW_PROFILE
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.workflow import inspect_workflow
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/organization.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-workflow-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    specifics = {
        'D01': ('Préparer la réclamation et sa revue', 'Confirmation ERP disponible', 'Aucune confirmation client en l’absence de confirmation ERP'),
        'D02': ('Préparer l’inspection et sa revue', 'Mesure disponible avec sa date', 'Une mesure trop ancienne impose une nouvelle préparation'),
        'D03': ('Préparer la révocation et sa revue', 'Sources IAM rapprochées', 'Des sources contradictoires imposent une nouvelle préparation'),
    }
    reports = [];start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            objects = old['objects'];function = next(o for o in objects if o['meta']['type'] == 'air.Function')
            actor = next(o for o in objects if o['meta']['type'] == 'air.Actor' and not o['body']['roles'])
            coordinator = next(o for o in objects if o['meta']['type'] == 'air.Actor' and o['body']['roles'])
            unit = next(o for o in objects if o['meta']['type'] == 'air.OrganizationUnit' and o['meta']['namespace'] != 'asteria.shared')
            role = next(o for o in objects if o['meta']['type'] == 'air.Role')
            authority = next(o for o in objects if o['meta']['type'] == 'air.AuthorityScope')
            service = next(o for o in objects if o['meta']['type'] == 'air.BusinessService')
            verification = [exact(o) for o in objects if o['meta']['type'] == 'air.VerificationCase']
            title, condition, rule_text = specifics[code]
            def obj(kind, suffix, name, body):
                meta = deepcopy(unit['meta']);meta.update(id='urn:asteria:workflow:' + code.lower() + ':' + suffix, type='air.' + kind, revision=1, name=name)
                return {'meta': meta, 'body': body}
            review = obj('Function', 'review', 'Revoir le dossier de préparation', {'kind': 'HUMAN', 'inputs': [], 'outputs': [], 'preconditions': ['Dossier préparé et accessible au relecteur'],
                'postconditions': ['Observation de revue enregistrée sans autorisation métier implicite'], 'effects': [], 'exceptions': [], 'atomic': False, 'satisfies': function['body']['satisfies']})
            workflow = obj('Workflow', 'workflow', title, {'steps': [
                {'binding': 'air.workflow-step/0.22', 'id': 'prepare', 'name': function['meta']['name'], 'function': exact(function), 'participants': [exact(actor)]},
                {'binding': 'air.workflow-step/0.22', 'id': 'review', 'name': 'Revue de préparation', 'function': exact(review), 'participants': [exact(coordinator)]}],
                'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'to-review', 'source': 'prepare', 'target': 'review', 'condition': condition}],
                'start_steps': ['prepare'], 'termination_policy': 'Proposition revue et exception conservée ; toute action réelle dépend d’une autorisation distincte', 'compensations': []})
            if code != 'D01': workflow['body']['flows'].append({'binding': 'air.workflow-flow/0.22', 'id': 'rework', 'source': 'review', 'target': 'prepare', 'condition': rule_text})
            updated_unit = deepcopy(unit);updated_unit['meta']['revision'] += 1
            operating = obj('OperatingModel', 'operating', 'Modèle opératoire — ' + case['title'], {'services': [exact(service)], 'responsibility_map': [exact(role), exact(updated_unit)],
                'workflows': [exact(workflow)], 'resource_policies': [exact(authority)]})
            updated_unit['body']['operating_model'] = exact(operating)
            rule = obj('BusinessRule', 'rule', 'Règle de préparation — ' + case['title'], {'statement': rule_text,
                'applicability': 'Avant toute décision de lancement sur ce dossier', 'authority': authority['body']['principal'], 'verification': verification})
            additions = [review, workflow, operating, rule, updated_unit]
            assert 'error' not in client('air_import_drafts', {'objects': additions})
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:workflow-baseline:' + code.lower(), revision=1)
            members = [o for o in objects if o['meta']['id'] != unit['meta']['id']] + additions
            base = client('air_freeze_baseline', {'meta': meta, 'profile': WORKFLOW_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base and len(base['baseline']['body']['members']) == 62
            request = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}}
            report = client('air_inspect_workflow', request);assert 'error' not in report
            request_file = workspace / (code + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
            cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'workflow-inspect', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert cli.returncode == 0, cli.stderr
            assert json.loads(cli.stdout) == report
            session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'workflow-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_inspect_workflow', 'arguments': request}})['result']['structuredContent'] == report
            assert report['workflows'][0]['structure']['cycle_detected'] == (code != 'D01')
            assert not report['functions_executed'] and not report['rules_evaluated'] and not report['authorization_granted']
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': request['baseline'], 'report': report})
        denied = APIClient(home, 'observer-D01.json', port)('air_inspect_workflow', {'baseline': reports[2]['baseline']})
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            assert inspect_workflow(store, actor, AccessPolicy.load(settings.home), {'baseline': case['baseline']}) == case['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': WORKFLOW_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_reports_identical': True, 'prior_baselines_preserved': True,
        'functions_executed': False, 'business_scenarios_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/workflow.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
