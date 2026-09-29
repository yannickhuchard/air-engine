"""Validate bounded flat JSON payloads against exact, authorized local artifacts."""
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from itertools import islice
import json
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.validators import extend
from air import artifacts
from air.access import ScopedStore
from air.core import TEXT, record, digest
import re as _re
from air.data_schema import FIELD_NAME
FIELD_NAME_RE = _re.compile(FIELD_NAME['pattern'])
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.packages import reference
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict

def _integer(checker, value):
    return not isinstance(value, bool) and (isinstance(value, int) or isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value())


ExactValidator = extend(Draft202012Validator, type_checker=Draft202012Validator.TYPE_CHECKER.redefine('integer', _integer))
ENGINE = 'air.data-validation/0.23'
REQUEST = record({'baseline': SNAPSHOT, 'subject': SNAPSHOT, 'payload_artifact': artifacts.LOOKUP['properties']['artifact']})
MAX_BYTES = 1048576
SCALAR = {'type': ['string', 'number', 'integer', 'boolean']}
PROPERTY = record({'type': {'enum': ['string', 'number', 'integer', 'boolean']},
    'format': {'enum': ['date-time', 'uri']}, 'description': TEXT,
    'enum': {'type': 'array', 'items': SCALAR, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True},
    'minLength': {'type': 'integer', 'minimum': 0, 'maximum': 131072},
    'maxLength': {'type': 'integer', 'minimum': 0, 'maximum': 131072},
    'minimum': {'type': 'number'}, 'maximum': {'type': 'number'}}, ['type'])
FLAT_SCHEMA = record({'$schema': {'const': 'https://json-schema.org/draft/2020-12/schema'},
    'type': {'const': 'object'}, 'title': TEXT, 'description': TEXT,
    'properties': {'type': 'object', 'minProperties': 1, 'maxProperties': 128, 'propertyNames': FIELD_NAME, 'additionalProperties': PROPERTY},
    'required': {'type': 'array', 'items': FIELD_NAME, 'maxItems': 128, 'uniqueItems': True},
    'additionalProperties': {'const': False}}, ['$schema', 'type', 'properties', 'required', 'additionalProperties'])


STRUCTURED = 'air.structured-json/0.30'
STRUCTURED_DEPTH = 6
STRUCTURED_NODES = 512
SCALAR_TYPES = ('string', 'number', 'integer', 'boolean')
SCALAR_KEYS = {'type', 'format', 'description', 'title', 'enum', 'minLength', 'maxLength', 'minimum', 'maximum', 'pattern'}
OBJECT_KEYS = {'type', 'title', 'description', 'properties', 'required', 'additionalProperties', '$schema'}
ARRAY_KEYS = {'type', 'title', 'description', 'items', 'minItems', 'maxItems'}


