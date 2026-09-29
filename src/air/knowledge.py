"""Read a declared knowledge dossier without promoting, executing or resolving it."""
from datetime import datetime
from air.access import ScopedStore
from air.core import INSTANT, record, digest
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot

REQUEST = record({'baseline': SNAPSHOT, 'as_of': INSTANT})
ENGINE = 'air.knowledge-dossier/0.17'


def inspect_knowledge(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Knowledge context exceeds its budget') from exc
    objects = sorted(exported['objects'], key=lambda o: key(exact(o)))
    index = {key(exact(o)): o for o in objects}
    as_of = datetime.fromisoformat(request['as_of'])
    def pin(obj): return {**exact(obj), 'digest': digest(obj)}
    def temporal(obj):
        period = obj['meta']['validity']
        if datetime.fromisoformat(period['start']) > as_of: return 'NOT_YET_VALID'
        if period['end'] and datetime.fromisoformat(period['end']) <= as_of: return 'EXPIRED'
        return 'WITHIN_DECLARED_VALIDITY'
    assertions, inferences, conflicts = [], [], []
    for obj in objects:
        if obj['meta']['type'] != 'air.Assertion': continue
        body = obj['body'];evidence = []
        for ref in body['evidence']:
            proof = index[key(ref)];source = index[key(proof['body']['source'])]
            direction = next(link['direction'] for link in proof['body']['supports_or_refutes'] if key(link) == key(exact(obj)))
            evidence.append({'reference': pin(proof), 'direction': direction,
                'kind': proof['body']['evidence_kind'], 'selector': proof['body']['selector'],
                'limitations': proof['body']['limitations'], 'source': pin(source),
                'source_captured_at': source['body']['captured_at'],
                'source_capture_after_as_of': datetime.fromisoformat(source['body']['captured_at']) > as_of,
                'validity': temporal(proof)})
        assertions.append({'reference': pin(obj), 'name': obj['meta']['name'], 'statement': body['statement'],
            'scope': body['subject_scope'], 'declared_status': body['epistemic_status'], 'validity': temporal(obj),
            'review_overdue': 'review_due' in body and datetime.fromisoformat(body['review_due']) <= as_of,
            'evidence': evidence, 'truth_verified': False})
    states = {key(a['reference']): a for a in assertions}
    for obj in objects:
        body = obj['body']
        if obj['meta']['type'] == 'air.Inference':
            premises = []
            for ref in body['premises']:
                state = states[key(ref)];risks = []
                if state['declared_status'] != 'ESTABLISHED': risks.append('PREMISE_NOT_ESTABLISHED')
                if state['declared_status'] in ('CONTESTED', 'REFUTED', 'EXPIRED'): risks.append('PREMISE_' + state['declared_status'])
                if state['validity'] != 'WITHIN_DECLARED_VALIDITY': risks.append(state['validity'])
                if state['review_overdue']: risks.append('REVIEW_OVERDUE')
                if any(e['source_capture_after_as_of'] for e in state['evidence']): risks.append('SOURCE_CAPTURE_AFTER_AS_OF')
                premises.append({'reference': state['reference'], 'declared_status': state['declared_status'], 'risks': risks})
            inferences.append({'reference': pin(obj), 'conclusion': body['conclusion'], 'premises': premises,
                'derivation': body['derivation'], 'limitations': body['limitations'], 'validity': temporal(obj),
                'derivation_execution': 'NOT_EXECUTED', 'execution_reason': 'No data binding from textual assertions to expression inputs',
                'conclusion_promoted': False})
        elif obj['meta']['type'] == 'air.Conflict':
            decision = index[key(body['resolution'])] if 'resolution' in body else None
            conflicts.append({'reference': pin(obj), 'statements': body['statements'], 'scope': body['overlap_scope'],
                'reason': body['reason'], 'validity': temporal(obj), 'qualification': 'DECLARED_NOT_SEMANTICALLY_VERIFIED',
                'resolution_state': 'DECISION_RECORDED_UNVERIFIED' if decision else 'OPEN_DECLARATION',
                'resolution': {'reference': pin(decision), 'selection': decision['body']['selection'], 'rationale': decision['body']['rationale']} if decision else None,
                'statements_preserved': True, 'new_state_verified': False})
    report = {'engine': ENGINE, 'baseline': request['baseline'], 'as_of': request['as_of'],
        'time_semantics': 'DECLARED_VALIDITY_AT_AS_OF_NOT_HISTORICAL_REGISTRY_KNOWLEDGE',
        'assertions': assertions, 'inferences': inferences, 'conflicts': conflicts,
        'truth_promotion_performed': False, 'automatic_resolution': False, 'model_updated': False,
        'business_verification_granted': False, 'external_action_executed': False,
        'limitations': ['Declarations and exact links do not establish the truth of natural-language assertions',
            'Evidence artifacts are not downloaded or independently validated',
            'A resolution decision does not verify a changed external state'],
        'request_digest': artifact_digest(request)}
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Knowledge report exceeds its budget') from exc
    return report
