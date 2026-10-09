"""Declared teams and responsibilities for three fictional Asteria dossiers."""
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
from air.core import ORGANIZATION_PROFILE, digest
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.organization import inspect_organization
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/audience.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-organization-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        shared = json.loads((ROOT / 'examples/scope.json').read_text(encoding='utf-8'))
        shared['meta'].update(id='urn:asteria:organization:architecture', type='air.OrganizationUnit', name='Direction architecture Astéria', namespace='asteria.shared')
        shared['meta']['provenance'].update(source_refs=[], method='Fictional organization charter')
        shared['body'] = {'mandate': 'Maintenir les conventions et coordonner les revues d’architecture transverses', 'roles': []}
        store.put(shared, 'fictional-charter')
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    teams = {
        'D01': ('Applications et intégration SAV', 'Contrats ERP et parcours de réclamation', 'Aucun engagement de délai client sans confirmation ERP'),
        'D02': ('Atelier et systèmes industriels', 'Fraîcheur des mesures et inspections', 'Aucune commande machine ni contournement de sécurité'),
        'D03': ('IAM et sécurité', 'Traçabilité des habilitations et révocations', 'Aucune révocation sur sources contradictoires'),
    }
    reports = [];start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            scope = next(o for o in old['objects'] if o['meta']['type'] == 'air.Scope' and o['meta']['namespace'] != 'asteria.shared')
            team_name, responsibility, limit = teams[code]
            def obj(kind, suffix, name, body):
                meta = deepcopy(scope['meta']);meta.update(id='urn:asteria:organization:' + code.lower() + ':' + suffix, type='air.' + kind, revision=1, name=name)
                return {'meta': meta, 'body': body}
            authority = obj('AuthorityScope', 'authority', 'Périmètre déclaré - ' + team_name, {'principal': 'urn:asteria:team:' + code.lower() + ':engineering', 'scope': exact(scope),
                'allowed_decisions': ['Proposer le contrat de conception', 'Documenter les écarts et préparer une revue'], 'limits': [limit, 'Aucun mandat d’admission ou d’activation créé par cette déclaration'],
                'delegations': [], 'separation_rules': ['La revue de réception exige un acteur indépendant']})
            role = obj('Role', 'role', 'Architecte référent - ' + team_name, {'responsibilities': [responsibility, 'Conserver les hypothèses, inconnues et décisions'],
                'required_competencies': [{'binding': 'air.skill-requirement/0.21', 'competency': responsibility, 'minimum_level': 'Praticien autonome', 'assessment_method': 'Revue de dossier par un pair habilité'}], 'authority': exact(authority)})
            unit = obj('OrganizationUnit', 'unit', team_name, {'mandate': responsibility, 'parent': exact(shared), 'roles': [exact(role)]})
            domain = obj('Domain', 'domain', 'Domaine - ' + case['title'], {'purpose': responsibility, 'scope': exact(scope), 'authority': exact(authority)})
            actor = obj('Actor', 'coordinator', 'Référent de coordination - ' + team_name, {'kind': 'HUMAN', 'boundary': exact(scope), 'roles': [exact(role)]})
            additions = [authority, role, unit, domain, actor]
            assert 'error' not in client('air_import_drafts', {'objects': additions})
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:organization-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': ORGANIZATION_PROFILE, 'members': [exact(o) for o in old['objects'] + [shared] + additions], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base and len(base['baseline']['body']['members']) == 58
            request = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}}
            report = client('air_inspect_organization', request);assert 'error' not in report
            request_file = workspace / (code + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
            cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'organization-inspect', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert cli.returncode == 0, cli.stderr
            assert json.loads(cli.stdout) == report
            session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'organization-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_inspect_organization', 'arguments': request}})['result']['structuredContent'] == report
            assert len(report['units']) == 2 and len(report['roles']) == len(report['domains']) == len(report['authorities']) == 1
            assert not report['authorization_granted'] and not report['policy_updated']
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': request['baseline'], 'report': report})
        denied = APIClient(home, 'observer-D01.json', port)('air_inspect_organization', {'baseline': reports[2]['baseline']})
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            assert inspect_organization(store, actor, AccessPolicy.load(settings.home), {'baseline': case['baseline']}) == case['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': ORGANIZATION_PROFILE, 'home': str(home), 'treatments': reports,
        'shared_organization': {**exact(shared), 'digest': digest(shared)}, 'cross_dossier_refused': True, 'cli_mcp_identical': True,
        'restored_reports_identical': True, 'prior_baselines_preserved': True, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/organization.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
