"""Retain and recover the bytes of three explicitly fictional dossier documents."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__, artifacts
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.core import KNOWLEDGE_PROFILE
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    source = json.loads((ROOT / 'tmp/demo-asteria/knowledge.json').read_text(encoding='utf-8'))
    original_home = Path(source['workbench_home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-artifacts-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in source['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case']
                write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    def cli(command, file, code, *extra, success=True):
        result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(file), '--credential', 'architect-' + code + '.json', '--port', str(port), *extra], capture_output=True, text=True, encoding='utf-8', timeout=45)
        assert (result.returncode == 0) == success, result.stderr
        return json.loads(result.stdout) if success else result
    results = [];contents = {}
    start(sys.executable, home, port)
    try:
        for case in source['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            baseline = client('air_export_baseline', case['baseline']);assert 'error' not in baseline
            original = next(o for o in baseline['objects'] if o['meta']['id'] == 'urn:asteria:knowledge:' + code.lower() + ':source')
            content = json.dumps({'classification': 'FICTIONAL_DEMONSTRATION', 'case': code, 'title': case['title'],
                'declared_statements': [o['body']['statement'] for o in baseline['objects'] if o['meta']['id'].startswith('urn:asteria:knowledge:' + code.lower() + ':statement-')],
                'limitations': ['Authored fictional dossier; no independent observation or evidence qualification.'], 'binary_attachment_version': 1}, ensure_ascii=False, indent=2).encode('utf-8')
            document = workspace / (code + '.json');document.write_bytes(content);contents[code] = content
            options = ['--namespace', original['meta']['namespace'], '--media-type', 'application/json', '--idempotency-key', 'demo-' + code]
            uploaded = cli('artifact-upload', document, code, *options)
            replay = cli('artifact-upload', document, code, *options)
            assert uploaded['created'] and not replay['created'] and uploaded['artifact'] == replay['artifact']
            lookup = {'artifact': uploaded['artifact']};request_file = workspace / (code + '-lookup.json')
            request_file.write_text(json.dumps(lookup), encoding='utf-8')
            output = workspace / (code + '-download.json');downloaded = cli('artifact-download', request_file, code, '--output', str(output))
            assert output.read_bytes() == content and downloaded['content_digest'] == uploaded['content_digest']
            cli('artifact-download', request_file, code, '--output', str(output), success=False)
            assert output.read_bytes() == content
            session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'artifact-demo', 'version': '1'}}})
            session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            mcp = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_read_artifact', 'arguments': lookup}})['result']
            assert not mcp['isError'] and base64.b64decode(mcp['structuredContent']['content_base64']) == content
            # This new Source is a retained authored document, not an independent supporting observation.
            retained = deepcopy(original);retained['meta'].update(id='urn:asteria:artifact-source:' + code.lower(), name='Pièce jointe conservée — ' + case['title'])
            retained['meta']['provenance']['source_refs'] = [exact(original)]
            retained['meta']['provenance']['method'] = 'Authored fictional summary retained as bytes; not independent evidence'
            retained['body'].update(locator=uploaded['artifact']['id'], source_revision=uploaded['content_digest'])
            assert 'error' not in client('air_import_drafts', {'objects': [retained]})
            meta = deepcopy(baseline['baseline']['meta']);meta.update(id='urn:asteria:artifact-baseline:' + code.lower(), revision=1)
            final = client('air_freeze_baseline', {'meta': meta, 'profile': KNOWLEDGE_PROFILE, 'members': [exact(o) for o in baseline['objects'] + [retained]], 'parent_baselines': [exact(baseline['baseline'])]})
            assert len(final['baseline']['body']['members']) == 49
            assert client('air_export_baseline', case['baseline'])['digest'] == baseline['digest']
            results.append({'case': code, 'title': case['title'], 'artifact': uploaded, 'source': exact(retained),
                'baseline': {**exact(final['baseline']), 'digest': final['digest']}, 'original_baseline': case['baseline'],
                'cli_replay_identical': True, 'download_bytes_identical': True, 'existing_file_preserved': True, 'mcp_bytes_identical': True})
        denied = APIClient(home, 'observer-D01.json', port)('air_read_artifact', {'artifact': results[2]['artifact']['artifact']})
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in results:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            restored, data = artifacts.download(store, actor, AccessPolicy.load(settings.home), {'artifact': case['artifact']['artifact']})
            assert data == contents[case['case']] and restored['artifact'] == case['artifact']['artifact']
            assert store.export_baseline(case['baseline'])['digest'] == case['baseline']['digest']
        with store.engine.connect() as conn: artifacts.verify_artifacts(store, conn)
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'home': str(home), 'treatments': results,
        'cross_dossier_refused': True, 'restored_bytes_and_baselines_identical': True, 'prior_baselines_preserved': True,
        'evidence_qualified': False, 'external_action_executed': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/artifacts.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
