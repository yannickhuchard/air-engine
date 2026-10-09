"""Offline financial summary and source-linked Sankey reading surfaces."""
from collections import defaultdict
from fractions import Fraction
from decimal import Decimal
from html import escape as H
from air import financial_view
from air.deliverables import mid
KINDS = {'FUNCTIONAL':'Fonctionnelle', 'NON_FUNCTIONAL':'Non fonctionnelle', 'GAP':'À tracer',
    'ArchitectureBlock':'Bloc d’architecture', 'ConstructionUnit':'Unité de livraison', 'RuntimeComponent':'Production prévue',
    'DOCUMENT':'Document', 'MARKETING_CAMPAIGN':'Campagne marketing', 'REPORT':'Reporting', 'SERVICE':'Service', 'PRODUCT':'Produit'}
GAPS = {'ARCHITECTURE_BLOCK_MISSING':'Aucun bloc d’architecture relié', 'CONSTRUCTION_UNIT_MISSING':'Unité de livraison non reliée',
    'OUTPUT_MISSING':'Sortie de livraison non tracée', 'DELIVERY_AND_TARGET_MISSING':'Livraison et cible non tracées'}

def object_link(ref, label, root=''):
    if not ref: return H(label)
    return '<a href="' + root + 'objects.html#' + mid(ref['id'] + ':' + str(ref['revision'])) + '">' + H(label) + '</a>'


def finance_summary(view, href='finance.html'):
    cards = []
    for plan in view['plans']:
        cur = plan['programme_envelope']['currency']
        cards += [('<span>Enveloppe de trésorerie</span><strong>' + financial_view.fmt(plan['treasury_envelope']) + ' ' + cur + '</strong><small>' +
            str(plan['months']) + ' mois, réserve TVA incluse</small>'),
            ('<span>Contingence</span><strong>' + financial_view.fmt(plan['contingency_total']) + ' ' + cur + '</strong><small>Provision distincte des dépenses engagées</small>')]
    if not cards:
        cards = ['<span>Postes déclarés, sur leurs périodes</span><strong>' + financial_view.fmt(t['amount']) + ' ' + H(t['currency']) + '</strong><small>Enveloppe globale à documenter</small>' for t in view['totals']]
    state = 'Budget de référence approuvé' if view['plans'] and all(p['reference_status'] == 'APPROVED_REFERENCE' for p in view['plans']) else 'Budget de référence à examiner'
    funded = view['plans'] and all(p['funding_status'] == 'COMMITTED_DECLARED' for p in view['plans'])
    return ('<section class="finance-summary" aria-label="Dimension financière"><p class="view-eyebrow">Dimension financière</p><h2>Comprendre l’investissement</h2><p>' + state +
        '. ' + ('Financement déclaré, preuves à examiner.' if funded else 'Financement non confirmé.') + '</p><div class="financial-metrics">' + ''.join('<div>' + c + '</div>' for c in cards) +
        '</div><p>' + ('Aucun poste de coût déclaré. ' if not view['rows'] else '') + str(view['missing']['calculations']) + ' poste(s) sans décomposition quantitative. ' +
        ('Contingence à documenter. ' if view['missing']['contingency'] else '') + '</p><a class="question-action" href="' + H(href) + '">Lire le plan financier et chaque calcul</a></section>')


def finance_page(view, markdown):
    rendered, _ = markdown(financial_view.lines(view), 'finance')
    body = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Dimension financière</nav><h1>Dimension financière</h1><p class="intro">De l’enveloppe au prix unitaire, comprendre chaque montant et ses hypothèses.</p>' + finance_summary(view, '17-plan-financier.html') + rendered
    body += '<h2>Références des calculs</h2><ul>'
    for row in view['rows']:
        body += '<li>' + object_link(row['reference'], row['name']) + ' : ' + (', '.join(object_link(s, 'source r' + str(s['revision'])) for s in row['sources']) or 'sources quantitatives absentes') + '</li>'
    for plan in view['plans']:
        body += '<li>' + object_link(plan['reference'], plan['name'])
        if 'approval_source' in plan: body += ' ; ' + object_link(plan['approval_source'], 'source de l’approbation du budget de référence')
        body += '</li>'
    return body + '</ul><p><a href="finance.json">Projection financière structurée</a> · <a href="17-plan-financier.html">Sujet financier et toutes ses sources</a></p>'


