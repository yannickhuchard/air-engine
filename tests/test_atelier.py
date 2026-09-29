from copy import deepcopy
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
import yaml
from air import atelier, ide_adapter
from air.core import validate
from air.access import AccessPolicy
from air.api import create_app
from air.cli import main
from air.config import Settings, write_private
from air.foundation import InvalidModel
from air.ide_adapter import compile_adapter, COMMITTING, CONTRIBUTE, READ_ONLY
from air.mcp import TOOLS
from air.workspace import compile_workspace, example_draft, _domain_view

WORKSPACE = {'organization': {'name': 'Asteria Industrie', 'urn_prefix': 'asteria', 'namespace_prefix': 'asteria'},
    'repository': {'name': 'Référentiel d’architecture Asteria', 'description': 'Trois dossiers de solution partagés.'},
    'domains': [{'code': 'sav', 'title': 'Portail SAV', 'purpose': 'Réclamations clients.', 'namespace': 'asteria.sav', 'urn_segment': 'sav'},
                {'code': 'atelier', 'title': 'Atelier connecté', 'purpose': 'Maintenance des machines.', 'namespace': 'asteria.atelier', 'urn_segment': 'atelier'}],
    'profiles': ['air.foundation/0.2', 'air.architecture/0.26'],
    'review': {'independent_review_required': True, 'namespace_policy': 'EXPLICIT'}}
ADAPTER = {'client': 'claude-code', 'workspace': {'name': 'Référentiel Asteria', 'organization': 'Asteria Industrie'},
    'server': {'interpreter': 'D:/air/.venv/Scripts/python.exe', 'home': 'D:/air/.air', 'credential': 'agent.json', 'port': 8740},
    'access': 'read-only'}
USER = {'subject': 'urn:air:identity:local:architect', 'role': 'editor'}


def contents(result):
    return {item['path']: item['content'] for item in result['files']}


def test_workspace_is_deterministic_bounded_and_writes_nothing(store):
    before = store.counts();result = compile_workspace(store, USER, AccessPolicy(), WORKSPACE)
    assert result == compile_workspace(store, USER, AccessPolicy(), WORKSPACE) and store.counts() == before
    files = contents(result)
    assert set(files) == {'.github/workflows/air-check.yml', '.gitattributes', '.gitignore', 'AGENTS.md', 'README.md', 'air-workspace.json',
        'air-workspace.request.json', 'docs/conventions-referentiel.md', 'domains/atelier/README.md', 'domains/atelier/dossier.json',
        'domains/atelier/drafts/README.md', 'domains/sav/README.md', 'domains/sav/dossier.json', 'domains/sav/drafts/README.md',
        'policies/namespace-policy.example.json'}
    manifest = json.loads(files['air-workspace.json'])
    assert [d['baseline_id'] for d in manifest['domains']] == ['urn:air:asteria:atelier:baseline', 'urn:air:asteria:sav:baseline']
    assert json.loads(files['domains/sav/dossier.json'])['namespace'] == 'asteria.sav'
    assert not result['registry_written'] and not result['baselines_created'] and not result['authorization_granted']
    assert not result['namespace_policy_installed'] and not result['conformance_claimed'] and not result['secrets_included']
    for item in result['files']:
        assert item['content_digest'] == 'sha256:' + hashlib.sha256(item['content'].encode()).hexdigest() and item['content'].endswith('\n')
    assert json.loads(files['policies/namespace-policy.example.json'])['subjects'] == {}


def test_workspace_stays_regenerable_and_scales(store):
    result = compile_workspace(store, USER, AccessPolicy(), WORKSPACE)
    request = json.loads(contents(result)['air-workspace.request.json'])
    assert request == WORKSPACE and compile_workspace(store, USER, AccessPolicy(), request)['files'] == result['files']
    readme = contents(result)['README.md']
    assert 'asteria.sav' not in readme and 'air-workspace.request.json' in readme
    many = {**WORKSPACE, 'domains': [{'code': 'd%02d' % i, 'title': 'Domaine %02d' % i, 'purpose': 'Finalité.',
        'namespace': 'asteria.d%02d' % i, 'urn_segment': 'd%02d' % i} for i in range(64)]}
    wide = compile_workspace(store, USER, AccessPolicy(), many)
    assert len(wide['files']) == 9 + 3 * 64 and wide['total_size'] <= atelier.TOTAL_MAX


