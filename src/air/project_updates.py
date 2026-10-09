"""News and open design work from one authorized pin, never invented events."""
from html import escape
from air.core import digest, record
from air.foundation import exact, check_schema
from air.expr import artifact_digest, bounded
from air.editorial import prose
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.project-updates/1'
REQUEST = record({'baseline': SNAPSHOT, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}}, ['baseline'])


def project(exported, gate, limit=6):
    pin = {**exact(exported['baseline']), 'digest': exported['digest']}
    if gate['baseline'] != pin: raise ValueError('Updates and readiness must have the same exact baseline')
    def row(o, fields):
        return {'name': o['meta']['name'], 'type': o['meta']['type'],
            'reference': {**exact(o), 'digest': digest(o)}, 'recorded_at': o['meta'].get('recorded_at'),
            'lifecycle': o['meta']['lifecycle'], 'description': o['meta']['description'],
            'fields': {k: o['body'][k] for k in fields if k in o['body']}}
    objects = [o for o in exported['objects'] if o['meta']['namespace'] == exported['baseline']['meta']['namespace']]
    def group(predicate, fields):
        selected = sorted([o for o in objects if predicate(o)], key=lambda o: (o['meta'].get('recorded_at', ''), o['meta']['id'], o['meta']['revision']), reverse=True)
        return {'items': [row(o, fields) for o in selected[:limit]], 'total': len(selected), 'omitted': max(0, len(selected)-limit)}
    result = {'engine': ENGINE, 'baseline': pin, 'name': exported['baseline']['meta']['name'],
        'news': group(lambda o: o['meta']['type'] in ('air.Decision', 'air.FinancialPlan', 'air.SourcingStrategy', 'air.ArchitectureTask'), ['selection', 'status', 'purpose', 'funding_status']),
        'decisions': group(lambda o: o['meta']['type'] == 'air.Decision', ['question', 'selection', 'rationale', 'consequences', 'revisit_conditions']),
        'open_questions': group(lambda o: o['meta']['type'] == 'air.Unknown' and o['body']['state'] in ('OPEN', 'INVESTIGATING'), ['question', 'state', 'resolution_owner', 'blocking_policy']),
        'active_tasks': group(lambda o: o['meta']['type'] == 'air.ArchitectureTask' and o['body']['status'] in ('TODO', 'IN_PROGRESS', 'BLOCKED'), ['purpose', 'status', 'owner']),
        'next_checks': [{'code': c['code'], 'status': c['status']} for c in gate['criteria'] if c['status'] not in ('MET', 'NOT_APPLICABLE')],
        'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'ordering': 'AUTHOR_RECORDED_AT_THEN_ID_NOT_REGISTRY_TIME_OR_PRIORITY',
        'registry_written': False, 'approval_inferred': False, 'business_execution_performed': False}
    return {**result, 'projection_digest': artifact_digest(result)}


def query(store, principal, policy, request):
    from air.access import ScopedStore
    from air.readiness import assess_readiness
    check_schema(request, REQUEST)
    e = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    result = project(e, assess_readiness(store, principal, policy, {'baseline': request['baseline']}), request.get('limit', 6))
    bounded(result)
    return result


def section(view, prefix='', compact=False):
    from air.deliverables import mid
    h = lambda x: escape(prose(str(x)), quote=True)
    key = 'project-news-' + mid(view['baseline']['id'] + ':' + str(view['baseline']['revision']))
    out = '<section class="project-news" id="' + key + '"><p class="eyebrow">Le point projet</p><h2>News du projet d’architecture</h2><p>Dernières informations déclarées dans le dossier r' + str(view['baseline']['revision']) + '. Les dates sont celles des auteurs ; elles ne prouvent ni livraison ni approbation.</p><div class="news-columns">'
    for group, title in [('news', 'Dernières informations'), ('decisions', 'Points de décision à examiner'), ('open_questions', 'Questions ouvertes'), ('active_tasks', 'Travaux à poursuivre')]:
        data = view[group]; visible = data['items'][:2] if compact else data['items']
        out += '<article><h3>' + title + ' <span>(' + str(data['total']) + ')</span></h3><ul>'
        for row in visible:
            r = row['reference']; href = prefix + 'objects.html#' + mid(r['id'] + ':' + str(r['revision']))
            out += '<li><a href="' + h(href) + '">' + h(row['name']) + '</a><p>' + h(row['description'][:240]) + ('…' if len(row['description']) > 240 else '') + '</p><small>' + h(row['type'][4:]) + ' · r' + str(r['revision']) + ' · ' + h(row['fields'].get('status', row['lifecycle'])) + '</small>'
            if not compact:
                out += '<details><summary>Lire les faits et la référence</summary><dl>' + ''.join('<dt>' + h(k) + '</dt><dd>' + h(v) + '</dd>' for k, v in row['fields'].items()) + '</dl><p>' + h(row['recorded_at'] or 'Date auteur non déclarée') + '</p><code>' + h(r['digest']) + '</code></details>'
            out += '</li>'
        out += '</ul>'
        if not visible: out += '<p>Aucun élément déclaré.</p>'
        if data['total'] > len(visible): out += '<p>' + str(data['total']-len(visible)) + ' autre(s) élément(s). Ouvrir la vue complète ou les objets sources.</p>'
        out += '</article>'
    out += '</div><p>Contrôles encore ouverts : ' + h(', '.join(c['code'] for c in view['next_checks']) or 'Aucun') + '.</p><p><a href="' + h(prefix + ('news.html' if compact else 'news.json')) + '">' + ('Lire les news, décisions et questions' if compact else 'Télécharger les données et références exactes') + '</a></p></section>'
    return out