def structured_issues(schema):
    """air.structured-json/0.30: objects, nested objects and arrays of scalars or objects, self-contained.

    A superset of air.flat-json/0.23: every flat schema satisfies it. Composition keywords, references and
    recursion stay out, so a compiled description never depends on resolution the engine does not perform.
    """
    rows, nodes = [], [0]

    def issue(path, message): rows.append({'path': path, 'keyword': STRUCTURED, 'message': message})

    def scalar(path, spec):
        unknown = set(spec) - SCALAR_KEYS
        if unknown: issue(path, 'Unsupported keyword for a scalar: ' + ', '.join(sorted(unknown)));return
        if {'minLength', 'maxLength', 'pattern', 'format'} & spec.keys() and spec['type'] != 'string':
            issue(path, 'String constraints require string type')
        if {'minimum', 'maximum'} & spec.keys() and spec['type'] not in ('number', 'integer'):
            issue(path, 'Numeric constraints require numeric type')
        if spec.get('minLength', 0) > spec.get('maxLength', 131072): issue(path, 'String bounds are inconsistent')
        if 'minimum' in spec and 'maximum' in spec and spec['minimum'] > spec['maximum']: issue(path, 'Numeric bounds are inconsistent')
        if 'format' in spec and spec['format'] not in ('date-time', 'uri'): issue(path, 'Only the date-time and uri formats are supported')
        if 'pattern' in spec:
            import re
            if len(spec['pattern']) > 256: issue(path, 'Pattern exceeds 256 characters')
            else:
                try: re.compile(spec['pattern'])
                except re.error: issue(path, 'Pattern is not a valid regular expression')
        check = ExactValidator({'type': spec['type'], **({'format': spec['format']} if 'format' in spec else {})}, format_checker=FormatChecker())
        if any(not check.is_valid(v) for v in spec.get('enum', [])): issue(path, 'Enum values must match the declared scalar type and format')

    def node(path, spec, depth, root=False):
        nodes[0] += 1
        if nodes[0] > STRUCTURED_NODES: issue(path, 'Schema exceeds 512 declared nodes');return
        if not isinstance(spec, dict) or 'type' not in spec: issue(path, 'Every node declares a type');return
        if depth > STRUCTURED_DEPTH: issue(path, 'Schema exceeds a nesting depth of 6');return
        kind = spec['type']
        if kind == 'object':
            unknown = set(spec) - OBJECT_KEYS
            if unknown: issue(path, 'Unsupported keyword for an object: ' + ', '.join(sorted(unknown)));return
            if root and spec.get('$schema') != 'https://json-schema.org/draft/2020-12/schema': issue(path, 'The root declares the 2020-12 dialect')
            if not root and '$schema' in spec: issue(path, 'Only the root declares a dialect')
            if spec.get('additionalProperties') is not False: issue(path, 'Objects declare additionalProperties false')
            properties = spec.get('properties')
            if not isinstance(properties, dict) or not 1 <= len(properties) <= 128: issue(path, 'Objects declare 1 to 128 properties');return
            required = spec.get('required', [])
            if not isinstance(required, list) or not set(required) <= properties.keys(): issue(path, 'Required fields must be declared properties')
            for name, child in sorted(properties.items()):
                if not FIELD_NAME_RE.fullmatch(name): issue(path + '/properties/' + name, 'Field names are letters, digits and underscore')
                node(path + '/properties/' + name, child, depth + 1)
        elif kind == 'array':
            unknown = set(spec) - ARRAY_KEYS
            if unknown: issue(path, 'Unsupported keyword for an array: ' + ', '.join(sorted(unknown)));return
            if 'items' not in spec: issue(path, 'Arrays declare their items');return
            if spec.get('minItems', 0) > spec.get('maxItems', 4096): issue(path, 'Item bounds are inconsistent')
            node(path + '/items', spec['items'], depth + 1)
        elif kind in SCALAR_TYPES: scalar(path, spec)
        else: issue(path, 'Unsupported type: ' + str(kind))

    if not isinstance(schema, dict): return [{'path': '/schema', 'keyword': STRUCTURED, 'message': 'A schema is a JSON object'}], False
    node('/schema', schema, 0, root=True)
    return sorted(rows, key=lambda r: (r['path'], r['message']))[:128], len(rows) > 128


class DataInputError(ValueError): pass


def parse_external(raw):
    if not 1 <= len(raw) <= MAX_BYTES: raise DataInputError('JSON artifact exceeds byte budget')
    def pairs(entries):
        result = {}
        for name, value in entries:
            if name in result: raise DataInputError('Duplicate JSON member')
            result[name] = value
        return result
    def number(value):
        if len(value) > 128: raise DataInputError('JSON number exceeds precision budget')
        try: result = Decimal(value)
        except DecimalInvalidOperation as exc: raise DataInputError('JSON number exceeds precision budget') from exc
        if not result.is_finite() or len(result.as_tuple().digits) > 38 or abs(result.as_tuple().exponent) > 128:
            raise DataInputError('JSON number exceeds precision budget')
        return result
    def integer(value):
        number(value)
        return int(value)
    def nonfinite(value): raise DataInputError('Non-finite JSON number')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_float=number, parse_int=integer, parse_constant=nonfinite)
        pending = [(value, 0)];nodes = 0
        while pending:
            item, depth = pending.pop();nodes += 1
            if nodes > 10000 or depth > 48: raise DataInputError('JSON structure exceeds budget')
            if isinstance(item, dict):
                for name, child in item.items(): name.encode('utf-8');pending.append((child, depth + 1))
            elif isinstance(item, list): pending.extend((child, depth + 1) for child in item)
            elif isinstance(item, str): item.encode('utf-8')
        return value
    except DataInputError: raise
    except (ValueError, UnicodeError, RecursionError) as exc: raise DataInputError('Malformed UTF-8 JSON') from exc


