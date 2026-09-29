"""Tranche 30: what the health insurance pilot could not express, or could not have checked, in 0.29."""
from copy import deepcopy
import json
import pytest
from air.access import AccessPolicy, Forbidden, ScopedStore
from air.architecture import inspect_architecture
from air.architecture_schema import HTTP_MAPPING_030
from air.baseline_closure import compute_closure
from air.construction import assess_baseline
from air.core import ARCHITECTURE_PROFILE, digest, validate
from air.data_validation import structured_issues, schema_issues, STRUCTURED
from air.foundation import exact, InvalidModel
from air.openapi_compiler import compile_openapi
from test_architecture import prepare as prepare_architecture, find
from test_openapi_compiler import prepare as prepare_compiler

DIALECT = 'https://json-schema.org/draft/2020-12/schema'
AGGREGATE = {'$schema': DIALECT, 'title': 'Claim', 'type': 'object', 'additionalProperties': False,
             'required': ['claimId', 'claimedAmount', 'lines'],
             'properties': {'claimId': {'type': 'string', 'pattern': '^[A-Z0-9-]{4,32}$'},
                            'claimedAmount': {'type': 'object', 'additionalProperties': False, 'required': ['amount', 'currency'],
                                              'properties': {'amount': {'type': 'string'}, 'currency': {'type': 'string', 'minLength': 3, 'maxLength': 3}}},
                            'lines': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['procedureCode'],
                                                                 'properties': {'procedureCode': {'type': 'string'}, 'amount': {'type': 'number'}}}}}}


def compiled(store, tmp_path, example, mutate):
    """An architecture baseline with a mutated binding, plus the compilation request that pins it."""
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    binding = find(objects, 'TechnicalBinding')
    return objects, user, {**request, 'binding': {**exact(binding), 'digest': digest(binding)},
                           'info': {'title': 'Pilot API', 'version': '1.0.0'}}


def test_structured_subset_carries_aggregates_and_refuses_unbounded_shapes():
    assert structured_issues(AGGREGATE) == ([], False)          # value object and collection: the pilot's claim
    assert schema_issues(AGGREGATE)[0], 'the flat subset still refuses it'
    flat = {'$schema': DIALECT, 'type': 'object', 'additionalProperties': False, 'required': [], 'properties': {'a': {'type': 'string'}}}
    assert structured_issues(flat) == ([], False), 'every flat schema stays valid under the structured subset'
    for broken, expected in (({'properties': {'a': {'$ref': '#/$defs/x'}}}, 'type'),
                             ({'properties': {'a': {'type': 'object', 'properties': {'b': {'type': 'string'}}, 'required': [], 'additionalProperties': True}}}, 'additionalProperties'),
                             ({'properties': {'a': {'type': 'array'}}}, 'items'),
                             ({'properties': {'a': {'type': 'string', 'pattern': '([unclosed'}}}, 'regular expression')):
        rows, _ = structured_issues({'$schema': DIALECT, 'type': 'object', 'additionalProperties': False, 'required': [], **broken})
        assert rows and any(expected in row['message'] for row in rows), (broken, rows)
    deep = {'type': 'string'}
    for _ in range(8): deep = {'type': 'object', 'additionalProperties': False, 'required': [], 'properties': {'x': deep}}
    assert any('depth' in row['message'] for row in structured_issues({'$schema': DIALECT, **deep})[0])