def sankey_svg(view):
    if not view['nodes']: return '<p>Aucune exigence déclarée : tracer le besoin avant de dessiner ses livrables.</p>'
    if len(view['nodes']) > 250:
        return '<p>Le dossier dépasse 250 nœuds. Pour préserver la lisibilité, consulter les chemins par exigence ci-dessous et la projection complète ; aucun lien n’est supprimé du modèle.</p>'
    columns = defaultdict(list); weights = defaultdict(Fraction)
    for link in view['links']:
        value = Fraction(**link['value']); weights[(link['source'], 'out')] += value; weights[(link['target'], 'in')] += value
    scale = 20; gap = 22; positions = {}; height = 0
    for n in view['nodes']: columns[n['layer']].append(n)
    for layer in range(4):
        y = 70
        for n in columns[layer]:
            w = max(weights[(n['id'], 'in')], weights[(n['id'], 'out')]); h = max(46, float(w) * scale)
            positions[n['id']] = (layer * 290 + 16, y, h)
            y += h + gap
        height = max(height, y)
    outgoing = defaultdict(float); incoming = defaultdict(float); flows = []
    node_map = {n['id']: n for n in view['nodes']}
    memberships = defaultdict(set)
    for p in view['paths']:
        req = p['nodes'][0]
        for identity in p['nodes']: memberships[identity].add(req)
        for a, b in zip(p['nodes'], p['nodes'][1:]): memberships[(a, b)].add(req)
    for link in view['links']:
        a, b = link['source'], link['target']; x, y, h = positions[a]; tx, ty, th = positions[b]
        aw = float(weights[(a, 'out')]) * scale; bw = float(weights[(b, 'in')]) * scale
        y += (h - aw) / 2 + outgoing[a]; ty += (th - bw) / 2 + incoming[b]
        width = float(Fraction(**link['value'])) * scale; outgoing[a] += width; incoming[b] += width
        sx = x + 12; cx = (sx + tx) / 2
        d = f'M{sx},{y} C{cx},{y} {cx},{ty} {tx},{ty} L{tx},{ty+width} C{cx},{ty+width} {cx},{y+width} {sx},{y+width} Z'
        flows.append('<path class="sankey-flow" data-requirements="' + ' '.join(sorted(memberships[(a, b)])) + '" d="' + d + '"><title>' + H(node_map[a]['name'] + ' → ' + node_map[b]['name']) + '</title></path>')
    out = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1160 ' + str(height) + '" role="img" aria-labelledby="sankey-title sankey-description"><title id="sankey-title">Des exigences aux cibles prévues</title><desc id="sankey-description">Sankey de références déclarées. Les chemins et preuves textuels sont disponibles après le graphique.</desc>'
    for i, label in enumerate(['Exigences', 'Blocs d’architecture', 'Livraison', 'Cibles prévues']):
        out += '<text class="sankey-column" x="' + str(i * 290 + 16) + '" y="28">' + label + '</text>'
    out += ''.join(flows)
    for n in view['nodes']:
        x, y, h = positions[n['id']]; name = n['name'][:33] + ('…' if len(n['name']) > 33 else '')
        href = 'objects.html#' + mid(n['reference']['id'] + ':' + str(n['reference']['revision'])) if n['reference'] else None
        out += '<g class="sankey-node kind-' + H(n['kind'] if n['kind'] in ('GAP', 'FUNCTIONAL', 'NON_FUNCTIONAL') else 'BLOCK') + '" data-requirements="' + ' '.join(sorted(memberships[n['id']])) + '">'
        if href: out += '<a href="' + href + '" aria-label="' + H(n['name'] + ', ouvrir la source exacte') + '">'
        out += '<title>' + H(n['name'] + ' (' + n['kind'] + ')') + '</title><rect x="' + str(x) + '" y="' + str(y) + '" width="12" height="' + str(h) + '" rx="3"/><text x="' + str(x + 20) + '" y="' + str(y + 17) + '">' + H(name) + '</text><text class="sankey-kind" x="' + str(x + 20) + '" y="' + str(y + 35) + '">' + H(KINDS.get(n['kind'],n['kind'])) + '</text>'
        if href: out += '</a>'
        out += '</g>'
    return out + '</svg>'


def sankey_preview(view, href='traceability.html'):
    return '<section class="traceability-preview"><p class="view-eyebrow">Traçabilité du dossier</p><h2>Du besoin à ce qui sera livré</h2><ol class="trace-stages"><li>Exigences</li><li>Blocs d’architecture</li><li>Livrables</li><li>Cibles prévues</li></ol><p>' + str(view['requirements']) + ' exigences, ' + str(len(view['paths'])) + ' chemins déclarés, ' + str(len(view['gaps'])) + ' rupture(s) de traçabilité.</p><a class="question-action" href="' + H(href) + '">Explorer le Sankey et les preuves de chaque chemin</a></section>'


