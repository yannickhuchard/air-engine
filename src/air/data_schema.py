"""Bounded semantic data declarations and flat JSON message bindings."""
from copy import deepcopy

PROFILE = 'air.data/0.23'
NAMES = ['Concept', 'DataAuthority', 'DataEntity', 'DataSchema', 'Message', 'Event']
FIELD_NAME = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]{0,63}$'}
VALUE_TYPES = ['Boolean', 'Text', 'Integer', 'Decimal', 'Instant']


def bodies(record, text, uri, ref, refs, artifact_ref):
    field = record({'binding': {'const': 'air.field/0.23'}, 'name': FIELD_NAME})
    fields = {'type': 'array', 'items': field, 'maxItems': 128, 'uniqueItems': True}
    attribute = record({'binding': {'const': 'air.attribute/0.23'}, 'name': FIELD_NAME,
        'value_type': {'enum': VALUE_TYPES}, 'required': {'type': 'boolean'}, 'description': text})
    artifact = deepcopy(artifact_ref);artifact['properties']['size']['maximum'] = 1048576
    return {
        'air.Concept': record({'definition': text, 'domain': ref, 'semantic_relations': {'type': 'array', 'maxItems': 0}, 'steward': uri}),
        'air.DataAuthority': record({'data_scope': ref, 'operations': {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True},
            'responsible': uri, 'writer_policy': text, 'coordination_policy': text}),
        'air.DataEntity': record({'concept': ref, 'attributes': {'type': 'array', 'items': attribute, 'minItems': 1, 'maxItems': 128},
            'identity': {**fields, 'minItems': 1}, 'ownership': ref, 'constraints': {'type': 'array', 'maxItems': 0}}),
        'air.DataSchema': record({'format': {'const': 'JSON Schema'}, 'dialect_version': {'const': '2020-12'}, 'artifact': artifact,
            'represents': {**refs, 'maxItems': 128}, 'compatibility_policy': text}),
        'air.Message': record({'schema': ref, 'meaning': text, 'classification': record({'level': {'enum': ['PUBLIC', 'INTERNAL']}}),
            'correlation_keys': fields, 'idempotency_key': field}, ['schema', 'meaning', 'classification', 'correlation_keys']),
        'air.Event': record({'semantic_meaning': text, 'payload_schema': ref, 'occurrence_time': field,
            'correlation': fields, 'delivery_contract': ref}, ['semantic_meaning', 'payload_schema', 'occurrence_time', 'correlation']),
    }


def slots(obj):
    body, kind = obj['body'], obj['meta']['type']
    one = {'air.Concept': {'domain': ['air.Domain']}, 'air.DataAuthority': {'data_scope': ['air.Scope']},
           'air.DataEntity': {'concept': ['air.Concept'], 'ownership': ['air.DataAuthority']}, 'air.Message': {'schema': ['air.DataSchema']},
           'air.Event': {'payload_schema': ['air.DataSchema'], 'delivery_contract': ['air.SemanticContract']}}
    for field, kinds in one.get(kind, {}).items():
        if field in body: yield 'body/' + field, body[field], kinds
    if kind == 'air.DataSchema':
        for ref in body['represents']: yield 'body/represents', ref, ['air.DataEntity', 'air.Message']


def local_issues(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.DataEntity':
        names = [a['name'] for a in body['attributes']]
        if len(set(names)) != len(names): yield 'AIR_DATA_ATTRIBUTE_ID', 'Data attribute names must be unique'
        required = {a['name'] for a in body['attributes'] if a['required']}
        if not {f['name'] for f in body['identity']} <= required:
            yield 'AIR_DATA_IDENTITY', 'Identity fields must reference required local attributes'


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.DataAuthority': body['operations'].sort()
    if kind == 'air.DataEntity':
        body['attributes'].sort(key=lambda a: a['name']);body['identity'].sort(key=lambda f: f['name'])
    if kind == 'air.DataSchema': body['represents'].sort(key=lambda r: (r['id'], r['revision']))
    if kind == 'air.Message': body['correlation_keys'].sort(key=lambda f: f['name'])
    if kind == 'air.Event': body['correlation'].sort(key=lambda f: f['name'])
