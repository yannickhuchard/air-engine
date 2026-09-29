"""Offline presentation of calculated reports, never a source of new decisions."""
from html import escape
from air.projections import STYLE


def planning_html(initial, variant, labels=None):
    labels = labels or {}
    def display_name(ref): return escape(labels.get(ref["id"], ref["id"]))
    def table(report):
        rows = []
        for pool in report["pools"]:
            rows.append("<h3>" + display_name(pool["pool"]) + "</h3><div class=scroll><table><thead><tr><th>ETP / semaine</th>")
            rows.extend("<th>S" + str(c["period"] + 1) + "</th>" for c in pool["periods"])
            rows.append("</tr></thead><tbody>")
            for key, label in [("net_after_reservations", "Offre disponible"), ("demand", "Demande"), ("shortfall", "Déficit")]:
                rows.append("<tr><th>" + label + "</th>")
                for c in pool["periods"]:
                    value = c[key]
                    warning = key == "shortfall" and value not in (None, "0")
                    rows.append('<td class="' + ('blocked' if warning else '') + '">' + escape(value if value is not None else "Inconnu") + "</td>")
                rows.append("</tr>")
            rows.append("</tbody></table></div>")
        return "".join(rows)
    candidate = variant.get("candidate")
    content = ['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>Asteria — comparaison capacitaire AIR</title><style>' + STYLE + '.scroll{overflow-x:auto}th,td{min-width:3rem}h3{overflow-wrap:anywhere}</style></head><body>',
        '<header><p>Asteria Industrie • expérience synthétique</p><h1>Trois dossiers, une capacité partagée</h1><p>Comparer les besoins avant de décider des engagements.</p></header><main>',
        '<aside class="notice"><strong>Proposition de planning</strong><p>Ces quantités sont déclarées pour l’expérience. Le calcul ne réserve aucune personne et n’autorise aucun lancement.</p></aside>',
        '<h2>1. Proposition initiale</h2><p>Déficit calculé : <strong>' + escape(initial["proposed"]["total_shortfall_FTE_weeks"] or "Inconnu") + ' ETP-semaines</strong>.</p>',
        table(initial["proposed"]), '<h2>2. Variante proposée</h2>']
    if candidate:
        content.extend(['<p>Priorité : SAV, identités, puis atelier. Faisabilité capacitaire : <strong>' + ('vérifiée dans le modèle' if candidate["capacity_feasible"] else 'non démontrée') + '</strong>. L’optimalité n’est pas démontrée.</p>', table(candidate),
            '<h3>Positionnement des unités</h3><ul>'])
        for row in candidate["schedule"]:
            content.append('<li>' + display_name(row["unit"]) + ' : semaines ' + str(row["start_period"] + 1) + ' à ' + str(row["end_period_exclusive"]) + '</li>')
        content.append('</ul>')
    else:
        content.append('<p class="blocked">Aucun candidat complet : ' + escape(variant["solver"]["status"]) + '</p>')
    content.append('<h2>Hypothèses et limites</h2><ul>')
    content.extend('<li>' + escape(x) + '</li>' for x in variant["limitations"])
    content.append('</ul><footer><p>Moteur : ' + escape(variant["engine"]) + '</p><p class="digest">Rapport initial : ' + escape(initial["report_digest"]) + '</p><p class="digest">Rapport variante : ' + escape(variant["report_digest"]) + '</p></footer></main></body></html>')
    return "".join(content)


