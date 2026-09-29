from copy import deepcopy
from decimal import Decimal
import json
import socket
import pytest
from fastapi.testclient import TestClient
from air import artifacts
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import DATA_PROFILE, WORKFLOW_PROFILE, canonical, validate, digest
from air.data_validation import validate_payload, parse_external, DataInputError
from air.foundation import exact, validate_graph, InvalidModel
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict
from test_artifacts import setup
from test_organization import models

VALID = b'{"id":"claim-001","occurred_at":"2026-09-20T00:00:00Z","quantity":0.1}'


def prepare(store, tmp_path, example, payload=VALID, schema_mutator=None, model_mutator=None, integer=False):
    settings, user, token, policy, upload = setup(store, tmp_path)
    upload = {**upload, 'namespace': 'tests.data_artifacts'}
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'additionalProperties': False,
        'properties': {'id': {'type': 'string', 'minLength': 1}, 'occurred_at': {'type': 'string', 'format': 'date-time'},
                       'quantity': {'type': 'integer' if integer else 'number'}}, 'required': ['id', 'occurred_at', 'quantity']}
    if schema_mutator: schema_mutator(schema)
    schema_artifact = artifacts.put(store, user, policy, settings, {**upload, 'media_type': 'application/json', 'idempotency_key': 'schema'}, json.dumps(schema).encode())
    payload_artifact = artifacts.put(store, user, policy, settings, {**upload, 'media_type': 'application/json', 'idempotency_key': 'payload'}, payload)
    org = models(example);scope = org[0];domain = org[5]
    def obj(kind, suffix, body):
        meta = deepcopy(example['meta']);meta.update(id='urn:data:' + suffix, type='air.' + kind, name=suffix)
        return {'meta': meta, 'body': body}
    field = lambda name: {'binding': 'air.field/0.23', 'name': name}
    concept = obj('Concept', 'concept', {'definition': 'Claim submission', 'domain': exact(domain), 'semantic_relations': [], 'steward': 'urn:person:steward'})
    authority = obj('DataAuthority', 'owner', {'data_scope': exact(scope), 'operations': ['Create draft'], 'responsible': 'urn:person:owner', 'writer_policy': 'Declared team responsibility', 'coordination_policy': 'Review before external effects'})
    entity = obj('DataEntity', 'entity', {'concept': exact(concept), 'ownership': exact(authority), 'identity': [field('id')], 'constraints': [],
        'attributes': [{'binding': 'air.attribute/0.23', 'name': name, 'value_type': kind, 'required': True, 'description': name}
                       for name, kind in [('id', 'Text'), ('occurred_at', 'Instant'), ('quantity', 'Integer' if integer else 'Decimal')]]})
    schema_obj = obj('DataSchema', 'schema', {'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': schema_artifact['artifact_reference'], 'represents': [exact(entity)], 'compatibility_policy': 'Explicit review for changes'})
    message = obj('Message', 'message', {'schema': exact(schema_obj), 'meaning': 'Claim proposal', 'classification': {'level': 'INTERNAL'}, 'correlation_keys': [field('id')], 'idempotency_key': field('id')})
    event = obj('Event', 'event', {'semantic_meaning': 'Claim proposed', 'payload_schema': exact(schema_obj), 'occurrence_time': field('occurred_at'), 'correlation': [field('id')]})
    objects = org + [concept, authority, entity, schema_obj, message, event]
    if model_mutator: model_mutator(objects)
    store.put_bundle(objects, 'fixture')
    meta = deepcopy(example['meta']);meta.update(id='urn:data:baseline', type='air.Baseline')
    base = store.create_baseline({'meta': meta, 'profile': DATA_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    request = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}, 'subject': {**exact(message), 'digest': digest(message)}, 'payload_artifact': payload_artifact['artifact']}
    return settings, user, token, objects, request


