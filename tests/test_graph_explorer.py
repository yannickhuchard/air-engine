from copy import deepcopy
from html.parser import HTMLParser
import json
import pytest
from air import graph_explorer, deliverables
from air.core import digest, reference_slots
from air.expr import artifact_digest
from air.foundation import exact, TooLarge
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_graph_preserves_every_exact_reference_and_local_control_flow(store, compiled):
    _, request, _ = compiled
    exported = store.export_baseline(request['baselines'][0]);before = store.counts()
    graph = graph_explorer.project_graph(exported)
    assert graph == graph_explorer.project_graph(exported) and store.counts() == before
    objects = {(o['meta']['id'], o['meta']['revision']): o for o in exported['objects']}
    object_nodes = [n for n in graph['nodes'] if not n['local_step']]
    assert len(object_nodes) == len(objects)
    assert {n['reference']['digest'] for n in object_nodes} == {digest(o) for o in objects.values()}
    refs = [e for e in graph['edges'] if 'occurrence' in e]
    assert len(refs) == sum(len(list(reference_slots(o))) for o in objects.values())
    assert len({e['id'] for e in graph['edges']}) == len(graph['edges'])
    nodes = {n['id']: n for n in graph['nodes']}
    for e in graph['edges']:
        assert e['source'] in nodes and e['target'] in nodes
        source = objects[(e['evidence']['id'], e['evidence']['revision'])]
        assert e['evidence']['digest'] == digest(source)
        if e['kind'] == 'CONTROL_FLOW':
            assert nodes[e['source']]['local_step'] and nodes[e['target']]['local_step']
            assert e['declared'] in source['body']['flows']
    assert not graph['causality_verified'] and not graph['conditions_evaluated']
    assert artifact_digest({k: v for k, v in graph.items() if k != 'graph_digest'}) == graph['graph_digest']


def test_direction_cardinality_nullable_source_and_topology_are_not_inferred(store, compiled):
    _, request, _ = compiled
    exported = store.export_baseline(request['baselines'][0]);graph = graph_explorer.project_graph(exported)
    by_ref = {(o['meta']['id'], o['meta']['revision']): o for o in exported['objects']}
    assert any(e['kind'] == 'CONNECTION' for e in graph['edges'])
    for e in graph['edges']:
        if e['kind'] in ('CONNECTION', 'DATA_FLOW', 'CONCEPT_RELATION'):
            obj = by_ref[(e['evidence']['id'], e['evidence']['revision'])]
            assert e['declared'] == obj['body']
            assert e['source'] == graph_explorer.node_id(obj['body'].get('subject', obj['body'].get('source')))
            assert e['target'] == graph_explorer.node_id(obj['body'].get('object', obj['body'].get('destination', obj['body'].get('target'))))
            assert not any(x['kind'] == 'DATA_FLOW' and x['evidence'] == e['evidence'] for x in graph['edges']) if e['kind'] == 'CONNECTION' else True

    # Two revisions of the same topology object can declare identical endpoints;
    # their edges still need separate identities and separate source revisions.
    connection = next(o for o in exported['objects'] if o['meta']['type'] == 'air.Connection')
    newer = deepcopy(connection);newer['meta']['revision'] += 1
    revised = graph_explorer.project_graph({**exported, 'objects': exported['objects'] + [newer]})
    projections = [e for e in revised['edges'] if e['kind'] == 'CONNECTION' and e['evidence']['id'] == connection['meta']['id']]
    assert len(projections) == 2 and len({e['id'] for e in projections}) == 2
    assert len({e['evidence']['revision'] for e in projections}) == 2


def test_revisions_duplicate_names_and_step_identifiers_do_not_collapse(store, compiled):
    _, request, _ = compiled
    exported = store.export_baseline(request['baselines'][0])
    original = next(o for o in exported['objects'] if o['meta']['type'] == 'air.Workflow')
    newer = deepcopy(original);newer['meta']['revision'] += 1
    twin = deepcopy(original);twin['meta']['id'] += ':twin'
    graph = graph_explorer.project_graph({**exported, 'objects': [original, newer, twin]})
    assert len({n['id'] for n in graph['nodes']}) == len(graph['nodes'])
    assert len([n for n in graph['nodes'] if not n['local_step']]) == 3
    assert len([n for n in graph['nodes'] if n['local_step']]) == 3 * len(original['body']['steps'])
    assert graph['gaps'], 'Absent external references are disclosed, not created as readable nodes'
    assert graph_explorer.node_id({'id': 'urn:x:1:step:s', 'revision': 2}) != graph_explorer.node_id({'id': 'urn:x', 'revision': 1}, 's:2')


def test_budgets_fail_explicitly_instead_of_silently_dropping_objects(store, compiled):
    _, request, _ = compiled;exported = store.export_baseline(request['baselines'][0])
    first = exported['objects'][0]
    with pytest.raises(TooLarge): graph_explorer.project_graph({**exported, 'objects': [first] * 1001})
    wf = next(o for o in exported['objects'] if o['meta']['type'] == 'air.Workflow')
    many = []
    for i in range(17):
        copy = deepcopy(wf);copy['meta']['id'] += ':' + str(i)
        copy['body']['steps'] = [{**deepcopy(wf['body']['steps'][0]), 'id': 's' + str(j)} for j in range(256)]
        copy['body']['flows'] = [];many.append(copy)
    with pytest.raises(TooLarge): graph_explorer.project_graph({**exported, 'objects': many})


class EmbeddedGraph(HTMLParser):
    def __init__(self): super().__init__();self.active = False;self.text = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'air-graph': self.active = True
    def handle_endtag(self, tag):
        if tag == 'script': self.active = False
    def handle_data(self, text):
        if self.active: self.text += text


def test_site_embeds_the_same_graph_without_mutating_its_digest(store, compiled):
    report, request, user = compiled
    files = {f['path']: f['content'] for f in report['files']}
    assert report['website']['interactive_graphs'] == len(request['baselines'])
    for dossier in report['website']['dossiers']:
        path = 'livrables/site/' + dossier['graph'];parser = EmbeddedGraph();parser.feed(files[path])
        embedded = json.loads(parser.text);graph = json.loads(files[path[:-5] + '.json'])
        assert embedded['graph'] == graph and graph['graph_digest'] == dossier['graph_digest']
        assert all(href.startswith('objects.html#') for href in embedded['links'].values())
        assert embedded['paths'] and all(p['objects'] for p in embedded['paths'])
    selective = deliverables.compile_deliverables(store, user, POLICY, {**request, 'website': False})
    assert selective['website'] is None and not any('/site/' in f['path'] for f in selective['files'])


def test_hostile_model_strings_remain_inert_graph_data(store, compiled):
    report, request, user = compiled
    exported = store.export_baseline(request['baselines'][0])
    from air.architecture_site import graph_page, shell
    from air.deliverables import Graph
    changed = deepcopy(exported);changed['objects'][0]['meta']['name'] = '</script><img src=https://bad.invalid/x onerror=alert(1)>'
    data = graph_explorer.project_graph(changed);body, links = graph_page(data, Graph([changed]), [])
    page = shell('Graph', body, 'Project', '', '../../', graph_data={'graph': data, 'paths': [], 'links': links})
    assert '</script><img' not in page and '<img src=https://bad.invalid' not in page
    parser = EmbeddedGraph();parser.feed(page);assert json.loads(parser.text)['graph'] == data