def test_path_parameters_errors_and_security_reach_the_description(store, tmp_path, example):
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding');contract = find(additions, 'SemanticContract')
        failure = deepcopy(contract);failure['meta'].update(id='urn:architecture:failure-030', type='air.FailureMode', name='ClaimOnFraudHold')
        failure['body'] = {'trigger': 'A hold is active', 'effect': 'Command refused', 'detection': 'Checked before any effect',
                           'response': 'Return problem details', 'recovery_condition': 'The hold is released'}
        additions.append(failure)
        contract['body']['error_contract'] = [{'code': 'ClaimOnFraudHold', 'failure_mode': exact(failure), 'response': 'HTTP 409 problem details'}]
        mapping = binding['body']['schema_mapping'][0]
        binding['body']['schema_mapping'] = [{**mapping, 'binding': HTTP_MAPPING_030, 'path': '/proposals/{proposalId}',
            'parameters': [{'name': 'proposalId', 'in': 'path', 'required': True, 'type': 'string', 'description': 'Aggregate identity'},
                           {'name': 'Idempotency-Key', 'in': 'header', 'required': True, 'type': 'string'},
                           {'name': 'status', 'in': 'query', 'required': False, 'type': 'string', 'enum': ['OPEN', 'CLOSED']}],
            'errors': [{'code': 'ClaimOnFraudHold', 'status': '409', 'response_schema': mapping['response_schema']}]}]
        binding['body']['security_scheme'] = {'kind': 'HTTP_BEARER'}
    objects, user, request = compiled(store, tmp_path, example, mutate)
    result = compile_openapi(store, user, AccessPolicy(), request)
    document = json.loads(result['content'])
    operation = document['paths']['/proposals/{proposalId}']['post']
    assert [p['name'] for p in operation['parameters']] == ['Idempotency-Key', 'proposalId', 'status']
    assert operation['parameters'][1]['in'] == 'path' and operation['parameters'][1]['required'] is True
    assert operation['parameters'][2]['schema']['enum'] == ['OPEN', 'CLOSED']
    assert operation['description'] and operation['tags'], 'the function statement and its contract reach the reader'
    assert '409' in operation['responses'] and 'application/problem+json' in operation['responses']['409']['content']
    assert document['components']['securitySchemes']['AirDeclaredScheme']['type'] == 'http' and document['security']
    assert all(not name.startswith('schema_') for name in document['components']['schemas']), list(document['components']['schemas'])
    assert result['error_responses_generated'] == ['ClaimOnFraudHold'] and result['parameters_generated'] == 3
    assert {'BEHAVIOR_NOT_IMPLEMENTED', 'SECURITY_NOT_VERIFIED'} <= {loss['code'] for loss in result['losses']}
    assert 'ERROR_CONTRACT_NOT_MAPPED' not in {loss['code'] for loss in result['losses']}
    assert not result['security_verified'] and not result['behavior_implemented'] and not result['authorization_granted']
    from jsonschema import Draft202012Validator, FormatChecker
    from pathlib import Path
    official = json.loads(Path(__file__).parent.joinpath('fixtures/openapi-3.1-schema-2022-10-07.json').read_text(encoding='utf-8'))
    Draft202012Validator(official, format_checker=FormatChecker()).validate(document)


def test_binding_refuses_an_undeclared_path_parameter_and_names_the_object():
    binding = {'meta': {'id': 'urn:t:binding', 'type': 'air.TechnicalBinding', 'revision': 1, 'name': 'b', 'description': 'd', 'namespace': 'test',
                        'owner': 'urn:o', 'classification': {'level': 'INTERNAL'}, 'lifecycle': 'DRAFT', 'recorded_at': '2026-09-22T00:00:00Z',
                        'validity': {'start': '2026-09-22T00:00:00Z', 'end': None},
                        'provenance': {'recorded_by': 'urn:a', 'method': 'test', 'source_refs': []}},
               'body': {'contract': {'id': 'urn:t:contract', 'revision': 1}, 'protocol': 'HTTP', 'protocol_version': '1.1',
                        'security_binding': [{'id': 'urn:t:control', 'revision': 1}],
                        'schema_mapping': [{'binding': HTTP_MAPPING_030, 'operation': 'Get', 'method': 'GET', 'path': '/claims/{claimId}',
                                            'response_schema': {'id': 'urn:t:schema', 'revision': 1}, 'response_status': '200'}]}}
    report = validate([binding])
    assert any(d['code'] == 'AIR_BINDING_PARAMETER' for d in report['diagnostics']), report['diagnostics']
    assert all(d['object'] == {'id': 'urn:t:binding', 'revision': 1, 'type': 'air.TechnicalBinding'} for d in report['diagnostics'])
    templated = deepcopy(binding)
    templated['body']['schema_mapping'][0]['parameters'] = [{'name': 'claimId', 'in': 'path', 'required': True, 'type': 'string'}]
    assert validate([templated])['valid']
    old = deepcopy(binding);old['body']['schema_mapping'][0].update(binding='air.http-json-mapping/0.26', path='/claims/{claimId}')
    assert not validate([old])['valid'], 'the 0.26 mapping keeps refusing a template'


