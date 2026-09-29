"""Generate the Asteria architecture repository and its Claude Code adapter, then start the declared MCP process."""
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
from air.ide_adapter import compile_adapter, COMMITTING
from air.mcp import APIClient, PROTOCOL, Session, TOOLS
from air.storage import Store
from air.workspace import compile_workspace
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]
DOMAINS = [{'code': 'sav', 'title': 'Portail SAV et orchestration des interventions', 'purpose': 'Réclamations clients et interventions.', 'namespace': 'asteria.sav', 'urn_segment': 'sav'},
           {'code': 'atelier', 'title': 'Maintenance connectée d’un atelier', 'purpose': 'Mesures machines et inspections.', 'namespace': 'asteria.atelier', 'urn_segment': 'atelier'},
           {'code': 'identites', 'title': 'Arrivées, mobilités et départs', 'purpose': 'Cycle de vie des accès.', 'namespace': 'asteria.identites', 'urn_segment': 'identites'},
           {'code': 'socle', 'title': 'Socle partagé', 'purpose': 'Périmètres et sources communs aux trois dossiers.', 'namespace': 'asteria.shared', 'urn_segment': 'socle'}]
SPECIFICATION = {'organization': {'name': 'Asteria Industrie', 'urn_prefix': 'asteria', 'namespace_prefix': 'asteria'},
    'repository': {'name': 'Référentiel d’architecture de solution Asteria', 'description': 'Quatre domaines partageant une même installation AIR.'},
    'domains': DOMAINS, 'profiles': ['air.foundation/0.2', 'air.construction/0.4', 'air.architecture/0.26'],
    'review': {'independent_review_required': True, 'namespace_policy': 'EXPLICIT'}}
CASE_DOMAIN = {'D01': 'asteria.sav', 'D02': 'asteria.atelier', 'D03': 'asteria.identites'}


def run_cli(home, port, command, document, repository, credential, extra=()):
    argv = [sys.executable, '-m', 'air', '--home', str(home), command, str(document), '--workspace', str(repository),
            '--credential', credential, '--port', str(port), *extra]
    return subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', timeout=90)


def through_mcp(client, name, arguments, label):
    session = Session(client)
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': label, 'version': '1'}}})
    session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    return session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})['result']['structuredContent']