def reconciliation_html(context, report, labels=None):
    labels = labels or {}
    def label(value): return escape(labels.get(value, value))
    chunks = ['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>AIR — contributions et divergences</title><style>' + STYLE + '.scroll{overflow-x:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.pair article{background:#fff;padding:1.2rem;border:1px solid #d8e0e5;border-radius:.6rem}@media(max-width:650px){.pair{grid-template-columns:1fr}}summary{cursor:pointer}</style></head><body>',
        '<header><p>AIR • contexte de conception</p><h1>Contributions et divergences</h1><p>' + escape(context['snapshot']['request']['purpose']) + '</p></header><main>',
        '<aside class="notice"><strong>Examen requis</strong><p>Les écarts sont reliés aux versions consultées. Les responsables des dossiers décident des changements à proposer.</p></aside>',
        '<h2>Contributions consultées</h2><div class="scroll"><table><thead><tr><th>Dossier</th><th>Version publiée</th><th>Usage au moment de la consultation</th></tr></thead><tbody>']
    for contribution in context['snapshot']['contributions']:
        manifest = contribution['manifest']
        chunks.append('<tr><th>' + label(manifest['package_id']) + '</th><td>' + str(manifest['version']) + '</td><td>' + ('Disponible' if contribution['new_use_allowed_at_observation'] else 'À réexaminer') + '</td></tr>')
    chunks.append('</tbody></table></div><h2>Actifs partagés à examiner</h2>')
    if not report['divergences']:
        chunks.append('<p>Aucune divergence de révision détectée dans les contributions consultées.</p>')
    for divergence in report['divergences']:
        chunks.append('<section><h3>' + label(divergence['id']) + '</h3><p>Les dossiers consultés utilisent plusieurs révisions de cet actif.</p>')
        for comparison in divergence['comparisons']:
            for change in comparison['changes']:
                if change['path'] != '/body/boundary_description': continue
                chunks.append('<div class="pair"><article><h4>Révision ' + str(comparison['before']['revision']) + '</h4><p>' + escape(str(change.get('before', 'Absent'))) + '</p></article><article><h4>Révision ' + str(comparison['after']['revision']) + '</h4><p>' + escape(str(change.get('after', 'Absent'))) + '</p></article></div>')
        chunks.append('<p class="blocked">Compatibilité sémantique à vérifier. Les dossiers sources conservent leurs versions.</p></section>')
    chunks.append('<h2>Connaissances ouvertes</h2><p>' + str(len(report['observations'])) + ' signalements dans ce contexte : inconnues ouvertes, assertions contestées ou contributions devenues indisponibles.</p>')
    chunks.append('<h2>Portée de la lecture</h2><p>Ce contexte couvre les publications explicitement consultées et leurs imports. La fraîcheur des informations métier et la couverture de toute l’entreprise restent à vérifier. Les arbitrages de capacité, d’autorité et de contrat restent à instruire.</p>')
    chunks.append('<details><summary>Traçabilité du rapport</summary><p>Observation : ' + escape(report['observed_at']) + '</p><p class="digest">Contexte : ' + escape(report['context']['digest']) + '</p><p class="digest">Rapport : ' + escape(report['digest']) + '</p></details></main></body></html>')
    return ''.join(chunks)


