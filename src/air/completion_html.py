"""Static progress of durable design runs, with exact resume references."""
from air.site_handoff_html import H

LABELS = {'PAUSED': 'En pause', 'CANCELLED': 'Annulé', 'ACTIVE': 'En cours',
    'READY_TO_BUILD': 'Prêt à construire', 'REQUIRES_MORE_DESIGN': 'Conception à poursuivre',
    'BLOCKED_ON_DECISION': 'Décision ou qualification attendue', 'AWAITING_AUTHORIZATION': 'Mandat technique attendu',
    'AUTHORIZATION_EXPIRED': 'Mandat expiré', 'AUTHORIZATION_CHANGED': 'Politique modifiée',
    'AUTHORIZATION_REVOKED': 'Mandat révoqué', 'BUDGET_EXHAUSTED': 'Budget de travail atteint',
    'NEEDS_REPLAN': 'Replanification nécessaire', 'BASELINE_MOVED': 'Nouvelle version à examiner',
    'EXECUTOR_NOT_AUTHORIZED': 'Exécutant hors mandat', 'WRITE_NOT_AUTHORIZED': 'Écriture non autorisée',
    'DESIGN': 'Travail de conception', 'QUALIFICATION': 'Qualification à obtenir', 'OPEN': 'À traiter', 'ANSWERED': 'Réponse enregistrée'}


def render(report):
    body = '<h1>Progression avec un agent</h1><p class="intro">Reprendre le dossier, comprendre le prochain travail et voir les décisions attendues.</p>'
    body += '<p>Cette vue est figée à l’export. Le modèle du client raisonne ; AIR conserve les checkpoints et vérifie les critères. Une session fermée ne laisse pas nécessairement un modèle actif.</p>'
    body += '<p><a href="completion-runs.json">Télécharger les références de reprise</a></p>'
    if report.get('coverage') == 'BOUNDED': body += '<p>Vue limitée à 32 parcours. Interroger les références des autres parcours dans le registre ; cette page ne représente pas leur état.</p>'
    if not report['runs']: body += '<p>Aucun parcours autonome n’est enregistré pour cette baseline. Créez un parcours avec une intention, un Scope et des objectifs exacts, puis faites autoriser son périmètre technique.</p>'
    for run in report['runs']:
        body += '<section><h2>' + H(run['purpose']) + '</h2><p class="gate">' + H(LABELS.get(run['execution_state'], run['execution_state'])) + ' · ' + H(LABELS[run['outcome']]) + '</p>'
        body += '<p>' + H(run['cycles']) + ' changements appliqués, checkpoint ' + H(run['sequence']) + '. Baseline suivie : révision ' + H(run['baseline']['revision']) + '.</p>'
        if not run['matches_export']: body += '<p>Ce parcours suit une autre version que cet export. Reprendre avec le registre avant de continuer.</p>'
        body += '<h3>Prochains travaux</h3><ol>'
        from air.deliverables import CRITERIA_FR
        for task in run['tasks']:
            title, next_step = CRITERIA_FR.get(task['id'], (task['title'], task['next_step']))
            body += '<li><strong>' + H(title) + '</strong><p>' + H(next_step) + '</p><small>' + H(LABELS[task['kind']]) + '</small></li>'
        body += '</ol><h3>Décisions attendues</h3>'
        for question in run['questions']:
            body += '<details><summary>' + H(question['question']) + ' · ' + H(LABELS[question['state']]) + '</summary><p>' + H(question.get('answer', 'Une réponse mandatée est nécessaire.')) + '</p></details>'
        body += '<details><summary>Reprendre dans ChatGPT, Claude, Cursor ou Antigravity</summary><pre>' + H(run['resume_prompt']) + '</pre></details></section>'
    return body + '<p>READY_TO_BUILD provient du contrôle AIR de la version exacte. Une réponse à une question, un nom de relecteur ou une progression documentaire ne constitue pas une approbation.</p>'