def sankey_page(view):
    nodes = {n['id']: n for n in view['nodes']}; grouped = defaultdict(list)
    for path in view['paths']: grouped[path['nodes'][0]].append(path)
    body = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Traçabilité</nav><h1>Du besoin aux cibles prévues</h1><p class="intro">Suivre les exigences fonctionnelles et non fonctionnelles jusqu’aux blocs, aux livrables et aux composants prévus en production.</p><div class="sankey-legend"><p><strong>Une unité par exigence applicable</strong>, répartie entre ses chemins. Bleu : fonctionnelle, violet : non fonctionnelle, ambre : rupture. Chaque lien décrit le design prévu.</p><details><summary>Lire la légende et les règles de traçabilité</summary><p>La largeur représente une répartition de chemins déclarés, sans mesure de coût, charge ou performance.</p><p>Les références intermédiaires sont jointes explicitement. Un composant de l’environnement PRODUCTION reste un design prévu. Les sorties de livraison peuvent être un produit, un service, un document, une campagne ou un rapport ; leur simple déclaration ne confirme pas leur exploitation.</p><p>Couleurs des exigences : fonctionnelles en bleu, non fonctionnelles en violet. Les ruptures sont signalées en ambre et dans le texte.</p></details></div>'
    body += '<label for="sankey-filter">Mettre en évidence une exigence</label><select id="sankey-filter"><option value="">Toutes les exigences</option>' + ''.join('<option value="' + H(k) + '">' + H(nodes[k]['name']) + '</option>' for k in grouped) + '</select><p id="sankey-status" role="status">Tous les chemins déclarés sont disponibles.</p><p class="sankey-hint">Faire défiler le graphique horizontalement pour lire les quatre colonnes. Les chemins textuels sont disponibles juste après.</p><div class="sankey-scroll" tabindex="0" aria-label="Sankey, défilement horizontal possible">' + sankey_svg(view) + '</div><h2>Les chemins et leurs sources</h2><p>Ouvrir une exigence pour lire chaque chemin et les champs qui le justifient. Les liens sont accessibles au clavier, avec ou sans JavaScript.</p>'
    for reqid, paths in grouped.items():
        req = nodes[reqid]
        body += '<details class="sankey-paths" data-requirement="' + reqid + '"><summary>' + H(req['name']) + ' (' + str(len(paths)) + ' chemins)</summary><p>' + object_link(req['reference'], 'Exigence source') + '</p>'
        for path in paths:
            body += '<article><ol class="trace-chain">' + ''.join('<li>' + object_link(nodes[k]['reference'], nodes[k]['name']) + '</li>' for k in path['nodes']) + '</ol><p>' + H({'GAP': 'Chemin incomplet', 'DECLARED_DELIVERABLE_OUTPUT': 'Sortie de livraison déclarée', 'PLANNED_PRODUCTION_COMPONENT': 'Composant de production prévu'}[path['status']]) + '.</p><details><summary>Références qui justifient ce chemin</summary><ul>'
            for ev in path['evidence']:
                target = object_link(ev['target'], ev['target']['id']) if 'id' in ev['target'] else H(ev['target']['name'] + ' (' + ev['target']['kind'] + ')')
                body += '<li>' + object_link(ev['source'], ev['source']['id']) + ' r' + str(ev['source']['revision']) + ' : <code>' + H(ev['field']) + '</code> → ' + target + (' ; statut déclaré ' + H(ev['status']) if ev['status'] else '') + '<br><code>' + ev['source_digest'] + '</code></li>'
            body += '</ul></details></article>'
        body += '</details>'
    body += '<h2>Ruptures et exclusions déclarées</h2><ul>'
    for gap in view['gaps']: body += '<li>' + object_link(gap['requirement'], gap['requirement']['id']) + ' : ' + H(GAPS.get(gap['reason'],gap['reason'])) + '</li>'
    for ex in view['exclusions']: body += '<li>' + object_link(ex['reference'], ex['reference']['id']) + ' : déclarée non applicable, selon ' + ', '.join(object_link(r, 'mapping source') for r in ex['mappings']) + '.</li>'
    return body + '</ul><p><a href="traceability.json">Projection complète et empreinte des chemins</a> · <a href="13-tracabilite.html">Sujet de traçabilité</a></p>'
