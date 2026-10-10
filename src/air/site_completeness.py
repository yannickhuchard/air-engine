"""Readable contextual gaps and design-only contract suites."""
from html import escape
import hashlib
from air.editorial import prose

LABELS = {'DIGITAL_SERVICE': 'Service numérique', 'DATA_PLATFORM': 'Plateforme de données', 'PHYSICAL_SYSTEM': 'Système physique',
    'ORGANIZATIONAL_CHANGE': 'Transformation organisationnelle', 'REGULATED_ACTIVITY': 'Activité réglementée'}
STATES = {'DOCUMENTED': 'Documenté dans la portée du contrôle', 'NOT_DOCUMENTED': 'À documenter', 'PARTIAL': 'À compléter',
    'EXCLUDED_APPROVED': 'Exclusion couverte par une revue effective de cette baseline',
    'EXCLUSION_DECLARED': 'Exclusion déclarée, approbation non vérifiée', 'CONTEXT_REQUIRED': 'Contexte à sélectionner',
    'INCOMPLETE': 'Questions à résoudre', 'PASS_DESIGN_EXAMPLES': 'Exemples de design cohérents', 'BLOCKED': 'Contrat à corriger'}
H = lambda value: escape(prose(str(value)), quote=True)


def slug(ref): return 'n' + hashlib.sha256((ref['id'] + ':' + str(ref['revision'])).encode()).hexdigest()[:12]


def preview(model, prefix=''):
    missing = sum(n for state, n in model['counts'].items() if state not in ('DOCUMENTED', 'EXCLUDED_APPROVED'))
    return '<section class="contextual-completeness"><h2>Le dossier répond-il aux questions de ce projet ?</h2><p><strong>' + H(STATES.get(model['result'], model['result'])) + '</strong>. ' + str(missing) + ' question(s) à traiter dans la portée du catalogue.</p><p>' + ('Profils : ' + H(', '.join(LABELS[p] for p in model['profiles'])) if model['profiles'] else 'Le type de projet n’est pas encore sélectionné ; seules les questions communes sont proposées.') + '</p><p>Ces contrôles complètent la couverture documentaire et les critères de préparation du profil retenu. Ils ne valident ni le design ni le lancement.</p><a href="' + prefix + 'completeness.html">Examiner les questions et les contrats</a></section>'


def page(model, topics, suites, labels=None):
    labels = labels or {}
    links = {t['name'][:2]: t['name'] + '.html' for t in topics}
    text = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Complétude</nav><h1>Complétude selon le contexte</h1>' + preview(model)
    text += '<p>Catalogue <code>' + H(model['catalogue']) + '</code>. Baseline r' + str(model['baseline']['revision']) + ', empreinte <code>' + H(model['baseline']['digest']) + '</code>. <a href="completeness.json">Données et références exactes</a>.</p>'
    if model['context_state'] != 'SELECTED':
        text += '<details><summary>Choisir le contexte avec l’architecte</summary><p>Décrire DossierContext avec air_describe_type ; choisir un ou plusieurs profils, puis proposer la contribution. Les questions communes restent toujours applicables. Le choix nécessite le profil de modèle air.build-design/0.35 ; aucune ancienne baseline n’est modifiée.</p><ul>' + ''.join('<li>' + H(LABELS[p]) + '</li>' for p in model['available_profiles']) + '</ul></details>'
    text += '<div class="table-wrap"><table><thead><tr><th scope="col">Question</th><th scope="col">État</th><th scope="col">Sources et action</th></tr></thead><tbody>'
    for c in model['checks']:
        sources = ''.join('<li><a title="' + H(r['id']) + '" href="objects.html#' + slug(r) + '">' + H(labels.get((r['id'], r['revision']), r['id'])) + '</a>, r' + str(r['revision']) + '</li>' for r in c['sources'])
        issue = '<ul>' + ''.join('<li>' + H(i) + '</li>' for i in c['issues']) + '</ul>' if c['issues'] else ''
        exclusion = ('<p>Exclusion : ' + H(c['exclusion']['reason']) + ('. Revue effective de la baseline.' if c['exclusion']['approval_verified'] else '. Décision déclarée, approbation non vérifiée.') + '</p>') if c['exclusion'] else ''
        action = '<a href="' + links.get(c['topic'], 'questions.html') + '">Lire le sujet à compléter</a>'
        text += '<tr><td>' + H(c['question']) + '</td><td>' + H(STATES[c['status']]) + '</td><td>' + ('<ul>' + sources + '</ul>' if sources else '<p>Aucune source liée.</p>') + issue + exclusion + action + '</td></tr>'
    text += '</tbody></table></div><h2>Contrats pour les constructeurs</h2><p>Les suites vérifient les schémas JSON et les préconditions, postconditions et invariants purs déclarés. Les politiques d’autorisation, idempotence, concurrence, délai, retry et compensation sont documentées ; leur exécution réelle n’est pas testée.</p>'
    if not suites: text += '<p>Aucune InterfaceSpecification déclarée. Le guide aide à relier la spécification au contrat et à son binding exact.</p>'
    for suite in suites:
        ref = suite['specification']
        text += '<details><summary>' + H(labels.get((ref['id'], ref['revision']), ref['id'])) + ' : ' + H(STATES.get(suite['result'], suite['result'])) + '</summary>'
        if suite.get('diagnostic'): text += '<p>' + H(suite['diagnostic']) + '</p>'
        if suite['files']:
            base = 'interfaces/' + slug(suite['specification']) + '/'
            text += '<ul>' + ''.join('<li><a href="' + base + H(f['path']) + '">' + H(f['path']) + '</a></li>' for f in suite['files']) + '</ul><p>Le script est téléchargeable. Le site ne l’exécute pas.</p>'
        text += '</details>'
    if model['exclusion_issues']: text += '<h2>Exclusions à corriger</h2><ul>' + ''.join('<li>' + H(i['check_id']) + ' : contrôle absent du catalogue courant.</li>' for i in model['exclusion_issues']) + '</ul>'
    return text
