"""Declared architecture blocks, HTTP and messaging bindings, and flows, without deployment effects."""
import re
from urllib.parse import urlsplit

PROFILE = 'air.architecture/0.26'
NAMES = ['ArchitectureBlock', 'TechnicalBinding', 'Port', 'DataFlow', 'RequiredOutput', 'ArchitectureGap']
HTTP_MAPPING_026 = 'air.http-json-mapping/0.26'
HTTP_MAPPING_030 = 'air.http-json-mapping/0.30'
CHANNEL_MAPPING_030 = 'air.message-channel-mapping/0.30'
MESSAGING_PROTOCOLS = ['KAFKA', 'AMQP', 'MQTT', 'NATS']
SEGMENT = r'(?:[A-Za-z0-9._~-]+|\{[A-Za-z][A-Za-z0-9_]{0,63}\})'
TEMPLATED_PATH = re.compile('^/(?:' + SEGMENT + r'(?:/' + SEGMENT + ')*)?$')
PARAMETER_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,63}$')
TEMPLATE = re.compile(r'\{([A-Za-z][A-Za-z0-9_]{0,63})\}')
ROLE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$')
BROKER_SCHEMES = ('kafka', 'amqp', 'amqps', 'mqtt', 'mqtts', 'nats', 'tls', 'ssl', 'tcp', 'ws', 'wss')
ERROR_STATUS = ['400', '401', '403', '404', '405', '409', '410', '412', '415', '422', '429', '500', '502', '503', '504']


