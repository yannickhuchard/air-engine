"""Scoped delivery gates, exact trace chains and declared work dashboards."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from air.access import ScopedStore
from air.core import record, REF, TEXT, digest, reference_slots
from air.expr import artifact_digest
from air.foundation import check_schema, exact, key, InvalidModel, TooLarge, check_budget
from air.projections import SNAPSHOT, snapshot
from air.delivery_assurance_schema import LAYERS

ENGINE = 'air.delivery-assurance/1'
BASE = {'baseline': SNAPSHOT}
GATES = record({**BASE, 'gates': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True}}, ['baseline'])
COVERAGE = record({**BASE, 'gate': SNAPSHOT}, ['baseline'])
DAY = {'type': 'string', 'format': 'date'}
DASHBOARD = record({'baselines': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
    'as_of': DAY, 'team': TEXT, 'member': TEXT,
    'week': {'type': 'string', 'pattern': '^20[0-9]{2}-W[0-9]{2}$'},
    'late': {'type': 'boolean'}, 'blocked': {'type': 'boolean'},
    'offset': {'type': 'integer', 'minimum': 0, 'maximum': 10000},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000}}, ['baselines', 'as_of'])


def pin(o): return {**exact(o), 'digest': digest(o)}
def index(exported): return {key(o['meta']): o for o in exported['objects']}


def selected(exported, selector):
    o = index(exported).get(key(selector))
    if not o or o['meta']['type'] != 'air.ScopeGate' or pin(o) != selector:
        raise InvalidModel('Select an exact ScopeGate member of this baseline')
    return o


def gate_closure(exported, gate):
    """Review authorship includes every transitive model input, excluding other gates."""
    by = index(exported); todo = [exact(gate)]; seen = set(); result = []
    while todo:
        r = todo.pop(); k = key(r)
        if k in seen: continue
        seen.add(k); o = by.get(k)
        if o is None: raise InvalidModel('Scope gate dependency is absent from its baseline')
        if o['meta']['type'] == 'air.ScopeGate' and k != key(gate['meta']): continue
        result.append(o)
        todo.extend(r for field, r, _ in reference_slots(o) if not
            (o['meta']['type'] == 'air.ScopeGate' and (field == 'body/depends_on' or field.startswith('body/depends_on/'))))
        if len(seen) > 10000: raise TooLarge('Gate review closure exceeds 10000 objects')
    return result


def coverage_project(exported, gate=None):
    all_objects = index(exported)
    allowed = {key(r) for r in gate['body']['members']} if gate else set(all_objects)
    by = {k: o for k, o in all_objects.items() if k in allowed}
    requirements = [all_objects[key(r)] for r in gate['body']['requirements']] if gate else [o for o in by.values() if o['meta']['type'] in LAYERS[0]]
    edges = defaultdict(list)
    for o in by.values():
        if o['meta']['type'] != 'air.TraceabilityLink': continue
        b = o['body']; source, target = all_objects.get(key(b['source'])), all_objects.get(key(b['target']))
        if not source or not target or not any(source['meta']['type'] in a and target['meta']['type'] in z for a, z in zip(LAYERS, LAYERS[1:])):
            raise InvalidModel('Traceability link has invalid adjacent layers')
        if key(b['source']) in by and key(b['target']) in by: edges[key(b['source'])].append(o)
    rows = []; explored = 0
    for root in sorted(requirements, key=lambda o: key(o['meta'])):
        paths = []; gaps = []; todo = [(root, 0, [pin(root)], [])]
        design_complete = True
        while todo:
            o, layer, chain, witnesses = todo.pop(); explored += 1
            if explored > 20000: raise TooLarge('Traceability exceeds 20000 path steps; select a smaller gate')
            if layer == 5:
                if key(o['body']['case']) != key(chain[4]):
                    gaps.append({'at': pin(o), 'missing_layer': 'EVIDENCE', 'reason': 'EVIDENCE_CASE_MISMATCH'}); continue
                paths.append({'objects': chain, 'links': witnesses, 'declared_result': o['body'].get('result'),
                    'proof_level': o['body'].get('proof_level', 'RECORDED_OPERATIONAL_RESULT')}); continue
            outgoing = sorted(edges[key(o['meta'])], key=lambda x: key(x['meta']))
            if not outgoing:
                gaps.append({'at': pin(o), 'missing_layer': ['REQUIREMENT', 'RULE', 'DATA', 'API', 'TEST', 'EVIDENCE'][layer + 1], 'reason': 'NO_EXPLICIT_LINK'})
                if layer < 4: design_complete = False
            for link in outgoing:
                target = by[key(link['body']['target'])]
                todo.append((target, layer + 1, chain + [pin(target)], witnesses + [pin(link)]))
        rows.append({'requirement': pin(root), 'name': root['meta']['name'], 'paths': paths, 'gaps': gaps,
            'design_chain_complete': design_complete, 'status': 'COVERED' if paths and not gaps else 'GAPS'})
    result = {'engine': ENGINE, 'baseline': {**exact(exported['baseline']), 'digest': exported['digest']},
        'gate': pin(gate) if gate else None, 'layers': ['REQUIREMENT', 'RULE', 'DATA', 'API', 'TEST', 'EVIDENCE'],
        'requirements': rows, 'totals': {'requirements': len(rows), 'covered': sum(r['status'] == 'COVERED' for r in rows),
            'paths': sum(len(r['paths']) for r in rows)},
        'coverage_basis': 'EXPLICIT_ADJACENT_TYPED_LINKS_AT_EXACT_PINS',
        'semantic_correctness_verified': False, 'runtime_executed': False, 'ready_to_build': False}
    check_budget(result)
    return {**result, 'report_digest': artifact_digest(result)}


def coverage(store, principal, policy, request):
    check_schema(request, COVERAGE)
    e = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    return coverage_project(e, selected(e, request['gate']) if request.get('gate') else None)


def evidence_state(store, principal, policy, obj):
    """Read retained bytes through the existing authorization boundary, never fetch a URL."""
    report = obj['body'].get('report')
    if not report: return 'REPORT_MISSING'
    from air import artifacts
    from air.packages import reference
    record = store.get_record(report['locator'])
    if not record or record['kind'] != 'artifact_manifest': return 'REPORT_UNAVAILABLE'
    try:
        descriptor, data = artifacts.download(store, principal, policy, {'artifact': reference(record)})
    except (InvalidModel, KeyError): return 'REPORT_UNAVAILABLE'
    expected = 'sha256:' + report['digest']['value']
    import hashlib
    if len(data) != report['size'] or 'sha256:' + hashlib.sha256(data).hexdigest() != expected:
        return 'REPORT_DIGEST_MISMATCH'
    if record['scope'] != obj['meta']['namespace']: return 'REPORT_NAMESPACE_MISMATCH'
    if record['payload']['request']['media_type'] != report['media_type']: return 'REPORT_MEDIA_MISMATCH'
    if obj['body'].get('method') not in (None, 'TEST'): return 'NOT_AN_EXECUTED_TEST'
    if obj['body'].get('proof_level') not in (None, 'EXECUTED_TEST'): return 'NOT_AN_EXECUTED_TEST'
    if datetime.fromisoformat(obj['body']['executed_at']) > datetime.now(timezone.utc): return 'FUTURE_EXECUTION'
    if obj['body']['result'] != 'PASS': return obj['body']['result']
    if any(m['observed_seconds'] > m['target_seconds'] for m in obj['body'].get('metrics', [])): return 'TARGET_EXCEEDED'
    return 'PASS_RECORDED_NOT_INDEPENDENTLY_QUALIFIED'


def assess_gates(store, principal, policy, request):
    check_schema(request, GATES)
    e = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    return assess_exported(store, principal, policy, e, request)


def assess_exported(store, principal, policy, e, request):
    """Internal candidate assessment; callers authorize the complete exported closure first."""
    by = index(e)
    gates = [selected(e, p) for p in request['gates']] if request.get('gates') else [o for o in by.values() if o['meta']['type'] == 'air.ScopeGate']
    from air.reviews import read_review
    results = {}; visiting = set()
    def visit(g):
        k = key(g['meta'])
        if k in results: return results[k]
        if k in visiting: raise InvalidModel('Scope gate prerequisite cycle')
        if len(visiting) >= 64: raise TooLarge('Scope gate prerequisite depth exceeds 64')
        visiting.add(k); b = g['body']; blockers = []; deps = []
        for r in b['depends_on']:
            d = by.get(key(r))
            if not d or d['meta']['type'] != 'air.ScopeGate': raise InvalidModel('Unresolved ScopeGate prerequisite')
            state = visit(d); deps.append({'gate': pin(d), 'result': state['result']})
            if state['result'] != 'PASS_SCOPED_GATE': blockers.append({'code': 'PREREQUISITE_NOT_MET', 'reference': pin(d)})
        coverage = coverage_project(e, g)
        if not coverage['requirements'] or not all(r['design_chain_complete'] for r in coverage['requirements']): blockers.append({'code': 'DESIGN_TRACE_GAPS'})
        evidence = []
        if b['verification_policy'] == 'RECORDED_TESTS':
            if any(r['status'] != 'COVERED' for r in coverage['requirements']): blockers.append({'code': 'EVIDENCE_TRACE_GAPS'})
            for p in [p for r in coverage['requirements'] for p in r['paths']]:
                obj = by[key(p['objects'][-1])]; state = evidence_state(store, principal, policy, obj)
                evidence.append({'reference': pin(obj), 'status': state})
                if state != 'PASS_RECORDED_NOT_INDEPENDENTLY_QUALIFIED': blockers.append({'code': 'EVIDENCE_NOT_PASS', 'reference': pin(obj), 'status': state})
        accepted = []; rejected = []
        for receipt in store.reviews_of(g['meta']['id'], g['meta']['namespace']):
            r = store.get_record(receipt['receipt'])
            q = r['payload']['request']
            if q['baseline'] != request['baseline'] or q['target'] != pin(g): continue
            review = read_review(store, principal, policy, r['id'])
            if review['effective']:
                (accepted if review['outcome'] == 'ACCEPTED' else rejected).append({'id': r['id'], 'digest': r['request_digest']})
        if rejected: blockers.append({'code': 'INDEPENDENT_REJECTION', 'reviews': rejected})
        if b['review_required'] and not accepted: blockers.append({'code': 'SCOPE_REVIEW_REQUIRED'})
        result = {'gate': pin(g), 'name': g['meta']['name'], 'scope': b['scope'],
            'review_required': b['review_required'],
            'verification_policy': b['verification_policy'], 'dependencies': deps, 'coverage': coverage,
            'evidence': evidence, 'accepted_reviews': accepted, 'blockers': blockers,
            'result': 'BLOCKED' if blockers else 'PASS_SCOPED_GATE'}
        results[k] = result; visiting.remove(k); return result
    for gate in sorted(gates, key=lambda o: key(o['meta'])): visit(gate)
    report = {'engine': ENGINE, 'baseline': request['baseline'], 'gates': [results[k] for k in sorted(results)],
        'scope': 'EXPLICIT_GATE_CRITERIA_ONLY', 'global_readiness_overridden': False,
        'runtime_executed': False, 'launch_authorized': False}
    check_budget(report)
    return {**report, 'report_digest': artifact_digest(report)}


def dashboard_project(exports, request):
    as_of = date.fromisoformat(request['as_of']); interval = None
    if request.get('week'):
        year, week = request['week'].split('-W')
        try: interval = (date.fromisocalendar(int(year), int(week), 1), date.fromisocalendar(int(year), int(week), 7))
        except ValueError as exc: raise InvalidModel('Week must exist in the ISO calendar') from exc
    by = {}; pins = []
    for e in exports:
        pins.append({**exact(e['baseline']), 'digest': e['digest']})
        for o in e['objects']:
            k = key(o['meta'])
            if k in by and digest(o) != digest(by[k]): raise InvalidModel('Conflicting object at identical pin')
            by[k] = o
            if len(by) > 10000: raise TooLarge('Dashboard supports at most 10000 model objects')
    rows = []
    for k, o in sorted(by.items()):
        if o['meta']['type'] != 'air.ArchitectureTask': continue
        b = o['body']; active = b['status'] not in ('DONE', 'CANCELLED')
        due = date.fromisoformat(b['due']) if b.get('due') else None
        start = date.fromisoformat(b['start']) if b.get('start') else due
        late = bool(active and due and due < as_of)
        unresolved = [r for r in b['depends_on'] if not by.get(key(r)) or by[key(r)]['body'].get('status') != 'DONE'] if active else []
        blocked = bool(active and (b['status'] == 'BLOCKED' or b.get('blockers') or b.get('blocker_reason') or unresolved))
        members = sorted(set([b['owner'], *[r['id'] for r in b.get('members', [])]]))
        row = {'task': pin(o), 'name': o['meta']['name'], 'project': b['project'], 'team': b.get('team'),
            'members': members, 'status': b['status'], 'start': b.get('start'), 'due': b.get('due'),
            'late': late, 'days_late': (as_of - due).days if late else 0, 'blocked': blocked,
            'blockers': b.get('blockers', []), 'blocker_reason': b.get('blocker_reason'), 'unresolved_prerequisites': unresolved}
        if request.get('team') and row['team'] != request['team']: continue
        if request.get('member') and request['member'] not in members: continue
        if 'late' in request and late != request['late'] or 'blocked' in request and blocked != request['blocked']: continue
        if interval and (not start or not due or start > interval[1] or due < interval[0]): continue
        rows.append(row)
    totals = dict(Counter(r['status'] for r in rows)); total = len(rows); done = totals.get('DONE', 0); cancelled = totals.get('CANCELLED', 0)
    offset = request.get('offset', 0); page = rows[offset:offset + request.get('limit', 1000)]
    result = {'engine': ENGINE, 'baselines': sorted(pins, key=key), 'as_of': request['as_of'], 'filters': {k: v for k, v in request.items() if k not in ('baselines', 'offset', 'limit')},
        'tasks': page, 'total_matching': total, 'next_offset': offset + len(page) if offset + len(page) < total else None,
        'totals': {'statuses': totals, 'late': sum(r['late'] for r in rows), 'blocked': sum(r['blocked'] for r in rows),
            'done': done, 'cancelled': cancelled, 'completion_percent': round(100 * done / (total - cancelled)) if total > cancelled else None},
        'totals_scope': 'FILTERED_TASKS_BEFORE_PAGINATION', 'basis': 'DECLARED_DESIGN_WORK_NOT_IMPLEMENTATION_PROGRESS'}
    check_budget(result)
    return {**result, 'report_digest': artifact_digest(result)}


def dashboard(store, principal, policy, request):
    check_schema(request, DASHBOARD)
    return dashboard_project([snapshot(ScopedStore(store, principal, policy), p) for p in request['baselines']], request)