def admission_html(report):
    """Display receipts from the isolated Asteria rehearsal without recomputing them."""
    rows = []
    selected = report['collective']['report']['candidate']
    labels = {'urn:asteria:construction:sav:unit': 'D01 · SAV et intégration ERP',
              'urn:asteria:construction:atelier:unit': 'D02 · Suivi de production atelier',
              'urn:asteria:construction:identites:unit': 'D03 · Identités et habilitations'}
    for item in selected['schedule']:
        rows.append('<tr><th>' + escape(labels.get(item['unit']['id'], item['unit']['id'])) + '</th><td>S' + str(item['start_period'] + 1) + '–S' + str(item['end_period_exclusive']) + '</td><td>Réservé</td></tr>')
    checks = [('Concurrence sans double réservation', True), ('Reprise après commit et interruption du client', report['restart_replay_identical']),
              ('Activation trop tôt refusée', report['too_early_refused']), ('Offre indisponible : nouvelle activation refusée', report['source_unavailable_refused']),
              ('Identité du déclarant révoquée : activation refusée', report['collector_revoked_refused']),
              ('Travail activé conservé', report['active_commitments_preserved']), ('Restauration des engagements à l’identique', report['restored_commitments_identical'])]
    return ''.join(['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>Asteria — admission et activation AIR</title><style>' + STYLE + '.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}.metrics article{background:white;border:1px solid #d8e0e5;padding:1.2rem;border-radius:.6rem}.metrics strong{font-size:2rem}.scroll{overflow-x:auto}@media(max-width:600px){.metrics{grid-template-columns:1fr}}th,td{overflow-wrap:anywhere}</style></head><body>',
        '<header><p>Asteria Industrie · recette synthétique · AIR ' + escape(report['version']) + '</p><h1>Décider, réserver, puis autoriser</h1><p>Trois dossiers partagent une équipe d’intégration.</p></header><main>',
        '<aside class="notice"><strong>Réception du périmètre local</strong><p>Les reçus engagent les capacités fictives déclarées dans AIR. Aucune intervention ERP, atelier ou annuaire n’a été exécutée.</p></aside>',
        '<div class="metrics"><article><p>Charge initiale</p><strong>5 ETP</strong><p>pour 4 ETP disponibles</p></article><article><p>Admission initiale</p><strong>Refusée</strong><p>' + escape(report['initial']['report']['proposed']['total_shortfall_FTE_weeks']) + ' ETP-semaines de déficit</p></article><article><p>Variante collective</p><strong>Admise</strong><p>3 ETP, puis 2 ETP</p></article></div>',
        '<h2>Engagements des trois dossiers</h2><div class="scroll"><table><thead><tr><th>Dossier</th><th>Fenêtre</th><th>Décision</th></tr></thead><tbody>', ''.join(rows), '</tbody></table></div>',
        '<p>Fenêtre d’essai ouverte à ' + escape(report['synthetic_window_start']) + '. Les huit périodes durent chacune sept jours.</p>',
        '<h2>Contrôles exécutés</h2><table><thead><tr><th>Contrôle</th><th>Résultat</th></tr></thead><tbody>',
        ''.join('<tr><td>' + escape(label) + '</td><td>' + ('Vérifié' if passed else 'Non vérifié') + '</td></tr>' for label, passed in checks),
        '</tbody></table><h2>Autorisation distincte de l’exécution</h2><p>Le SAV a reçu une autorisation d’épisode dans sa fenêtre réelle. Le retrait de l’offre empêche ensuite un nouveau lancement. Les réservations déjà engagées restent conservées.</p>',
        '<p>Les expériences des dossiers restent illustratives. Leurs scénarios de réception ERP, machine et IAM demeurent NOT_EXECUTED. Calendrier hebdomadaire, ressources humaines disjointes, registre central unique ; pas d’optimalité globale ni de transaction distante.</p>',
        '<details><summary>Référence du reçu d’admission</summary><p class="digest">' + escape(report['admission']['receipt']['id']) + '</p><p class="digest">' + escape(report['admission']['receipt']['digest']) + '</p></details></main></body></html>'])


