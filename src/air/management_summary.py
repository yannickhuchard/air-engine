"""A bounded management brief regenerated from one authorized exact baseline."""
from html import escape
from air.core import digest
from air.expr import artifact_digest
from air.foundation import InvalidModel, exact
from air.editorial import prose

ENGINE = 'air.management-summary/1'
NAME = '00-management-summary'
LIMIT = 5


def project(exported, gate):
    from air.deliverables import Graph, _criterion_row
    from air import financial_view
    meta = exported['baseline']['meta']
    pin = {**exact(exported['baseline']), 'digest': exported['digest']}
    if gate['baseline'] != pin:
        raise InvalidModel('Management summary and readiness must use the same exact baseline')
    g = Graph([exported])
    def entries(kind, fields, predicate=lambda o: True):
        objects = [o for o in g.of(kind) if o['meta']['namespace'] == meta['namespace'] and predicate(o)]
        objects.sort(key=lambda o: (o['body'].get('target_date', ''), o['meta']['id'], o['meta']['revision']))
        rows = []
        for o in objects[:LIMIT]:
            rows.append({'name': o['meta']['name'], 'reference': {**exact(o), 'digest': digest(o)},
                'fields': [{'field': f, 'value': o['body'][f]} for f in fields if f in o['body']],
                'lifecycle': o['meta']['lifecycle'], 'approval_inferred': False})
        return {'items': rows, 'total': len(objects), 'omitted': max(0, len(objects) - LIMIT)}
    criteria = []
    for c in gate['criteria']:
        row = _criterion_row(c)
        criteria.append({'code': c['code'], 'status': c['status'], 'label': row[0], 'next_action': row[3]})
    finance = financial_view.project(g)
    # Financial declarations may contain imported objects: exact membership is
    # retained, never projected into a fictional consolidated enterprise budget.
    plans = [{k: p[k] for k in ('reference', 'name', 'programme_envelope', 'vat_bridge', 'treasury_envelope',
        'calculated_cost', 'contingency_total', 'headroom', 'start', 'end', 'reference_status', 'funding_status')} for p in finance['plans'][:LIMIT]]
    result = {'engine': ENGINE, 'baseline': pin, 'name': meta['name'], 'namespace': meta['namespace'],
        'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'live_sync': False,
        'selection_policy': 'FIRST_FIVE_BY_DATE_AND_ID_NOT_PRIORITY_RANKING',
        'intent': entries('Intent', ['desired_change']), 'goals': entries('Goal', ['outcome']),
        'scope': entries('Scope', ['boundary_description']),
        'decisions': entries('Decision', ['question', 'selection', 'rationale', 'consequences', 'revisit_conditions']),
        'risks': entries('Risk', ['scenario', 'consequences', 'residual_assessment']),
        'unknowns': entries('Unknown', ['question', 'blocking_policy', 'resolution_owner'], lambda o: o['body'].get('state') in ('OPEN', 'INVESTIGATING')),
        'assumptions': entries('Assumption', ['statement', 'impact_if_false', 'validation_plan'], lambda o: o['body'].get('state') in ('OPEN', 'UNDER_TEST')),
        'milestones': entries('Milestone', ['target_date', 'exit_criteria']),
        'sourcing': entries('SourcingStrategy', ['strategy', 'status', 'purpose', 'criteria']),
        'finance': {'plans': plans, 'omitted_plans': max(0, len(finance['plans']) - LIMIT), 'totals': finance['totals'], 'missing': finance['missing'],
            'projection_digest': finance['projection_digest'], 'aggregate_scope': 'EXACT_MEMBERSHIP_NOT_CONSOLIDATED_PROGRAMME',
            'sources': [{'reference': r['reference'], 'sources': r['sources']} for r in finance['rows']]},
        'gate': {'code': gate['result'], 'met': sum(c['status'] == 'MET' for c in criteria), 'total': len(criteria),
            'criteria': criteria, 'proof': gate.get('proof', {}), 'report_digest': gate.get('report_digest')},
        'approval_inferred': False, 'business_execution_performed': False}
    return {**result, 'projection_digest': artifact_digest(result)}


def short(value):
    text = prose('; '.join(str(x) for x in value) if isinstance(value, list) else str(value))
    return text[:480] + ('… [extrait ; lire la source exacte]' if len(text) > 480 else '')