def test_workspace_draft_skeleton_is_a_valid_typed_object(store):
    views = [_domain_view(WORKSPACE['organization'], domain) for domain in WORKSPACE['domains']]
    assert validate([example_draft(view) for view in views])['valid']
    body = contents(compile_workspace(store, USER, AccessPolicy(), WORKSPACE))['domains/sav/drafts/README.md']
    assert json.loads(body.split('~~~json')[1].split('~~~')[0]) == example_draft(_domain_view(WORKSPACE['organization'], WORKSPACE['domains'][0]))


def test_workspace_reports_the_current_policy_without_granting_it(store):
    policy = AccessPolicy({'version': 'test/1', 'subjects': {USER['subject']: {'read': ['asteria.sav'], 'write': []}}})
    result = compile_workspace(store, USER, policy, WORKSPACE)
    access = {domain['code']: domain['current_policy'] for domain in result['domains']}
    assert access['sav'] == {'read': True, 'write': False} and access['atelier'] == {'read': False, 'write': False}
    assert result['policy_digest'] == policy.digest and not result['authorization_granted']


@pytest.mark.parametrize('fault', ['namespace-duplicated', 'namespace-outside-prefix', 'code-duplicated', 'segment-duplicated', 'unknown-profile'])
def test_workspace_refuses_an_inconsistent_specification(store, fault):
    request = deepcopy(WORKSPACE)
    if fault == 'namespace-duplicated': request['domains'][1]['namespace'] = 'asteria.sav'
    if fault == 'namespace-outside-prefix': request['domains'][1]['namespace'] = 'autre.atelier'
    if fault == 'code-duplicated': request['domains'][1]['code'] = 'sav'
    if fault == 'segment-duplicated': request['domains'][1]['urn_segment'] = 'sav'
    if fault == 'unknown-profile': request['profiles'] = ['air.federation/9.9']
    with pytest.raises(InvalidModel): compile_workspace(store, USER, AccessPolicy(), request)


def test_adapter_declares_its_surface_and_refuses_committing_tools(store):
    result = compile_adapter(store, USER, AccessPolicy(), ADAPTER)
    assert result == compile_adapter(store, USER, AccessPolicy(), ADAPTER)
    files = contents(result)
    assert set(files) == {'.claude/agents/air-relecteur.md', '.claude/air-adapter.json', '.claude/commands/air-dossier.md',
        '.claude/commands/air-proposer.md', '.claude/commands/air-relire.md', '.claude/commands/air-prouver.md', '.claude/commands/air-impact.md', '.claude/commands/air-livrer.md', '.claude/commands/air-accepter.md', '.claude/commands/air-presenter.md', '.claude/settings.json',
        '.claude/skills/air-architecte/SKILL.md', '.claude/skills/air-architecte/references/modelling.md', '.claude/skills/air-presentation/SKILL.md',
        '.claude/skills/air-presentation/references/closing.md', '.claude/skills/air-presentation/references/critique.md', '.claude/skills/air-presentation/references/storyline.md',
        '.claude/skills/air-referentiel/SKILL.md', '.mcp.json', 'CLAUDE.md'}
    server = json.loads(files['.mcp.json'])['mcpServers']['air']
    assert server['command'] == 'D:/air/.venv/Scripts/python.exe'
    assert server['args'] == ['-m', 'air.mcp', '--home', 'D:/air/.air', '--credential', 'agent.json', '--port', '8740']
    settings = json.loads(files['.claude/settings.json'])
    assert set(result['tools_allowed']) == set(READ_ONLY) and set(result['tools_denied']) == set(CONTRIBUTE + COMMITTING)
    assert all('mcp__air__' + name in settings['permissions']['deny'] for name in COMMITTING)
    assert 'Read(**/credentials.json)' in settings['permissions']['deny']
    assert json.loads(files['.claude/air-adapter.json'])['source_digest'] == result['source_digest']
    assert result['adapter']['support_state'] == 'ADAPTER_DELIVERED' and not result['client_qualified']
    assert not result['secrets_included'] and not result['credential_read'] and not result['server_contacted']


def test_adapter_front_matter_is_loadable_and_grants_the_tools_it_uses(store):
    result = compile_adapter(store, USER, AccessPolicy(), {**ADAPTER, 'access': 'contribute'})
    for item in result['files']:
        if not item['path'].endswith('.md') or not item['content'].startswith('---'): continue
        front = yaml.safe_load(item['content'].split('---')[1])
        assert isinstance(front, dict) and front.get('description')
        declared = front.get('tools') or front.get('allowed-tools')
        if declared is not None: assert {'Read', 'Glob', 'Grep'} <= set(declared), item['path']
    settings = json.loads(contents(result)['.claude/settings.json'])
    assert 'Read(**/.air/**)' in settings['permissions']['deny'] and 'D:/air' not in json.dumps(settings)
    assert next(item['zone'] for item in result['files'] if item['path'] == '.claude/settings.json') == 'GENERATED'