def diagnostics(errors, prefix=''):
    found = list(islice(errors, 129));truncated = len(found) > 128
    rows = [{'path': (prefix + '/' + '/'.join(str(x).replace('~', '~0').replace('/', '~1') for x in e.absolute_path))[:512],
             'keyword': str(e.validator)[:64], 'message': 'Constraint not satisfied'} for e in found[:128]]
    return sorted(rows, key=lambda r: (r['path'], r['keyword'])), truncated


def schema_issues(schema):
    rows, truncated = diagnostics(ExactValidator(FLAT_SCHEMA).iter_errors(schema), '/schema')
    if rows: return rows, truncated
    def issue(path, message): rows.append({'path': path, 'keyword': 'air.flat-json/0.23', 'message': message})
    if not set(schema['required']) <= schema['properties'].keys(): issue('/schema/required', 'Required fields must be declared properties')
    for name, spec in schema['properties'].items():
        string_keys = {'format', 'minLength', 'maxLength'} & spec.keys()
        numeric_keys = {'minimum', 'maximum'} & spec.keys()
        if string_keys and spec['type'] != 'string': issue('/schema/properties/' + name, 'String constraints require string type')
        if numeric_keys and spec['type'] not in ('number', 'integer'): issue('/schema/properties/' + name, 'Numeric constraints require numeric type')
        if spec.get('minLength', 0) > spec.get('maxLength', 131072): issue('/schema/properties/' + name, 'String bounds are inconsistent')
        if 'minimum' in spec and 'maximum' in spec and spec['minimum'] > spec['maximum']: issue('/schema/properties/' + name, 'Numeric bounds are inconsistent')
        check = ExactValidator({'type': spec['type'], **({'format': spec['format']} if 'format' in spec else {})}, format_checker=FormatChecker())
        if any(not check.is_valid(v) for v in spec.get('enum', [])): issue('/schema/properties/' + name, 'Enum values must match the declared scalar type and format')
    return sorted(rows, key=lambda r: (r['path'], r['message']))[:128], len(rows) > 128


def mappings(subject, schema_obj, schema, index):
    rows = [];properties = schema['properties'];required = set(schema['required'])
    def issue(path, message): rows.append({'path': path, 'keyword': 'air.field/0.23', 'message': message})
    body = subject['body']
    fields = body['correlation_keys'] if subject['meta']['type'] == 'air.Message' else body['correlation']
    for field in fields:
        if field['name'] not in properties: issue('/subject/correlation', 'Correlation field is absent from schema')
    if subject['meta']['type'] == 'air.Message' and 'idempotency_key' in body:
        name = body['idempotency_key']['name']
        if name not in required or properties.get(name, {}).get('type') not in ('string', 'integer'):
            issue('/subject/idempotency_key', 'Idempotency field must be a required string or integer property')
    if subject['meta']['type'] == 'air.Event':
        name = body['occurrence_time']['name'];spec = properties.get(name, {})
        if name not in required or spec.get('type') != 'string' or spec.get('format') != 'date-time':
            issue('/subject/occurrence_time', 'Occurrence time must be a required date-time string property')
    types = {'Text': 'string', 'Boolean': 'boolean', 'Integer': 'integer', 'Decimal': 'number', 'Instant': 'string'}
    for ref in schema_obj['body']['represents']:
        entity = index[key(ref)]
        if entity['meta']['type'] != 'air.DataEntity': continue
        for attribute in entity['body']['attributes']:
            name = attribute['name'];spec = properties.get(name, {})
            if spec.get('type') != types[attribute['value_type']] or attribute['value_type'] == 'Instant' and spec.get('format') != 'date-time':
                issue('/entity/' + name, 'Entity attribute type differs from the schema property')
            if attribute['required'] and name not in required: issue('/entity/' + name, 'Required entity attribute is optional or absent in schema')
    return sorted(rows, key=lambda r: (r['path'], r['message']))[:128], len(rows) > 128


