"""Editorial presentation must not corrupt pinned sources, code or identifiers."""
from copy import deepcopy
import json
from air import branding, deliverables, editorial
from air.atelier import product, render_json, render_text
from air.site_pwa import add_identity
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_normalization_preserves_markup_code_payload_and_digests():
    dash = '\u2014'
    original = {'name': 'Projet ' + dash + ' cible'}
    payload = render_json(original)
    html = '<p title="A' + dash + 'B">A' + dash + 'B &mdash; C &#8212; D</p>\n'
    html += '<script type="application/json">' + payload + '</script><pre><code>' + dash + '</code></pre>'
    rendered = product('page.html', 'text/html', html, 'GENERATED')
    assert '<p title="A' + dash + 'B">A-B - C - D</p>' in rendered['content']
    assert payload in rendered['content'] and '<pre><code>' + dash in rendered['content']
    assert editorial.html(rendered['content']) == rendered['content']
    assert json.loads(product('source.json', 'application/json', payload, 'GENERATED')['content']) == original
    text = render_text(['A' + dash + 'B', '```json', payload, '```', '`id' + dash + 'exact`'])
    assert text.startswith('A-B\n') and payload in text and '`id' + dash + 'exact`' in text


def test_branding_normalizes_display_without_rewriting_source():
    source = {'name': 'Studio\u2014Conseil', 'tagline': 'Atlas d’architecture'}
    saved = deepcopy(source)
    brand = branding.normalize(source)
    assert brand['profile']['name'] == 'Studio-Conseil'
    assert brand['profile']['tagline'] == 'Projet d’architecture'
    assert brand['source'] == saved == source
    assert branding.normalize({})['profile']['tagline'] == 'Projet d’architecture'
    files = {}
    add_identity(lambda path, media, content: files.update({path: content}), 'Projet\u2014cible', brand)
    assert json.loads(files['manifest.webmanifest'])['name'] == 'Projet-cible - Studio-Conseil'
    assert deliverables.label('Composant\u2014prévu') == '"Composant-prévu"'


def test_site_style_does_not_change_exported_revision(store, example):
    source = obj(example, 'Source', 'editorial-source', {'kind': 'DOCUMENT', 'locator': 'urn:fiction:source',
        'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'test', 'retention_policy': 'test'})
    source['meta']['name'] = 'Source\u2014lisible'
    source['meta']['description'] = 'Texte\u2014importé'
    store.put_bundle([source], 'fixture')
    pin = frozen(store, example, [source], 'urn:baseline:editorial')
    report = deliverables.compile_deliverables(store, {'subject': 'local-admin', 'role': 'admin'}, POLICY,
                                             {'title': 'Projet\u2014test', 'baselines': [pin]})
    files = {f['path']: f['content'] for f in report['files']}
    model = json.loads(files['livrables/architecture-model.json'])
    assert source in model['snapshots'][0]['objects']
    assert model['snapshots'][0]['digest'] == store.export_baseline(pin)['digest']
    pages = [value for path, value in files.items() if path.endswith('/objects.html')]
    assert pages and all('Source-lisible' in page and 'Texte-importé' in page for page in pages)
    assert 'Projet d’architecture' in files['livrables/site/index.html']