def test_adapter_tool_partition_matches_the_live_catalogue():
    assert sorted(READ_ONLY) == sorted(name for name, value in TOOLS.items() if value[4])
    assert set(READ_ONLY + CONTRIBUTE + COMMITTING) == set(TOOLS)
    assert not set(CONTRIBUTE) & set(COMMITTING)


def test_adapter_contribute_access_keeps_commitment_out(store):
    result = compile_adapter(store, USER, AccessPolicy(), {**ADAPTER, 'access': 'contribute'})
    assert set(result['tools_allowed']) == set(READ_ONLY + CONTRIBUTE) and set(result['tools_denied']) == set(COMMITTING)


def test_adapter_avoids_duplicating_shared_instructions(store):
    shared = contents(compile_adapter(store, USER, AccessPolicy(), {**ADAPTER, 'shared_instructions': 'AGENTS.md'}))['CLAUDE.md']
    standalone = contents(compile_adapter(store, USER, AccessPolicy(), ADAPTER))['CLAUDE.md']
    assert '[AGENTS.md](AGENTS.md)' in shared and '### Règles' not in shared
    assert '### Règles' in standalone and 'AGENTS.md' not in standalone


@pytest.mark.parametrize('fault', ['relative-interpreter', 'credential-path', 'token-in-url', 'plain-http-remote', 'unknown-client'])
def test_adapter_refuses_unsafe_configuration(store, fault):
    request = deepcopy(ADAPTER)
    if fault == 'relative-interpreter': request['server']['interpreter'] = '.venv/Scripts/python.exe'
    if fault == 'credential-path': request['server']['credential'] = '../secret.json'
    if fault == 'token-in-url': request['server']['url'] = 'https://user:secret@air.example.org:8740'
    if fault == 'plain-http-remote': request['server']['url'] = 'http://air.example.org:8740'
    if fault == 'unknown-client': request['client'] = 'unknown-ide'
    with pytest.raises(InvalidModel): compile_adapter(store, USER, AccessPolicy(), request)


def test_generated_files_never_carry_credential_material(store):
    for result in (compile_workspace(store, USER, AccessPolicy(), WORKSPACE), compile_adapter(store, USER, AccessPolicy(), ADAPTER)):
        for item in result['files']:
            assert 'access_token' not in item['content'] and not atelier.TOKEN.search(item['content'])
    with pytest.raises(InvalidModel):
        atelier.no_secret([{'path': 'x.json', 'content': '{"access_token": "value"}'}])


def test_plan_and_apply_preserve_local_work(tmp_path, store):
    adapter = compile_adapter(store, USER, AccessPolicy(), ADAPTER)
    scaffold = compile_workspace(store, USER, AccessPolicy(), WORKSPACE)
    root = tmp_path / 'repo';root.mkdir()
    for result in (scaffold, adapter):
        steps = atelier.plan_files(root, result['files'])
        assert {step['action'] for step in steps} == {'CREATE'}
        assert sorted(atelier.apply_files(root, result['files'], steps)) == sorted(item['path'] for item in result['files'])
        assert {step['action'] for step in atelier.plan_files(root, result['files'])} == {'UNCHANGED'}
    seeded = root / 'README.md';seeded.write_text('# Titre choisi par l’équipe' + chr(10), encoding='utf-8')
    claude = root / 'CLAUDE.md';note = chr(10) + 'Note locale conservée.' + chr(10)
    claude.write_text(claude.read_text(encoding='utf-8') + note, encoding='utf-8')
    generated = root / '.claude/commands/air-dossier.md';generated.write_text('Texte local divergent' + chr(10), encoding='utf-8')
    updated = compile_adapter(store, USER, AccessPolicy(), {**ADAPTER, 'access': 'contribute'})
    steps = {step['path']: step for step in atelier.plan_files(root, updated['files'] + scaffold['files'])}
    assert steps['README.md']['action'] == 'PRESERVED' and steps['CLAUDE.md']['action'] == 'SECTION_UPDATE'
    assert steps['.claude/commands/air-dossier.md']['action'] == 'CONFLICT'
    atelier.apply_files(root, updated['files'] + scaffold['files'], list(steps.values()))
    assert seeded.read_text(encoding='utf-8') == '# Titre choisi par l’équipe' + chr(10)
    assert generated.read_text(encoding='utf-8') == 'Texte local divergent' + chr(10)
    assert claude.read_text(encoding='utf-8').endswith(note) and 'contribute' in claude.read_text(encoding='utf-8')
    atelier.apply_files(root, updated['files'] + scaffold['files'], list(steps.values()), replace_generated=True)
    assert generated.read_text(encoding='utf-8') == contents(updated)['.claude/commands/air-dossier.md']
    assert seeded.read_text(encoding='utf-8') == '# Titre choisi par l’équipe' + chr(10)
    settled = {step['action'] for step in atelier.plan_files(root, updated['files'] + scaffold['files'])}
    assert settled == {'UNCHANGED', 'PRESERVED'} and claude.read_text(encoding='utf-8').endswith(note)


