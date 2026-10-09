from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
import yaml
from air.access import AccessPolicy, Forbidden, ScopedStore
from air.api import create_app
from air.config import Settings
from air.foundation import exact, InvalidModel
from air.ide_adapter import compile_adapter, READ_ONLY
from air.mcp import TOOLS
from air.portfolio import access_policy, compile_portfolio, index_portfolio, _views, CHAIN, PLACEHOLDER_PATH
from air.storage import Conflict
from air.workspace import compile_workspace

SPEC = {'organization': {'name': 'Asteria Industrie', 'urn_prefix': 'asteria', 'namespace_prefix': 'asteria'},
    'portfolio': {'name': 'Portefeuille Asteria', 'description': 'Trois projets et un socle.'},
    'projects': [{'code': 'sav', 'title': 'Portail SAV', 'purpose': 'Réclamations clients.', 'namespace': 'asteria.sav', 'urn_segment': 'sav'},
                 {'code': 'atelier', 'title': 'Atelier connecté', 'purpose': 'Maintenance des machines.', 'namespace': 'asteria.atelier', 'urn_segment': 'atelier'},
                 {'code': 'identites', 'title': 'Identités', 'purpose': 'Cycle de vie des accès.', 'namespace': 'asteria.identites', 'urn_segment': 'identites'}],
    'shared': {'code': 'socle', 'title': 'Socle partagé', 'purpose': 'Objets communs.', 'namespace': 'asteria.shared', 'urn_segment': 'socle'},
    'subjects': [{'subject': 'architect-sav', 'label': 'Architecte SAV', 'projects': ['sav'], 'reviews': ['atelier']},
                 {'subject': 'portfolio-architect', 'projects': ['sav', 'atelier', 'identites'], 'shared_write': True}],
    'profiles': ['air.foundation/0.2', 'air.architecture/0.26'],
    'review': {'independent_review_required': True, 'namespace_policy': 'EXPLICIT'}}
USER = {'subject': 'portfolio-architect', 'role': 'editor'}
COMMON = {'.github/workflows/air-check.yml', '.gitattributes', '.gitignore', 'AGENTS.md', 'README.md', 'air-portfolio.json', 'air-portfolio.request.json',
          'claude-code.example.json', 'docs/charte-pilote.md', 'docs/conventions-portefeuille.md', 'policies/access-policy.json', 'portfolio-index.request.json'}


def contents(result):
    return {item['path']: item['content'] for item in result['files']}


def scope(example, namespace, identity, name, includes=(), revision=1):
    meta = deepcopy(example['meta']);meta.update(id=identity, namespace=namespace, name=name, revision=revision)
    return {'meta': meta, 'body': {'includes': [exact(o) for o in includes], 'excludes': [], 'boundary_description': name}}


