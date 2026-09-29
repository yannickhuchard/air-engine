from copy import deepcopy
import json
import pytest
from air.access import AccessPolicy, Forbidden
from air.audience import compile_view
from air.config import Settings
from air.core import AUDIENCE_PROFILE, KNOWLEDGE_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.portability import export_registry, import_registry
from air.storage import Store, Conflict
from test_business import setup_business


def prepare(store, tmp_path):
    settings, user, token, request, business, runtime, original, plan = setup_business(store, tmp_path)
    stakeholder = next(o for o in business if o['meta']['type'] == 'air.Stakeholder')
    concern = next(o for o in business if o['meta']['type'] == 'air.Concern')
    meta = deepcopy(concern['meta']);meta.update(id='urn:asteria:viewpoint:sav', type='air.Viewpoint', name='Vue métier SAV')
    viewpoint = {'meta': meta, 'body': {'audience': [exact(stakeholder)], 'concerns': [exact(concern)],
        'selection': {'binding': 'air.selector/0.19', 'types': ['air.Goal', 'air.BusinessService'], 'objects': []},
        'presentation': {'format': 'air.audience-html/0.19', 'title': 'Décision SAV', 'sections': [{'id': 'outcomes', 'heading': 'Objectifs', 'types': ['air.Goal']}, {'id': 'service', 'heading': 'Services', 'types': ['air.BusinessService']}]},
        'disclosure_policy': 'Dossier interne ; mêmes droits de namespace'}}
    store.put(viewpoint, 'fixture')
    objects = original + runtime + business + [viewpoint]
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta']);meta['id'] = 'urn:asteria:audience-baseline:sav'
    base = store.create_baseline({'meta': meta, 'profile': AUDIENCE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    request = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}, 'viewpoint': {**exact(viewpoint), 'digest': digest(viewpoint)}}
    return user, request, viewpoint, objects


def test_audience_selection_mapping_and_replay(store, tmp_path):
    user, request, viewpoint, objects = prepare(store, tmp_path)
    result = compile_view(store, user, AccessPolicy(), request)
    assert result == compile_view(store, user, AccessPolicy(), request)
    selected = [o for o in objects if o['meta']['type'] in ('air.Goal', 'air.BusinessService')]
    assert result['objects_selected'] == 2 and result['objects_excluded'] == len(objects) - 2
    assert {m['object']['id'] for m in result['source_mapping']} == {o['meta']['id'] for o in selected}
    assert all(m['selector'][1:] in result['content'] for m in result['source_mapping'])
    assert len(result['context_mapping']) == 4
    assert all(m['selector'][1:] in result['content'] for m in result['context_mapping'])
    assert not result['authorization_granted'] and not result['normative_view_persisted']
    assert not result['live_connection'] and not result['credentials_embedded']
    assert not validate_graph(objects, KNOWLEDGE_PROFILE)['valid']
    assert validate_graph(objects, AUDIENCE_PROFILE)['valid']
    linked = deepcopy(objects)
    next(o for o in linked if o['meta']['type'] == 'air.Concern')['body']['addressed_by'] = [exact(viewpoint)]
    assert validate_graph(linked, AUDIENCE_PROFILE)['valid']


def test_audience_exact_context_and_access(store, tmp_path):
    user, request, viewpoint, objects = prepare(store, tmp_path)
    denied = AccessPolicy({'version': 'deny', 'subjects': {}})
    with pytest.raises(Forbidden): compile_view(store, user, denied, request)
    changed = deepcopy(request);changed['viewpoint']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(Conflict): compile_view(store, user, AccessPolicy(), changed)
    changed = deepcopy(request);changed['viewpoint']['id'] = 'urn:absent:viewpoint'
    with pytest.raises(InvalidModel): compile_view(store, user, AccessPolicy(), changed)


