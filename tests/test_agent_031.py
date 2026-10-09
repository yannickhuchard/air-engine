"""Tranche 31: an architect works a solution architecture through an agent, guided and without guessing.

Each test comes from what an agent session met in the health insurance pilot (pass 3), or from a defect the
tranche-30 review reproduced.
"""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air import agent, artifacts
from air.access import AccessPolicy, Forbidden, NotFound, ScopedStore
from air.api import create_app
from air.architecture import inspect_architecture
from air.architecture_schema import HTTP_MAPPING_030, CHANNEL_MAPPING_030
from air.atelier import appended, apply_files, plan_files, previous_generation, BEGIN
from air.config import Settings
from air.construction import validate_construction
from air.core import ARCHITECTURE_PROFILE, digest, validate
from air.foundation import exact
from air.ide_adapter import compile_adapter
from air.mcp import Session, TOOLS
from air.openapi_compiler import compile_openapi
from air.projections import diff
from test_architecture import prepare as prepare_architecture, find

POLICY = AccessPolicy()


def snapshot_of(request):
    return request['baseline']


def function_revision(objects, **changes):
    """The function at revision 2 with a changed postcondition: the smallest real content change."""
    function = deepcopy(find(objects, 'Function'))
    function['meta']['revision'] = 2
    function['body'].update(changes or {'postconditions': ['Proposal recorded and acknowledged']})
    return function


# ---------------------------------------------------------------- finding the current state

