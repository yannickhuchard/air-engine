"""Operator-controlled signed outbox for exact local publications; no network side effects."""
import base64
from datetime import timedelta
from pathlib import Path

import rfc8785
from sqlalchemy import select

from air.access import AccessPolicy, Forbidden
from air.backup_crypto import create_key, read_key
from air.config import protect_directory, write_private
from air.core import URI, INSTANT, record
from air.federation import ENGINE, KEY_ID, clock, instant
from air.foundation import InvalidModel, check_schema, check_budget
from air.jobs import check_identity
from air.packages import RECORD_REF, identifier, lock_registry, publication_tree, reference
from air.storage import Conflict, service_records

MAX_OUTBOX = 4096

REQUEST = record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'publication': RECORD_REF, 'peer': URI, 'key_id': KEY_ID,
    'audience': {'type': 'string', 'minLength': 1, 'maxLength': 128}, 'expires_at': INSTANT})


def private_key(path):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise InvalidModel('Signed publication requires the optional AIR proofs extra') from exc
    return Ed25519PrivateKey.from_private_bytes(read_key(path))


def keygen(directory):
    # Uses the same 32-byte private-file/ACL contract as backup keys, in a new directory.
    created = create_key(directory)
    path = Path(created['key_file'])
    renamed = path.with_name('publication.key')
    path.rename(renamed)
    key = private_key(renamed)
    public = base64.b64encode(key.public_key().public_bytes_raw()).decode()
    write_private(renamed.with_name('public-key.json'), {'algorithm': 'Ed25519', 'public_key': public})
    return {'key_file': str(renamed), 'public_key': public, 'key_contents_displayed': False}


def export_checkpoint(store, principal, policy, settings, request, key_path):
    check_schema(request, REQUEST); check_budget(request)
    if settings.instance_id == 'unconfigured': raise InvalidModel('Configure the source instance first')
    signing = private_key(key_path)
    public = base64.b64encode(signing.public_key().public_bytes_raw()).decode()
    command = identifier('federation-outbox-command', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        lock_registry(conn); check_identity(store, conn, principal, settings)
        if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Authority changed')
        source, reasons = publication_tree(store, conn, principal, policy, request['publication'], False)
        if source['actor'] != principal['subject']: raise Forbidden('Only the publication owner may sign its checkpoint')
        policy.require(principal, 'publish', source['scope'])
        manifest = source['payload']['manifest']
        # The source key identity is immutable, including after restart or restoring another instance.
        store._record_once(conn, identifier('federation-signer', request['peer'], request['key_id']),
            'federation_signer', source['scope'], principal['subject'],
            {'instance_id': settings.instance_id, 'peer': request['peer'], 'key_id': request['key_id'],
             'public_key': public, 'subject': principal['subject']})
        prior = store._get_record(conn, command)
        if prior:
            if prior['payload']['request'] != request: raise Conflict('Outbox idempotency key was reused')
            envelope = prior['payload']['envelope']
            if reasons and envelope['event']['status'] == 'PUBLISHED':
                raise InvalidModel('Publication is no longer usable; export a new withdrawal checkpoint')
            if instant(envelope['event']['expires_at']) <= clock(): raise InvalidModel('Outbox checkpoint expired')
            return {'outbox': reference(prior), 'envelope': envelope, 'created': False, 'network_sent': False}
        current = clock()
        if not current < instant(request['expires_at']) <= current + timedelta(days=7):
            raise InvalidModel('Checkpoint expires within seven days')
        ids = conn.execute(select(service_records.c.id).where(service_records.c.kind == 'federation_outbox',
                           service_records.c.scope == source['scope']).limit(MAX_OUTBOX + 1)).scalars().all()
        if len(ids) >= MAX_OUTBOX: raise InvalidModel('Federation outbox namespace budget exceeded')
        history = []
        for rid in ids:
            event = store._get_record(conn, rid)['payload']['envelope']['event']
            if (event['peer'], event['aggregate'], event['audience']) == (request['peer'], manifest['package_id'], request['audience']):
                history.append(event)
        for event in history:
            a, b = event['manifest']['baseline'], manifest['baseline']
            if a['id'] == b['id'] and a['revision'] > b['revision']:
                raise Conflict('Cannot export a regressing baseline revision')
        sequence = max((e['sequence'] for e in history), default=0) + 1
        baseline = store._required(conn, manifest['baseline'], 'air.Baseline')
        event = {'format': ENGINE, 'peer': request['peer'], 'key_id': request['key_id'],
            'audience': request['audience'], 'aggregate': manifest['package_id'], 'namespace': source['scope'],
            'sequence': sequence, 'published_at': current.isoformat().replace('+00:00', 'Z'),
            'expires_at': request['expires_at'], 'status': 'REVOKED' if reasons else 'PUBLISHED',
            'manifest': {'baseline': manifest['baseline'], 'exports': manifest['exports'],
                         'profiles': baseline['body']['profiles']}}
        envelope = {'event': event, 'signature': base64.b64encode(signing.sign(rfc8785.dumps(event))).decode()}
        from air.federation import IMPORT
        check_schema(envelope, IMPORT)
        result = store._record_once(conn, command, 'federation_outbox', source['scope'], principal['subject'],
                                    {'request': request, 'envelope': envelope, 'source_instance': settings.instance_id})
    return {'outbox': reference(result['record']), 'envelope': envelope, 'created': result['created'], 'network_sent': False}


def write_envelope(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    protect_directory(directory)
    path = directory / 'checkpoint.json'
    write_private(path, result['envelope'])
    return {'outbox': result['outbox'], 'created': result['created'], 'file': str(path), 'network_sent': False}
