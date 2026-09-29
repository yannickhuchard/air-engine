"""Bounded, declarative audience views; selection never grants disclosure rights."""
PROFILE = 'air.audience/0.19'
NAMES = ['Viewpoint']


def bodies(record, text, ref, refs, nonempty, data_types):
    types = {'type': 'array', 'items': {'enum': data_types}, 'maxItems': len(data_types), 'uniqueItems': True}
    selection = record({'binding': {'const': 'air.selector/0.19'}, 'types': types, 'objects': {**refs, 'maxItems': 256}})
    section = record({'id': {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{0,63}$'}, 'heading': text, 'types': {**types, 'minItems': 1}})
    presentation = record({'format': {'const': 'air.audience-html/0.19'}, 'title': text,
        'sections': {'type': 'array', 'items': section, 'minItems': 1, 'maxItems': 32}})
    return {'air.Viewpoint': record({'audience': {**nonempty, 'maxItems': 64}, 'concerns': {**nonempty, 'maxItems': 256},
        'selection': selection, 'presentation': presentation, 'disclosure_policy': text})}


def slots(obj, data_types):
    if obj['meta']['type'] != 'air.Viewpoint': return
    body = obj['body']
    for ref in body['audience']: yield 'body/audience', ref, ['air.Stakeholder']
    for ref in body['concerns']: yield 'body/concerns', ref, ['air.Concern']
    for ref in body['selection']['objects']: yield 'body/selection/objects', ref, data_types


def local_issues(obj):
    if obj['meta']['type'] != 'air.Viewpoint': return
    body = obj['body'];selection = body['selection'];sections = body['presentation']['sections']
    if not selection['types'] and not selection['objects']:
        yield 'AIR_VIEWPOINT_EMPTY', 'Declare at least one selected type or exact object'
    if len({s['id'] for s in sections}) != len(sections) or any(s['id'] == 'air-unassigned' for s in sections):
        yield 'AIR_VIEWPOINT_SECTION', 'Presentation section identifiers must be unique'
    types = [t for s in sections for t in s['types']]
    if len(set(types)) != len(types):
        yield 'AIR_VIEWPOINT_SECTION', 'A type belongs to at most one presentation section'


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    for obj in objects:
        if obj['meta']['type'] != 'air.Viewpoint': continue
        body = obj['body'];covered = set()
        for ref in body['audience']:
            stakeholder = by_ref.get(key(ref))
            if stakeholder and stakeholder['meta']['type'] == 'air.Stakeholder':
                covered.update(key(r) for r in stakeholder['body']['concerns'])
        if not {key(r) for r in body['concerns']} <= covered:
            yield 'AIR_VIEWPOINT_CONCERN', obj['meta']['id'], 'Every viewpoint concern must be declared by at least one selected stakeholder'


def canonicalize(obj):
    if obj['meta']['type'] != 'air.Viewpoint': return
    body = obj['body'];key = lambda r: (r['id'], r['revision'])
    for field in ('audience', 'concerns'): body[field].sort(key=key)
    body['selection']['types'].sort();body['selection']['objects'].sort(key=key)
    for section in body['presentation']['sections']: section['types'].sort()
    # Sections retain their declared presentation order.
