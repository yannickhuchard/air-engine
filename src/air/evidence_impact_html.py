"""Source-linked, static reading of proof declarations and change witnesses."""
from air.site_handoff_html import H, source_link

STATUS = {'IMPACTED': 'À revérifier', 'INCONCLUSIVE_DEPENDENCIES': 'Liens à compléter',
    'NO_DECLARED_IMPACT': 'Aucun impact déclaré', 'BLOCKED': 'Analyse bloquée'}


def render(report):
    body = '<div class="verification-view"><h1>Vérifications et changements</h1><p class="intro">Comprendre les résultats consignés, les preuves à reprendre et les limites du design.</p>'
    body += '<p>Cette vue est figée à l’export. Un résultat déclaré ne constitue pas une qualification indépendante. Aucun effet métier n’est exécuté et aucun avis ne passe automatiquement à une nouvelle baseline.</p>'
    body += '<p><a href="verification-impact.json">Télécharger les résultats et les chemins exacts</a></p><section><h2>Vérifications du dossier</h2>'
    inventory = report['inventory']
    if not inventory: body += '<p>Aucune vérification n’est déclarée dans cette baseline.</p>'
    for entry in inventory:
        body += '<details><summary>' + H(entry['name']) + ' · ' + H(entry.get('result') or 'À vérifier') + '</summary><p>' + source_link(entry['reference'], entry['name']) + '</p><p>' + H(entry['type']) + '</p><p>' + H(entry.get('summary', '')) + '</p></details>'
    body += '</section><section><h2>Changements depuis les versions parentes</h2>'
    if not report['comparisons']: body += '<p>Aucune baseline parente n’est déclarée. Comparez explicitement deux versions par CLI ou MCP pour préparer une évolution.</p>'
    for comparison in report['comparisons']:
        before = comparison['before']
        body += '<h3>Depuis la révision ' + H(before['revision']) + '</h3>'
        if comparison.get('status') == 'BLOCKED':
            body += '<p>' + H(comparison['diagnostic']) + '</p>'; continue
        summary = comparison['summary']
        body += '<p>' + H(summary['IMPACTED']) + ' preuves ou cas à revérifier ; ' + H(summary['INCONCLUSIVE_DEPENDENCIES']) + ' avec liens incomplets.</p>'
        for entry in comparison['evidence']:
            body += '<details><summary>' + H(entry['name']) + ' · ' + H(STATUS[entry['status']]) + '</summary><p>' + H(entry['next_action']) + '</p>'
            for witness in entry['changed_dependencies']:
                body += '<p>Dépendance modifiée : ' + H(witness['dependency']['id']) + ', révision ' + H(witness['dependency']['revision']) + '</p><ol>'
                for step in witness['path']:
                    body += '<li>' + H(step['from']['id']) + ' via ' + H(step['field']) + ' vers ' + H(step['to']['id']) + '</li>'
                body += '</ol>'
                for change in witness.get('body_changes', []):
                    body += '<p>Champ modifié : ' + H(change['path']) + ' (' + H(change['change']) + ')</p>'
            body += '<p>' + H(len(entry['unresolved_dependencies'])) + ' références hors de la baseline source.</p></details>'
    return body + '</section><p>Pour rechercher une erreur : déclarez un petit domaine d’entrées, l’attente et les limites avec behavior-states ou behavior-interfaces. Conservez le contre-exemple, corrigez le modèle et rejouez exactement son entrée.</p></div>'
