"""Two declared audience views for each of the three fictional Asteria dossiers."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.audience import compile_view
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.core import AUDIENCE_PROFILE, digest
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/artifacts.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-audience-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    output = ROOT / 'tmp/demo-asteria/audience';output.mkdir(parents=True, exist_ok=True)
    groups = {
        'business': [('outcomes', 'Intentions et objectifs', ['air.Intent', 'air.Goal', 'air.Metric']),
            ('services', 'Capacités et services', ['air.Capability', 'air.BusinessService', 'air.Product']),
            ('decisions', 'Décisions et incertitudes', ['air.Decision', 'air.Conflict', 'air.Unknown'])],
        'engineering': [('construction', 'Contrats et construction', ['air.Requirement', 'air.AcceptanceCriterion', 'air.Function', 'air.SemanticContract', 'air.ConstructionUnit', 'air.VerificationCase']),
            ('observations', 'Observations et écarts', ['air.RuntimeObservation', 'air.Drift', 'air.Incident']),
            ('knowledge', 'Hypothèses et désaccords', ['air.Assumption', 'air.Unknown', 'air.Inference', 'air.Conflict', 'air.Decision'])],
    }
    reports = []
    start(sys.executable, home, port)
    try:
        for case in previous['treatments']:
            code = case['case'];client = APIClient(home, 'architect-' + code + '.json', port)
            old = client('air_export_baseline', case['baseline']);assert 'error' not in old
            stakeholder = next(o for o in old['objects'] if o['meta']['type'] == 'air.Stakeholder')
            concern = next(o for o in old['objects'] if o['meta']['type'] == 'air.Concern')
            engineering = deepcopy(stakeholder)
            engineering['meta'].update(id='urn:asteria:audience-stakeholder:' + code.lower() + ':engineering', name={'D01': 'Équipe applications et intégration', 'D02': 'Équipe atelier et systèmes industriels', 'D03': 'Équipe IAM et sécurité'}[code])
            engineering['body'].update(identity_or_group='urn:asteria:team:' + code.lower() + ':engineering', participation_role='Conception et réalisation technique')
            viewpoints = []
            for audience, sections in groups.items():
                label = 'Métier' if audience == 'business' else 'Ingénierie'
                meta = deepcopy(concern['meta']);meta.update(id='urn:asteria:viewpoint:' + code.lower() + ':' + audience,
                    type='air.Viewpoint', revision=1, name=label + ' - ' + case['title'])
                viewpoints.append({'meta': meta, 'body': {'audience': [exact(stakeholder if audience == 'business' else engineering)], 'concerns': [exact(concern)],
                    'selection': {'binding': 'air.selector/0.19', 'types': [t for _, _, types in sections for t in types], 'objects': []},
                    'presentation': {'format': 'air.audience-html/0.19', 'title': label + ' - ' + case['title'],
                        'sections': [{'id': identifier, 'heading': title, 'types': types} for identifier, title, types in sections]},
                    'disclosure_policy': 'Usage interne de l’équipe habilitée sur ce dossier fictif ; aucun masquage automatique de champs ni droit de transmission à un tiers.'}})
            assert 'error' not in client('air_import_drafts', {'objects': [engineering, *viewpoints]})
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:audience-baseline:' + code.lower(), revision=1)
            base = client('air_freeze_baseline', {'meta': meta, 'profile': AUDIENCE_PROFILE, 'members': [exact(o) for o in old['objects'] + [engineering, *viewpoints]], 'parent_baselines': [exact(old['baseline'])]})
            assert len(base['baseline']['body']['members']) == 52
            pin = {**exact(base['baseline']), 'digest': base['digest']};views = []
            for audience, viewpoint in zip(groups, viewpoints):
                request = {'baseline': pin, 'viewpoint': {**exact(viewpoint), 'digest': digest(viewpoint)}}
                result = client('air_compile_audience_view', request);assert 'error' not in result
                request_file = workspace / (code + '-' + audience + '.json');request_file.write_text(json.dumps(request), encoding='utf-8')
                html = workspace / (code + '-' + audience + '.html')
                cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'audience-view', str(request_file), '--output', str(html), '--credential', 'architect-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=45)
                assert cli.returncode == 0, cli.stderr
                assert html.read_bytes() == result['content'].encode('utf-8') and json.loads(cli.stdout)['content_digest'] == result['content_digest']
                session = Session(client);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'audience-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_compile_audience_view', 'arguments': request}})['result']['structuredContent'] == result
                destination = output / html.name;destination.write_bytes(result.pop('content').encode('utf-8'))
                views.append({'audience': audience, 'request': request, 'report': result, 'path': str(destination)})
            assert views[0]['report']['content_digest'] != views[1]['report']['content_digest']
            assert client('air_export_baseline', case['baseline'])['digest'] == old['digest']
            reports.append({'case': code, 'title': case['title'], 'baseline': pin, 'views': views})
        denied = APIClient(home, 'observer-D01.json', port)('air_compile_audience_view', reports[2]['views'][0]['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for case in reports:
            actor = {'subject': 'observer-' + case['case'], 'role': 'editor'}
            for view in case['views']:
                replay = compile_view(store, actor, AccessPolicy.load(settings.home), view['request']);replay.pop('content')
                assert replay == view['report']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': AUDIENCE_PROFILE, 'home': str(home), 'treatments': reports,
        'cross_dossier_refused': True, 'cli_mcp_identical': True, 'restored_views_identical': True, 'prior_baselines_preserved': True,
        'field_redaction': False, 'authorization_granted': False, 'normative_view_persisted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/audience.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
