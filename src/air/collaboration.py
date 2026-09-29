"""Authenticated draft authorship, distinct from business approval or delegation."""
import json
from air.access import ScopedStore, Forbidden
from air.core import record, schema, validate, canonical, digest, reference_slots
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import InvalidModel, check_schema, exact
from air.packages import reference, lock_registry, RECORD_REF
from air.reviews import record_key
from air.storage import Conflict

SUBMIT = record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'object': {'oneOf': [schema('air.Contribution'), schema('air.Decision')]}})
READ = record({'submission': RECORD_REF})


def identity_context(principal, settings):
    return {'instance_id': settings.instance_id, 'mode': settings.auth_mode,
        'issuer': settings.oidc['issuer'] if settings.auth_mode == 'oidc' else None, 'subject': principal['subject']}


def identity_uri(context):
    return 'urn:air:identity:' + artifact_digest(context).split(':')[1]


def whoami(principal, settings):
    from air.tool_access import actions
    context = identity_context(principal, settings)
    return {'identity': identity_uri(context), 'subject': principal['subject'], 'role': principal['role'],
        'actions': actions(principal, principal['policy']) if 'policy' in principal else [],
        'identity_binding': 'CONNECTION_CREDENTIAL', 'client_supplied_identity_accepted': False,
        'authority': 'AUTHENTICATED_IDENTITY_ONLY', 'business_mandate_granted': False}


def author_field(obj):
    return 'author' if obj['meta']['type'] == 'air.Contribution' else 'authority'


def submit(store, principal, policy, settings, request):
    check_schema(request, SUBMIT)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel(str(exc)) from exc
    report = validate(request['object'])
    if not report['valid']: raise InvalidModel('Invalid collaboration draft', report)
    obj = json.loads(canonical(request['object']))
    request = {'idempotency_key': request['idempotency_key'], 'object': obj}
    context = identity_context(principal, settings);uri = identity_uri(context)
    if obj['body'][author_field(obj)] != uri or obj['meta']['provenance']['recorded_by'] != uri:
        raise Forbidden('Draft authorship must match the authenticated identity')
    policy.require(principal, 'write', obj['meta']['namespace'])
    refs = reference_slots(obj)
    ScopedStore(store, principal, policy).check_read([ref for _, ref, _ in refs])
    identifier = record_key('collaboration-submission', uri, request['idempotency_key'])
    from air.jobs import check_identity
    with store.write() as conn:
        lock_registry(conn);check_identity(store, conn, principal, settings)
        prior = store._get_record(conn, identifier)
        if prior:
            if prior['payload']['request'] != request: raise Conflict('Submission idempotency key was reused')
            return {'submission': reference(prior), 'created': False, 'object': prior['payload']['object'],
                'identity': uri, 'qualification': 'DRAFT', 'business_mandate_granted': False}
        for _, ref, kinds in refs:
            target = store._required(conn, ref)
            if target['meta']['type'] not in kinds: raise InvalidModel('Draft reference has an incompatible target type')
        row = store._put(conn, obj, principal['subject'])
        pin = {k: row[k] for k in ('id', 'revision', 'digest')}
        receipt = store._record_once(conn, identifier, 'collaboration_submission', obj['meta']['namespace'], principal['subject'],
            {'request': request, 'object': pin, 'identity_context': context, 'identity': uri,
             'policy_digest': policy.digest, 'qualification': 'DRAFT', 'business_mandate_granted': False})
    return {'submission': reference(receipt['record']), 'created': receipt['created'], 'object': pin,
        'identity': uri, 'qualification': 'DRAFT', 'business_mandate_granted': False}


def read(store, principal, policy, request):
    check_schema(request, READ)
    with store.engine.connect() as conn:
        row = store._get_record(conn, request['submission']['id'])
        if row is None or row['kind'] != 'collaboration_submission': raise Forbidden('Submission is unavailable')
        policy.require(principal, 'read', row['scope'])
        pin = row['payload']['object']
        ScopedStore(store, principal, policy).check_read([pin])
        if row['request_digest'] != request['submission']['digest']: raise Conflict('Submission digest differs')
        obj = store._required(conn, pin)
    return {'submission': reference(row), 'object': obj, 'identity': row['payload']['identity'],
        'authenticated_subject_at_submission': row['actor'], 'qualification': 'DRAFT',
        'business_mandate_granted': False, 'historical_receipt': True}


def verify_submissions(store, conn):
    from sqlalchemy import select
    from air.storage import service_records
    for identifier in conn.execute(select(service_records.c.id).where(service_records.c.kind == 'collaboration_submission')).scalars():
        row = store._get_record(conn, identifier);payload = row['payload'];request = payload['request']
        check_schema(request, SUBMIT)
        obj = request['object'];context = payload['identity_context'];uri = identity_uri(context)
        if not validate(obj)['valid']: raise InvalidModel('Imported collaboration draft is invalid')
        expected = {**exact(obj), 'digest': digest(obj)}
        stored = store._required(conn, expected)
        if (canonical(stored) != canonical(obj) or payload['object'] != expected or row['scope'] != obj['meta']['namespace']
            or row['actor'] != context['subject'] or payload['identity'] != uri
            or obj['body'][author_field(obj)] != uri or obj['meta']['provenance']['recorded_by'] != uri
            or identifier != record_key('collaboration-submission', uri, request['idempotency_key'])
            or payload['qualification'] != 'DRAFT' or payload['business_mandate_granted'] is not False):
            raise InvalidModel('Imported submission witness differs from its exact draft')
        for _, ref, kinds in reference_slots(obj):
            if store._required(conn, ref)['meta']['type'] not in kinds:
                raise InvalidModel('Imported submission reference has an incompatible type')
