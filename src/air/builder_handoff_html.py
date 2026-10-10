"""Accessible static receipt reading. No approval action is performed in the browser."""
from air.site_handoff_html import H, source_link

STATES = {'NO_PACKAGES': 'Aucun paquet enregistré', 'INCOMPLETE': 'Transmission à compléter',
    'DRAFT_WITH_GAPS': 'Périmètre à préciser', 'AWAITING_RECEIPTS': 'Réceptions attendues',
    'CHANGES_REQUESTED': 'Changements demandés', 'BASELINE_CHANGED': 'Baseline différente',
    'RECEIVED_FOR_BUILD_PLANNING': 'Périmètre reçu pour préparer la réalisation', 'MISSING': 'Réception manquante', 'ACCEPTED': 'Accepté'}


def section(report):
    body = '<section id="builder-receipts" class="handoff-section"><h2>Réception des paquets</h2><p class="intro">' + H(STATES[report['state']]) + '</p>'
    body += '<p>Cette vue décrit la baseline exportée. La réception du périmètre ne vaut pas autorisation de lancer, livraison du logiciel ou exécution des tests. Régénérez le site après une nouvelle réception.</p>'
    for package in report['packages']:
        manifest = package['manifest']
        body += '<details class="handoff-section"><summary><strong>' + H(manifest.get('title', manifest['package_id'])) + '</strong>, version ' + str(manifest['version']) + ' : ' + H(STATES[package['state']]) + '</summary>'
        if package.get('superseded'): body += '<p>Version remplacée dans cette baseline. Conservée pour l’historique ; seule la dernière version participe à la synthèse.</p>'
        names = {p['target']['id']: p['name'] for p in manifest['packets']}
        body += '<h3>Périmètre exact</h3><ul>' + ''.join('<li>' + source_link(unit, names.get(unit['id'], unit['id']) + ' r' + str(unit['revision'])) + '</li>' for unit in manifest['units']) + '</ul>'
        body += '<p>Identifiant : <code>' + H(manifest['package_id']) + '</code></p>'
        body += '<h3>Responsabilités et réception</h3><ul>'
        for role in package['roles']:
            assignments = [r for r in manifest['responsibilities'] if r['role'] == role['role']]
            title = ', '.join(sorted({r['role_name'] + ' (' + r['team_name'] + ')' for r in assignments}))
            body += '<li><strong>' + H(title) + '</strong> : ' + H(STATES[role['state']]) + '<ul>'
            for receipt in role['receipts']:
                body += '<li>' + H(receipt['actor']) + ' : ' + H(STATES.get(receipt['outcome'], receipt['outcome'])) + '. ' + H(receipt['rationale'])
                if not receipt['effective']: body += ' Réception inactive : ' + H(', '.join(receipt['ineffective_reasons'])) + '.'
                body += '<ul>' + ''.join('<li>' + H(q) + '</li>' for q in receipt['questions']) + '</ul></li>'
            body += '</ul></li>'
        body += '</ul>'
        if manifest['gaps']: body += '<h3>Points à préciser</h3><ul>' + ''.join('<li>' + H(g['label']) + '</li>' for g in manifest['gaps']) + '</ul>'
        body += '<p>Empreinte du paquet : <code>' + H(package['package']['digest']) + '</code></p></details>'
    if report['units_without_package']:
        body += '<h3>Unités sans paquet</h3><ul>' + ''.join('<li>' + source_link(unit, unit['id'] + ' r' + str(unit['revision'])) + '</li>' for unit in report['units_without_package']) + '</ul>'
    body += '<p><a href="builder-receipts.json" download>Exporter le détail des paquets et réceptions</a></p></section>'
    return body
