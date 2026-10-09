from copy import deepcopy
import json

import pytest

from air import artifacts, connectors, runtime
from air.access import AccessPolicy, Forbidden
from air.foundation import InvalidModel
from test_runtime import setup_runtime


def captured(store, tmp_path, content=None, media='application/json'):
    settings, user, ingestion, token = setup_runtime(store, tmp_path)
    raw = content if content is not None else json.dumps({'observations': ingestion['observations']}).encode()
    stored = artifacts.put(store, user, AccessPolicy(), settings, {'idempotency_key': 'raw',
        'namespace': ingestion['observations'][0]['meta']['namespace'], 'media_type': media}, raw)
    request = {'adapter': connectors.ADAPTER, 'artifact': stored['artifact'],
               'source': ingestion['source'], 'idempotency_key': 'connector-import'}
    return settings, user, request, token


def test_preview_is_read_only_and_ingestion_pins_exact_source_bytes(store, tmp_path):
    settings, user, request, _ = captured(store, tmp_path)
    before = store.counts(), store.audit_log()
    report = connectors.preview(store, user, AccessPolicy(), request)
    assert (store.counts(), store.audit_log()) == before
    assert report == connectors.preview(store, user, AccessPolicy(), request)
    assert not report['measurement_authenticity_verified'] and not report['registry_written']
    command = report['prepared_ingestion']
    received = runtime.ingest(store, user, AccessPolicy(), settings, command)
    assert received['created'] and received['qualification'] == 'DRAFT'
    assert not runtime.ingest(store, user, AccessPolicy(), settings, command)['created']
    saved = store.get_record(received['ingestion']['id'])['payload']['request']
    assert saved['source_artifact'] == request['artifact'] and saved['connector'] == connectors.ADAPTER


def test_modified_mapping_is_rejected_before_any_write(store, tmp_path):
    settings, user, request, _ = captured(store, tmp_path)
    command = connectors.preview(store, user, AccessPolicy(), request)['prepared_ingestion']
    command['observations'][0]['meta']['name'] = 'Fabricated replacement'
    before = store.counts(), store.audit_log()
    with pytest.raises(InvalidModel, match='mapping'):
        runtime.ingest(store, user, AccessPolicy(), settings, command)
    assert (store.counts(), store.audit_log()) == before


@pytest.mark.parametrize('content', [b'{"observations":[],"run":"delete files"}',
                                     b'{"observations":[],"observations":[]}',
                                     b'!!python/object/apply:os.system ["whoami"]'])
def test_artifact_cannot_supply_instructions_or_executable_extensions(store, tmp_path, content):
    _, user, request, _ = captured(store, tmp_path, content)
    before = store.counts(), store.audit_log()
    with pytest.raises(ValueError): connectors.preview(store, user, AccessPolicy(), request)
    assert (store.counts(), store.audit_log()) == before


def test_read_preview_does_not_grant_write_or_new_visibility(store, tmp_path):
    settings, user, request, _ = captured(store, tmp_path)
    reader_token = store.create_token('reader', 'reader')
    reader = store.authenticate(reader_token['access_token'], True)
    reader['authorization']['instance_id'] = settings.instance_id
    command = connectors.preview(store, reader, AccessPolicy(), request)['prepared_ingestion']
    with pytest.raises(Forbidden): runtime.ingest(store, reader, AccessPolicy(), settings, command)
    with pytest.raises(Forbidden):
        connectors.preview(store, user, AccessPolicy({'version': 'revoked', 'subjects': {}}), request)


def test_mapping_descriptor_cannot_be_detached_from_artifact(store, tmp_path):
    settings, user, request, _ = captured(store, tmp_path)
    command = connectors.preview(store, user, AccessPolicy(), request)['prepared_ingestion']
    del command['source_artifact']
    with pytest.raises(InvalidModel): runtime.ingest(store, user, AccessPolicy(), settings, command)


def test_http_mcp_preview_parity(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, user, request, token = captured(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        direct = client.post('/v1/connectors/preview', json=request, headers=headers)
        assert direct.status_code == 200
        rpc = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_preview_connector', 'arguments': request}}, headers={**headers,
            'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()
        assert rpc['result']['structuredContent'] == direct.json()