def lines(view):
    from air.financial_view import fmt
    out = ['## Management Summary : ' + prose(view['name']), '',
        'Baseline `' + view['baseline']['id'] + '` r' + str(view['baseline']['revision']) + ' ; `' + view['baseline']['digest'] + '`.',
        'Préparation : ' + str(view['gate']['met']) + '/' + str(view['gate']['total']) + ', ' + view['gate']['code'] + '.', '',
        'Résumé régénéré depuis cette version exacte. Les choix restent des déclarations ; leur affichage ne vaut pas approbation.', '']
    labels = [('intent', 'Pourquoi ce projet'), ('goals', 'Résultats attendus'), ('scope', 'Périmètre'),
        ('decisions', 'Choix et conséquences'), ('risks', 'Risques à examiner'), ('unknowns', 'Questions ouvertes'),
        ('assumptions', 'Hypothèses à vérifier'), ('milestones', 'Jalons prévus'), ('sourcing', 'Consultations fournisseurs')]
    for key, label in labels:
        group = view[key]; out += ['### ' + label, '']
        if not group['items']: out += ['Non documenté dans les objets sélectionnés de cette version.' if key not in ('unknowns', 'assumptions') else 'Aucun élément ouvert déclaré.', '']
        for row in group['items']:
            out += ['- ' + prose(row['name']) + ' : ' + ' / '.join(short(f['value']) for f in row['fields']),
                '  Source : `' + row['reference']['id'] + '` r' + str(row['reference']['revision']) + ' ; `' + row['reference']['digest'] + '`.']
        if group['omitted']: out += [str(group['omitted']) + ' autre(s) élément(s) : ouvrir le dossier complet. Sélection par identifiant, sans classement de priorité.']
        out += ['']
    out += ['### Enveloppe et financement', '']
    if not view['finance']['plans']: out += ['Aucun FinancialPlan : enveloppe et statut de financement non documentés.']
    for p in view['finance']['plans']:
        cur = p['programme_envelope']['currency']
        out += ['- ' + prose(p['name']) + ' : ' + fmt(p['treasury_envelope']) + ' ' + cur + ' de trésorerie ; coûts ' + fmt(p['calculated_cost']) +
            ', contingence incluse ' + fmt(p['contingency_total']) + ', réserve TVA ' + fmt(p['vat_bridge']['value']) + '.',
            '  Période : ' + p['start'] + ' à ' + p['end'] + '. Référence : ' + p['reference_status'] + '. Financement : ' + p['funding_status'] + '.']
    out += ['', '### Ce qui conditionne la suite', '']
    for c in view['gate']['criteria']:
        if c['status'] not in ('MET', 'NOT_APPLICABLE'): out += ['- ' + c['label'] + ' : ' + c['status'] + '. ' + c['next_action']]
    out += ['', 'Conception et simulation pour réalisation ultérieure. Les tests métier futurs ne sont pas déclarés exécutés.',
        'Un site déjà exporté reste attaché à sa baseline ; régénérer puis appliquer la nouvelle copie pour mettre à jour la lecture.']
    return out


def section(view, prefix='', compact=False):
    from air.deliverables import mid
    from air.financial_view import fmt
    h = lambda x: escape(prose(str(x)), quote=True)
    heading = 'h2' if compact else 'h1'
    section_id = 'management-summary-' + mid(view['baseline']['id'] + ':' + str(view['baseline']['revision'])) if prefix else 'management-summary'
    text = '<section class="management-summary" id="' + section_id + '"><' + heading + '>Management Summary</' + heading + '>'
    text += '<p class="intro">' + h(view['name']) + ' : lecture de direction depuis la révision ' + str(view['baseline']['revision']) + '.</p>'
    for row in view['intent']['items'][:1]: text += '<p>' + h(short(row['fields'][0]['value'])) + '</p>'
    text += '<p class="gate">Préparation : <strong>' + str(view['gate']['met']) + '/' + str(view['gate']['total']) + '</strong>. ' + h(view['gate']['code']) + '.</p>'
    for p in view['finance']['plans']:
        text += '<p><strong>Trésorerie : ' + h(fmt(p['treasury_envelope']) + ' ' + p['programme_envelope']['currency']) + '</strong>. Financement : ' + h(p['funding_status']) + '. <a href="' + h(prefix + 'finance.html') + '">Lire la décomposition et les sources</a></p>'
    if compact:
        text += '<p>' + str(view['unknowns']['total']) + ' question(s) ouverte(s), ' + str(view['risks']['total']) + ' risque(s) déclaré(s). <a href="' + h(prefix + 'management-summary.html') + '">Lire le résumé et les arbitrages</a></p>'
    else:
        for key, label in [('goals', 'Résultats attendus'), ('scope', 'Périmètre'), ('decisions', 'Choix et conséquences'), ('risks', 'Risques à examiner'), ('unknowns', 'Questions ouvertes'), ('assumptions', 'Hypothèses à vérifier'), ('milestones', 'Jalons prévus'), ('sourcing', 'Consultations fournisseurs')]:
            group = view[key];text += '<section><h2>' + label + '</h2><ul>'
            for row in group['items']:
                pin = row['reference']; href = prefix + 'objects.html#' + mid(pin['id'] + ':' + str(pin['revision']))
                text += '<li><a href="' + h(href) + '">' + h(row['name']) + '</a><p>' + h(' / '.join(short(f['value']) for f in row['fields'])) + '</p></li>'
            text += '</ul>'
            if not group['items']: text += '<p>Aucun élément déclaré pour cette section.</p>'
            if group['omitted']: text += '<p>' + str(group['omitted']) + ' autre(s) élément(s) dans le dossier. Sélection par identifiant, sans priorité inférée.</p>'
            text += '</section>'
        text += '<h2>Ce qui conditionne la suite</h2><ul>' + ''.join('<li>' + h(c['label']) + ' : ' + h(c['status']) + '. ' + h(c['next_action']) + '</li>' for c in view['gate']['criteria'] if c['status'] not in ('MET', 'NOT_APPLICABLE')) + '</ul>'
        text += '<p><a href="' + h(prefix + 'management-summary.json') + '">Résumé structuré et références exactes</a> · <a href="' + h(prefix + 'management-summary.md') + '">Version Markdown</a></p>'
    text += '<p class="summary-context">Version exacte, sans synchronisation en direct. Régénérer le dossier après évolution. Ce résumé ne remplace pas les preuves ni les approbations.</p></section>'
    return text
