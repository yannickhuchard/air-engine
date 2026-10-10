"""Pinned documentary coverage and calculated readiness, never inferred approval."""
from html import escape
from air.expr import artifact_digest

ENGINE = 'air.site-progress/2'
COLUMNS = [('TODO', 'À documenter'), ('PARTIAL', 'À compléter'), ('VALIDATE', 'À valider'), ('DOCUMENTED', 'Documenté ou calculé')]
PARTS = [
    ('intention', 'Intention et choix', ['23', '02', '14', '24', '25'], []),
    ('experience', 'Expérience', ['03', '04', '30'], []),
    ('architecture', 'Architecture', ['01', '09', '10', '11', '29', '26'], ['REFERENCE_CLOSURE', 'STRUCTURE', 'EXTERNAL_DEPENDENCIES', 'RUNTIME']),
    ('data', 'Données', ['18', '19', '20'], []),
    ('quality', 'Qualité et risques', ['12', '15', '16', '22', '34', '35'], ['KNOWLEDGE', 'GAPS', 'SECURITY_ZONES', 'COMPLIANCE']),
    ('delivery', 'Réalisation', ['05', '06', '07', '08', '21', '31', '27', '37'], ['PLANNING']),
    ('finance', 'Finances', ['17', '36'], []),
    ('verification', 'Vérification', ['13', '28', '32', '33'], ['CONSTRUCTION_CHAIN', 'VERIFICATION', 'INDEPENDENT_REVIEW', 'CONTEXTUAL_COMPLETENESS']),
]


def parts(reading):
    """Unweighted documentary topic coverage, with separate declared work and gates."""
    result = []; linked = set()
    ref_key = lambda r: (r['id'], r['revision'])
    work = reading.get('design_tasks', [])
    for identity, label, topics, gates in PARTS:
        questions = [q for q in reading['questions'] if q['id'] in topics]
        sources = {ref_key(s['reference']) for q in questions for s in q['sources']}
        declared = [t for t in work if any(ref_key(r) in sources for r in t['deliverables'])]
        linked.update(ref_key(t['reference']) for t in declared)
        investigating = {ref_key(s['reference']): s for q in questions for s in q['sources']
            if s.get('type') == 'air.Unknown' and s.get('declared_state') == 'INVESTIGATING'}
        covered = sum(q['state'] in ('SOURCES_PRESENT', 'CALCULATED') for q in questions)
        result.append({'id': identity, 'label': label, 'covered': covered, 'total': len(questions),
            'percent': 100 * covered // len(questions) if questions else None,
            'questions': questions, 'remaining_controls': [c for c in reading['calculated_criteria']
                if c['code'] in gates and c['status'] == 'NOT_MET'],
            'declared_work': declared, 'investigating': list(investigating.values()),
            'in_progress': sum(t['status'] == 'IN_PROGRESS' for t in declared) + len(investigating),
            'semantic_completeness_certified': False})
    return result, [t for t in work if ref_key(t['reference']) not in linked]


