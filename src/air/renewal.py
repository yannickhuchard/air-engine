"""Renew local admission authority without changing its reserved work."""
from copy import deepcopy
from sqlalchemy import select, update
from air import admission, planning
from air.access import ScopedStore
from air.authority import KEY, authorize
from air.core import record
from air.expr import bounded
from air.foundation import InvalidModel, check_schema
from air.packages import RECORD_REF, reference, required
from air.reviews import record_key
from air.storage import Conflict, authorization_heads, reservations

PROPOSE = record({'idempotency_key': KEY, 'admission': RECORD_REF,
    'expected_authorization': {'anyOf': [RECORD_REF, {'type': 'null'}]},
    'offers': admission.PROPOSE['properties']['offers']})
RENEW = admission.ADMIT


def current(store, conn, original):
    head = conn.execute(select(authorization_heads).where(authorization_heads.c.admission_id == original['id'])).mappings().first()
    if head is None: return original, 0
    row = store._get_record(conn, head['receipt_id'])
    if row is None or row['kind'] != 'admission_renewal': raise InvalidModel('Admission authorization head is invalid')
    return row, head['generation']


def check_held(store, conn, original):
    if original['payload']['outcome']['status'] != 'ADMITTED': raise InvalidModel('Only admitted work can be renewed')
    expected = {r['id']: r for r in admission.reservation_rows(original['id'], original['payload']['selected'])}
    actual = {r['id']: dict(r) for r in conn.execute(select(reservations).where(reservations.c.admission_id == original['id'])).mappings()}
    if not expected or actual != expected: raise Conflict('Admission reservations are not fully held')


def propose(store, principal, policy, settings, request):
    check_schema(request, PROPOSE);bounded(request)
    request = deepcopy(request);request['offers'].sort(key=lambda p: p['id'])
    record_id = record_key('renewal-proposal', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'write', [])
        original, _ = admission.admission_row(store, conn, principal, policy, request['admission'])
        check_held(store, conn, original)
        head, generation = current(store, conn, original)
        expected = reference(head) if generation else None
        prior = store._get_record(conn, record_id)
        if prior:
            if prior['payload'].get('renewal_request') != request: raise Conflict('Renewal idempotency key was reused')
            admission.proposal_row(store, conn, principal, policy, reference(prior))
            return {'proposal': reference(prior), 'created': False, 'report': prior['payload']['report']}
        if request['expected_authorization'] != expected: raise Conflict('Admission authorization has changed')
        selected = deepcopy(original['payload']['selected'])
        selected.update(idempotency_key=request['idempotency_key'], offers=request['offers'], strategy='AS_PROPOSED')
        original_pools = {d['pool']['id'] for d in selected['demands']}
        new_pools = {required(store, conn, pin, 'capacity_offer')['payload']['request']['scope']['id'] for pin in request['offers']}
        if original_pools != new_pools: raise InvalidModel('Renewal must cover exactly the originally reserved pools')
        args, scopes = admission.build_plan(store, conn, principal, policy, settings, stamp, selected, exclude_admission=original['id'])
        for scope in scopes: policy.require(principal, 'write', scope)
        report = planning.plan(ScopedStore(store, principal, policy), args)
        payload = {'request': selected, 'selected': selected, 'report': report, 'scopes': scopes, 'policy': stamp,
            'capacity_provenance': 'AUTHORITY_REGISTRY_OFFERS', 'design_acceptance': 'NOT_EXECUTED',
            'renewal_of': request['admission'], 'renewal_request': request, 'expected_generation': generation}
        bounded(payload)
        result = store._record_once(conn, record_id, 'admission_proposal', original['scope'], principal['subject'], payload)
    return {'proposal': reference(result['record']), 'created': result['created'], 'report': report}


def renew(store, principal, policy, settings, request):
    check_schema(request, RENEW);request = deepcopy(request);request['approvals'].sort(key=lambda p: p['id'])
    record_id = record_key('admission-renewal', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'admit', [])
        proposal = admission.proposal_row(store, conn, principal, policy, request['proposal']); payload = proposal['payload']
        if 'renewal_of' not in payload: raise InvalidModel('Renewal requires a dedicated proposal')
        original, _ = admission.admission_row(store, conn, principal, policy, payload['renewal_of'])
        for scope in payload['scopes']: policy.require(principal, 'admit', scope)
        prior = admission.replay(store, conn, record_id, request)
        if prior: return admission.response(prior, False)
        check_held(store, conn, original)
        previous, generation = current(store, conn, original)
        if generation != payload['expected_generation']: raise Conflict('Admission authorization has changed')
        if payload['policy'] != stamp: raise Conflict('Renewal proposal authority has changed')
        admission.check_approvals(store, conn, policy, stamp, proposal, request['approvals'])
        args, _ = admission.build_plan(store, conn, principal, policy, settings, stamp, payload['selected'], exclude_admission=original['id'])
        report = planning.plan(ScopedStore(store, principal, policy), args)
        if payload['report']['result'] != 'SATISFIED' or report['result'] != 'SATISFIED':
            raise Conflict('Renewal conditions are not satisfied; existing work remains protected')
        receipt = {'request': request, 'admission': reference(original), 'previous_authorization': reference(previous),
            'generation': generation + 1, 'policy': stamp, 'selected': payload['selected'], 'report': report,
            'outcome': {'status': 'REAUTHORIZED', 'generation': generation + 1, 'reservations_created': False, 'business_execution_authorized': False}}
        bounded(receipt)
        result = store._record_once(conn, record_id, 'admission_renewal', original['scope'], principal['subject'], receipt)
        if generation:
            conn.execute(update(authorization_heads).where(authorization_heads.c.admission_id == original['id']).values(generation=generation + 1, receipt_id=record_id))
        else:
            conn.execute(authorization_heads.insert().values(admission_id=original['id'], generation=1, receipt_id=record_id))
    return admission.response(result['record'], result['created'])


def verify_projection(store, conn):
    for head in conn.execute(select(authorization_heads)).mappings():
        row = store._get_record(conn, head['receipt_id'])
        generation = head['generation'];seen = set()
        while generation:
            if row is None or row['id'] in seen or row['kind'] != 'admission_renewal': raise InvalidModel('Invalid authorization renewal chain')
            seen.add(row['id']);payload = row['payload']
            if payload['generation'] != generation or payload['admission']['id'] != head['admission_id']: raise InvalidModel('Renewal projection disagrees with its receipt')
            original = required(store, conn, payload['admission'], 'admission_receipt')
            before = {k: v for k, v in original['payload']['selected'].items() if k not in ('offers', 'idempotency_key')}
            after = {k: v for k, v in payload['selected'].items() if k not in ('offers', 'idempotency_key')}
            if before != after: raise InvalidModel('Renewal changed the originally reserved work')
            previous = payload['previous_authorization']
            row = required(store, conn, previous, 'admission_renewal' if generation > 1 else 'admission_receipt')
            generation -= 1
        if row['id'] != head['admission_id']: raise InvalidModel('Renewal chain does not start at its admission')
