"""Declared organizational structure, never an executable authorization policy."""
PROFILE = 'air.organization/0.21'
NAMES = ['Role', 'OrganizationUnit', 'AuthorityScope', 'Domain']


def bodies(record, text, uri, ref, refs):
    texts = {'type': 'array', 'items': text, 'maxItems': 128, 'uniqueItems': True}
    skill = record({'binding': {'const': 'air.skill-requirement/0.21'}, 'competency': text, 'minimum_level': text, 'assessment_method': text})
    return {
        'air.Role': record({'responsibilities': {**texts, 'minItems': 1},
            'required_competencies': {'type': 'array', 'items': skill, 'maxItems': 128, 'uniqueItems': True},
            'authority': ref}, ['responsibilities', 'required_competencies']),
        'air.OrganizationUnit': record({'mandate': text, 'parent': ref, 'roles': {**refs, 'maxItems': 128}, 'operating_model': ref}, ['mandate', 'roles']),
        'air.AuthorityScope': record({'principal': uri, 'scope': ref, 'allowed_decisions': {**texts, 'minItems': 1},
            'limits': {**texts, 'minItems': 1}, 'delegations': {'type': 'array', 'maxItems': 0}, 'separation_rules': texts}),
        'air.Domain': record({'purpose': text, 'scope': ref, 'authority': ref}),
    }


def slots(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind in ('air.Role', 'air.Domain') and 'authority' in body:
        yield 'body/authority', body['authority'], ['air.AuthorityScope']
    if kind in ('air.Domain', 'air.AuthorityScope'):
        yield 'body/scope', body['scope'], ['air.Scope']
    if kind == 'air.OrganizationUnit':
        if 'parent' in body: yield 'body/parent', body['parent'], ['air.OrganizationUnit']
        for ref in body['roles']: yield 'body/roles', ref, ['air.Role']
    if kind == 'air.Actor':
        for ref in body['roles']: yield 'body/roles', ref, ['air.Role']


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    parents = {}
    for obj in objects:
        body, kind = obj['body'], obj['meta']['type']
        if kind == 'air.Domain':
            authority = by_ref.get(key(body['authority']))
            if authority and authority['meta']['type'] == 'air.AuthorityScope' and key(authority['body']['scope']) != key(body['scope']):
                yield 'AIR_DOMAIN_AUTHORITY_SCOPE', obj['meta']['id'], 'Domain and authority must reference the same exact scope in this binding'
        if kind == 'air.OrganizationUnit' and 'parent' in body:
            parents[(obj['meta']['id'], obj['meta']['revision'])] = key(body['parent'])
    # Iterative traversal: the graph budget allows 1000 members, beyond Python recursion limits.
    complete = set()
    for start in parents:
        trail = set(); current = start
        while current in parents and current not in complete:
            if current in trail:
                yield 'AIR_ORGANIZATION_CYCLE', start[0], 'Organization parent links must be acyclic'
                break
            trail.add(current); current = parents[current]
        complete.update(trail)


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind in ('air.OrganizationUnit', 'air.Actor'):
        body['roles'].sort(key=lambda r: (r['id'], r['revision']))
    if kind == 'air.Role':
        body['responsibilities'].sort()
        body['required_competencies'].sort(key=lambda s: (s['competency'], s['minimum_level'], s['assessment_method']))
    if kind == 'air.AuthorityScope':
        for field in ('allowed_decisions', 'limits', 'separation_rules'): body[field].sort()
