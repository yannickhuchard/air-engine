import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from air.api import create_app
from air.config import Settings
from air.operations import State, read_document_bytes
from air.parsing import MAX_BYTES


@pytest.mark.parametrize('name,value', [
    ('AIR_MAX_INFLIGHT_PER_SUBJECT', '0'), ('AIR_MAX_INFLIGHT_PER_SUBJECT', '1025'),
    ('AIR_MAX_INFLIGHT_PER_SUBJECT', '1.5'), ('AIR_BODY_TIMEOUT_SECONDS', '0'),
    ('AIR_BODY_TIMEOUT_SECONDS', '301'), ('AIR_BODY_TIMEOUT_SECONDS', 'nan'),
    ('AIR_BODY_TIMEOUT_SECONDS', 'inf'), ('AIR_BODY_TIMEOUT_SECONDS', 'bad')])
def test_invalid_budgets_refuse_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError): State()


def test_identity_limit_is_shared_by_tokens_and_mcp_but_not_other_users(store, tmp_path, example, monkeypatch):
    monkeypatch.setenv('AIR_MAX_INFLIGHT_PER_SUBJECT', '1')
    first, second = [store.create_token('PRIVATE_SUBJECT', 'editor')['access_token'] for _ in range(2)]
    other = store.create_token('other', 'editor')['access_token']
    admin = store.create_token('operator', 'admin')['access_token']
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        data = json.dumps(example).encode()
        async def body():
            yield data[:2]
            entered.set()
            await release.wait()
            yield data[2:]
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1') as client:
                headers = {'Authorization':'Bearer '+first, 'Content-Type':'application/json'}
                task = asyncio.create_task(client.post('/v1/drafts', content=body(), headers=headers))
                try:
                    await asyncio.wait_for(entered.wait(), 5)
                    same = {'Authorization':'Bearer '+second}
                    denied = await client.get('/v1/capabilities', headers=same)
                    assert denied.status_code == 429 and denied.json()['detail']['code'] == 'AIR_SUBJECT_BUSY'
                    assert denied.headers['retry-after'] == '1'
                    assert (await client.post('/mcp', headers=same, json={})).status_code == 429
                    assert (await client.get('/v1/capabilities', headers={'Authorization':'Bearer '+other})).status_code == 200
                    metrics = await client.get('/v1/operations', headers={'Authorization':'Bearer '+admin})
                    assert metrics.status_code == 200
                    assert metrics.json()['identity_admission']['rejected_busy'] == 2
                    for secret in ('PRIVATE_SUBJECT', first, second, other, admin): assert secret not in metrics.text
                    assert store.counts()['revisions'] == 0
                finally: release.set()
                assert (await task).status_code == 201
                assert (await client.get('/v1/capabilities', headers=headers)).status_code == 200
        assert app.state.operations.snapshot()['identity_admission']['active_subjects'] == 0
        assert app.state.operations.subjects == {}
    asyncio.run(scenario())


@pytest.mark.parametrize('path', ['/v1/drafts', '/mcp'])
def test_slow_body_times_out_before_mutation_and_releases_identity(store, tmp_path, example, monkeypatch, path):
    monkeypatch.setenv('AIR_BODY_TIMEOUT_SECONDS', '1')
    token = store.create_token('slow', 'admin')['access_token']
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    async def scenario():
        async def trickle():
            # Every chunk arrives in less than one second; the *total* deadline still expires.
            while True:
                yield b' '
                await asyncio.sleep(.2)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1') as client:
                headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json',
                           'Accept':'application/json, text/event-stream'}
                response = await client.post(path, headers=headers, content=trickle())
                assert response.status_code == 408 and response.json() == {'detail':{'code':'AIR_INPUT_TIMEOUT'}}
                assert token not in response.text
                assert store.counts()['revisions'] == 0
                assert app.state.operations.snapshot()['input_limits']['rejections']['timeout'] == 1
                assert app.state.operations.subjects == {}
                assert (await client.post('/v1/drafts', headers=headers, json=example)).status_code == 201
    asyncio.run(scenario())


def test_cancellation_releases_global_and_identity_capacity(store, tmp_path):
    token = store.create_token('cancelled', 'admin')['access_token']
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    async def scenario():
        entered = asyncio.Event()
        async def body():
            entered.set()
            await asyncio.Event().wait()
            yield b'{}'
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1') as client:
                headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json'}
                task = asyncio.create_task(client.post('/v1/drafts', headers=headers, content=body()))
                await asyncio.wait_for(entered.wait(), 5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError): await task
                state = app.state.operations.snapshot()
                assert state['active_requests'] == state['identity_admission']['active_subjects'] == 0
                assert store.counts()['revisions'] == 0
                assert (await client.get('/v1/capabilities', headers=headers)).status_code == 200
    asyncio.run(scenario())


def test_identity_slot_stays_occupied_until_response_is_sent(store, tmp_path, monkeypatch):
    monkeypatch.setenv('AIR_MAX_INFLIGHT_PER_SUBJECT', '1')
    token = store.create_token('slow-reader', 'reader')['access_token']
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
        async def send(message):
            if message['type'] == 'http.response.body':
                entered.set()
                await release.wait()
        scope = {'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'GET',
                 'scheme':'http','path':'/v1/capabilities','query_string':b'',
                 'headers':[(b'host',b'127.0.0.1'),(b'authorization',('Bearer '+token).encode())]}
        async with app.router.lifespan_context(app):
            task = asyncio.create_task(app(scope,receive,send))
            try:
                await asyncio.wait_for(entered.wait(),5)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://127.0.0.1') as client:
                    response = await client.get('/v1/capabilities',headers={'Authorization':'Bearer '+token})
                    assert response.status_code == 429
            finally:
                release.set()
                await task
        assert app.state.operations.subjects == {}
    asyncio.run(scenario())


@pytest.mark.parametrize('headers,chunks,status,reason', [
    ([(b'content-length', str(MAX_BYTES+1).encode())], [], 413, 'too_large'),
    ([(b'content-length', b'-1')], [], 400, 'invalid_length'),
    ([(b'content-length', b'2'), (b'content-length', b'2')], [], 400, 'invalid_length'),
    ([(b'content-length', b'1')], [b'{}'], 400, 'invalid_length'),
    ([], [b'x'*MAX_BYTES, b'x'], 413, 'too_large'),
])
def test_stream_bounds_and_lengths_are_enforced(headers, chunks, status, reason):
    state = State()
    async def scenario():
        messages = [{'type':'http.request', 'body':chunk, 'more_body':i < len(chunks)-1} for i,chunk in enumerate(chunks)]
        async def receive():
            assert messages, 'Invalid header must be rejected before reading the body'
            return messages.pop(0)
        request = Request({'type':'http', 'headers':headers}, receive)
        with pytest.raises(HTTPException) as caught: await read_document_bytes(request, state)
        assert caught.value.status_code == status
        assert state.snapshot()['input_limits']['rejections'][reason] == 1
    asyncio.run(scenario())


def test_disconnect_is_not_a_partial_document():
    async def scenario():
        state = State()
        async def receive(): return {'type':'http.disconnect'}
        with pytest.raises(HTTPException) as caught:
            await read_document_bytes(Request({'type':'http','headers':[]},receive), state)
        assert caught.value.status_code == 400
        assert state.snapshot()['input_limits']['rejections']['disconnected'] == 1
    asyncio.run(scenario())
