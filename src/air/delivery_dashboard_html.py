"""Source-linked delivery ledger with accessible client-side filters."""
from html import escape
import json
from air.editorial import prose


def render(report, coverage, gates, object_links=None, object_names=None):
    h = lambda x: escape(prose(str(x)), quote=True)
    links = object_links or {}
    names = object_names or {}
    labels = {'PREREQUISITE_NOT_MET': 'Prérequis du socle à traiter', 'DESIGN_TRACE_GAPS': 'Chaîne de conception incomplète',
        'EVIDENCE_TRACE_GAPS': 'Preuves à relier aux tests', 'EVIDENCE_NOT_PASS': 'Résultat de test à vérifier',
        'INDEPENDENT_REJECTION': 'Rejet indépendant effectif', 'SCOPE_REVIEW_REQUIRED': 'Revue indépendante du périmètre attendue',
        'DESIGN_CONTRACTS': 'Contrats de conception documentés', 'RECORDED_TESTS': 'Tests enregistrés, qualification distincte',
        'PASS_SCOPED_GATE': 'satisfait', 'BLOCKED': 'Bloquée', 'TODO': 'À faire', 'IN_PROGRESS': 'En cours', 'DONE': 'Terminée', 'CANCELLED': 'Annulée',
        'RULE': 'règle', 'DATA': 'donnée', 'API': 'API', 'TEST': 'test', 'EVIDENCE': 'preuve', 'NO_EXPLICIT_LINK': 'aucun lien explicite',
        'EVIDENCE_CASE_MISMATCH': 'preuve rattachée à un autre test'}
    display = lambda x: h(labels.get(x, x))
    person = lambda value: h(next((v for (identity, _), v in names.items() if identity == value), value.rsplit(':', 1)[-1]))
    def source(r, name=None):
        href = links.get((r['id'], r['revision']))
        label = h(name or names.get((r['id'], r['revision']), r['id']))
        return '<a href="' + h(href) + '">' + label + '</a>' if href else label
    out = '<section data-delivery><h1>Livraison et gates par périmètre</h1><p class="intro">Voir qui avance, ce qui bloque et les dépendances du socle commun. Les tâches suivent le travail de conception déclaré.</p>'
    out += '<div class="assurance-ledger"><section><h2>Critères de sortie indépendants</h2>'
    for g in gates['gates']:
        out += '<article class="assurance-gate" data-state="' + h(g['result']) + '"><h3>' + source(g['gate'], g['name']) + '</h3><p><strong>' + ('Critères satisfaits' if g['result'] == 'PASS_SCOPED_GATE' else 'Critères à traiter') + '</strong></p>'
        if g['dependencies']: out += '<p>Prérequis : ' + ', '.join(source(d['gate']) + ' (' + display(d['result']) + ')' for d in g['dependencies']) + '.</p>'
        out += '<ul>' + ''.join('<li>' + display(b['code']) + '</li>' for b in g['blockers']) + '</ul><p>Critère : ' + display(g['verification_policy']) + '.</p><p>' + ('Revue indépendante requise.' if g.get('review_required') else 'Revue indépendante non requise par ces critères.') + ' Revues effectives : ' + str(len(g['accepted_reviews'])) + '.</p></article>'
    if not gates['gates']: out += '<p>Aucun ScopeGate défini. Déclarer les périmètres, leurs membres et leurs prérequis avant de conclure sur leurs critères.</p>'
    out += '<p>Ces critères ciblés ne remplacent ni la préparation à construire globale, ni une autorisation de lancement.</p></section><section><h2>Couverture de bout en bout</h2><p>Exigences → règles → données → API → tests → preuves.</p>'
    out += '<p><strong>' + str(coverage['totals']['covered']) + ' / ' + str(coverage['totals']['requirements']) + '</strong> exigences avec toutes les branches déclarées reliées.</p>'
    for row in coverage['requirements']:
        out += '<details><summary>' + source(row['requirement'], row['name']) + ' : ' + ('reliée' if row['status'] == 'COVERED' else 'liens à compléter') + '</summary><ul>'
        out += ''.join('<li>Manque : ' + display(g['missing_layer']) + ' (' + display(g['reason']) + ')</li>' for g in row['gaps'])
        for path in row['paths']:
            out += '<li>' + ' → '.join(source(r) for r in path['objects']) + '. Résultat déclaré : ' + h(path['declared_result']) + '.</li>'
        out += '</ul></details>'
    if not coverage['requirements']: out += '<p>Aucune exigence documentée.</p>'
    out += '<p>Une relation prouve la traçabilité déclarée, pas la correction sémantique du design. <a href="traceability-coverage.json">Lire tous les témoins exacts</a>.</p></section></div>'
    tasks = report['tasks']; teams = sorted({r['team'] for r in tasks if r['team']}); members = sorted({m for r in tasks for m in r['members']})
    out += '<h2>Travail de conception</h2><form class="delivery-filters">'
    for field, label, values in [('team', 'Équipe', teams), ('member', 'Membre', members)]:
        out += '<label>' + label + '<select data-filter="' + field + '"><option value="">Tous</option>' + ''.join('<option value="' + h(v) + '">' + person(v) + '</option>' for v in values) + '</select></label>'
    out += '<label>Semaine ISO<input type="week" data-filter="week"></label><label>Date de suivi<input type="date" data-filter="as-of" value="' + h(report['as_of']) + '"></label>'
    for field, label in [('late', 'Retard uniquement'), ('blocked', 'Bloquées uniquement')]:
        out += '<label class="delivery-check"><input type="checkbox" data-filter="' + field + '">' + label + '</label>'
    out += '<button type="reset">Réinitialiser</button></form><p data-delivery-count role="status" aria-live="polite">' + str(len(tasks)) + ' tâche(s) affichée(s).</p>'
    out += '<p data-delivery-progress></p><progress data-delivery-bar max="100" value="0" aria-label="Avancement des tâches filtrées"></progress>'
    if report['next_offset'] is not None: out += '<p>Vue limitée à ' + str(len(tasks)) + ' / ' + str(report['total_matching']) + ' tâches. Utiliser la pagination CLI/MCP pour la suite.</p>'
    out += '<div class="delivery-table"><table><caption>Statuts déclarés à la baseline. Les dates absentes ne sont pas supposées.</caption><thead><tr><th scope="col">Travail et responsabilité</th><th scope="col">Échéance</th><th scope="col">État</th><th scope="col">Blocages</th></tr></thead><tbody>'
    for row in tasks:
        data = {'team': row['team'] or '', 'members': json.dumps(row['members']), 'start': row['start'] or '', 'due': row['due'] or '', 'active': str(row['status'] not in ('DONE', 'CANCELLED')).lower(), 'blocked': str(row['blocked']).lower(), 'status': row['status']}
        attrs = ' '.join('data-' + k + '="' + h(v) + '"' for k, v in data.items())
        out += '<tr data-delivery-task ' + attrs + '><th scope="row">' + source(row['task'], row['name']) + '<small>' + (person(row['team']) if row['team'] else 'Équipe non documentée') + '<br>' + ', '.join(person(m) for m in row['members']) + '</small></th><td>' + h(row['due'] or 'Non documentée') + '<small data-late>' + ('Retard : ' + str(row['days_late']) + ' jour(s)' if row['late'] else '') + '</small></td><td>' + display(row['status']) + '</td><td>' + h(row['blocker_reason'] or '')
        out += '<ul>' + ''.join('<li>' + source(r) + '</li>' for r in row['blockers'] + row['unresolved_prerequisites']) + '</ul></td></tr>'
    out += '</tbody></table></div><p>Un travail annulé ne compte pas comme terminé. Le pourcentage de tâches terminées ne qualifie pas le dossier d’architecture.</p><p><a href="checklist.csv" download>Exporter le suivi complet en CSV</a> · <a href="delivery-dashboard.json">Données du tableau</a> · <a href="scope-gates.json">Résultats des gates</a></p><p>Excel : utiliser air_export_checklist ou CLI checklist-export avec format XLSX.</p></section>'
    # No inline script, including form event handlers, under the site CSP.
    return out
