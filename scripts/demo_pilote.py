"""Pilot rehearsal: three project repositories, one central portfolio repository, one AIR instance.

Chained after demo_atelier.py. The central repository is compiled from the declared portfolio, its access
policy is installed, each project repository is produced from the central specification, the holistic index
is compiled from the three closed Asteria baselines, a shared-object divergence is created and detected, an
undeclared subject is refused, and the MCP process declared by the central repository for Claude Code is started.
"""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.core import ARCHITECTURE_PROFILE
from air.foundation import exact
from air.mcp import APIClient, PROTOCOL, Session, TOOLS
from air.storage import Store
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = json.loads((ROOT / 'examples/portfolio.json').read_text(encoding='utf-8'))
CASE_PROJECT = {'D01': 'sav', 'D02': 'atelier', 'D03': 'identites'}
SUBJECTS = ['architect-D01', 'architect-D02', 'architect-D03', 'portfolio-architect', 'intrus']


def run_cli(home, port, command, document, repository, credential, extra=()):
    argv = [sys.executable, '-m', 'air', '--home', str(home), command, str(document), '--workspace', str(repository),
            '--credential', credential, '--port', str(port), *extra]
    return subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', timeout=120)


def through_mcp(client, name, arguments, label):
    session = Session(client)
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': label, 'version': '1'}}})
    session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    return session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})['result']['structuredContent']


def declared_process(repository, credential):
    """Start the process exactly as the generated configuration declares it and list its tools."""
    server = json.loads((repository / '.mcp.json').read_text(encoding='utf-8'))['mcpServers']['air']
    argv = [server['command'], *server['args']]
    assert argv[argv.index('--credential') + 1] == credential
    requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'claude-code-probe', 'version': '1'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
    process = subprocess.run(argv, input='\n'.join(json.dumps(item) for item in requests) + '\n', text=True, encoding='utf-8', capture_output=True, timeout=60)
    assert process.returncode == 0 and process.stderr == '', process.stderr
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    return {'argv_declared': argv[1:], 'tools_listed': len(rows[1]['result']['tools']), 'stderr_empty': True}


def plan_of(completed, expected_code=0):
    assert completed.returncode == expected_code, completed.stderr or completed.stdout
    return {step['path']: step['action'] for step in json.loads(completed.stdout)['plan']}


