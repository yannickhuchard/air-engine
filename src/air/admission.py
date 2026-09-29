"""Single-registry resource admission. No external action or design acceptance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func
from air import planning
from air.access import ScopedStore, Forbidden
from air.authority import KEY, authorize, pinned_inputs, period_key, micro, quantity, consistent_read
from air.core import INSTANT, TEXT, record
from air.expr import bounded
from air.foundation import InvalidModel, check_schema, key
from air.packages import RECORD_REF, reference, required, identifier
from air.projections import SNAPSHOT, snapshot
from air.reviews import record_key
from air.jobs import check_identity
from air.storage import Conflict, capacity_heads, reservations, activation_heads, now

PROPOSE = record({**{k: v for k, v in planning.REQUEST['properties'].items() if k not in ('pools', 'basis', 'as_of', 'unit')},
    'idempotency_key': KEY, 'offers': {'type': 'array', 'items': RECORD_REF, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True}})
REVIEW = record({'idempotency_key': KEY, 'proposal': RECORD_REF, 'decision': {'enum': ['ACCEPT', 'REJECT']}, 'rationale': TEXT, 'expires_at': INSTANT})
ADMIT = record({'idempotency_key': KEY, 'proposal': RECORD_REF,
    'approvals': {'type': 'array', 'items': RECORD_REF, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True}})
READ = record({'admission': RECORD_REF})
RELEASE = record({'idempotency_key': KEY, 'admission': RECORD_REF, 'rationale': TEXT})
ACTIVATE = record({'idempotency_key': KEY, 'admission': RECORD_REF, 'unit': SNAPSHOT})
REVOKE = record({'review': RECORD_REF, 'rationale': TEXT})


def scopes_for(store, principal, policy, request):
    guarded = ScopedStore(store, principal, policy)
    scopes = set()
    for pin in {d['baseline']['id']: d['baseline'] for d in request['demands']}.values():
        baseline = snapshot(guarded, pin)
        scopes.update(o['meta']['namespace'] for o in [baseline['baseline'], *baseline['objects']])
    guarded.check_read([d['unit'] for d in request['demands']])
    return scopes


def proposal_row(store, conn, principal, policy, pin):
    row = required(store, conn, pin, 'admission_proposal')
    scopes_for(store, principal, policy, row['payload']['request'])
    for scope in row['payload']['scopes']: policy.require(principal, 'read', scope)
    for offer_pin in row['payload']['request']['offers']:
        offer = required(store, conn, offer_pin, 'capacity_offer')
        pinned_inputs(store, principal, policy, offer['payload']['request'])
    return row


def build_plan(store, conn, principal, policy, settings, stamp, request, exclude_admission=None):
    pools, scopes = [], scopes_for(store, principal, policy, request)
    for pin in request['offers']:
        row = required(store, conn, pin, 'capacity_offer')
        observation = row['payload']['request']
        check_identity(store, conn, row['payload']['publisher_identity'], settings)
        scope = pinned_inputs(store, principal, policy, observation); scopes.add(scope)
        source = store._required(conn, observation['source'], 'air.Source')
        if datetime.fromisoformat(source['body']['captured_at']) > datetime.now(timezone.utc):
            raise InvalidModel('Capacity source capture is in the future')
        head = conn.execute(select(capacity_heads).where(capacity_heads.c.id == observation['scope']['id'])).mappings().first()
        if head is None or head['offer_id'] != row['id']: raise Conflict('Capacity offer has been superseded')
        if row['payload']['policy'] != stamp: raise Conflict('Capacity offer authority changed; publish a fresh observation')
        policy.require({'subject': row['actor'], 'role': row['payload']['publisher_role']}, 'capacity', scope)
        positions = {period_key(p): i for i, p in enumerate(observation['periods'])}
        indices = []
        for period in request['periods']:
            point = period_key(period)
            if point not in positions: raise InvalidModel('Selected periods fall outside the exact capacity offer')
            indices.append(positions[point])
        pool = {k: deepcopy(v) for k, v in observation.items() if k in planning.POOL['properties']}
        for field in ('gross', 'baseline_obligations'): pool[field] = [observation[field][i] for i in indices]
        bookings = []
        for period in request['periods']:
            start, end = period_key(period)
            query = select(func.coalesce(func.sum(reservations.c.micro_fte), 0)).where(reservations.c.pool_id == head['id'],
                reservations.c.released == 0, reservations.c.period_start < end, reservations.c.period_end > start)
            if exclude_admission: query = query.where(reservations.c.admission_id != exclude_admission)
            bookings.append(quantity(int(conn.execute(query).scalar_one())))
        pool['existing_reservations'] = bookings; pools.append(pool)
    args = {k: deepcopy(v) for k, v in request.items() if k in planning.REQUEST['properties']}
    args.update(pools=pools, basis='SCENARIO_INPUT', as_of=now(), unit='FTE')
    return args, sorted(scopes)


def replay(store, conn, record_id, request):
    prior = store._get_record(conn, record_id)
    if prior and prior['payload']['request'] != request: raise Conflict('Business operation idempotency key was reused')
    return prior


def response(row, created):
    return {'receipt': reference(row), 'created': created, **deepcopy(row['payload']['outcome'])}


def propose(store, principal, policy, settings, request):
    check_schema(request, PROPOSE); bounded(request); request = deepcopy(request)
    request['offers'].sort(key=lambda p: p['id'])
    scopes = scopes_for(store, principal, policy, request)
    record_id = record_key('admission-proposal', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'write', scopes)
        prior = replay(store, conn, record_id, request)
        if prior:
            proposal_row(store, conn, principal, policy, reference(prior))
            return {'proposal': reference(prior), 'created': False, 'report': prior['payload']['report']}
        args, scopes = build_plan(store, conn, principal, policy, settings, stamp, request)
        report = planning.plan(ScopedStore(store, principal, policy), args)
        selected = deepcopy(request)
        if report['candidate'] is not None:
            allocations = {(key(a['unit']), key(a['pool'])): a['per_week'] for a in report['candidate']['allocations']}
            for demand in selected['demands']: demand['per_week'] = allocations[(key(demand['unit']), key(demand['pool']))]
        selected['strategy'] = 'AS_PROPOSED'
        payload = {'request': request, 'selected': selected, 'report': report, 'scopes': scopes, 'policy': stamp,
            'capacity_provenance': 'AUTHORITY_REGISTRY_OFFERS', 'design_acceptance': 'NOT_EXECUTED'}
        bounded(payload)
        result = store._record_once(conn, record_id, 'admission_proposal', scopes[0], principal['subject'], payload)
    return {'proposal': reference(result['record']), 'created': result['created'], 'report': report}


def review(store, principal, policy, settings, request):
    check_schema(request, REVIEW); record_id = record_key('admission-review', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'review', [])
        proposal = proposal_row(store, conn, principal, policy, request['proposal'])
        for scope in proposal['payload']['scopes']: policy.require(principal, 'review', scope)
        if principal['subject'] == proposal['actor']: raise Forbidden('Independent review requires a different authenticated subject')
        prior = replay(store, conn, record_id, request)
        if prior: return {'review': reference(prior), 'created': False}
        if proposal['payload']['policy'] != stamp: raise Conflict('Proposal authority has changed')
        current = datetime.now(timezone.utc)
        if not current < datetime.fromisoformat(request['expires_at']) <= current + timedelta(days=7):
            raise InvalidModel('Review expiry must be within the next seven days')
        payload = {'request': deepcopy(request), 'policy': stamp, 'reviewer_role': principal['role']}
        result = store._record_once(conn, record_id, 'admission_review', proposal['scope'], principal['subject'], payload)
    return {'review': reference(result['record']), 'created': result['created']}


def revoke_review(store, principal, policy, settings, request):
    check_schema(request, REVOKE)
    with store.write() as conn:
        authorize(store, conn, settings, principal, policy, 'review', [])
        row = required(store, conn, request['review'], 'admission_review')
        proposal_row(store, conn, principal, policy, row['payload']['request']['proposal'])
        if row['actor'] != principal['subject']: raise Forbidden('Only the original reviewer can revoke their receipt')
        result = store._record_once(conn, identifier('admission-review-revoked', row['id']), 'admission_review_revocation',
            row['scope'], principal['subject'], deepcopy(request))
    return {'revocation': reference(result['record']), 'created': result['created']}


def check_approvals(store, conn, policy, stamp, proposal, pins):
    for pin in pins:
        row = required(store, conn, pin, 'admission_review'); payload = row['payload']; request = payload['request']
        if request['proposal'] != reference(proposal) or request['decision'] != 'ACCEPT' or row['actor'] == proposal['actor']:
            raise InvalidModel('Approval does not independently accept the exact proposal')
        if payload['policy'] != stamp or datetime.fromisoformat(request['expires_at']) <= datetime.now(timezone.utc):
            raise Conflict('Approval expired or its authority changed')
        if store._get_record(conn, identifier('admission-review-revoked', row['id'])): raise Conflict('Approval was revoked')
        for scope in proposal['payload']['scopes']:
            policy.require({'subject': row['actor'], 'role': payload['reviewer_role']}, 'review', scope)


def admit(store, principal, policy, settings, request):
    check_schema(request, ADMIT); request = deepcopy(request); request['approvals'].sort(key=lambda p: p['id'])
    record_id = record_key('admission', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'admit', [])
        proposal = proposal_row(store, conn, principal, policy, request['proposal']); payload = proposal['payload']
        for scope in payload['scopes']: policy.require(principal, 'admit', scope)
        prior = replay(store, conn, record_id, request)
        if prior: return response(prior, False)
        if payload.get('renewal_of'): raise InvalidModel('Use renewal to reauthorize existing reservations')
        if payload['policy'] != stamp: raise Conflict('Proposal authority changed')
        check_approvals(store, conn, policy, stamp, proposal, request['approvals'])
        args, _ = build_plan(store, conn, principal, policy, settings, stamp, payload['selected'])
        report = planning.plan(ScopedStore(store, principal, policy), args)
        accepted = payload['report']['result'] == 'SATISFIED' and report['result'] == 'SATISFIED'
        # A second key cannot reserve the same approved proposal twice.
        claim_id = identifier('proposal-admitted', proposal['id'])
        if store._get_record(conn, claim_id): raise Conflict('Proposal already admitted')
        current = datetime.now(timezone.utc)
        if any(micro(d['per_week'][i]) and datetime.fromisoformat(p['start']) < current for d in args['demands'] for i, p in enumerate(args['periods'])):
            raise InvalidModel('Admission cannot reserve work in a period that has already started')
        outcome = {'status': 'ADMITTED' if accepted else 'DENIED', 'capacity_result': report['result'],
            'reservations_created': accepted, 'business_execution_authorized': False, 'design_acceptance': 'NOT_EXECUTED'}
        record_payload = {'request': request, 'policy': stamp, 'outcome': outcome, 'report': report, 'selected': payload['selected']}
        bounded(record_payload)
        result = store._record_once(conn, record_id, 'admission_receipt', proposal['scope'], principal['subject'], record_payload)
        if accepted:
            unit_ids = sorted({d['unit']['id'] for d in payload['selected']['demands']})
            if conn.execute(select(reservations.c.id).where(reservations.c.unit_id.in_(unit_ids), reservations.c.released == 0).limit(1)).first():
                raise Conflict('A selected construction unit already holds an unreleased commitment')
            store._record_once(conn, claim_id, 'admission_claim', proposal['scope'], principal['subject'], {'proposal': reference(proposal), 'admission': reference(result['record'])})
            rows = reservation_rows(record_id, payload['selected'])
            if rows: conn.execute(reservations.insert(), rows)
    return response(result['record'], result['created'])


def reservation_rows(admission_id, selected):
    rows = []
    for demand in selected['demands']:
        for i, amount in enumerate(demand['per_week']):
            quantity_micro = micro(amount)
            if not quantity_micro: continue
            start, end = period_key(selected['periods'][i])
            rows.append({'id': identifier('reservation', admission_id, demand['unit'], demand['pool'], start),
                'admission_id': admission_id, 'pool_id': demand['pool']['id'], 'unit_id': demand['unit']['id'],
                'unit_revision': demand['unit']['revision'], 'period_start': start, 'period_end': end, 'micro_fte': quantity_micro, 'released': 0})
    return rows


def admission_row(store, conn, principal, policy, pin):
    row = required(store, conn, pin, 'admission_receipt')
    proposal = proposal_row(store, conn, principal, policy, row['payload']['request']['proposal'])
    return row, proposal


def read(store, principal, policy, request):
    check_schema(request, READ)
    with consistent_read(store) as conn:
        row, proposal = admission_row(store, conn, principal, policy, request['admission'])
        bookings = [dict(r) for r in conn.execute(select(reservations).where(reservations.c.admission_id == row['id']).order_by(reservations.c.id)).mappings()]
        released = store._get_record(conn, identifier('admission-released', row['id'])) is not None
        from air.renewal import current
        authorization, generation = current(store, conn, row)
        proposal_row(store, conn, principal, policy, authorization['payload']['request']['proposal'])
        episodes = []
        for episode in conn.execute(select(activation_heads).where(activation_heads.c.admission_id == row['id']).order_by(activation_heads.c.id)).mappings():
            activation = store._get_record(conn, episode['id'])
            closed = store._get_record(conn, identifier('episode-closed', episode['id']))
            episodes.append({'activation': reference(activation), 'unit': activation['payload']['request']['unit'],
                'status': 'CLOSED' if closed else 'OPEN', 'closure': closed['payload']['closure'] if closed else None})
    return {**response(row, False), 'released': released, 'reservations': bookings,
        'authorization': reference(authorization), 'authorization_generation': generation, 'episodes': episodes}


def release(store, principal, policy, settings, request):
    check_schema(request, RELEASE)
    with store.write() as conn:
        authorize(store, conn, settings, principal, policy, 'admit', [])
        row, proposal = admission_row(store, conn, principal, policy, request['admission'])
        for scope in proposal['payload']['scopes']: policy.require(principal, 'admit', scope)
        record_id = record_key('release', principal['subject'], request['idempotency_key'])
        prior = replay(store, conn, record_id, request)
        if prior: return response(prior, False)
        if row['payload']['outcome']['status'] != 'ADMITTED': raise InvalidModel('Only admitted capacity can be released')
        for episode_id in conn.execute(select(activation_heads.c.id).where(activation_heads.c.admission_id == row['id'])).scalars():
            if store._get_record(conn, identifier('episode-closed', episode_id)) is None:
                raise Conflict('Activated work is protected; explicit completion is required before release')
        payload = {'request': deepcopy(request), 'outcome': {'status': 'RELEASED', 'business_execution_authorized': False}}
        result = store._record_once(conn, record_id, 'admission_release', row['scope'], principal['subject'], payload)
        store._record_once(conn, identifier('admission-released', row['id']), 'admission_release_marker', row['scope'],
            principal['subject'], {'admission': reference(row)})
        conn.execute(update(reservations).where(reservations.c.admission_id == row['id']).values(released=1))
    return response(result['record'], result['created'])


def activate(store, principal, policy, settings, request):
    check_schema(request, ACTIVATE)
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'activate', [])
        row, proposal = admission_row(store, conn, principal, policy, request['admission'])
        for scope in proposal['payload']['scopes']: policy.require(principal, 'activate', scope)
        record_id = record_key('activation', principal['subject'], request['idempotency_key'])
        prior = replay(store, conn, record_id, request)
        if prior: return response(prior, False)
        from air.renewal import current
        authorization, generation = current(store, conn, row)
        effective_proposal = proposal_row(store, conn, principal, policy, authorization['payload']['request']['proposal'])
        for scope in effective_proposal['payload']['scopes']: policy.require(principal, 'activate', scope)
        if row['payload']['outcome']['status'] != 'ADMITTED' or authorization['payload']['policy'] != stamp:
            raise Conflict('Admission is not effective under current authority')
        if store._get_record(conn, identifier('admission-released', row['id'])): raise Conflict('Admission was released')
        selected = authorization['payload']['selected']
        matching = [d for d in selected['demands'] if d['unit'] == request['unit']]
        if not matching: raise InvalidModel('Unit is outside the admitted selection')
        check_approvals(store, conn, policy, stamp, effective_proposal, authorization['payload']['request']['approvals'])
        args, _ = build_plan(store, conn, principal, policy, settings, stamp, selected, exclude_admission=row['id'])
        if planning.plan(ScopedStore(store, principal, policy), args)['result'] != 'SATISFIED':
            raise Conflict('Admitted capacity is no longer supported by current conditions')
        periods = [i for d in matching for i, q in enumerate(d['per_week']) if micro(q)]
        current = datetime.now(timezone.utc)
        if not any(datetime.fromisoformat(selected['periods'][i]['start']) <= current < datetime.fromisoformat(selected['periods'][i]['end']) for i in periods):
            raise Conflict('Activation is outside its admitted time window')
        expected = {r['id']: r for r in reservation_rows(row['id'], selected)}
        actual = {r['id']: dict(r) for r in conn.execute(select(reservations).where(reservations.c.admission_id == row['id'])).mappings()}
        if actual != expected: raise Conflict('Admission reservations are no longer fully held')
        witness_id = identifier('unit-activation', row['id'], request['unit'])
        if store._get_record(conn, witness_id): raise Conflict('Unit already has an activation episode')
        payload = {'request': deepcopy(request), 'policy': stamp, 'authorization': reference(authorization), 'authorization_generation': generation, 'outcome': {'status': 'AUTHORIZED',
            'authorization_scope': 'LOCAL_RESOURCE_EPISODE', 'external_action_executed': False, 'design_acceptance': 'NOT_EXECUTED'}}
        result = store._record_once(conn, record_id, 'activation_receipt', row['scope'], principal['subject'], payload)
        store._record_once(conn, witness_id, 'activation_claim', row['scope'], principal['subject'], {'activation': reference(result['record'])})
        conn.execute(activation_heads.insert().values(id=record_id, admission_id=row['id'], unit_id=request['unit']['id'], unit_revision=request['unit']['revision']))
    return response(result['record'], result['created'])