def test_data_models_exact_references_and_canonical_sets(store, tmp_path, example):
    settings, user, token, objects, request = prepare(store, tmp_path, example)
    assert validate_graph(objects, DATA_PROFILE)['valid']
    assert not validate_graph(objects, WORKFLOW_PROFILE)['valid']
    entity = next(o for o in objects if o['meta']['type'] == 'air.DataEntity')
    equivalent = deepcopy(entity);equivalent['body']['attributes'].reverse()
    assert canonical(equivalent) == canonical(entity)
    invalid = deepcopy(entity);invalid['body']['identity'][0]['name'] = 'absent'
    assert not validate(invalid)['valid']
    invalid = deepcopy(entity);invalid['body']['attributes'][0]['required'] = False
    assert not validate(invalid)['valid']


def test_data_payload_validation_is_pure_exact_and_preserves_decimal(store, tmp_path, example):
    settings, user, token, objects, request = prepare(store, tmp_path, example)
    before = store.counts();result = validate_payload(store, user, AccessPolicy(), request)
    assert result == validate_payload(store, user, AccessPolicy(), request)
    assert result['schema_validation'] == result['field_mapping_validation'] == result['payload_validation'] == 'SATISFIED'
    assert not result['authorization_granted'] and not result['event_truth_verified'] and not result['semantic_compatibility_verified']
    assert store.counts() == before
    assert parse_external(VALID)['quantity'] == Decimal('0.1')
    event = next(o for o in objects if o['meta']['type'] == 'air.Event')
    assert validate_payload(store, user, AccessPolicy(), {**request, 'subject': {**exact(event), 'digest': digest(event)}})['payload_validation'] == 'SATISFIED'
    wrong = deepcopy(request);wrong['subject']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): validate_payload(store, user, AccessPolicy(), wrong)


@pytest.mark.parametrize('payload', [b'{"id":"a","id":"b"}', b'{"id":"a"}', b'{"id":false,"occurred_at":"2026-09-20T00:00:00Z","quantity":1}',
    b'{"id":"a","occurred_at":"not-a-time","quantity":1}', b'{"id":"a","occurred_at":"2026-09-20T00:00:00Z","quantity":1,"extra":true}',
    b'{"quantity":NaN}', b'{"quantity":1e9999999999999999999999999}', b'{"quantity":Infinity}', b'[]', b'{'])
def test_data_invalid_payload_is_reported(store, tmp_path, example, payload):
    settings, user, token, objects, request = prepare(store, tmp_path, example, payload=payload)
    result = validate_payload(store, user, AccessPolicy(), request)
    assert result['schema_validation'] == 'SATISFIED' and result['payload_validation'] == 'VIOLATED'
    assert result['diagnostics']


@pytest.mark.parametrize('mutation', ['root-ref', 'property-ref', 'pattern', 'wrong-format', 'unknown-required'])
def test_data_schema_rejects_unsupported_features_without_network(store, tmp_path, example, monkeypatch, mutation):
    def mutate(schema):
        if mutation == 'root-ref': schema['$ref'] = 'https://untrusted.example/schema'
        if mutation == 'property-ref': schema['properties']['id']['$ref'] = '#/$defs/missing'
        if mutation == 'pattern': schema['properties']['id']['pattern'] = '(a+)+$'
        if mutation == 'wrong-format': schema['properties']['quantity']['format'] = 'date-time'
        if mutation == 'unknown-required': schema['required'].append('absent')
    settings, user, token, objects, request = prepare(store, tmp_path, example, schema_mutator=mutate)
    def no_network(*args, **kwargs): raise AssertionError('Schema validation must not open a network connection')
    monkeypatch.setattr(socket, 'create_connection', no_network)
    result = validate_payload(store, user, AccessPolicy(), request)
    assert result['schema_validation'] == 'VIOLATED' and result['payload_validation'] == 'NOT_EXECUTED'