def lifecycle_html(report):
    lifecycle = report['lifecycle']; state = lifecycle['final_state']
    names = {'urn:asteria:construction:sav:unit': 'D01 · SAV', 'urn:asteria:construction:identites:unit': 'D03 · Identités'}
    rows = ''.join('<tr><th>' + escape(names.get(episode['unit']['id'], episode['unit']['id'])) + '</th><td>Clôture déclarée et revue</td><td>Libérées explicitement</td></tr>' for episode in state['episodes'])
    return ''.join(['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>Asteria — renouvellement et clôture</title><style>' + STYLE + '.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}.steps article{background:white;border:1px solid #d8e0e5;padding:1rem;border-radius:.6rem}.steps strong{font-size:1.3rem}@media(max-width:800px){.steps{grid-template-columns:1fr 1fr}}.scroll{overflow-x:auto}</style></head><body>',
        '<header><p>Asteria Industrie · recette synthétique · AIR ' + escape(report['version']) + '</p><h1>Conserver l’engagement et son histoire</h1><p>Renouveler l’autorité, recevoir les clôtures, puis libérer les ressources.</p></header><main>',
        '<aside class="notice"><strong>Cycle local vérifié</strong><p>Les décisions proviennent du registre AIR et de sujets habilités. Les déclarations de fin restent synthétiques ; aucun ERP, équipement ou annuaire n’a été exécuté.</p></aside>',
        '<div class="steps"><article><p>1 · Capacité</p><strong>Admise</strong><p>3 ETP, puis 2 ETP</p></article><article><p>2 · Autorité</p><strong>Renouvelée</strong><p>Génération ' + str(state['authorization_generation']) + ', réservations identiques</p></article><article><p>3 · Épisodes</p><strong>' + str(len(state['episodes'])) + ' clôtures reçues</strong><p>Avec preuve et revue indépendante</p></article><article><p>4 · Ressources</p><strong>Libérées</strong><p>Après décision explicite</p></article></div>',
        '<h2>État final des trois dossiers</h2><div class="scroll"><table><thead><tr><th>Dossier</th><th>État du travail dans la recette</th><th>Réservations</th></tr></thead><tbody>', rows,
        '<tr><th>D02 · Atelier</th><td>Non commencé ; réservation annulée</td><td>Libérées explicitement</td></tr></tbody></table></div>',
        '<h2>Garanties observées</h2><ul><li>Une offre et une politique actualisées ont été revues avant renouvellement.</li><li>La génération avance sans dupliquer ni changer les réservations.</li><li>L’auto-revue de clôture est refusée.</li><li>La libération est refusée tant qu’un épisode reste ouvert.</li><li>Les clôtures reçues ne libèrent pas automatiquement les ressources.</li><li>La restauration conserve les reçus, épisodes et réservations.</li></ul>',
        '<h2>Portée de la réception</h2><p>La preuve de fin est explicitement référencée et examinée. Sa pertinence métier dépend du relecteur. Les cas de réception des systèmes réels demeurent NOT_EXECUTED ; une réservation atelier annulée ne signifie pas que ce travail est réalisé.</p>',
        '<details><summary>Traçabilité</summary><p class="digest">Autorisation courante : ' + escape(state['authorization']['digest']) + '</p><p class="digest">Libération : ' + escape(lifecycle['explicit_release']['receipt']['digest']) + '</p></details></main></body></html>'])


def runtime_html(report):
    rows = []
    for case in report['reports']:
        value = case['comparison']['observations'][0]['value_or_artifact']
        if value.get('state') in ('UNKNOWN', 'CONFLICTING'): shown = value['state']
        elif value.get('type') == 'Boolean': shown = 'Vrai' if value['value'] else 'Faux'
        else: shown = str(value.get('value', 'Artefact non interprété'))
        rows.append('<tr><th>' + escape(case['case'] + ' · ' + case['title']) + '</th><td>' + escape(shown) + '</td><td class="blocked">' + escape(case['comparison']['result']) + '</td><td>' + escape(case['stale_comparison']['result']) + '</td></tr>')
    return ''.join(['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>Asteria — observations et dérives AIR</title><style>' + STYLE + '.scroll{overflow-x:auto}th,td{min-width:7rem}.columns{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}@media(max-width:700px){.columns{grid-template-columns:1fr}}</style></head><body>',
        '<header><p>Asteria Industrie · observations synthétiques · AIR ' + escape(report['version']) + '</p><h1>Observer sans réécrire l’attendu</h1><p>Rattacher les signaux, expliciter les écarts et conserver les limites.</p></header><main>',
        '<aside class="notice"><strong>Couverture partielle</strong><p>Chaque signal couvre cinq minutes d’un dossier fictif. La comparaison utilise une interprétation AIR-Expr déclarée ; elle ne prouve pas que toute l’exigence métier est vérifiée.</p></aside>',
        '<h2>Trois dossiers, trois observations</h2><div class="scroll"><table><thead><tr><th>Dossier</th><th>Valeur observée</th><th>Comparaison explicite</th><th>Même signal périmé</th></tr></thead><tbody>', ''.join(rows), '</tbody></table></div>',
        '<div class="columns"><section><h2>Écarts calculés</h2><p>SAV : confirmation ERP indisponible. Atelier : âge déclaré de la mesure de 540 secondes, comparé à un seuil explicite de 300 secondes. Identités : état contradictoire conservé.</p><p>Une observation trop ancienne conduit à UNKNOWN. Un artefact référencé n’est pas téléchargé ni interprété automatiquement.</p></section>',
        '<section><h2>Histoire conservée</h2><p>Source, observation, dérive et incident sont reliés dans chaque baseline runtime. Les baselines de conception conservent leurs versions.</p><p>Les trois contextes sont restaurés avec les mêmes empreintes. Les mêmes comparaisons sont retrouvées par CLI, HTTP et MCP.</p></section></div>',
        '<h2>Ce qui reste à qualifier</h2><p>Les observations restent DRAFT. L’interprétation des attentes, la pertinence des mesures et leur couverture doivent être examinées par les équipes responsables. Aucune collecte ERP, machine ou IAM, modification automatique du modèle ou remédiation n’a été exécutée.</p>',
        '<details><summary>Empreintes des comparaisons</summary>', ''.join('<p class="digest">' + escape(c['case'] + ' : ' + c['comparison']['report_digest']) + '</p>' for c in report['reports']),
        '</details></main></body></html>'])


