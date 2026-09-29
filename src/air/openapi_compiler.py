"""Deterministic OpenAPI design descriptions from exact local HTTP/JSON bindings."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from importlib import metadata, resources
import json
import platform
from jsonschema import FormatChecker
from air import __version__, artifacts
from air.access import ScopedStore
from air.core import TEXT, record, digest
from air.architecture_schema import HTTP_MAPPING_030, messaging, TEMPLATE
from air.data_validation import parse_external, structured_issues, STRUCTURED, DataInputError
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.packages import reference
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict

ENGINE = 'air.openapi-compiler/0.31'
REQUEST = record({'baseline': SNAPSHOT, 'binding': SNAPSHOT,
    'info': record({'title': {**TEXT, 'maxLength': 128}, 'version': {**TEXT, 'maxLength': 128}})})
OUTPUT_MAX = 524288
SCHEMA_TOTAL_MAX = 1048576


def _toolchain():
    components = sorted([{'name': 'air/' + file.name, 'digest': 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest()}
        for file in resources.files('air').iterdir() if file.name.endswith('.py') and file.is_file()], key=lambda x: x['name'])
    return {'binding': 'air.compiler-toolchain/0.30', 'engine': ENGINE, 'air_version': __version__, 'python_version': platform.python_version(),
        'source_observation': 'MODULE_STARTUP', 'components': components, 'source_digest': artifact_digest(components),
        'dependencies': [{'name': name, 'version': metadata.version(name)} for name in ('jsonschema', 'rfc8785')]}


TOOLCHAIN = _toolchain()


def exact_json(value):
    """Sorted JSON with exact decimal numbers. This is deliberately not called JCS."""
    if value is None: return 'null'
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, int): return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite() or len(value.as_tuple().digits) > 38 or abs(value.as_tuple().exponent) > 128:
            raise InvalidModel('Decimal exceeds compilation bounds')
        return format(value, 'f')
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list): return '[' + ','.join(exact_json(x) for x in value) + ']'
    if isinstance(value, dict): return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + exact_json(value[k]) for k in sorted(value)) + '}'
    raise InvalidModel('Unsupported value in exact JSON output')


def pointer(value): return value.replace('~', '~0').replace('/', '~1')


def component_name(schema_obj, taken):
    """A reader recognises ClaimSubmission, not an empty digest; the digest stays in x-air-schema."""
    raw = schema_obj['meta']['name'] or schema_obj['meta']['id'].rsplit(':', 1)[-1]
    candidate = ''.join(part.capitalize() if not part[:1].isupper() else part for part in ''.join(
        c if c.isalnum() else ' ' for c in raw).split())
    candidate = (candidate if candidate[:1].isalpha() else 'Schema' + candidate)[:64] or 'Schema'
    if candidate not in taken: return candidate
    suffix = 2
    while candidate + str(suffix) in taken: suffix += 1
    return candidate + str(suffix)


def parameter_object(parameter):
    schema = {'type': parameter['type']}
    for field in ('format', 'enum'):
        if field in parameter: schema[field] = parameter[field]
    item = {'name': parameter['name'], 'in': parameter['in'], 'required': parameter['required'], 'schema': schema}
    if 'description' in parameter: item['description'] = parameter['description']
    return item


def security_objects(scheme):
    """Declared authentication, generated as a scheme; AIR neither verifies nor implements it."""
    kind = scheme['kind']
    if kind == 'HTTP_BEARER': generated = {'type': 'http', 'scheme': 'bearer'}
    elif kind == 'API_KEY': generated = {'type': 'apiKey', 'in': scheme['location'], 'name': scheme['name']}
    elif kind == 'MUTUAL_TLS': generated = {'type': 'mutualTLS'}
    else: generated = {'type': 'oauth2', 'flows': {'clientCredentials': {'tokenUrl': scheme['token_endpoint'],
        'scopes': {value: 'Declared scope' for value in scheme.get('scopes', [])}}}}
    generated['description'] = 'Declared by the AIR binding; not verified or implemented by this description.'
    return {'AirDeclaredScheme': generated}, [{'AirDeclaredScheme': list(scheme.get('scopes', []))}]


def compile_openapi(store, principal, policy, request):
    check_schema(request, REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('Compilation request exceeds its budget') from exc
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Compilation context exceeds its budget') from exc
    index = {key(exact(o)): o for o in exported['objects']};binding = index.get(key(request['binding']))
    if not binding or binding['meta']['type'] != 'air.TechnicalBinding': raise InvalidModel('Binding must be an exact member of the baseline')
    if digest(binding) != request['binding']['digest']: raise Conflict('Binding digest differs')
    body = binding['body'];contract = index[key(body['contract'])]
    if messaging(body): raise InvalidModel('This compiler describes HTTP bindings; a messaging binding has no OpenAPI description')
    schema_problems = []
    merged_statuses = []
    pin = lambda obj: {**exact(obj), 'digest': digest(obj)}
    mappings = [{'selector': '/x-air-baseline', 'object': request['baseline'], 'source_field': ''}, {'selector': '/x-air-binding', 'object': request['binding'], 'source_field': ''}];schema_sources = [];components = {};resolved = {};total_bytes = 0
    def schema_for(ref):
        nonlocal total_bytes
        identity = key(ref)
        if identity in resolved: return resolved[identity]
        schema_obj = index[identity];descriptor = schema_obj['body']['artifact'];manifest = store.get_record(descriptor['locator'])
        if not manifest or manifest['kind'] != 'artifact_manifest': raise InvalidModel('Schema must be a retained local artifact')
        lookup = {'artifact': reference(manifest)};meta = artifacts.describe(store, principal, policy, lookup)
        if meta['artifact_reference'] != descriptor: raise Conflict('Schema descriptor differs from its retained manifest')
        total_bytes += meta['size']
        if meta['media_type'] != 'application/json' or total_bytes > SCHEMA_TOTAL_MAX: raise InvalidModel('Schema artifacts exceed compilation MIME or byte bounds')
        raw = artifacts.download(store, principal, policy, lookup)[1]
        try: parsed = parse_external(raw)
        except DataInputError as exc: raise InvalidModel('Invalid local schema JSON') from exc
        issues, truncated = structured_issues(parsed)
        if issues:
            schema_problems.append({'schema': pin(schema_obj), 'name': schema_obj['meta']['name'], 'subset': STRUCTURED,
                                    'issues': issues, 'issues_truncated': truncated})
        name = component_name(schema_obj, components);components[name] = parsed;resolved[identity] = name
        origin = {'schema': pin(schema_obj), 'artifact': meta['artifact'], 'content_digest': meta['content_digest']}
        schema_sources.append(origin)
        mappings.append({'selector': '/components/schemas/' + name, 'object': pin(schema_obj), 'source_field': '/body/artifact', 'artifact': meta['artifact']})
        return name
    document = {'openapi': '3.1.1', 'info': {**request['info'], 'description': 'AIR design description. Security mechanisms and business behavior require independent implementation and verification.'},
        'paths': {}, 'components': {'schemas': components}, 'x-air-baseline': request['baseline'], 'x-air-binding': request['binding'],
        'x-air-status': 'DRAFT_DESIGN_ONLY', 'x-air-security-unmapped': True}
    if 'endpoint_template' in body:
        if not FormatChecker().conforms(body['endpoint_template'], 'uri'): raise InvalidModel('Endpoint is not a URI accepted by this compiler')
        document['servers'] = [{'url': body['endpoint_template'], 'description': 'Declared endpoint; not contacted or deployed by AIR'}]
        mappings.append({'selector': '/servers/0/url', 'object': pin(binding), 'source_field': '/body/endpoint_template'})
    known = {op['name']: op for op in contract['body']['operations']};mapped = set();mapped_errors = set()
    declared_errors = {failure['code']: failure for failure in contract['body']['error_contract']}
    for item in sorted(body['schema_mapping'], key=lambda m: (m['path'], m['method'])):
        operation = known[item['operation']];mapped.add(item['operation']);method = item['method'].lower();route = item['path'];base = '/paths/' + pointer(route) + '/' + method
        function = index[key(operation['function'])]
        responses = {}
        if 'response_schema' in item:
            responses[item['response_status']] = {'description': 'Declared response for ' + item['operation'],
                'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + schema_for(item['response_schema'])}}}}
        else:
            responses[item['response_status']] = {'description': 'Declared response for ' + item['operation'] + ' without content'}
        generated = {'operationId': item['operation'], 'summary': item['operation'], 'description': function['meta']['description'],
            'tags': [contract['meta']['name']], 'responses': responses,
            'x-air-contract': pin(contract), 'x-air-function': pin(function), 'x-air-controls': body['security_binding'],
            'x-air-security-unmapped': 'security_scheme' not in body}
        if item.get('parameters'):
            generated['parameters'] = [parameter_object(p) for p in sorted(item['parameters'], key=lambda p: (p['in'], p['name']))]
        if item.get('authorization_roles'):
            # OpenAPI 3.1 lets a requirement list role names for any scheme type; without a scheme the roles stay declared.
            generated['x-air-authorization-roles'] = sorted(item['authorization_roles'])
            if 'security_scheme' in body:
                generated['security'] = [{'AirDeclaredScheme': sorted(item['authorization_roles'])}]
        by_status = {}
        for failure in sorted(item.get('errors', []), key=lambda f: f['code']):
            mapped_errors.add(failure['code'])
            by_status.setdefault(failure['status'], []).append(failure)
        for status, failures in sorted(by_status.items()):
            refs = []
            for failure in failures:
                ref = {'$ref': '#/components/schemas/' + schema_for(failure['response_schema'])}
                if ref not in refs: refs.append(ref)
            texts = [f['code'] + (': ' + declared_errors[f['code']]['response'] if f['code'] in declared_errors else '') for f in failures]
            response = {'description': ' | '.join(texts), 'content': {'application/problem+json': {'schema': refs[0] if len(refs) == 1 else {'oneOf': refs}}},
                        'x-air-error-codes': [f['code'] for f in failures]}
            modes = [declared_errors[f['code']]['failure_mode'] for f in failures if f['code'] in declared_errors]
            if len(failures) == 1 and modes: response['x-air-failure-mode'] = modes[0]
            elif modes: response['x-air-failure-modes'] = modes
            if len(failures) > 1:
                merged_statuses.append({'operation': item['operation'], 'status': status, 'error_codes': [f['code'] for f in failures]})
            responses[status] = response
        if 'request_schema' in item:
            request_name = schema_for(item['request_schema'])
            generated['requestBody'] = {'required': item['request_required'], 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + request_name}}}}
        document['paths'].setdefault(route, {})[method] = generated
        source_index = next(i for i, m in enumerate(body['schema_mapping']) if m['operation'] == item['operation'])
        mappings.append({'selector': base, 'object': pin(binding), 'source_field': '/body/schema_mapping/' + str(source_index)})
        mappings.append({'selector': base + '/x-air-function', 'object': pin(index[key(operation['function'])]), 'source_field': ''})
        mappings.append({'selector': base + '/x-air-contract', 'object': pin(contract), 'source_field': ''})
        mappings.append({'selector': base + '/x-air-controls', 'object': pin(binding), 'source_field': '/body/security_binding'})
    if 'security_scheme' in body:
        schemes, requirement = security_objects(body['security_scheme'])
        document['components']['securitySchemes'] = schemes;document['security'] = requirement
        mappings.append({'selector': '/components/securitySchemes', 'object': pin(binding), 'source_field': '/body/security_scheme'})
    document['tags'] = [{'name': contract['meta']['name'], 'description': contract['meta']['description']}]
    unmapped_errors = sorted(set(declared_errors) - mapped_errors)
    if merged_statuses:
        merged_loss = [{'code': 'ERROR_STATUS_SHARED', 'objects': [pin(binding)], 'responses': merged_statuses,
                        'detail': 'Several error codes share one HTTP status: the response lists every code; a client tells them apart by the problem type, not by the status'}]
    else:
        merged_loss = []
    losses = [
        {'code': 'ENTITY_MAPPING_NOT_VERIFIED', 'objects': [s['schema'] for s in schema_sources], 'detail': 'Schema shape is validated; represented data-entity semantics are not qualified by this compilation'},
        {'code': 'SECURITY_NOT_VERIFIED', 'objects': [pin(index[key(r)]) for r in body['security_binding']],
         'detail': ('A declared security scheme is generated; it is not verified, and the referenced controls are not implemented'
                    if 'security_scheme' in body else 'Declared controls are references, not generated authentication or authorization mechanisms')},
        {'code': 'BEHAVIOR_NOT_IMPLEMENTED', 'objects': [pin(contract)], 'detail': 'Authorization, effects, pre/postconditions and runtime behavior are not implemented by this description'},
    ]
    losses += merged_loss
    if unmapped_errors:
        losses.append({'code': 'ERROR_CONTRACT_NOT_MAPPED', 'objects': [pin(contract)], 'error_codes': unmapped_errors,
                       'detail': 'Contract error codes without a mapped status remain absent from the description'})
    if schema_problems:
        raise InvalidModel('Schemas outside ' + STRUCTURED, {'schemas': sorted(schema_problems, key=lambda s: s['schema']['id'])})
    unmapped = sorted(set(known) - mapped)
    if unmapped: losses.append({'code': 'OPERATIONS_NOT_MAPPED', 'objects': [pin(contract)], 'operations': unmapped, 'detail': 'Contract operations without a route remain absent from the description'})
    document['x-air-losses'] = [loss['code'] for loss in losses]
    content = exact_json(document) + '\n'
    try: raw = content.encode('utf-8')
    except UnicodeError as exc: raise InvalidModel('Invalid Unicode in compilation') from exc
    if len(raw) > OUTPUT_MAX: raise InvalidModel('OpenAPI output exceeds 512 KiB')
    report = {'engine': ENGINE, 'regime': 'DESIGN_ONLY', 'baseline': request['baseline'], 'binding': request['binding'], 'format': 'OpenAPI 3.1.1',
        'media_type': 'application/json', 'content': content, 'content_digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size': len(raw),
        'generator': deepcopy(TOOLCHAIN), 'source_mapping': sorted(mappings, key=lambda m: (m['selector'], m['object']['id'])),
        'context_mapping': [{'selector': '/info/title', 'request_field': '/info/title'}, {'selector': '/info/version', 'request_field': '/info/version'}],
        'schema_sources': sorted(schema_sources, key=lambda s: key(s['schema'])), 'losses': losses, 'schema_subset': STRUCTURED,
        'error_responses_generated': sorted(mapped_errors), 'parameters_generated': sum(len(m.get('parameters', [])) for m in body['schema_mapping']),
        'operation_coverage': {'mapped': sorted(mapped), 'unmapped': unmapped, 'complete': not unmapped},
        'external_schema_resolution': False, 'endpoints_contacted': False, 'security_verified': False, 'behavior_implemented': False, 'data_model_conformance_verified': False,
        'authorization_granted': False, 'model_updated': False, 'request_digest': artifact_digest(request)}
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Compilation report exceeds its budget') from exc
    return report