def bodies(record, text, uri, ref, refs, nonempty):
    many = {**nonempty, 'maxItems': 128};optional = {**refs, 'maxItems': 128}
    field = record({'binding': {'const': 'air.field/0.23'}, 'name': {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]{0,63}$'}})
    mapping = record({'binding': {'const': HTTP_MAPPING_026}, 'operation': {**text, 'maxLength': 128},
        'method': {'enum': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']}, 'path': {'type': 'string', 'pattern': '^/[A-Za-z0-9._~/-]*$', 'maxLength': 256},
        'request_schema': ref, 'request_required': {'type': 'boolean'}, 'response_schema': ref, 'response_status': {'enum': ['200', '201', '202']}},
        ['binding', 'operation', 'method', 'path', 'response_schema', 'response_status'])
    parameter = record({'name': {'type': 'string', 'pattern': PARAMETER_NAME.pattern, 'maxLength': 64},
        'in': {'enum': ['path', 'query', 'header']}, 'required': {'type': 'boolean'}, 'description': {**text, 'maxLength': 512},
        'type': {'enum': ['string', 'integer', 'number', 'boolean']}, 'format': {'enum': ['date-time', 'uri']},
        'enum': {'type': 'array', 'items': {'type': ['string', 'number', 'integer', 'boolean']}, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True}},
        ['name', 'in', 'required', 'type'])
    failure = record({'code': {**text, 'maxLength': 128}, 'status': {'enum': ERROR_STATUS}, 'response_schema': ref}, ['code', 'status', 'response_schema'])
    mapping30 = record({'binding': {'const': HTTP_MAPPING_030}, 'operation': {**text, 'maxLength': 128},
        'method': {'enum': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']}, 'path': {'type': 'string', 'pattern': TEMPLATED_PATH.pattern, 'maxLength': 256},
        'request_schema': ref, 'request_required': {'type': 'boolean'}, 'response_schema': ref,
        'response_status': {'enum': ['200', '201', '202', '204']},
        'parameters': {'type': 'array', 'items': parameter, 'maxItems': 64}, 'errors': {'type': 'array', 'items': failure, 'maxItems': 32},
        'authorization_roles': {'type': 'array', 'items': {'type': 'string', 'pattern': ROLE_NAME.pattern, 'maxLength': 64}, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True}},
        ['binding', 'operation', 'method', 'path', 'response_status'])
    channel = record({'binding': {'const': CHANNEL_MAPPING_030}, 'event': ref, 'channel': {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'},
        'action': {'enum': ['PUBLISH', 'SUBSCRIBE']}, 'message_schema': ref, 'key': field,
        'ordering': {'enum': ['PER_KEY', 'NONE']}, 'delivery': {'enum': ['AT_LEAST_ONCE', 'AT_MOST_ONCE', 'EFFECTIVELY_ONCE_DECLARED']}},
        ['binding', 'event', 'channel', 'action', 'message_schema', 'ordering', 'delivery'])
    security = record({'kind': {'enum': ['HTTP_BEARER', 'API_KEY', 'MUTUAL_TLS', 'OAUTH2_CLIENT_CREDENTIALS']},
        'name': {**text, 'maxLength': 128}, 'location': {'enum': ['header', 'query']}, 'token_endpoint': uri,
        'scopes': {'type': 'array', 'items': {**text, 'maxLength': 128}, 'maxItems': 64, 'uniqueItems': True}}, ['kind'])
    http_binding = record({'contract': ref, 'protocol': {'const': 'HTTP'}, 'protocol_version': {'enum': ['1.1', '2', '3']},
        'schema_mapping': {'type': 'array', 'items': {'oneOf': [mapping, mapping30]}, 'minItems': 1, 'maxItems': 128},
        'endpoint_template': {**text, 'maxLength': 2048}, 'security_binding': many, 'security_scheme': security},
        ['contract', 'protocol', 'protocol_version', 'schema_mapping', 'security_binding'])
    messaging_binding = record({'contract': ref, 'protocol': {'enum': MESSAGING_PROTOCOLS}, 'protocol_version': {**text, 'maxLength': 32},
        'channel_mapping': {'type': 'array', 'items': channel, 'minItems': 1, 'maxItems': 128},
        'endpoint_template': {**text, 'maxLength': 2048}, 'security_binding': many, 'security_scheme': security},
        ['contract', 'protocol', 'protocol_version', 'channel_mapping', 'security_binding'])
    return {
        'air.ArchitectureBlock': record({'kind': {'enum': ['SYSTEM', 'SUBSYSTEM', 'MODULE', 'ADAPTER', 'GATEWAY', 'STORE', 'EXTERNAL_SYSTEM']},
            'responsibilities': {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 128, 'uniqueItems': True}, 'functions': many,
            'provided_contracts': optional, 'required_contracts': optional, 'owned_state': optional}),
        'air.TechnicalBinding': {'oneOf': [http_binding, messaging_binding]},
        'air.Port': record({'block': ref, 'direction': {'enum': ['PROVIDED', 'REQUIRED']}, 'contract': ref, 'bindings': optional}),
        'air.DataFlow': record({'source': ref, 'destination': ref, 'schema': ref, 'purpose': text, 'transformations': optional, 'controls': optional}),
        'air.RequiredOutput': record({'expected_artifact': text, 'acceptance': many, 'construction_unit': ref, 'due_gate': text}, ['expected_artifact', 'acceptance', 'due_gate']),
        'air.ArchitectureGap': record({'missing_element_kind': text, 'affected_scope': ref, 'impact': text, 'resolution_owner': uri, 'required_output': ref},
            ['missing_element_kind', 'affected_scope', 'impact', 'resolution_owner']),
    }


def route_shape(path):
    """Two routes with the same literal segments and templates at the same positions are one OpenAPI path."""
    return TEMPLATE.sub('{}', path)


def broker_endpoint(value):
    if any(c.isspace() or ord(c) < 32 for c in value) or any(c in value for c in '?#{}' + chr(92)): return False
    try:
        parsed = urlsplit(value);port = parsed.port
    except ValueError: return False
    return (parsed.scheme in BROKER_SCHEMES and bool(parsed.hostname) and parsed.username is None and parsed.password is None
            and '@' not in parsed.netloc and (port is None or port > 0))


def messaging(body):
    """A binding declares either HTTP operations or message channels; never both."""
    return 'channel_mapping' in body


def slots(obj):
    body, kind = obj['body'], obj['meta']['type']
    fields = {
        'air.ArchitectureBlock': {'functions': ['air.Function'], 'provided_contracts': ['air.SemanticContract'], 'required_contracts': ['air.SemanticContract'], 'owned_state': ['air.DataEntity']},
        'air.TechnicalBinding': {'contract': ['air.SemanticContract'], 'security_binding': ['air.Control']},
        'air.Port': {'block': ['air.ArchitectureBlock'], 'contract': ['air.SemanticContract'], 'bindings': ['air.TechnicalBinding']},
        'air.DataFlow': {'source': ['air.ArchitectureBlock', 'air.Port', 'air.Actor', 'air.DataEntity'], 'destination': ['air.ArchitectureBlock', 'air.Port', 'air.Actor', 'air.DataEntity'],
            'schema': ['air.DataSchema'], 'transformations': ['air.Function'], 'controls': ['air.Control']},
        'air.RequiredOutput': {'acceptance': ['air.AcceptanceCriterion'], 'construction_unit': ['air.ConstructionUnit']},
        'air.ArchitectureGap': {'affected_scope': ['air.Scope'], 'required_output': ['air.RequiredOutput']},
    }.get(kind, {})
    for field, targets in fields.items():
        if field not in body: continue
        for reference in body[field] if isinstance(body[field], list) else [body[field]]: yield 'body/' + field, reference, targets
    if kind == 'air.TechnicalBinding':
        if messaging(body):
            for index, item in enumerate(body['channel_mapping']):
                yield 'body/channel_mapping/' + str(index) + '/event', item['event'], ['air.Event']
                yield 'body/channel_mapping/' + str(index) + '/message_schema', item['message_schema'], ['air.DataSchema']
            return
        for index, mapping in enumerate(body['schema_mapping']):
            for field in ('request_schema', 'response_schema'):
                if field in mapping: yield 'body/schema_mapping/' + str(index) + '/' + field, mapping[field], ['air.DataSchema']
            for position, failure in enumerate(mapping.get('errors', [])):
                yield 'body/schema_mapping/' + str(index) + '/errors/' + str(position) + '/response_schema', failure['response_schema'], ['air.DataSchema']


def local_issues(obj):
    if obj['meta']['type'] != 'air.TechnicalBinding': return
    body = obj['body']
    if messaging(body):
        channels = [(item['channel'], item['action'], (item['event']['id'], item['event']['revision'])) for item in body['channel_mapping']]
        if len(set(channels)) != len(channels):
            yield 'AIR_BINDING_DUPLICATE', 'Channel, action and exact event must be unique within a binding'
        for item in body['channel_mapping']:
            if item['ordering'] == 'PER_KEY' and 'key' not in item:
                yield 'AIR_BINDING_CHANNEL', 'Per-key ordering requires the declared key field'
        if 'endpoint_template' in body and not broker_endpoint(body['endpoint_template']):
            yield 'AIR_BINDING_ENDPOINT', ('Broker endpoint must be a declared URI (' + ', '.join(BROKER_SCHEMES)
                                           + ') without credentials, query, fragment or whitespace; secrets never belong in a dossier')
        return
    operations = [m['operation'] for m in body['schema_mapping']];routes = [(m['method'], m['path']) for m in body['schema_mapping']]
    if len(set(operations)) != len(operations) or len(set(routes)) != len(routes):
        yield 'AIR_BINDING_DUPLICATE', 'Operations and method/path routes must each be unique within a binding'
    shapes = {}
    for m in body['schema_mapping']:
        shapes.setdefault(route_shape(m['path']), set()).add(m['path'])
    for shape, paths in sorted(shapes.items()):
        if len(paths) > 1:
            yield 'AIR_BINDING_PATH', ('Templated routes differ only by parameter names, which OpenAPI treats as the same path: '
                                       + ', '.join(sorted(paths)) + '; use one parameter name per position')
    for mapping in body['schema_mapping']:
        modern = mapping['binding'] == HTTP_MAPPING_030
        if ('request_schema' in mapping) != ('request_required' in mapping):
            yield 'AIR_BINDING_BODY', 'Request schema and required flag must be declared together'
        if '//' in mapping['path'] or any(p in ('.', '..') for p in mapping['path'].split('/')):
            yield 'AIR_BINDING_PATH', 'Literal routes cannot contain double separators or dot segments'
        if mapping['method'] in ('GET', 'DELETE') and 'request_schema' in mapping:
            yield 'AIR_BINDING_BODY', 'GET and DELETE request bodies are outside this binding'
        if not modern:
            continue
        declared = {p['name'] for p in mapping.get('parameters', []) if p['in'] == 'path'}
        occurrences = TEMPLATE.findall(mapping['path'])
        if len(set(occurrences)) != len(occurrences):
            yield 'AIR_BINDING_PARAMETER', 'A path parameter name appears once per route: ' + mapping['path']
        templated = set(occurrences)
        if templated - declared:
            yield 'AIR_BINDING_PARAMETER', 'Every path template names a declared path parameter: ' + ', '.join(sorted(templated - declared))
        if declared - templated:
            yield 'AIR_BINDING_PARAMETER', 'Path parameters must appear in the route: ' + ', '.join(sorted(declared - templated))
        if any(not p['required'] for p in mapping.get('parameters', []) if p['in'] == 'path'):
            yield 'AIR_BINDING_PARAMETER', 'Path parameters are always required'
        names = [(p['in'], p['name'].lower()) for p in mapping.get('parameters', [])]
        if len(set(names)) != len(names):
            yield 'AIR_BINDING_PARAMETER', 'Parameter names are unique per location'
        codes = [failure['code'] for failure in mapping.get('errors', [])]
        if len(set(codes)) != len(codes):
            yield 'AIR_BINDING_ERROR', 'Error codes are unique within an operation'
        if mapping['response_status'] == '204' and 'response_schema' in mapping:
            yield 'AIR_BINDING_BODY', 'A 204 response declares no body'
        if mapping['response_status'] != '204' and 'response_schema' not in mapping:
            yield 'AIR_BINDING_BODY', 'A response with content declares its schema'
    if 'security_scheme' in body:
        scheme = body['security_scheme']
        if scheme['kind'] == 'API_KEY' and not {'name', 'location'} <= scheme.keys():
            yield 'AIR_BINDING_SECURITY', 'An API key declares its name and location'
        if scheme['kind'] == 'OAUTH2_CLIENT_CREDENTIALS' and 'token_endpoint' not in scheme:
            yield 'AIR_BINDING_SECURITY', 'OAuth2 client credentials declare a token endpoint'
    if 'endpoint_template' in body:
        try:
            parsed = urlsplit(body['endpoint_template']);port = parsed.port
            valid = parsed.scheme in ('http', 'https') and parsed.hostname and parsed.username is None and parsed.password is None and not any(c in body['endpoint_template'] for c in '?#') and (port is None or port > 0)
            valid = valid and not any(c.isspace() or ord(c) < 32 for c in body['endpoint_template']) and not any(c in body['endpoint_template'] for c in '{}\\')
        except ValueError: valid = False
        if not valid: yield 'AIR_BINDING_ENDPOINT', 'Endpoint must be a declared absolute HTTP(S) base URL without credentials, query, fragment or variables'


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    for obj in objects:
        body, kind = obj['body'], obj['meta']['type'];location = obj['meta']['id']
        if kind == 'air.TechnicalBinding':
            contract = by_ref.get(key(body['contract']))
            if not contract or contract['meta']['type'] != 'air.SemanticContract': continue
            if messaging(body):
                for item in body['channel_mapping']:
                    event = by_ref.get(key(item['event']))
                    if not event or event['meta']['type'] != 'air.Event': continue
                    if 'delivery_contract' in event['body'] and key(event['body']['delivery_contract']) != key(body['contract']):
                        yield 'AIR_BINDING_CHANNEL', location, 'A channel carries an event delivered under the same exact contract'
                    if key(item['message_schema']) != key(event['body']['payload_schema']):
                        yield 'AIR_BINDING_CHANNEL', location, 'A channel message schema is the exact payload schema of its event'
                continue
            known = {op['name'] for op in contract['body']['operations']}
            if any(m['operation'] not in known for m in body['schema_mapping']):
                yield 'AIR_BINDING_OPERATION', location, 'Each mapping must name an operation of its exact semantic contract'
            declared = {failure['code'] for failure in contract['body']['error_contract']}
            mapped = {failure['code'] for m in body['schema_mapping'] for failure in m.get('errors', [])}
            if mapped - declared:
                yield 'AIR_BINDING_ERROR', location, 'Mapped error codes must be declared by the exact contract: ' + ', '.join(sorted(mapped - declared))
        elif kind == 'air.Port':
            block = by_ref.get(key(body['block']))
            field = 'provided_contracts' if body['direction'] == 'PROVIDED' else 'required_contracts'
            if block and block['meta']['type'] == 'air.ArchitectureBlock' and key(body['contract']) not in {key(r) for r in block['body'][field]}:
                yield 'AIR_PORT_CONTRACT', location, 'Port direction and exact contract must match its block declaration'
            for ref in body['bindings']:
                binding = by_ref.get(key(ref))
                if binding and binding['meta']['type'] == 'air.TechnicalBinding' and key(binding['body']['contract']) != key(body['contract']):
                    yield 'AIR_PORT_BINDING', location, 'Port and binding must reference the same exact semantic contract'


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type'];key = lambda r: (r['id'], r['revision'])
    fields = {'air.ArchitectureBlock': ['functions', 'provided_contracts', 'required_contracts', 'owned_state'], 'air.TechnicalBinding': ['security_binding'],
        'air.Port': ['bindings'], 'air.DataFlow': ['controls'], 'air.RequiredOutput': ['acceptance']}.get(kind, [])
    for field in fields: body[field].sort(key=key)
    if kind == 'air.ArchitectureBlock': body['responsibilities'].sort()
    if kind == 'air.TechnicalBinding':
        if messaging(body): body['channel_mapping'].sort(key=lambda c: (c['channel'], c['action'], c['event']['id'], c['event']['revision']))
        else:
            body['schema_mapping'].sort(key=lambda m: (m['operation'], m['method'], m['path']))
            for mapping in body['schema_mapping']:
                if 'errors' in mapping: mapping['errors'].sort(key=lambda f: f['code'])
                if 'parameters' in mapping: mapping['parameters'].sort(key=lambda p: (p['in'], p['name']))
    # Flow transformations retain order: no implicit composition is performed.