def rehearse():
    previous = json.loads((ROOT / 'tmp/demo-asteria/atelier.json').read_text(encoding='utf-8'))
    original_home = Path(previous['home']).resolve()
    assert original_home.is_relative_to((ROOT / 'tmp').resolve()) and original_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-pilote-' + uuid.uuid4().hex)
    protect_directory(workspace);snapshot(original_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for name in SUBJECTS: write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    central = workspace / 'portefeuille';spec_file = workspace / 'portfolio.json'
    spec_file.write_text(json.dumps(SPECIFICATION, ensure_ascii=False), encoding='utf-8')
    interpreter, home_text = sys.executable.replace('\\', '/'), str(home).replace('\\', '/')
    pins = {CASE_PROJECT[case['case']]: case['baseline'] for case in previous['treatments']}
    report = {'version': __version__, 'home': str(home), 'central': str(central), 'source_report': 'tmp/demo-asteria/atelier.json'}
    start(sys.executable, home, port)
    try:
        lead = APIClient(home, 'portfolio-architect.json', port)
        scaffold = lead('air_compile_portfolio', SPECIFICATION);assert 'error' not in scaffold, scaffold
        assert through_mcp(lead, 'air_compile_portfolio', SPECIFICATION, 'portfolio-demo') == scaffold
        assert plan_of(run_cli(home, port, 'portfolio-init', spec_file, central, 'portfolio-architect.json')) == {item['path']: 'CREATE' for item in scaffold['files']}
        assert set(plan_of(run_cli(home, port, 'portfolio-init', spec_file, central, 'portfolio-architect.json', ('--apply',))).values()) == {'UNCHANGED'}
        for item in scaffold['files']: assert (central / item['path']).read_bytes() == item['content'].encode('utf-8')
        # The generated policy is installed by the administration step, not by the compilation.
        installed = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'policy-set', str(central / 'policies/access-policy.json')],
                                   capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert installed.returncode == 0, installed.stderr
        intruder = APIClient(home, 'intrus.json', port)('air_index_portfolio', {'portfolio': SPECIFICATION, 'baselines': [{'project': 'sav', 'baseline': pins['sav']}]})
        assert 'error' in intruder, intruder
        sav_architect = APIClient(home, 'architect-D01.json', port)
        identity = sav_architect('air_get', {'id': 'urn:asteria:scope:identity', 'revision': 1});assert 'error' not in identity, identity
        outside = deepcopy(identity['object']);outside['meta'].update(id='urn:asteria:scope:pilote-hors-mandat', revision=1, name='Hors mandat')
        refused_write = sav_architect('air_import_drafts', {'objects': [outside]});assert 'error' in refused_write, refused_write
        repositories = {}
        for code in ('sav', 'atelier', 'identites', 'socle'):
            request_file = central / 'projects' / code / 'workspace.request.json';repository = workspace / code
            assert set(plan_of(run_cli(home, port, 'workspace-init', request_file, repository, 'portfolio-architect.json', ('--apply',))).values()) == {'UNCHANGED'}
            repositories[code] = {'directory': str(repository), 'files': sum(1 for p in repository.rglob('*') if p.is_file()),
                'dossier': json.loads((repository / 'domains' / code / 'dossier.json').read_text(encoding='utf-8'))['namespace']}
        # The team completes the generated client examples with the workstation paths; nothing else is written by hand.
        adapters = {}
        for name, example_file in (('sav', central / 'projects/sav/claude-code.example.json'), ('portefeuille', central / 'claude-code.example.json')):
            request = json.loads(example_file.read_text(encoding='utf-8'))
            request['server'].update(interpreter=interpreter, home=home_text, port=port);adapters[name] = request
            adapter_file = workspace / ('adapter-' + name + '.json');adapter_file.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
            target = central if name == 'portefeuille' else workspace / name
            assert set(plan_of(run_cli(home, port, 'ide-setup', adapter_file, target, request['server']['credential'], ('--apply',))).values()) == {'UNCHANGED'}
        assert adapters['sav']['server']['credential'] == 'architect-D01.json' and adapters['portefeuille']['workspace']['kind'] == 'portfolio'
        assert (central / '.claude/commands/air-portefeuille.md').exists() and not (central / '.claude/commands/air-proposer.md').exists()
        assert not (workspace / 'sav' / '.claude/commands/air-portefeuille.md').exists()
        declared = declared_process(central, 'portfolio-architect.json');assert declared['tools_listed'] == len(TOOLS)
        # Holistic index at the three closed Asteria baselines, written into the central repository.
        index_request = {'portfolio': SPECIFICATION, 'baselines': [{'project': code, 'baseline': pins[code]} for code in sorted(pins)]}
        # The team's pins file carries the pins only; the CLI joins the declaration kept in the central repository.
        pin_file = central / 'portfolio-index.request.json';pin_file.write_text(json.dumps({'baselines': index_request['baselines']}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        index = lead('air_index_portfolio', index_request);assert 'error' not in index, index
        assert through_mcp(lead, 'air_index_portfolio', index_request, 'index-demo') == index
        assert set(plan_of(run_cli(home, port, 'portfolio-index', pin_file, central, 'portfolio-architect.json', ('--apply',))).values()) == {'UNCHANGED'}
        written = json.loads((central / 'portfolio-index.json').read_text(encoding='utf-8'))
        assert written['index_digest'] == index['index_digest'] and (central / 'docs/portefeuille.md').exists()
        assert index['totals']['projects_indexed'] == 3 and index['totals']['divergences'] == 0 and index['result'] == 'CONSISTENT_AT_PINS', index['totals']
        assert index['shared_identities'] and all(item['status'] == 'AGREEMENT' for item in index['shared_identities'])
        assert all(entry['chain_absent'] == [] for entry in index['projects'] if entry['status'] == 'INDEXED')
        assert next(entry for entry in index['projects'] if entry['code'] == 'socle')['status'] == 'NO_BASELINE_DECLARED'  # Asteria's socle has no baseline of its own
        project_reader = APIClient(home, 'architect-D02.json', port)('air_index_portfolio', index_request);assert 'error' not in project_reader
        # The socle evolves: one project follows it, another does not. The index must say so.
        common = deepcopy(identity['object']);common['meta'].update(id='urn:asteria:scope:pilote-commun', revision=1, name='Périmètre commun du pilote')
        assert 'error' not in lead('air_import_drafts', {'objects': [common]})
        revised = deepcopy(common);revised['meta']['revision'] = 2;revised['body']['boundary_description'] = 'Périmètre commun révisé pendant le pilote.'
        assert 'error' not in lead('air_import_drafts', {'objects': [revised]})
        divergent_pins = dict(pins)
        for code, member, credential in (('sav', common, 'architect-D01.json'), ('atelier', revised, 'architect-D02.json')):
            architect = APIClient(home, credential, port);old = architect('air_export_baseline', pins[code]);assert 'error' not in old, old
            meta = deepcopy(old['baseline']['meta']);meta.update(id='urn:asteria:architecture-baseline:' + code + '-pilote', revision=1)
            frozen = architect('air_freeze_baseline', {'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in old['objects']] + [exact(member)], 'parent_baselines': [exact(old['baseline'])]})
            assert 'error' not in frozen, frozen
            divergent_pins[code] = {**exact(frozen['baseline']), 'digest': frozen['digest']}
        divergent_request = {'portfolio': SPECIFICATION, 'baselines': [{'project': code, 'baseline': divergent_pins[code]} for code in sorted(divergent_pins)]}
        pin_file.write_text(json.dumps({'baselines': divergent_request['baselines']}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # A stale generated index is a CONFLICT: the plan says so and exits 1 until the team asks to replace it.
        refreshed = plan_of(run_cli(home, port, 'portfolio-index', pin_file, central, 'portfolio-architect.json'), expected_code=1)
        assert refreshed == {'docs/portefeuille.md': 'CONFLICT', 'portfolio-index.json': 'CONFLICT'}, refreshed
        assert set(plan_of(run_cli(home, port, 'portfolio-index', pin_file, central, 'portfolio-architect.json', ('--apply', '--replace-generated'))).values()) == {'UNCHANGED'}
        divergent = json.loads((central / 'portfolio-index.json').read_text(encoding='utf-8'))
        divergence = next(item for item in divergent['shared_identities'] if item['id'] == 'urn:asteria:scope:pilote-commun')
        assert divergence['status'] == 'DIVERGENCE' and divergence['repositories']['sav']['revision'] == 1 and divergence['repositories']['atelier']['revision'] == 2
        assert divergent['result'] == 'REVIEW_REQUIRED' and divergent['totals']['divergences'] == 1
        assert 'DIVERGENCE' in (central / 'docs/portefeuille.md').read_text(encoding='utf-8')
        assert lead('air_export_baseline', pins['sav'])['digest'] == pins['sav']['digest']
        # Regeneration keeps the team's files: the pinned request is theirs, the index is AIR's.
        reapplied = plan_of(run_cli(home, port, 'portfolio-init', spec_file, central, 'portfolio-architect.json', ('--apply',)))
        assert reapplied['portfolio-index.request.json'] == 'PRESERVED' and set(reapplied.values()) == {'UNCHANGED', 'PRESERVED'}
        assert json.loads(pin_file.read_text(encoding='utf-8')) == {'baselines': divergent_request['baselines']}
        report.update({'status': 'PASS_SCOPED', 'dossiers': 3, 'repositories_created': sorted(repositories), 'treatments': previous['treatments'], 'pins': pins, 'divergent_pins': divergent_pins,
            'scaffold_report': {k: scaffold[k] for k in ('engine', 'file_set_digest', 'total_size', 'subjects_declared', 'policy_installable', 'projects')},
            'index_at_pins': {k: index[k] for k in ('engine', 'index_digest', 'result', 'totals', 'dependencies')},
            'index_after_divergence': {k: divergent[k] for k in ('index_digest', 'result', 'totals')}, 'divergence': divergence,
            'project_repositories': repositories, 'declared_process': declared, 'policy_installed_by_administration': True,
            'undeclared_subject_refused': True, 'project_architect_cannot_write_shared': True, 'project_architect_reads_whole_portfolio': True,
            'cli_api_mcp_identical': True, 'seeded_files_preserved': True, 'generated_index_refused_without_replace': True,
            'prior_baselines_preserved': True, 'single_instance': True, 'federation_implemented': False, 'client_qualified': False,
            'business_scenarios_executed': False, 'semantic_compatibility_executed': False, 'authorization_granted': False,
            'live_instance_modified': False, 'external_actions_executed': False})
    finally: stop(home)
    # The index is a pure function of the registry at the pins: a restored copy yields the same digest.
    snapshot(home, workspace / 'final-backup');restore(workspace / 'final-backup', workspace / 'restored')
    from air.access import AccessPolicy
    from air.portfolio import index_portfolio
    restored = Store(Settings.load(workspace / 'restored').database_url)
    try:
        again = index_portfolio(restored, {'subject': 'portfolio-architect', 'role': 'editor'}, AccessPolicy.load(workspace / 'restored'), divergent_request)
    finally: restored.engine.dispose()
    assert again['index_digest'] == report['index_after_divergence']['index_digest']
    report['restored_index_identical'] = True
    return report


if __name__ == '__main__':
    result = rehearse();output = ROOT / 'tmp/demo-asteria/pilote.json'
    output.parent.mkdir(parents=True, exist_ok=True);output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': result['dossiers'], 'report': str(output)}))