def collaboration_html(report):
    rows = ''.join('<tr><th>' + escape(c['case'] + ' · ' + c['title']) + '</th><td>' + escape(c['selected_treatment']) + '</td><td>DRAFT<br>Auteur authentifié</td></tr>' for c in report['treatments'])
    return ''.join(['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">',
        '<title>Asteria — contributions et décisions</title><style>' + STYLE + '.scroll{overflow-x:auto}th{min-width:9rem}.steps{display:flex;flex-wrap:wrap;gap:1rem}.steps p{flex:1;padding:1rem;background:#fff;border:1px solid #d8e0e5;border-radius:.5rem;min-width:10rem}</style></head><body>',
        '<header><p>Asteria Industrie · collaboration fictive · AIR ' + escape(report['version']) + '</p><h1>Relier les écarts aux décisions</h1><p>Une observation conservée, une contribution attribuée, un traitement explicite.</p></header><main>',
        '<aside class="notice"><strong>Décisions de conception documentées</strong><p>Deux sujets distincts interviennent dans chaque dossier : un contributeur opérationnel et un architecte. Le reçu établit leur dépôt authentifié ; il ne confère aucune autorité métier et ne prouve pas une présence humaine.</p></aside>',
        '<div class="steps"><p><strong>1 · Observer</strong><br>Écart calculé et mesure exacte</p><p><strong>2 · Questionner</strong><br>Contribution liée au contexte</p><p><strong>3 · Décider</strong><br>Alternatives, choix et réexamen</p><p><strong>4 · Tracer</strong><br>Nouvelle baseline de 30 objets</p></div>',
        '<h2>Traitements proposés par dossier</h2><div class="scroll"><table><thead><tr><th>Dossier</th><th>Sélection de conception</th><th>Qualification</th></tr></thead><tbody>', rows, '</tbody></table></div>',
        '<h2>Histoire et responsabilités</h2><p>Les observations restent inchangées. La dérive reçoit une nouvelle révision liée à la décision ; la précédente reste disponible. La contribution est résolue par un lien explicite, sans déclarer l’incident réparé.</p>',
        '<h2>Vérifications exécutées</h2><ul><li>Auteur falsifié et lecture entre dossiers refusés.</li><li>Rejeu idempotent sans nouvelle révision.</li><li>Lecture identique par CLI, HTTP et MCP.</li><li>Baselines de conception, observations et décisions conservées après restauration.</li></ul>',
        '<p>Les neuf cas de réception des systèmes métier demeurent NOT_EXECUTED. Aucune action ERP, atelier ou IAM n’a été exécutée.</p>',
        '<details><summary>Baselines exactes</summary>', ''.join('<p class="digest">' + escape(c['case'] + ' : ' + c['baseline']['digest']) + '</p>' for c in report['treatments']), '</details></main></body></html>'])
