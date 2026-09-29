"""Local schema validation of fictional SAV, workshop and IAM payload artifacts."""
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
from air.core import DATA_PROFILE, digest
from air.data_validation import validate_payload
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/workflow.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-data-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    particulars = {
        'D01': ('Réclamation SAV proposée', 'claim_id', 'order_id', 'requested_amount', 'Decimal', '0.1', 'SAV-2026-0142', 'ORDER-8401'),
        'D02': ('Inspection industrielle proposée', 'inspection_id', 'machine_id', 'temperature', 'Decimal', '87.35', 'INSP-2026-031', 'PRESS-12'),
        'D03': ('Révocation IAM proposée', 'request_id', 'identity_id', 'access_count', 'Integer', '1.0', 'IAM-2026-089', 'EMP-042'),
    }
    reports = [];start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            objects = old['objects'];domain = next(o for o in objects if o['meta']['type'] == 'air.Domain')
            authority = next(o for o in objects if o['meta']['type'] == 'air.AuthorityScope')
            contract = next(o for o in objects if o['meta']['type'] == 'air.SemanticContract')
            title, id_field, context_field, number_field, number_type, value, identifier, context_id = particulars[code]
            namespace = domain['meta']['namespace']
            def upload(suffix, data):
                result = client('air_import_artifact', {'namespace': namespace, 'media_type': 'application/json', 'idempotency_key': code + '-' + suffix,
                    'content_base64': base64.b64encode(data).decode('ascii')})
                assert 'error' not in result, result
                return result
            schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'additionalProperties': False,
                'properties': {id_field: {'type': 'string', 'minLength': 1}, context_field: {'type': 'string', 'minLength': 1},
                    'occurred_at': {'type': 'string', 'format': 'date-time'}, number_field: {'type': 'integer' if number_type == 'Integer' else 'number', 'minimum': 0}},
                'required': [id_field, context_field, 'occurred_at', number_field]}
            schema_artifact = upload('schema', json.dumps(schema).encode())
            raw = ('{' + json.dumps(id_field) + ':' + json.dumps(identifier) + ',' + json.dumps(context_field) + ':' + json.dumps(context_id)
                   + ',"occurred_at":"2026-09-20T08:00:00Z",' + json.dumps(number_field) + ':' + value + '}').encode()
            good = upload('valid-payload', raw);bad_payload = json.loads(raw)
            if code == 'D01': del bad_payload[id_field]
            elif code == 'D02': bad_payload[number_field] = 'hot'
            else: bad_payload['unexpected_privilege'] = 'admin'
            bad = upload('invalid-payload', json.dumps(bad_payload).encode())
            field = lambda name: {'binding': 'air.field/0.23', 'name': name}
            def obj(kind, suffix, body):
                meta = deepcopy(domain['meta']);meta.update(id='urn:asteria:data:' + code.lower() + ':' + suffix, type='air.' + kind, revision=1, name=title + ' — ' + suffix)
                return {'meta': meta, 'body': body}
            concept = obj('Concept', 'concept', {'definition': title, 'domain': exact(domain), 'semantic_relations': [], 'steward': authority['body']['principal']})
            owner = obj('DataAuthority', 'authority', {'data_scope': domain['body']['scope'], 'operations': ['Préparer une proposition', 'Corriger une proposition sous revue'],
                'responsible': authority['body']['principal'], 'writer_policy': 'Équipe du dossier ; déclaration sans droit serveur implicite', 'coordination_policy': 'Révision exacte et revue indépendante avant tout effet externe'})
            entity = obj('DataEntity', 'entity', {'concept': exact(concept), 'ownership': exact(owner), 'identity': [field(id_field)], 'constraints': [],
                'attributes': [{'binding': 'air.attribute/0.23', 'name': name, 'value_type': kind, 'required': True, 'description': 'Champ fictif ' + name}
                    for name, kind in [(id_field, 'Text'), (context_field, 'Text'), ('occurred_at', 'Instant'), (number_field, number_type)]]})
            data_schema = obj('DataSchema', 'schema', {'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': schema_artifact['artifact_reference'],
                'represents': [exact(entity)], 'compatibility_policy': 'Revue explicite pour tout changement de champ ou de sens'})
            message = obj('Message', 'message', {'schema': exact(data_schema), 'meaning': title, 'classification': {'level': 'INTERNAL'},
                'correlation_keys': [field(context_field)], 'idempotency_key': field(id_field)})
            event = obj('Event', 'event', {'semantic_meaning': title, 'payload_schema': exact(data_schema), 'occurrence_time': field('occurred_at'),
                'correlation': [field(context_field)], 'delivery_contract': exact(contract)})
            additions = [concept, owner, entity, data_schema, message, event]
            assert 'error' not in client('air_import_drafts', {'objects': additions})
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:data-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': DATA_PROFILE, 'members': [exact(o) for o in objects + additions], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in base and len(base['baseline']['body']['members']) == 68
            pin = {**exact(base['baseline']), 'digest': base['digest']};runs = []
            for label, subject, artifact, expected in [('valid-message', message, good, 'SATISFIED'), ('invalid-message', message, bad, 'VIOLATED'), ('valid-event-shape', event, good, 'SATISFIED')]:
                request = {'baseline': pin, 'subject': {**exact(subject), 'digest': digest(subject)}, 'payload_artifact': artifact['artifact']}
                result = client('air_validate_data', request);assert 'error' not in result
                assert result['payload_validation'] == expected and not result['event_truth_verified'] and not result['authorization_granted']
                request_file = workspace / (code + '-' + label + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
                cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'data-validate', str(request_file), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
                assert cli.returncode == 0, cli.stderr
                assert json.loads(cli.stdout) == result
                session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'data-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_validate_data', 'arguments': request}})['result']['structuredContent'] == result
                runs.append({'case': label, 'request': request, 'report': result})
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': pin, 'validations': runs})
        denied = APIClient(home, 'observer-D01.json', port)('air_validate_data', reports[2]['validations'][0]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            for validation in case['validations']:
                assert validate_payload(store, actor, AccessPolicy.load(settings.home), validation['request']) == validation['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': DATA_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_validations_identical': True, 'prior_baselines_preserved': True,
        'business_scenarios_executed': False, 'event_truth_verified': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/data.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