def test_revisions_are_listed_newest_first_and_a_missing_revision_says_what_exists(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    listing = agent.list_revisions(store, user, POLICY, {'id': 'urn:architecture:baseline'})
    assert listing['latest']['revision'] == 1 and listing['latest']['digest'] == request['baseline']['digest']
    assert listing['type'] == 'air.Baseline' and listing['revisions'][0]['members'] == len(objects)
    with pytest.raises(NotFound) as missing:
        ScopedStore(store, user, POLICY).export_baseline({'id': 'urn:architecture:baseline', 'revision': 7})
    assert missing.value.detail['latest_revision'] == 1, 'export and get now agree: not found, and the latest readable revision'
    with pytest.raises(NotFound):
        agent.list_revisions(store, user, POLICY, {'id': 'urn:architecture:never'})
    closed = AccessPolicy({'version': 't', 'subjects': {user['subject']: {'read': ['other.space']}}})
    with pytest.raises(Forbidden):
        agent.list_revisions(store, user, closed, {'id': 'urn:architecture:baseline'})
    hidden = ScopedStore(store, user, closed).missing('urn:architecture:baseline', 7)
    assert 'latest_revision' not in hidden.detail, 'a namespace you cannot read discloses no revision'


def test_the_guide_gives_state_health_and_exact_next_calls_without_a_revision(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    report = agent.guide(store, user, POLICY, {'baseline': {'id': 'urn:architecture:baseline'}})
    assert report['baseline']['revision'] == 1 and report['baseline']['is_latest'] and not report['registry_written']
    health = report['health']
    assert health['reference_closure'] == 'VALID'
    assert set(health['architecture_checks']['families']) == {'EXCLUSIVITY', 'EXHAUSTIVENESS', 'CONTEXT_COHERENCE', 'COMPILABILITY', 'DECLARATION'}
    assert all(row['complete_list'] == (row['count'] <= 25) and len(row['items']) == min(row['count'], 25 if row['count'] <= 25 else 3)
               for row in health['construction']['by_code'])
    assert health['construction'] is not None and all('explanation' in row and 'fix_hint' in row for row in health['construction']['by_code'])
    assert any(step['tool'] == 'air_compile_openapi' and step['arguments']['baseline'] == request['baseline'] for step in report['next_steps'])
    change = agent.guide(store, user, POLICY, {'baseline': {'id': 'urn:architecture:baseline'}, 'intent': 'CHANGE'})
    assert [s['tool'] for s in change['next_steps'] if s['tool']][:6] == ['air_browse_baseline', 'air_describe_type', 'air_validate_drafts',
                                                                          'air_rebase_drafts', 'air_deposit_prepared', 'air_freeze_prepared']


def test_browse_pages_filters_and_inlines_schema_files(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    outline = agent.browse_baseline(store, user, POLICY, {'baseline': {'id': 'urn:architecture:baseline'}, 'limit': 5})
    assert outline['matching'] == len(objects) and len(outline['items']) == 5 and outline['next_offset'] == 5
    assert 'object' not in outline['items'][0] and outline['counts_by_type']['air.TechnicalBinding']['owned'] == 1
    schemas = agent.browse_baseline(store, user, POLICY, {'baseline': request['baseline'], 'types': ['air.DataSchema'], 'schemas': True})
    assert schemas['items'][0]['schema']['status'] == 'INLINED' and schemas['items'][0]['schema']['content']['type'] == 'object'
    found = agent.browse_baseline(store, user, POLICY, {'baseline': request['baseline'], 'text': 'provider', 'fields': 'FULL'})
    assert [i['id'] for i in found['items']] == ['urn:architecture:provider'] and found['items'][0]['object']['body']['kind'] == 'MODULE'


def test_a_schema_file_opens_from_the_reference_the_dossier_carries(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    descriptor = find(objects, 'DataSchema')['body']['artifact']
    lookup = {'artifact': {'id': descriptor['locator'], 'digest': 'sha256:' + descriptor['digest']['value']}}
    assert artifacts.describe(store, user, POLICY, lookup)['artifact_reference'] == descriptor


def test_describe_type_gives_schema_skeleton_and_reference_fields(store):
    described = agent.describe_type(store, None, POLICY, {'type': 'air.Function'})
    assert set(described['skeleton']) == {'meta', 'body'} and described['first_profile'] == 'air.construction/0.4'
    assert 'body/satisfies/[]' in described['reference_fields'] and described['json_schema']['properties']['meta']['properties']['type'] == {'const': 'air.Function'}


# ---------------------------------------------------------------- preparing a change safely

def test_validation_is_a_dry_run_that_finds_the_stale_dependents(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    draft = function_revision(objects)
    report = agent.validate_drafts(store, user, POLICY, {'objects': [draft], 'base': request['baseline']})
    assert report['deposit_ready'] and not report['freeze_ready'] and not report['registry_written']
    assert report['storage'][0]['storage'] == 'NEW_REVISION' and report['storage'][0]['latest_stored_revision'] == 1
    stale = {row['object']['id'] for row in report['candidate']['stale_dependents_sample']}
    assert {'urn:architecture:contract', 'urn:architecture:provider', 'urn:architecture:consumer', 'urn:architecture:case'} <= stale
    assert report['next_steps'][-1]['tool'] == 'air_rebase_drafts'
    assert report['candidate']['construction']['status'] == 'NOT_COMPARABLE_UNTIL_REBASE', 'no fake "resolved" list before the rebase'
    assert store.get('urn:architecture:function', 2) is None, 'nothing was stored'
    broken = deepcopy(draft);broken['body']['satisfies'] = [{'id': 'urn:architecture:ghost', 'revision': 1}]
    refused = agent.validate_drafts(store, user, POLICY, {'objects': [broken]})
    assert not refused['deposit_ready'] and refused['references']['problems'][0]['target'] == {'id': 'urn:architecture:ghost', 'revision': 1}
    conflict = deepcopy(find(objects, 'Function'));conflict['body']['postconditions'] = ['Changed without a new revision']
    assert agent.validate_drafts(store, user, POLICY, {'objects': [conflict]})['storage'][0]['storage'] == 'REVISION_CONFLICT'


def test_rebase_completes_the_change_and_its_baseline_request_freezes_as_is(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    draft = function_revision(objects)
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [draft], 'include_bundle': True})
    ids = {row['id'] for row in rebased['rebased']}
    assert {'urn:architecture:contract', 'urn:architecture:binding', 'urn:architecture:provided', 'urn:architecture:flow'} <= ids, 'the cascade is followed to its end'
    assert rebased['candidate']['valid'] and not rebased['unreachable_references'] and not rebased['registry_written']
    assert rebased['bundle']['content_changes'] == 1 and rebased['bundle']['reference_only_revisions'] == len(ids)
    assert rebased['baseline_request']['meta']['provenance']['method'].startswith('Baseline prepared by air_rebase_drafts: 1 content changes')
    assert rebased['fields_to_review'] == ['baseline_request.meta.name', 'baseline_request.meta.description']
    store.put_bundle(rebased['objects'], 'architect')
    frozen = store.create_baseline(rebased['baseline_request'], 'architect')
    assert frozen['baseline']['meta']['revision'] == 2 and frozen['validation']['valid']
    changes = diff(ScopedStore(store, user, POLICY), {'before': request['baseline'],
                                                        'after': {**exact(frozen['baseline']), 'digest': frozen['digest']}})
    natures = {c['after']['id']: c['nature'] for c in changes['changes'] if c['change'] == 'REPLACE'}
    assert natures['urn:architecture:function'] == 'CONTENT' and natures['urn:architecture:contract'] == 'REFERENCE_ONLY'
    assert changes['summary']['content_changes'] == 1 and changes['summary']['reference_only_changes'] == len(ids)
    after = agent.validate_drafts(store, user, POLICY, {'objects': rebased['objects'], 'base': {**exact(frozen['baseline']), 'digest': frozen['digest']}})
    assert all(row['storage'] == 'UNCHANGED' for row in after['storage'])


def test_validation_shows_the_construction_diagnostic_a_change_introduces_with_its_operation(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    draft = function_revision(objects, effects=[{'kind': 'STATE_CHANGE', 'description': 'Proposal becomes RECORDED'}])
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [draft], 'include_bundle': True})
    report = agent.validate_drafts(store, user, POLICY, {'objects': rebased['objects'], 'base': request['baseline']})
    introduced = report['candidate']['construction']['introduced']
    effect = next(row for row in introduced if row['code'] == 'AIR_CONTRACT_EFFECTS')
    assert effect['operation'] == 'Submit' and effect['path'].endswith('#operations/Submit')
    assert effect['missing_state_effects'] == [{'kind': 'STATE_CHANGE', 'description': 'Proposal becomes RECORDED'}] and effect['fix_hint']


def test_rebase_preserves_deposited_drafts_outside_seed_baseline(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    # An interrupted creation deposited the full bundle but froze only sources.
    exported = store.export_baseline(request['baseline'])
    meta = deepcopy(exported['baseline']['meta']);meta['id'] = 'urn:architecture:seed'
    sources = [o for o in objects if o['meta']['type'] == 'air.Source']
    seed = store.create_baseline({'meta':meta,'profile':ARCHITECTURE_PROFILE,
        'members':[exact(o) for o in sources],'parent_baselines':[]}, 'architect')
    pin = {**exact(seed['baseline']),'digest':seed['digest']}
    draft = function_revision(objects)
    bundle = [deepcopy(o) for o in objects if o['meta']['id'] != draft['meta']['id']] + [draft]
    before = {o['meta']['id']:digest(o) for o in objects}
    rebased = agent.rebase_drafts(store,user,POLICY,None,{'base':pin,'objects':bundle,'include_bundle':True})
    assert rebased['candidate']['valid'] and rebased['prepared_change']
    assert any(r['id'] == 'urn:architecture:contract' and r['to_revision'] == 2 for r in rebased['rebased'])
    validation = agent.validate_drafts(store,user,POLICY,{'prepared_change':rebased['prepared_change']['id']})
    assert validation['deposit_ready'] and validation['freeze_ready']
    again = agent.rebase_drafts(store,user,POLICY,None,{'base':pin,'objects':bundle,'include_bundle':True})
    assert again['prepared_change']['id'] == rebased['prepared_change']['id']
    store.put_bundle(rebased['objects'],'architect')
    frozen = store.create_baseline(rebased['baseline_request'],'architect')
    assert frozen['validation']['valid']
    assert all(digest(store.get(o['meta']['id'],1)['object']) == before[o['meta']['id']] for o in objects)


# ---------------------------------------------------------------- what the agent reads when AIR refuses

def test_refusals_reach_the_agent_with_code_diagnostics_and_hint(store, tmp_path, example):
    relayed = agent.relay_http_error(422, {'detail': {'code': 'AIR_INVALID_MODEL', 'message': 'Invalid draft bundle',
                                                      'report': {'diagnostics': [{'code': 'AIR_SCHEMA', 'path': '0/body', 'message': 'x'}] * 80}}})
    assert relayed['error'] == 'AIR_INVALID_MODEL' and relayed['diagnostics_total'] == 80 and len(relayed['diagnostics']) == 50 and relayed['hint']
    assert agent.relay_http_error(404, {'detail': 'Not Found'}) == {'error': 'AIR_NOT_FOUND', 'http_status': 404, 'hint': agent.HINTS['AIR_NOT_FOUND']}
    assert agent.relay_http_error(500, '<html>proxy text</html>')['error'] == 'AIR_API_REJECTED', 'foreign text is never relayed'
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        missing = client.get('/v1/baselines/' + 'urn:architecture:baseline' + '/revisions/9/export', headers=auth)
        assert missing.status_code == 404 and missing.json()['detail']['latest_revision'] == 1
        got = client.get('/v1/objects/urn:architecture:baseline/revisions/9', headers=auth)
        assert got.status_code == 404 and got.json()['detail']['code'] == 'AIR_NOT_FOUND'
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_export_baseline',
                          'arguments': {'id': 'urn:architecture:baseline', 'revision': 9}}},
                          headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        content = mcp.json()['result']['structuredContent']
        assert mcp.json()['result']['isError'] and content['error'] == 'AIR_NOT_FOUND' and content['latest_revision'] == 1 and 'air_list_revisions' in content['hint']
        guided = client.post('/v1/agent/guide', json={'baseline': {'id': 'urn:architecture:baseline'}}, headers=auth)
        assert guided.status_code == 200 and guided.json()['baseline']['revision'] == 1


def test_invalid_tool_arguments_name_the_field(store):
    session = Session(lambda name, arguments: {})
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 't'}}})
    session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    answer = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_index_portfolio', 'arguments': {'baselines': []}}})
    assert answer['error']['code'] == -32602 and 'portfolio' in answer['error']['message'] and answer['error']['data']['problems']


