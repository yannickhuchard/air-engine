"""Source fidelity, separation of revisions and safe offline delivery."""
import base64
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import PurePosixPath
import posixpath
from urllib.parse import urlsplit
import pytest
from air import deliverables
from air.core import digest, schema
from air.access import AccessPolicy, Forbidden
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def contents(report):
    return {f['path']: f['content'] for f in report['files']}


def test_model_export_preserves_objects_schemas_and_bytes(store, compiled):
    report, request, user = compiled
    model = json.loads(contents(report)['livrables/architecture-model.json'])
    exported = store.export_baseline(request['baselines'][0])
    assert model['snapshots'][0]['objects'] == sorted(exported['objects'], key=lambda o: (o['meta']['id'], o['meta']['revision']))
    assert model['snapshots'][0]['digest'] == exported['digest']
    for item in model['snapshots'][0]['object_digests']:
        source = next(o for o in exported['objects'] if o['meta']['id'] == item['id'])
        assert item['digest'] == digest(source)
    assert model['metamodel']['air.PhysicalTable'] == schema('air.PhysicalTable')
    assert model['schema_artifacts']
    for item in model['schema_artifacts']:
        raw = base64.b64decode(item['content'], validate=True)
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == item['manifest']['content_digest']
        assert len(raw) == item['manifest']['size']


class Links(HTMLParser):
    def __init__(self): super().__init__();self.targets = [];self.ids = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        if tag in ('a', 'script', 'link'):
            target = attrs.get('href', attrs.get('src'))
            if target: self.targets.append(target)


def test_every_topic_diagram_and_local_link_is_delivered(compiled):
    report, request, user = compiled
    files = contents(report);site = report['website']
    assert site['complete_topics'] and site['offline']
    dossier = site['dossiers'][0]
    assert dossier['topics'] == len(deliverables.CATALOGUE)
    root = 'livrables/site/' + str(PurePosixPath(dossier['path']).parent)
    for name, _ in deliverables.CATALOGUE:
        assert root + '/' + name + '.html' in files
        assert root + '/' + name + '.md' in files
    pages = {p: text for p, text in files.items() if p.startswith('livrables/site/') and p.endswith('.html')}
    assert sum('/diagram-' in p for p in pages) == site['diagrams']
    parsed = {}
    for path, text in pages.items():
        parsed[path] = Links();parsed[path].feed(text)
        assert "connect-src &#x27;self&#x27;" in text and "worker-src &#x27;self&#x27;" in text and 'https://cdn' not in text
    for path, links in parsed.items():
        for target in links.targets:
            parsed_target = urlsplit(target)
            file, fragment = parsed_target.path, parsed_target.fragment
            destination = posixpath.normpath(posixpath.join(str(PurePosixPath(path).parent), file)) if file else path
            assert destination in files, (path, target)
            if fragment: assert fragment in parsed[destination].ids, (path, target)


def test_nullable_and_semantic_cardinality_are_not_lost_or_invented(compiled):
    report, _, _ = compiled
    exported = json.loads(contents(report)['livrables/architecture-model.json'])['snapshots'][0]['objects']
    g = deliverables.Graph([{'objects': exported}])
    physical = next(o for o in exported if o['meta']['type'] == 'air.PhysicalTable')
    before = deliverables.d_physical(g)[1]
    altered = deepcopy(exported);next(o for o in altered if o['meta']['id'] == physical['meta']['id'])['body']['columns'][1]['nullable'] = True
    after = deliverables.d_physical(deliverables.Graph([{'objects': altered}]))[1]
    assert before != after and '| amount | numeric(12,2) | oui |' in '\n'.join(after)
    concepts = [o for o in exported if o['meta']['type'] == 'air.Concept']
    c = concepts[0]
    rel = {'meta': {**c['meta'], 'id': 'urn:relation:test', 'type': 'air.ConceptRelation'},
           'body': {'subject': {'id': c['meta']['id'], 'revision': c['meta']['revision']}, 'object': {'id': c['meta']['id'], 'revision': c['meta']['revision']}, 'predicate': 'HAS', 'cardinality': '0..1'}}
    first = deliverables.d_logical(deliverables.Graph([{'objects': exported + [rel]}]))[1]
    rel = deepcopy(rel);rel['body']['cardinality'] = '1..*'
    second = deliverables.d_logical(deliverables.Graph([{'objects': exported + [rel]}]))[1]
    assert first != second and '1..*' in '\n'.join(second)
    assert '||--o{' not in '\n'.join(first), 'A predicate must not invent inverse cardinality'