def test_apply_refuses_a_tampered_or_escaping_product(tmp_path, store):
    result = compile_adapter(store, USER, AccessPolicy(), ADAPTER);root = tmp_path / 'repo';root.mkdir()
    tampered = [{**item} for item in result['files']]
    tampered[0] = {**tampered[0], 'content': tampered[0]['content'] + 'ajout'}
    with pytest.raises(InvalidModel, match='checksum'): atelier.plan_files(root, tampered)
    escaping = [{**result['files'][0], 'path': 'ok.md'}, {**result['files'][0], 'path': 'sous/../../escape.md'}]
    with pytest.raises(InvalidModel): atelier.plan_files(root, escaping)
    assert not (tmp_path / 'escape.md').exists()
    unc = deepcopy(ADAPTER);unc['server']['home'] = '//serveur/partage/.air'
    with pytest.raises(InvalidModel, match='network share'): compile_adapter(store, USER, AccessPolicy(), unc)


def test_a_checkout_with_crlf_is_not_a_conflict(tmp_path, store):
    """Git for Windows rewrites line endings on checkout; the products are the same products."""
    result = compile_workspace(store, USER, AccessPolicy(), WORKSPACE);root = tmp_path / 'repo';root.mkdir()
    atelier.apply_files(root, result['files'], atelier.plan_files(root, result['files']))
    for item in result['files']:
        if item['media_type'].startswith('text/') or item['media_type'] == 'application/json':
            (root / item['path']).write_bytes(item['content'].encode('utf-8').replace(b'\n', b'\r\n'))
    steps = atelier.plan_files(root, result['files'])
    assert {step['action'] for step in steps} == {'UNCHANGED'}
    assert any(step.get('line_endings') == 'CRLF_ON_DISK' for step in steps)
    assert '.gitattributes' in {item['path'] for item in result['files']}


def test_plan_names_a_file_blocking_a_generated_directory(tmp_path, store):
    result = compile_adapter(store, USER, AccessPolicy(), ADAPTER);root = tmp_path / 'repo'
    (root / '.claude').mkdir(parents=True);(root / '.claude/skills').write_text('obstacle' + chr(10), encoding='utf-8')
    with pytest.raises(InvalidModel, match='occupies a directory'): atelier.plan_files(root, result['files'])
    assert (root / '.claude/skills').read_text(encoding='utf-8') == 'obstacle' + chr(10)
    assert not (root / '.mcp.json').exists()


def test_plan_reports_a_marked_file_without_its_section(tmp_path, store):
    result = compile_adapter(store, USER, AccessPolicy(), ADAPTER);root = tmp_path / 'repo';root.mkdir()
    (root / 'CLAUDE.md').write_text('# Local seulement\n', encoding='utf-8')
    steps = {step['path']: step for step in atelier.plan_files(root, result['files'])}
    assert steps['CLAUDE.md']['action'] == 'SECTION_APPEND', 'a file without any marker receives the section at its end'
    atelier.apply_files(root, result['files'], list(steps.values()))
    assert (root / 'CLAUDE.md').read_text(encoding='utf-8').startswith('# Local seulement\n\n' + atelier.BEGIN)
    # A file with a lone marker is ambiguous: nothing is appended or replaced, even with --replace-generated.
    (root / 'CLAUDE.md').write_text('# Local seulement\n' + atelier.BEGIN + '\n', encoding='utf-8')
    steps = {step['path']: step for step in atelier.plan_files(root, result['files'])}
    assert steps['CLAUDE.md']['action'] == 'SECTION_MISSING'
    atelier.apply_files(root, result['files'], list(steps.values()), replace_generated=True)
    assert (root / 'CLAUDE.md').read_text(encoding='utf-8') == '# Local seulement\n' + atelier.BEGIN + '\n'


