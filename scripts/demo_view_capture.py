"""Capture six exact views across three fictional dossiers, then recover their bytes."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__, artifacts, view_capture
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/audience.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-view-capture-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    def cli(command, file, code, *options):
        result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(file), '--credential', 'architect-' + code + '.json', '--port', str(port), *options], capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    reports = [];expected_bytes = {}
    start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port);views = []
            for source_view in case['views']:
                audience = source_view['audience'];request = {'id': 'urn:asteria:captured-view:' + code.lower() + ':' + audience,
                    'revision': 1, 'name': ('Métier' if audience == 'business' else 'Ingénierie') + ' — ' + case['title'],
                    **source_view['request'], 'idempotency_key': 'capture-' + code + '-' + audience}
                request_file = workspace / (code + '-' + audience + '-request.json');request_file.write_text(json.dumps(request), encoding='utf-8')
                result = cli('view-capture', request_file, code);assert result['created']
                replay = cli('view-capture', request_file, code);assert not replay['created']
                assert {k: v for k, v in replay.items() if k != 'created'} == {k: v for k, v in result.items() if k != 'created'}
                pin = {**exact(result['view']['object']), 'digest': result['view']['digest']};lookup = {'view': pin}
                lookup_file = workspace / (code + '-' + audience + '-lookup.json');lookup_file.write_text(json.dumps(lookup), encoding='utf-8')
                checked = cli('view-read', lookup_file, code)
                assert checked == {k: v for k, v in result.items() if k != 'created'}
                session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'capture-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_read_captured_view', 'arguments': lookup}})['result']['structuredContent'] == checked
                files = {}
                for field, extension in [('output', '.html'), ('source_mapping', '.json')]:
                    artifact_lookup = workspace / (code + '-' + audience + '-' + field + '-lookup.json')
                    artifact_lookup.write_text(json.dumps({'artifact': result[field]['artifact']}), encoding='utf-8')
                    destination = workspace / (code + '-' + audience + '-' + field + extension)
                    downloaded = cli('artifact-download', artifact_lookup, code, '--output', str(destination))
                    assert downloaded['source_context_required']
                    data = destination.read_bytes();expected_bytes[(code, audience, field)] = data;files[field] = str(destination)
                original = Path(source_view['path']).resolve();assert original.is_relative_to((ROOT / 'tmp').resolve())
                assert expected_bytes[(code, audience, 'output')] == original.read_bytes()
                mapping = json.loads(expected_bytes[(code, audience, 'source_mapping')])
                assert mapping['source_mapping'] == source_view['report']['source_mapping'] and mapping['context_mapping'] == source_view['report']['context_mapping']
                assert client('air_export_baseline', case['baseline'])['digest'] == case['baseline']['digest']
                views.append({'audience': audience, 'request': request, 'pin': pin, 'result': checked, 'files': files,
                    'prior_render_bytes_identical': True, 'cli_mcp_identical': True})
            reports.append({'case': code, 'title': case['title'], 'source_baseline': case['baseline'], 'views': views})
        outsider = APIClient(home, 'observer-D01.json', port)
        target = reports[2]['views'][0]
        assert outsider('air_read_captured_view', {'view': target['pin']})['http_status'] == 403
        assert outsider('air_describe_artifact', {'artifact': target['result']['output']['artifact']})['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'};policy = AccessPolicy.load(settings.home)
            for view in case['views']:
                assert view_capture.read(store, actor, policy, {'view': view['pin']}) == view['result']
                for field in ('output', 'source_mapping'):
                    assert artifacts.download(store, actor, policy, {'artifact': view['result'][field]['artifact']})[1] == expected_bytes[(case['case'], view['audience'], field)]
        with store.engine.connect() as conn: artifacts.verify_artifacts(store, conn);view_capture.verify_views(store, conn)
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'home': str(home), 'treatments': reports, 'captured_views': 6,
        'cross_dossier_view_and_artifact_refused': True, 'restored_products_and_bytes_identical': True, 'prior_baselines_preserved': True,
        'external_action_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/view-capture.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'views': result['captured_views'], 'report': str(output)}))