def test_same_identity_at_two_revisions_has_two_separate_dossiers(store, example):
    body = {'kind': 'DOCUMENT', 'locator': 'urn:fiction:source', 'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'test', 'retention_policy': 'test'}
    old = obj(example, 'Source', 'shared-source', body);old['meta']['description'] = 'Description historique'
    new = deepcopy(old);new['meta']['revision'] = 2;new['meta']['description'] = 'Description cible'
    store.put_bundle([old, new], 'fixture')
    pins = [frozen(store, example, [old], 'urn:baseline:old'), frozen(store, example, [new], 'urn:baseline:new')]
    user = {'subject': 'local-admin', 'role': 'admin'}
    report = deliverables.compile_deliverables(store, user, POLICY, {'title': 'Projet', 'baselines': pins})
    assert report['projection_conflicts'] == [{'id': old['meta']['id'], 'revisions': [1, 2]}]
    files = contents(report)
    for index, expected, forbidden in [(0, 'Description historique', 'Description cible'), (1, 'Description cible', 'Description historique')]:
        parent = str(PurePosixPath(report['website']['dossiers'][index]['path']).parent)
        page = files['livrables/site/' + parent + '/objects.html']
        assert expected in page and forbidden not in page
    g = deliverables.Graph([{'objects': [old, new]}])
    assert g.get({'id': old['meta']['id'], 'revision': 1}) == old


def test_model_text_cannot_become_html_or_external_navigation(store, example):
    old = obj(example, 'Source', 'hostile', {'kind': 'DOCUMENT', 'locator': 'javascript:alert(1)', 'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'test', 'retention_policy': 'test'})
    old['meta']['description'] = '<img src="https://hostile.invalid/x" onerror="alert(1)">'
    store.put_bundle([old], 'fixture');pin = frozen(store, example, [old])
    report = deliverables.compile_deliverables(store, {'subject': 'local-admin', 'role': 'admin'}, POLICY, {'title': '<script>alert(1)</script>', 'baselines': [pin]})
    for path, text in contents(report).items():
        if path.endswith('.html') and '/site/' in path:
            assert '<img src="https://hostile.invalid' not in text and '<script>alert(1)</script>' not in text
            parser = Links();parser.feed(text)
            assert not any(x.startswith(('javascript:', 'https:', 'http:')) for x in parser.targets)


def test_site_is_authorized_and_selective_reads_remain_small(store, compiled):
    report, request, user = compiled
    small = deliverables.compile_deliverables(store, user, POLICY, {**request, 'only': ['19-modele-logique']})
    assert small['website'] is None
    assert 'livrables/architecture-model.json' in contents(small)
    assert not any('/site/' in p for p in contents(small))
    with pytest.raises(Forbidden):
        deliverables.compile_deliverables(store, {'subject': 'unrelated', 'role': 'reader'}, AccessPolicy({'version': 'restricted', 'subjects': {'unrelated': {'read': ['other.project']}}}), request)


def test_schema_artifact_rights_are_checked_separately(store, compiled):
    _, request, user = compiled
    exported = store.export_baseline(request['baselines'][0])
    namespaces = sorted({o['meta']['namespace'] for o in exported['objects'] + [exported['baseline']]})
    policy = AccessPolicy({'version': 'objects-only', 'subjects': {user['subject']: {'read': namespaces}}})
    with pytest.raises(Forbidden):
        deliverables.compile_deliverables(store, user, policy, {**request, 'only': ['19-modele-logique']})


def test_same_names_do_not_collapse_entities_or_tables(compiled):
    report, _, _ = compiled
    exported = json.loads(contents(report)['livrables/architecture-model.json'])['snapshots'][0]['objects']
    entity = next(o for o in exported if o['meta']['type'] == 'air.DataEntity')
    twin = deepcopy(entity);twin['meta']['id'] += ':second-component'
    table = next(o for o in exported if o['meta']['type'] == 'air.PhysicalTable')
    table_twin = deepcopy(table);table_twin['meta']['id'] += ':second-store'
    g = deliverables.Graph([{'objects': exported + [twin, table_twin]}])
    from air.deliverables import mid
    logical = '\n'.join(deliverables.d_logical(g)[1]);physical = '\n'.join(deliverables.d_physical(g)[1])
    assert mid(entity['meta']['id']) in logical and mid(twin['meta']['id']) in logical
    assert mid(table['meta']['id']) in physical and mid(table_twin['meta']['id']) in physical


def test_http_and_mcp_expose_the_same_site_manifest_and_digests(store, tmp_path, compiled):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.config import Settings
    from air.mcp import PROTOCOL
    report, request, user = compiled
    token = store.create_token('site-api-reader', 'reader')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test')
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    query = {**request, 'content': 'DIGESTS'}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        response = client.post('/v1/deliverables/compile', json=query, headers=headers)
        assert response.status_code == 200
        http = response.json()
        assert http['file_set_digest'] == report['file_set_digest'] and http['website'] == report['website']
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_compile_deliverables', 'arguments': query}},
            headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL}).json()['result']
        assert not result['isError'] and result['structuredContent']['file_set_digest'] == http['file_set_digest']
        assert result['structuredContent']['website'] == http['website']
        assert client.post('/v1/deliverables/compile', json=query).status_code == 401


def test_static_business_paths_match_the_authenticated_service(store, compiled):
    from air import business_paths
    report, request, user = compiled
    files = contents(report)
    paths = [json.loads(value) for path, value in files.items() if '/site/' in path and '/path-' in path and path.endswith('.json')]
    assert paths
    for exported in paths:
        root = {k: exported['root']['reference'][k] for k in ('id', 'revision')}
        response = business_paths.query_paths(store, user, POLICY, {'baselines': request['baselines'], 'start': {'baseline': exported['baseline'], 'object': root}})
        assert {**response['result'], 'engine': response['engine']} == exported
        assert not exported['causality_verified'] and not exported['business_execution_performed']
    pages = [v for p, v in files.items() if '/path-' in p and p.endswith('.html')]
    assert any('Pas de jointure explicite dans cette étape' in v for v in pages)
