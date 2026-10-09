from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air import business_paths
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import DELIVERY_PROFILE, digest, reference_slots
from air.foundation import exact, InvalidModel
from air.storage import Conflict

POLICY = AccessPolicy()
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def design(store):
    manifest = json.loads((ROOT / 'fixtures/enterprise/asteria/manifest.json').read_text(encoding='utf-8'))
    case = manifest['dossiers'][0]
    members = json.loads((ROOT / 'fixtures/enterprise/asteria' / case['construction']).read_text(encoding='utf-8'))
    own = [o for o in members if o['meta']['namespace'] != 'asteria.shared']
    find = lambda k: next(o for o in own if o['meta']['type'] == 'air.' + k)
    scope, function, actor, original_contract = (find(k) for k in ['Scope', 'Function', 'Actor', 'SemanticContract'])
    def obj(kind, suffix, name, body):
        return {'meta': {**deepcopy(scope['meta']), 'id': 'urn:paths:' + suffix, 'type': 'air.' + kind, 'name': name, 'description': name}, 'body': body}
    workflow = obj('Workflow', 'address', 'Adresse de correspondance', {'steps': [
        {'binding': 'air.workflow-step/0.22', 'id': s, 'name': name, 'function': exact(function), 'participants': [exact(actor)]}
        for s, name in [('submit', 'Recevoir l’adresse'), ('review', 'Contrôler la demande'), ('accept', 'Préparer la mise à jour'), ('reject', 'Expliquer le refus')]],
        'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'a', 'source': 'submit', 'target': 'review', 'condition': 'Demande reçue'},
                  {'binding': 'air.workflow-flow/0.32', 'id': 'b', 'source': 'review', 'target': 'accept', 'condition': 'Recevable',
                   'guard': {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': {'literal': {'type': 'Boolean', 'value': False}}}},
                  {'binding': 'air.workflow-flow/0.22', 'id': 'c', 'source': 'review', 'target': 'reject', 'condition': 'Non recevable'}],
        'start_steps': ['submit'], 'termination_policy': 'Une proposition ou un refus expliqué', 'compensations': [exact(function)]})
    block = obj('ArchitectureBlock', 'component', 'Gestion des correspondances', {'kind': 'MODULE', 'responsibilities': ['Préparer les changements'],
        'functions': [exact(function)], 'provided_contracts': [exact(original_contract)], 'required_contracts': [], 'owned_state': []})
    added = [workflow, block];store.put_bundle(members + added, 'fictional-design')
    def freeze(objects, suffix):
        meta = {**deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Scope')['meta']), 'id': 'urn:paths:baseline:' + suffix, 'type': 'air.Baseline'}
        b = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
        return {**exact(b['baseline']), 'digest': b['digest']}
    pin = freeze(members + added, 'address')
    user = {'subject': 'paths-reader', 'role': 'reader'}
    request = {'baselines': [pin], 'start': {'baseline': pin, 'object': exact(workflow)}}
    return members + added, workflow, block, freeze, user, request


def test_branch_guards_sources_and_associations_do_not_execute(store, design):
    objects, wf, block, _, user, request = design
    before = store.counts();report = business_paths.query_paths(store, user, POLICY, request)
    assert report == business_paths.query_paths(store, user, POLICY, request)
    result = report['result'];workflow = result['workflows'][0]
    assert [p['steps'] for p in workflow['paths']] == [['submit', 'review', 'accept'], ['submit', 'review', 'reject']]
    assert workflow['flows'][1]['guard']['ast']['literal']['value'] is False, 'False guard is retained; not evaluated as a real path'
    assert not result['conditions_evaluated'] and not result['causality_verified'] and not result['business_execution_performed']
    assert result['status'] == 'PARTIAL_DECLARATIONS' and store.counts() == before
    assert {'COMPENSATION_ORDER_UNDECLARED', 'CONDITION_NOT_FORMALIZED', 'COMPONENT_DATA_FLOW_UNDECLARED'} <= {g['code'] for g in result['gaps']}
    refs = {(o['meta']['id'], o['meta']['revision']): o for o in objects}
    for edge in result['context_graph']['edges']:
        evidence = edge['evidence'];assert evidence['digest'] == digest(refs[(evidence['id'], evidence['revision'])])
        assert edge['kind'] in ['REFERENCE', 'REALIZATION', 'OPERATION_BINDING']


def test_search_is_lexical_and_ambiguity_never_guesses(store, design):
    objects, wf, _, freeze, user, request = design;pin = request['baselines'][0]
    found = business_paths.query_paths(store, user, POLICY, {'baselines': [pin], 'query': 'donne moi le chemin de l’adresse de correspondance'})
    assert found['result']['root']['reference']['id'] == wf['meta']['id']
    twin = deepcopy(wf);twin['meta']['id'] += ':second';store.put_bundle([twin], 'fixture')
    other = freeze(objects + [twin], 'ambiguous')
    ambiguous = business_paths.query_paths(store, user, POLICY, {'baselines': [other], 'query': 'adresse correspondance'})
    assert ambiguous['status'] == 'AMBIGUOUS' and ambiguous['candidate_count'] == 2 and ambiguous['result'] is None
    absent = business_paths.query_paths(store, user, POLICY, {'baselines': [pin], 'query': 'opportunité partenaire'})
    assert absent['status'] == 'NOT_FOUND'
    with pytest.raises(InvalidModel): business_paths.query_paths(store, user, POLICY, {'baselines': [pin], 'query': 'donne moi le chemin'})


def test_two_revisions_and_dossiers_are_not_merged(store, design):
    objects, wf, _, freeze, user, request = design;old = request['baselines'][0]
    new = deepcopy(wf);new['meta']['revision'] = 2;new['meta']['description'] = 'Variante cible';new['body']['termination_policy'] = 'Revue cible'
    store.put_bundle([new], 'fixture');pin = freeze([o for o in objects if exact(o) != exact(wf)] + [new], 'target')
    query = {'baselines': [old, pin], 'query': 'adresse correspondance'}
    ambiguous = business_paths.query_paths(store, user, POLICY, query)
    assert ambiguous['status'] == 'AMBIGUOUS' and {c['reference']['revision'] for c in ambiguous['candidates']} == {1, 2}
    for baseline, root, termination in [(old, wf, wf['body']['termination_policy']), (pin, new, 'Revue cible')]:
        result = business_paths.query_paths(store, user, POLICY, {'baselines': [old, pin], 'start': {'baseline': baseline, 'object': exact(root)}})['result']
        assert result['workflows'][0]['termination_policy'] == termination
        assert len(result['workflows']) == 1
    with pytest.raises(InvalidModel): business_paths.query_paths(store, user, POLICY, {**request, 'start': {'baseline': pin, 'object': exact(new)}})


def test_pinned_digest_and_authorization_fail_closed(store, design):
    _, _, _, _, user, request = design
    bad = deepcopy(request);bad['baselines'][0]['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): business_paths.query_paths(store, user, POLICY, bad)
    with pytest.raises(Forbidden): business_paths.query_paths(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)
    with pytest.raises(InvalidModel): business_paths.query_paths(store, user, POLICY, {**request, 'query': 'adresse'})
    missing = deepcopy(request);missing['start']['object']['revision'] = 999
    with pytest.raises(InvalidModel): business_paths.query_paths(store, user, POLICY, missing)


def test_cycles_unreachable_parallel_and_limits(design):
    objects, wf, _, _, _, request = design
    wf = deepcopy(wf);wf['body']['steps'][1].update(binding='air.workflow-step/0.35', join='ALL')
    wf['body']['flows'].append({'binding': 'air.workflow-flow/0.22', 'id': 'loop', 'source': 'accept', 'target': 'review', 'condition': 'Retry'})
    isolated = deepcopy(wf['body']['steps'][0]);isolated['id'] = 'isolated';wf['body']['steps'].append(isolated)
    exported = {'objects': [wf if exact(o) == exact(wf) else o for o in objects]}
    report = business_paths.project_path(exported, exact(wf))
    assert any(p['outcome'] == 'CYCLE' for p in report['workflows'][0]['paths'])
    assert report['workflows'][0]['unreachable_steps'] == ['isolated']
    assert 'PARALLEL_JOIN_REQUIRES_SIMULATION' in {g['code'] for g in report['gaps']}
    limited = business_paths.project_path(exported, exact(wf), max_nodes=8, max_depth=1, max_paths=1, max_steps=2)
    assert limited['context_graph']['truncated'] and limited['workflows'][0]['paths_truncated']
    assert len(limited['workflows'][0]['paths']) <= 1


def test_http_mcp_cli_and_client_catalogues_share_service(store, tmp_path, design, monkeypatch, capsys):
    from air import cli
    from air.mcp import PROTOCOL
    from air.ide_adapter import GUIDED
    _, _, _, _, user, request = design
    token = store.create_token(user['subject'], 'reader')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    expected = business_paths.query_paths(store, user, POLICY, request)
    assert 'air_query_business_paths' in GUIDED
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        response = client.post('/v1/business-paths/query', json=request, headers=headers)
        assert response.status_code == 200 and response.json() == expected
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_query_business_paths', 'arguments': request}},
            headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL}).json()['result']
        assert not result['isError'] and result['structuredContent'] == expected
        assert client.post('/v1/business-paths/query', json=request).status_code == 401
    path = tmp_path / 'request.json';path.write_text(json.dumps(request), encoding='utf-8')
    from air.config import write_private
    write_private(tmp_path / 'credentials.json', token)
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return json.dumps(expected).encode()
    class Opener:
        def open(self, request, **kwargs): calls.append(request);return Response()
    monkeypatch.setattr(cli, 'resolve_transport', lambda args: ('http://127.0.0.1:8740', None))
    monkeypatch.setattr(cli, 'client_transport', lambda *args: ('http://127.0.0.1:8740', Opener()))
    assert cli.main(['--home', str(tmp_path), 'business-paths', str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == expected
    assert calls[0].full_url.endswith('/v1/business-paths/query') and json.loads(calls[0].data) == request


def test_missing_flow_does_not_create_one_from_a_connection(design):
    objects, wf, block, _, _, _ = design
    result = business_paths.project_path({'objects': objects}, exact(wf))
    assert result['data_flows'] == []
    assert not any(e['kind'] == 'DECLARED_DATA_FLOW' for e in result['context_graph']['edges'])


def test_declared_data_flow_keeps_direction_evidence_and_schema(design):
    objects, wf, block, _, _, _ = design
    second = deepcopy(block);second['meta']['id'] += ':destination'
    schema = {'meta': {**deepcopy(block['meta']), 'id': 'urn:paths:schema', 'type': 'air.DataSchema'},
              'body': {'represents': [], 'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': {'locator': 'urn:artifact:retained'}, 'compatibility_policy': 'review'}}
    flow = {'meta': {**deepcopy(block['meta']), 'id': 'urn:paths:flow', 'type': 'air.DataFlow'},
            'body': {'source': exact(block), 'destination': exact(second), 'schema': exact(schema), 'purpose': 'Proposition', 'transformations': [], 'controls': []}}
    result = business_paths.project_path({'objects': objects + [second, schema, flow]}, exact(wf))
    edge = next(e for e in result['context_graph']['edges'] if e['kind'] == 'DECLARED_DATA_FLOW')
    assert edge['source'] == exact(block) and edge['target'] == exact(second) and edge['evidence']['digest'] == digest(flow)
    assert result['data_flows'][0]['declared']['schema'] == exact(schema)
    assert not result['causality_verified']


def test_one_unauthorized_baseline_prevents_partial_discovery(store, design):
    objects, wf, _, freeze, user, request = design
    foreign = deepcopy(objects)
    for o in foreign:
        o['meta']['id'] += ':private'
        o['meta']['namespace'] = 'other.private'
        for _, ref, _ in reference_slots(o): ref['id'] += ':private'
    store.put_bundle(foreign, 'fixture');pin = freeze(foreign, 'private')
    policy = AccessPolicy({'version': 'one-project', 'subjects': {user['subject']: {'read': sorted({o['meta']['namespace'] for o in objects})}}})
    with pytest.raises(Forbidden): business_paths.query_paths(store, user, policy, {'baselines': [request['baselines'][0], pin], 'query': 'adresse'})
