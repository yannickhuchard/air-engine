"""Exact architecture structure for fictional SAV, workshop and IAM dossiers."""
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
from air.core import ARCHITECTURE_PROFILE, digest
from air.architecture import inspect_architecture
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/policies.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-architecture-' + uuid.uuid4().hex)
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
            objects = old['objects'];find = lambda kind: next(o for o in objects if o['meta']['type'] == 'air.' + kind)
            domain, contract, schema, entity, control = [find(kind) for kind in ('Domain', 'SemanticContract', 'DataSchema', 'DataEntity', 'Control')]
            criterion, unit = find('AcceptanceCriterion'), find('ConstructionUnit')
            function = contract['body']['operations'][0]['function'];operation = contract['body']['operations'][0]['name']
            def obj(kind, suffix, body):
                meta = deepcopy(domain['meta']);meta.update(id='urn:asteria:architecture:' + code.lower() + ':' + suffix, type='air.' + kind, revision=1, name=case['title'] + ' — ' + suffix)
                return {'meta': meta, 'body': body}
            provider = obj('ArchitectureBlock', 'provider', {'kind': 'MODULE', 'responsibilities': ['Recevoir les propositions', 'Conserver la traçabilité'],
                'functions': [function], 'provided_contracts': [exact(contract)], 'required_contracts': [], 'owned_state': [exact(entity)]})
            consumer = obj('ArchitectureBlock', 'consumer', {'kind': 'ADAPTER' if code == 'D02' else 'GATEWAY', 'responsibilities': ['Préparer et transmettre les propositions'],
                'functions': [function], 'provided_contracts': [], 'required_contracts': [exact(contract)], 'owned_state': []})
            route = {'D01': '/claims', 'D02': '/inspections', 'D03': '/access-revocation-proposals'}[code]
            binding = obj('TechnicalBinding', 'binding', {'contract': exact(contract), 'protocol': 'HTTP', 'protocol_version': '1.1',
                'endpoint_template': 'https://' + code.lower() + '.asteria.invalid', 'security_binding': [exact(control)],
                'schema_mapping': [{'binding': 'air.http-json-mapping/0.26', 'operation': operation, 'method': 'POST', 'path': route,
                    'request_schema': exact(schema), 'request_required': True, 'response_schema': exact(schema), 'response_status': '202'}]})
            provided = obj('Port', 'provided', {'block': exact(provider), 'direction': 'PROVIDED', 'contract': exact(contract), 'bindings': [exact(binding)]})
            required = obj('Port', 'required', {'block': exact(consumer), 'direction': 'REQUIRED', 'contract': exact(contract), 'bindings': [exact(binding)]})
            flow = obj('DataFlow', 'request-flow', {'source': exact(required), 'destination': exact(provided), 'schema': exact(schema),
                'purpose': 'Transmettre une proposition fictive pour revue', 'transformations': [], 'controls': [exact(control)]})
            output = obj('RequiredOutput', 'output', {'expected_artifact': 'Adaptateur HTTP implémenté et vérifié', 'acceptance': [exact(criterion)], 'construction_unit': exact(unit), 'due_gate': 'construction-review'})
            gap = obj('ArchitectureGap', 'gap', {'missing_element_kind': 'Implémentation et qualification du binding', 'affected_scope': domain['body']['scope'],
                'impact': 'Aucun endpoint métier fourni par cette démonstration', 'resolution_owner': 'urn:asteria:architecture-owner:' + code.lower(), 'required_output': exact(output)})
            additions = [provider, consumer, binding, provided, required, flow, output, gap]
            imported = client('air_import_drafts', {'objects': additions});assert 'error' not in imported, imported
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:architecture-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in objects + additions], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base, base
            assert len(base['baseline']['body']['members']) == 88
            pin = {**exact(base['baseline']), 'digest': base['digest']};request = {'baseline': pin}
            result = client('air_inspect_architecture', request);assert 'error' not in result, result
            assert len(result['blocks']) == 2 and len(result['ports']) == 2 and len(result['flows']) == 1 and len(result['gaps']) == 1
            assert result['bindings'][0]['operation_coverage']['mapped'] == [operation]
            assert not result['endpoints_contacted'] and not result['security_verified'] and not result['outputs_constructed']
            request_file = workspace / (code + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
            cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'architecture-inspect', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert cli.returncode == 0, cli.stderr
            assert json.loads(cli.stdout) == result
            session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'architecture-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_inspect_architecture', 'arguments': request}})['result']['structuredContent'] == result
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': pin, 'request': request, 'report': result})
        denied = APIClient(home, 'observer-D01.json', port)('air_inspect_architecture', reports[2]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            assert inspect_architecture(store, actor, AccessPolicy.load(settings.home), case['request']) == case['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': ARCHITECTURE_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_reports_identical': True, 'prior_baselines_preserved': True,
        'business_scenarios_executed': False, 'external_actions_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/architecture.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