def test_atelier_products_stay_inside_their_bounds():
    with pytest.raises(InvalidModel): atelier.product('../escape.md', 'text/markdown', 'x\n', 'GENERATED')
    with pytest.raises(InvalidModel): atelier.product('a.md', 'text/markdown', 'x' * (atelier.FILE_MAX + 1), 'GENERATED')
    with pytest.raises(InvalidModel): atelier.product('a.md', 'text/markdown', 'sans marqueur\n', 'MARKED_SECTION')
    with pytest.raises(InvalidModel): atelier.collate([atelier.product('a.md', 'text/markdown', 'x\n', 'GENERATED')] * 2)


def test_atelier_api_and_mcp(tmp_path, store):
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    token = store.create_token('atelier-user', 'editor');auth = {'Authorization': 'Bearer ' + token['access_token']}
    expected = compile_adapter(store, store.authenticate(token['access_token'], True), AccessPolicy(), ADAPTER)
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        assert client.post('/v1/ide/adapters', json=ADAPTER, headers=auth).json() == expected
        assert client.post('/v1/workspaces/compile', json=WORKSPACE, headers=auth).json()['engine'] == 'air.workspace/0.28'
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_compile_ide_adapter', 'arguments': ADAPTER}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.status_code == 200 and mcp.json()['result']['structuredContent'] == expected
        assert client.post('/v1/ide/adapters', json=ADAPTER).status_code == 401
        assert client.post('/v1/workspaces/compile', json=WORKSPACE).status_code == 401


@pytest.mark.parametrize('command,request_body', [('ide-setup', ADAPTER), ('workspace-init', WORKSPACE)])
def test_cli_plans_then_applies_without_destroying_local_work(tmp_path, monkeypatch, store, command, request_body):
    import io
    from air import cli
    service = compile_adapter if command == 'ide-setup' else compile_workspace
    result = service(store, USER, AccessPolicy(), request_body)

    class Opener:
        def open(self, request, timeout): return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr(cli, 'client_transport', lambda *args: ('http://127.0.0.1', Opener()))
    (tmp_path / 'credentials.json').write_text(json.dumps({'access_token': 'fictional-test-token'}), encoding='utf-8')
    document = tmp_path / 'request.json';document.write_text(json.dumps(request_body), encoding='utf-8')
    root = tmp_path / 'repo'
    assert cli.main(['--home', str(tmp_path), command, str(document), '--workspace', str(root)]) == 0
    assert list(root.rglob('*.md')) == []
    assert cli.main(['--home', str(tmp_path), command, str(document), '--workspace', str(root), '--apply']) == 0
    for item in result['files']:
        assert (root / item['path']).read_bytes() == item['content'].encode('utf-8')
    assert cli.main(['--home', str(tmp_path), command, str(document), '--workspace', str(root), '--apply']) == 0
    generated = next(item for item in result['files'] if item['zone'] == 'GENERATED')
    (root / generated['path']).write_text('divergence locale' + chr(10), encoding='utf-8')
    assert cli.main(['--home', str(tmp_path), command, str(document), '--workspace', str(root), '--apply']) == 1
    assert (root / generated['path']).read_text(encoding='utf-8') == 'divergence locale' + chr(10)
    assert cli.main(['--home', str(tmp_path), command, str(document), '--workspace', str(root), '--apply', '--replace-generated']) == 0
    assert (root / generated['path']).read_bytes() == generated['content'].encode('utf-8')


def test_cli_refuses_a_workspace_path_outside_its_directory(tmp_path, monkeypatch, store):
    import io
    from air import cli
    result = compile_adapter(store, USER, AccessPolicy(), ADAPTER)
    result['files'][0] = {**result['files'][0], 'path': 'ok.md'}
    result['files'].append({**result['files'][0], 'path': '.claude/../../escape.md'})

    class Opener:
        def open(self, request, timeout): return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr(cli, 'client_transport', lambda *args: ('http://127.0.0.1', Opener()))
    (tmp_path / 'credentials.json').write_text(json.dumps({'access_token': 'fictional-test-token'}), encoding='utf-8')
    document = tmp_path / 'request.json';document.write_text(json.dumps(ADAPTER), encoding='utf-8')
    assert cli.main(['--home', str(tmp_path), 'ide-setup', str(document), '--workspace', str(tmp_path / 'repo'), '--apply']) == 1
    assert not (tmp_path / 'escape.md').exists()
