"""Declared inference and conflict subset of white paper A.2, without truth promotion."""
from datetime import datetime
from air.expr import Program, bounded, typed, wire, ExprError

PROFILE = 'air.knowledge/0.17'
NAMES = ['Inference', 'Conflict']


def bodies(record, text, ref, refs, nonempty):
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'const': '0.1'},
        'ast': {'type': 'object'}, 'result_type': text,
        'required_inputs': {'type': 'array', 'items': record({'name': text, 'type': text}), 'maxItems': 256}},
        ['language', 'language_version', 'ast', 'result_type'])
    return {
        'air.Inference': record({'conclusion': ref, 'premises': {**nonempty, 'maxItems': 256},
            'derivation': {'oneOf': [text, expression]}, 'limitations': {'type': 'array', 'items': text, 'maxItems': 256}}),
        'air.Conflict': record({'statements': {**refs, 'minItems': 2, 'maxItems': 256},
            'overlap_scope': ref, 'reason': text, 'resolution': ref}, ['statements', 'overlap_scope', 'reason']),
    }


def literal_values(expression):
    pending = [expression['ast']]
    while pending:
        node = pending.pop()
        if 'literal' in node: yield node['literal']
        pending.extend(node.get('args', []))
        if 'over' in node: pending.extend([node['over'], node['predicate']])


def slots(obj, data_types):
    kind, body = obj['meta']['type'], obj['body']
    if kind == 'air.Inference':
        yield 'body/conclusion', body['conclusion'], ['air.Assertion']
        for ref in body['premises']: yield 'body/premises', ref, ['air.Assertion']
        if isinstance(body['derivation'], dict):
            try: Program(body['derivation'])
            except ExprError: return
            for value in literal_values(body['derivation']):
                checked = typed(value)
                if checked.type == 'Reference': yield 'body/derivation/ast/literal', checked.value, data_types
                elif checked.type == 'Collection[Reference]':
                    for item in checked.value:
                        if item.state == 'KNOWN': yield 'body/derivation/ast/literal', item.value, data_types
    elif kind == 'air.Conflict':
        for ref in body['statements']: yield 'body/statements', ref, ['air.Assertion']
        yield 'body/overlap_scope', body['overlap_scope'], ['air.Scope']
        if 'resolution' in body: yield 'body/resolution', body['resolution'], ['air.Decision']


def local_issues(obj):
    kind, body = obj['meta']['type'], obj['body']
    if kind == 'air.Inference':
        if body['conclusion'] in body['premises']:
            yield 'AIR_INFERENCE_SELF', 'An assertion cannot be its own premise'
        if isinstance(body['derivation'], dict):
            try: bounded(body['derivation']);Program(body['derivation'])
            except ExprError as exc: yield exc.code, str(exc)
    elif kind == 'air.Conflict' and len({r['id'] for r in body['statements']}) != len(body['statements']):
        yield 'AIR_CONFLICT_STATEMENTS', 'Conflict statements must have distinct assertion identities'


def graph_issues(objects, by_ref):
    def key(ref): return ref['id'], ref['revision']
    def lookup(ref, kind):
        obj = by_ref.get(key(ref))
        return obj if obj and obj['meta']['type'] == kind else None
    dependencies = {}
    for obj in objects:
        body = obj['body']
        if obj['meta']['type'] == 'air.Inference':
            conclusion = key(body['conclusion'])
            dependencies.setdefault(conclusion, set()).update(key(r) for r in body['premises'])
        elif obj['meta']['type'] == 'air.Conflict':
            statements = [lookup(ref, 'air.Assertion') for ref in body['statements']]
            scope = lookup(body['overlap_scope'], 'air.Scope')
            if not scope or not all(statements): continue
            if any(a['body']['subject_scope'] != body['overlap_scope'] for a in statements):
                yield 'AIR_CONFLICT_SCOPE', obj['meta']['id'], 'This profile requires one identical exact scope for every conflicting assertion'
            periods = [x['meta']['validity'] for x in [obj, scope, *statements]]
            start = max(datetime.fromisoformat(p['start']) for p in periods)
            ends = [datetime.fromisoformat(p['end']) for p in periods if p['end']]
            if ends and min(ends) <= start:
                yield 'AIR_CONFLICT_PERIOD', obj['meta']['id'], 'The declared conflict and its assertions need a nonempty common validity interval'
    # Iterative graph walk supports the full bounded baseline without Python recursion.
    state = {}
    for initial in sorted(dependencies):
        if state.get(initial): continue
        pending = [(initial, False)]
        while pending:
            node, leaving = pending.pop()
            if leaving:
                state[node] = 2;continue
            if state.get(node) == 1:
                yield 'AIR_INFERENCE_CYCLE', node[0], 'Conclusion-to-premise dependencies contain a cycle'
                return
            if state.get(node) == 2: continue
            state[node] = 1
            pending.append((node, True))
            pending.extend((child, False) for child in sorted(dependencies.get(node, set()), reverse=True))


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type']
    key = lambda r: (r['id'], r['revision'])
    if kind == 'air.Conflict': body['statements'].sort(key=key)
    if kind == 'air.Inference':
        body['premises'].sort(key=key)
        if isinstance(body['derivation'], dict):
            expression = body['derivation']
            if 'required_inputs' in expression: expression['required_inputs'].sort(key=lambda spec: spec['name'])
            for value in literal_values(expression):
                normalized = wire(typed(value));value.clear();value.update(normalized)
