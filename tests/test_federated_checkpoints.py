import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
import rfc8785

pytest.importorskip('cryptography')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from air import federation as fed
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.foundation import InvalidModel
from air.storage import Conflict, Store


def iso(value): return value.isoformat().replace('+00:00', 'Z')


@pytest.fixture
def peer(store, tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(fed, 'clock', lambda: now)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='receiver')
    policy = AccessPolicy({'version': 'federation-test', 'subjects': {
        'receiver': {'read': ['synthetic.architecture'], 'write': ['synthetic.architecture']},
        'urn:peer:publisher': {'publish': ['synthetic.architecture']}}})
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    token = store.create_token('receiver', 'editor')
    user = store.authenticate(token['access_token'], include_binding=True)
    user['authorization']['instance_id'] = settings.instance_id
    private = Ed25519PrivateKey.generate()
    trust = {'peer': 'urn:peer:source', 'key_id': 'key1', 'subject': 'urn:peer:publisher',
        'public_key': base64.b64encode(private.public_key().public_bytes_raw()).decode(),
        'namespaces': ['synthetic.architecture'], 'not_before': iso(now - timedelta(days=1)),
        'expires_at': iso(now + timedelta(days=1)), 'max_age_seconds': 3600}
    fed.register_peer(store, settings, trust)
    def message(sequence=1, revision=None, status='PUBLISHED'):
        event = {'format': fed.ENGINE, 'peer': trust['peer'], 'key_id': 'key1', 'audience': 'receiver',
            'aggregate': 'urn:package:design', 'namespace': 'synthetic.architecture', 'sequence': sequence,
            'published_at': iso(now), 'expires_at': iso(now + timedelta(minutes=30)), 'status': status,
            'manifest': {'baseline': {'id': 'urn:remote:baseline', 'revision': revision or sequence,
                                     'digest': 'sha256:' + 'a' * 64}, 'exports': [], 'profiles': ['air.foundation/0.2']}}
        return sign(event)
    def sign(event):
        return {'event': event, 'signature': base64.b64encode(private.sign(rfc8785.dumps(event))).decode()}
    return settings, policy, user, message, sign, now, token


def test_reorder_duplicate_and_restart_do_not_regress_projection(store, peer):
    settings, policy, user, message, _, _, _ = peer
    first = message(3)
    result = fed.ingest(store, user, policy, settings, first)
    assert result['created'] and result['head_sequence'] == 3
    assert not fed.ingest(store, user, policy, settings, first)['created']
    stale = fed.ingest(store, user, policy, settings, message(1))
    assert stale['head_sequence'] == 3 and not stale['head_changed']
    reopened = Store(settings.database_url)
    try:
        read = fed.read(reopened, user, policy, settings, {k: first['event'][k] for k in ('peer', 'aggregate', 'namespace')})
        assert read['event']['sequence'] == 3 and read['new_use_allowed']
        assert not read['distributed_admission'] and store.counts()['revisions'] == 0
    finally: reopened.engine.dispose()


@pytest.mark.parametrize('fault', ['signature', 'audience', 'expired', 'future', 'namespace', 'revoked', 'authority', 'token'])
def test_invalid_or_unauthorized_checkpoint_never_enters_index(store, peer, tmp_path, fault):
    settings, policy, user, message, sign, now, token = peer
    request = message()
    if fault == 'signature': request['signature'] = base64.b64encode(b'0' * 64).decode()
    elif fault in ('audience', 'expired', 'future', 'namespace'):
        event = request['event']
        if fault == 'audience': event['audience'] = 'other-instance'
        elif fault == 'expired': event['expires_at'] = iso(now)
        elif fault == 'future': event['published_at'] = iso(now + timedelta(seconds=1))
        else: event['namespace'] = 'other.team'
        request = sign(event)
    elif fault == 'revoked': fed.revoke_peer(store, {'peer': request['event']['peer'], 'key_id': 'key1', 'rationale': 'test'})
    elif fault == 'authority':
        policy = AccessPolicy({'version': 'removed', 'subjects': {'receiver': {'write': ['synthetic.architecture']}}})
        (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    else: store.revoke_token(token['token_id'])
    with pytest.raises((InvalidModel, Forbidden)):
        fed.ingest(store, user, policy, settings, request)


def test_equivocation_regression_and_no_fallback_after_revocation(store, peer):
    settings, policy, user, message, sign, _, _ = peer
    fed.ingest(store, user, policy, settings, message(3))
    with pytest.raises(Conflict): fed.ingest(store, user, policy, settings, message(3, status='REVOKED'))
    with pytest.raises(Conflict): fed.ingest(store, user, policy, settings, message(4, revision=2))
    with pytest.raises(Conflict): fed.ingest(store, user, policy, settings, message(2, revision=4))
    changed = message(4)['event'];changed['manifest']['baseline'].update(revision=3, digest='sha256:' + 'b' * 64)
    with pytest.raises(Conflict): fed.ingest(store, user, policy, settings, sign(changed))
    revoked = message(4, status='REVOKED')
    fed.ingest(store, user, policy, settings, revoked)
    query = {k: revoked['event'][k] for k in ('peer', 'aggregate', 'namespace')}
    assert not fed.read(store, user, policy, settings, query)['new_use_allowed']
    fed.revoke_peer(store, {'peer': query['peer'], 'key_id': 'key1', 'rationale': 'test'})
    with pytest.raises(Forbidden): fed.read(store, user, policy, settings, query)


def test_receiver_binding_prevents_cross_instance_replay(store, peer, tmp_path):
    settings, policy, user, message, _, _, _ = peer
    other = Store('sqlite:///' + (tmp_path / 'independent.db').as_posix())
    other.migrate()
    try:
        # Another registry does not inherit the first registry's trust registration.
        with other.engine.connect() as conn:
            with pytest.raises(InvalidModel, match='not trusted'):
                fed.verify(other, conn, Settings(tmp_path, other.engine.url.render_as_string(hide_password=False),
                           instance_id='other'), policy, message())
    finally: other.engine.dispose()


def test_http_mcp_and_current_permissions(store, peer):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, policy, user, message, _, _, token = peer
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    payload = message()
    query = {k: payload['event'][k] for k in ('peer', 'aggregate', 'namespace')}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        received = client.post('/v1/federation/checkpoints', json=payload, headers=headers)
        assert received.status_code == 200 and received.json()['head_changed']
        direct = client.post('/v1/federation/read', json=query, headers=headers)
        rpc = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_read_checkpoint', 'arguments': query}}, headers={**headers,
            'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()
        assert rpc['result']['structuredContent'] == direct.json()
        store.revoke_token(token['token_id'])
        assert client.post('/v1/federation/read', json=query, headers=headers).status_code == 401
