"""Declared workflow graphs and operating models, without execution authority."""
from air.expr import Program, bounded, typed, wire, ExprError
from air.knowledge_schema import literal_values

PROFILE = 'air.workflow/0.22'
FLOW_032 = 'air.workflow-flow/0.32'
NAMES = ['Workflow', 'OperatingModel', 'BusinessRule']


def bodies(record, text, uri, ref, refs, nonempty):
    identifier = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'}
    step = record({'binding': {'const': 'air.workflow-step/0.22'}, 'id': identifier, 'name': text, 'function': ref, 'participants': {**nonempty, 'maxItems': 64}})
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'const': '0.1'},
        'ast': {'type': 'object'}, 'result_type': {'const': 'Boolean'},
        'required_inputs': {'type': 'array', 'items': record({'name': text, 'type': text}), 'maxItems': 256}},
        ['language', 'language_version', 'ast', 'result_type'])
    flow22 = record({'binding': {'const': 'air.workflow-flow/0.22'}, 'id': identifier, 'source': identifier, 'target': identifier, 'condition': text})
    # 0.32: the condition keeps its text for readers and may carry an executable guard; a flow without guard is always taken.
    flow32 = record({'binding': {'const': FLOW_032}, 'id': identifier, 'source': identifier, 'target': identifier, 'condition': text,
                     'guard': expression}, ['binding', 'id', 'source', 'target', 'condition'])
    flow = {'oneOf': [flow22, flow32]}
    return {
        'air.Workflow': record({'steps': {'type': 'array', 'items': step, 'minItems': 1, 'maxItems': 256},
            'flows': {'type': 'array', 'items': flow, 'maxItems': 1024},
            'start_steps': {'type': 'array', 'items': identifier, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
            'termination_policy': text, 'compensations': {**refs, 'maxItems': 256}}),
        'air.OperatingModel': record({'services': {**nonempty, 'maxItems': 128}, 'responsibility_map': {**nonempty, 'maxItems': 256},
            'workflows': {**nonempty, 'maxItems': 128}, 'resource_policies': {**refs, 'maxItems': 128}}),
        'air.BusinessRule': record({'statement': text, 'applicability': text, 'expression': expression, 'authority': uri,
            'verification': {**nonempty, 'maxItems': 128}}, ['statement', 'applicability', 'authority', 'verification']),
    }


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.Workflow':
        for step in body['steps']:
            yield 'body/steps/' + step['id'] + '/function', step['function'], ['air.Function']
            for ref in step['participants']: yield 'body/steps/' + step['id'] + '/participants', ref, ['air.Actor']
        for ref in body['compensations']: yield 'body/compensations', ref, ['air.Function']
    elif kind == 'air.OperatingModel':
        for field, targets in {'services': ['air.BusinessService'], 'responsibility_map': ['air.Role', 'air.OrganizationUnit', 'air.AuthorityScope'],
                               'workflows': ['air.Workflow'], 'resource_policies': ['air.AuthorityScope']}.items():
            for ref in body[field]: yield 'body/' + field, ref, targets
    elif kind == 'air.BusinessRule':
        for ref in body['verification']: yield 'body/verification', ref, ['air.VerificationCase']
        if 'expression' in body:
            try: Program(body['expression'])
            except ExprError: return
            for value in literal_values(body['expression']):
                checked = typed(value)
                if checked.type == 'Reference' and checked.state == 'KNOWN': yield 'body/expression/ast/literal', checked.value, data_types
                elif checked.type == 'Collection[Reference]' and checked.state == 'KNOWN':
                    for item in checked.value:
                        if item.state == 'KNOWN': yield 'body/expression/ast/literal', item.value, data_types
    elif kind == 'air.OrganizationUnit' and 'operating_model' in body:
        yield 'body/operating_model', body['operating_model'], ['air.OperatingModel']


def local_issues(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.Workflow':
        ids = [s['id'] for s in body['steps']];flows = [f['id'] for f in body['flows']]
        if len(set(ids)) != len(ids) or len(set(flows)) != len(flows):
            yield 'AIR_WORKFLOW_ID', 'Step and flow identifiers must be unique within their collection'
        known = set(ids)
        if not set(body['start_steps']) <= known or any(f['source'] not in known or f['target'] not in known for f in body['flows']):
            yield 'AIR_WORKFLOW_LOCAL_REFERENCE', 'Start steps and flow endpoints must reference declared local steps'
        for flow in body['flows']:
            if 'guard' in flow:
                try: bounded(flow['guard']);Program(flow['guard'])
                except ExprError as exc: yield exc.code, str(exc) + ' at body/flows/' + flow['id'] + '/guard (operators and arities: air_describe_type)'
    elif kind == 'air.BusinessRule' and 'expression' in body:
        try: bounded(body['expression']);Program(body['expression'])
        except ExprError as exc: yield exc.code, str(exc)


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type'];key = lambda r: (r['id'], r['revision'])
    if kind == 'air.Workflow':
        body['steps'].sort(key=lambda s: s['id']);body['flows'].sort(key=lambda f: f['id']);body['start_steps'].sort();body['compensations'].sort(key=key)
        for step in body['steps']: step['participants'].sort(key=key)
        for flow in body['flows']:
            if 'guard' in flow:
                if 'required_inputs' in flow['guard']: flow['guard']['required_inputs'].sort(key=lambda p: p['name'])
                for value in literal_values(flow['guard']):
                    normalized = wire(typed(value));value.clear();value.update(normalized)
    elif kind == 'air.OperatingModel':
        for field in ('services', 'responsibility_map', 'workflows', 'resource_policies'): body[field].sort(key=key)
    elif kind == 'air.BusinessRule':
        body['verification'].sort(key=key)
        if 'expression' in body:
            expression = body['expression']
            if 'required_inputs' in expression: expression['required_inputs'].sort(key=lambda p: p['name'])
            for value in literal_values(expression):
                normalized = wire(typed(value));value.clear();value.update(normalized)
