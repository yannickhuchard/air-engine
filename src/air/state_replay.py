"""Illustrative state replay with explicit inputs, no external effects and shared budgets."""
from air.access import ScopedStore
from air.core import TEXT, record, digest
from air.expr import Program, Budget, evaluate, typed, wire, artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot
from air.state_schema import ID, RESERVED, expressions
from air.storage import Conflict

ENGINE = 'air.state-replay/0.24'
LIMITS = {'expression_steps': 50000, 'expression_calls': 512, 'stimuli': 128}
VALUE = record({'type': TEXT, 'state': {'enum': ['KNOWN', 'UNKNOWN', 'CONFLICTING']}, 'value': {}}, ['type'])
CONTEXT = {'type': 'object', 'maxProperties': 128, 'propertyNames': ID, 'additionalProperties': VALUE}
REQUEST = record({'baseline': SNAPSHOT, 'machine': SNAPSHOT, 'initial_context': CONTEXT,
    'stimuli': {'type': 'array', 'items': record({'trigger': ID, 'context': CONTEXT}), 'maxItems': 128},
    'start_state': ID, 'continue_on_refusal': {'type': 'boolean'}}, ['baseline', 'machine', 'initial_context', 'stimuli'])


def replay(store, principal, policy, request):
    check_schema(request, REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('State replay request exceeds its budget') from exc
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('State replay context exceeds its budget') from exc
    machine = next((o for o in exported['objects'] if key(exact(o)) == key(request['machine'])), None)
    if not machine or machine['meta']['type'] != 'air.StateMachine': raise InvalidModel('Machine must be an exact member of the baseline')
    if digest(machine) != request['machine']['digest']: raise Conflict('Machine digest differs')
    declarations = {}
    for path, expression in expressions(machine): declarations.update(Program(expression).inputs)
    def context(value):
        if RESERVED in value: raise InvalidModel('Reserved state input is supplied only by the replay engine')
        if set(value) - declarations.keys(): raise InvalidModel('Replay context contains undeclared input names')
        normalized = {}
        for name, supplied in value.items():
            try: checked = typed(supplied)
            except ExprError as exc: raise InvalidModel('Invalid typed replay input') from exc
            if checked.type != declarations[name]: raise InvalidModel('Replay input type differs from its declaration')
            normalized[name] = wire(checked)
        return normalized
    initial = context(request['initial_context']);stimuli = [{**s, 'context': context(s['context'])} for s in request['stimuli']]
    body = machine['body'];states = {s['id']: s for s in body['states']}
    if 'start_state' in request and request['start_state'] not in states: raise InvalidModel('start_state is not a declared state of the machine')
    current = request.get('start_state', body['initial_state']);keep_going = request.get('continue_on_refusal', False)
    budget = Budget(limit=LIMITS['expression_steps']);calls = 0
    report = {'engine': ENGINE, 'regime': 'ILLUSTRATIVE', 'input_qualification': 'DECLARED_CONTEXTS',
        'baseline': request['baseline'], 'machine': request['machine'], 'initial_state': current,
        'initial_invariants': [], 'trace': [], 'outcome': 'INPUT_EXHAUSTED', 'limits': dict(LIMITS),
        'external_actions_executed': False, 'business_verification_granted': False, 'authorization_granted': False,
        'model_updated': False, 'request_digest': artifact_digest(request),
        'started_from': 'DECLARED_START_STATE' if 'start_state' in request else 'INITIAL_STATE',
        'trigger_sources': {trigger: sorted({t['source'] for t in body['transitions'] if t['trigger'] == trigger})
                            for trigger in sorted({s['trigger'] for s in request['stimuli']})}}
    def run(expression, values, state):
        nonlocal calls
        if calls >= LIMITS['expression_calls']:
            return {'execution': 'BUDGET_EXCEEDED', 'result': 'UNKNOWN', 'diagnostics': [{'code': 'AIR_STATE_CALL_BUDGET', 'message': 'Expression call budget exhausted'}], 'diagnostics_total': 1, 'cost': {'steps': 0, 'limit': budget.limit}}
        calls += 1
        names = {s['name'] for s in expression.get('required_inputs', [])}
        inputs = {name: value for name, value in values.items() if name in names}
        if RESERVED in names: inputs[RESERVED] = {'type': 'Text', 'value': state}
        result = evaluate({'expression': expression, 'inputs': inputs}, budget=budget)
        diagnostics = [{k: str(v)[:256] for k, v in d.items()} for d in result['diagnostics'][:4]]
        return {'execution': result['execution'], 'result': result['result'], 'diagnostics': diagnostics,
                'diagnostics_total': len(result['diagnostics']), 'cost': result['cost']}
    def invariants(values, state):
        results = []
        for index, expression in enumerate(body['invariants']):
            value = run(expression, values, state);results.append({'index': index, **value})
            if value['execution'] != 'EXECUTED' or value['result'] != 'SATISFIED': break
        return results
    def failure(results, invariant=False):
        if any(r['execution'] == 'BUDGET_EXCEEDED' for r in results): return 'BUDGET_EXCEEDED'
        if any(r['execution'] != 'EXECUTED' for r in results): return 'EVALUATION_ERROR'
        if any(r['result'] == 'CONFLICTING' for r in results): return 'CONFLICTING'
        if any(r['result'] == 'UNKNOWN' for r in results): return 'UNKNOWN'
        if invariant and any(r['result'] == 'VIOLATED' for r in results): return 'INVARIANT_VIOLATED'
        return None
    report['initial_invariants'] = invariants(initial, current)
    outcome = failure(report['initial_invariants'], True)
    initial_valid = outcome is None
    if outcome: report['outcome'] = outcome
    else:
        for index, stimulus in enumerate(stimuli):
            frame = {'index': index, 'trigger': stimulus['trigger'], 'source': current, 'target': current,
                     'context_digest': artifact_digest(stimulus['context']), 'guards': [], 'pre_invariants': [], 'post_invariants': [],
                     'transition_applied': False, 'state_changed': False, 'declared_effects_count': 0}
            report['trace'].append(frame)
            if states[current]['terminal']:
                frame['outcome'] = 'TERMINAL_STATE'
                if keep_going: continue
                report['outcome'] = 'TERMINAL_STATE';break
            frame['pre_invariants'] = invariants(stimulus['context'], current)
            outcome = failure(frame['pre_invariants'], True)
            candidates = [t for t in body['transitions'] if t['source'] == current and t['trigger'] == stimulus['trigger']]
            if not outcome:
                for transition in sorted(candidates, key=lambda t: t['id']):
                    value = run(transition['guard'], stimulus['context'], current)
                    frame['guards'].append({'transition': transition['id'], **value})
                    if value['execution'] == 'BUDGET_EXCEEDED': break
                outcome = failure(frame['guards'])
            chosen = [g['transition'] for g in frame['guards'] if g['execution'] == 'EXECUTED' and g['result'] == 'SATISFIED']
            if outcome not in ('BUDGET_EXCEEDED', 'EVALUATION_ERROR', 'CONFLICTING') and len(chosen) > 1: outcome = 'CONFLICTING'
            if not outcome and not chosen: outcome = 'NO_TRANSITION'
            if not outcome:
                transition = next(t for t in candidates if t['id'] == chosen[0])
                frame.update(proposed_transition=transition['id'], proposed_target=transition['target'])
                frame['post_invariants'] = invariants(stimulus['context'], transition['target'])
                outcome = failure(frame['post_invariants'], True)
                if not outcome:
                    current = transition['target'];frame.update(target=current, transition_applied=True, state_changed=current != frame['source'],
                        transition=transition['id'], declared_effects_count=len(transition['effects']))
                    frame['outcome'] = 'TRANSITION_APPLIED'
            if outcome:
                frame['outcome'] = outcome
                if keep_going and outcome in ('NO_TRANSITION', 'UNKNOWN'): continue
                report['outcome'] = outcome;break
    if report['outcome'] == 'INPUT_EXHAUSTED' and states[current]['terminal'] and initial_valid: report['outcome'] = 'TERMINAL_REACHED'
    report.update(final_state=current, terminal_state_reached=states[current]['terminal'] and initial_valid,
                  stimuli_attempted=len(report['trace']),
                  stimuli_consumed=sum(1 for f in report['trace'] if f['transition_applied']),
                  stimuli_unprocessed=len(stimuli) - len(report['trace']),
                  stimuli_refused=sum(1 for f in report['trace'] if f.get('outcome') in ('NO_TRANSITION', 'TERMINAL_STATE', 'UNKNOWN')),
                  cost={'steps': budget.used, 'expression_calls': calls})
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('State replay report exceeds its budget') from exc
    return report
