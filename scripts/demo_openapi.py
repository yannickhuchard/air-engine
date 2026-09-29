"""Compile exact OpenAPI design descriptions for the three fictional Asteria dossiers."""
import base64
import hashlib
from jsonschema import Draft202012Validator, FormatChecker
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
from air.openapi_compiler import compile_openapi
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/architecture.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-openapi-' + uuid.uuid4().hex)
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
    official_schema = json.loads((ROOT / 'tests/fixtures/openapi-3.1-schema-2022-10-07.json').read_text(encoding='utf-8'))
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            binding = next(o for o in old['objects'] if o['meta']['type'] == 'air.TechnicalBinding')
            request = {'baseline': case['baseline'], 'binding': {**exact(binding), 'digest': digest(binding)}, 'info': {'title': case['title'], 'version': 'draft-1'}}
            result = client('air_compile_openapi', request);assert 'error' not in result, result
            content = result['content'].encode('utf-8');document = json.loads(content)
            Draft202012Validator(official_schema, format_checker=FormatChecker()).validate(document)
            assert 'sha256:' + hashlib.sha256(content).hexdigest() == result['content_digest'] and len(content) == result['size']
            assert not result['endpoints_contacted'] and not result['security_verified'] and not result['behavior_implemented']
            assert {'SECURITY_NOT_TRANSLATED', 'BEHAVIOR_NOT_IMPLEMENTED', 'ERROR_CONTRACT_NOT_MAPPED'} <= {loss['code'] for loss in result['losses']}
            request_file = workspace / (code + '.json');request_file.write_text(json.dumps(request), encoding='utf-8');output = workspace / (code + '.openapi.json')
            command = [sys.executable, '-m', 'air', '--home', str(home), 'openapi-compile', str(request_file), '--output', str(output), '--credential', 'architect-' + code + '.json', '--port', str(port)]
            cli = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert cli.returncode == 0, cli.stderr
            cli_result = json.loads(cli.stdout);cli_result.pop('output');assert cli_result == {k: v for k, v in result.items() if k != 'content'}
            assert output.read_bytes() == content
            duplicate = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert duplicate.returncode != 0 and output.read_bytes() == content
            session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'openapi-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_compile_openapi', 'arguments': request}})['result']['structuredContent'] == result
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': case['baseline'], 'request': request, 'report': result, 'output': str(output)})
        denied = APIClient(home, 'observer-D01.json', port)('air_compile_openapi', reports[2]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            assert compile_openapi(store, actor, AccessPolicy.load(settings.home), case['request']) == case['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_reports_identical': True, 'prior_baselines_preserved': True,
        'existing_outputs_preserved': True, 'official_openapi_schema_validation': True,
        'business_scenarios_executed': False, 'external_actions_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/openapi.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