def validate_payload(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Data context exceeds its budget') from exc
    index = {key(exact(o)): o for o in exported['objects']}
    subject = index.get(key(request['subject']))
    if not subject or subject['meta']['type'] not in ('air.Message', 'air.Event'): raise InvalidModel('Subject must be an exact Message or Event in the baseline')
    if digest(subject) != request['subject']['digest']: raise Conflict('Subject digest differs')
    schema_ref = subject['body'].get('schema', subject['body'].get('payload_schema'));schema_obj = index[key(schema_ref)]
    descriptor = schema_obj['body']['artifact'];manifest = store.get_record(descriptor['locator'])
    if not manifest or manifest['kind'] != 'artifact_manifest': raise InvalidModel('Schema artifact is not a retained local manifest')
    schema_lookup = {'artifact': reference(manifest)}
    schema_meta = artifacts.describe(store, principal, policy, schema_lookup)
    if schema_meta['artifact_reference'] != descriptor: raise Conflict('Schema artifact descriptor differs from its retained manifest')
    payload_lookup = {'artifact': request['payload_artifact']};payload_meta = artifacts.describe(store, principal, policy, payload_lookup)
    if schema_meta['size'] > MAX_BYTES or payload_meta['size'] > MAX_BYTES: raise InvalidModel('Data validation accepts artifacts up to 1 MiB')
    if schema_meta['media_type'] != 'application/json' or payload_meta['media_type'] != 'application/json': raise InvalidModel('Schema and payload artifacts must declare application/json')
    report = {'engine': ENGINE, 'binding': 'air.flat-json/0.23', 'baseline': request['baseline'], 'subject': request['subject'],
        'schema': {**exact(schema_obj), 'digest': digest(schema_obj)}, 'schema_artifact': schema_meta['artifact'],
        'schema_content_digest': schema_meta['content_digest'], 'payload_artifact': payload_meta['artifact'], 'payload_content_digest': payload_meta['content_digest'],
        'schema_validation': 'NOT_EXECUTED', 'field_mapping_validation': 'NOT_EXECUTED', 'payload_validation': 'NOT_EXECUTED',
        'diagnostics': [], 'diagnostics_truncated': False, 'semantic_compatibility_verified': False, 'event_truth_verified': False,
        'authorization_granted': False, 'model_updated': False, 'network_schema_resolution': False, 'request_digest': artifact_digest(request)}
    def finish():
        report['report_digest'] = artifact_digest(report)
        bounded(report)
        return report
    raw_schema = artifacts.download(store, principal, policy, schema_lookup)[1]
    try: schema = parse_external(raw_schema)
    except DataInputError as exc:
        report.update(schema_validation='VIOLATED', diagnostics=[{'path': '/schema', 'keyword': 'json', 'message': str(exc)}]);return finish()
    errors, truncated = schema_issues(schema)
    report.update(schema_validation='VIOLATED' if errors else 'SATISFIED', diagnostics=errors, diagnostics_truncated=truncated)
    if errors: return finish()
    errors, truncated = mappings(subject, schema_obj, schema, index)
    report.update(field_mapping_validation='VIOLATED' if errors else 'SATISFIED', diagnostics=errors, diagnostics_truncated=truncated)
    if errors: return finish()
    raw_payload = artifacts.download(store, principal, policy, payload_lookup)[1]
    try: payload = parse_external(raw_payload)
    except DataInputError as exc:
        report.update(payload_validation='VIOLATED', diagnostics=[{'path': '/payload', 'keyword': 'json', 'message': str(exc)}]);return finish()
    errors, truncated = diagnostics(ExactValidator(schema, format_checker=FormatChecker()).iter_errors(payload), '/payload')
    report.update(payload_validation='VIOLATED' if errors else 'SATISFIED', diagnostics=errors, diagnostics_truncated=truncated)
    return finish()
