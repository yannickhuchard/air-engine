"""Persona-first offline journeys, with exact design references."""
from html import escape
from air.editorial import prose
from air.deliverables import mid

KINDS = {'DIGITAL': 'Numérique', 'PHYSICAL': 'Physique', 'GEOGRAPHIC': 'Géographique'}
CATEGORIES = {'NOMINAL': 'Service nominal', 'EXCEPTION': 'Exception et repli', 'SUPPORT': 'Assistance',
              'OPERATIONS': 'Exploitation', 'GOVERNANCE': 'Gouvernance', 'UNDECLARED': 'Catégorie à préciser'}


def h(v): return escape(prose(str(v)), quote=True)
def anchor(pin): return mid(pin['id'] + ':' + str(pin['revision']))
def link(d): return '<a href="objects.html#' + anchor(d['reference']) + '">' + h(d['name']) + '</a>'


def preview(view, href='journeys.html'):
    return '<section class="journey-preview"><p class="view-eyebrow">Expérience et usages</p><h2>Qui intervient, où et comment ?</h2><p>' + str(len(view['journeys'])) + ' parcours, ' + str(len(view['personas'])) + ' personas inventoriés, ' + str(view['touchpoint_count']) + ' points de contact. Usages numériques, physiques et géographiques reliés au dossier.</p><p><a class="dossier-home" href="' + h(href) + '">Explorer les parcours par persona</a></p></section>'


def checklist(view):
    body = '<section id="journey-checklist"><h2>Checklist de couverture des parcours</h2><p>Contrôle documentaire calculé sur les références de cette baseline. Il ne certifie ni une recherche utilisateur, ni la conformité réglementaire, ni la réception terrain.</p><ul>'
    for c in view['checks']:
        body += '<li><strong>' + ('Documenté' if c['status'] == 'MET' else 'À compléter') + '</strong> : ' + h(c['label']) + ' (' + str(c['gap_count']) + ' lacune(s)).</li>'
    body += '</ul>'
    if view['gaps']:
        body += '<details><summary>Voir les lacunes exactes (' + str(len(view['gaps'])) + ')</summary><ul>'
        for gap in view['gaps']:
            body += '<li>' + h(gap['code']) + (' : <a href="objects.html#' + anchor(gap['source']) + '">' + h(gap['source']['id'].rsplit(':', 1)[-1]) + '</a>' if 'source' in gap else '') + ' ' + h(gap.get('selector', '')) + ' ' + h(', '.join(gap.get('contexts', []))) + '</li>'
        body += '</ul></details>'
    return body + '</section>'


def page(view):
    body = '<h1>Parcours clients et intervenants</h1><p class="intro">Partir d’un persona, comprendre son intention, puis suivre les points de contact et les éléments d’architecture prévus.</p><p>Le catalogue définit son périmètre et ses exclusions. Les lieux proposés ne sont ni des corridors autorisés ni des trajets géolocalisés exécutés.</p>'
    body += '<label for="journey-persona">Choisir un persona</label><select id="journey-persona"><option value="">Tous les personas</option>' + ''.join('<option value="' + anchor(p['reference']) + '">' + h(p['name']) + '</option>' for p in view['personas']) + '</select><p id="journey-filter-status" role="status"></p>'
    for c in view['catalogs']:
        body += '<details class="journey-scope"><summary>' + h(c['name']) + '</summary><p>' + h(c['purpose']) + '</p><p>Périmètre : ' + link(c['scope']) + '.</p><p>Source : ' + link(c) + '.</p></details>'
    for p in view['personas']:
        key = anchor(p['reference'])
        body += '<section class="persona-journeys" id="persona-' + key + '" data-persona="' + key + '"><h2>' + link(p) + '</h2><p>' + h(p['rationale']) + '</p><p>' + ('Hors périmètre, avec justification.' if p['coverage'] == 'EXCLUDED' else 'Contextes requis : ' + h(', '.join(KINDS[c] for c in p['required_contexts'])) + '. Contextes déclarés : ' + h(', '.join(KINDS[c] for c in p['declared_contexts']) or 'Aucun')) + '</p><div class="journey-cards">'
        selected = {(r['id'], r['revision']) for r in p['journeys']}
        for j in view['journeys']:
            if (j['reference']['id'], j['reference']['revision']) in selected:
                body += '<article class="journey-card"><p class="view-eyebrow">' + h(CATEGORIES[j['category']]) + '</p><h3><a href="journey-' + anchor(j['reference']) + '.html">' + h(j['name']) + '</a></h3><p>' + h(j['goal']) + '</p><p>' + str(len(j['steps'])) + ' étapes. Résultat prévu : ' + h(j['outcome']) + '</p><a href="journey-map-' + anchor(j['reference']) + '.html">Explorer la carte visuelle</a></article>'
        body += '</div>' + ('<p>Aucun parcours inventorié pour ce persona.</p>' if not selected and p['coverage'] == 'REQUIRED' else '') + '</section>'
    listed = {(r['id'], r['revision']) for p in view['personas'] for r in p['journeys']}
    unlisted = [j for j in view['journeys'] if (j['reference']['id'], j['reference']['revision']) not in listed]
    if unlisted:
        body += '<section><h2>Parcours à rattacher au catalogue</h2><ul>' + ''.join('<li><a href="journey-' + anchor(j['reference']) + '.html">' + h(j['name']) + '</a></li>' for j in unlisted) + '</ul></section>'
    return body + checklist(view) + '<p><a href="journeys.json">Catalogue complet, contrôles et sources exactes en JSON</a> · <a href="graph.html">Explorer les relations dans le graphe</a></p>'


