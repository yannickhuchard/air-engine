"""Immutable, authorized artifact bytes inside the transactional registry."""
import base64
import binascii
import hashlib
from sqlalchemy import select
from air.access import AccessPolicy, Forbidden, ScopedStore
from air.collaboration import identity_context, identity_uri
from air.core import META, TEXT, URI, REF, record
from air.foundation import InvalidModel, check_schema
from air.jobs import check_identity
from air.packages import RECORD_REF, lock_registry, reference
from air.reviews import record_key
from air.storage import artifact_blobs, artifact_chunks, service_records, Conflict

MAX_SIZE = 16 * 1024 * 1024
JSON_MAX_SIZE = 512 * 1024
CHUNK_SIZE = 256 * 1024
CHECKSUM = {'type': 'string', 'pattern': '^sha256:[a-f0-9]{64}$'}
MEDIA_TYPE = {'type': 'string', 'maxLength': 255, 'pattern': '^[a-z0-9][a-z0-9.+_-]*/[a-z0-9][a-z0-9.+_-]*$'}
UPLOAD = record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'namespace': META['properties']['namespace'], 'media_type': MEDIA_TYPE})
IMPORT = record({**UPLOAD['properties'], 'content_base64': {'type': 'string', 'minLength': 1, 'maxLength': ((JSON_MAX_SIZE + 2) // 3) * 4}})
LOOKUP = record({'artifact': RECORD_REF})
OBJECT_PIN = record({**REF['properties'], 'digest': CHECKSUM})
CONTEXT_GUARD = record({'format': {'const': 'air.artifact-context/0.20'}, 'artifact': RECORD_REF, 'baseline': OBJECT_PIN, 'view': OBJECT_PIN})
DESCRIPTOR = record({**UPLOAD['properties'], 'content_digest': CHECKSUM, 'size': {'type': 'integer', 'minimum': 1, 'maximum': MAX_SIZE}})
CONTEXT = record({'instance_id': TEXT, 'mode': {'enum': ['local', 'oidc']}, 'issuer': {'anyOf': [URI, {'type': 'null'}]}, 'subject': {'type': 'string', 'minLength': 1, 'maxLength': 256}})
PAYLOAD = record({'format': {'enum': ['air.artifact/0.18', 'air.artifact/0.20']}, 'request': DESCRIPTOR,
    'identity_context': CONTEXT, 'identity': URI, 'policy_digest': CHECKSUM, 'evidence_qualified': {'const': False}})
PAYLOAD['properties']['context_required'] = {'const': True}


def _load_blob(conn, checksum):
    row = conn.execute(select(artifact_blobs).where(artifact_blobs.c.digest == checksum)).mappings().first()
    if row is None or not 1 <= row['size'] <= MAX_SIZE or row['chunks'] != (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE:
        raise InvalidModel('Artifact blob metadata is missing or invalid')
    output = bytearray();hasher = hashlib.sha256();count = 0
    query = select(artifact_chunks).where(artifact_chunks.c.digest == checksum).order_by(artifact_chunks.c.ordinal)
    for chunk in conn.execute(query).mappings():
        data = chunk['payload']
        expected = min(CHUNK_SIZE, row['size'] - count * CHUNK_SIZE)
        if chunk['ordinal'] != count or not isinstance(data, bytes) or len(data) != expected or expected <= 0:
            raise InvalidModel('Artifact chunks are incomplete or invalid')
        output.extend(data);hasher.update(data);count += 1
    if count != row['chunks'] or len(output) != row['size'] or hasher.hexdigest() != checksum:
        raise InvalidModel('Artifact content checksum mismatch')
    return bytes(output)


def _result(row):
    request = row['payload']['request']
    return {'artifact': reference(row), 'namespace': row['scope'], 'media_type': request['media_type'],
        'size': request['size'], 'content_digest': request['content_digest'],
        'artifact_reference': {'locator': row['id'], 'media_type': request['media_type'], 'size': request['size'],
            'digest': {'algorithm': 'sha256', 'value': request['content_digest'].split(':')[1]},
            'access_policy': 'Authenticated namespace access', 'retention_policy': 'Retained; no automatic deletion in this binding'},
        'identity': row['payload']['identity'], 'evidence_qualified': False, 'source_context_required': bool(row['payload'].get('context_required'))}


def _prepare(principal, policy, settings, request, data):
    check_schema(request, UPLOAD)
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_SIZE:
        raise InvalidModel('Artifact must contain 1 byte to 16 MiB')
    policy.require(principal, 'write', request['namespace'])
    checksum = hashlib.sha256(data).hexdigest()
    descriptor = {**request, 'content_digest': 'sha256:' + checksum, 'size': len(data)}
    context = identity_context(principal, settings);identity = identity_uri(context)
    identifier = record_key('artifact', identity, request['namespace'] + ':' + request['idempotency_key'])
    return checksum, descriptor, context, identity, identifier


def _put_locked(store, conn, principal, policy, settings, prepared, data, context_required=False):
    """Internal: caller owns a registry-locked write transaction; bytes were prepared outside it."""
    checksum, descriptor, context, identity, identifier = prepared
    check_identity(store, conn, principal, settings)
    current_policy = AccessPolicy.load(settings.home)
    if current_policy.digest != policy.digest: raise Forbidden('Access policy changed during artifact upload')
    current_policy.require(principal, 'write', descriptor['namespace'])
    prior = store._get_record(conn, identifier)
    if prior:
        if prior['kind'] != 'artifact_manifest' or prior['payload']['request'] != descriptor or bool(prior['payload'].get('context_required')) != context_required:
            raise Conflict('Artifact idempotency key was reused for different content')
        _load_blob(conn, checksum)
        return {**_result(prior), 'created': False}
    from air.quotas import artifact as check_quota
    check_quota(conn, descriptor['namespace'], len(data), checksum)
    created = store.insert_once(conn, artifact_blobs, {'digest': checksum, 'size': len(data), 'chunks': (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE}, ['digest'])
    if created:
        conn.execute(artifact_chunks.insert(), [{'digest': checksum, 'ordinal': index // CHUNK_SIZE, 'payload': data[index:index + CHUNK_SIZE]} for index in range(0, len(data), CHUNK_SIZE)])
    else:
        _load_blob(conn, checksum)
    receipt = store._record_once(conn, identifier, 'artifact_manifest', descriptor['namespace'], principal['subject'],
        {'format': 'air.artifact/0.20' if context_required else 'air.artifact/0.18', 'request': descriptor, 'identity_context': context, 'identity': identity,
         'policy_digest': policy.digest, 'evidence_qualified': False, **({'context_required': True} if context_required else {})})
    return {**_result(receipt['record']), 'created': receipt['created']}


def put(store, principal, policy, settings, request, data):
    prepared = _prepare(principal, policy, settings, request, data)
    with store.write() as conn:
        lock_registry(conn)
        return _put_locked(store, conn, principal, policy, settings, prepared, data)


def import_base64(store, principal, policy, settings, request):
    check_schema(request, IMPORT)
    try: data = base64.b64decode(request['content_base64'], validate=True)
    except (ValueError, binascii.Error): raise InvalidModel('Invalid artifact base64 encoding') from None
    if len(data) > JSON_MAX_SIZE: raise InvalidModel('JSON artifact import exceeds 512 KiB; use the binary CLI/API')
    return put(store, principal, policy, settings, {k: request[k] for k in UPLOAD['properties']}, data)


def context_guard_id(artifact_id):
    return record_key('artifact-context', artifact_id, 'view')


def _context_guard(store, conn, row):
    if (row['payload']['format'] == 'air.artifact/0.20') != bool(row['payload'].get('context_required')):
        raise InvalidModel('Artifact context requirement differs from its binding')
    guard = store._get_record(conn, context_guard_id(row['id']))
    if guard is None:
        if row['payload'].get('context_required'): raise InvalidModel('Required artifact source context is missing')
        return None
    if not row['payload'].get('context_required'): raise InvalidModel('Unexpected artifact source context')
    check_schema(guard['payload'], CONTEXT_GUARD)
    if guard['kind'] != 'artifact_context' or guard['scope'] != row['scope'] or guard['actor'] != row['actor'] or guard['payload']['artifact'] != reference(row):
        raise InvalidModel('Artifact context guard differs from its manifest')
    store._required(conn, guard['payload']['baseline'], 'air.Baseline')
    store._required(conn, guard['payload']['view'], 'air.View')
    return guard


def _authorized(store, conn, principal, policy, request):
    row = store._get_record(conn, request['artifact']['id'])
    if row is None or row['kind'] != 'artifact_manifest': raise Forbidden('Artifact is unavailable')
    policy.require(principal, 'read', row['scope'])
    # A DataSchema or Source carries {locator, content digest}; the manifest digest is equally exact. Either one binds the read.
    if request['artifact']['digest'] not in (row['request_digest'], row['payload']['request']['content_digest']):
        raise Conflict('Artifact digest differs: give the manifest digest or the content digest (sha256:<artifact_reference.digest.value>)')
    check_schema(row['payload'], PAYLOAD)
    guard = _context_guard(store, conn, row)
    if guard:
        ScopedStore(store, principal, policy).check_read([guard['payload']['baseline']])
    return row


def describe(store, principal, policy, request):
    check_schema(request, LOOKUP)
    with store.engine.connect() as conn:
        return _result(_authorized(store, conn, principal, policy, request))


def download(store, principal, policy, request):
    check_schema(request, LOOKUP)
    with store.engine.connect() as conn:
        row = _authorized(store, conn, principal, policy, request)
        result = _result(row)
        data = _load_blob(conn, result['content_digest'].split(':')[1])
        if len(data) != result['size']: raise InvalidModel('Artifact manifest size differs from its content')
    return result, data


def read_base64(store, principal, policy, request):
    result = describe(store, principal, policy, request)
    if result['size'] > JSON_MAX_SIZE: raise InvalidModel('JSON artifact read exceeds 512 KiB; use the binary CLI/API')
    result, data = download(store, principal, policy, request)
    return {**result, 'content_base64': base64.b64encode(data).decode('ascii')}


def verify_artifacts(store, conn):
    referenced = set()
    for row in conn.execute(select(service_records).where(service_records.c.kind == 'artifact_manifest')).mappings():
        entry = store._get_record(conn, row['id']);payload = entry['payload']
        check_schema(payload, PAYLOAD)
        _context_guard(store, conn, entry)
        request, context = payload['request'], payload['identity_context']
        identity = identity_uri(context)
        expected = record_key('artifact', identity, request['namespace'] + ':' + request['idempotency_key'])
        if entry['id'] != expected or entry['scope'] != request['namespace'] or entry['actor'] != context['subject'] or payload['identity'] != identity:
            raise InvalidModel('Artifact receipt identity or namespace differs')
        if context['mode'] == 'local' and context['issuer'] is not None or context['mode'] == 'oidc' and context['issuer'] is None:
            raise InvalidModel('Artifact receipt authentication context differs')
        checksum = request['content_digest'].split(':')[1]
        data = _load_blob(conn, checksum)
        if len(data) != request['size']: raise InvalidModel('Artifact receipt size differs')
        referenced.add(checksum)
    blobs = set(conn.execute(select(artifact_blobs.c.digest)).scalars())
    chunks = set(conn.execute(select(artifact_chunks.c.digest).distinct()).scalars())
    if blobs != referenced or chunks != blobs:
        raise InvalidModel('Artifact content is orphaned or missing its manifest')

    for raw in conn.execute(select(service_records).where(service_records.c.kind == 'artifact_context')).mappings():
        guard = store._get_record(conn, raw['id']);check_schema(guard['payload'], CONTEXT_GUARD)
        manifest = store._get_record(conn, guard['payload']['artifact']['id'])
        if manifest is None or manifest['kind'] != 'artifact_manifest' or guard['id'] != context_guard_id(manifest['id']):
            raise InvalidModel('Artifact context guard is orphaned')
        _context_guard(store, conn, manifest)
