from html.parser import HTMLParser
from pathlib import PurePosixPath
from collections import Counter
from air import architecture_site, deliverables, site_navigation, site_questions
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hrefs = []
        self.current = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.hrefs.append(attrs['href'])
            if attrs.get('aria-current') == 'page': self.current.append(attrs['href'])


def topics():
    return [{'name': name, 'title': name} for name, _ in deliverables.CATALOGUE]


def test_every_catalogue_topic_has_one_dimension_and_one_menu_entry():
    entries = [entry for stage in site_navigation.stages(topics()) for group in stage['dimensions'] for entry in group['entries']]
    expected = {name + '.html' for name, _ in deliverables.CATALOGUE}
    counts = Counter(entry['href'] for entry in entries if entry['topic'])
    assert set(counts) == expected and set(counts.values()) == {1}
    nav = Links(architecture_site.navigation(topics()).html)
    assert all(nav.hrefs.count(name) == 1 for name in expected)
    assert len(nav.hrefs) == len(set(nav.hrefs))
    assert nav.current == ['index.html']


def test_all_topics_and_views_have_one_current_link_and_a_matching_chapter():
    for stage in site_navigation.stages(topics()):
        for entry in [dict(key=stage['key'], href=stage['href']), *[entry for group in stage['dimensions'] for entry in group['entries']]]:
            nav = architecture_site.navigation(topics(), entry['key'])
            assert Links(nav.html).current == [entry['href']]
            assert 'data-nav-stage="' + stage['id'] + '" open data-nav-active="true"' in nav.html
            assert stage['title'] in nav.context
            assert ('rel="prev"' in nav.context) == (stage['number'] > 1)
            assert ('rel="next"' in nav.context) == (stage['number'] < 7)
    for key, _ in site_navigation.INTRO + site_navigation.AUDIENCES + site_navigation.TOOLS:
        assert Links(architecture_site.navigation(topics(), key).html).current == [key + '.html']
    assert Links(architecture_site.navigation(topics(), 'handoff-team-example').html).current == ['handoff.html']
    assert Links(architecture_site.navigation(topics(), 'diagram-handoff-example').html).current == ['handoff.html']


def test_nav_labels_are_escaped_and_role_routes_are_preserved():
    changed = topics()
    changed[0]['title'] = '<img src=x onerror=alert(1)>'
    nav = architecture_site.navigation(changed)
    assert '<img' not in nav.html and '&lt;img' in nav.html
    for role, *_ in site_questions.ROLES:
        assert Links(architecture_site.navigation(changed, 'role-' + role).html).current == ['role-' + role + '.html']


def test_compiled_chapters_preserve_existing_topic_urls_and_progression(compiled):
    report, _, _ = compiled
    files = {f['path']: f['content'] for f in report['files']}
    dossier = report['website']['dossiers'][0]
    prefix = 'livrables/site/' + str(PurePosixPath(dossier['path']).parent) + '/'
    assert dossier['reading_navigation']['purpose'] == 'READING_ORDER_NOT_GATING'
    assert len(dossier['reading_navigation']['stages']) == 7
    for stage in site_navigation.stages(topics()):
        page = files[prefix + stage['href']]
        assert 'À expliquer au métier' in page and 'équipes de réalisation' in page
        assert 'class="reading-position"' in page
        for href in Links(page).hrefs:
            if href.startswith('../../') or '#' in href: continue
            assert prefix + href in files, href
    for name, _ in deliverables.CATALOGUE:
        assert prefix + name + '.html' in files
    home = files[prefix + 'index.html']
    assert 'class="reading-outline"' in home
    for key in ('story', 'graph', 'objects', 'business-paths', 'questions', 'management-summary', 'news', 'finance', 'handoff'):
        assert Links(files[prefix + key + '.html']).current == [key + '.html']