def focus(j):
    from air.journey_map import render
    body = '<nav class="breadcrumb"><a href="journeys.html">Parcours par persona</a></nav><h1>' + h(j['name']) + '</h1><p class="intro">' + h(j['goal']) + '</p><p>Persona principal : ' + link(j['persona']) + '. ' + h(CATEGORIES[j['category']]) + '.</p><p><strong>Déclencheur :</strong> ' + h(j['trigger']) + '</p><p><strong>Résultat prévu :</strong> ' + h(j['outcome']) + '</p><ol class="journey-steps">'
    body = body.removesuffix('<ol class="journey-steps">') + render(j, focused=True) + '<details class="journey-provenance"><summary>Examiner le détail des étapes et les preuves des liens</summary><ol class="journey-steps">'
    for s in j['steps']:
        body += '<li><article><h2>' + h(s['name']) + '</h2><p class="view-eyebrow">' + h(s['channel']) + '</p><p>' + h(s['touchpoint']) + '</p>'
        if 'touchpoint_object' in s: body += '<p>Point de contact : ' + link(s['touchpoint_object']) + '. ' + h(s.get('touchpoint_purpose', '')) + '</p><p>Accessibilité : ' + h(s.get('accessibility', '')) + '</p>'
        body += '<p>Autres intervenants : ' + (', '.join(link(p) for p in s['participants']) or 'Non déclarés') + '</p><div class="usage-points">'
        for p in s['usage_points']:
            body += '<article class="usage-point"><h3>' + h(KINDS.get(p.get('kind'), 'Contexte non résolu')) + '</h3><p>' + link(p) + '</p><p>' + h(p.get('purpose', '')) + '</p><p>' + h(p.get('location_description', '')) + '</p><p>' + h(p.get('city', '')) + ' ' + h(p.get('country', '')) + '</p><p>' + ('Proposé' if p.get('status') == 'PROPOSED' else 'Confirmé selon déclaration' if p.get('status') == 'CONFIRMED_DECLARED' else 'À préciser') + '</p>'
            if p.get('parents'): body += '<p>Dans : ' + ', '.join(link(parent) for parent in p['parents']) + '</p>'
            body += '</article>'
        body += '</div><p><strong>Résultat de l’étape :</strong> ' + h(s.get('outcome', 'Non déclaré')) + '</p><p><strong>Irritants :</strong> ' + h('; '.join(s.get('pain_points', [])) or 'Non documentés') + '</p><details><summary>Éléments d’architecture et preuves des liens (' + str(len(s['architecture_links'])) + ')</summary><ul>'
        for a in s['architecture_links']:
            body += '<li>' + link(a) + ' <small>' + h(a['type']) + '</small><p>Source : <a href="objects.html#' + anchor(a['witness']) + '">' + h(a['witness']['id'].rsplit(':', 1)[-1]) + '</a>, champ <code>' + h(a['selector']) + '</code>, empreinte <code>' + h(a['witness']['digest']) + '</code>.</p></li>'
        body += '</ul></details><p>Étape déclarée dans ' + link(j) + ' au champ <code>' + h(s['selector']) + '</code>.</p></article></li>'
    return body + '</ol></details><p><a href="path-' + anchor(j['reference']) + '.html">Examiner le contexte technique du parcours et ses limites</a> · <a href="graph.html">Explorer le graphe</a></p><p>L’ordre des étapes est déclaré. Il ne démontre pas une exécution réelle, une causalité technique ou une validation par les utilisateurs.</p>'
