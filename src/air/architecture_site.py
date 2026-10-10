"""Static, offline, source-linked architecture dossiers. One topic per page.

Model text is escaped, never trusted Markdown/HTML. All diagrams retain their
source and use a pinned local Mermaid bundle with strict rendering and no network.
"""
from html import escape as H
from importlib import resources
import json
import re
from air.atelier import product, render_json, render_text
from air.core import digest
from air.deliverables import Graph, mid
from air import business_paths, graph_explorer, temporal_site, site_pwa, architecture_story, site_questions
from air import branding, site_handoff, site_handoff_html, question_capsule, question_capsule_html
from air.expr import artifact_digest
from functools import partial
from air import financial_view, traceability_sankey, site_finance_trace, journey_catalog, site_journeys, management_summary, transformation_view, project_updates
from air import journey_map, journey_visual, process_diagrams

ENGINE = 'air.architecture-site/1'
GROUPS = [
    ('Comprendre le projet', ['23', '02', '03', '14', '24']),
    ('Suivre les mécanismes', ['01', '04', '09', '10', '11', '29', '30']),
    ('Comprendre les données', ['18', '19', '20']),
    ('Examiner les choix et les impacts', ['25', '12', '15', '16', '13', '34', '35']),
    ('Préparer la réalisation', ['08', '21', '22', '26', '31', '05', '06', '07', '17', '27', '36', '37', '32', '33', '28']),
]
QUESTIONS = {
    '01': ('Quels composants portent la solution ?', 'Relier les composants, les contrats et les connexions à leurs responsabilités.'),
    '02': ('Quelle valeur le projet doit-il rendre ?', 'Lire la chaîne depuis son déclencheur jusqu’au résultat attendu.'),
    '03': ('Que cherche à accomplir chaque utilisateur ?', 'Suivre les points de contact, les opérations et les difficultés déclarées.'),
    '04': ('Comment le travail circule-t-il ?', 'Examiner les étapes, les participants et les conditions du processus.'),
    '05': ('Qui assume les responsabilités ?', 'Distinguer les rôles, leurs compétences et leur autorité déclarée.'),
    '06': ('Qui réalise et qui décide ?', 'Lire l’organisation de réalisation et les responsabilités RACI.'),
    '07': ('Qui exploitera la solution ?', 'Identifier les équipes et responsabilités prévues pour l’exploitation.'),
    '08': ('Comment construire, livrer et exploiter ?', 'Comparer les environnements prévus, sans confondre design et déploiement réel.'),
    '09': ('Qui appelle qui, et dans quel ordre ?', 'Lire les interactions déclarées. Une séquence ne prouve pas un comportement exécuté.'),
    '10': ('Comment les objets changent-ils d’état ?', 'Repérer déclencheurs, gardes et états terminaux.'),
    '11': ('Quelles règles orientent le parcours ?', 'Comprendre les conditions et branches prévues dans le modèle.'),
    '12': ('Sur quoi repose le raisonnement ?', 'Séparer hypothèses, inconnues, assertions et preuves.'),
    '13': ('Comment le besoin conduit-il à la réalisation ?', 'Relier exigences, fonctions, contrats, unités et vérifications.'),
    '14': ('Quelles capacités métier sont concernées ?', 'Comprendre les fonctions requises et les objectifs auxquels elles contribuent.'),
    '15': ('Qu’est-ce qui manque encore ?', 'Lire les écarts déclarés et les critères qui empêchent de préparer la construction.'),
    '16': ('Quels risques faut-il traiter ?', 'Examiner scénarios, traitements, cotations et conséquences déclarées.'),
    '17': ('Quelle enveloppe financer et pourquoi ?', 'Dimension financière : décomposer CAPEX, OPEX, contingence, trésorerie, quantités, prix et sources.'),
    '18': ('Que signifient les mots de ce dossier ?', 'Lire les concepts, leurs définitions, responsables et relations typées.'),
    '19': ('Quelles données la solution manipule-t-elle ?', 'Examiner entités, attributs, identités et relations sans supposer un stockage.'),
    '20': ('Comment ces données seront-elles stockées ?', 'Lire tables, colonnes, clés et index déclarés par composant de stockage.'),
    '21': ('Où les composants seront-ils placés ?', 'Suivre environnements, zones, réseaux et connexions.'),
    '22': ('Comment protéger la solution ?', 'Examiner zones de confiance, traversées et contrôles déclarés.'),
    '23': ('Pourquoi entreprendre ce projet ?', 'Comprendre les changements voulus et les résultats mesurables.'),
    '24': ('Quels principes guident les choix ?', 'Lire les raisons et implications des principes d’architecture.'),
    '25': ('Pourquoi ces choix, et avec quelles conséquences ?', 'Examiner options, décisions, raisons et conditions de révision.'),
    '26': ('Quelles technologies sont retenues ?', 'Distinguer technologies adoptées, en essai, à évaluer ou à éviter.'),
    '27': ('Quels jalons rythment la réalisation ?', 'Lire dates, livrables et critères de sortie déclarés.'),
    '28': ('Le design est-il prêt à construire ?', 'Lire les critères calculés et leurs limites, sans remplacer une approbation humaine.'),
    '29': ('Quels événements circulent ?', 'Identifier publications, canaux, garanties déclarées et consommateurs.'),
    '30': ('Comment naviguer dans l’interface conçue ?', 'Suivre écrans, transitions, personas et opérations.'),
    '31': ('Quels équipements hébergeront les composants ?', 'Lire implantation, capacité et équipements encore non affectés.'),
    '32': ('Quels parcours seront acceptés ?', 'Examiner les scénarios et leur rejeu sur le design avant construction.'),
    '33': ('Quels comportements faudra-t-il préserver ?', 'Lire le socle de non-régression et les tests à exécuter après construction.'),
    '34': ('Quels contrôles sont couverts ?', 'Relier exigences et contrôles aux mécanismes déclarés et aux vérifications.'),
    '35': ('Quels niveaux de qualité sont attendus ?', 'Examiner cibles, priorités et méthodes de vérification.'),
    '36': ('Comment l’outillage agentique affecte-t-il l’effort ?', 'Lire les estimations et leurs hypothèses, sans promettre un gain mesuré.'),
    '37': ('Quelles trajectoires de réalisation comparer ?', 'Examiner phases, dépendances, risques et alternatives déclarées.'),
}
CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'none'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'"
MAX_FILE = 4194304


def anchor(obj):
    return mid(obj['meta']['id'] + ':' + str(obj['meta']['revision']))


def inline(text):
    # Escape first; no arbitrary URLs, raw HTML or image syntax is interpreted.
    value = H(str(text))
    value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)


