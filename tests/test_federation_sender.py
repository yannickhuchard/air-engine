from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

import pytest

pytest.importorskip('cryptography')

from air import federation as fed
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.federation_sender import keygen, export_checkpoint, write_envelope
from air.foundation import InvalidModel
from air.packages import revoke_package
from air.storage import Conflict, Store
from test_construction import construction
from test_packages import context, publish


@pytest.fixture
def sending(store, construction, tmp_path):
    owner, policy, proposal = context(store, construction)
    published = publish(store, owner, policy, proposal)
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='sender')
    token = store.create_token(owner['subject'], owner['role'])
    user = store.authenticate(token['access_token'], include_binding=True)
    user['authorization']['instance_id'] = settings.instance_id
    key = keygen(tmp_path / 'keys')
    request = {'idempotency_key': 'export-one', 'publication': published['publication'],
               'peer': 'urn:peer:sender', 'key_id': 'key1', 'audience': 'receiver',
               'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')}
    return settings, policy, user, key, request, token


def test_two_independent_registries_publication_retry_restart_and_withdrawal(store, sending, tmp_path):
    settings, policy, user, key, request, _ = sending
    signed = export_checkpoint(store, user, policy, settings, request, key['key_file'])
    assert signed['created'] and not signed['network_sent']
    assert signed['envelope']['event']['manifest']['exports']
    reopened = Store(settings.database_url)
    try:
        retry = export_checkpoint(reopened, user, policy, settings, request, key['key_file'])
        assert not retry['created'] and retry['envelope'] == signed['envelope']
    finally: reopened.engine.dispose()
    out = write_envelope(signed, tmp_path / 'delivery')
    message = json.loads((tmp_path / 'delivery' / 'checkpoint.json').read_text(encoding='utf-8'))
    assert out['network_sent'] is False and message == signed['envelope']
    receiver_home = tmp_path / 'receiver'; receiver_home.mkdir()
    receiver = Store('sqlite:///' + (receiver_home / 'air.db').as_posix()); receiver.migrate()
    try:
        target = Settings(receiver_home, receiver.engine.url.render_as_string(hide_password=False), instance_id='receiver')
        recipient_policy = AccessPolicy({'version': 'receiver', 'subjects': {
            'recipient': {'read': ['*'], 'write': ['*']}, 'urn:peer:publisher': {'publish': ['*']}}})
        (receiver_home / 'access-policy.json').write_text(json.dumps(recipient_policy.document), encoding='utf-8')
        token = receiver.create_token('recipient', 'editor')
        recipient = receiver.authenticate(token['access_token'], include_binding=True)
        recipient['authorization']['instance_id'] = target.instance_id
        now = datetime.now(timezone.utc)
        fed.register_peer(receiver, target, {'peer': request['peer'], 'key_id': 'key1',
            'subject': 'urn:peer:publisher', 'public_key': key['public_key'], 'namespaces': ['*'],
            'not_before': (now - timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
            'expires_at': (now + timedelta(days=1)).isoformat().replace('+00:00', 'Z'), 'max_age_seconds': 3600})
        received = fed.ingest(receiver, recipient, recipient_policy, target, message)
        assert received['head_sequence'] == 1
        revoke_package(store, user, policy, {'publication': request['publication'], 'rationale': 'design withdrawn'})
        with pytest.raises(InvalidModel, match='withdrawal'):
            export_checkpoint(store, user, policy, settings, request, key['key_file'])
        withdrawn = {**request, 'idempotency_key': 'withdraw-two'}
        second = export_checkpoint(store, user, policy, settings, withdrawn, key['key_file'])
        assert second['envelope']['event']['status'] == 'REVOKED'
        fed.ingest(receiver, recipient, recipient_policy, target, second['envelope'])
        stale = fed.ingest(receiver, recipient, recipient_policy, target, message)
        assert not stale['head_changed'] and stale['head_sequence'] == 2
        query = {k: message['event'][k] for k in ('peer', 'aggregate', 'namespace')}
        assert not fed.read(receiver, recipient, recipient_policy, target, query)['new_use_allowed']
        assert receiver.counts()['revisions'] == 0
    finally: receiver.engine.dispose()


def test_key_identity_idempotence_owner_and_current_token(store, sending, tmp_path):
    settings, policy, user, key, request, token = sending
    export_checkpoint(store, user, policy, settings, request, key['key_file'])
    other_key = keygen(tmp_path / 'other-keys')
    with pytest.raises(Conflict):
        export_checkpoint(store, user, policy, settings, request, other_key['key_file'])
    changed = {**request, 'audience': 'another'}
    with pytest.raises(Conflict): export_checkpoint(store, user, policy, settings, changed, key['key_file'])
    store.revoke_token(token['token_id'])
    with pytest.raises(Forbidden): export_checkpoint(store, user, policy, settings, request, key['key_file'])


def test_failure_before_commit_does_not_consume_outbox_sequence(store, sending, monkeypatch):
    settings, policy, user, key, request, _ = sending
    original = store._record_once
    def fail(conn, rid, kind, scope, actor, payload):
        if kind == 'federation_outbox': raise RuntimeError('Synthetic interruption before commit')
        return original(conn, rid, kind, scope, actor, payload)
    monkeypatch.setattr(store, '_record_once', fail)
    with pytest.raises(RuntimeError): export_checkpoint(store, user, policy, settings, request, key['key_file'])
    monkeypatch.setattr(store, '_record_once', original)
    result = export_checkpoint(store, user, policy, settings, request, key['key_file'])
    assert result['envelope']['event']['sequence'] == 1


def test_concurrent_repetition_creates_one_outbox_event(store, sending):
    settings, policy, user, key, request, _ = sending
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: export_checkpoint(store, user, policy, settings, request, key['key_file']), range(2)))
    assert sum(r['created'] for r in results) == 1
    assert results[0]['envelope'] == results[1]['envelope']


def test_other_publisher_cannot_sign_another_owners_publication(store, sending):
    settings, policy, _, key, request, _ = sending
    altered = {'version': 'two-publishers', 'subjects': {**policy.document['subjects'],
               'another': {'read': ['*'], 'publish': ['*']}}}
    policy = AccessPolicy(altered)
    (settings.home / 'access-policy.json').write_text(json.dumps(altered), encoding='utf-8')
    token = store.create_token('another', 'editor')
    user = store.authenticate(token['access_token'], include_binding=True)
    user['authorization']['instance_id'] = settings.instance_id
    with pytest.raises(Forbidden, match='owner'):
        export_checkpoint(store, user, policy, settings, request, key['key_file'])


def test_full_outbox_allows_exact_retry_but_no_additional_event(store, sending, monkeypatch):
    settings, policy, user, key, request, _ = sending
    monkeypatch.setattr('air.federation_sender.MAX_OUTBOX', 1)
    first = export_checkpoint(store, user, policy, settings, request, key['key_file'])
    assert not export_checkpoint(store, user, policy, settings, request, key['key_file'])['created']
    with pytest.raises(InvalidModel, match='budget'):
        export_checkpoint(store, user, policy, settings, {**request, 'idempotency_key': 'second'}, key['key_file'])
    assert export_checkpoint(store, user, policy, settings, request, key['key_file'])['outbox'] == first['outbox']
