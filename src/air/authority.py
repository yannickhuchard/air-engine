"""Committed local business policy and scoped, versioned capacity observations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import select, update, delete, func
from air.access import AccessPolicy, ScopedStore, Forbidden
from air.core import URI, INSTANT, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema
from air.jobs import check_identity
from air.packages import RECORD_REF, identifier, lock_registry, reference, required
from air.planning import OBSERVATIONS
from air.projections import SNAPSHOT
from air.reviews import record_key
from air.storage import Conflict, authority_policies, capacity_heads, resource_bindings, reservations, now

KEY = {'type': 'string', 'minLength': 1, 'maxLength': 128}
PERIODS = {'type': 'array', 'minItems': 1, 'maxItems': 104,
           'items': record({'start': INSTANT, 'end': INSTANT})}
OFFER = record({'idempotency_key': KEY, 'scope': SNAPSHOT, 'source': SNAPSHOT,
    'expected_offer': {'anyOf': [RECORD_REF, {'type': 'null'}]},
    'resource_kind': {'const': 'HUMAN_FTE'},
    'resource_ids': {'type': 'array', 'items': URI, 'minItems': 1, 'maxItems': 1000, 'uniqueItems': True},
    'availability': {'enum': ['AVAILABLE', 'UNAVAILABLE']}, 'observed_at': INSTANT, 'expires_at': INSTANT,
    'periods': PERIODS, 'gross': OBSERVATIONS, 'baseline_obligations': OBSERVATIONS})
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
WEEK = 7 * 86400


def epoch(value):
    date = datetime.fromisoformat(value)
    if date.microsecond: raise InvalidModel('Capacity periods use whole UTC seconds')
    delta = date - EPOCH
    return delta.days * 86400 + delta.seconds


def period_key(period): return epoch(period['start']), epoch(period['end'])


def micro(value):
    whole, _, fraction = value.partition('.')
    return int(whole) * 1000000 + int((fraction + '000000')[:6])


def quantity(value):
    whole, fraction = divmod(value, 1000000)
    return str(whole) + ('.' + str(fraction).zfill(6).rstrip('0') if fraction else '')


def sync_policy(store, policy, only_if_missing=False):
    """Trusted OS operator operation, intentionally absent from the public API."""
    with store.write() as conn:
        lock_registry(conn)
        prior = conn.execute(select(authority_policies).where(authority_policies.c.id == 1).with_for_update()).mappings().first()
        if prior is not None and (only_if_missing or prior['digest'] == policy.digest):
            return {'generation': prior['generation'], 'digest': prior['digest'], 'changed': False}
        generation = prior['generation'] + 1 if prior else 1
        payload = json.dumps(policy.document, ensure_ascii=False, sort_keys=True)
        record_id = identifier('authority-policy', policy.digest)
        store._record_once(conn, record_id, 'authority_policy', 'air.system', 'local-operator',
                           {'policy': policy.document, 'digest': policy.digest})
        values = {'generation': generation, 'digest': policy.digest, 'payload': payload,
                  'actor': 'local-operator', 'updated_at': now()}
        if prior is None: conn.execute(authority_policies.insert().values(id=1, **values))
        else: conn.execute(update(authority_policies).where(authority_policies.c.id == 1).values(**values))
        store.audit(conn, 'local-operator', 'authority.policy-set', str(generation) + ':' + policy.digest)
    return {'generation': generation, 'digest': policy.digest, 'changed': True}


def policy_stamp(conn, policy):
    head = conn.execute(select(authority_policies).where(authority_policies.c.id == 1).with_for_update()).mappings().first()
    if head is None: raise InvalidModel('Business authority policy is not configured; use policy-set from the AIR home')
    committed = AccessPolicy(json.loads(head['payload']))
    if committed.digest != head['digest']: raise InvalidModel('Committed authority policy integrity failed')
    if head['digest'] != policy.digest: raise Conflict('Business policy is pending synchronization with its committed version')
    return {'generation': head['generation'], 'digest': head['digest']}


def authorize(store, conn, settings, principal, policy, action, namespaces):
    lock_registry(conn)
    stamp = policy_stamp(conn, policy)
    check_identity(store, conn, principal, settings)
    for namespace in namespaces: policy.require(principal, action, namespace)
    return stamp


def normalize_offer(request):
    check_schema(request, OFFER)
    request = deepcopy(request)
    request['resource_ids'].sort()
    previous = None
    for period in request['periods']:
        start, end = period_key(period)
        if end - start != WEEK or previous is not None and start != previous:
            raise InvalidModel('Capacity periods must be contiguous half-open UTC weeks')
        previous = end
        for field in ('start', 'end'):
            period[field] = datetime.fromisoformat(period[field]).isoformat(timespec='seconds').replace('+00:00', 'Z')
    for field in ('gross', 'baseline_obligations'):
        if len(request[field]) != len(request['periods']): raise InvalidModel('Capacity vectors differ from their periods')
        normalized = []
        for value in request[field]:
            if value is None: normalized.append(None);continue
            amount = micro(value)
            if amount > 1000 * 1000000 or field == 'gross' and amount > len(request['resource_ids']) * 1000000:
                raise InvalidModel('Declared human capacity exceeds the distinct resource bound')
            normalized.append(quantity(amount))
        request[field] = normalized
    return request


def pinned_inputs(store, principal, policy, request):
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([request['scope'], request['source']])
    with store.engine.connect() as conn:
        scope = store._required(conn, request['scope'], 'air.Scope')
        store._required(conn, request['source'], 'air.Source')
    return scope['meta']['namespace']


def publish_offer(store, principal, policy, settings, request):
    request = normalize_offer(request)
    namespace = pinned_inputs(store, principal, policy, request)
    offer_id = record_key('capacity-offer', principal['subject'], request['idempotency_key'])
    pool_id = request['scope']['id']
    with store.write() as conn:
        stamp = authorize(store, conn, settings, principal, policy, 'capacity', [namespace])
        head = conn.execute(select(capacity_heads).where(capacity_heads.c.id == pool_id)).mappings().first()
        prior = store._get_record(conn, offer_id)
        if prior is not None:
            if prior['payload']['request'] != request: raise Conflict('Capacity idempotency key was reused')
            return {'offer': reference(prior), 'created': False, 'current': bool(head and head['offer_id'] == prior['id'])}
        current = datetime.now(timezone.utc)
        source = store._required(conn, request['source'], 'air.Source')
        if datetime.fromisoformat(source['body']['captured_at']) > current: raise InvalidModel('Capacity source capture is in the future')
        if datetime.fromisoformat(request['observed_at']) > current:
            raise InvalidModel('Capacity observation cannot come from the future')
        expiry = datetime.fromisoformat(request['expires_at'])
        if not current < expiry <= current + timedelta(days=366): raise InvalidModel('Capacity observation must expire within the next 366 days')
        if request['availability'] == 'AVAILABLE' and expiry < datetime.fromisoformat(request['periods'][-1]['end']):
            raise InvalidModel('An available offer must remain valid through its declared horizon')
        if head is None and request['expected_offer'] is not None:
            raise Conflict('Capacity pool has no previous offer')
        if head is not None:
            previous = store._get_record(conn, head['offer_id'])
            if request['expected_offer'] != reference(previous): raise Conflict('Capacity offer was superseded; use its exact current version')
            if head['namespace'] != namespace: raise Conflict('Capacity pool cannot change namespace')
        anchor = epoch(request['periods'][0]['start']) % WEEK
        if head is not None and head['week_anchor'] != anchor:
            raise InvalidModel('Capacity pool periods must retain their established weekly grid')
        resources = request['resource_ids']
        for offset in range(0, len(resources), 256):
            existing = conn.execute(select(resource_bindings).where(resource_bindings.c.id.in_(resources[offset:offset + 256]))).mappings()
            if any(row['pool_id'] != pool_id for row in existing):
                raise Conflict('A resource already belongs to another capacity pool')
        old_ids = set(conn.execute(select(resource_bindings.c.id).where(resource_bindings.c.pool_id == pool_id)).scalars())
        active = conn.execute(select(reservations.c.id).where(reservations.c.pool_id == pool_id, reservations.c.released == 0).limit(1)).first()
        if old_ids - set(resources) and active:
            raise InvalidModel('Release or close existing commitments before removing their resource identities')
        payload = {'request': request, 'policy': stamp, 'publisher_role': principal['role'], 'publisher_identity': {k: deepcopy(principal[k]) for k in ('subject', 'role', 'authorization')}, 'evidence_class': 'DECLARED_BY_AUTHORIZED_SUBJECT'}
        result = store._record_once(conn, offer_id, 'capacity_offer', namespace, principal['subject'], payload)
        generation = head['generation'] + 1 if head else 1
        if head is None:
            conn.execute(capacity_heads.insert().values(id=pool_id, namespace=namespace, offer_id=offer_id, generation=generation, week_anchor=anchor))
        else:
            conn.execute(update(capacity_heads).where(capacity_heads.c.id == pool_id).values(offer_id=offer_id, generation=generation))
        conn.execute(delete(resource_bindings).where(resource_bindings.c.pool_id == pool_id))
        conn.execute(resource_bindings.insert(), [{'id': resource_id, 'pool_id': pool_id} for resource_id in resources])
    return {'offer': reference(result['record']), 'created': result['created'], 'current': True, 'generation': generation,
            'reservations_created': False, 'business_execution_authorized': False}


def consistent_read(store):
    connection = store.engine.connect()
    return connection if store.sqlite else connection.execution_options(isolation_level='REPEATABLE READ')


def get_offer(store, principal, policy, request):
    check_schema(request, record({'pool_id': URI}))
    with consistent_read(store) as conn:
        head = conn.execute(select(capacity_heads).where(capacity_heads.c.id == request['pool_id'])).mappings().first()
        if head is None: raise Forbidden('Capacity pool is unavailable in the permitted scope')
        row = store._get_record(conn, head['offer_id'])
        offer = row['payload']['request']
        pinned_inputs(store, principal, policy, offer)
        bookings = []
        for period in offer['periods']:
            start, end = period_key(period)
            amount = conn.execute(select(func.coalesce(func.sum(reservations.c.micro_fte), 0)).where(
                reservations.c.pool_id == head['id'], reservations.c.released == 0,
                reservations.c.period_start < end, reservations.c.period_end > start)).scalar_one()
            bookings.append(quantity(int(amount)))
        return {'offer': reference(row), 'generation': head['generation'], 'observation': offer,
            'existing_reservations': bookings, 'expired': datetime.fromisoformat(offer['expires_at']) <= datetime.now(timezone.utc),
            'evidence_class': row['payload']['evidence_class'], 'business_execution_authorized': False}


def verify_projection(store, conn):
    """Reject transfer heads that disagree with immutable capacity/admission receipts."""
    from air.storage import service_records, activation_heads
    from air.admission import reservation_rows
    head = conn.execute(select(authority_policies)).mappings().first()
    if head:
        policy = AccessPolicy(json.loads(head['payload']))
        witness = store._get_record(conn, identifier('authority-policy', policy.digest))
        if head['id'] != 1 or head['generation'] < 1 or head['digest'] != policy.digest or witness is None or witness['kind'] != 'authority_policy' or witness['payload'] != {'policy': policy.document, 'digest': policy.digest}:
            raise InvalidModel('Invalid imported authority policy projection')
    expected_bindings = {}
    for pool in conn.execute(select(capacity_heads)).mappings():
        offer = store._get_record(conn, pool['offer_id'])
        if offer is None or offer['kind'] != 'capacity_offer': raise InvalidModel('Invalid imported capacity offer head')
        request = normalize_offer(offer['payload']['request'])
        scope = store._required(conn, request['scope'], 'air.Scope')
        store._required(conn, request['source'], 'air.Source')
        if request != offer['payload']['request'] or pool['id'] != request['scope']['id'] or pool['namespace'] != scope['meta']['namespace'] or pool['week_anchor'] != epoch(request['periods'][0]['start']) % WEEK:
            raise InvalidModel('Invalid imported capacity pool projection')
        seen, row = set(), offer
        while row:
            if row['id'] in seen or row['payload']['request']['scope']['id'] != pool['id']: raise InvalidModel('Invalid imported capacity history')
            seen.add(row['id']); previous = row['payload']['request']['expected_offer']
            row = required(store, conn, previous, 'capacity_offer') if previous else None
        if pool['generation'] != len(seen): raise InvalidModel('Capacity generation disagrees with its history')
        for resource_id in request['resource_ids']:
            if resource_id in expected_bindings: raise InvalidModel('Imported capacity counts a resource twice')
            expected_bindings[resource_id] = pool['id']
    actual = {r['id']: r['pool_id'] for r in conn.execute(select(resource_bindings)).mappings()}
    if actual != expected_bindings: raise InvalidModel('Imported resource bindings differ from current offers')
    expected_reservations, expected_activations = {}, {}
    for record_id in conn.execute(select(service_records.c.id).where(service_records.c.kind.in_(['admission_receipt', 'activation_receipt']))).scalars():
        row = store._get_record(conn, record_id); payload = row['payload']
        if row['kind'] == 'admission_receipt':
            if payload['outcome']['status'] != 'ADMITTED': continue
            marker = store._get_record(conn, identifier('admission-released', row['id']))
            claim = store._get_record(conn, identifier('proposal-admitted', payload['request']['proposal']['id']))
            if claim is None or claim['payload'].get('admission') != reference(row): raise InvalidModel('Imported admission claim is missing')
            for booking in reservation_rows(row['id'], payload['selected']):
                booking['released'] = int(marker is not None)
                expected_reservations[booking['id']] = booking
        else:
            request = payload['request']
            required(store, conn, request['admission'], 'admission_receipt')
            expected_activations[row['id']] = {'id': row['id'], 'admission_id': request['admission']['id'],
                'unit_id': request['unit']['id'], 'unit_revision': request['unit']['revision']}
    actual = {r['id']: dict(r) for r in conn.execute(select(reservations)).mappings()}
    if actual != expected_reservations: raise InvalidModel('Imported reservations differ from immutable admission receipts')
    actual = {r['id']: dict(r) for r in conn.execute(select(activation_heads)).mappings()}
    if actual != expected_activations: raise InvalidModel('Imported activation projection differs from immutable receipts')

    from air.renewal import verify_projection as verify_renewals
    verify_renewals(store, conn)

    from air.closure import verify_projection as verify_closures
    verify_closures(store, conn)