def declared_process(repository, credential):
    """Start the process exactly as the generated configuration declares it and complete an MCP session."""
    server = json.loads((repository / '.mcp.json').read_text(encoding='utf-8'))['mcpServers']['air']
    argv = [server['command'], *server['args']]
    assert argv[argv.index('--credential') + 1] == credential, 'The declared credential is the one the recipe minted'
    requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'claude-code-probe', 'version': '1'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
    process = subprocess.run(argv, input='\n'.join(json.dumps(item) for item in requests) + '\n', text=True,
                             encoding='utf-8', capture_output=True, timeout=60)
    assert process.returncode == 0 and process.stderr == '', process.stderr
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == 2 and rows[0]['result']['protocolVersion'] == PROTOCOL
    return {'argv_declared': argv[1:], 'tools_listed': len(rows[1]['result']['tools']), 'stdout_lines': len(rows), 'stderr_empty': True}


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/openapi.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-atelier-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in previous['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case'];write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    repository = workspace / 'referentiel-asteria'
    adapter_request = {'client': 'claude-code', 'workspace': {'name': SPECIFICATION['repository']['name'], 'organization': 'Asteria Industrie'},
        'server': {'interpreter': sys.executable.replace('\\', '/'), 'home': str(home).replace('\\', '/'), 'credential': 'architect-D01.json', 'port': port},
        'access': 'read-only', 'shared_instructions': 'AGENTS.md'}
    specification_file = workspace / 'workspace.json';specification_file.write_text(json.dumps(SPECIFICATION, ensure_ascii=False), encoding='utf-8')
    adapter_file = workspace / 'adapter.json';adapter_file.write_text(json.dumps(adapter_request, ensure_ascii=False), encoding='utf-8')
    start(sys.executable, home, port)
    try:
        client = APIClient(home, 'architect-D01.json', port)
        scaffold = client('air_compile_workspace', SPECIFICATION);assert 'error' not in scaffold, scaffold
        adapter = client('air_compile_ide_adapter', adapter_request);assert 'error' not in adapter, adapter
        assert through_mcp(client, 'air_compile_workspace', SPECIFICATION, 'workspace-demo') == scaffold
        assert through_mcp(client, 'air_compile_ide_adapter', adapter_request, 'adapter-demo') == adapter
        for command, document, product in (('workspace-init', specification_file, scaffold), ('ide-setup', adapter_file, adapter)):
            dry = run_cli(home, port, command, document, repository, 'architect-D01.json')
            assert dry.returncode == 0, dry.stderr
            assert {step['action'] for step in json.loads(dry.stdout)['plan']} == {'CREATE'}
            applied = run_cli(home, port, command, document, repository, 'architect-D01.json', ('--apply',))
            assert applied.returncode == 0, applied.stderr
            assert {step['action'] for step in json.loads(applied.stdout)['plan']} == {'UNCHANGED'}
            for item in product['files']:
                assert (repository / item['path']).read_bytes() == item['content'].encode('utf-8')
        declared = declared_process(repository, 'architect-D01.json')
        assert declared['tools_listed'] == len(TOOLS)
        assert set(adapter['tools_allowed']) <= {tool for tool in TOOLS}
        conventions = {domain['code']: json.loads((repository / ('domains/' + domain['code'] + '/dossier.json')).read_text(encoding='utf-8')) for domain in DOMAINS}
        observed = []
        for case in previous['treatments']:
            reader = APIClient(home, 'architect-' + case['case'] + '.json', port)
            exported = reader('air_export_baseline', case['baseline']);assert 'error' not in exported, exported
            namespaces = sorted({obj['meta']['namespace'] for obj in exported['objects']})
            assert set(namespaces) <= {CASE_DOMAIN[case['case']], 'asteria.shared'}, namespaces
            observed.append({'case': case['case'], 'baseline': case['baseline'], 'namespaces': namespaces,
                'declared_namespace': CASE_DOMAIN[case['case']], 'objects': len(exported['objects']),
                'baseline_convention': conventions[next(d['code'] for d in DOMAINS if d['namespace'] == CASE_DOMAIN[case['case']])]['baseline_id']})
        restricted = APIClient(home, 'observer-D01.json', port)('air_compile_workspace', SPECIFICATION)
        assert 'error' not in restricted, restricted
        scoped = {domain['code']: domain['current_policy'] for domain in restricted['domains']}
        assert scoped['sav'] == {'read': True, 'write': True} and scoped['socle'] == {'read': True, 'write': False}
        assert scoped['identites'] == {'read': False, 'write': False} and scoped['atelier'] == {'read': False, 'write': False}
        note = 'Note locale conservée par la recette.' + chr(10)
        claude = repository / 'CLAUDE.md';claude.write_text(claude.read_text(encoding='utf-8') + chr(10) + note, encoding='utf-8')
        seeded = repository / 'README.md';seeded.write_text('# Titre choisi par l’équipe' + chr(10), encoding='utf-8')
        generated = repository / '.claude/commands/air-dossier.md';generated.write_text('Texte local divergent' + chr(10), encoding='utf-8')
        adapter_request['access'] = 'contribute';adapter_file.write_text(json.dumps(adapter_request, ensure_ascii=False), encoding='utf-8')
        refused = run_cli(home, port, 'ide-setup', adapter_file, repository, 'architect-D01.json', ('--apply',))
        assert refused.returncode == 1
        steps = {step['path']: step['action'] for step in json.loads(refused.stdout)['plan']}
        assert steps['.claude/commands/air-dossier.md'] == 'CONFLICT' and steps['CLAUDE.md'] == 'UNCHANGED'
        assert claude.read_text(encoding='utf-8').endswith(note) and 'contribute' in claude.read_text(encoding='utf-8')
        assert generated.read_text(encoding='utf-8') == 'Texte local divergent' + chr(10)
        repaired = run_cli(home, port, 'ide-setup', adapter_file, repository, 'architect-D01.json', ('--apply', '--replace-generated'))
        repaired_plan = {step['path']: step['action'] for step in json.loads(repaired.stdout)['plan']}
        assert repaired.returncode == 0 and set(repaired_plan.values()) == {'UNCHANGED'}, repaired_plan
        assert claude.read_text(encoding='utf-8').endswith(note)
        preserved = run_cli(home, port, 'workspace-init', specification_file, repository, 'architect-D01.json', ('--apply', '--replace-generated'))
        assert preserved.returncode == 0
        assert {step['path']: step['action'] for step in json.loads(preserved.stdout)['plan']}['README.md'] == 'PRESERVED'
        assert seeded.read_text(encoding='utf-8') == '# Titre choisi par l’équipe' + chr(10)
        contribute = client('air_compile_ide_adapter', adapter_request)
        assert set(contribute['tools_denied']) == set(adapter['tools_denied']) - set(contribute['tools_allowed'])
        assert not set(contribute['tools_allowed']) & set(COMMITTING) and set(contribute['tools_denied']) == set(COMMITTING)
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        actor = {'subject': 'architect-D01', 'role': 'editor'};policy = AccessPolicy.load(settings.home)
        assert compile_adapter(store, actor, policy, {**adapter_request, 'access': 'read-only'})['files'] == adapter['files']
        assert compile_workspace(store, actor, policy, SPECIFICATION)['files'] == scaffold['files']
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'home': str(home), 'repository': str(repository),
        'workspace_report': scaffold, 'adapter_report': adapter, 'declared_process': declared, 'treatments': observed,
        'cli_api_mcp_identical': True, 'idempotent_reapply': True, 'local_work_preserved': True, 'seeded_files_preserved': True,
        'generated_conflict_refused': True, 'restored_products_identical': True, 'declared_namespaces_cover_baseline_objects': True,
        'committing_tools_refused': True, 'client_qualified': False, 'business_scenarios_executed': False,
        'external_actions_executed': False, 'authorization_granted': False, 'live_instance_modified': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/atelier.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
