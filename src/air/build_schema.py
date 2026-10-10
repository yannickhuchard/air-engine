"""Context and construction specifications. No deployment or inferred approval."""
from air.expr import Program, ExprError

PROFILE = 'air.build-design/0.35'
NAMES = ['DossierContext', 'InterfaceSpecification', 'DataLifecycleSpecification']
CONTEXTS = ['DIGITAL_SERVICE', 'DATA_PLATFORM', 'PHYSICAL_SYSTEM', 'ORGANIZATIONAL_CHANGE', 'REGULATED_ACTIVITY']
CATALOGUE = 'air.completeness-catalogue/1'


def bodies(record, text, uri, ref, refs, nonempty):
    short = {**text, 'maxLength': 128}
    array = lambda item, n=0: {'type': 'array', 'items': item, 'minItems': n, 'maxItems': 64}
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'enum': ['0.1', '0.2']},
        'result_type': {'const': 'Boolean'}, 'ast': {'type': 'object'},
        'required_inputs': array(record({'name': short, 'type': {'enum': ['Text', 'Boolean', 'Integer', 'Decimal']}}))})
    condition = record({'name': short, 'phase': {'enum': ['PRE', 'POST', 'INVARIANT']}, 'description': text,
        'expression': expression, 'inputs': array(record({'name': short, 'type': {'enum': ['Text', 'Boolean', 'Integer', 'Decimal']},
            'side': {'enum': ['REQUEST', 'RESPONSE']}, 'pointer': {'type': 'string', 'maxLength': 256, 'pattern': r'^(/([^~/]|~[01])*)*$'}}))})
    operation = record({'name': short, 'request_schema': {'type': 'object'}, 'response_schema': {'type': 'object'},
        'conditions': array(condition, 2),
        'authorization': record({'mode': {'enum': ['PUBLIC', 'AUTHENTICATED']}, 'roles': array(short), 'basis': text}),
        'idempotency': record({'mode': {'enum': ['REQUIRED', 'NOT_APPLICABLE']}, 'header': short,
            'window_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 2592000},
            'replay': {'enum': ['SAME_RESPONSE', 'REJECT_DUPLICATE']}, 'basis': text}, ['mode', 'basis']),
        'concurrency': record({'mode': {'enum': ['NONE', 'OPTIMISTIC', 'SERIALIZED']}, 'token': short, 'basis': text}, ['mode', 'basis']),
        'timeout_ms': {'type': 'integer', 'minimum': 1, 'maximum': 86400000},
        'retry': record({'max_attempts': {'type': 'integer', 'minimum': 1, 'maximum': 10},
            'backoff_ms': {'type': 'integer', 'minimum': 0, 'maximum': 3600000},
            'statuses': array({'type': 'integer', 'minimum': 400, 'maximum': 599})}),
        'compensation': record({'mode': {'enum': ['NOT_REQUIRED', 'OPERATION']}, 'operation': short, 'basis': text}, ['mode', 'basis']),
        'examples': array(record({'name': short, 'kind': {'enum': ['REQUEST_VALID', 'REQUEST_INVALID', 'EXCHANGE_VALID', 'EXCHANGE_INVALID']},
            'request': {}, 'response': {}}, ['name', 'kind', 'request']), 2)})
    return {
        'air.DossierContext': record({'scope': ref, 'catalogue': {'const': CATALOGUE},
            'profiles': {**array({'enum': CONTEXTS}, 1), 'uniqueItems': True}, 'rationale': text,
            'exclusions': array(record({'check_id': short, 'reason': text, 'decision': ref}))}),
        'air.InterfaceSpecification': record({'contract': ref, 'binding': ref,
            'version': {'type': 'string', 'pattern': '^[0-9]{1,4}\\.[0-9]{1,4}\\.[0-9]{1,4}$'},
            'compatibility': record({'strategy': {'enum': ['STRICT', 'BACKWARD']}, 'breaking_change_policy': text}),
            'operations': array(operation, 1)}),
        'air.DataLifecycleSpecification': record({'table': ref, 'owner': ref,
            'unique_keys': array(array(short, 1)),
            'indexes': array(record({'name': short, 'columns': array(short, 1), 'unique': {'type': 'boolean'}})),
            'retention': record({'mode': {'enum': ['FIXED_DAYS', 'NOT_APPLICABLE']}, 'days': {'type': 'integer', 'minimum': 1, 'maximum': 36500},
                'basis': text, 'trigger': text}, ['mode', 'basis', 'trigger']),
            'migration': record({'plan': text, 'verification': nonempty}),
            'rollback': record({'plan': text, 'verification': nonempty})}),
    }


def slots(obj):
    b, kind = obj['body'], obj['meta']['type']
    fields = {
        'air.DossierContext': {'scope': ['air.Scope']},
        'air.InterfaceSpecification': {'contract': ['air.SemanticContract'], 'binding': ['air.TechnicalBinding']},
        'air.DataLifecycleSpecification': {'table': ['air.PhysicalTable'], 'owner': ['air.Actor']},
    }.get(kind, {})
    for field, targets in fields.items(): yield 'body/' + field, b[field], targets
    if kind == 'air.DossierContext':
        for i, item in enumerate(b['exclusions']): yield f'body/exclusions/{i}/decision', item['decision'], ['air.Decision']
    if kind == 'air.DataLifecycleSpecification':
        for field in ('migration', 'rollback'):
            for i, ref in enumerate(b[field]['verification']): yield f'body/{field}/verification/{i}', ref, ['air.VerificationCase']


