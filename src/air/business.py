"""Evaluate explicit goal targets on exact metric observations; no outcome claim."""
from copy import deepcopy
from datetime import datetime
from air.access import ScopedStore
from air.core import record, INSTANT, canonical
from air.expr import bounded, evaluate, ExprError, artifact_digest
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT
from air import runtime

ENGINE = 'air.business-targets/0.15'
ASSESS = record({'goal': SNAPSHOT, 'as_of': INSTANT, 'window': runtime.COMPARE['properties']['window'],
    'max_age_seconds': runtime.COMPARE['properties']['max_age_seconds'],
    'bindings': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': record({
        'target': {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'}, 'observation': SNAPSHOT})}})


def assess(store, principal, policy, request):
    check_schema(request, ASSESS)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel(str(exc)) from exc
    request = deepcopy(request);request['bindings'].sort(key=lambda b: b['target'])
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([request['goal']] + [b['observation'] for b in request['bindings']])
    start, end = (datetime.fromisoformat(request['window'][f]) for f in ('start', 'end'))
    as_of = datetime.fromisoformat(request['as_of'])
    if not start < end <= as_of: raise InvalidModel('Goal comparison window must be nonempty and end by as_of')
    comparisons, pins = [], []
    with store.engine.connect() as conn:
        goal = store._required(conn, request['goal'], 'air.Goal');body = goal['body']
        ids = [binding['target'] for binding in request['bindings']]
        if len(ids) != len(set(ids)) or set(ids) != {t['id'] for t in body['targets']}:
            raise InvalidModel('Every explicit goal target requires exactly one observation binding')
        if 'horizon' in body and not datetime.fromisoformat(body['horizon']['start']) <= start < end <= datetime.fromisoformat(body['horizon']['end']):
            raise InvalidModel('Requested window lies outside the declared goal horizon')
        by_target = {b['target']: b['observation'] for b in request['bindings']}
        budget = len(canonical(goal))
        for target in body['targets']:
            metric = store._required(conn, target['metric'], 'air.Metric')
            if metric['body']['unit'] != target['unit']: raise InvalidModel('Goal target unit differs from its exact metric')
            if 'window' in metric['body'] and (end - start).total_seconds() != int(metric['body']['window'][2:-1]):
                raise InvalidModel('Comparison window differs from the explicit metric sample window')
            observation = store._required(conn, by_target[target['id']], 'air.RuntimeObservation')
            if observation['body']['metric_or_signal'] != target['metric']:
                raise InvalidModel('Observation must pin the exact target metric; text names are not a binding')
            scope = store._required(conn, target['context'], 'air.Scope')
            budget += len(canonical(metric)) + len(canonical(observation)) + len(canonical(scope))
            if budget > 1024 * 1024: raise InvalidModel('Goal comparison context exceeds 1 MiB')
            from air.core import digest
            expression = {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
                'required_inputs': [{'name': 'signal', 'type': target['value']['type']}, {'name': 'threshold', 'type': target['value']['type']}],
                'ast': {'op': {'EQ': 'eq', 'LTE': 'lte', 'GTE': 'gte'}[target['operator']],
                    'args': [{'ref': 'signal'}, {'ref': 'threshold'}]}}
            comparison = {'scope': {**exact(scope), 'digest': digest(scope)}, 'expected': request['goal'],
                'as_of': request['as_of'], 'window': request['window'], 'max_age_seconds': request['max_age_seconds'],
                'bindings': [{'input': 'signal', 'observation': by_target[target['id']]}],
                'method': {'basis': 'DECLARED_MAPPING', 'rationale': 'Direct evaluation of structured Goal target ' + target['id'] + '; no interpretation of free text or population aggregation', 'expression': expression}}
            comparisons.append((target, comparison));pins.append({**exact(metric), 'digest': digest(metric)})
    reports, literals, aggregate_inputs = [], [], {}
    for (target, comparison), metric_pin in zip(comparisons, pins):
        result = runtime.compare_with_constants(store, principal, policy, comparison, {'threshold': target['value']})
        state = result['result']
        value = {'type': 'Boolean', 'value': state == 'SATISFIED'} if state in ('SATISFIED', 'VIOLATED') else {'type': 'Boolean', 'state': state}
        name = 'target_' + str(len(reports));aggregate_inputs[name] = value
        literals.append({'ref': name})
        reports.append({'target': target['id'], 'metric': metric_pin, 'operator': target['operator'], 'threshold': target['value'],
            'unit': target['unit'], 'result': state, 'comparison': result})
    while len(literals) > 1:
        literals = [{'op': 'and', 'args': literals[i:i+2]} if i + 1 < len(literals) else literals[i] for i in range(0, len(literals), 2)]
    ast = literals[0]
    aggregation = evaluate({'expression': {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'required_inputs': [{'name': name, 'type': 'Boolean'} for name in aggregate_inputs], 'ast': ast}, 'inputs': aggregate_inputs})
    failed = any(r['comparison']['execution'] == 'ERROR' for r in reports)
    report = {'engine': ENGINE, 'goal': request['goal'], 'execution': 'ERROR' if failed else aggregation['execution'],
        'result': 'UNKNOWN' if failed else aggregation['result'], 'result_scope': 'DECLARED_TARGETS_ON_BOUND_OBSERVATIONS',
        'targets': reports, 'aggregation': aggregation, 'coverage': 'PARTIAL', 'metric_population_qualification': 'DECLARED_NOT_VALIDATED',
        'goal_outcome_verified': False, 'business_verification_granted': False, 'external_action_executed': False,
        'request_digest': artifact_digest(request), 'limitations': ['Only structured targets are evaluated; goal outcome text is not compiled',
            'Metric aggregation, population and collection method remain declarations', 'Partial DRAFT observations do not establish enterprise-wide goal satisfaction']}
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Goal comparison report exceeds 1 MiB') from exc
    report['report_digest'] = artifact_digest(report)
    return report