def test_the_draft_import_tool_schema_is_small_and_points_to_describe_type():
    assert len(json.dumps(TOOLS['air_import_drafts'][1])) < 4000 and 'air_describe_type' in TOOLS['air_import_drafts'][0]
    assert {'air_guide', 'air_list_revisions', 'air_browse_baseline', 'air_describe_type', 'air_validate_drafts', 'air_rebase_drafts'} <= set(TOOLS)


# ---------------------------------------------------------------- checks named after the principles; review defects

def test_checks_carry_their_family_and_a_foreign_baseline_is_not_a_pass(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    report = inspect_architecture(store, user, POLICY, {**request, 'detail': 'SUMMARY'})
    assert report['checks']['families']['EXCLUSIVITY']['principle'].startswith('MECE') and 'declaration' not in report['blocks'][0]
    assert report['checks']['families']['CONTEXT_COHERENCE']['principle'].startswith('DDD')
    meta = deepcopy(example['meta']);meta.update(id='urn:architecture:elsewhere', type='air.Baseline', namespace='other.portfolio')
    foreign = store.create_baseline({'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'probe')
    elsewhere = inspect_architecture(store, user, POLICY, {'baseline': {**exact(foreign['baseline']), 'digest': foreign['digest']}})
    assert elsewhere['checks']['result'] == 'NOTHING_OWNED' and elsewhere['checks']['observations'][-1]['code'] == 'AIR_ARCH_NOTHING_OWNED'


def mapping30(mapping, **extra):
    return {**{k: v for k, v in mapping.items() if k not in ('request_schema', 'request_required')}, 'binding': HTTP_MAPPING_030, **extra}


@pytest.mark.parametrize('routes, fragment', [
    ([('Submit', '/proposals/{id}', ['id']), ('Read', '/proposals/{proposalId}', ['proposalId'])], 'same path'),
    ([('Submit', '/proposals/{id}/lines/{id}', ['id'])], 'appears once'),
])
def test_ambiguous_templated_routes_are_refused(store, tmp_path, example, routes, fragment):
    captured = {}
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding');contract = find(additions, 'SemanticContract')
        if len(routes) > 1: contract['body']['operations'].append({'name': 'Read', 'function': contract['body']['operations'][0]['function']})
        m = binding['body']['schema_mapping'][0]
        binding['body']['schema_mapping'] = [mapping30(m, operation=op, method='GET' if op == 'Read' else 'POST', path=path, response_status='200',
            parameters=[{'name': n, 'in': 'path', 'required': True, 'type': 'string'} for n in names]) for op, path, names in routes]
        captured['binding'] = binding
        raise StopIteration
    with pytest.raises(StopIteration):
        prepare_architecture(store, tmp_path, example, mutate)
    messages = [d['message'] for d in validate(captured['binding'])['diagnostics']]
    assert any(fragment in m for m in messages), messages


def test_a_broker_endpoint_with_credentials_is_refused(store, tmp_path, example):
    captured = {}
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding')
        event = {'id': 'urn:data:event', 'revision': 1}
        binding['body'] = {'contract': binding['body']['contract'], 'protocol': 'KAFKA', 'protocol_version': '3', 'security_binding': binding['body']['security_binding'],
                           'endpoint_template': 'kafka://svc:S3cret@broker.internal:9093',
                           'channel_mapping': [{'binding': CHANNEL_MAPPING_030, 'event': event, 'channel': 'claims.events', 'action': 'PUBLISH',
                                                'message_schema': {'id': 'urn:data:schema', 'revision': 1}, 'ordering': 'NONE', 'delivery': 'AT_LEAST_ONCE'}]}
        captured['binding'] = binding
        raise StopIteration
    with pytest.raises(StopIteration):
        prepare_architecture(store, tmp_path, example, mutate)
    assert 'AIR_BINDING_ENDPOINT' in {d['code'] for d in validate(captured['binding'])['diagnostics']}
    captured['binding']['body']['endpoint_template'] = 'kafka://broker.internal:9093'
    assert 'AIR_BINDING_ENDPOINT' not in {d['code'] for d in validate(captured['binding'])['diagnostics']}


def test_inspection_reads_one_schema_file_once_however_many_mappings_use_it(store, tmp_path, example, monkeypatch):
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding');contract = find(additions, 'SemanticContract')
        base = binding['body']['schema_mapping'][0]
        for n in range(40):
            contract['body']['operations'].append({'name': 'Op' + str(n), 'function': contract['body']['operations'][0]['function']})
        binding['body']['schema_mapping'] += [{**base, 'operation': 'Op' + str(n), 'path': '/proposals/op' + str(n)} for n in range(40)]
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    calls = {'n': 0};real = artifacts.download
    def counted(*args, **kwargs):
        calls['n'] += 1;return real(*args, **kwargs)
    monkeypatch.setattr(artifacts, 'download', counted)
    inspect_architecture(store, user, POLICY, request)
    assert calls['n'] == 1


def test_operation_roles_reach_the_description(store, tmp_path, example):
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding')
        m = binding['body']['schema_mapping'][0]
        binding['body']['schema_mapping'] = [{**m, 'binding': HTTP_MAPPING_030, 'authorization_roles': ['claims-handler']}]
        binding['body']['security_scheme'] = {'kind': 'HTTP_BEARER'}
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    binding = find(objects, 'TechnicalBinding')
    result = compile_openapi(store, user, POLICY, {**request, 'binding': {**exact(binding), 'digest': digest(binding)}, 'info': {'title': 'T', 'version': '1'}})
    operation = json.loads(result['content'])['paths']['/proposals']['post']
    assert operation['security'] == [{'AirDeclaredScheme': ['claims-handler']}] and operation['x-air-authorization-roles'] == ['claims-handler']
    inspected = inspect_architecture(store, user, POLICY, request)
    assert inspected['bindings'][0]['operation_authorization'] == [{'operation': 'Submit', 'roles': ['claims-handler'], 'declared': True}]


def test_diff_compares_lists_by_their_key(store, tmp_path, example):
    from air.projections import changes
    before = {'operations': [{'name': 'Submit', 'x': 1}, {'name': 'Read', 'x': 1}]}
    after = {'operations': [{'name': 'Read', 'x': 2}, {'name': 'Submit', 'x': 1}, {'name': 'Cancel', 'x': 1}]}
    rows = changes(before, after)
    assert {r['path'] for r in rows} == {'/operations/[name=Cancel]', '/operations/[name=Read]/x'}


# ---------------------------------------------------------------- generated agent configuration

SERVER = {'interpreter': 'D:/air/.venv/Scripts/python.exe', 'home': 'D:/air/.air', 'credential': 'architect.json', 'port': 8750}


def test_codex_adapter_enables_the_tools_asks_before_writes_and_carries_the_journeys(store):
    report = compile_adapter(store, None, POLICY, {'client': 'codex', 'workspace': {'name': 'Platform', 'organization': 'Org'},
                                                   'server': SERVER, 'access': 'contribute'})
    files = {f['path']: f['content'] for f in report['files']}
    assert {'.codex/config.toml', 'AGENTS.md', '.agents/skills/air-referentiel/SKILL.md', '.agents/skills/air-proposer/SKILL.md', '.codex/air-adapter.json'} <= set(files)
    config = files['.codex/config.toml']
    assert '[mcp_servers.air]' in config and '"air_guide"' in config and '"air_admission_admit"' not in config
    assert '[mcp_servers.air.tools.air_import_drafts]\napproval_mode = "prompt"' in config
    assert 'air_validate_drafts' in files['.agents/skills/air-proposer/SKILL.md'] and files['.agents/skills/air-proposer/SKILL.md'].startswith('---\nname: air-proposer\n')
    assert report['client'] == 'codex' and not report['client_qualified'] and report['adapter']['journeys'][0] == 'air-dossier'
    readonly = compile_adapter(store, None, POLICY, {'client': 'codex', 'workspace': {'name': 'P', 'organization': 'O'}, 'server': SERVER, 'access': 'read-only'})
    assert 'approval_mode' not in {f['path']: f['content'] for f in readonly['files']}['.codex/config.toml']


def test_claude_adapter_commands_follow_the_guided_journeys(store):
    report = compile_adapter(store, None, POLICY, {'client': 'claude-code', 'workspace': {'name': 'Platform', 'organization': 'Org'},
                                                   'server': SERVER, 'access': 'contribute', 'shared_instructions': 'AGENTS.md'})
    files = {f['path']: f['content'] for f in report['files']}
    assert {'.claude/commands/' + n + '.md' for n in ('air-dossier', 'air-proposer', 'air-relire', 'air-impact', 'air-livrer')} <= set(files)
    assert 'mcp__air__air_guide' in files['.claude/settings.json'] and 'air_rebase_drafts' in files['.claude/commands/air-proposer.md']
    assert 'allowed-tools' not in files['.claude/commands/air-proposer.md'] and 'allowed-tools' in files['.claude/commands/air-relire.md']
    portfolio = compile_adapter(store, None, POLICY, {'client': 'claude-code', 'workspace': {'name': 'P', 'organization': 'O', 'kind': 'portfolio'},
                                                      'server': SERVER, 'access': 'read-only'})
    command = {f['path']: f['content'] for f in portfolio['files']}['.claude/commands/air-portefeuille.md']
    assert '"content": "DIGESTS"' in command and 'air-portfolio.request.json' in command


def test_an_upgrade_replaces_untouched_generated_files_and_keeps_edited_ones(tmp_path, store):
    request = {'client': 'claude-code', 'workspace': {'name': 'Platform', 'organization': 'Org'}, 'server': SERVER, 'access': 'contribute'}
    first = compile_adapter(store, None, POLICY, request)['files']
    apply_files(tmp_path, first, plan_files(tmp_path, first))
    edited = tmp_path / '.claude/commands/air-livrer.md'
    edited.write_text(edited.read_text(encoding='utf-8') + '\nLocal tweak\n', encoding='utf-8')
    second = compile_adapter(store, None, POLICY, {**request, 'access': 'read-only'})['files']
    steps = {s['path']: s['action'] for s in plan_files(tmp_path, second, previous_generation(tmp_path, second))}
    assert steps['.claude/settings.json'] == 'UPGRADE' and steps['.claude/air-adapter.json'] == 'UPGRADE'
    assert steps['CLAUDE.md'] == 'SECTION_UPDATE'
    without_manifest = {s['path']: s['action'] for s in plan_files(tmp_path, second)}
    assert without_manifest['.claude/settings.json'] == 'CONFLICT', 'without the previous record an upgrade and an edit cannot be told apart'


def test_a_marked_section_is_appended_to_instructions_that_have_none(tmp_path, store):
    (tmp_path / 'AGENTS.md').write_text('# Team rules\n\nKeep this line.\n', encoding='utf-8')
    files = compile_adapter(store, None, POLICY, {'client': 'codex', 'workspace': {'name': 'P', 'organization': 'O'}, 'server': SERVER, 'access': 'read-only'})['files']
    steps = plan_files(tmp_path, files)
    assert {s['path']: s['action'] for s in steps}['AGENTS.md'] == 'SECTION_APPEND'
    apply_files(tmp_path, files, steps)
    text = (tmp_path / 'AGENTS.md').read_text(encoding='utf-8')
    assert text.startswith('# Team rules\n\nKeep this line.\n') and text.count(BEGIN) == 1
    assert {s['path']: s['action'] for s in plan_files(tmp_path, files)}['AGENTS.md'] == 'UNCHANGED'


# ---------------------------------------------------------------- portfolio: what the holistic view used to hide

def test_the_index_lists_declared_gaps_stale_borrowings_and_can_omit_file_contents(store, example):
    from test_portfolio import scope, pinned, USER
    from air.portfolio import index_portfolio
    shared = scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:common', 'Socle')
    newer = scope(example, 'asteria.shared', 'urn:air:asteria:socle:scope:common', 'Socle v2', revision=2)
    sav = scope(example, 'asteria.sav', 'urn:air:asteria:sav:scope:claims', 'SAV', [shared])
    gap_meta = deepcopy(example['meta']);gap_meta.update(id='urn:air:asteria:sav:gap:events', namespace='asteria.sav', type='air.ArchitectureGap', name='Canal attendu')
    gap = {'meta': gap_meta, 'body': {'missing_element_kind': 'Event channel', 'affected_scope': exact(shared), 'impact': 'No real-time sensing',
                                      'resolution_owner': 'urn:team:socle'}}
    store.put_bundle([shared, newer, sav, gap], 'fixture')

    def freeze(identity, namespace, members):
        meta = deepcopy(example['meta']);meta.update(id=identity, type='air.Baseline', namespace=namespace)
        result = store.create_baseline({'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fixture')
        return {**exact(result['baseline']), 'digest': result['digest']}
    pins = {'sav': freeze('urn:air:asteria:sav:baseline', 'asteria.sav', [shared, sav, gap]),
            'socle': freeze('urn:air:asteria:socle:baseline', 'asteria.shared', [newer])}
    result = index_portfolio(store, USER, AccessPolicy(), {**pinned(pins), 'content': 'DIGESTS'})
    declared = next(g for g in result['gaps'] if g['code'] == 'DECLARED_ARCHITECTURE_GAP')
    assert declared['project'] == 'sav' and declared['other_repositories'] == ['socle'] and declared['severity'] == 'ATTENTION'
    stale = next(g for g in result['gaps'] if g['code'] == 'BORROWED_BEHIND_OWNER_PIN')
    assert stale['project'] == 'sav' and stale['owner'] == 'socle' and stale['sample'] == ['urn:air:asteria:socle:scope:common']
    assert result['totals']['cross_project_gaps'] == 1 and result['totals']['stale_dependencies'] == 1
    assert set(result['attention']) == {'DECLARED_ARCHITECTURE_GAP', 'BORROWED_BEHIND_OWNER_PIN'}
    assert all('content' not in f and f['content_digest'] for f in result['files'])
    assert result['dependencies'][0]['referencing_objects'] <= result['dependencies'][0]['references']


def test_a_prepared_change_is_deposited_and_frozen_by_reference_by_its_author_only(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [function_revision(objects)]})
    handle = rebased['prepared_change']['id']
    assert [s['tool'] for s in rebased['next_steps'] if s['tool']][:2] == ['air_deposit_prepared', 'air_freeze_prepared']
    assert store.get('urn:architecture:function', 2) is None, 'preparing stores no registry object'
    with pytest.raises(Forbidden):
        agent.deposit_prepared(store, {**user, 'subject': 'someone-else'}, POLICY, {'prepared_change': handle})
    deposited = agent.deposit_prepared(store, user, POLICY, {'prepared_change': handle})
    assert deposited['objects'] == rebased['bundle']['objects'] and deposited['next_steps'][0]['tool'] == 'air_freeze_prepared'
    frozen = agent.freeze_prepared(store, user, POLICY, {'prepared_change': handle, 'name': 'Acknowledged proposals', 'description': 'Proposals are acknowledged'})
    assert frozen['baseline']['revision'] == 2 and frozen['validation']['valid']
    assert store.get('urn:architecture:baseline', 2)['object']['meta']['description'] == 'Proposals are acknowledged'
    reader = AccessPolicy({'version': 't', 'subjects': {user['subject']: {'read': ['*']}}})
    assert agent.rebase_drafts(store, user, reader, None, {'base': {**exact(store.get('urn:architecture:baseline', 2)['object']), 'digest': frozen['baseline']['digest']},
                                                           'objects': [function_revision(objects, postconditions=['Third'])]})['prepared_change'] is None


def test_errors_sharing_a_status_are_all_described(store, tmp_path, example):
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding');contract = find(additions, 'SemanticContract')
        failures = []
        for code in ('ClaimOnFraudHold', 'InvalidStateTransition'):
            failure = deepcopy(contract);failure['meta'].update(id='urn:architecture:failure-' + code.lower(), type='air.FailureMode', name=code)
            failure['body'] = {'trigger': code, 'effect': 'Command refused', 'detection': 'Checked first', 'response': 'Problem details', 'recovery_condition': 'None'}
            failures.append(failure)
        additions.extend(failures)
        contract['body']['error_contract'] = [{'code': f['meta']['name'], 'failure_mode': exact(f), 'response': 'HTTP 409'} for f in failures]
        m = binding['body']['schema_mapping'][0]
        binding['body']['schema_mapping'] = [{**m, 'binding': HTTP_MAPPING_030, 'errors': [{'code': f['meta']['name'], 'status': '409', 'response_schema': m['response_schema']} for f in failures]}]
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    binding = find(objects, 'TechnicalBinding')
    result = compile_openapi(store, user, POLICY, {**request, 'binding': {**exact(binding), 'digest': digest(binding)}, 'info': {'title': 'T', 'version': '1'}})
    conflict = json.loads(result['content'])['paths']['/proposals']['post']['responses']['409']
    assert conflict['x-air-error-codes'] == ['ClaimOnFraudHold', 'InvalidStateTransition'] and len(conflict['x-air-failure-modes']) == 2
    assert 'ClaimOnFraudHold' in conflict['description'] and 'InvalidStateTransition' in conflict['description']
    shared = next(loss for loss in result['losses'] if loss['code'] == 'ERROR_STATUS_SHARED')
    assert shared['responses'] == [{'operation': 'Submit', 'status': '409', 'error_codes': ['ClaimOnFraudHold', 'InvalidStateTransition']}]


def test_describe_type_publishes_the_expression_operators_for_lifecycles(store):
    described = agent.describe_type(store, None, POLICY, {'type': 'air.StateMachine'})
    assert described['expression_language']['operators']['lte'] == 2 and 'every' in described['expression_language']['nodes']['quantifier']['op']
    assert 'expression_language' not in agent.describe_type(store, None, POLICY, {'type': 'air.Function'})


def test_undeclared_roles_and_silent_events_are_observed(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    checks = inspect_architecture(store, user, POLICY, request)['checks']
    codes = {o['code']: o for o in checks['observations']}
    assert codes['AIR_ARCH_OPERATION_ROLES_UNDECLARED']['operations'] == ['Submit']
    assert codes['AIR_ARCH_EVENT_WITHOUT_CHANNEL']['family'] == 'DECLARATION'



def test_an_oversized_answer_is_named_as_such_with_a_useful_hint(store):
    from air.atelier import product
    from air.foundation import TooLarge
    with pytest.raises(TooLarge) as refusal:
        product('big.json', 'application/json', 'x' * 70000, 'GENERATED')
    relayed = agent.error_from_exception(refusal.value)
    assert relayed['error'] == 'AIR_OUTPUT_TOO_LARGE' and '70000 bytes' in relayed['message'] and 'DIGESTS' in relayed['hint']
    assert product('big.json', 'application/json', 'x' * 70000, 'GENERATED', max_size=2 ** 21)['size'] == 70000


def test_revisions_of_a_baseline_say_who_froze_them_and_whether_they_were_reviewed(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    baseline = store.get('urn:architecture:baseline', 1)
    namespace = baseline['object']['meta']['namespace']
    target = {'id': 'urn:architecture:baseline', 'revision': 1, 'digest': baseline['digest']}
    store.record_once('urn:air:review:' + 'a' * 64, 'review', namespace, 'independent-reviewer',
                      {'request': {'target': target, 'expires_at': '2027-01-01T00:00:00Z'}, 'authorization_granted': False})
    listing = agent.list_revisions(store, user, POLICY, {'id': 'urn:architecture:baseline'})
    latest = listing['latest']
    assert latest['reviews'] == [{'receipt': 'urn:air:review:' + 'a' * 64, 'reviewer': 'independent-reviewer', 'revision': 1,
                                  'digest': baseline['digest'], 'recorded_at': latest['reviews'][0]['recorded_at'],
                                  'expires_at': '2027-01-01T00:00:00Z', 'revoked': False}]
    assert latest['recorded_by'] and 'admission' in listing['review_note']


def test_the_review_guide_names_the_parent_and_what_the_change_introduced(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    draft = function_revision(objects, effects=[{'kind': 'STATE_CHANGE', 'description': 'Proposal becomes RECORDED'}])
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [draft], 'include_bundle': True})
    agent.deposit_prepared(store, user, POLICY, {'prepared_change': rebased['prepared_change']['id']})
    agent.freeze_prepared(store, user, POLICY, {'prepared_change': rebased['prepared_change']['id'], 'description': 'Recording effect'})
    review = agent.guide(store, user, POLICY, {'baseline': {'id': 'urn:architecture:baseline'}, 'intent': 'REVIEW'})
    since = review['health']['since_parent']
    assert since['parent'] == request['baseline'] and review['next_steps'][0]['arguments']['before'] == request['baseline']
    assert [d['code'] for d in since['construction']['introduced']] == ['AIR_CONTRACT_EFFECTS']
    assert agent.list_revisions(store, user, POLICY, {'id': 'urn:architecture:baseline'})['latest']['description'] == 'Recording effect'


def test_diff_names_the_schema_properties_a_new_file_adds(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test')
    schema_obj = find(objects, 'DataSchema')
    descriptor = schema_obj['body']['artifact']
    manifest = store.get_record(descriptor['locator'])
    from air.packages import reference as manifest_reference
    old = json.loads(artifacts.download(store, user, POLICY, {'artifact': manifest_reference(manifest)})[1])
    old['properties']['reopenedAt'] = {'type': 'string', 'format': 'date-time'}
    put = artifacts.put(store, user, POLICY, settings, {'idempotency_key': 'schema-v2', 'namespace': 'tests.data_artifacts', 'media_type': 'application/json'},
                        json.dumps(old).encode())
    revised = deepcopy(schema_obj);revised['meta']['revision'] = 2;revised['body']['artifact'] = put['artifact_reference']
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [revised], 'include_bundle': True})
    agent.deposit_prepared(store, user, POLICY, {'prepared_change': rebased['prepared_change']['id']})
    frozen = agent.freeze_prepared(store, user, POLICY, {'prepared_change': rebased['prepared_change']['id']})
    changes = diff(ScopedStore(store, user, POLICY), {'before': request['baseline'], 'after': frozen['baseline']})
    entry = next(c for c in changes['changes'] if c.get('after', {}).get('id') == schema_obj['meta']['id'])
    assert entry['schema_changes'] == {'added': ['/reopenedAt'], 'removed': [], 'changed': []}


def test_a_consumer_project_realigns_on_the_owner_latest_revisions_and_deposits_without_writing_there(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    owner_namespace = find(objects, 'Function')['meta']['namespace']
    # the consumer project borrows the architecture and owns one scope that points at the contract
    contract = find(objects, 'SemanticContract')
    meta = deepcopy(example['meta']);meta.update(id='urn:consumer:scope', namespace='other.project', name='Consumer scope')
    own = {'meta': meta, 'body': {'includes': [exact(contract)], 'excludes': [], 'boundary_description': 'Uses the proposal contract'}}
    store.put_bundle([own], 'consumer')
    meta = deepcopy(example['meta']);meta.update(id='urn:consumer:baseline', type='air.Baseline', namespace='other.project')
    base = store.create_baseline({'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in objects + [own]], 'parent_baselines': []}, 'consumer')
    consumer = {**exact(base['baseline']), 'digest': base['digest']}
    # the owner changes its function and freezes the complete change
    owned = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [function_revision(objects)]})
    agent.deposit_prepared(store, user, POLICY, {'prepared_change': owned['prepared_change']['id']})
    agent.freeze_prepared(store, user, POLICY, {'prepared_change': owned['prepared_change']['id']})
    guide = agent.guide(store, user, POLICY, {'baseline': consumer, 'intent': 'IMPACT'})
    assert guide['health']['borrowed_objects_behind_latest']['count'] > 0
    assert guide['health']['borrowed_alignment'][owner_namespace]['matching_baselines'][0]['revision'] == 1
    assert any(s['tool'] == 'air_rebase_drafts' and s['arguments'] == {'base': consumer, 'realign_borrowed': True} for s in guide['next_steps'])
    consumer_policy = AccessPolicy({'version': 't', 'subjects': {user['subject']: {'read': ['*'], 'write': ['other.project']}}})
    realigned = agent.rebase_drafts(store, user, consumer_policy, None, {'base': consumer, 'realign_borrowed': True})
    assert realigned['candidate']['valid'] and not realigned['borrowed_conflicts'] and realigned['bundle']['content_changes'] == 0
    assert [r['id'] for r in realigned['rebased']] == ['urn:consumer:scope'] and realigned['bundle']['borrowed_repins'] >= 2
    assert not realigned['bundle_included'] and {o['role'] for o in realigned['objects']} == {'BORROWED_REPIN', 'REFERENCE_ONLY'}
    dry = agent.validate_drafts(store, user, consumer_policy, {'objects': [store.get(o['id'], o['revision'])['object'] if o['role'] == 'BORROWED_REPIN'
                                                                             else None for o in realigned['objects'] if o['role'] == 'BORROWED_REPIN'], 'base': consumer})
    assert dry['forbidden_namespaces'] == [] and dry['borrowed_repins'] >= 2, 'stored borrowed revisions are pins, not writes'
    deposited = agent.deposit_prepared(store, user, consumer_policy, {'prepared_change': realigned['prepared_change']['id']})
    assert deposited['created'] == 1, 'only the consumer scope is written'
    frozen = agent.freeze_prepared(store, user, consumer_policy, {'prepared_change': realigned['prepared_change']['id']})
    after = agent.guide(store, user, consumer_policy, {'baseline': frozen['baseline']})
    assert after['health']['borrowed_objects_behind_latest']['count'] == 0
    assert after['health']['borrowed_alignment'][owner_namespace]['matching_baselines'][0]['revision'] == 2


def test_preparing_twice_returns_the_same_change_and_it_can_be_validated_by_reference(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    draft = function_revision(objects, effects=[{'kind': 'STATE_CHANGE', 'description': 'Proposal becomes RECORDED'}])
    first = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [draft]})
    second = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [draft], 'include_bundle': True})
    assert first['prepared_change']['id'] == second['prepared_change']['id']
    introduced = first['candidate']['construction']['introduced']
    assert [(r['code'], r['owner']) for r in introduced] == [('AIR_CONTRACT_EFFECTS', 'THIS_PROJECT')]
    checked = agent.validate_drafts(store, user, POLICY, {'prepared_change': first['prepared_change']['id']})
    assert checked['deposit_ready'] and checked['freeze_ready'] and [s['tool'] for s in checked['next_steps']] == ['air_deposit_prepared', 'air_freeze_prepared']
    early = agent.validate_drafts(store, user, POLICY, {'objects': [draft], 'base': request['baseline']})
    assert early['candidate']['architecture'] == {'status': 'NOT_COMPARABLE_UNTIL_REBASE', 'reason': early['candidate']['construction']['reason']}
