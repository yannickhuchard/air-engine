"""Three local Asteria design packages, atomic portfolio publication and recovery."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import digest
from air.foundation import exact
from air.mcp import APIClient, PROTOCOL, Session
from air.packages import read_package
from air.portability import export_registry, import_home
from air.storage import Store
from demo_projections import read, ref, evolve
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse(with_context=False):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Isolated demo requires default SQLite')
    workspace = ROOT / 'tmp' / ('air-packages-' + uuid.uuid4().hex)
    home = workspace / 'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    policy = {'version': 'asteria-packages-1', 'subjects': {'release-manager': {'read': ['*'], 'publish': ['*']},
        'portfolio-reader': {'read': ['*']}, 'sav-reader': {'read': ['asteria.sav', 'asteria.shared']}}}
    write_private(home / 'access-policy.json', policy)
    write_private(home / 'publisher.json', store.create_token('release-manager', 'editor'))
    write_private(home / 'reader.json', store.create_token('portfolio-reader', 'reader'))
    write_private(home / 'sav-reader.json', store.create_token('sav-reader', 'reader'))
    dossiers, all_objects = [], {}
    try:
        for case in read('manifest.json')['dossiers']:
            objects = read(case['construction']);store.put_bundle(objects, 'architect-' + case['id'])
            baseline = store.create_baseline(read(case['construction_baseline_request']), 'architect-' + case['id'])
            functions = [o for o in objects if o['meta']['type'] == 'air.Function']
            dossiers.append({'case': case['id'], 'baseline': ref(baseline), 'exports': [{**exact(o), 'digest': digest(o)} for o in functions]})
            all_objects.update({o['meta']['id']: o for o in objects})
        combined = deepcopy(read(read('manifest.json')['dossiers'][0]['construction_baseline_request']))
        combined['meta'].update(id='urn:asteria:baseline:portfolio', namespace='asteria.portfolio', name='Portefeuille Asteria - conception')
        combined['members'] = [exact(o) for o in all_objects.values()]
        portfolio = ref(store.create_baseline(combined, 'enterprise-architect'))
        evolved_dossier = None
        if with_context:
            case = read('manifest.json')['dossiers'][2]
            evolved = evolve(read(case['construction']));store.put_bundle(evolved, 'architect-D03')
            evolved_request = deepcopy(read(case['construction_baseline_request']))
            evolved_request['meta']['id'] += ':identity-revised'
            evolved_request['members'] = [exact(o) for o in evolved]
            evolved_base = ref(store.create_baseline(evolved_request, 'architect-D03'))
            evolved_dossier = {'baseline': evolved_base, 'exports': [{**exact(o), 'digest': digest(o)} for o in evolved if o['meta']['type'] == 'air.Function']}
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    start(Path(sys.executable), home, port)
    def execute(command, body, credential='publisher.json', expected=0):
        file = workspace / (command + '-' + uuid.uuid4().hex + '.json')
        file.write_text(json.dumps(body), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(file), '--port', str(port), '--credential', credential],
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert result.returncode == expected, 'Unexpected result for ' + command
        return json.loads(result.stdout if result.returncode == 0 else result.stderr)
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')
    publications = []
    contexts = None
    try:
        for dossier in dossiers:
            request = {'idempotency_key': dossier['case'], 'package_id': 'urn:asteria:package:' + dossier['case'].lower(), 'version': 1,
                'baseline': dossier['baseline'], 'exports': dossier['exports'], 'imports': [], 'expires_at': expires}
            stage = execute('package-prepare', request)
            assert not stage['published']
            command = {'idempotency_key': dossier['case'], 'preparation': stage['preparation']}
            published = execute('package-publish', command)
            assert not execute('package-publish', command)['created']
            publications.append(published['publication'])
        stage = execute('package-prepare', {'idempotency_key': 'portfolio', 'package_id': 'urn:asteria:package:portfolio', 'version': 1,
            'baseline': portfolio, 'exports': [r for d in dossiers for r in d['exports']], 'imports': publications, 'expires_at': expires})
        command = {'idempotency_key': 'portfolio', 'preparation': stage['preparation']}
        denied = execute('package-publish', command, 'reader.json', 1)
        assert denied['status'] == 403
        published_portfolio = execute('package-publish', command)['publication']
        query = {'publication': published_portfolio, 'purpose': 'NEW_USE'}
        view = execute('package-read', query, 'reader.json')
        assert len(view['manifest']['imports']) == 3 and not view['authorization_granted']
        assert execute('package-read', query, 'sav-reader.json', 1)['status'] == 403
        session = Session(APIClient(home, 'reader.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'asteria-replay', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        replay = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_package_read', 'arguments': query}})['result']
        assert not replay['isError'] and replay['structuredContent'] == view
        if with_context:
            for namespace, publication in zip(['asteria.sav', 'asteria.atelier', 'asteria.identites'], publications):
                discovered = execute('discover', {'namespace': namespace, 'include_unavailable': False, 'page_size': 20, 'cursor': None}, 'reader.json')
                assert publication in [p['publication'] for p in discovered['packages']]
            observed = execute('context-create', {'idempotency_key': 'before-revocation', 'publications': publications, 'purpose': 'Contexte initial des trois dossiers'}, 'reader.json')
            baseline_analysis = execute('reconcile', {'context': observed['context']}, 'reader.json')
            assert not baseline_analysis['divergences']
            reread = execute('context-read', {'context': observed['context']}, 'reader.json')
            assert reread['snapshot'] == observed['snapshot']
            mcp_analysis = session.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'air_reconcile', 'arguments': {'context': observed['context']}}})['result']
            assert not mcp_analysis['isError'] and mcp_analysis['structuredContent'] == baseline_analysis
            evolved_stage = execute('package-prepare', {'idempotency_key': 'D03-v2', 'package_id': 'urn:asteria:package:d03', 'version': 2,
                'baseline': evolved_dossier['baseline'], 'exports': evolved_dossier['exports'], 'imports': [], 'expires_at': expires})
            evolved_publication = execute('package-publish', {'idempotency_key': 'D03-v2', 'preparation': evolved_stage['preparation']})['publication']
            divergent = execute('context-create', {'idempotency_key': 'divergent', 'publications': publications[:2] + [evolved_publication], 'purpose': 'Évolution IAM non encore reprise par SAV et atelier'}, 'reader.json')
            divergence = execute('reconcile', {'context': divergent['context']}, 'reader.json')
            assert any(d['id'] == 'urn:asteria:scope:identity' for d in divergence['divergences'])
            assert not divergence['source_mutations']
            contexts = {'initial': observed, 'initial_analysis': baseline_analysis, 'divergent': divergent, 'divergent_analysis': divergence}
        execute('package-revoke', {'publication': publications[2], 'rationale': 'Retrait fictif après découverte d’une divergence IAM.'})
        assert execute('package-read', query, 'reader.json', 1)['status'] == 422
        query['purpose'] = 'HISTORICAL'
        historical = execute('package-read', query, 'reader.json')
        assert not historical['new_use_allowed']
        if with_context:
            assert execute('reconcile', {'context': contexts['initial']['context']}, 'reader.json') == contexts['initial_analysis']
            fresh = execute('context-create', {'idempotency_key': 'after-revocation', 'publications': publications, 'purpose': 'Réévaluation après retrait IAM'}, 'reader.json')
            fresh_analysis = execute('reconcile', {'context': fresh['context']}, 'reader.json')
            assert any(o['code'] == 'CONTRIBUTION_UNAVAILABLE' for o in fresh_analysis['observations'])
            contexts.update(after_revocation=fresh, current_analysis=fresh_analysis, historical_replay_identical=True)
    finally: stop(home)
    source = Store(Settings.load(home).database_url)
    try: exported = export_registry(source, workspace / 'transfer', policy)
    finally: source.engine.dispose()
    recovered_home = workspace / 'recovered'
    recovery = import_home(workspace / 'transfer', recovered_home)
    target = Store(Settings.load(recovered_home).database_url)
    try:
        recovered = read_package(target, {'subject': 'portfolio-reader', 'role': 'reader'}, AccessPolicy.load(recovered_home), query)
        assert recovered['manifest'] == historical['manifest']
        assert not recovered['new_use_allowed']
    finally: target.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'binding': 'real CLI/HTTP and MCP API bridge',
        'contexts': contexts, 'dossiers': dossiers, 'publications': publications, 'portfolio': published_portfolio,
        'three_imports_exact': True, 'idempotent_replay': True, 'cross_scope_refused': True,
        'revoked_dependency_blocks_new_use': True, 'historical_manifest_preserved_after_transfer': True,
        'recovery': recovery, 'external_effects': False, 'business_authorization_granted': False,
        'scope': 'Local design publications, not admission or deployment', 'live_instance_modified': False}


if __name__ == '__main__':
    result = rehearse()
    output = ROOT / 'tmp/demo-asteria/packages.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'report': str(output)}))
