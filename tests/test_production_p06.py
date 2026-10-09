"""Operational boundaries: no waiting queue, no content in metrics, live authority."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from air.api import create_app
from air.config import Settings
from air.operations import AdmissionGuard, State


def test_overload_rejects_before_processing_and_probes_remain_available():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls, responses = [], []
        async def downstream(scope, receive, send):
            calls.append(scope['path'])
            if scope['path'] == '/held':
                entered.set()
                await release.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok'})
        async def receive(): return {'type': 'http.request', 'body': b''}
        async def send(message): responses.append(message)
        state = State(1)
        guard = AdmissionGuard(downstream, state)
        async def request(path):
            await guard({'type': 'http', 'path': path, 'query_string': b'SECRET',
                         'headers': [(b'authorization', b'Bearer PRIVATE')]}, receive, send)
        first = asyncio.create_task(request('/held'))
        await entered.wait()
        await request('/private-identifier')
        assert calls == ['/held']
        assert responses[0]['status'] == 503
        assert (b'retry-after', b'1') in responses[0]['headers']
        await request('/ready')
        await request('/health')
        assert calls == ['/held', '/ready', '/health']
        release.set()
        await first
        await request('/after')
        result = state.snapshot()
        assert (result['accepted_requests'], result['finished_requests'], result['active_requests'], result['rejected_busy']) == (2, 2, 0, 1)
        assert result['http_status_classes']['2xx'] == 2
        assert all(v == 2 for v in list(result['duration_seconds']['cumulative_buckets'].values())[-1:])
        for secret in ('SECRET', 'PRIVATE', '/private-identifier', '/held'):
            assert secret not in json.dumps(result)
    asyncio.run(scenario())


@pytest.mark.parametrize('error', [RuntimeError, asyncio.CancelledError])
def test_failure_or_cancellation_releases_the_slot(error):
    async def scenario():
        async def broken(*args): raise error()
        state = State(1)
        with pytest.raises(error):
            await AdmissionGuard(broken, state)({'type': 'http', 'path': '/'}, None, None)
        assert state.snapshot()['active_requests'] == 0
        assert state.snapshot()['http_status_classes']['5xx'] == 1
        assert state.enter()
    asyncio.run(scenario())


@pytest.mark.parametrize('value', ['0', '-1', '1025', 'bad', '1.5'])
def test_invalid_capacity_fails_startup(monkeypatch, value):
    monkeypatch.setenv('AIR_MAX_INFLIGHT', value)
    with pytest.raises(ValueError): State()


def test_readiness_checks_policy_storage_and_worker_without_error_text(store, tmp_path, monkeypatch):
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    with TestClient(app) as client:
        assert client.get('/ready').json() == {'status': 'ready'}
        app.state.worker_status = 'RETRYING'
        assert client.get('/ready').status_code == 503
        app.state.worker_status = 'DISABLED'
        policy = tmp_path / 'access-policy.json'
        policy.write_text('private-bad-policy')
        response = client.get('/ready')
        assert response.status_code == 503 and response.json() == {'status': 'not_ready'}
        policy.write_text('{"version":"1","subjects":{}}')
        def unavailable(): raise RuntimeError('password=PRIVATE_STORAGE')
        monkeypatch.setattr(app.state.store, 'check_version', unavailable)
        response = client.get('/ready')
        assert response.status_code == 503 and 'PRIVATE' not in response.text


def test_metrics_require_current_admin_and_explicit_operate_when_policy_exists(store, tmp_path):
    headers = {role: {'Authorization': 'Bearer ' + store.create_token(role, role)['access_token']}
               for role in ('reader', 'editor', 'admin')}
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    with TestClient(app) as client:
        assert client.get('/v1/operations').status_code == 401
        for role in ('reader', 'editor'):
            assert client.get('/v1/operations', headers=headers[role]).status_code == 403
        assert client.get('/v1/operations', headers=headers['admin']).status_code == 200
        document = {'version': '1', 'subjects': {'admin': {'read': ['*'], 'write': ['*']}}}
        path = tmp_path / 'access-policy.json'
        path.write_text(json.dumps(document))
        assert client.get('/v1/operations', headers=headers['admin']).status_code == 403
        document['subjects']['admin']['operate'] = ['air.system']
        path.write_text(json.dumps(document))
        response = client.get('/v1/operations', headers=headers['admin'])
        assert response.status_code == 200
        assert response.json()['scope'] == 'PROCESS_LOCAL_HTTP'
        assert response.json()['http_status_classes']['4xx'] == 4
        document['subjects']['admin']['operate'] = []
        path.write_text(json.dumps(document))
        assert client.get('/v1/operations', headers=headers['admin']).status_code == 403