def project(reading, journeys=None):
    tasks = []
    for q in reading['questions']:
        state = q['state']
        column = 'TODO' if state == 'NOT_DOCUMENTED' else 'PARTIAL' if state == 'PARTIAL' else 'DOCUMENTED'
        tasks.append({'id': 'topic-' + q['id'], 'label': q['question'], 'column': column,
                      'kind': 'DOCUMENTARY_COVERAGE', 'status': state, 'href': q['topic'],
                      'detail': '; '.join(q['missing_dimensions']) or
                      ('Résultat calculé : ouvrir le sujet pour lire ses limites.' if state == 'CALCULATED' else
                       'Sources présentes. La qualité du contenu et son approbation restent à examiner.' if q['sources'] else
                       'Aucune source déclarée pour ce sujet.'),
                      'sources': [s['reference'] for s in q['sources']], 'approved': False})
    for c in reading['calculated_criteria']:
        tasks.append({'id': 'gate-' + c['code'], 'label': c['label'],
                      'column': 'DOCUMENTED' if c['status'] in ('MET', 'NOT_APPLICABLE') else 'VALIDATE',
                      'kind': 'CALCULATED_READINESS', 'status': c['status'],
                      'href': '28-preparation-construction.html', 'detail': c['next_action'],
                      'sources': [], 'approved': False})
    seen = set()
    for q in reading['questions']:
        for source in q['sources']:
            pin = source['reference'];key = (pin['id'],pin['revision'])
            if key in seen or source.get('type') != 'air.Unknown' or source.get('declared_state') not in ('OPEN','INVESTIGATING'): continue
            seen.add(key)
            from air.deliverables import mid
            tasks.append({'id':'unknown-' + mid(pin['id']), 'label':source['name'], 'column':'VALIDATE',
                          'kind':'DECLARED_OPEN_QUESTION','status':source['declared_state'],
                          'href':'objects.html#' + mid(pin['id'] + ':' + str(pin['revision'])),
                          'detail':' '.join(s['text'] for s in source['statements']) + ' Responsable proposé : ' + source['resolution_owner'],
                          'sources':[pin], 'approved':False})
    if journeys is not None:
        for c in journeys['checks']:
            tasks.append({'id': 'journeys-' + c['code'], 'label': c['label'],
                'column': 'DOCUMENTED' if c['status'] == 'MET' else 'PARTIAL',
                'kind': 'JOURNEY_DOCUMENTARY_COVERAGE', 'status': c['status'],
                'href': 'journeys.html#journey-checklist', 'sources': journeys['sources'], 'approved': False,
                'detail': str(c['gap_count']) + ' lacune(s). Contrôle documentaire, pas une validation UX ou réglementaire.'})
    blocks, unlinked = parts(reading)
    result = {'engine': ENGINE, 'baseline': reading['baseline'], 'gate': reading['gate'],
              'parts': blocks, 'unlinked_design_tasks': unlinked,
              'percentage_basis': 'FLOOR_100_COVERED_TOPICS_OVER_PRESENT_TOPICS_UNWEIGHTED',
              'tasks': tasks, 'documented_topics': sum(q['state'] in ('SOURCES_PRESENT', 'CALCULATED') for q in reading['questions']),
              'total_topics': len(reading['questions']),
              'met_criteria': sum(c['status'] == 'MET' for c in reading['calculated_criteria']),
              'total_criteria': len(reading['calculated_criteria']),
              'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'semantic_completeness_certified': False,
              'business_execution_performed': False}
    return {**result, 'projection_digest': artifact_digest(result)}


def ribbon(progress, prefix=''):
    """Native disclosure keeps the complete drill-down usable without JavaScript."""
    from air.deliverables import mid
    from air.editorial import prose
    h = lambda value: escape(prose(str(value)), quote=True)
    scope = mid(progress['baseline']['id'] + ':' + str(progress['baseline']['revision']) + ':' + prefix)
    html = '<section class="completion-ribbon" aria-label="Avancement par partie du dossier"><div class="completion-heading"><h2>Avancement du dossier</h2><a href="' + h(prefix + '28-preparation-construction.html') + '">Préparation : ' + str(progress['met_criteria']) + '/' + str(progress['total_criteria']) + '</a></div>'
    html += '<p class="completion-caption">Couverture documentaire par partie. Cliquez pour voir les manques et le travail déclaré. Ces pourcentages ne valent pas validation du design.</p><div class="completion-parts">'
    for block in progress['parts']:
        identifier = 'completion-' + scope + '-' + block['id']
        percent = block['percent']; caption = str(percent) + ' %' if percent is not None else 'Non évalué'
        missing = block['total'] - block['covered']; controls = len(block['remaining_controls'])
        state = str(missing) + ' à compléter' if missing else 'Sujets couverts' if block['total'] else 'Aucun sujet évalué'
        if controls: state += ', ' + str(controls) + ' contrôle(s) restant(s)'
        html += '<details class="completion-part" id="' + identifier + '"><summary><span class="completion-name">' + h(block['label']) + '</span><strong>' + h(caption) + '</strong><span class="completion-track" aria-hidden="true"><span style="width:' + str(percent or 0) + '%"></span></span><span class="completion-state">' + h(state) + '</span></summary><div class="completion-detail">'
        html += '<h3>' + h(block['label']) + '</h3><p>' + str(block['covered']) + '/' + str(block['total']) + ' sujets documentés ou calculés. Couverture de la baseline r' + str(progress['baseline']['revision']) + '.</p><ul>'
        for q in block['questions']:
            state = {'NOT_DOCUMENTED': 'À documenter', 'PARTIAL': 'À compléter', 'SOURCES_PRESENT': 'Sources présentes', 'CALCULATED': 'Calcul disponible'}[q['state']]
            detail = '; '.join(q['missing_dimensions']) or ('Aucune source déclarée.' if not q['sources'] and q['state'] != 'CALCULATED' else 'Lire le sujet et ses limites.')
            html += '<li><a href="' + h(prefix + q['topic']) + '">' + h(q['question']) + '</a><span class="completion-state">' + h(state) + '</span><p>' + h(detail) + '</p></li>'
        html += '</ul><h4>Contrôles restants</h4>'
        html += '<ul>' + ''.join('<li>' + h(c['label']) + '<p>' + h(c['next_action']) + '</p></li>' for c in block['remaining_controls']) + '</ul>' if controls else '<p>Aucun contrôle restant rattaché à cette partie. Consulter la préparation globale.</p>'
        html += '<h4>Travail déclaré</h4>'
        states = {'TODO': 'À faire', 'IN_PROGRESS': 'En cours', 'BLOCKED': 'Bloqué', 'DONE': 'Terminé, déclaré', 'CANCELLED': 'Annulé'}
        for task in block['declared_work']:
            ref = task['reference']
            html += '<p><a href="' + h(prefix + 'objects.html#' + mid(ref['id'] + ':' + str(ref['revision']))) + '">' + h(task['name']) + '</a> : ' + h(states[task['status']]) + '. Responsable déclaré : ' + h(task['owner']) + '.</p>'
        for unknown in block['investigating']:
            ref = unknown['reference']
            html += '<p><a href="' + h(prefix + 'objects.html#' + mid(ref['id'] + ':' + str(ref['revision']))) + '">' + h(unknown['name']) + '</a> : investigation en cours, déclarée.</p>'
        if not block['declared_work'] and not block['investigating']: html += '<p>Aucun travail en cours rattaché par une référence exacte. Un manque ne signifie pas qu’une tâche a démarré.</p>'
        html += '<p><a href="' + h(prefix + 'cooperate.html') + '">Discuter ces manques avec un assistant</a></p></div></details>'
    html += '</div>'
    if progress['unlinked_design_tasks']:
        html += '<details class="completion-unlinked"><summary>Travail du dossier sans rattachement à une partie (' + str(len(progress['unlinked_design_tasks'])) + ')</summary><ul>'
        for task in progress['unlinked_design_tasks']:
            ref = task['reference']
            html += '<li><a href="' + h(prefix + 'objects.html#' + mid(ref['id'] + ':' + str(ref['revision']))) + '">' + h(task['name']) + '</a> : ' + h(task['status']) + '</li>'
        html += '</ul></details>'
    return html + '</section>'


