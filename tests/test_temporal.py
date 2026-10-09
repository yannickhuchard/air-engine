from copy import deepcopy

import pytest
from sqlalchemy import update

from air.access import AccessPolicy, Forbidden
from air.foundation import InvalidModel
from air.storage import revisions
from air.temporal import reconstruct

READER = {'subject': 'reader', 'role': 'reader'}


def history(store, example):
    first = deepcopy(example)
    first['meta']['validity'] = {'start': '2026-01-01T00:00:00Z', 'end': None}
    second = deepcopy(first)
    second['meta'].update(revision=2, name='Correction received later')
    second['meta']['validity']['start'] = '2026-02-01T00:00:00Z'
    # A client's old recorded_at must never forge earlier registry knowledge.
    second['meta']['recorded_at'] = first['meta']['recorded_at']
    for obj, at in [(first, '2026-01-02T00:00:00Z'), (second, '2026-03-01T00:00:00Z')]:
        store.put(obj, 'fixture')
        with store.write() as conn:
            conn.execute(update(revisions).where(revisions.c.id == obj['meta']['id'],
                         revisions.c.revision == obj['meta']['revision']).values(stored_at=at))
    return {'ids': [first['meta']['id']], 'known_at': '2026-02-15T00:00:00Z',
            'valid_at': '2026-02-10T00:00:00Z'}


def test_late_correction_and_independent_time_axes(store, example):
    req = history(store, example)
    def read(): return reconstruct(store, READER, AccessPolicy(), req)
    original = read()
    assert original['objects'][0]['object']['meta']['revision'] == 1
    req['known_at'] = '2026-03-01T00:00:00Z'
    assert read()['objects'][0]['object']['meta']['revision'] == 2
    req['valid_at'] = '2026-01-31T23:59:59Z'
    assert read()['objects'][0]['object']['meta']['revision'] == 1
    assert store.get(example['meta']['id'], 1)['object'] == original['objects'][0]['object']
    req['known_at'] = '2026-01-01T00:00:00Z'
    assert read()['unavailable_ids'] == req['ids']
    assert not read()['closed_baseline']


def test_current_authority_and_bounded_history(store, example, monkeypatch):
    req = history(store, example)
    with pytest.raises(Forbidden):
        reconstruct(store, READER, AccessPolicy({'version': 'removed', 'subjects': {}}), req)
    monkeypatch.setattr('air.temporal.MAX_REVISIONS', 1)
    with pytest.raises(InvalidModel, match='budget'):
        reconstruct(store, READER, AccessPolicy(), req)


def test_exclusive_end_and_determinism(store, example):
    example['meta']['validity'] = {'start': '2026-01-01T00:00:00Z', 'end': '2026-02-01T00:00:00Z'}
    store.put(example, 'fixture')
    request = {'ids': [example['meta']['id']], 'known_at': '2099-01-01T00:00:00Z',
               'valid_at': '2026-02-01T00:00:00Z'}
    assert reconstruct(store, READER, AccessPolicy(), request)['objects'] == []
    request['valid_at'] = '2026-01-31T23:59:59Z'
    a = reconstruct(store, READER, AccessPolicy(), request)
    assert len(a['objects']) == 1 and a == reconstruct(store, READER, AccessPolicy(), request)


def test_http_mcp_parity(store, example, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.config import Settings
    from air.mcp import PROTOCOL
    request = history(store, example)
    token = store.create_token('reader', 'reader')
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False),
                    base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/temporal/reconstruct', json=request, headers=headers)
        assert response.status_code == 200
        rpc = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_reconstruct_temporal', 'arguments': request}}, headers={**headers,
            'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()
        assert rpc['result']['structuredContent'] == response.json()
        store.revoke_token(token['token_id'])
        assert client.post('/v1/temporal/reconstruct', json=request, headers=headers).status_code == 401