def markdown(lines, topic, display_title=None, diagram_renderer=None):
    """Render only AIR's generated subset. Return every diagram separately too."""
    out, diagrams, i, section = [], [], 0, display_title or topic
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            language = line[3:];code = [];i += 1
            while i < len(lines) and lines[i] != '```': code.append(lines[i]);i += 1
            raw = '\n'.join(code)
            if language == 'mermaid':
                n = len(diagrams) + 1
                diagrams.append({'number': n, 'title': section, 'code': raw})
                out.append(diagram_renderer(n, raw, section) if diagram_renderer else diagram(raw, f'diagram-{topic}-{n}.html', section))
            else: out.append('<pre><code>' + H(raw) + '</code></pre>')
        elif line.startswith('## '):
            section = line[3:];out.append('<h2>' + inline(section) + '</h2>')
        elif line.startswith('### '): out.append('<h3>' + inline(line[4:]) + '</h3>')
        elif line.startswith('| '):
            rows = []
            while i < len(lines) and lines[i].startswith('| '):
                cells = lines[i].strip('| ').split(' | ')
                if not all(re.fullmatch(r':?-+:?', c.strip()) for c in cells): rows.append(cells)
                i += 1
            out.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + inline(c) + '</th>' for c in rows[0]) + '</tr></thead><tbody>' +
                       ''.join('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in r) + '</tr>' for r in rows[1:]) + '</tbody></table></div>')
            continue
        elif line.startswith('- '):
            items = []
            while i < len(lines) and lines[i].startswith('- '): items.append('<li>' + inline(lines[i][2:]) + '</li>');i += 1
            out.append('<ul>' + ''.join(items) + '</ul>');continue
        elif line.strip(): out.append('<p>' + inline(line) + '</p>')
        i += 1
    return ''.join(out), diagrams


def diagram(code, link=None, title=None):
    return '<figure class="diagram"><figcaption>' + H(title or 'Diagramme du modèle') + ((' <a href="' + H(link) + '">Ouvrir ce diagramme</a>') if link else '') + '</figcaption>' + \
        '<div class="diagram-tools"><button type="button" data-zoom="in">Agrandir</button><button type="button" data-zoom="out">Réduire</button><button type="button" data-zoom="reset">Ajuster</button></div>' + \
        '<p class="diagram-status" role="status">Le diagramme sera dessiné à l’ouverture de la page.</p><div class="diagram-canvas"><pre class="mermaid">' + H(code) + '</pre></div>' + \
        '<details class="diagram-source"><summary>Lire la source du diagramme</summary><pre><code>' + H(code) + '</code></pre></details></figure>'


def legend():
    return '<details class="legend"><summary>Comprendre la légende et le niveau de preuve</summary><ul>' + \
        '<li>Flèches : liens ou flux déclarés ; leur libellé précise le sens. Une proximité visuelle ne signifie pas une interaction.</li>' + \
        '<li>PK : champ de clé primaire ou d’identité. FK : référence de colonne déclarée. Une multiplicité absente reste inconnue.</li>' + \
        '<li>Gardes : conditions du parcours. Les diagrammes de séquence décrivent les interactions, sans prouver leur exécution.</li>' + \
        '<li>Couleurs des objets reliés : bleu pour composants, violet pour données, vert pour fonctions/objectifs, ambre pour décisions/risques. Les types sont aussi indiqués en texte.</li>' + \
        '<li>DRAFT et hypothèse : déclarés. MET/PASS : résultat du contrôle nommé, dans sa portée. UNKNOWN, CONFLICTING, FAIL ou INCONCLUSIVE restent visibles.</li>' + \
        '<li>Cliquer sur un objet relié du graphe ouvre sa définition exacte. Les listes de sources restent accessibles au clavier.</li></ul></details>'


def sources(used):
    distinct = {(o['meta']['id'], o['meta']['revision']): o for o in used}
    return '<section class="sources"><h2>Objets et preuves de ce sujet</h2>' + (
        '<ul>' + ''.join('<li><a href="objects.html#' + anchor(o) + '">' + H(o['meta']['name']) + '</a> <span>' +
                        H(o['meta']['type'][4:]) + ' · révision ' + str(o['meta']['revision']) + '</span></li>' for _, o in sorted(distinct.items())) + '</ul>'
        if distinct else '<p>Aucun objet ne porte encore ce sujet. Il reste à le documenter.</p>') + '</section>'


def properties(value, g):
    if isinstance(value, dict):
        target = g.get(value) if 'id' in value and 'revision' in value else None
        if target: return '<a href="#' + anchor(target) + '">' + H(target['meta']['name']) + '</a> <small>r' + str(value['revision']) + '</small>'
        return '<dl>' + ''.join('<dt>' + H(k) + '</dt><dd>' + properties(v, g) + '</dd>' for k, v in value.items()) + '</dl>'
    if isinstance(value, list): return '<ul>' + ''.join('<li>' + properties(x, g) + '</li>' for x in value) + '</ul>' if value else '<span>Non déclaré</span>'
    return H(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)


def shell(title, body, project, nav, root, nodes=(), graph_data=None, temporal_data=None, story_data=None, brand=None, brand_root=None):
    profile = (brand or branding.normalize({}))['profile']
    brand_root = brand_root if brand_root is not None else root + 'branding/'
    image = brand_root + 'logo.svg' if 'logo_svg' in profile else root + 'assets/icon-192.svg'
    # Diagram anchors only need objects present on this page. The lossless
    # model and object catalogue remain complete; avoid copying the entire
    # registry's navigation envelope into every focus and topic page.
    nodes = [n for n in nodes if re.search(r'\b' + re.escape(n['node']) + r'\b', body)]
    data = json.dumps(list(nodes), ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    graph_script = '<script defer src="' + root + 'assets/graph.js"></script>' if graph_data is not None else ''
    graph_json = '<script type="application/json" id="air-graph">' + json.dumps(graph_data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026') + '</script>' if graph_data is not None else ''
    temporal_script = '<script defer src="' + root + 'assets/temporal.js"></script>' if temporal_data is not None else ''
    temporal_json = '<script type="application/json" id="air-temporal">' + json.dumps(temporal_data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026') + '</script>' if temporal_data is not None else ''
    story_script = '<script defer src="' + root + 'assets/story.js"></script>' if story_data is not None else ''
    story_json = '<script type="application/json" id="air-story">' + json.dumps(story_data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026') + '</script>' if story_data is not None else ''
    process_assets = ('<link rel="stylesheet" href="' + root + 'assets/bpmn-diagram.css"><script defer src="' + root + 'assets/bpmn-js-18.16.0.js"></script><script defer src="' + root + 'assets/process.js"></script>') if 'class="process-viewer"' in body else ''
    journey_assets = ('<link rel="stylesheet" href="' + root + 'assets/journey.css"><script defer src="' + root + 'assets/journey.js"></script>') if 'data-journey-visual' in body else ''
    return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + \
        '<meta http-equiv="Content-Security-Policy" content="' + H(CSP, quote=True) + '"><title>' + H(title + ' | ' + project) + '</title>' + \
        '<link rel="stylesheet" href="' + root + 'assets/site.css"><link rel="stylesheet" href="' + H(brand_root) + 'brand.css"><script defer src="' + root + 'assets/mermaid-12.1.0.js"></script>' + \
        '<meta name="theme-color" content="' + profile['colors']['header'] + '"><link rel="icon" href="' + H(image) + '" type="image/svg+xml">' + \
        '<script defer src="' + root + 'assets/site.js"></script><script defer src="' + root + 'assets/pwa.js"></script>' + graph_script + temporal_script + story_script + process_assets + journey_assets + '</head><body><a class="skip" href="#content">Aller au contenu</a>' + \
        '<header class="workspace-header"><a class="brand" href="' + root + 'index.html"><img src="' + H(image) + '" alt="" width="40" height="40"><span>' + H(profile['name']) + ' <small>' + H(profile['tagline']) + '</small></span></a><span class="project-name">' + H(project) + '</span>' + \
        '<details class="app-menu"><summary>Hors ligne</summary><div><p id="pwa-status" role="status">Ouverture directe du dossier. L’installation utilise une adresse locale.</p><p>Conserver ce site dans ce navigateur crée une copie de ses données d’architecture sur ce poste.</p>' + \
        '<button id="pwa-enable" type="button" hidden>Conserver hors ligne</button><button id="pwa-install" type="button" hidden>Installer l’application</button><button id="pwa-update" type="button" hidden>Appliquer la nouvelle version</button><button id="pwa-clear" type="button" hidden>Effacer la copie hors ligne</button></div></details></header>' + \
        '<div class="layout"><aside aria-label="Navigation des dossiers"><details class="workspace-nav" open><summary>Explorer les dossiers</summary><nav aria-label="Sujets d’architecture">' + nav + '</nav></details></aside><main id="content" tabindex="-1">' + body + '</main></div>' + \
        '<footer>Conception et simulation pour une réalisation ultérieure. Cet export statique contient des données : sa diffusion reste limitée aux destinataires autorisés.</footer>' + \
        '<script type="application/json" id="air-nodes">' + data + '</script>' + graph_json + temporal_json + story_json + '</body></html>'


def navigation(topics, active=''):
    parts = ['<a class="dossier-home" href="news.html">News, décisions et questions ouvertes</a>', '<a class="dossier-home" href="management-summary.html">Management Summary</a>',
             '<a class="dossier-home" href="index.html">Vue d’ensemble du dossier</a>',
             '<a class="dossier-home" href="transformation.html">Programmes, projets et tâches</a>',
             '<a class="dossier-home" href="journeys.html">Parcours par persona et usages</a>',
             '<a class="dossier-home" href="processes.html">Processus en couloirs</a>',
             '<a class="dossier-home" ' + ('aria-current="page" ' if active == 'finance' else '') + 'href="finance.html">Dimension financière</a>',
             '<a class="dossier-home" ' + ('aria-current="page" ' if active == 'traceability' else '') + 'href="traceability.html">Du besoin aux livrables : Sankey</a>',
             '<a class="dossier-home" href="questions.html">Trouver une réponse</a>',
             '<a class="dossier-home" ' + ('aria-current="page" ' if active == 'cooperate' else '') + 'href="cooperate.html">Travailler avec un assistant</a>',
             '<a class="dossier-home" ' + ('aria-current="page" ' if active.startswith('handoff') or active.startswith('diagram-handoff') else '') + 'href="handoff.html">Préparer la réalisation</a>',
             '<details' + (' open' if active.startswith('role-') else '') + '><summary>Mon parcours de lecture</summary><ul>' + ''.join(
                 '<li><a ' + ('aria-current="page" ' if active == 'role-' + role else '') + 'href="role-' + role + '.html">' + H(label) + '</a></li>'
                 for role, label, _, _ in site_questions.ROLES) + '</ul></details>']
    by_prefix = {t['name'][:2]: t for t in topics}
    for group, prefixes in GROUPS:
        entries = [by_prefix[p] for p in prefixes if p in by_prefix]
        if entries:
            parts.append('<details' + (' open' if any(t['name'] == active for t in entries) else '') + '><summary>' + H(group) + '</summary><ul>' + ''.join(
                '<li><a ' + ('aria-current="page" ' if t['name'] == active else '') + 'href="' + t['name'] + '.html">' + H(t['title']) + '</a></li>' for t in entries) + '</ul></details>')
    return '<a class="dossier-home" href="story.html">Lire l’architecture story</a><a class="dossier-home" href="graph.html">Explorer le graphe 2D</a><br><a href="../../timeline.html">Comparer les états et les dates</a>' + ''.join(parts) + '<a href="business-paths.html">Suivre les parcours métier</a><br><a href="objects.html">Explorer les objets et leur ontologie</a>'


def reading_routes(root=''):
    return '<div class="reading-routes">' + ''.join(
        '<a class="reading-route" href="' + root + 'role-' + role + '.html"><strong>' + H(label) + '</strong><span>' + H(purpose) + '</span></a>'
        for role, label, purpose, _ in site_questions.ROLES) + '</div>'


def dossier_card(d):
    """The project index explains the declared purpose, with its exact source."""
    base = d['path'].removesuffix('index.html')
    purpose = d['purpose']
    text = H(purpose['text'][:500]) + ('…' if len(purpose['text']) > 500 else '')
    source = '<p class="dossier-source-link"><a href="' + base + 'objects.html#' + purpose['anchor'] + '">Lire la déclaration source</a></p>' if purpose.get('anchor') else ''
    return '<article class="dossier"><div class="dossier-description"><p class="dossier-state">Conception, révision ' + str(d['baseline']['revision']) + '</p><h2><a href="' + d['path'] + '">' + H(d['name']) + '</a></h2><p class="dossier-purpose">' + text + '</p>' + source + '</div><div class="dossier-actions"><p class="dossier-gate">' + H(site_questions.GATE_LABELS.get(d['gate'], d['gate'])) + '</p><a class="dossier-explore" href="' + d['path'] + '">Comprendre ce dossier</a><a href="' + d['graph'] + '">Lire la carte d’architecture</a><a href="' + d['questions'] + '">Trouver une réponse</a></div><details class="dossier-context"><summary>Sujets et contexte exact</summary><p>' + str(d['topics']) + ' sujets, ' + str(d['diagrams']) + ' diagrammes.</p><p><code>' + H(d['baseline']['id']) + '</code>, révision ' + str(d['baseline']['revision']) + ', <code>' + d['baseline']['digest'] + '</code>.</p></details></article>'


def question_page(model, g, role=None):
    selected = next((r for r in model['roles'] if r['id'] == role), None)
    title = selected['label'] if selected else 'Les questions du dossier'
    purpose = selected['purpose'] if selected else 'Rechercher une question, un sujet ou une source déclarée.'
    body = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Parcours de lecture</nav><h1>' + H(title) + '</h1><p class="intro">' + H(purpose) + '</p>'
    if role == 'realisation':
        body += '<p><a class="question-action" href="handoff.html">Ouvrir les fiches par composant et par équipe</a></p>'
    body += '<p><a href="finance.html">Dimension financière et détail de l’investissement</a> · <a href="traceability.html">Traçabilité des exigences et des livrables</a></p>'
    body += '<p class="gate">' + H(model['gate']['label']) + '. <a href="28-preparation-construction.html">Lire les critères calculés</a>.</p><p>Ces parcours facilitent la lecture. Ils ne filtrent pas les données du site et ne remplacent ni la validation des équipes ni une autorisation d’accès.</p>'
    body += '<label for="question-search">Rechercher dans les questions et leurs sources</label><input id="question-search" type="search"><p id="question-search-status" role="status"></p><div class="question-list">'
    by_id = {q['id']: q for q in model['questions']}
    ordered = [by_id[i] for i in selected['questions'] if i in by_id] if selected else model['questions']
    for q in ordered:
        state = 'Contrôle calculé' if q['state'] == 'CALCULATED' else 'À compléter' if q['state'] == 'PARTIAL' else 'Des sources sont déclarées' if q['sources'] else 'À documenter'
        body += '<section class="question-card" id="q' + q['id'] + '"><p class="question-state">' + state + '</p><h2><a href="' + q['topic'] + '">' + H(q['question']) + '</a></h2><p>' + H(q['purpose']) + '</p><p><a href="cooperate.html?topic=' + q['id'] + '&amp;audience=' + (role or 'solution') + '">Discuter cette question avec un assistant</a></p>'
        if q['state'] == 'CALCULATED':
            body += '<p><strong>Résultat</strong> : ' + H(model['gate']['label']) + '. Ce contrôle porte sur le design exact ; il ne vaut pas approbation humaine ni exécution de la future solution.</p><details><summary>Examiner les critères et les prochaines actions</summary><ul>' + ''.join(
                '<li><strong>' + H(c['label']) + '</strong> : ' + H({'MET': 'tenu', 'NOT_MET': 'non tenu', 'NOT_APPLICABLE': 'sans objet'}.get(c['status'], c['status'])) + '. ' + H(c['detail']) + ('<p>Pour avancer : ' + H(c['next_action']) + '</p>' if c['status'] == 'NOT_MET' else '') + '</li>'
                for c in model['calculated_criteria']) + '</ul></details>'
        if q['missing_dimensions']:
            body += '<p><strong>Dimensions non documentées</strong> : ' + H('; '.join(q['missing_dimensions'])) + '. À recueillir avec les responsables du sujet.</p>'
        if q['sources']:
            previews = [(s, statement) for s in q['sources'] for statement in s['statements']]
            for source, statement in previews[:2]:
                body += '<p class="question-answer"><strong>' + H(statement['label']) + '</strong> (déclaration) : ' + H(statement['text'][:500]) + ('…' if len(statement['text']) > 500 else '') + ' <a href="objects.html#' + anchor(g.get(source['reference'])) + '">Source : ' + H(source['name']) + '</a>.</p>'
            body += '<p><strong>Ce que le dossier fournit</strong> : ' + str(len(q['sources'])) + ' objet(s) source. Leur présence ne prouve pas que la réponse est complète, validée ou mise en œuvre.</p><details><summary>Lire les déclarations et leurs sources exactes</summary><ul>'
            for source in q['sources']:
                target = g.get(source['reference'])
                body += '<li><a href="objects.html#' + anchor(target) + '">' + H(source['name']) + '</a> <small>' + H(source['type'][4:]) + ' · r' + str(source['reference']['revision']) + ' · ' + H(source['lifecycle']) + '</small><p>' + H(source['description']) + '</p></li>'
            body += '</ul></details><p><strong>Prochaine action</strong> : examiner le sujet détaillé et ses preuves avec les équipes concernées ; préciser les engagements qui restent ouverts.</p>'
        elif q['state'] != 'CALCULATED':
            body += '<p><strong>Information manquante</strong> : aucun objet source de ce sujet n’est présent dans cette baseline. Cela ne signifie ni un coût nul, ni une absence de risque, ni une responsabilité attribuée.</p><p><strong>Prochaine action</strong> : recueillir les informations avec les équipes concernées, nommer les responsables et consigner les preuves avant de figer une nouvelle révision.</p>'
        body += '<a class="question-action" href="' + q['topic'] + '">Examiner le sujet et ses diagrammes</a></section>'
    body += '</div><details class="reading-context"><summary>Contexte exact de cette lecture</summary><p>Baseline <code>' + H(model['baseline']['id']) + '</code>, révision ' + str(model['baseline']['revision']) + '.</p><p>Empreinte : <code>' + model['baseline']['digest'] + '</code>.</p><p>Ces sources décrivent une conception pour sa réalisation ultérieure. Les responsabilités de rédaction ne sont pas déduites du lecteur choisi.</p><a href="questions.json">Télécharger les questions et leurs références exactes</a></details>'
    return body


def graph_page(data, g, paths):
    links = {node['id']: 'objects.html#' + anchor(g.get(node['reference'])) for node in data['nodes']}
    family_choices = ''.join('<label class="graph-choice"><input type="checkbox" data-graph-family="' + f['id'] + '" ' + ('checked' if f['id'] in ('behavior', 'interface', 'component') else '') + '><span class="graph-swatch family-' + f['id'] + '"></span>' + H(f['label']) + '</label>' for f in data['families'])
    relation_choices = ''.join('<label class="graph-choice"><input type="checkbox" data-graph-kind="' + k + '" ' + ('checked' if k not in ('CONTEXT', 'PROVENANCE', 'COMPOSITION') else '') + '>' + H(v) + '</label>' for k, v in data['relation_kinds'].items())
    objects = ''.join('<option value="' + n['id'] + '">' + H(n['name']) + ' (' + H(n['type'][4:]) + ')</option>' for n in data['nodes'])
    types = ''.join('<option value="' + H(t, quote=True) + '">' + H(t[4:]) + '</option>' for t in sorted({n['type'] for n in data['nodes']}))
    path_choices = ''.join('<option value="' + str(i) + '">' + H(p['name']) + '</option>' for i, p in enumerate(paths))
    body = '<div class="graph-view"><nav class="breadcrumb"><a href="index.html">Dossier</a> / Carte d’architecture</nav><h1>Carte d’architecture</h1><p class="intro">Choisissez un angle, puis un objet ou une relation pour lire sa source.</p>'
    body += '<div class="graph-toolbar" hidden><div class="graph-presets" role="group" aria-label="Angle de lecture">' + ''.join('<button type="button" data-graph-preset="' + key + '" aria-pressed="' + ('true' if key == 'solution' else 'false') + '">' + title + '</button>' for key, title in [('business', 'Besoins'), ('solution', 'Solution'), ('data', 'Données'), ('delivery', 'Réalisation')]) + '</div><label for="graph-search">Chercher un objet</label><input type="search" id="graph-search">'
    body += '<details id="graph-filters"><summary>Ajuster les objets, parcours et relations</summary><div class="graph-search-row"><label>Objet à examiner<select id="graph-object"><option value="">Vue d’ensemble</option>' + objects + '</select></label><label>Parcours déclaré<select id="graph-path"><option value="">Aucun parcours</option>' + path_choices + '</select></label><label>Type d’objet<select id="graph-type"><option value="">Tous les types</option>' + types + '</select></label></div><div class="graph-actions"><label><input type="checkbox" id="graph-neighbors" checked> Limiter à l’objet et ses voisins directs</label><label><input type="checkbox" id="graph-only-path"> Limiter au parcours choisi</label></div><fieldset><legend>Couches de lecture</legend>' + family_choices + '</fieldset><details><summary>Types de relations</summary><fieldset><legend>Le libellé précise le sens de la flèche</legend>' + relation_choices + '</fieldset></details><div class="graph-actions"><label><input type="checkbox" id="graph-motion" checked> Déplacements animés</label><button type="button" id="graph-reset">Revenir à la vue initiale</button></div><p>Le réglage de mouvement réduit de votre système est respecté. Le point de lecture initial ne désigne pas un début de processus métier.</p></details></div>'
    body += '<p id="graph-path-status" role="status"></p><div class="graph-workspace"><div><div class="graph-camera" hidden><button type="button" data-graph-zoom="in">Zoom +</button><button type="button" data-graph-zoom="out">Zoom -</button><button type="button" data-graph-zoom="fit" aria-label="Cadrer tous les objets visibles">Cadrer</button><button type="button" id="graph-center" aria-label="Centrer l’objet sélectionné">Centrer</button></div><div class="graph-map" hidden><div id="graph-canvas" class="graph-canvas" tabindex="0" aria-label="Graphe 2D. Glisser le fond pour déplacer ; utiliser les boutons ou les touches plus, moins et flèches pour naviguer."></div><div class="graph-overview-box"><span>Vue globale</span><div id="graph-overview"></div></div></div><p id="graph-status" role="status">Activez JavaScript pour manipuler la carte. Les objets et le JSON restent accessibles ci-dessous.</p><p class="graph-help">Les flèches sont typées : une référence n’est pas un appel. Les branches restent potentielles, sans évaluation des gardes. Entrez dans un objet au clavier ou choisissez-le dans les filtres.</p></div><section id="graph-detail" class="graph-detail" aria-label="Objet et relations sélectionnés"><h2>Lire un objet</h2><p>Choisissez une définition ou une relation pour examiner ses sources exactes.</p></section></div>'
    body += '<details class="legend"><summary>Légende, contexte et limites de la carte</summary><ul><li>Couleurs des objets : composants bleus, données violettes, fonctions vertes, choix et risques ambre. Le type est aussi écrit.</li><li>Trait discontinu : référence, périmètre ou provenance. Bleu : réalisation ou fonction prévue. Violet : flux de données ou relation de concepts. Vert : contrôle du workflow. Gris : connexion prévue.</li><li>La position et la proximité n’impliquent pas une interaction. Le voisinage initial est une sélection de lecture ; les filtres ne retirent rien du modèle exact.</li><li>La surbrillance d’un parcours ne prouve pas une chaîne d’appels, sa causalité ni l’invocation d’un workflow associé.</li><li>Au plus 180 objets et 1 000 relations sont dessinés ; les compteurs signalent les limites. La liste et le JSON conservent la portée complète.</li><li>La lecture en trois étapes explique une seule relation déclarée ; elle n’est pas une simulation ni une trace d’exécution.</li></ul><p>Baseline <code>' + H(data['baseline']['id']) + '</code>, révision ' + str(data['baseline']['revision']) + '. Empreinte <code>' + data['baseline']['digest'] + '</code>.</p></details>'
    body += '<p><a href="graph.json">Télécharger le graphe exact et ses sources</a> · <a href="objects.html">Lire toutes les définitions</a></p><details><summary>Liste complète des objets et étapes</summary><ul>' + ''.join('<li><a href="' + links[n['id']] + '">' + H(n['name']) + '</a> · ' + H(n['type'][4:]) + ' · r' + str(n['reference']['revision']) + '</li>' for n in data['nodes']) + '</ul></details></div>'
    return body, links


GAP_LABELS = {
    'WORKFLOW_ASSOCIATION_IS_NOT_CAUSAL_CONTINUATION': 'Ce workflow partage des références ; son invocation par le parcours choisi n’est pas établie.',
    'CONDITION_NOT_FORMALIZED': 'Condition décrite en texte, sans garde formalisée.',
    'CONTROL_PATHS_TRUNCATED': 'Les limites de lecture ne permettent pas de montrer tous les chemins.',
    'PARALLEL_JOIN_REQUIRES_SIMULATION': 'Une synchronisation ALL nécessite la simulation pour examiner les branches ensemble.',
    'COMPENSATION_ORDER_UNDECLARED': 'Les fonctions de compensation sont déclarées, leur ordre et leurs déclencheurs ne le sont pas.',
    'UNREACHABLE_STEPS': 'Certaines étapes ne sont pas atteignables depuis les entrées déclarées.',
    'FUNCTION_COMPONENT_UNDECLARED': 'Aucun composant de réalisation n’est déclaré pour cette fonction.',
    'FUNCTION_OPERATION_UNDECLARED': 'Aucune opération de contrat n’est déclarée pour cette fonction.',
    'ERROR_REFERENCE_IS_NOT_CONTROL_FLOW': 'Un mode d’échec est référencé ; sa présence ne définit pas une branche de workflow.',
    'COMPONENT_DATA_FLOW_UNDECLARED': 'Aucun flux de données explicite n’est déclaré pour ce composant.',
    'ORDERED_WORKFLOW_UNDECLARED_FOR_CONTEXT': 'Aucun workflow ordonné n’est relié dans ce contexte.',
    'CONTEXT_TRUNCATED': 'Le contexte est limité ; consulter le modèle exact ou élargir la requête.',
    'EXACT_REFERENCE_MISSING': 'Une référence exacte est absente du contexte.',
}


def path_story(result, g):
    text = '<p class="intro">Suivre les étapes déclarées et comprendre quels composants, contrats et données leur sont associés.</p>' + \
        '<p>Les chemins de contrôle sont potentiels : les conditions ne sont pas évaluées. Les liens de référence, de réalisation et de transport ne prouvent pas une chaîne d’appels métier.</p>'
    for workflow in result['workflows']:
        text += '<section><h2>' + H(workflow['source']['name']) + '</h2><p>' + ('Workflow choisi.' if workflow['relationship_to_root'] == 'SELECTED_WORKFLOW' else 'Workflow associé par références. Cette association ne prouve pas son invocation.') + '</p><p>' + H(workflow['termination_policy']) + '</p><ol>'
        steps = {s['id']: s for s in workflow['steps']}
        for path in workflow['paths']:
            text += '<li>' + ' → '.join(H(steps[s]['name']) for s in path['steps']) + ' <strong>' + H(path['outcome']) + '</strong></li>'
        text += '</ol><p>La liste montre des branches, pas un ordre d’exécution des branches parallèles. Voir <a href="04-processus-metier.html">les diagrammes de processus</a>.</p>'
        text += '<h3>Fonctions et participants de chaque étape</h3><ol>'
        for step in workflow['steps']:
            join = {'ALL': 'Toutes les entrées requises', 'ANY': 'Une entrée suffit'}.get(step.get('join'), 'Pas de jointure explicite dans cette étape')
            text += '<li><strong>' + H(step['name']) + '</strong>' + properties({'Fonction': step['function'], 'Participants': step['participants'], 'Synchronisation': join}, g) + '</li>'
        text += '</ol><details><summary>Branches et gardes exactes</summary>' + properties(workflow['flows'], g) + '</details></section>'
    for field, title in [('journeys', 'Points de contact utilisateur'), ('value_streams', 'Chaînes de valeur'),
                         ('contracts', 'Opérations et modes d’échec'), ('bindings', 'Canaux et bindings de transport'),
                         ('data_flows', 'Flux de données directionnels'), ('connections', 'Connexions prévues')]:
        if result[field]:
            text += '<section><h2>' + title + '</h2>' + ''.join('<details><summary>' + H(d['source']['name']) + '</summary>' + properties(d['declared'], g) + '</details>' for d in result[field]) + '</section>'
    text += '<section><h2>Ce qui manque ou nécessite une autre vérification</h2>'
    text += '<ul>' + ''.join('<li><strong>' + H(GAP_LABELS.get(gap['code'], gap['code'])) + '</strong>' + properties({k: v for k, v in gap.items() if k != 'code'}, g) + '</li>' for gap in result['gaps']) + '</ul>' if result['gaps'] else '<p>Aucune lacune détectée par ces contrôles limités. La complétude et la causalité métier ne sont pas vérifiées.</p>'
    text += '</section><section><h2>Objets associés et sources exactes</h2><ul>'
    for node in result['context_graph']['nodes']:
        obj = g.get(node['reference'])
        text += '<li><a href="objects.html#' + anchor(obj) + '">' + H(node['name']) + '</a> · ' + H(node['type'][4:]) + ' · r' + str(node['reference']['revision']) + '</li>'
    return (text + '</ul></section>').replace('href="#', 'href="objects.html#')


def story(g):
    content = []
    sections = [('Pourquoi ce projet', 'Intent', 'desired_change'), ('Résultats attendus', 'Goal', 'outcome'),
                ('Valeur à rendre', 'ValueStream', 'value'), ('Parcours à comprendre', 'CustomerJourney', 'goal')]
    for title, kind, field in sections:
        objects = g.of(kind)
        content.append('<section><h2>' + title + '</h2>' + ('<ul>' + ''.join('<li><strong>' + H(o['meta']['name']) + '</strong> : ' + H(o['body'][field]) + '</li>' for o in objects) + '</ul>' if objects else '<p>Ce point n’est pas encore déclaré dans le dossier.</p>') + '</section>')
    decisions = g.of('Decision')
    content.append('<section><h2>Choix et conséquences</h2>' + ('<ul>' + ''.join('<li><strong>' + H(o['meta']['name']) + '</strong> : ' + H(o['body'].get('rationale', 'Raison non déclarée')) +
        '<ul>' + ''.join('<li>' + H(str(c)) + '</li>' for c in o['body'].get('consequences', [])) + '</ul></li>' for o in decisions) + '</ul>' if decisions else '<p>Aucune décision n’est déclarée. Lire les écarts avant de considérer les choix comme acquis.</p>') + '</section>')
    open_objects = g.of('Unknown') + g.of('Assumption') + g.of('ArchitectureGap') + g.of('Risk')
    content.append('<section><h2>Questions ouvertes et risques déclarés</h2>' + ('<ul>' + ''.join('<li><a href="objects.html#' + anchor(o) + '">' + H(o['meta']['name']) + '</a> : ' +
        H(o['body'].get('question', o['body'].get('statement', o['body'].get('scenario', o['body'].get('impact', o['meta']['description']))))) +
        ('<p>Conséquence déclarée : ' + H(o['body']['impact_if_false']) + '</p>' if 'impact_if_false' in o['body'] else '') + '</li>' for o in open_objects) + '</ul>' if open_objects else '<p>Aucun objet de ce type n’est déclaré ; cela ne démontre pas l’absence de risque ou d’inconnue.</p>') + '</section>')
    return ''.join(content)


def architecture_story_page(model, g):
    body = '<nav class="breadcrumb"><a href="index.html">Dossier</a></nav><h1>Architecture story</h1><p class="intro">' + H(model['name']) + '</p><p>Du besoin à la réalisation : six angles de lecture du même design. L’ordre du récit est une présentation ; il ne décrit pas une exécution métier.</p>'
    body += '<div class="story-controls" hidden><button type="button" id="story-play">Lire le récit court</button><label for="story-seek">Position dans le récit (secondes)</label><input id="story-seek" type="range" min="0" max="24" value="0" step="0.1"><output id="story-clock" for="story-seek">0 / 24 s</output><p id="story-status" role="status">Animation narrative. Les conditions ne sont pas évaluées.</p></div>'
    body += '<nav class="story-chapters" aria-label="Chapitres du récit">' + ''.join('<a href="#story-' + p['id'] + '" data-story-chapter="' + p['id'] + '">' + str(i+1) + '. ' + H(p['title']) + '</a>' for i,p in enumerate(model['phases'])) + '</nav><div class="story-reader">'
    for phase in model['phases']:
        body += '<section class="story-chapter" id="story-' + phase['id'] + '"><p class="eyebrow">' + H(phase['id'].upper()) + '</p><h2>' + H(phase['title']) + '</h2><p>' + H(phase['explanation']) + '</p><div class="story-cards">'
        for entry in phase['entries']:
            source = entry['source']; obj = g.get(source)
            body += '<article class="story-card"><p class="story-type">' + H(source['type'][4:]) + ' · r' + str(source['revision']) + '</p><h3><a href="objects.html#' + anchor(obj) + '">' + H(source['name']) + '</a></h3><p>' + H(entry['description']) + '</p>'
            for field in entry['fields']:
                value = field['value']; text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                body += '<details><summary>' + H(field['selector']) + '</summary><p>' + H(text[:300]) + ('… <em>Extrait ; ouvrir la source pour la propriété complète.</em>' if len(text) > 300 else '') + '</p></details>'
            body += '</article>'
        body += '</div>'
        if phase['empty']: body += '<p>Aucun objet de ces types n’est déclaré dans cette baseline. Ce chapitre ne démontre pas l’absence de besoin.</p>'
        if phase['omitted_entries']: body += '<p>' + str(phase['omitted_entries']) + ' objet(s) supplémentaires : consulter le modèle complet.</p>'
        if phase['id'] == 'mechanism':
            for path in model['potential_paths']:
                body += '<article class="story-path"><h3>' + H(path['source']['name']) + '</h3><p>Branche de contrôle potentielle · gardes non évaluées · ' + H(path['outcome']) + '</p><ol>' + ''.join('<li>' + H(s['name']) + '</li>' for s in path['steps']) + '</ol></article>'
            body += '<p><a href="business-paths.html">Examiner toutes les branches disponibles, gardes, participants et lacunes</a>. La lecture courte peut omettre des branches ; elle ne reconstitue pas les synchronisations parallèles.</p>'
        if phase['id'] == 'evolution':
            body += '<p>' + str(len(model['comparisons'])) + ' comparaison(s) explicitement choisie(s) pour cet état. <a href="../../timeline.html">Lire les différences et le calendrier déclaré</a>.</p>'
        if phase['id'] == 'next':
            body += '<p class="gate">Préparation à la construction : <strong>' + H(model['readiness']['result']) + '</strong></p><p><a href="28-preparation-construction.html">Lire les critères et blocages calculés</a>. Le film ne fournit aucune preuve supplémentaire de simulation ou de réception.</p>'
        body += '</section>'
    body += '</div><section><h2>Sources et vidéo</h2><p>Le mode court suit Hook → Reveal → Highlights → Outro en 24 secondes. Les chapitres Données et Évolution restent disponibles dans la lecture complète.</p><p>Le skill <code>architecture-story</code> prépare les compositions vidéo à partir de ce même modèle, puis BRAG et Hyperframes produisent les MP4 en option. Aucun outil vidéo n’est requis pour installer AIR.</p><p><a href="story.json">Télécharger le modèle de récit exact</a> · <a href="../../architecture-model.json">Télécharger toute l’ontologie et ses modèles</a></p><p>Empreinte du récit : <code>' + H(model['story_digest']) + '</code></p></section>'
    return body


def temporal_page(data, dossiers, exports):
    links = {}
    states = []
    for snapshot, dossier, exported in zip(data['snapshots'], dossiers, exports):
        parent = dossier['path'].rsplit('/', 1)[0]
        object_links = {anchor(o): parent + '/objects.html#' + anchor(o) for o in exported['objects']}
        ref_links = {o['meta']['id'] + '\u0000' + str(o['meta']['revision']): object_links[anchor(o)] for o in exported['objects']}
        links[dossier['baseline']['digest']] = {'objects': ref_links, 'graph': dossier['graph'], 'dossier': dossier['path']}
        states.append('<details><summary>' + H(snapshot['name']) + ' - r' + str(snapshot['baseline']['revision']) + '</summary><p>' + H(snapshot['namespace']) + '</p><ul>' + ''.join(
            '<li><a href="' + ref_links[o['reference']['id'] + '\u0000' + str(o['reference']['revision'])] + '">' + H(o['name']) + '</a> r' + str(o['reference']['revision']) +
            ' - validité déclarée [' + H(o['validity']['start']) + ', ' + H(o['validity']['end'] or 'fin non déclarée') + ')</li>' for o in snapshot['objects']) + '</ul>' +
            '<h3>Calendrier prévu</h3>' + ('<ul>' + ''.join('<li>' + H(p['name']) + ' : ' + H(p['start']) + (' → ' + H(p['end']) if p['end'] else '') + '</li>' for p in snapshot['plans']) + '</ul>' if snapshot['plans'] else '<p>Aucun jalon ou phase de roadmap déclaré.</p>') + '</details>')
    comparisons = '<ul>' + ''.join('<li>' + H(c['title']) + ' : ' + ', '.join(str(v) + ' ' + H(data['change_labels'][k]) for k,v in c['summary'].items() if v) + '</li>' for c in data['comparisons']) + '</ul>' if data['comparisons'] else '<p>Aucune paire d’états n’a été choisie pour comparaison. Épingler les deux baselines et déclarer la paire dans la requête de livrables.</p>'
    body = '<h1>Comprendre les changements et les dates</h1><p class="intro">Comparer les designs choisis, puis situer leur validité et les jalons prévus.</p>' + \
        '<p>Les états restent des baselines exactes. Les dates de validité et le calendrier prévu sont des déclarations ; aucun déploiement ou comportement métier n’est prouvé ici.</p>' + \
        '<section id="temporal-interactive" hidden><h2>Comparer deux états choisis</h2><label for="temporal-comparison">Comparaison déclarée</label><select id="temporal-comparison"></select><p id="temporal-comparison-status" role="status"></p><div id="temporal-state-links"></div>' + \
        '<div class="temporal-filter"><label for="temporal-search">Rechercher un objet ou un type</label><input type="search" id="temporal-search"><label for="temporal-kind">Changements à afficher</label><select id="temporal-kind"></select></div><p id="temporal-diff-count" role="status"></p><div class="temporal-workspace"><div id="temporal-diff" class="temporal-diff"></div><section id="temporal-detail" class="graph-detail" aria-label="Détail du changement"><h3>Lire un changement</h3><p>Sélectionnez une ligne pour examiner les champs et les sources exactes.</p></section></div>' + \
        '<h2>Validité déclarée du design</h2><label for="temporal-snapshot">État à examiner</label><select id="temporal-snapshot"></select><label for="temporal-boundary">Instant de validité, en UTC</label><select id="temporal-boundary"></select><input id="temporal-slider" type="range" min="0" value="0" aria-label="Parcourir les frontières de validité déclarée"><p id="temporal-validity-status" role="status"></p><div id="temporal-validity"></div>' + \
        '<h2>Calendrier de transformation prévu</h2><p>Ces jalons et phases n’établissent pas qu’un composant a été réalisé, déployé ou arrêté.</p><div id="temporal-plans"></div></section>' + \
        '<details class="legend"><summary>Comprendre les axes de temps et la légende</summary><ul><li>Comparaison : deux états exacts explicitement choisis, sans ordre chronologique inféré de leur nom.</li><li>Validité : intervalle déclaré avec début inclus et fin exclue. Le curseur parcourt ses frontières ; filtrer ne recrée pas une baseline fermée.</li><li>Calendrier : dates prévues de Milestone et Roadmap, sans réalisation inférée.</li><li>La date auteur recorded_at n’est pas la réception dans le registre. Cet export ne contient pas cet historique de réception.</li><li>Les changements décrivent les champs déclarés, sans vérification de compatibilité sémantique ou de migration.</li><li>Les dessins présentent au plus 150 lignes ; les compteurs et le JSON conservent leur portée complète.</li></ul></details>' + \
        '<p><a href="timeline.json">Télécharger les états, comparaisons et dates sourcés</a></p><details><summary>Comparaisons et états consultables sans JavaScript</summary>' + comparisons + ''.join(states) + '</details>'
    return body, links


def compile_site(exports, gates, request, build_topics, model_content, brands=None):
    """Each pinned dossier is rendered separately: conflicting revisions never merge."""
    directory = request.get('directory', 'livrables') + '/site'
    files, dossiers, diagram_count = [], [], 0
    default_brand, dossier_brands = brands or branding.selection(request, request['baselines'])
    site_shell = partial(shell, brand=default_brand)
    def add(path, media, content):
        # Keep lossless machine projections compact. Whitespace is presentation,
        # not source identity; retained artifact bytes stay base64 and untouched.
        if media == 'application/json': content = json.dumps(json.loads(content), ensure_ascii=False, separators=(',', ':')) + '\n'
        files.append(product(directory + '/' + path, media, content, 'GENERATED', MAX_FILE))
    def add_brand(result, prefix):
        for item in branding.files(result, prefix): add(item['path'], item['media_type'], item['content'])
    add_brand(default_brand, 'branding/')
    assets = resources.files('air').joinpath('assets')
    for source, target, media in [('architecture-site.css', 'site.css', 'text/css'), ('architecture-site.js', 'site.js', 'text/javascript'),
                                  ('graph-explorer.js', 'graph.js', 'text/javascript'),
                                  ('question-capsule.js', 'capsule.js', 'text/javascript'),
                                  ('temporal-site.js', 'temporal.js', 'text/javascript'),
                                  ('architecture-pwa.js', 'pwa.js', 'text/javascript'),
                                  ('architecture-story.js', 'story.js', 'text/javascript'),
                                  ('mermaid-12.1.0.js', 'mermaid-12.1.0.js', 'text/javascript'), ('mermaid-LICENSE.txt', 'mermaid-LICENSE.txt', 'text/plain'),
                                  ('mermaid-thirdparty-APACHE-2.0.txt', 'mermaid-thirdparty-APACHE-2.0.txt', 'text/plain'),
                                  ('mermaid-provenance.json', 'mermaid-provenance.json', 'application/json'),
                                  ('bpmn-js-18.16.0.js', 'bpmn-js-18.16.0.js', 'text/javascript'),
                                  ('bpmn-diagram.css', 'bpmn-diagram.css', 'text/css'),
                                  ('bpmn-LICENSE.txt', 'bpmn-LICENSE.txt', 'text/plain'),
                                  ('bpmn-provenance.json', 'bpmn-provenance.json', 'application/json'),
                                  ('architecture-process.js', 'process.js', 'text/javascript'),
                                  ('architecture-journey.js', 'journey.js', 'text/javascript'),
                                  ('architecture-journey.css', 'journey.css', 'text/css')]:
        add('assets/' + target, media, assets.joinpath(source).read_text(encoding='utf-8'))
    site_pwa.add_identity(add, request['title'], default_brand)
    temporal = temporal_site.project(exports, request.get('comparisons', []))
    # Same model, compact JSON: keep the bounded pack usable with six states.
    # Object/schema payloads and their digests are unchanged by whitespace.
    add('architecture-model.json', 'application/json', json.dumps(json.loads(model_content), ensure_ascii=False, separators=(',', ':')) + '\n')
    for e, gate in zip(exports, gates):
        g = Graph([e]);baseline = e['baseline'];meta = baseline['meta']
        slug = mid(meta['id'] + ':' + str(meta['revision']) + ':' + e['digest'])
        prefix = 'dossiers/' + slug + '/'
        pin = {'id': meta['id'], 'revision': meta['revision'], 'digest': e['digest']}
        selected_brand = dossier_brands.get(artifact_digest(pin), default_brand)
        add_brand(selected_brand, prefix + 'branding/')
        dossier_shell = partial(shell, brand=selected_brand, brand_root='branding/')
        topics = build_topics(g, [gate])
        work = transformation_view.project([e])
        work_links = {(o['meta']['id'], o['meta']['revision']): 'objects.html#' + anchor(o) for o in e['objects']}
        add(prefix + 'transformation.json', 'application/json', render_json(work))
        add(prefix + 'transformation.html', 'text/html', dossier_shell('Piloter la transformation',
            '<p><a href="../../transformation.html">Vue globale aux baselines du projet</a></p>' + transformation_view.html(work, work_links),
            request['title'], navigation(topics, 'transformation'), '../../'))
        summary = management_summary.project(e, gate)
        updates = project_updates.project(e, gate)
        add(prefix + 'news.json', 'application/json', render_json(updates))
        add(prefix + 'news.html', 'text/html', dossier_shell('News du projet d’architecture', project_updates.section(updates), request['title'], navigation(topics, 'news'), '../../'))
        add(prefix + 'management-summary.json', 'application/json', render_json(summary))
        add(prefix + 'management-summary.md', 'text/markdown', render_text(['# Management Summary', '', *management_summary.lines(summary)]))
        add(prefix + 'management-summary.html', 'text/html', dossier_shell('Management Summary', management_summary.section(summary), request['title'], navigation(topics, 'management-summary'), '../../'))
        finance = financial_view.project(g); finance['baseline'] = pin
        finance['projection_digest'] = artifact_digest({k: v for k, v in finance.items() if k != 'projection_digest'})
        sankey = traceability_sankey.project(g); sankey['baseline'] = pin
        sankey['projection_digest'] = artifact_digest({k: v for k, v in sankey.items() if k != 'projection_digest'})
        add(prefix + 'finance.json', 'application/json', render_json(finance))
        add(prefix + 'traceability.json', 'application/json', render_json(sankey))
        add(prefix + 'finance.html', 'text/html', dossier_shell('Dimension financière', site_finance_trace.finance_page(finance, markdown), request['title'], navigation(topics, 'finance'), '../../'))
        add(prefix + 'traceability.html', 'text/html', dossier_shell('Sankey de traçabilité', site_finance_trace.sankey_page(sankey), request['title'], navigation(topics, 'traceability'), '../../'))
        journeys = journey_catalog.project(g); journeys['baseline'] = pin
        journeys['projection_digest'] = artifact_digest({k: v for k, v in journeys.items() if k != 'projection_digest'})
        add(prefix + 'journeys.json', 'application/json', render_json(journeys))
        add(prefix + 'journeys.html', 'text/html', dossier_shell('Parcours par persona', site_journeys.page(journeys), request['title'], navigation(topics, 'journeys'), '../../'))
        for journey in journeys['journeys']:
            add(prefix + 'journey-' + site_journeys.anchor(journey['reference']) + '.html', 'text/html', dossier_shell(journey['name'], site_journeys.focus(journey), request['title'], navigation(topics, 'journeys'), '../../'))
            visual_name = 'journey-map-' + journey_visual.anchor(journey)
            add(prefix + visual_name + '.html', 'text/html', dossier_shell(journey['name'], journey_visual.page(journey), request['title'], navigation(topics, 'journeys'), '../../'))
            add(prefix + visual_name + '.svg', 'image/svg+xml', journey_visual.svg(journey, selected_brand['profile'], visual_name + '.html'))
            add(prefix + visual_name + '.json', 'application/json', render_json({'engine': journey_visual.ENGINE, 'baseline': pin, 'journey': journey, 'research_validated': False, 'business_execution_performed': False}))
        processes = [process_diagrams.project(g, w) for w in g.of('Workflow')]
        add(prefix + 'processes.html', 'text/html', dossier_shell('Processus en couloirs', process_diagrams.index(processes), request['title'], navigation(topics, 'processes'), '../../'))
        for process in processes:
            filename = prefix + 'process-' + process_diagrams.anchor(process['reference'])
            add(filename + '.json', 'application/json', render_json({'baseline': pin, **process}))
            add(filename + '.bpmn', 'application/xml', process_diagrams.bpmn(process))
            add(filename + '.html', 'text/html', dossier_shell(process['name'], process_diagrams.focus(process), request['title'], navigation(topics, 'processes'), '../../'))
        nodes = [{'node': mid(o['meta']['id']), 'name': o['meta']['name'], 'type': o['meta']['type'][4:], 'href': 'objects.html#' + anchor(o)} for o in g.by_id.values()]
        focus_nodes = [{'node': anchor(o), 'name': o['meta']['name'], 'type': o['meta']['type'][4:], 'href': 'objects.html#' + anchor(o)} for o in g.by_ref.values()]
        handoff = site_handoff.project(e, gate)
        add(prefix + 'handoff.json', 'application/json', render_json(handoff))
        for page_path, page_title, page_body in site_handoff_html.pages(handoff, g, diagram):
            add(prefix + page_path, 'text/html', dossier_shell(page_title, page_body, request['title'], navigation(topics, page_path[:-5]), '../../', focus_nodes))
            if page_path.startswith('diagram-'): diagram_count += 1
        title = meta['name'];nav = navigation(topics)
        intentions = sorted([o for o in g.of('Intent') if o['meta']['namespace'] == meta['namespace']], key=lambda o: (o['meta']['name'], o['meta']['id']))
        goals = sorted([o for o in g.of('Goal') if o['meta']['namespace'] == meta['namespace']], key=lambda o: (o['meta']['name'], o['meta']['id']))
        source = (intentions or goals or [None])[0]
        purpose = {'text': source['body']['desired_change' if source['meta']['type'] == 'air.Intent' else 'outcome'],
                   'reference': {'id': source['meta']['id'], 'revision': source['meta']['revision'], 'digest': digest(source)},
                   'anchor': anchor(source)} if source else {'text': meta['description']}
        reading = site_questions.project(e, gate, topics, QUESTIONS)
        from air import site_progress
        progress = site_progress.project(reading, journeys)
        add(prefix + 'progress.json', 'application/json', render_json(progress))
        cooperation, default_capsules = question_capsule_html.page(reading, meta['namespace'])
        add(prefix + 'cooperate.html', 'text/html', dossier_shell('Travailler avec un assistant', cooperation, request['title'], navigation(topics, 'cooperate'), '../../'))
        for topic_id, capsule_request in default_capsules:
            add(prefix + 'question-' + topic_id + '.json', 'application/json', render_json(capsule_request))
        add(prefix + 'questions.json', 'application/json', render_json(reading))
        add(prefix + 'questions.html', 'text/html', dossier_shell('Les questions du dossier', question_page(reading, g), request['title'], nav, '../../'))
        for role, label, _, _ in site_questions.ROLES:
            add(prefix + 'role-' + role + '.html', 'text/html', dossier_shell(label, question_page(reading, g, role), request['title'], navigation(topics, 'role-' + role), '../../'))
        body = '<nav class="breadcrumb"><a href="../../index.html">Projet</a> / Dossier</nav><h1>' + H(title) + '</h1>' + management_summary.section(summary, compact=True) + site_progress.ribbon(progress) + '<p class="intro">' + H(meta['description']) + '</p>' + \
            '<p class="gate"><strong>' + H(reading['gate']['label']) + '</strong>. <a href="28-preparation-construction.html">Comprendre les critères</a></p>' + \
            '<h2>Les réponses dont vous avez besoin</h2><p>Choisissez votre parcours, puis ouvrez les sujets qui portent la réponse et ses preuves.</p>' + reading_routes() + '<p><a href="questions.html">Rechercher parmi toutes les questions du dossier</a></p>' + \
            '<p>Chaque sujet présente une facette du même modèle. Commencez par le besoin, suivez les mécanismes, puis examinez les choix et les preuves.</p>' + story(g) + \
            '<h2>Parcours de lecture</h2><ol class="reading-path">' + ''.join('<li><a href="' + t['name'] + '.html">' + H(QUESTIONS[t['name'][:2]][0]) + '</a><p>' + H(QUESTIONS[t['name'][:2]][1]) + '</p></li>' for p in ['23', '03', '01', '18', '25', '15', '28'] for t in topics if t['name'][:2] == p) + '</ol>'
        body = body.replace('<h2>Parcours de lecture</h2>', site_journeys.preview(journeys) + site_finance_trace.finance_summary(finance) + site_finance_trace.sankey_preview(sankey) + '<h2>Parcours de lecture</h2>')
        body += project_updates.section(updates, compact=True) + transformation_view.preview(work)
        body += site_progress.section(progress)
        add(prefix + 'index.html', 'text/html', dossier_shell(title, body, request['title'], nav, '../../'))
        objects = '<h1>Objets et définitions du dossier</h1><p>Les noms, définitions, relations et propriétés ci-dessous viennent des révisions exactes. Les liens suivent ces révisions.</p><label for="object-search">Rechercher un objet, un type ou une définition</label><input id="object-search" type="search"><p id="object-search-status" role="status"></p>'
        for o in sorted(g.by_ref.values(), key=lambda x: (x['meta']['type'], x['meta']['name'], x['meta']['id'], x['meta']['revision'])):
            objects += '<details class="object" id="' + anchor(o) + '"><summary>' + H(o['meta']['name']) + ' <span>' + H(o['meta']['type'][4:]) + ' · r' + str(o['meta']['revision']) + '</span></summary><p>' + H(o['meta']['description']) + '</p>' + \
                '<p><code>' + H(o['meta']['id']) + '</code><br>Empreinte : <code>' + digest(o) + '</code></p>' + properties(o['body'], g) + '<details><summary>Provenance et métadonnées</summary>' + properties(o['meta'], g) + '</details></details>'
        add(prefix + 'objects.html', 'text/html', dossier_shell('Objets et définitions', objects, request['title'], nav, '../../'))
        roots = sorted([o for o in e['objects'] if o['meta']['type'] in ['air.Workflow', 'air.CustomerJourney', 'air.ValueStream']], key=lambda o: (o['meta']['name'], o['meta']['id']))
        if len(roots) > 64:
            from air.foundation import TooLarge
            raise TooLarge('Static site supports at most 64 workflow/journey/value-stream roots per dossier; split the dossier or disable website')
        entries = [];graph_paths = [];path_results = []
        for root in roots:
            result = business_paths.project_path(e, {'id': root['meta']['id'], 'revision': root['meta']['revision']})
            path_results.append(result)
            name = 'path-' + anchor(root)
            add(prefix + name + '.json', 'application/json', render_json({'engine': business_paths.ENGINE, 'baseline': {'id': meta['id'], 'revision': meta['revision'], 'digest': e['digest']}, **result}))
            body = '<nav class="breadcrumb"><a href="business-paths.html">Parcours du dossier</a></nav><h1>' + H(root['meta']['name']) + '</h1>' + path_story(result, g) + '<p><a href="' + name + '.json">Résultat structuré et liens typés</a></p>'
            add(prefix + name + '.html', 'text/html', dossier_shell(root['meta']['name'], body, request['title'], nav, '../../'))
            graph_paths.append({'name': root['meta']['name'], 'href': name + '.html', 'reference': result['root']['reference'],
                                'objects': [n['reference'] for n in result['context_graph']['nodes']],
                                'workflows': [w['source']['reference'] for w in result['workflows']],
                                'status': result['status'], 'gaps': len(result['gaps']),
                                'context_truncated': result['context_graph']['truncated']})
            entries.append('<article class="business-path"><h2><a href="' + name + '.html">' + H(root['meta']['name']) + '</a></h2><p>' + H(root['meta']['description']) + '</p><p>' + H(root['meta']['type'][4:]) + ' · ' + str(len(result['gaps'])) + ' point(s) de vigilance.</p></article>')
        body = '<h1>Suivre les parcours métier</h1><p class="intro">Choisir une intention déclarée, lire ses étapes et ouvrir les objets qui portent son mécanisme.</p><p>Chaque résultat conserve cette baseline. Plusieurs correspondances restent plusieurs choix ; une association ne devient pas une interaction prouvée.</p><label for="path-search">Rechercher un parcours</label><input id="path-search" type="search"><p id="path-search-status" role="status"></p>' + (''.join(entries) if entries else '<p>Aucun workflow, parcours utilisateur ou chaîne de valeur n’est déclaré dans ce dossier.</p>')
        add(prefix + 'business-paths.html', 'text/html', dossier_shell('Parcours métier', body, request['title'], nav, '../../'))
        narrative = architecture_story.project(e, gate, path_results, temporal['comparisons'])
        add(prefix + 'story.json', 'application/json', json.dumps(narrative, ensure_ascii=False, separators=(',', ':')) + '\n')
        add(prefix + 'story.html', 'text/html', dossier_shell('Architecture story', architecture_story_page(narrative, g), request['title'], nav, '../../', story_data=narrative['trailer']))
        graph_data = graph_explorer.project_graph(e)
        graph_body, graph_links = graph_page(graph_data, g, graph_paths)
        # UI links and highlighting are a separate presentation envelope: the
        # graph digest identifies the semantic projection before these fields.
        add(prefix + 'graph.json', 'application/json', render_json(graph_data))
        add(prefix + 'graph.html', 'text/html', dossier_shell('Graphe d’architecture 2D', graph_body, request['title'], nav, '../../', graph_data={'graph': graph_data, 'paths': graph_paths, 'links': graph_links}))
        for topic in topics:
            name, focus = topic['name'], QUESTIONS[topic['name'][:2]]
            journey_order = [{(j['reference']['id'], j['reference']['revision']):j for j in journeys['journeys']}[(o['meta']['id'],o['meta']['revision'])] for o in g.of('CustomerJourney')]
            special = journey_order if name.startswith('03-') else processes if name.startswith('04-') else []
            def special_diagram(n, code, title):
                if n > len(special): return diagram(code, f'diagram-{name}-{n}.html', title)
                return journey_map.render(special[n-1]) if name.startswith('03-') else process_diagrams.figure(special[n-1])
            rendered, diagrams = markdown(topic['lines'], name, topic['title'], special_diagram if special else None)
            src = sources(topic['used'])
            from air.deliverables import src as source_lines
            add(prefix + name + '.md', 'text/markdown', render_text(['# ' + topic['title'], '',
                'Baseline `' + meta['id'] + '` r' + str(meta['revision']) + ' - `' + e['digest'] + '`.', '', *topic['lines'], '', *source_lines(topic['used'])]))
            body = '<nav class="breadcrumb"><a href="../../index.html">Projet</a> / <a href="index.html">' + H(title) + '</a></nav><h1>' + H(topic['title']) + '</h1><p class="intro">' + H(focus[0]) + '</p><p>' + H(focus[1]) + '</p>' + legend() + rendered + src + \
                '<p><a href="' + name + '.md">Document Markdown de ce dossier exact</a> · <a href="../../architecture-model.json">Modèle exact exporté</a></p>'
            add(prefix + name + '.html', 'text/html', dossier_shell(topic['title'], body, request['title'], navigation(topics, name), '../../', nodes))
            for d in diagrams:
                diagram_count += 1
                visual = (journey_map.render(special[d['number']-1], True) if name.startswith('03-') else process_diagrams.figure(special[d['number']-1])) if special and d['number'] <= len(special) else diagram(d['code'], title=d['title'])
                body = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / <a href="' + name + '.html">' + H(topic['title']) + '</a></nav><h1>' + H(d['title']) + '</h1><p class="intro">' + H(focus[0]) + '</p>' + legend() + visual + src
                add(prefix + 'diagram-' + name + '-' + str(d['number']) + '.html', 'text/html', dossier_shell(d['title'], body, request['title'], navigation(topics, name), '../../', nodes))
        dossiers.append({'name': title, 'namespace': meta['namespace'], 'baseline': {'id': meta['id'], 'revision': meta['revision'], 'digest': e['digest']},
                         'news': prefix + 'news.html', 'news_data': prefix + 'news.json', 'news_digest': updates['projection_digest'],
                         'purpose': purpose,
                         'management_summary': prefix + 'management-summary.html', 'management_summary_data': prefix + 'management-summary.json', 'management_summary_digest': summary['projection_digest'],
                         'transformation': prefix + 'transformation.html', 'transformation_data': prefix + 'transformation.json', 'transformation_digest': work['projection_digest'],
                         'journeys': prefix + 'journeys.html', 'journeys_data': prefix + 'journeys.json', 'journeys_digest': journeys['projection_digest'],
                         'processes': prefix + 'processes.html', 'process_count': len(processes),
                         'finance': prefix + 'finance.html', 'finance_data': prefix + 'finance.json', 'finance_digest': finance['projection_digest'],
                         'traceability': prefix + 'traceability.html', 'traceability_data': prefix + 'traceability.json', 'traceability_digest': sankey['projection_digest'],
                         'branding': {'profile_digest': selected_brand['profile_digest'], 'path': prefix + 'branding/brand.json', 'warnings': selected_brand['warnings']},
                         'path': prefix + 'index.html', 'graph': prefix + 'graph.html', 'graph_digest': graph_data['graph_digest'],
                         'story': prefix + 'story.html', 'story_data': prefix + 'story.json', 'story_digest': narrative['story_digest'],
                         'progress': prefix + 'progress.json', 'progress_digest': progress['projection_digest'],
                         'questions': prefix + 'questions.html', 'questions_data': prefix + 'questions.json', 'question_digest': reading['projection_digest'],
                         'cooperation': prefix + 'cooperate.html',
                         'handoff': prefix + 'handoff.html', 'handoff_data': prefix + 'handoff.json', 'handoff_digest': handoff['projection_digest'],
                         'handoff_foci': len(handoff['packets']), 'handoff_teams': len(handoff['teams']),
                         'topics': len(topics), 'gate': gate['result'], 'diagrams': sum(len(markdown(t['lines'], t['name'])[1]) for t in topics) + len(handoff['packets'])})
    body = '<h1>' + H(request['title']) + '</h1><p class="intro">Comprendre les dossiers d’architecture, leurs mécanismes et leurs conséquences.</p><p>Choisissez un dossier. Chaque dossier conserve sa baseline : les variantes et les révisions ne sont pas fusionnées.</p><label for="dossier-search">Rechercher un dossier</label><input id="dossier-search" type="search"><p id="dossier-search-status" role="status"></p><div class="dossiers">' + \
        ''.join(dossier_card(d) for d in dossiers) + '</div><section><h2>Lire et transmettre ce dossier</h2><p>Le site fonctionne hors ligne. Transmettez le dossier complet pour conserver ses diagrammes et liens. Les constats et limites restent attachés au modèle exporté.</p><a href="architecture-model.json">Télécharger les modèles et schémas exacts</a></section>'
    for d in dossiers:
        base = d['path'].rsplit('/', 1)[0] + '/'
        summary_file = next(f for f in files if f['path'] == directory + '/' + d['management_summary_data'])
        news_file = next(f for f in files if f['path'] == directory + '/' + d['news_data'])
        body = body.replace('<label for="dossier-search">', project_updates.section(json.loads(news_file['content']), base, compact=True) + '<label for="dossier-search">', 1)
        body = body.replace('<label for="dossier-search">', management_summary.section(json.loads(summary_file['content']), base, compact=True) + '<label for="dossier-search">', 1)
        if len(dossiers) == 1:
            progress_file = next(f for f in files if f['path'] == directory + '/' + d['progress'])
            body = body.replace('<label for="dossier-search">', site_progress.ribbon(json.loads(progress_file['content']), base) + '<label for="dossier-search">', 1)
        finance_file = next(f for f in files if f['path'] == directory + '/' + d['finance_data'])
        trace_file = next(f for f in files if f['path'] == directory + '/' + d['traceability_data'])
        body += '<section class="dossier-dimensions"><h2>' + H(d['name']) + '</h2>' + site_finance_trace.finance_summary(json.loads(finance_file['content']), d['finance']) + site_finance_trace.sankey_preview(json.loads(trace_file['content']), d['traceability']) + '</section>'
        journeys_file = next(f for f in files if f['path'] == directory + '/' + d['journeys_data'])
        body += site_journeys.preview(json.loads(journeys_file['content']), d['journeys'])
        progress_file = next(f for f in files if f['path'] == directory + '/' + d['progress'])
        body += site_progress.section(json.loads(progress_file['content']), d['path'].rsplit('/', 1)[0] + '/', 'Complétude : ' + d['name'])
    temporal_body, temporal_links = temporal_page(temporal, dossiers, exports)
    work = transformation_view.project(exports)
    work_links = {}
    for e, d in zip(exports, dossiers):
        for o in e['objects']:
            work_links.setdefault((o['meta']['id'], o['meta']['revision']), d['path'].rsplit('/', 1)[0] + '/objects.html#' + anchor(o))
    body = body.replace('<label for="dossier-search">', transformation_view.preview(work) + '<label for="dossier-search">', 1)
    add('transformation.json', 'application/json', render_json(work))
    add('timeline.json', 'application/json', render_json(temporal))
    nav = '<a class="dossier-home" href="index.html">Vue d’ensemble du projet</a><a class="dossier-home" href="timeline.html">Comparer les états et les dates</a><h2>Dossiers du projet</h2><ul>' + ''.join('<li><a href="' + d['path'] + '">' + H(d['name']) + '</a></li>' for d in dossiers) + '</ul><a href="architecture-model.json">Modèles et schémas exacts</a>'
    nav = '<a class="dossier-home" href="transformation.html">Piloter la transformation</a>' + nav
    add('transformation.html', 'text/html', site_shell('Piloter la transformation', transformation_view.html(work, work_links), request['title'], nav, ''))
    add('timeline.html', 'text/html', site_shell('Changements et dates', temporal_body, request['title'], nav, '', temporal_data={'temporal': temporal, 'links': temporal_links}))
    add('index.html', 'text/html', site_shell(request['title'], body, request['title'], nav, ''))
    manifest = {'engine': ENGINE, 'entrypoint': directory + '/index.html', 'dossiers': dossiers, 'diagrams': diagram_count,
                'management_summary': {'engine': management_summary.ENGINE, 'dossiers': len(dossiers), 'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'approval_inferred': False},
                'transformation': {'engine': transformation_view.ENGINE, 'path': 'transformation.html', 'data': 'transformation.json',
                    'projection_digest': work['projection_digest'], 'completion_attested': False, 'federation_implemented': False},
                'branding': {'engine': branding.ENGINE, 'profile_digest': default_brand['profile_digest'], 'path': 'branding/brand.json'},
                'interactive_graphs': len(dossiers), 'graph_engine': graph_explorer.ENGINE,
                'journey_catalog': {'engine': journey_catalog.ENGINE, 'dossiers': len(dossiers), 'research_validated': False},
                'financial_dimension': {'engine': financial_view.ENGINE, 'dossiers': len(dossiers), 'source_calculations_required_for_detail': True},
                'traceability_sankey': {'engine': traceability_sankey.ENGINE, 'dossiers': len(dossiers), 'business_execution_performed': False},
                'architecture_stories': len(dossiers), 'story_engine': architecture_story.ENGINE,
                'reading_routes': {'engine': site_questions.ENGINE, 'roles_per_dossier': len(site_questions.ROLES), 'questions_per_dossier': len(QUESTIONS), 'audience_is_access_control': False},
                'agent_cooperation': {'engine': question_capsule.ENGINE, 'dossiers': len(dossiers),
                                      'context_tool': 'air_resume_question', 'automatic_connection': False,
                                      'credentials_included': False},
                'implementation_handoff': {'engine': site_handoff.ENGINE, 'foci': sum(d['handoff_foci'] for d in dossiers),
                                           'teams': sum(d['handoff_teams'] for d in dossiers), 'explicit_assignments_only': True,
                                           'business_execution_performed': False},
                'graph_reading': {'engine': 'air.graph-reading/1', 'initial_view': 'DECLARED_NEIGHBORHOOD', 'presets': 4,
                                  'relation_steps': ['SOURCE', 'RELATION', 'DESTINATION'], 'user_controlled': True,
                                  'reduced_motion': True, 'business_execution_performed': False},
                'temporal': {'page': 'timeline.html', 'data': 'timeline.json', 'engine': temporal_site.ENGINE,
                             'comparisons': len(temporal['comparisons']), 'report_digest': temporal['report_digest']},
                'progress': {'engine': site_progress.ENGINE, 'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'semantic_completeness_certified': False},
                'offline': True, 'read_only': True, 'revision_policy': 'ONE_EXACT_BASELINE_PER_DOSSIER', 'complete_topics': True}
    manifest['pwa'] = site_pwa.compile_worker(files, directory, add)
    add('site-manifest.json', 'application/json', render_json(manifest))
    # Agent metadata is bounded; the complete exact cache list lives in the
    # generated site manifest, whose file digest is already in the pack.
    return files, {**manifest, 'pwa': {k: v for k, v in manifest['pwa'].items() if k != 'resources'}}