def section(progress, prefix='', heading='Complétude et progression'):
    h = lambda value: escape(str(value), quote=True)
    summary = (str(progress['documented_topics']) + '/' + str(progress['total_topics']) + ' sujets documentés ou calculés ; ' +
               str(progress['met_criteria']) + '/' + str(progress['total_criteria']) + ' critères de préparation satisfaits.')
    html = '<section class="project-progress" aria-label="' + h(heading) + '"><h2>' + h(heading) + '</h2><p class="intro">' + h(summary) + '</p>'
    html += '<p>La présence de sources ne certifie ni la complétude sémantique ni une approbation. Les validations du design et les essais du futur service restent distincts.</p>'
    html += '<p><strong>' + h(progress['gate']['label']) + '</strong>. État de la baseline r' + h(progress['baseline']['revision']) + '. Régénérer le site après chaque nouvelle baseline.</p>'
    html += '<details class="completion-checklist"><summary>Checklist des sujets et des vérifications</summary><ul>'
    labels = dict(COLUMNS)
    for task in progress['tasks']:
        html += '<li><span class="progress-state state-' + h(task['column'].lower()) + '">' + h(labels[task['column']]) + '</span> <a href="' + h(prefix + task['href']) + '">' + h(task['label']) + '</a><p>' + h(task['detail']) + '</p></li>'
    html += '</ul></details><h3>Kanban du dossier</h3><p>Les sujets suivent leurs sources ; les critères suivent le calcul AIR. Aucun déplacement manuel ne modifie la preuve.</p><div class="progress-board">'
    for column, label in COLUMNS:
        tasks = [t for t in progress['tasks'] if t['column'] == column]
        html += '<section class="progress-column state-' + column.lower() + '"><h4>' + h(label) + ' <span>(' + str(len(tasks)) + ')</span></h4><ul>'
        for task in tasks:
            html += '<li><a href="' + h(prefix + task['href']) + '">' + h(task['label']) + '</a><p>' + h(task['detail']) + '</p></li>'
        html += '</ul>' + ('<p>Aucun élément dans cette colonne.</p>' if not tasks else '') + '</section>'
    return html + '</div><p><a href="' + h(prefix + 'progress.json') + '">État structuré, références et empreinte</a></p></section>'
