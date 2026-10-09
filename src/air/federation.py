"""Signed full publication checkpoints from independently operated AIR registries.

This is a read projection, not distributed admission. Imported source authority
is never transferred, and no business reservation or model revision is created.
"""
import base64
from datetime import datetime, timezone

import rfc8785
from sqlalchemy import select

from air.access import AccessPolicy, Forbidden, NAMESPACES
from air.core import INSTANT, URI, TEXT, record
from air.expr import artifact_digest
from air.external_proofs import crypto
from air.foundation import check_budget, check_schema, InvalidModel
from air.jobs import check_identity
from air.packages import identifier, lock_registry, reference
from air.projections import SNAPSHOT
from air.storage import Conflict, service_records

ENGINE = 'air.federated-checkpoint/1'
KEY_ID = {'type': 'string', 'pattern': '^[a-zA-Z0-9_.-]{1,128}$'}
NAMESPACE = {'type': 'string', 'pattern': '^[a-z][a-z0-9_.-]{0,127}$'}
TRUST = record({'peer': URI, 'key_id': KEY_ID, 'subject': URI,
    'public_key': {'type': 'string', 'minLength': 44, 'maxLength': 44},
    'namespaces': NAMESPACES, 'not_before': INSTANT, 'expires_at': INSTANT,
    'max_age_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 604800}})
MANIFEST = record({'baseline': SNAPSHOT, 'exports': {'type': 'array', 'items': SNAPSHOT, 'maxItems': 256, 'uniqueItems': True},
                   'profiles': {'type': 'array', 'items': TEXT, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True}})
EVENT = record({'format': {'const': ENGINE}, 'peer': URI, 'key_id': KEY_ID,
    'audience': {'type': 'string', 'minLength': 1, 'maxLength': 128}, 'aggregate': URI,
    'namespace': NAMESPACE, 'sequence': {'type': 'integer', 'minimum': 1, 'maximum': 9007199254740991},
    'published_at': INSTANT, 'expires_at': INSTANT, 'status': {'enum': ['PUBLISHED', 'REVOKED']},
    'manifest': MANIFEST})
IMPORT = record({'event': EVENT, 'signature': {'type': 'string', 'minLength': 88, 'maxLength': 88}})
READ = record({'peer': URI, 'aggregate': URI, 'namespace': NAMESPACE})
REVOKE = record({'peer': URI, 'key_id': KEY_ID, 'rationale': TEXT})


def clock(): return datetime.now(timezone.utc)
def instant(value): return datetime.fromisoformat(value)
def trust_id(peer, key): return identifier('federation-key', peer, key)
def revoked_id(peer, key): return identifier('federation-revoked', peer, key)


def register_peer(store, settings, request):
    """Trusted local operator command, deliberately absent from HTTP/MCP."""
    check_schema(request, TRUST)
    public, _ = crypto()
    try: public.from_public_bytes(base64.b64decode(request['public_key'], validate=True))
    except ValueError as exc: raise InvalidModel('Invalid peer Ed25519 public key') from exc
    if not request['namespaces'] or not instant(request['not_before']) < instant(request['expires_at']):
        raise InvalidModel('Peer trust needs explicit scope and a nonempty validity interval')
    with store.write() as conn:
        lock_registry(conn)
        result = store._record_once(conn, trust_id(request['peer'], request['key_id']), 'federation_key',
            'air.system', 'local-operator', {'instance_id': settings.instance_id, 'request': request})
    return {'key': reference(result['record']), 'created': result['created']}


def revoke_peer(store, request):
    check_schema(request, REVOKE)
    with store.write() as conn:
        lock_registry(conn)
        if not store._get_record(conn, trust_id(request['peer'], request['key_id'])):
            raise InvalidModel('Unknown peer trust key')
        result = store._record_once(conn, revoked_id(request['peer'], request['key_id']), 'federation_key_revoked',
                                   'air.system', 'local-operator', request)
    return {'revocation': reference(result['record']), 'created': result['created']}


def verify(store, conn, settings, policy, envelope):
    check_schema(envelope, IMPORT)
    event = envelope['event']; current = clock()
    row = store._get_record(conn, trust_id(event['peer'], event['key_id']))
    if row is None or row['kind'] != 'federation_key': raise InvalidModel('Peer key is not trusted')
    if store._get_record(conn, revoked_id(event['peer'], event['key_id'])):
        raise Forbidden('Peer key has been revoked')
    trust = row['payload']['request']
    if row['payload']['instance_id'] != settings.instance_id or event['audience'] != settings.instance_id:
        raise Forbidden('Federated checkpoint is for another receiver')
    if not instant(trust['not_before']) <= current < instant(trust['expires_at']):
        raise Forbidden('Peer trust expired or not yet valid')
    published = instant(event['published_at'])
    if not instant(trust['not_before']) <= published <= current < instant(event['expires_at']):
        raise InvalidModel('Checkpoint is future-dated, expired or predates peer trust')
    if (current - published).total_seconds() > trust['max_age_seconds']:
        raise InvalidModel('Checkpoint exceeds its permitted freshness')
    if event['namespace'] not in trust['namespaces'] and '*' not in trust['namespaces']:
        raise Forbidden('Checkpoint namespace is outside the trusted peer scope')
    policy.require({'subject': trust['subject'], 'role': 'editor'}, 'publish', event['namespace'])
    public, bad_signature = crypto()
    try:
        key = public.from_public_bytes(base64.b64decode(trust['public_key'], validate=True))
        key.verify(base64.b64decode(envelope['signature'], validate=True), rfc8785.dumps(event))
    except (ValueError, bad_signature) as exc:
        raise InvalidModel('Invalid federated checkpoint signature') from exc


def checkpoints(store, conn, request):
    # Fail closed rather than accidentally selecting a stale head from a truncated index.
    ids = conn.execute(select(service_records.c.id).where(service_records.c.kind == 'federation_checkpoint',
                       service_records.c.scope == request['namespace']).limit(4097)).scalars().all()
    if len(ids) > 4096: raise InvalidModel('Federation namespace checkpoint budget exceeded')
    selected = []
    for rid in ids:
        row = store._get_record(conn, rid)
        e = row['payload']['envelope']['event']
        if e['peer'] == request['peer'] and e['aggregate'] == request['aggregate']:
            selected.append(row)
    return sorted(selected, key=lambda r: r['payload']['envelope']['event']['sequence'])


def ingest(store, principal, policy, settings, request):
    check_schema(request, IMPORT); check_budget(request)
    event = request['event']
    policy.require(principal, 'write', event['namespace'])
    with store.write() as conn:
        lock_registry(conn); check_identity(store, conn, principal, settings)
        if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Authority changed')
        verify(store, conn, settings, policy, request)
        store._record_once(conn, identifier('federation-aggregate', event['peer'], event['aggregate']),
            'federation_aggregate', event['namespace'], event['peer'],
            {'peer': event['peer'], 'aggregate': event['aggregate'], 'namespace': event['namespace']})
        history = checkpoints(store, conn, event)
        for old in history:
            previous = old['payload']['envelope']['event']
            a, b = previous['manifest']['baseline'], event['manifest']['baseline']
            if a['id'] == b['id']:
                if a['revision'] == b['revision'] and a['digest'] != b['digest']:
                    raise Conflict('Peer changed the content of an exact baseline revision')
                if (previous['sequence'] - event['sequence']) * (a['revision'] - b['revision']) < 0:
                    raise Conflict('Checkpoint sequence and baseline revision orders contradict')
        record_id = identifier('federation-checkpoint', event['peer'], event['aggregate'], event['sequence'])
        prior = store._get_record(conn, record_id)
        if prior and prior['payload']['envelope'] != request:
            raise Conflict('Peer equivocation: sequence already received with different content')
        if prior: result = {'record': prior, 'created': False}
        else:
            result = store._record_once(conn, record_id, 'federation_checkpoint', event['namespace'],
                principal['subject'], {'envelope': request, 'authority_transferred': False})
        rows = checkpoints(store, conn, event)
        latest = rows[-1]['payload']['envelope']['event']
    return {'checkpoint': reference(result['record']), 'created': result['created'],
            'head_sequence': latest['sequence'], 'head_status': latest['status'],
            'head_changed': result['created'] and latest['sequence'] == event['sequence'],
            'canonical_model_changed': False, 'reservations_created': False}


def read(store, principal, policy, settings, request):
    check_schema(request, READ)
    policy.require(principal, 'read', request['namespace'])
    with store.engine.connect() as conn:
        rows = checkpoints(store, conn, request)
        if not rows: raise InvalidModel('No readable federated checkpoint')
        latest = rows[-1]
        # Revocation/expiration must not fall back to an older favorable publication.
        verify(store, conn, settings, policy, latest['payload']['envelope'])
        event = latest['payload']['envelope']['event']
    return {'engine': ENGINE, 'checkpoint': reference(latest), 'event': event,
            'new_use_allowed': event['status'] == 'PUBLISHED', 'source_authority_preserved': True,
            'coverage': 'ONE_SIGNED_FULL_PUBLICATION_CHECKPOINT', 'distributed_admission': False}
