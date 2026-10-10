"""Bounded, offline interface design checks. No endpoint or business runtime."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from itertools import islice
from air.access import ScopedStore
from air.core import record, TEXT, digest
from air.expr import ExprError, evaluate, artifact_digest, bounded
from air.foundation import InvalidModel, check_schema, key
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict
from air.atelier import product

ENGINE = 'air.interface-contracts/1'
REQUEST = record({'baseline': SNAPSHOT, 'specification': SNAPSHOT, 'content': {'enum': ['FULL', 'DIGESTS']}}, ['baseline', 'specification'])
VERIFY_REQUEST = record({'baseline': SNAPSHOT, 'specification': SNAPSHOT, 'operation': {**TEXT, 'maxLength': 128},
    'request': {}, 'response': {}}, ['baseline', 'specification', 'operation', 'request'])
MISSING = object()
UNVERIFIED = ['Authorization enforcement', 'Idempotency storage and replay', 'Concurrency and timing',
    'Retries and compensation', 'Compatibility with earlier versions', 'Runtime state and side effects', 'Error responses']
KEYWORDS = {'$schema', 'title', 'description', 'type', 'properties', 'required', 'additionalProperties', 'items',
    'enum', 'const', 'minimum', 'maximum', 'minLength', 'maxLength', 'minItems', 'maxItems'}


def schema_issues(schema):
    """A deliberately small structural subset; no references, regex or network."""
    issues = []
    count = 0
    def visit(s, depth=0):
        nonlocal count
        count += 1
        if count > 256 or depth > 12:
            raise ValueError('Schema exceeds 256 nodes or depth 12')
        if not isinstance(s, dict): raise ValueError('Schema nodes must be objects')
        if set(s) - KEYWORDS: raise ValueError('Unsupported schema keywords: ' + ', '.join(sorted(set(s) - KEYWORDS)))
        if s.get('$schema', 'https://json-schema.org/draft/2020-12/schema') != 'https://json-schema.org/draft/2020-12/schema':
            raise ValueError('Only JSON Schema 2020-12 is supported')
        if s.get('type') not in ('object', 'array', 'string', 'integer', 'number', 'boolean', 'null'):
            raise ValueError('Each schema node needs one explicit type')
        if 'additionalProperties' in s and not isinstance(s['additionalProperties'], bool):
            raise ValueError('additionalProperties must be boolean')
        if s['type'] == 'object' and 'additionalProperties' not in s:
            raise ValueError('Object schemas must state additionalProperties explicitly')
        props = s.get('properties', {})
        if not isinstance(props, dict) or len(props) > 64: raise ValueError('At most 64 object properties')
        for child in props.values(): visit(child, depth + 1)
        if 'items' in s: visit(s['items'], depth + 1)
        if s['type'] == 'array' and ('items' not in s or 'maxItems' not in s or s['maxItems'] > 256):
            raise ValueError('Array schemas need items and maxItems <= 256')
        if len(s.get('enum', [])) > 64: raise ValueError('At most 64 enum entries')
        if set(s.get('required', [])) - set(props): raise ValueError('Required properties must be defined')
    try:
        bounded(schema); Draft202012Validator.check_schema(schema); visit(schema)
    except (ValueError, ExprError, SchemaError) as exc: issues.append(str(exc).splitlines()[0])
    return issues


def pointer(document, path):
    value = document
    if not path: return value
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict): value = value[token]
        elif isinstance(value, list) and token.isdigit() and (token == '0' or not token.startswith('0')): value = value[int(token)]
        else: raise KeyError(path)
    return value


def condition_result(condition, request, response):
    values = {}
    for item in condition['inputs']:
        document = request if item['side'] == 'REQUEST' else response
        try:
            raw = pointer(document, item['pointer'])
            if item['type'] == 'Decimal':
                if isinstance(raw, bool): raise ValueError('Boolean is not Decimal')
                raw = str(raw)
            values[item['name']] = {'type': item['type'], 'value': raw}
        except (KeyError, IndexError, TypeError, ValueError):
            values[item['name']] = {'type': item['type'], 'state': 'UNKNOWN'}
    return evaluate({'expression': condition['expression'], 'inputs': values})


def verify_exchange(document, operation, request, response=MISSING):
    """Verify data and declared pure predicates, never policy enforcement."""
    bounded({'request': request, **({} if response is MISSING else {'response': response})})
    ops = [op for op in document['operations'] if op['name'] == operation]
    if len(ops) != 1: raise InvalidModel('Operation must identify exactly one specification operation')
    op = ops[0]
    issues = []
    conditions = []
    for field, value in [('request_schema', request)] + ([] if response is MISSING else [('response_schema', response)]):
        problems = schema_issues(op[field])
        if problems: raise InvalidModel('Unsupported interface schema', {'problems': problems})
        errors = list(islice(Draft202012Validator(op[field]).iter_errors(value), 64))
        issues += [{'code': 'SCHEMA', 'side': field.split('_')[0].upper(),
            'path': '/' + '/'.join(str(p) for p in e.absolute_path), 'keyword': str(e.validator)} for e in errors]
    if not issues:
        for c in op['conditions']:
            if response is MISSING and c['phase'] != 'PRE': continue
            report = condition_result(c, request, response)
            conditions.append({'name': c['name'], 'phase': c['phase'], 'result': report['result'],
                'execution': report['execution'], 'diagnostics': report['diagnostics']})
    result = ('FAIL' if issues or any(c['result'] == 'VIOLATED' for c in conditions) else
        'INCONCLUSIVE' if any(c['result'] != 'SATISFIED' for c in conditions) else 'PASS')
    report = {'engine': ENGINE, 'result': result, 'scope': 'JSON_SHAPE_AND_DECLARED_PURE_PREDICATES',
        'operation': operation, 'response_checked': response is not MISSING,
        'issues': issues, 'conditions': conditions, 'unverified': UNVERIFIED,
        'runtime_executed': False, 'authorization_granted': False,
        'input_digest': artifact_digest({'request': request, **({} if response is MISSING else {'response': response})})}
    return {**report, 'report_digest': artifact_digest(report)}


def specification_issues(spec, objects):
    index = {key(o['meta']): o for o in objects}
    b = spec['body']; issues = []
    contract = index.get(key(b['contract'])); binding = index.get(key(b['binding']))
    if not contract or contract['meta']['type'] != 'air.SemanticContract' or not binding or binding['meta']['type'] != 'air.TechnicalBinding':
        return ['CONTRACT_OR_BINDING_UNRESOLVED']
    if key(binding['body']['contract']) != key(b['contract']): issues.append('BINDING_CONTRACT_MISMATCH')
    if binding['body']['protocol'] != 'HTTP': issues.append('PROTOCOL_NOT_SUPPORTED')
    names = {o['name'] for o in contract['body']['operations']}
    if names != {o['name'] for o in b['operations']}: issues.append('OPERATION_SET_MISMATCH')
    mapped = {m['operation']: m for m in binding['body'].get('schema_mapping', [])}
    if names != set(mapped): issues.append('BINDING_OPERATION_SET_MISMATCH')
    for op in b['operations']:
        for example in op['examples']:
            try:
                observed = verify_exchange(b, op['name'], example['request'], example.get('response', MISSING))['result']
                expected = 'FAIL' if example['kind'].endswith('INVALID') else 'PASS'
                if observed != expected: issues.append('EXAMPLE_MISMATCH:' + op['name'] + ':' + example['name'])
            except (InvalidModel, ExprError): issues.append('EXAMPLE_UNCHECKABLE:' + op['name'] + ':' + example['name'])
        route = mapped.get(op['name'])
        if not route: continue
        if sorted(route.get('authorization_roles', [])) != sorted(op['authorization']['roles']):
            issues.append('AUTHORIZATION_ROLES_MISMATCH:' + op['name'])
        if op['authorization']['mode'] == 'AUTHENTICATED' and 'security_scheme' not in binding['body']:
            issues.append('SECURITY_SCHEME_MISSING:' + op['name'])
        if route['method'] not in ('GET', 'PUT', 'DELETE') and op['retry']['max_attempts'] > 1 and op['idempotency']['mode'] != 'REQUIRED':
            issues.append('UNSAFE_RETRY:' + op['name'])
        if op['idempotency']['mode'] == 'REQUIRED':
            if not any(p['in'] == 'header' and p['required'] and p['type'] == 'string' and p['name'].lower() == op['idempotency']['header'].lower()
                for p in route.get('parameters', [])):
                issues.append('IDEMPOTENCY_HEADER_MISSING:' + op['name'])
        if op['concurrency']['mode'] == 'OPTIMISTIC' and not any(p['in'] == 'header' and p['required'] and p['name'].lower() == op['concurrency']['token'].lower() for p in route.get('parameters', [])):
            issues.append('CONCURRENCY_HEADER_MISSING:' + op['name'])
        if op['compensation']['mode'] == 'OPERATION' and op['compensation']['operation'] not in names:
            issues.append('COMPENSATION_OPERATION_MISSING:' + op['name'])
    return sorted(set(issues))


def _load(store, principal, policy, request):
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    from air.completeness import snapshot_budget
    snapshot_budget(exported)
    spec = next((o for o in exported['objects'] if key(o['meta']) == key(request['specification'])), None)
    if not spec or spec['meta']['type'] != 'air.InterfaceSpecification': raise InvalidModel('Specification must be an exact baseline member')
    if digest(spec) != request['specification']['digest']: raise Conflict('Specification digest differs')
    issues = specification_issues(spec, exported['objects'])
    if issues: raise InvalidModel('Interface specification contradicts its binding', {'issues': issues})
    match_schemas(store, principal, policy, exported['objects'], spec)
    # Check the same retained artifacts as the existing compiler, not a second schema truth.
    from air.openapi_compiler import compile_openapi
    binding = next(o for o in exported['objects'] if key(o['meta']) == key(spec['body']['binding']))
    openapi = compile_openapi(store, principal, policy, {'baseline': request['baseline'],
        'binding': {**spec['body']['binding'], 'digest': digest(binding)},
        'info': {'title': spec['meta']['name'], 'version': spec['body']['version']}})
    return exported, spec, openapi


def match_schemas(store, principal, policy, objects, spec):
    """Also works on an isolated prepared candidate. Retained bytes stay exact."""
    from air import artifacts
    from air.packages import reference
    from air.data_validation import parse_external, DataInputError
    index = {key(o['meta']): o for o in objects}
    binding = index.get(key(spec['body']['binding']))
    if not binding or binding['meta']['type'] != 'air.TechnicalBinding':
        raise InvalidModel('Binding is unavailable in the exact candidate')
    routes = {m['operation']: m for m in binding['body'].get('schema_mapping', [])}
    total = 0; parsed = {}
    for op in spec['body']['operations']:
        route = routes.get(op['name'])
        if route is None: raise InvalidModel('Operation mapping is unavailable: ' + op['name'])
        for field in ('request_schema', 'response_schema'):
            ref = route.get(field)
            if ref:
                if key(ref) not in parsed:
                    schema = index.get(key(ref))
                    if not schema or schema['meta']['type'] != 'air.DataSchema':
                        raise InvalidModel('Schema reference is unavailable in the exact candidate')
                    descriptor = schema['body']['artifact']
                    manifest = store.get_record(descriptor['locator'])
                    if not manifest or manifest['kind'] != 'artifact_manifest': raise InvalidModel('Schema must be a retained local artifact')
                    lookup = {'artifact': reference(manifest)}
                    metadata = artifacts.describe(store, principal, policy, lookup)
                    if metadata['artifact_reference'] != descriptor: raise Conflict('Schema descriptor differs from retained manifest')
                    total += metadata['size']
                    if metadata['media_type'] != 'application/json' or total > 1048576: raise InvalidModel('Interface schema artifacts exceed their budget')
                    try: value = parse_external(artifacts.download(store, principal, policy, lookup)[1])
                    except DataInputError as exc: raise InvalidModel('Invalid local schema JSON') from exc
                    if schema_issues(value): raise InvalidModel('Binding schema is outside the interface subset')
                    parsed[key(ref)] = value
                value = parsed[key(ref)]
            else: value = {'type': 'null'}
            if value != op[field]: raise InvalidModel('Specification schema differs from retained binding schema: ' + op['name'] + '/' + field)


def inspect_members(store, principal, policy, exported):
    reports = []
    home = exported['baseline']['meta']['namespace']
    for spec in sorted(exported['objects'], key=lambda o: key(o['meta'])):
        if spec['meta']['namespace'] != home or spec['meta']['type'] != 'air.InterfaceSpecification': continue
        report = {'specification': {**{f: spec['meta'][f] for f in ('id', 'revision')}, 'digest': digest(spec)}, 'result': 'PASS_DESIGN_EXAMPLES'}
        try:
            issues = specification_issues(spec, exported['objects'])
            if issues: raise InvalidModel('Specification has inconsistent declarations or examples')
            match_schemas(store, principal, policy, exported['objects'], spec)
        except (InvalidModel, ExprError, Conflict) as exc: report.update(result='BLOCKED', diagnostic=str(exc))
        reports.append(report)
    return reports


def compile_suite(store, principal, policy, request):
    check_schema(request, REQUEST); bounded(request)
    exported, spec, openapi = _load(store, principal, policy, request)
    document = {'engine': ENGINE, 'baseline': request['baseline'], 'specification': request['specification'],
        'contract': spec['body']['contract'], 'binding': spec['body']['binding'],
        'version': spec['body']['version'], 'compatibility': deepcopy(spec['body']['compatibility']),
        'operations': deepcopy(spec['body']['operations']), 'unverified': UNVERIFIED, 'runtime_executed': False}
    examples = []
    for op in document['operations']:
        for example in op['examples']:
            result = verify_exchange(document, op['name'], example['request'], example.get('response', MISSING))
            expected = 'FAIL' if example['kind'].endswith('INVALID') else 'PASS'
            examples.append({'operation': op['name'], 'name': example['name'], 'kind': example['kind'],
                'expected': expected, 'observed': result['result'], 'matches': expected == result['result'], 'report': result})
    result = 'PASS_DESIGN_EXAMPLES' if all(e['matches'] for e in examples) else 'INCONCLUSIVE' if any(e['observed'] == 'INCONCLUSIVE' for e in examples) else 'FAIL_DESIGN_EXAMPLES'
    content = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
    readme = ('# Contrat de construction\n\nBaseline et spécification exactes dans interface-contract.json.\n'
        'Exécuter les exemples avec un environnement AIR installé :\n\n'
        '    python verify.py\n\n'
        'Le fournisseur et le consommateur construisent indépendamment sur le même contrat.\n'
        'Ce contrôle inspecte les formes JSON et les prédicats purs déclarés.\n'
        'Il ne prouve pas l’autorisation, les effets métier, les retries, la concurrence ou le fonctionnement réel.\n')
    verifier = '''import json
from pathlib import Path
from air.interface_contracts import verify_exchange, MISSING
doc = json.loads(Path(__file__).with_name('interface-contract.json').read_text(encoding='utf-8'))
failures = []
for op in doc['operations']:
    for example in op['examples']:
        observed = verify_exchange(doc, op['name'], example['request'], example.get('response', MISSING))['result']
        expected = 'FAIL' if example['kind'].endswith('INVALID') else 'PASS'
        if observed != expected: failures.append([op['name'], example['name'], expected, observed])
print(json.dumps({'scope': 'DESIGN_EXAMPLES_ONLY', 'failures': failures}))
raise SystemExit(bool(failures))
'''
    files = []
    for path, media, data in [('interface-contract.json', 'application/json', content), ('openapi.json', 'application/json', openapi['content']),
        ('README.md', 'text/markdown', readme), ('verify.py', 'text/plain', verifier)]:
        item = product(path, media, data, 'GENERATED')
        if request.get('content', 'FULL') != 'FULL': item.pop('content')
        files.append(item)
    report = {'engine': ENGINE, 'result': result, 'baseline': request['baseline'], 'specification': request['specification'],
        'examples': examples, 'files': files, 'source_mapping': openapi['source_mapping'], 'unverified': UNVERIFIED,
        'registry_written': False, 'endpoints_contacted': False, 'runtime_executed': False}
    bounded(report)
    return {**report, 'report_digest': artifact_digest(report)}


def verify(store, principal, policy, request):
    check_schema(request, VERIFY_REQUEST); bounded(request)
    _, spec, _ = _load(store, principal, policy, request)
    report = verify_exchange(spec['body'], request['operation'], request['request'], request.get('response', MISSING))
    return {**report, 'baseline': request['baseline'], 'specification': request['specification']}


def compile_members(store, principal, policy, exported, content='DIGESTS'):
    meta = exported['baseline']['meta']
    baseline = {'id': meta['id'], 'revision': meta['revision'], 'digest': exported['digest']}
    reports = []
    for obj in sorted(exported['objects'], key=lambda o: key(o['meta'])):
        if obj['meta']['namespace'] != meta['namespace'] or obj['meta']['type'] != 'air.InterfaceSpecification': continue
        spec = {**{f: obj['meta'][f] for f in ('id', 'revision')}, 'digest': digest(obj)}
        try: report = compile_suite(store, principal, policy, {'baseline': baseline, 'specification': spec, 'content': content})
        except (InvalidModel, ExprError) as exc:
            report = {'engine': ENGINE, 'baseline': baseline, 'specification': spec, 'result': 'BLOCKED',
                'diagnostic': str(exc), 'files': [], 'runtime_executed': False}
        reports.append(report)
    return reports
