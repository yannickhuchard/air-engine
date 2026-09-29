from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from air import artifacts
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import digest
from air.foundation import exact, InvalidModel
from air.openapi_compiler import compile_openapi, exact_json
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict
from test_architecture import prepare as prepare_architecture, find


def prepare(store, tmp_path, example, raw_schema=None, tamper=False, partial=False, endpoint=None):
    def mutate(additions):
        if endpoint is not None: find(additions, 'TechnicalBinding')['body']['endpoint_template'] = endpoint
        if partial:
            contract = find(additions, 'SemanticContract');contract['body']['operations'].append({'name': 'ReadStatus', 'function': contract['body']['operations'][0]['function']})
        if raw_schema is None and not tamper: return
        schema = deepcopy(store.get('urn:data:schema', 1)['object']);schema['meta']['id'] = 'urn:compiler:schema'
        if raw_schema is not None:
            token = store.create_token('compiler-schema-author', 'editor');user = store.authenticate(token['access_token'], True)
            settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test');user['authorization']['instance_id'] = settings.instance_id
            manifest = artifacts.put(store, user, AccessPolicy(), settings, {'namespace': 'tests.data_artifacts', 'media_type': 'application/json', 'idempotency_key': 'compiler-schema'}, raw_schema)
            schema['body']['artifact'] = manifest['artifact_reference']
        if tamper: schema['body']['artifact']['digest']['value'] = '0' * 64
        mapping = find(additions, 'TechnicalBinding')['body']['schema_mapping'][0]
        mapping['request_schema'] = exact(schema);mapping['response_schema'] = exact(schema);additions.append(schema)
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    binding = find(objects, 'TechnicalBinding')
    return objects, user, token, {**request, 'binding': {**exact(binding), 'digest': digest(binding)}, 'info': {'title': 'Fictional proposal API', 'version': 'draft-1'}}


def resolve_pointer(document, selector):
    result = document
    for segment in selector.split('/')[1:]:
        decoded = segment.replace('~1', '/').replace('~0', '~');result = result[int(decoded)] if isinstance(result, list) else result[decoded]
    return result


def test_compiler_produces_valid_openapi_exact_mappings_and_visible_losses(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);before = store.counts()
    result = compile_openapi(store, user, AccessPolicy(), request)
    assert result == compile_openapi(store, user, AccessPolicy(), request) and store.counts() == before
    raw = result['content'].encode();assert result['size'] == len(raw) and result['content_digest'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
    document = json.loads(raw);fixture = Path(__file__).parent / 'fixtures/openapi-3.1-schema-2022-10-07.json'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == 'da01ba28852cac0de53893797cb8d1942bc3b05084f526dcc216717dec314ed0'
    Draft202012Validator(json.loads(fixture.read_text(encoding='utf-8')), format_checker=FormatChecker()).validate(document)
    assert document['paths']['/proposals']['post']['requestBody']['required'] is True
    assert document['x-air-status'] == 'DRAFT_DESIGN_ONLY' and 'security' not in document
    for mapping in result['source_mapping']: assert resolve_pointer(document, mapping['selector']) is not None
    assert {'SECURITY_NOT_VERIFIED', 'BEHAVIOR_NOT_IMPLEMENTED', 'ENTITY_MAPPING_NOT_VERIFIED'} <= {loss['code'] for loss in result['losses']}
    assert 'ERROR_CONTRACT_NOT_MAPPED' not in {loss['code'] for loss in result['losses']}  # this contract declares no error code
    assert not result['endpoints_contacted'] and not result['authorization_granted'] and not result['behavior_implemented']


def test_compiler_preserves_exact_decimal_bounds(store, tmp_path, example):
    schema = b'{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","properties":{"quantity":{"type":"number","minimum":0.10000000000000000000000000000000000001}},"required":["quantity"],"additionalProperties":false}'
    objects, user, token, request = prepare(store, tmp_path, example, raw_schema=schema)
    result = compile_openapi(store, user, AccessPolicy(), request)
    document = json.loads(result['content'], parse_float=Decimal, parse_int=Decimal)
    generated_schema = next(iter(document['components']['schemas'].values()))
    assert generated_schema['properties']['quantity']['minimum'] == Decimal('0.10000000000000000000000000000000000001')
    assert '0.10000000000000000000000000000000000001' in result['content']
    with pytest.raises(InvalidModel): exact_json(0.1)


@pytest.mark.parametrize('schema', [b'{"$ref":"https://example.invalid/schema"}', b'{"type":"object","type":"object"}', b'{"type":"object","properties":{},"required":[],"additionalProperties":true}'])
def test_compiler_refuses_unsupported_schema_without_network(store, tmp_path, example, schema, monkeypatch):
    objects, user, token, request = prepare(store, tmp_path, example, raw_schema=schema)
    def forbidden(*args, **kwargs): raise AssertionError('Network schema resolution attempted')
    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    with pytest.raises(InvalidModel): compile_openapi(store, user, AccessPolicy(), request)


def test_compiler_checks_artifact_access_and_exact_descriptor(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example)
    policy = AccessPolicy({'version': 'model-only', 'subjects': {user['subject']: {'read': [example['meta']['namespace']]}}})
    with pytest.raises(Forbidden): compile_openapi(store, user, policy, request)


def test_compiler_refuses_descriptor_tamper(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example, tamper=True)
    with pytest.raises(Conflict): compile_openapi(store, user, AccessPolicy(), request)


def test_compiler_requires_exact_binding_and_baseline(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example)
    for field in ('binding', 'baseline'):
        wrong = deepcopy(request);wrong[field]['digest'] = 'sha256:' + '0' * 64
        with pytest.raises(Conflict): compile_openapi(store, user, AccessPolicy(), wrong)
    wrong = deepcopy(request);wrong['binding']['id'] = 'urn:absent'
    with pytest.raises(InvalidModel): compile_openapi(store, user, AccessPolicy(), wrong)


def test_compiler_keeps_unmapped_operations_explicit(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example, partial=True)
    result = compile_openapi(store, user, AccessPolicy(), request)
    assert result['operation_coverage'] == {'mapped': ['Submit'], 'unmapped': ['ReadStatus'], 'complete': False}
    assert next(loss for loss in result['losses'] if loss['code'] == 'OPERATIONS_NOT_MAPPED')['operations'] == ['ReadStatus']


def test_compiler_transfer_preserves_exact_output(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);expected = compile_openapi(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'compiler-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert compile_openapi(target, user, AccessPolicy(), request) == expected
    finally: target.engine.dispose()


def test_compiler_api_mcp(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example);settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/compilations/openapi', json=request, headers=auth)
        assert response.status_code == 200 and json.loads(response.json()['content'])['openapi'] == '3.1.1'
        mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_compile_openapi', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert mcp.status_code == 200 and mcp.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/compilations/openapi', json=request).status_code == 401


def test_compiler_requires_well_formed_endpoint_uri(store, tmp_path, example):
    objects, user, token, request = prepare(store, tmp_path, example, endpoint='https://example.invalid/%zz')
    with pytest.raises(InvalidModel, match='URI'): compile_openapi(store, user, AccessPolicy(), request)


def test_compiler_enforces_output_byte_budget(store, tmp_path, example):
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'required': [], 'additionalProperties': False,
        'properties': {'field_' + str(i): {'type': 'string', 'description': 'x' * 4200} for i in range(128)}}
    objects, user, token, request = prepare(store, tmp_path, example, raw_schema=json.dumps(schema).encode())
    with pytest.raises(InvalidModel, match='512 KiB'): compile_openapi(store, user, AccessPolicy(), request)
