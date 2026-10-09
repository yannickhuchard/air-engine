"""Pinned documentary coverage and calculated readiness, never inferred approval."""
from html import escape
from air.expr import artifact_digest

ENGINE = 'air.site-progress/1'
COLUMNS = [('TODO', 'À documenter'), ('PARTIAL', 'À compléter'), ('VALIDATE', 'À valider'), ('DOCUMENTED', 'Documenté ou calculé')]


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
    result = {'engine': ENGINE, 'baseline': reading['baseline'], 'gate': reading['gate'],
              'tasks': tasks, 'documented_topics': sum(q['state'] in ('SOURCES_PRESENT', 'CALCULATED') for q in reading['questions']),
              'total_topics': len(reading['questions']),
              'met_criteria': sum(c['status'] == 'MET' for c in reading['calculated_criteria']),
              'total_criteria': len(reading['calculated_criteria']),
              'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE', 'semantic_completeness_certified': False,
              'business_execution_performed': False}
    return {**result, 'projection_digest': artifact_digest(result)}


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
