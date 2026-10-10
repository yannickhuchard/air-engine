"""Isolated SQLite receipt exercise with two fictional teams, CLI and MCP."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from air import __version__, artifacts, builder_handoff, deliverables
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import BUILD_PROFILE
from air.foundation import exact
from air.mcp import APIClient, PROTOCOL, Session
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder_demo', ROOT / 'fixtures/builder_handoff/model.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated SQLite demonstration')
    output.mkdir(parents=True, exist_ok=False)
    home = output / '.air'; bootstrap(home); settings = Settings.load(home); store = Store(settings.database_url)
    credential = json.loads((home / 'credentials.json').read_text(encoding='utf-8'))
    architect = store.authenticate(credential['access_token'], True); architect['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy(); server = None; log = None
    env = dict(os.environ); env['PYTHONUTF8'] = '1'; env.pop('AIR_DATABASE_URL', None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        build = fixture.build
        descriptors = {name: artifacts.put(store, architect, policy, settings,
            {'namespace': build.NAMESPACE, 'media_type': 'application/json', 'idempotency_key': name},
            (build.ROOT / (name + '.schema.json')).read_bytes())['artifact_reference'] for name in ('request', 'response')}
        objects = fixture.with_teams(build.objects(descriptors)); store.put_bundle(objects, architect['subject'])
        baseline = store.create_baseline({'meta': build.obj('Baseline', 'baseline', {})['meta'], 'profile': BUILD_PROFILE,
            'members': [exact(o) for o in objects], 'parent_baselines': []}, architect['subject'])
        pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
        grants = {'version': '1', 'subjects': {architect['subject']: {'read': ['*'], 'write': ['*']}}}
        roles = {}
        for side in ('provider', 'consumer'):
            roles[side] = [builder_handoff.pin(o) for o in objects if o['meta']['type'] == 'air.Role' and o['meta']['name'].startswith(side)]
            subject = 'fictional-' + side
            grants['subjects'][subject] = {'read': ['*'], 'receive': [build.NAMESPACE], 'builder_roles': roles[side]}
            write_private(home / (side + '.json'), store.create_token(subject, 'editor'))
        write_private(home / 'access-policy.json', grants); policy = AccessPolicy(grants)
        with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        log = (output / 'private-server.log').open('wb')
        server = subprocess.Popen([sys.executable, '-m', 'air', '--home', str(home), 'serve', '--port', str(port), '--no-worker'],
            stdout=log, stderr=log, env=env, creationflags=flags)
        deadline = time.monotonic() + 60
        while True:
            try:
                with urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=1): break
            except OSError:
                if server.poll() is not None or time.monotonic() > deadline: raise RuntimeError('Isolated API did not start')
                time.sleep(.1)
        commands = []
        def cli(command, request, credential='credentials.json', extra=()):
            path = output / ('request-' + str(len(commands)) + '.json'); path.write_text(json.dumps(request), encoding='utf-8')
            run = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(path), '--port', str(port),
                '--credential', credential, *extra], capture_output=True, text=True, encoding='utf-8', env=env, timeout=120, creationflags=flags)
            if run.returncode: raise RuntimeError('Isolated CLI command failed: ' + command)
            commands.append(command); return json.loads(run.stdout)
        request = {'package_id': 'urn:air:reference:delivery', 'title': 'Fournisseur et consommateur de devis', 'version': 1, 'baseline': pin,
            'units': [builder_handoff.pin(o) for o in objects if o['meta']['type'] == 'air.ConstructionUnit']}
        compiled = cli('handoff-compile', request, extra=['--workspace', str(output / 'packet'), '--apply'])
        assert compiled['manifest']['gaps'] == [] and compiled['applied']
        package = cli('handoff-create', {**request, 'idempotency_key': 'create'})['package']
        expiry = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        def receipt(side, role, key, outcome='ACCEPTED', questions=None):
            return cli('handoff-receive', {'package': package, 'role': role, 'idempotency_key': key, 'outcome': outcome,
                'rationale': 'Réception technique fictive du périmètre, sans avis humain.', 'questions': questions or [], 'expires_at': expiry}, side + '.json')
        question = receipt('provider', roles['provider'][0], 'question', 'CHANGES_REQUESTED', ['Qui réalise les retries ?'])
        assert cli('handoff-read', {'package': package, 'baseline': pin})['state'] == 'CHANGES_REQUESTED'
        for side in roles:
            for i, role in enumerate(roles[side]): receipt(side, role, side + str(i))
        assert cli('handoff-assess', {'baseline': pin})['state'] == 'INCOMPLETE'
        cli('handoff-revoke', {'receipt': question['receipt'], 'rationale': 'Question traitée dans la recette fictive.'}, 'provider.json')
        assessment = cli('handoff-assess', {'baseline': pin}); assert assessment['state'] == 'RECEIVED_FOR_BUILD_PLANNING'
        # MCP bridge retrieves precisely the same state through the HTTP service.
        session = Session(APIClient(home, 'provider.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'builder-receipt', 'version': '1'}}})
        response = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_assess_builder_handoffs', 'arguments': {'baseline': pin}}})
        assert response['result']['structuredContent'] == assessment
        # A new version gets no receipts and cannot hide an uncovered unit.
        cli('handoff-create', {**request, 'version': 2, 'units': request['units'][:1], 'idempotency_key': 'version-2'})
        pending = cli('handoff-assess', {'baseline': pin})
        assert pending['state'] == 'INCOMPLETE' and len(pending['units_without_package']) == 1
        site = deliverables.compile_deliverables(store, architect, policy, {'title': 'Asteria : réception des constructeurs', 'baselines': [pin]})
        apply_files(output / 'project', site['files'], plan_files(output / 'project', site['files']))
        report = {'status': 'PASS_SCOPED', 'engine_version': __version__, 'baseline': pin, 'package': package,
            'cli_commands': commands, 'mcp_matches_cli': True, 'two_fictional_teams': True, 'required_roles': 4,
            'questions_block_acceptance_until_withdrawn': True, 'new_version_requires_new_receipts': True,
            'missing_unit_visible': True, 'site_dossier': site['website']['dossiers'][0], 'site_files': len(site['files']),
            'real_teams_validated': False, 'authorization_granted': False, 'ci_executed': False}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': report['status'], 'cli_commands': len(commands), 'roles': 4, 'site_files': report['site_files']}))
    finally:
        if server is not None:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
        store.engine.dispose()
        if log is not None: log.close()


if __name__ == '__main__': main()