def test_inspection_checks_exclusivity_exhaustiveness_and_the_schema_subset(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    report = inspect_architecture(store, user, AccessPolicy(), request)
    assert report['checks']['result'] == 'NO_STRUCTURAL_VIOLATION' and report['checks']['not_checked']
    assert report['bindings'][0]['schema_artifacts_validated'] and report['bindings'][0]['schema_subset'] == STRUCTURED
    assert report['scope']['owned_objects'] and report['dependencies'] and report['bindings'][0]['transport'] == 'HTTP'


def test_inspection_reports_an_aggregate_owned_by_two_blocks(store, tmp_path, example):
    def duplicate_owner(additions):
        blocks = [o for o in additions if o['meta']['type'] == 'air.ArchitectureBlock']
        consumer = next(b for b in blocks if b['meta']['id'].endswith(':consumer'))
        provider = next(b for b in blocks if b['meta']['id'].endswith(':provider'))
        consumer['body']['owned_state'] = list(provider['body']['owned_state'])
        consumer['body']['provided_contracts'] = list(provider['body']['provided_contracts'])
    objects, user, token, request = prepare_architecture(store, tmp_path, example, duplicate_owner)
    report = inspect_architecture(store, user, AccessPolicy(), request)
    codes = {v['code'] for v in report['checks']['violations']}
    assert {'AIR_ARCH_ENTITY_OWNED_TWICE', 'AIR_ARCH_CONTRACT_PROVIDED_TWICE'} <= codes, codes
    assert report['checks']['result'] == 'VIOLATIONS_FOUND'


def test_inspection_reports_a_schema_outside_the_subset_before_any_compilation(store, tmp_path, example):
    unbounded = json.dumps({'$schema': DIALECT, 'type': 'object', 'additionalProperties': False, 'required': [],
                            'properties': {'anything': {'type': 'object'}}}).encode()
    objects, user, token, request = prepare_compiler(store, tmp_path, example, raw_schema=unbounded)
    report = inspect_architecture(store, user, AccessPolicy(), {'baseline': request['baseline']})
    violation = next(v for v in report['checks']['violations'] if v['code'] == 'AIR_ARCH_SCHEMA_OUTSIDE_SUBSET')
    assert violation['schemas'][0]['name'] and not report['bindings'][0]['schema_artifacts_validated']
    with pytest.raises(InvalidModel) as failure:
        compile_openapi(store, user, AccessPolicy(), request)
    assert failure.value.report['schemas'][0]['issues'], 'every schema issue is reported, with the schema that carries it'


def test_construction_gate_assesses_an_architecture_baseline(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    report = assess_baseline(store, request)
    assert report['profile'] == ARCHITECTURE_PROFILE and 'traceability' in report and 'construction_ready' in report


def test_closure_returns_the_members_a_dependent_baseline_needs(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    contract = find(objects, 'SemanticContract')
    result = compute_closure(store, user, AccessPolicy(), {'roots': [exact(contract)], 'sources': [request['baseline']]})
    members = {(m['id'], m['revision']) for m in result['members']}
    assert (contract['meta']['id'], contract['meta']['revision']) in members and result['complete']
    assert len(members) > 1 and result['members_count'] == len(members)
    assert result['by_namespace'] and result['by_type'] and not result['registry_written'] and not result['baseline_created']
    absent = compute_closure(store, user, AccessPolicy(), {'roots': [{'id': 'urn:air:absent', 'revision': 1}], 'sources': [request['baseline']]})
    assert absent['roots_not_found'] == [{'id': 'urn:air:absent', 'revision': 1}] and not absent['complete']


def test_unavailable_references_are_named_back_to_the_caller(store):
    guarded = ScopedStore(store, {'subject': 'u', 'role': 'editor'}, AccessPolicy())
    with pytest.raises(Forbidden) as refusal:
        guarded.check_read([{'id': 'urn:air:never-deposited', 'revision': 1}])
    assert refusal.value.unavailable == [{'id': 'urn:air:never-deposited', 'revision': 1}]

def test_messaging_binding_declares_event_channels_and_their_coverage(store, tmp_path, example):
    """The fraud pilot could not bind an event channel at all; a channel is now declared, never executed."""
    def mutate(additions):
        binding = find(additions, 'TechnicalBinding');contract = find(additions, 'SemanticContract')
        stream = deepcopy(binding);stream['meta'].update(id='urn:architecture:event-binding', name='Claims event stream')
        stream['body'] = {'contract': exact(contract), 'protocol': 'KAFKA', 'protocol_version': '3.7',
            'endpoint_template': 'kafka://broker.health.invalid:9093', 'security_binding': list(binding['body']['security_binding']),
            'channel_mapping': [{'binding': 'air.message-channel-mapping/0.30', 'event': {'id': 'urn:data:event', 'revision': 1},
                                 'channel': 'claims.events', 'action': 'PUBLISH', 'message_schema': {'id': 'urn:data:schema', 'revision': 1},
                                 'key': {'binding': 'air.field/0.23', 'name': 'id'}, 'ordering': 'PER_KEY', 'delivery': 'AT_LEAST_ONCE'}]}
        additions.append(stream)
        provided = next(o for o in additions if o['meta']['type'] == 'air.Port' and o['body']['direction'] == 'PROVIDED')
        provided['body']['bindings'] = sorted(provided['body']['bindings'] + [exact(stream)], key=lambda r: r['id'])
    objects, user, token, request = prepare_architecture(store, tmp_path, example, mutate)
    report = inspect_architecture(store, user, AccessPolicy(), request)
    stream = next(b for b in report['bindings'] if b['transport'] == 'MESSAGING')
    assert stream['channel_coverage']['channels'] == ['claims.events'] and stream['channel_coverage']['complete']
    assert stream['channel_coverage']['events_mapped'] == ['urn:data:event'] and stream['schema_artifacts_validated']
    assert report['checks']['result'] == 'NO_STRUCTURAL_VIOLATION'
    unconsumed = next(o for o in report['checks']['observations'] if o['code'] == 'AIR_ARCH_EVENT_UNCONSUMED')
    assert [e['id'] for e in unconsumed['events']] == ['urn:data:event'] and unconsumed['family'] == 'DECLARATION', 'published, subscribed by nobody'
    with pytest.raises(InvalidModel, match='messaging binding'):
        compile_openapi(store, user, AccessPolicy(), {**request, 'binding': next(
            {**b['reference']} for b in report['bindings'] if b['transport'] == 'MESSAGING'), 'info': {'title': 'x', 'version': '1'}})


def test_messaging_binding_refuses_an_unkeyed_ordering_and_a_foreign_payload():
    binding = {'meta': {'id': 'urn:t:stream', 'type': 'air.TechnicalBinding', 'revision': 1, 'name': 's', 'description': 'd', 'namespace': 'test',
                        'owner': 'urn:o', 'classification': {'level': 'INTERNAL'}, 'lifecycle': 'DRAFT', 'recorded_at': '2026-09-22T00:00:00Z',
                        'validity': {'start': '2026-09-22T00:00:00Z', 'end': None},
                        'provenance': {'recorded_by': 'urn:a', 'method': 'test', 'source_refs': []}},
               'body': {'contract': {'id': 'urn:t:contract', 'revision': 1}, 'protocol': 'KAFKA', 'protocol_version': '3.7',
                        'security_binding': [{'id': 'urn:t:control', 'revision': 1}],
                        'channel_mapping': [{'binding': 'air.message-channel-mapping/0.30', 'event': {'id': 'urn:t:event', 'revision': 1},
                                             'channel': 'claims.events', 'action': 'PUBLISH', 'message_schema': {'id': 'urn:t:schema', 'revision': 1},
                                             'ordering': 'PER_KEY', 'delivery': 'AT_LEAST_ONCE'}]}}
    report = validate([binding])
    assert any(d['code'] == 'AIR_BINDING_CHANNEL' for d in report['diagnostics']), report['diagnostics']
    keyed = deepcopy(binding);keyed['body']['channel_mapping'][0]['key'] = {'binding': 'air.field/0.23', 'name': 'claimId'}
    assert validate([keyed])['valid']
    both = deepcopy(keyed);both['body']['schema_mapping'] = [{'binding': HTTP_MAPPING_030, 'operation': 'Get', 'method': 'GET', 'path': '/x',
                                                              'response_schema': {'id': 'urn:t:schema', 'revision': 1}, 'response_status': '200'}]
    assert not validate([both])['valid'], 'a binding declares operations or channels, never both'
