"""Explicit bounded state machine binding for illustrative deterministic replay."""
from air.expr import Program, bounded, typed, wire, ExprError
from air.knowledge_schema import literal_values

PROFILE = 'air.state/0.24'
NAMES = ['StateMachine']
ID = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]{0,63}$'}
RESERVED = 'air_state'


def bodies(record, text):
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'enum': ['0.1', '0.2']},
        'ast': {'type': 'object'}, 'result_type': {'const': 'Boolean'},
        'required_inputs': {'type': 'array', 'items': record({'name': ID, 'type': text}), 'maxItems': 128}},
        ['language', 'language_version', 'ast', 'result_type'])
    state = record({'binding': {'const': 'air.state-spec/0.24'}, 'id': ID, 'name': text, 'terminal': {'type': 'boolean'}})
    effect = record({'kind': {'enum': ['STATE_CHANGE', 'EVENT', 'HUMAN_ACTION', 'PHYSICAL_ACTION']}, 'description': text})
    transition = record({'binding': {'const': 'air.transition/0.24'}, 'id': ID, 'source': ID, 'target': ID,
        'trigger': ID, 'guard': expression, 'effects': {'type': 'array', 'items': effect, 'maxItems': 64}})
    return {'air.StateMachine': record({'states': {'type': 'array', 'items': state, 'minItems': 1, 'maxItems': 128},
        'initial_state': ID, 'transitions': {'type': 'array', 'items': transition, 'maxItems': 256},
        'invariants': {'type': 'array', 'items': expression, 'maxItems': 32}})}


def expressions(obj):
    if obj['meta']['type'] != 'air.StateMachine': return
    for transition in obj['body']['transitions']: yield 'body/transitions/' + transition['id'] + '/guard', transition['guard']
    for index, expression in enumerate(obj['body']['invariants']): yield 'body/invariants/' + str(index), expression


def slots(obj, data_types):
    for path, expression in expressions(obj):
        try: Program(expression)
        except ExprError: continue
        for value in literal_values(expression):
            checked = typed(value)
            if checked.type == 'Reference' and checked.state == 'KNOWN': yield path + '/ast/literal', checked.value, data_types
            elif checked.type == 'Collection[Reference]' and checked.state == 'KNOWN':
                for item in checked.value:
                    if item.state == 'KNOWN': yield path + '/ast/literal', item.value, data_types


def local_issues(obj):
    if obj['meta']['type'] != 'air.StateMachine': return
    body = obj['body'];states = {s['id'] for s in body['states']};terminal = {s['id'] for s in body['states'] if s['terminal']}
    transitions = [t['id'] for t in body['transitions']]
    if len(states) != len(body['states']) or len(set(transitions)) != len(transitions):
        yield 'AIR_STATE_ID', 'State and transition identifiers must be unique within their collection'
    if body['initial_state'] not in states or any(t['source'] not in states or t['target'] not in states for t in body['transitions']):
        yield 'AIR_STATE_LOCAL_REFERENCE', 'Initial state and transition endpoints must reference declared states'
    if any(t['source'] in terminal for t in body['transitions']):
        yield 'AIR_STATE_TERMINAL', 'Terminal states cannot declare outgoing transitions in this binding'
    inputs = {};nodes = 0
    for path, expression in expressions(obj):
        try: bounded(expression);program = Program(expression)
        except ExprError as exc:
            yield exc.code, str(exc) + ' at ' + path + ' (operators and arities: air_describe_type)';continue
        nodes += program.nodes
        for name, kind in program.inputs.items():
            if name == RESERVED and kind != 'Text': yield 'AIR_STATE_INPUT', 'Reserved state input must have type Text'
            if name in inputs and inputs[name] != kind: yield 'AIR_STATE_INPUT', 'An input name must keep one type across the machine'
            inputs[name] = kind
    if len(inputs) > 128: yield 'AIR_STATE_INPUT', 'A machine declares at most 128 distinct input names'
    if nodes > 16384: yield 'AIR_STATE_EXPRESSION_BUDGET', 'Aggregate expression node budget exceeded'


def canonicalize(obj):
    if obj['meta']['type'] != 'air.StateMachine': return
    body = obj['body'];body['states'].sort(key=lambda s: s['id']);body['transitions'].sort(key=lambda t: t['id'])
    # Invariants and declared effects retain order for diagnostic interpretation.
    for path, expression in expressions(obj):
        if 'required_inputs' in expression: expression['required_inputs'].sort(key=lambda s: s['name'])
        for value in literal_values(expression):
            normalized = wire(typed(value));value.clear();value.update(normalized)