def test_data_field_mapping_is_not_silently_ignored(store, tmp_path, example):
    def mutate(objects): next(o for o in objects if o['meta']['type'] == 'air.Message')['body']['idempotency_key']['name'] = 'absent'
    settings, user, token, objects, request = prepare(store, tmp_path, example, model_mutator=mutate)
    result = validate_payload(store, user, AccessPolicy(), request)
    assert result['field_mapping_validation'] == 'VIOLATED' and result['payload_validation'] == 'NOT_EXECUTED'


def test_data_artifact_access_and_descriptor_integrity(store, tmp_path, example):
    settings, user, token, objects, request = prepare(store, tmp_path, example)
    policy = AccessPolicy({'version': 'model-only', 'subjects': {user['subject']: {'read': [example['meta']['namespace']]}}})
    with pytest.raises(Forbidden): validate_payload(store, user, policy, request)
    schema = next(o for o in objects if o['meta']['type'] == 'air.DataSchema')
    changed = deepcopy(schema);changed['meta']['revision'] = 2;changed['body']['artifact']['digest']['value'] = '0' * 64
    store.put(changed, 'fixture')
    message = next(o for o in objects if o['meta']['type'] == 'air.Message')
    changed_message = deepcopy(message);changed_message['meta']['revision'] = 2;changed_message['body']['schema'] = exact(changed)
    event = next(o for o in objects if o['meta']['type'] == 'air.Event');changed_event = deepcopy(event);changed_event['meta']['revision'] = 2;changed_event['body']['payload_schema'] = exact(changed)
    store.put_bundle([changed_message, changed_event], 'fixture')
    replacements = {o['meta']['id']: o for o in [changed, changed_message, changed_event]};members = [replacements.get(o['meta']['id'], o) for o in objects]
    meta = deepcopy(example['meta']);meta.update(id='urn:data:bad-descriptor', type='air.Baseline')
    base = store.create_baseline({'meta': meta, 'profile': DATA_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fixture')
    lookup = {**request, 'baseline': {**exact(base['baseline']), 'digest': base['digest']}, 'subject': {**exact(changed_message), 'digest': digest(changed_message)}}
    with pytest.raises(Conflict): validate_payload(store, user, AccessPolicy(), lookup)


@pytest.mark.parametrize('value, expected', [('1.0', 'SATISFIED'), ('1.1', 'VIOLATED'), ('1e2', 'SATISFIED')])
def test_data_json_integer_semantics_with_exact_numbers(store, tmp_path, example, value, expected):
    payload = ('{"id":"a","occurred_at":"2026-09-20T00:00:00Z","quantity":' + value + '}').encode()
    settings, user, token, objects, request = prepare(store, tmp_path, example, payload=payload, integer=True)
    assert validate_payload(store, user, AccessPolicy(), request)['payload_validation'] == expected


def test_external_json_budget_and_unicode():
    for raw in [b'[' * 50 + b'0' + b']' * 50, b'"' + b'a' * 1048576 + b'"', b'{"n":123456789012345678901234567890123456789}', b'"\\ud800"']:
        with pytest.raises(DataInputError): parse_external(raw)


def test_data_transfer_replays_validation(store, tmp_path, example):
    settings, user, token, objects, request = prepare(store, tmp_path, example)
    expected = validate_payload(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'data-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'target.db').as_posix();import_registry(bundle, url);target = Store(url)
    try: assert validate_payload(target, user, AccessPolicy(), request) == expected
    finally: target.engine.dispose()


def test_data_api_and_mcp(store, tmp_path, example):
    settings, user, token, objects, request = prepare(store, tmp_path, example)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        auth = {'Authorization': 'Bearer ' + token['access_token']}
        response = client.post('/v1/data/validate', json=request, headers=auth)
        assert response.status_code == 200 and response.json()['payload_validation'] == 'SATISFIED'
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_validate_data', 'arguments': request}},
            headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert result.status_code == 200 and result.json()['result']['structuredContent'] == response.json()
        assert client.post('/v1/data/validate', json=request).status_code == 401
