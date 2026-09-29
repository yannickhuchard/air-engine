from copy import deepcopy
from html.parser import HTMLParser
import base64
import hashlib
import json
import pytest
from air.access import AccessPolicy, Forbidden
from air.core import COLLABORATION_PROFILE
from air.foundation import exact, InvalidModel
from air.storage import Conflict
from air.workbench import compile_workbench
from test_collaboration import setup_collaboration


class Document(HTMLParser):
    def __init__(self, content):
        super().__init__();self.scripts = [];self.active = None;self.csp = None;self.styles = []
        self.feed(content)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script': self.active = {'id': attrs.get('id'), 'text': ''};self.scripts.append(self.active)
        if tag == 'style': self.active = {'id': 'style', 'text': ''};self.styles.append(self.active)
        if tag == 'meta' and attrs.get('http-equiv') == 'Content-Security-Policy': self.csp = attrs['content']
    def handle_data(self, data):
        if self.active is not None: self.active['text'] += data
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.active = None


def setup_workbench(store, tmp_path, hostile=False):
    settings, principal, token, contribution, decision, original, runtime, plan = setup_collaboration(store, tmp_path)
    if hostile:
        contribution['meta']['name'] = '</title><img src="https://example.invalid/leak" onerror="window.airInjected=true">'
        contribution['body']['message'] = '</script><script>window.airInjected=true</script>'
    store.put_bundle([contribution, decision], 'fixture')
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta'])
    meta.update(id='urn:asteria:workbench:test', name='Architecture workbench')
    baseline = store.create_baseline({'meta': meta, 'profile': COLLABORATION_PROFILE,
        'members': [exact(o) for o in original + runtime + [contribution, decision]], 'parent_baselines': []}, 'fixture')
    return settings, principal, token, {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}}


def test_workbench_pure_replay_reference_mapping_and_no_credentials(store, tmp_path):
    settings, principal, token, request = setup_workbench(store, tmp_path)
    before = store.counts(), store.audit_log()
    result = compile_workbench(store, principal, AccessPolicy(), settings, request)
    assert result == compile_workbench(store, principal, AccessPolicy(), settings, request)
    assert (store.counts(), store.audit_log()) == before
    assert result['objects'] == 29 and len(result['source_mapping']) == 29
    assert not result['register_modified'] and not result['live_connection'] and not result['credentials_embedded']
    assert token['access_token'] not in result['content'] and token['token_id'] not in result['content']
    assert result['content_digest'] == 'sha256:' + hashlib.sha256(result['content'].encode()).hexdigest()
    parsed = Document(result['content']);data = json.loads(next(s['text'] for s in parsed.scripts if s['id'] == 'air-data'))
    refs = {(o['meta']['id'], o['meta']['revision']) for o in data['objects']}
    assert all((l['to']['id'], l['to']['revision']) in refs for l in data['links'])


def test_workbench_hostile_text_is_inert_and_script_is_hash_pinned(store, tmp_path):
    settings, principal, token, request = setup_workbench(store, tmp_path, hostile=True)
    result = compile_workbench(store, principal, AccessPolicy(), settings, request)
    parsed = Document(result['content'])
    assert len(parsed.scripts) == 2 and len(parsed.styles) == 1
    executable = next(s['text'] for s in parsed.scripts if s['id'] is None)
    pin = base64.b64encode(hashlib.sha256(executable.encode()).digest()).decode()
    assert "script-src 'sha256-" + pin + "'" in parsed.csp
    assert "connect-src 'none'" in parsed.csp and "form-action 'none'" in parsed.csp
    data = json.loads(next(s['text'] for s in parsed.scripts if s['id'] == 'air-data'))
    assert any('</script>' in o['body'].get('message', '') for o in data['objects'])
    assert '<img src="https://example.invalid/leak"' not in result['content']


def test_workbench_access_closure_reader_mode_and_wrong_digest(store, tmp_path):
    settings, principal, token, request = setup_workbench(store, tmp_path)
    restricted = AccessPolicy({'version': 'limited', 'subjects': {'architect': {'read': ['asteria.sav']}}})
    with pytest.raises(Forbidden): compile_workbench(store, principal, restricted, settings, request)
    reader = dict(principal, role='reader')
    result = compile_workbench(store, reader, AccessPolicy(), settings, request)
    parsed = Document(result['content']);data = json.loads(next(s['text'] for s in parsed.scripts if s['id'] == 'air-data'))
    assert data['writable_namespaces'] == []
    wrong = deepcopy(request);wrong['baseline']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): compile_workbench(store, principal, AccessPolicy(), settings, wrong)
    with pytest.raises(InvalidModel): compile_workbench(store, principal, AccessPolicy(), settings, {**request, 'token': 'forbidden'})


def test_workbench_http_and_mcp_share_generator(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, principal, token, request = setup_workbench(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/workbench', headers=headers, json=request)
        assert response.status_code == 200
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_compile_workbench', 'arguments': request}},
            headers={**headers, 'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()['result']
        assert not result['isError'] and result['structuredContent'] == response.json()
        assert client.post('/v1/workbench', json=request).status_code == 401
