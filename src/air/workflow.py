"""Bounded structural inspection: reachability is potential, conditions are not evaluated."""
from collections import deque
from air.access import ScopedStore
from air.core import record, digest
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot

REQUEST = record({'baseline': SNAPSHOT})
ENGINE = 'air.workflow-dossier/0.22'


def structure(body):
    nodes = {s['id'] for s in body['steps']};edges = {n: set() for n in nodes}
    for flow in body['flows']: edges[flow['source']].add(flow['target'])
    reachable = set();pending = list(body['start_steps'])
    while pending:
        node = pending.pop()
        if node in reachable: continue
        reachable.add(node);pending.extend(edges[node] - reachable)
    incoming = {n: 0 for n in nodes}
    for targets in edges.values():
        for target in targets: incoming[target] += 1
    queue = deque(n for n, count in incoming.items() if count == 0);visited = 0
    while queue:
        node = queue.popleft();visited += 1
        for target in edges[node]:
            incoming[target] -= 1
            if incoming[target] == 0: queue.append(target)
    return {'reachable_steps_ignoring_conditions': sorted(reachable), 'unreachable_steps': sorted(nodes - reachable),
            'terminal_steps': sorted(n for n in nodes if not edges[n]), 'cycle_detected': visited != len(nodes),
            'conditions_evaluated': False, 'termination_verified': False}


def inspect_workflow(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Workflow context exceeds its budget') from exc
    groups = {'air.Workflow': 'workflows', 'air.OperatingModel': 'operating_models', 'air.BusinessRule': 'business_rules'}
    report = {'engine': ENGINE, 'baseline': request['baseline'], **{v: [] for v in groups.values()},
        'functions_executed': False, 'compensations_executed': False, 'rules_evaluated': False,
        'business_verification_granted': False, 'authorization_granted': False, 'model_updated': False,
        'request_digest': artifact_digest(request)}
    for obj in sorted(exported['objects'], key=lambda o: key(exact(o))):
        group = groups.get(obj['meta']['type'])
        if not group: continue
        row = {'reference': {**exact(obj), 'digest': digest(obj)}, 'name': obj['meta']['name'],
               'validity': obj['meta']['validity'], 'lifecycle': obj['meta']['lifecycle'], 'declared': obj['body']}
        if group == 'workflows': row['structure'] = structure(obj['body'])
        if group == 'business_rules': row['verification_execution'] = 'NOT_EXECUTED'
        report[group].append(row)
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Workflow report exceeds its budget') from exc
    return report
