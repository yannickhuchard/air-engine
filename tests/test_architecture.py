from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.architecture import inspect_architecture
from air.config import Settings
from air.core import ARCHITECTURE_PROFILE, GOVERNANCE_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict
from test_data import prepare as prepare_data


def prepare(store, tmp_path, example, mutate=None):
    settings, user, token, objects, request = prepare_data(store, tmp_path, example)
    find = lambda kind: next(o for o in objects if o['meta']['type'] == 'air.' + kind)
    scope, actor, schema, entity = find('Scope'), find('Actor'), find('DataSchema'), find('DataEntity')
    def obj(kind, name, body):
        meta = deepcopy(example['meta']);meta.update(id='urn:architecture:' + name, type='air.' + kind, name=name)
        return {'meta': meta, 'body': body}
    ref = lambda name: {'id': 'urn:architecture:' + name, 'revision': 1}
    source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': 'urn:fiction:architecture', 'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'test', 'retention_policy': 'test'})
    requirement = obj('Requirement', 'requirement', {'statement': 'Submit a proposal', 'kind': 'FUNCTIONAL', 'priority': 'MUST', 'applicability': 'Declared scope', 'acceptance': [ref('criterion')], 'source': [exact(source)]})
    criterion = obj('AcceptanceCriterion', 'criterion', {'condition': 'Proposal recorded', 'verification_method': 'TEST', 'acceptance_authority': 'urn:person:reviewer', 'cases': [ref('case')]})
    function = obj('Function', 'function', {'kind': 'SOFTWARE', 'inputs': [], 'outputs': [], 'preconditions': [], 'postconditions': ['Proposal recorded'], 'effects': [], 'exceptions': [], 'atomic': True, 'satisfies': [exact(requirement)]})
    case = obj('VerificationCase', 'case', {'target': exact(function), 'method': 'TEST', 'inputs': [], 'oracle': 'Proposal recorded', 'acceptance': 'Matches contract', 'independence_basis': 'Separate reviewer'})
    contract = obj('SemanticContract', 'contract', {'operations': [{'name': 'Submit', 'function': exact(function)}], 'participants': [{'actor': exact(actor), 'role': 'requester'}], 'authorization': 'Independent authorization required', 'state_effects': [], 'error_contract': [], 'quality': [], 'compatibility_policy': 'Review exact changes'})
    control = obj('Control', 'control', {'objective': 'Review before use', 'mechanism': 'Independent review', 'scope': exact(scope), 'owner': 'urn:person:owner', 'verification': [exact(case)], 'evidence_requirements': ['Exact review']})
    provider = obj('ArchitectureBlock', 'provider', {'kind': 'MODULE', 'responsibilities': ['Receive proposals', 'Preserve traceability'], 'functions': [exact(function)], 'provided_contracts': [exact(contract)], 'required_contracts': [], 'owned_state': [exact(entity)]})
    consumer = obj('ArchitectureBlock', 'consumer', {'kind': 'ADAPTER', 'responsibilities': ['Submit proposals'], 'functions': [exact(function)], 'provided_contracts': [], 'required_contracts': [exact(contract)], 'owned_state': []})
    binding = obj('TechnicalBinding', 'binding', {'contract': exact(contract), 'protocol': 'HTTP', 'protocol_version': '1.1', 'endpoint_template': 'https://example.invalid/api',
        'schema_mapping': [{'binding': 'air.http-json-mapping/0.26', 'operation': 'Submit', 'method': 'POST', 'path': '/proposals', 'request_schema': exact(schema), 'request_required': True, 'response_schema': exact(schema), 'response_status': '202'}], 'security_binding': [exact(control)]})
    provided = obj('Port', 'provided', {'block': exact(provider), 'direction': 'PROVIDED', 'contract': exact(contract), 'bindings': [exact(binding)]})
    required = obj('Port', 'required', {'block': exact(consumer), 'direction': 'REQUIRED', 'contract': exact(contract), 'bindings': [exact(binding)]})
    flow = obj('DataFlow', 'flow', {'source': exact(required), 'destination': exact(provided), 'schema': exact(schema), 'purpose': 'Submit proposal', 'transformations': [], 'controls': [exact(control)]})
    output = obj('RequiredOutput', 'output', {'expected_artifact': 'Reviewed adapter', 'acceptance': [exact(criterion)], 'due_gate': 'construction-review'})
    gap = obj('ArchitectureGap', 'gap', {'missing_element_kind': 'Implemented adapter', 'affected_scope': exact(scope), 'impact': 'No external call possible', 'resolution_owner': 'urn:person:owner', 'required_output': exact(output)})
    additions = [source, requirement, criterion, function, case, contract, control, provider, consumer, binding, provided, required, flow, output, gap]
    if mutate: mutate(additions)
    store.put_bundle(additions, 'fixture');objects += additions
    meta = deepcopy(example['meta']);meta.update(id='urn:architecture:baseline', type='air.Baseline')
    base = store.create_baseline({'meta': meta, 'profile': ARCHITECTURE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    return objects, user, token, {'baseline': {**exact(base['baseline']), 'digest': base['digest']}}


def find(objects, kind): return next(o for o in objects if o['meta']['type'] == 'air.' + kind)


def test_architecture_is_pure_exact_and_declared(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);before = store.counts()
    result = inspect_architecture(store, user, AccessPolicy(), request)
    assert result == inspect_architecture(store, user, AccessPolicy(), request)
    assert len(result['blocks']) == 2 and len(result['ports']) == 2 and len(result['gaps']) == 1
    assert result['bindings'][0]['operation_coverage'] == {'mapped': ['Submit'], 'unmapped': [], 'complete': True}
    assert not result['endpoints_contacted'] and not result['security_verified'] and not result['behavioral_compatibility_verified'] and not result['outputs_constructed']
    assert store.counts() == before and validate_graph(objects, ARCHITECTURE_PROFILE)['valid']
    assert not validate_graph(objects, GOVERNANCE_PROFILE)['valid']
    block = find(objects, 'ArchitectureBlock');equivalent = deepcopy(block);equivalent['body']['responsibilities'].reverse()
    assert canonical(block) == canonical(equivalent)


@pytest.mark.parametrize('fault', ['unknown_operation', 'port_direction', 'binding_contract', 'wrong_schema', 'wrong_control', 'wrong_output'])
def test_architecture_cross_references_are_checked(store, tmp_path, example, fault):
    objects, user, token, request = prepare(store, tmp_path, example);bad = deepcopy(objects)
    if fault == 'unknown_operation': find(bad, 'TechnicalBinding')['body']['schema_mapping'][0]['operation'] = 'Absent'
    if fault == 'port_direction': find(bad, 'Port')['body']['direction'] = 'REQUIRED'
    if fault == 'binding_contract':
        contract = deepcopy(find(bad, 'SemanticContract'));contract['meta']['id'] = 'urn:architecture:other-contract';bad.append(contract)
        find(bad, 'TechnicalBinding')['body']['contract'] = exact(contract)
    if fault == 'wrong_schema': find(bad, 'DataFlow')['body']['schema'] = exact(find(bad, 'Control'))
    if fault == 'wrong_control': find(bad, 'TechnicalBinding')['body']['security_binding'] = [exact(find(bad, 'Source'))]
    if fault == 'wrong_output': find(bad, 'ArchitectureGap')['body']['required_output'] = exact(find(bad, 'Control'))
    assert not validate_graph(bad, ARCHITECTURE_PROFILE)['valid']


@pytest.mark.parametrize('fault', ['duplicate_operation', 'duplicate_route', 'dot_segments', 'double_separator', 'path_variable', 'get_body', 'missing_required_flag', 'orphan_required_flag', 'credential_url', 'empty_userinfo', 'query_url', 'empty_fragment', 'zero_port', 'variable_url', 'other_protocol'])
def test_http_binding_rejects_ambiguous_or_unsupported_shapes(store, tmp_path, example, fault):
    objects, user, token, request = prepare(store, tmp_path, example);binding = deepcopy(find(objects, 'TechnicalBinding'));body = binding['body'];mapping = body['schema_mapping'][0]
    if fault.startswith('duplicate_'):
        other = deepcopy(mapping)
        if fault == 'duplicate_operation': other['path'] = '/other'
        else: other['operation'] = 'Other'
        body['schema_mapping'].append(other)
    if fault == 'dot_segments': mapping['path'] = '/a/../b'
    if fault == 'double_separator': mapping['path'] = '//b'
    if fault == 'path_variable': mapping['path'] = '/items/{id}'
    if fault == 'get_body': mapping['method'] = 'GET'
    if fault == 'missing_required_flag': del mapping['request_required']
    if fault == 'orphan_required_flag': del mapping['request_schema']
    if fault == 'credential_url': body['endpoint_template'] = 'https://user:password@example.invalid'
    if fault == 'empty_userinfo': body['endpoint_template'] = 'https://@example.invalid'
    if fault == 'empty_fragment': body['endpoint_template'] = 'https://example.invalid#'
    if fault == 'zero_port': body['endpoint_template'] = 'https://example.invalid:0'
    if fault == 'query_url': body['endpoint_template'] = 'https://example.invalid?key=test'
    if fault == 'variable_url': body['endpoint_template'] = 'https://{tenant}.example.invalid'
    if fault == 'other_protocol': body['protocol'] = 'MQTT'
    assert not validate(binding)['valid']


def test_architecture_request_digest_and_acl(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example)
    wrong = deepcopy(request);wrong['baseline']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): inspect_architecture(store, user, AccessPolicy(), wrong)
    with pytest.raises(Forbidden): inspect_architecture(store, user, AccessPolicy({'version': 'deny', 'subjects': {}}), request)


def test_architecture_transfer_preserves_report(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);expected = inspect_architecture(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'architecture-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert inspect_architecture(target, user, AccessPolicy(), request) == expected
    finally: target.engine.dispose()


def test_architecture_api_mcp(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/architecture/inspect', json=request, headers=auth)
        assert response.status_code == 200 and len(response.json()['bindings']) == 1
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_inspect_architecture', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.status_code == 200 and mcp.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/architecture/inspect', json=request).status_code == 401


def test_partial_operation_mapping_is_reported(store, tmp_path, example):
    def mutate(additions):
        contract = find(additions, 'SemanticContract')
        contract['body']['operations'].append({'name': 'ReadStatus', 'function': contract['body']['operations'][0]['function']})
    objects, user, token, request = prepare(store, tmp_path, example, mutate)
    coverage = inspect_architecture(store, user, AccessPolicy(), request)['bindings'][0]['operation_coverage']
    assert coverage == {'mapped': ['Submit'], 'unmapped': ['ReadStatus'], 'complete': False}


def test_flow_transformation_order_is_preserved(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example)
    flow = deepcopy(find(objects, 'DataFlow'));flow['body']['transformations'] = [{'id': 'urn:step:first', 'revision': 1}, {'id': 'urn:step:second', 'revision': 1}]
    reversed_flow = deepcopy(flow);reversed_flow['body']['transformations'].reverse()
    assert canonical(flow) != canonical(reversed_flow)
