"""Finite, deterministic counterexample search over declared design inputs only."""
from itertools import product
from air import interface_contracts, state_replay
from air.core import record, TEXT
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, InvalidModel
from air.projections import SNAPSHOT

ENGINE = 'air.behavior-search/1'
OUTCOMES = ['TERMINAL_REACHED', 'INPUT_EXHAUSTED', 'NO_TRANSITION', 'TERMINAL_STATE']
STIMULUS = state_replay.REQUEST['properties']['stimuli']['items']
STATE_REQUEST = record({'baseline': SNAPSHOT, 'machine': SNAPSHOT,
    'initial_context': state_replay.CONTEXT,
    'alphabet': {'type': 'array', 'items': STIMULUS, 'minItems': 1, 'maxItems': 8, 'uniqueItems': True},
    'max_depth': {'type': 'integer', 'minimum': 1, 'maximum': 4},
    'max_trials': {'type': 'integer', 'minimum': 1, 'maximum': 64},
    'allowed_outcomes': {'type': 'array', 'items': {'enum': OUTCOMES}, 'minItems': 1, 'uniqueItems': True},
    'include_empty': {'type': 'boolean'}}, ['baseline', 'machine', 'initial_context', 'alphabet', 'max_depth', 'max_trials'])
INTERFACE_REQUEST = record({'baseline': SNAPSHOT, 'specification': SNAPSHOT,
    'operation': {**TEXT, 'maxLength': 128},
    'exchanges': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': record({
        'request': {}, 'response': {}, 'expected': {'enum': ['PASS', 'FAIL']},
        'scope': {'enum': ['REQUEST_ONLY', 'EXCHANGE']}}, ['request', 'expected'])}})


def _finish(request, trials, total, scope):
    examples = [t for t in trials if t['classification'] == 'COUNTEREXAMPLE']
    unknown = [t for t in trials if t['classification'] == 'INCONCLUSIVE']
    complete = len(trials) == total
    result = ('COUNTEREXAMPLE_FOUND' if examples else 'INCONCLUSIVE' if unknown or not complete
              else 'NO_COUNTEREXAMPLE_IN_DECLARED_DOMAIN')
    report = {'engine': ENGINE, 'scope': scope, 'baseline': request['baseline'],
        'request': request, 'request_digest': artifact_digest(request), 'result': result,
        'domain_size': total, 'trials_executed': len(trials), 'domain_exhausted': complete,
        'budget_exhausted': not complete, 'counterexamples': examples, 'inconclusive': unknown,
        'trials': trials, 'minimality': 'Shortest tested sequence in the declared breadth-first domain; not a globally minimal input',
        'limits': {'max_trials': 64, 'state_depth': 4, 'state_alphabet': 8, 'report_bytes': 1048576,
            'state_expression_steps_per_replay': state_replay.LIMITS['expression_steps']},
        'runtime_executed': False, 'authorization_granted': False, 'registry_written': False,
        'unverified': ['Inputs outside the declared finite domain', 'Real implementation and business effects',
            'Timing, concurrency and undeclared dependencies']}
    # Keep both witness and replay bounded before transport. No silent truncation.
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Behavior report exceeds 1 MiB; narrow the domain') from exc
    report['report_digest'] = artifact_digest(report)
    return report


def search_states(store, principal, policy, request):
    check_schema(request, STATE_REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('Behavior request exceeds its budget') from exc
    # Validate the full alphabet, including contexts that may fall outside the trial budget.
    validation = state_replay.replay(store, principal, policy, {'baseline': request['baseline'],
        'machine': request['machine'], 'initial_context': request['initial_context'], 'stimuli': request['alphabet']})
    del validation
    alphabet = request['alphabet']; depth = request['max_depth']; empty = request.get('include_empty', True)
    total = sum(len(alphabet) ** d for d in range(0 if empty else 1, depth + 1))
    allowed = request.get('allowed_outcomes', OUTCOMES)
    trials = []
    for length in range(0 if empty else 1, depth + 1):
        for sequence in product(range(len(alphabet)), repeat=length):
            if len(trials) >= request['max_trials']: return _finish(request, trials, total, 'DECLARED_STATE_SEQUENCES')
            replay_request = {'baseline': request['baseline'], 'machine': request['machine'],
                'initial_context': request['initial_context'], 'stimuli': [alphabet[i] for i in sequence]}
            report = state_replay.replay(store, principal, policy, replay_request)
            outcome = report['outcome']
            # A contradictory input is different from two known true guards.
            conflicting_input = any(v.get('state') == 'CONFLICTING' for values in
                [request['initial_context'], *(s['context'] for s in replay_request['stimuli'])] for v in values.values())
            uncertain = outcome in ('UNKNOWN', 'EVALUATION_ERROR', 'BUDGET_EXCEEDED') or (outcome == 'CONFLICTING' and conflicting_input)
            classification = 'INCONCLUSIVE' if uncertain else 'EXPECTED' if outcome in allowed else 'COUNTEREXAMPLE'
            trials.append({'index': len(trials), 'sequence': list(sequence), 'classification': classification,
                'replay_request': replay_request, 'report': report})
    return _finish(request, trials, total, 'DECLARED_STATE_SEQUENCES')


def search_interfaces(store, principal, policy, request):
    check_schema(request, INTERFACE_REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('Behavior request exceeds its budget') from exc
    _, spec, _ = interface_contracts._load(store, principal, policy, request)
    trials = []
    for exchange in request['exchanges']:
        if exchange.get('scope') == 'REQUEST_ONLY' and 'response' in exchange:
            raise InvalidModel('REQUEST_ONLY exchanges must not supply a response')
        report = interface_contracts.verify_exchange(spec['body'], request['operation'], exchange['request'],
            exchange.get('response', interface_contracts.MISSING))
        missing_response = 'response' not in exchange and exchange.get('scope', 'EXCHANGE') == 'EXCHANGE' and report['result'] == 'PASS'
        classification = ('INCONCLUSIVE' if report['result'] == 'INCONCLUSIVE' or missing_response else
            'EXPECTED' if exchange['expected'] == report['result'] else 'COUNTEREXAMPLE')
        trials.append({'index': len(trials), 'classification': classification, 'exchange': exchange, 'report': report,
            'missing_response': missing_response})
    result = _finish(request, trials, len(trials), 'DECLARED_INTERFACE_EXCHANGES')
    result['minimality'] = 'Declared exchanges only; no input minimization or implicit runtime call'
    result.pop('report_digest'); result['report_digest'] = artifact_digest(result)
    return result