def test_viewpoint_schema_order_and_closure(store, tmp_path):
    user, request, viewpoint, objects = prepare(store, tmp_path)
    equivalent = deepcopy(viewpoint);equivalent['body']['selection']['types'].reverse()
    assert canonical(equivalent) == canonical(viewpoint)
    reordered = deepcopy(viewpoint);reordered['body']['presentation']['sections'].reverse()
    assert digest(reordered) != digest(viewpoint)
    for field, value in [('types', []), ('objects', [{'id': 'urn:missing:object', 'revision': 1}])]:
        changed = deepcopy(viewpoint);changed['body']['selection'][field] = value
        assert not validate_graph([o for o in objects if o is not viewpoint] + [changed], AUDIENCE_PROFILE)['valid']
    wrong = deepcopy(viewpoint);wrong['body']['audience'] = [exact(next(o for o in objects if o['meta']['type'] == 'air.Goal'))]
    assert not validate_graph([o for o in objects if o is not viewpoint] + [wrong], AUDIENCE_PROFILE)['valid']
    injected = deepcopy(viewpoint);injected['body']['selection']['sql'] = 'SELECT * FROM objects'
    assert not validate(injected)['valid']


def test_audience_output_is_escaped_and_fields_unchanged(store, tmp_path):
    user, request, viewpoint, objects = prepare(store, tmp_path)
    hostile = deepcopy(viewpoint);hostile['meta']['revision'] = 2
    hostile['body']['presentation']['title'] = '<script>window.bad=true</script>'
    hostile['body']['selection']['objects'] = [exact(next(o for o in objects if o['meta']['type'] == 'air.Metric'))]
    store.put(hostile, 'fixture')
    old = store.export_baseline(request['baseline'])
    meta = deepcopy(old['baseline']['meta']);meta['revision'] = 2
    base = store.create_baseline({'meta': meta, 'profile': AUDIENCE_PROFILE, 'members': [exact(o) for o in objects if o is not viewpoint] + [exact(hostile)], 'parent_baselines': [exact(old['baseline'])]}, 'fixture')
    current = {'baseline': {**exact(base['baseline']), 'digest': base['digest']}, 'viewpoint': {**exact(hostile), 'digest': digest(hostile)}}
    result = compile_view(store, user, AccessPolicy(), current)
    assert '<script>' not in result['content'] and '&lt;script&gt;' in result['content']
    assert result['objects_selected'] == 3 and 'Autres objets sélectionnés' in result['content']
    assert 'Content-Security-Policy' in result['content']
    assert compile_view(store, user, AccessPolicy(), request)['objects_selected'] == 2


def test_audience_transfer_preserves_output(store, tmp_path):
    user, request, viewpoint, objects = prepare(store, tmp_path)
    result = compile_view(store, user, AccessPolicy(), request)
    bundle = tmp_path / 'audience-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'restored.db').as_posix();import_registry(bundle, url)
    target = Store(url)
    try: assert compile_view(target, user, AccessPolicy(), request) == result
    finally: target.engine.dispose()


def test_audience_http_and_mcp_use_same_compiler(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    user, request, viewpoint, objects = prepare(store, tmp_path)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    token = store.create_token(user['subject'], 'reader')
    auth = {'Authorization': 'Bearer ' + token['access_token']}
    expected = compile_view(store, user, AccessPolicy(), request)
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        assert client.post('/v1/audience-views', json=request).status_code == 401
        response = client.post('/v1/audience-views', json=request, headers=auth)
        assert response.status_code == 200 and response.json() == expected
        response = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_compile_audience_view', 'arguments': request}}, headers={**auth, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
        assert response.status_code == 200 and response.json()['result']['structuredContent'] == expected


@pytest.mark.parametrize('command', ['view', 'workbench', 'audience-view'])
def test_cli_html_preserves_exact_generated_bytes(tmp_path, monkeypatch, command):
    import io
    import hashlib
    from air import cli
    content = '<!doctype html>\n<title>Équipe Astéria</title>\n<p>Fins de ligne conservées.</p>\n'
    result = {'content': content, 'content_digest': 'sha256:' + hashlib.sha256(content.encode()).hexdigest()}
    class Opener:
        def open(self, request, timeout): return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr(cli, 'client_transport', lambda *args: ('http://127.0.0.1', Opener()))
    (tmp_path / 'credentials.json').write_text(json.dumps({'access_token': 'fictional-test-token'}), encoding='utf-8')
    request = tmp_path / 'request.json';request.write_text('{}', encoding='utf-8')
    output = tmp_path / 'view.html'
    assert cli.main(['--home', str(tmp_path), command, str(request), '--output', str(output)]) == 0
    assert output.read_bytes() == content.encode('utf-8')
