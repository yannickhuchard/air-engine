"""Pure policy diagnostics under exact baseline permissions; waivers confer no authority."""
from datetime import datetime
from air.access import ScopedStore
from air.core import INSTANT, TEXT, record, digest
from air.expr import Program, Budget, evaluate, typed, wire, artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict

ENGINE = 'air.policy-check/0.25'
VALUE = record({'type': TEXT, 'state': {'enum': ['KNOWN', 'UNKNOWN', 'CONFLICTING']}, 'value': {}}, ['type'])
INPUTS = {'type': 'object', 'maxProperties': 128, 'propertyNames': {'type': 'string', 'minLength': 1, 'maxLength': 256}, 'additionalProperties': VALUE}
REQUEST = record({'baseline': SNAPSHOT, 'policy': SNAPSHOT, 'as_of': INSTANT, 'applicability_inputs': INPUTS,
    'constraint_inputs': {'type': 'array', 'maxItems': 128, 'items': record({'constraint': SNAPSHOT, 'inputs': INPUTS})}})


def check_policy(store, principal, access_policy, request):
    check_schema(request, REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('Policy request exceeds its budget') from exc
    exported = snapshot(ScopedStore(store, principal, access_policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Policy context exceeds its budget') from exc
    index = {key(exact(o)): o for o in exported['objects']}
    policy = index.get(key(request['policy']))
    if not policy or policy['meta']['type'] != 'air.Policy': raise InvalidModel('Policy must be an exact member of the baseline')
    if digest(policy) != request['policy']['digest']: raise Conflict('Policy digest differs')
    constraints = {key(r): index[key(r)] for r in policy['body']['constraints']}
    as_of = datetime.fromisoformat(request['as_of']);budget = Budget(limit=50000)
    def pin(obj): return {**exact(obj), 'digest': digest(obj)}
    def validity(obj):
        period = obj['meta']['validity']
        if datetime.fromisoformat(period['start']) > as_of: return 'NOT_YET_VALID'
        if period['end'] and datetime.fromisoformat(period['end']) <= as_of: return 'EXPIRED'
        return 'WITHIN_DECLARED_VALIDITY'
    def normalize(condition, supplied):
        if isinstance(condition, str):
            if supplied: raise InvalidModel('Textual conditions have no executable input binding')
            return {}
        inputs = Program(condition).inputs
        if set(supplied) - inputs.keys(): raise InvalidModel('Undeclared policy input')
        result = {}
        for name, value in supplied.items():
            try: checked = typed(value)
            except ExprError as exc: raise InvalidModel('Invalid typed policy input') from exc
            if checked.type != inputs[name]: raise InvalidModel('Policy input type differs from declaration')
            result[name] = wire(checked)
        return result
    applicability_inputs = normalize(policy['body']['applicability'], request['applicability_inputs'])
    values = {}
    for supplied in request['constraint_inputs']:
        identity = key(supplied['constraint'])
        if identity not in constraints or identity in values: raise InvalidModel('Constraint input must target one distinct member of this policy')
        constraint = constraints[identity]
        if digest(constraint) != supplied['constraint']['digest']: raise Conflict('Constraint digest differs')
        values[identity] = normalize(constraint['body']['condition'], supplied['inputs'])
    def skipped(reason): return {'execution': 'NOT_EXECUTED', 'result': 'UNKNOWN', 'reason': reason, 'diagnostics': [], 'diagnostics_total': 0}
    def run(condition, inputs, temporal):
        if temporal != 'WITHIN_DECLARED_VALIDITY': return skipped(temporal)
        if isinstance(condition, str): return skipped('TEXT_REQUIRES_REVIEW')
        if budget.used >= budget.limit: return skipped('SHARED_BUDGET_EXHAUSTED')
        result = evaluate({'expression': condition, 'inputs': inputs}, budget=budget)
        return {'execution': result['execution'], 'result': result['result'],
            'diagnostics': [{k: str(v)[:256] for k, v in d.items()} for d in result['diagnostics'][:4]],
            'diagnostics_total': len(result['diagnostics']), 'cost': result['cost']}
    temporal = validity(policy)
    applicability = run(policy['body']['applicability'], applicability_inputs, temporal)
    applicable = applicability['execution'] == 'EXECUTED' and applicability['result'] == 'SATISFIED'
    not_applicable = applicability['execution'] == 'EXECUTED' and applicability['result'] == 'VIOLATED'
    checks = []
    for identity, constraint in sorted(constraints.items()):
        status = validity(constraint)
        evaluated = run(constraint['body']['condition'], values.get(identity, {}), status) if applicable else skipped('POLICY_NOT_APPLICABLE' if not_applicable else 'APPLICABILITY_UNRESOLVED')
        checks.append({'constraint': pin(constraint), 'mode': constraint['body']['mode'], 'scope': constraint['body']['scope'], 'validity': status,
            'input_digest': artifact_digest(values.get(identity, {})), 'evaluation': evaluated,
            'blocking': not not_applicable and constraint['body']['mode'] == 'hard' and (evaluated['execution'] != 'EXECUTED' or evaluated['result'] != 'SATISFIED')})
    related = set(constraints) | {key(exact(policy))};waivers = []
    for waiver in sorted(exported['objects'], key=lambda o: key(exact(o))):
        if waiver['meta']['type'] != 'air.Waiver' or key(waiver['body']['rule']) not in related: continue
        body = waiver['body'];approval = index[key(body['approval'])]
        waivers.append({'waiver': pin(waiver), 'rule': body['rule'], 'scope': body['scope'], 'validity': validity(waiver),
            'expires_at': body['expires_at'], 'expired': datetime.fromisoformat(body['expires_at']) <= as_of,
            'approval': pin(approval), 'approval_lifecycle': approval['meta']['lifecycle'], 'compensating_controls': body['compensating_controls'],
            'effectiveness': 'NOT_VERIFIED', 'applied': False})
    results = [c['evaluation'] for c in checks]
    if not_applicable: outcome = 'NOT_APPLICABLE'
    elif not applicable: outcome = 'CONFLICTING' if applicability['result'] == 'CONFLICTING' else 'UNKNOWN'
    elif any(r['result'] == 'CONFLICTING' for r in results): outcome = 'CONFLICTING'
    elif any(r['result'] == 'VIOLATED' for r in results): outcome = 'VIOLATED'
    elif any(r['execution'] != 'EXECUTED' or r['result'] == 'UNKNOWN' for r in results): outcome = 'UNKNOWN'
    else: outcome = 'SATISFIED'
    report = {'engine': ENGINE, 'regime': 'DIAGNOSTIC', 'input_qualification': 'DECLARED_INPUTS', 'baseline': request['baseline'], 'policy': request['policy'],
        'as_of': request['as_of'], 'policy_validity': temporal, 'applicability': applicability, 'constraints': checks, 'waivers': waivers, 'outcome': outcome,
        'blocking_constraints': sum(c['blocking'] for c in checks), 'all_constraints_satisfied': applicable and all(r['execution'] == 'EXECUTED' and r['result'] == 'SATISFIED' for r in results),
        'authorization_granted': False, 'waiver_applied': False, 'business_verification_granted': False, 'model_updated': False,
        'cost': {'steps': budget.used, 'limit': budget.limit}, 'request_digest': artifact_digest(request)}
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Policy report exceeds its budget') from exc
    return report