def local_issues(obj):
    b, kind = obj['body'], obj['meta']['type']
    if kind == 'air.DossierContext':
        names = [e['check_id'] for e in b['exclusions']]
        if len(names) != len(set(names)): yield 'AIR_CONTEXT_DUPLICATE', 'Duplicate excluded check'
    if kind == 'air.InterfaceSpecification':
        from air.interface_contracts import schema_issues
        if sum(len(o['examples']) for o in b['operations']) > 256 or sum(len(o['conditions']) for o in b['operations']) > 128:
            yield 'AIR_INTERFACE_BUDGET', 'At most 256 examples and 128 conditions per specification'
        names = [o['name'] for o in b['operations']]
        if len(names) != len(set(names)): yield 'AIR_INTERFACE_DUPLICATE', 'Duplicate operation'
        for op in b['operations']:
            for field in ('request_schema', 'response_schema'):
                for issue in schema_issues(op[field]): yield 'AIR_INTERFACE_SCHEMA', op['name'] + ': ' + issue
            for group in ('conditions', 'examples'):
                names = [v['name'] for v in op[group]]
                if len(names) != len(set(names)): yield 'AIR_INTERFACE_DUPLICATE', 'Duplicate ' + group
            if not {'PRE', 'POST'} <= {c['phase'] for c in op['conditions']}:
                yield 'AIR_INTERFACE_CONDITIONS', 'Each operation needs preconditions and postconditions'
            if not {'EXCHANGE_VALID', 'REQUEST_INVALID'} <= {e['kind'] for e in op['examples']}:
                yield 'AIR_INTERFACE_EXAMPLES', 'Each operation needs a valid exchange and invalid request'
            for c in op['conditions']:
                names = [i['name'] for i in c['inputs']]
                if len(names) != len(set(names)) or sorted((i['name'], i['type']) for i in c['inputs']) != sorted((i['name'], i['type']) for i in c['expression']['required_inputs']):
                    yield 'AIR_INTERFACE_INPUTS', 'Condition inputs must match expression inputs exactly'
                if c['phase'] == 'PRE' and any(i['side'] != 'REQUEST' for i in c['inputs']):
                    yield 'AIR_INTERFACE_INPUTS', 'A precondition cannot depend on the response'
                try: Program(c['expression'])
                except ExprError as exc: yield exc.code, str(exc)
                from air.knowledge_schema import literal_values
                if any(v.get('type') not in ('Text', 'Boolean', 'Integer', 'Decimal') for v in literal_values(c['expression'])):
                    yield 'AIR_INTERFACE_EXPRESSION_TYPES', 'Interface predicates only use scalar Text, Boolean, Integer and Decimal literals'
            auth = op['authorization']
            if bool(auth['roles']) != (auth['mode'] == 'AUTHENTICATED'):
                yield 'AIR_INTERFACE_AUTH', 'Authenticated operations need roles; public operations have no roles'
            idem = op['idempotency']
            extras = {'header', 'window_seconds', 'replay'} & set(idem)
            if (idem['mode'] == 'REQUIRED' and len(extras) != 3) or (idem['mode'] == 'NOT_APPLICABLE' and extras):
                yield 'AIR_INTERFACE_IDEMPOTENCY', 'Idempotency details must match its mode'
            concurrency = op['concurrency']
            if ('token' in concurrency) != (concurrency['mode'] == 'OPTIMISTIC'):
                yield 'AIR_INTERFACE_CONCURRENCY', 'Only optimistic concurrency requires a token'
            comp = op['compensation']
            if ('operation' in comp) != (comp['mode'] == 'OPERATION'):
                yield 'AIR_INTERFACE_COMPENSATION', 'Compensation details must match its mode'
            for e in op['examples']:
                if ('response' in e) != e['kind'].startswith('EXCHANGE_'):
                    yield 'AIR_INTERFACE_EXAMPLE', 'Only exchange examples include a response'
    if kind == 'air.DataLifecycleSpecification':
        if ('days' in b['retention']) != (b['retention']['mode'] == 'FIXED_DAYS'):
            yield 'AIR_DATA_RETENTION', 'Retention days must match its mode'
        names = [i['name'] for i in b['indexes']]
        if len(names) != len(set(names)): yield 'AIR_DATA_INDEX', 'Duplicate index'


def graph_issues(objects, index):
    from air.interface_contracts import specification_issues
    from air.completeness import data_issues
    for obj in objects:
        kind = obj['meta']['type']
        issues = (specification_issues(obj, objects) if kind == 'air.InterfaceSpecification' else
            data_issues(obj, objects) if kind == 'air.DataLifecycleSpecification' else [])
        for issue in issues: yield 'AIR_BUILD_SPECIFICATION', obj['meta']['id'], issue
