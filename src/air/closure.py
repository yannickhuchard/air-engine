"""Reviewed reports of local episode completion; no claim of external execution."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from air import admission
from air.access import ScopedStore, Forbidden
from air.authority import KEY, authorize
from air.core import TEXT, record
from air.foundation import InvalidModel, check_schema
from air.packages import RECORD_REF, reference, required, identifier
from air.projections import SNAPSHOT
from air.reviews import record_key
from air.storage import Conflict

PROPOSE = record({'idempotency_key': KEY, 'activation': RECORD_REF,
    'outcome': {'enum': ['COMPLETED', 'ABORTED']}, 'evidence': SNAPSHOT, 'rationale': TEXT})
REVIEW = admission.REVIEW
CLOSE = admission.ADMIT


def context(store, conn, principal, policy, activation):
    row = required(store, conn, activation, 'activation_receipt')
    original, proposal = admission.admission_row(store, conn, principal, policy, row['payload']['request']['admission'])
    return row, original, proposal['payload']['scopes']


def closure_proposal(store, conn, principal, policy, pin):
    row = required(store, conn, pin, 'episode_closure_proposal')
    context(store, conn, principal, policy, row['payload']['request']['activation'])
    ScopedStore(store, principal, policy).check_read([row['payload']['request']['evidence']])
    return row


def propose(store, principal, policy, settings, request):
    check_schema(request, PROPOSE);request = deepcopy(request)
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'activate', [])
        episode, original, scopes = context(store, conn, principal, policy, request['activation'])
        for scope in scopes: policy.require(principal, 'activate', scope)
        ScopedStore(store, principal, policy).check_read([request['evidence']])
        evidence = store._required(conn, request['evidence'], 'air.Evidence')
        if evidence['meta']['namespace'] not in scopes: raise InvalidModel('Closure evidence must belong to the episode scope')
        record_id = record_key('closure-proposal', principal['subject'], request['idempotency_key'])
        prior = admission.replay(store, conn, record_id, request)
        if prior: return {'proposal': reference(prior), 'created': False}
        if store._get_record(conn, identifier('episode-closed', episode['id'])): raise Conflict('Episode is already closed')
        payload = {'request': request, 'policy': stamp, 'scopes': scopes, 'evidence_class': 'DECLARED_COMPLETION', 'business_verification': 'NOT_EXECUTED'}
        result = store._record_once(conn, record_id, 'episode_closure_proposal', original['scope'], principal['subject'], payload)
    return {'proposal': reference(result['record']), 'created': result['created']}


def review(store, principal, policy, settings, request):
    check_schema(request, REVIEW)
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'review', [])
        proposal = closure_proposal(store, conn, principal, policy, request['proposal'])
        for scope in proposal['payload']['scopes']: policy.require(principal, 'review', scope)
        if proposal['actor'] == principal['subject']: raise Forbidden('Closure requires independent review')
        record_id = record_key('closure-review', principal['subject'], request['idempotency_key'])
        prior = admission.replay(store, conn, record_id, request)
        if prior: return {'review': reference(prior), 'created': False}
        if proposal['payload']['policy'] != stamp: raise Conflict('Closure proposal authority has changed')
        current = datetime.now(timezone.utc)
        if not current < datetime.fromisoformat(request['expires_at']) <= current + timedelta(days=7): raise InvalidModel('Closure review expires within seven days')
        result = store._record_once(conn, record_id, 'episode_closure_review', proposal['scope'], principal['subject'],
            {'request': deepcopy(request), 'policy': stamp, 'reviewer_role': principal['role']})
    return {'review': reference(result['record']), 'created': result['created']}


def close(store, principal, policy, settings, request):
    check_schema(request, CLOSE);request = deepcopy(request);request['approvals'].sort(key=lambda p: p['id'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'admit', [])
        proposal = closure_proposal(store, conn, principal, policy, request['proposal']); payload = proposal['payload']
        for scope in payload['scopes']: policy.require(principal, 'admit', scope)
        record_id = record_key('episode-closure', principal['subject'], request['idempotency_key'])
        prior = admission.replay(store, conn, record_id, request)
        if prior: return admission.response(prior, False)
        if payload['policy'] != stamp: raise Conflict('Closure proposal authority has changed')
        for pin in request['approvals']:
            row = required(store, conn, pin, 'episode_closure_review'); review = row['payload']
            if review['request']['proposal'] != reference(proposal) or review['request']['decision'] != 'ACCEPT' or row['actor'] == proposal['actor']:
                raise InvalidModel('Closure approval does not independently accept this proposal')
            if review['policy'] != stamp or datetime.fromisoformat(review['request']['expires_at']) <= datetime.now(timezone.utc): raise Conflict('Closure approval expired or changed')
            if store._get_record(conn, identifier('closure-review-revoked', row['id'])): raise Conflict('Closure approval was revoked')
            for scope in payload['scopes']: policy.require({'subject': row['actor'], 'role': review['reviewer_role']}, 'review', scope)
        marker_id = identifier('episode-closed', payload['request']['activation']['id'])
        if store._get_record(conn, marker_id): raise Conflict('Episode is already closed')
        result = store._record_once(conn, record_id, 'episode_closure', proposal['scope'], principal['subject'],
            {'request': request, 'policy': stamp, 'activation': payload['request']['activation'], 'evidence': payload['request']['evidence'],
             'outcome': {'status': 'CLOSED', 'reported_outcome': payload['request']['outcome'], 'reservations_released': False, 'business_verification': 'NOT_EXECUTED'}})
        store._record_once(conn, marker_id, 'episode_closed', proposal['scope'], principal['subject'], {'closure': reference(result['record']), 'activation': payload['request']['activation']})
    return admission.response(result['record'], result['created'])


def revoke_review(store, principal, policy, settings, request):
    check_schema(request, admission.REVOKE)
    with store.write() as conn:
        authorize(store, conn, settings, principal, policy, 'review', [])
        row = required(store, conn, request['review'], 'episode_closure_review')
        closure_proposal(store, conn, principal, policy, row['payload']['request']['proposal'])
        if row['actor'] != principal['subject']: raise Forbidden('Only the reviewer can revoke this receipt')
        result = store._record_once(conn, identifier('closure-review-revoked', row['id']), 'closure_review_revocation', row['scope'], principal['subject'], deepcopy(request))
    return {'revocation': reference(result['record']), 'created': result['created']}


def verify_projection(store, conn):
    from sqlalchemy import select
    from air.storage import service_records, activation_heads
    expected = {}
    for record_id in conn.execute(select(service_records.c.id).where(service_records.c.kind == 'episode_closure')).scalars():
        row = store._get_record(conn, record_id); payload = row['payload']
        episode = required(store, conn, payload['activation'], 'activation_receipt')
        store._required(conn, payload['evidence'], 'air.Evidence')
        proposal = required(store, conn, payload['request']['proposal'], 'episode_closure_proposal')
        if proposal['payload']['request']['activation'] != payload['activation'] or proposal['payload']['request']['evidence'] != payload['evidence']:
            raise InvalidModel('Closure receipt disagrees with its proposal')
        marker_id = identifier('episode-closed', episode['id'])
        if marker_id in expected: raise InvalidModel('Episode has multiple closure receipts')
        expected[marker_id] = {'closure': reference(row), 'activation': payload['activation']}
    actual = {r: store._get_record(conn, r)['payload'] for r in conn.execute(select(service_records.c.id).where(service_records.c.kind == 'episode_closed')).scalars()}
    if actual != expected: raise InvalidModel('Episode closure markers disagree with their receipts')
    for marker_id in conn.execute(select(service_records.c.id).where(service_records.c.kind == 'admission_release_marker')).scalars():
        marker = store._get_record(conn, marker_id)
        original = required(store, conn, marker['payload']['admission'], 'admission_receipt')
        for episode_id in conn.execute(select(activation_heads.c.id).where(activation_heads.c.admission_id == original['id'])).scalars():
            if identifier('episode-closed', episode_id) not in expected: raise InvalidModel('Imported release abandons an open episode')