def freeze(store, example, identity, namespace, members):
    meta = deepcopy(example['meta']);meta.update(id=identity, type='air.Baseline', namespace=namespace)
    result = store.create_baseline({'meta': meta, 'profile': 'air.foundation/0.2', 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fixture')
    return {**exact(result['baseline']), 'digest': result['digest']}


def two_projects(store, example):
    """Two closed project baselines sharing one socle object at the same revision."""
    shared = scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:common', 'Socle')
    sav = scope(example, 'asteria.sav', 'urn:air:asteria:sav:scope:claims', 'SAV', [shared])
    atelier_scope = scope(example, 'asteria.atelier', 'urn:air:asteria:atelier:scope:inspections', 'Atelier', [shared])
    store.put_bundle([shared, sav, atelier_scope], 'fixture')
    return shared, {'sav': freeze(store, example, 'urn:air:asteria:sav:baseline', 'asteria.sav', [shared, sav]),
                    'atelier': freeze(store, example, 'urn:air:asteria:atelier:baseline', 'asteria.atelier', [shared, atelier_scope])}


def pinned(pins, spec=SPEC):
    return {'portfolio': spec, 'baselines': [{'project': code, 'baseline': pin} for code, pin in sorted(pins.items())]}


def test_scaffold_is_deterministic_bounded_and_writes_nothing(store):
    before = store.counts();result = compile_portfolio(store, USER, AccessPolicy(), SPEC)
    assert result == compile_portfolio(store, USER, AccessPolicy(), SPEC) and store.counts() == before
    files = contents(result)
    per_repository = {'projects/' + code + '/' + name for code in ('sav', 'atelier', 'identites', 'socle') for name in ('README.md', 'workspace.request.json', 'claude-code.example.json')}
    assert set(files) == COMMON | per_repository
    manifest = json.loads(files['air-portfolio.json'])
    assert [p['code'] for p in manifest['projects']] == ['atelier', 'identites', 'sav'] and manifest['shared']['namespace'] == 'asteria.shared'
    assert manifest['single_instance'] and not manifest['federation_implemented'] and not manifest['registry_written']
    assert manifest['subjects'][0] == {'subject': 'architect-sav', 'label': 'Architecte SAV', 'projects': ['sav'], 'reviews': ['atelier'], 'shared_write': False}
    assert json.loads(files['air-portfolio.request.json']) == SPEC and json.loads(files['portfolio-index.request.json']) == {'baselines': []}
    assert not result['registry_written'] and not result['authorization_granted'] and not result['secrets_included'] and result['policy_installable']
    zones = {item['path']: item['zone'] for item in result['files']}
    assert zones['docs/charte-pilote.md'] == 'SEEDED' and zones['portfolio-index.request.json'] == 'SEEDED' and zones['claude-code.example.json'] == 'SEEDED'
    assert zones['policies/access-policy.json'] == 'GENERATED' and zones['projects/socle/workspace.request.json'] == 'GENERATED'
    assert 'asteria.sav' not in files['README.md']
    central = json.loads(files['claude-code.example.json']);project = json.loads(files['projects/sav/claude-code.example.json'])
    assert central['workspace']['kind'] == 'portfolio' and central['server']['credential'] == 'portfolio-architect.json' and central['access'] == 'read-only'
    assert 'kind' not in project['workspace'] and project['server']['credential'] == 'architect-sav.json' and project['access'] == 'contribute'
    assert PLACEHOLDER_PATH in project['server']['interpreter']
    with pytest.raises(InvalidModel):  # the example is not usable before the team writes the workstation paths
        compile_adapter(store, USER, AccessPolicy(), project)


def test_every_repository_request_produces_its_own_coherent_repository(store):
    files = contents(compile_portfolio(store, USER, AccessPolicy(), SPEC))
    for code in ('sav', 'atelier', 'identites', 'socle'):
        request = json.loads(files['projects/' + code + '/workspace.request.json'])
        repository = compile_workspace(store, USER, AccessPolicy(), request)
        assert [d['code'] for d in repository['domains']] == [code]
        dossier = json.loads(contents(repository)['domains/' + code + '/dossier.json'])
        assert dossier['namespace'] == ('asteria.shared' if code == 'socle' else 'asteria.' + code)
        assert dossier['baseline_id'] == 'urn:air:asteria:' + code + ':baseline'


def test_access_policy_is_installable_and_least_privilege(store):
    files = contents(compile_portfolio(store, USER, AccessPolicy(), SPEC))
    document = json.loads(files['policies/access-policy.json']);policy = AccessPolicy(document)
    everything = ['asteria.atelier', 'asteria.identites', 'asteria.sav', 'asteria.shared']
    assert document['subjects']['architect-sav'] == {'read': everything, 'write': ['asteria.sav'], 'review': ['asteria.atelier']}
    assert document['subjects']['portfolio-architect'] == {'read': everything, 'write': everything}
    assert policy.allows({'subject': 'architect-sav', 'role': 'editor'}, 'read', 'asteria.atelier')
    assert policy.allows({'subject': 'architect-sav', 'role': 'editor'}, 'review', 'asteria.atelier')
    assert not policy.allows({'subject': 'architect-sav', 'role': 'editor'}, 'write', 'asteria.shared')
    assert not policy.allows({'subject': 'portfolio-architect', 'role': 'editor'}, 'admit', 'asteria.sav')
    assert not policy.allows({'subject': 'intrus', 'role': 'editor'}, 'read', 'asteria.sav')
    without = {**SPEC, 'subjects': []};example = json.loads(contents(compile_portfolio(store, USER, AccessPolicy(), without))['policies/access-policy.json'])
    assert example['subjects'] == {} and 'x-air-note' in example
    for broken, message in (({'subject': 'x', 'projects': ['absent']}, 'undeclared project'),
                            ({'subject': 'Architect-SAV', 'projects': []}, 'unique'),
                            ({'subject': 'y', 'projects': [], 'reviews': ['absent']}, 'undeclared project')):
        with pytest.raises(InvalidModel, match=message):
            compile_portfolio(store, USER, AccessPolicy(), {**SPEC, 'subjects': SPEC['subjects'] + [broken]})
    with pytest.raises(InvalidModel, match='shared socle'):
        compile_portfolio(store, USER, AccessPolicy(), {k: v for k, v in SPEC.items() if k != 'shared'})
    with pytest.raises(InvalidModel):  # a newline in a subject name would hide a second name in a human review
        compile_portfolio(store, USER, AccessPolicy(), {**SPEC, 'subjects': [{'subject': 'a\nb', 'projects': []}]})
    with pytest.raises(InvalidModel, match='unique'):
        compile_portfolio(store, USER, AccessPolicy(), {**SPEC, 'shared': {**SPEC['shared'], 'namespace': 'asteria.sav'}})


def test_index_reports_agreement_dependencies_chain_and_missing_pins(store, example):
    shared, pins = two_projects(store, example);before = store.counts()
    result = index_portfolio(store, USER, AccessPolicy(), pinned(pins))
    assert result == index_portfolio(store, USER, AccessPolicy(), pinned(pins)) and store.counts() == before
    assert result['result'] == 'REVIEW_REQUIRED' and result['totals'] == {'projects_declared': 3, 'projects_indexed': 2, 'shared_pinned': False,
        'objects_owned': 2, 'objects_referenced': 2, 'distinct_identities': 3, 'shared_identities': 1, 'divergences': 0, 'blocking_gaps': 1,
        'declared_gaps': 0, 'cross_project_gaps': 0, 'stale_dependencies': 0}
    assert [s['status'] for s in result['shared_identities']] == ['AGREEMENT'] and result['shared_identities'][0]['semantic_compatibility'] == 'NOT_EXECUTED'
    assert result['dependencies'] == [{'from': 'atelier', 'to': 'socle', 'references': 1, 'referencing_objects': 1}, {'from': 'sav', 'to': 'socle', 'references': 1, 'referencing_objects': 1}]
    codes = {(g['code'], g.get('project')) for g in result['gaps']}
    assert ('NO_BASELINE_DECLARED', 'identites') in codes and ('CHAIN_TYPE_ABSENT', 'sav') in codes and ('NO_BASELINE_DECLARED', 'socle') not in codes
    entry = next(e for e in result['projects'] if e['code'] == 'sav')
    assert entry['chain']['air.Scope'] == 1 and set(entry['chain_absent']) == set(CHAIN) - {'air.Scope'}  # owned objects only
    assert entry['namespaces'] == ['asteria.sav', 'asteria.shared'] and entry['namespaces_outside_declaration'] == []
    assert entry['objects_owned'] == 1 and entry['objects_referenced'] == 1
    assert entry['referenced_repositories'] == [{'repository': 'socle', 'namespace': 'asteria.shared', 'objects': 1}]
    files = contents(result)
    assert set(files) == {'portfolio-index.json', 'docs/portefeuille.md', 'portfolio-index.manifest.json', 'transformation.json', 'transformation.html'}
    written = json.loads(files['portfolio-index.json'])
    assert written['index_digest'] == result['index_digest'] and 'generator' not in written and 'AGREEMENT' in files['docs/portefeuille.md']
    assert not result['registry_written'] and not result['authorization_granted'] and not result['semantic_compatibility_executed']


def test_index_pins_the_socle_counts_each_reference_once_and_flags_a_misplaced_baseline(store, example):
    shared, pins = two_projects(store, example)
    pins['socle'] = freeze(store, example, 'urn:air:asteria:socle:baseline', 'asteria.shared', [shared])
    result = index_portfolio(store, USER, AccessPolicy(), pinned(pins))
    assert result['totals']['shared_pinned'] and result['totals']['projects_indexed'] == 2
    assert result['shared_identities'][0]['repositories'].keys() == {'atelier', 'sav', 'socle'}
    # A socle object referencing a project object is counted once even though three baselines contain it.
    bridge = scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:bridge', 'Pont', [next(o for o in [store.get('urn:air:asteria:sav:scope:claims', 1)['object']])])
    store.put_bundle([bridge], 'fixture')
    sav_object = store.get('urn:air:asteria:sav:scope:claims', 1)['object']
    wide = {'sav': freeze(store, example, 'urn:air:asteria:sav:baseline-2', 'asteria.sav', [shared, sav_object, bridge]),
            'atelier': freeze(store, example, 'urn:air:asteria:atelier:baseline-2', 'asteria.atelier', [shared, store.get('urn:air:asteria:atelier:scope:inspections', 1)['object'], bridge, sav_object])}
    counted = index_portfolio(store, USER, AccessPolicy(), pinned(wide))
    assert {(d['from'], d['to']): d['references'] for d in counted['dependencies']}[('socle', 'sav')] == 1
    # Objects of another declared repository are a dependency, not a violation: only an undeclared namespace blocks.
    atelier_entry = next(e for e in counted['projects'] if e['code'] == 'atelier')
    assert {r['repository'] for r in atelier_entry['referenced_repositories']} == {'sav', 'socle'}
    assert not any(g['code'] == 'NAMESPACE_OUTSIDE_DECLARATION' for g in counted['gaps'])
    stray = scope(example, 'asteria.unknown', 'urn:air:asteria:unknown:scope:stray', 'Hors déclaration')
    store.put_bundle([stray], 'fixture')
    off = freeze(store, example, 'urn:air:asteria:atelier:baseline-3', 'asteria.atelier',
                 [shared, store.get('urn:air:asteria:atelier:scope:inspections', 1)['object'], stray])
    undeclared = index_portfolio(store, USER, AccessPolicy(), pinned({'atelier': off}))
    assert any(g['code'] == 'NAMESPACE_OUTSIDE_DECLARATION' and g['namespaces'] == ['asteria.unknown'] for g in undeclared['gaps'])
    misplaced = index_portfolio(store, USER, AccessPolicy(), pinned({'atelier': pins['sav']}))
    assert any(g['code'] == 'BASELINE_NAMESPACE_MISMATCH' and g['project'] == 'atelier' and g['baseline_namespace'] == 'asteria.sav' for g in misplaced['gaps'])


def test_index_detects_a_shared_identity_divergence_and_stays_exact(store, example):
    shared, pins = two_projects(store, example)
    revised = scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:common', 'Socle révisé', revision=2)
    atelier_scope = scope(example, 'asteria.atelier', 'urn:air:asteria:atelier:scope:inspections', 'Atelier', [revised], revision=2)
    store.put_bundle([revised, atelier_scope], 'fixture')
    pins['atelier'] = freeze(store, example, 'urn:air:asteria:atelier:baseline-2', 'asteria.atelier', [revised, atelier_scope])
    result = index_portfolio(store, USER, AccessPolicy(), pinned(pins))
    divergence = result['shared_identities'][0]
    assert divergence['status'] == 'DIVERGENCE' and divergence['resolution'] == 'REVIEW_REQUIRED'
    assert divergence['repositories']['sav']['revision'] == 1 and divergence['repositories']['atelier']['revision'] == 2
    assert result['totals']['divergences'] == 1 and any(g['code'] == 'SHARED_IDENTITY_VERSION_DIVERGENCE' for g in result['gaps'])
    assert 'DIVERGENCE' in contents(result)['docs/portefeuille.md']
    with pytest.raises(Conflict):
        index_portfolio(store, USER, AccessPolicy(), pinned({**pins, 'sav': {**pins['sav'], 'digest': 'sha256:' + '0' * 64}}))
    with pytest.raises(InvalidModel, match='undeclared repository'):
        index_portfolio(store, USER, AccessPolicy(), {'portfolio': SPEC, 'baselines': [{'project': 'absent', 'baseline': pins['sav']}]})
    with pytest.raises(InvalidModel, match='twice'):
        index_portfolio(store, USER, AccessPolicy(), {'portfolio': SPEC, 'baselines': [{'project': 'sav', 'baseline': pins['sav']}] * 2})


def test_index_refuses_an_undeclared_subject_and_reads_every_declared_namespace_for_declared_ones(store, example):
    shared, pins = two_projects(store, example)
    policy = AccessPolicy(access_policy(SPEC, *_views(SPEC)))
    with pytest.raises(Forbidden):
        index_portfolio(store, {'subject': 'intrus', 'role': 'editor'}, policy, pinned(pins))
    assert index_portfolio(store, {'subject': 'architect-sav', 'role': 'editor'}, policy, pinned(pins))['totals']['projects_indexed'] == 2
    with pytest.raises(Forbidden):
        ScopedStore(store, {'subject': 'architect-sav', 'role': 'editor'}, policy).put(scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:other', 'Hors mandat'), 'architect-sav')


def test_adapter_portfolio_kind_emits_only_holistic_commands(store):
    request = {'client': 'claude-code', 'workspace': {'name': 'Portefeuille', 'organization': 'Asteria', 'kind': 'portfolio'},
               'server': {'interpreter': 'D:/air/.venv/Scripts/python.exe', 'home': 'D:/air/.air', 'credential': 'agent.json'}, 'access': 'read-only'}
    result = compile_adapter(store, USER, AccessPolicy(), request);files = contents(result)
    assert {p for p in files if p.startswith('.claude/commands/')} == {'.claude/commands/air-portefeuille.md', '.claude/commands/air-relire.md', '.claude/commands/air-impact.md'}
    assert 'air_index_portfolio' in result['tools_allowed']
    front = yaml.safe_load(files['.claude/commands/air-portefeuille.md'].split('---')[1])
    assert 'mcp__air__air_index_portfolio' in front['allowed-tools'] and 'Read' in front['allowed-tools']
    for path in ('.claude/skills/air-referentiel/SKILL.md', '.claude/commands/air-relire.md', '.claude/agents/air-relecteur.md', 'CLAUDE.md'):
        assert 'domains/' not in files[path] and 'déposer' not in files[path], path
    assert 'D:/air' not in files['.claude/settings.json']
    project = compile_adapter(store, USER, AccessPolicy(), {**request, 'workspace': {'name': 'Projet', 'organization': 'Asteria'}})
    assert '.claude/commands/air-portefeuille.md' not in contents(project) and len(project['files']) == 20
    assert {'air_compile_portfolio', 'air_index_portfolio'} <= set(READ_ONLY) <= set(TOOLS)


def test_cli_api_and_mcp_agree_and_the_cli_joins_the_declaration_from_the_central_repository(tmp_path, monkeypatch, store, example):
    import io
    from air import cli
    shared, pins = two_projects(store, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    token = store.create_token('portfolio-architect', 'editor');headers = {'Authorization': 'Bearer ' + token['access_token']}
    principal = store.authenticate(token['access_token'], True)
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        scaffold = client.post('/v1/portfolios/compile', json=SPEC, headers=headers);assert scaffold.status_code == 200, scaffold.text
        assert scaffold.json() == compile_portfolio(store, principal, AccessPolicy(), SPEC)
        index = client.post('/v1/portfolios/index', json=pinned(pins), headers=headers);assert index.status_code == 200, index.text
        assert index.json() == index_portfolio(store, principal, AccessPolicy(), pinned(pins))
        assert client.post('/v1/portfolios/index', json=pinned({'sav': {**pins['sav'], 'digest': 'sha256:' + '1' * 64}}), headers=headers).status_code == 409
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_index_portfolio', 'arguments': pinned(pins)}},
                          headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.json()['result']['structuredContent'] == index.json()
    sent = []

    class Opener:
        def open(self, request, timeout):
            sent.append(json.loads(request.data))
            return io.BytesIO(json.dumps(scaffold.json() if 'projects' in sent[-1] else index.json()).encode())
    monkeypatch.setattr(cli, 'client_transport', lambda *args: ('http://127.0.0.1', Opener()))
    (tmp_path / 'credentials.json').write_text(json.dumps({'access_token': 'fictional-test-token'}), encoding='utf-8')
    spec_file = tmp_path / 'portfolio.json';spec_file.write_text(json.dumps(SPEC), encoding='utf-8')
    root = tmp_path / 'central';pin_file = tmp_path / 'pins.json';pin_file.write_text(json.dumps({'baselines': pinned(pins)['baselines']}), encoding='utf-8')
    assert cli.main(['--home', str(tmp_path), 'portfolio-index', str(pin_file), '--workspace', str(root), '--apply']) == 1  # no declaration yet
    assert cli.main(['--home', str(tmp_path), 'portfolio-init', str(spec_file), '--workspace', str(root), '--apply']) == 0
    assert cli.main(['--home', str(tmp_path), 'portfolio-index', str(pin_file), '--workspace', str(root), '--apply']) == 0
    assert sent[-1]['portfolio'] == SPEC and sent[-1]['baselines'] == pinned(pins)['baselines']
    assert (root / 'docs/portefeuille.md').read_text(encoding='utf-8') == contents(index.json())['docs/portefeuille.md']
    assert json.loads((root / 'portfolio-index.json').read_text(encoding='utf-8'))['index_digest'] == index.json()['index_digest']
    assert cli.main(['--home', str(tmp_path), 'portfolio-index', str(pin_file), '--workspace', str(root), '--apply']) == 0
    assert (root / 'docs/charte-pilote.md').exists() and (root / 'projects/socle/workspace.request.json').exists()
