"""Escaped, source-linked HTML views of the handoff projection."""
from html import escape as escape
from air.deliverables import mid, label
from air.editorial import prose
from air.site_handoff import SECTIONS, key
from air.site_questions import GATE_LABELS


def H(value): return escape(prose(str(value)))
def anchor(ref): return mid(ref['id'] + ':' + str(ref['revision']))
def focus_path(ref): return 'handoff-' + anchor(ref) + '.html'
def team_path(ref): return 'handoff-team-' + anchor(ref) + '.html'
def source_link(ref, text): return '<a href="objects.html#' + anchor(ref) + '">' + H(text) + '</a>'

FIELDS = {
    'responsibilities': 'Responsabilités', 'responsibility': 'Responsabilité', 'work_kind': 'Nature du travail',
    'outputs': 'Livrables attendus', 'statement': 'Exigence', 'condition': 'Condition d’acceptation',
    'method': 'Méthode', 'oracle': 'Résultat attendu', 'acceptance': 'Critère de vérification',
    'result': 'Résultat consigné', 'proof_level': 'Niveau de preuve', 'executed_at': 'Date consignée',
    'summary': 'Compte rendu', 'mandate': 'Mandat', 'activity': 'Activité', 'phase': 'Phase',
    'subject': 'Sujet exact', 'role': 'Rôle', 'rationale': 'Raison', 'consequences': 'Conséquences',
    'purpose': 'But', 'protocol': 'Protocole', 'target_date': 'Date cible déclarée',
    'exit_criteria': 'Critères de sortie', 'basis': 'Base déclarée', 'confidence': 'Confiance déclarée',
    'authorization': 'Autorisation attendue', 'compatibility_policy': 'Politique de compatibilité',
}
PREVIEWS = {
    'ArchitectureBlock': ['responsibilities'], 'RuntimeComponent': ['responsibility'],
    'ConstructionUnit': ['work_kind', 'outputs'], 'Requirement': ['statement'],
    'AcceptanceCriterion': ['condition', 'verification_method'],
    'VerificationCase': ['method', 'oracle', 'acceptance'],
    'VerificationRun': ['method', 'result', 'proof_level', 'executed_at', 'summary'],
    'OrganizationUnit': ['mandate'], 'Role': ['responsibilities'],
    'RaciAssignment': ['activity', 'phase', 'responsibility', 'subject', 'role'],
    'SemanticContract': ['authorization', 'compatibility_policy'], 'Connection': ['purpose', 'protocol'],
    'Milestone': ['target_date', 'exit_criteria'], 'QualityRequirement': ['statement', 'verification_method'],
    'Estimate': ['basis', 'confidence'], 'DeliveryEstimate': ['basis', 'confidence'],
    'Decision': ['rationale', 'consequences'],
}
RELATIONS = {'realizes': 'Réalise', 'functions': 'Fonction du bloc', 'provided_contracts': 'Fournit',
             'required_contracts': 'Requiert', 'owned_state': 'État déclaré', 'justified_by': 'Justifié par',
             'acceptance': 'Critère prévu', 'cases': 'Cas prévu', 'estimate': 'Estimation',
             'satisfies': 'Satisfait (déclaré)', 'exceptions': 'Échec prévu', 'target': 'Cible',
             'case': 'Cas du résultat', 'subject': 'Sujet RACI', 'role': 'Rôle', 'roles': 'Rôle de l’équipe',
             'operations': 'Expose la fonction', 'block': 'Bloc du port', 'contract': 'Contrat du port',
             'bindings': 'Binding déclaré', 'environment': 'Environnement', 'zone': 'Zone',
             'technologies': 'Technologie', 'stores': 'Donnée déclarée', 'store': 'Stockage',
             'implements': 'Implémente (déclaré)', 'source': 'Source', 'evidence': 'Preuve consignée',
             'deliverables': 'Livrable du jalon', 'unit': 'Unité estimée', 'scope': 'Périmètre', 'basis': 'Base du choix'}


def value(data, graph):
    if isinstance(data, dict):
        obj = graph.get(data) if 'id' in data and 'revision' in data else None
        if obj: return source_link(data, obj['meta']['name']) + ' <small>r' + str(data['revision']) + '</small>'
        return '<dl>' + ''.join('<dt>' + H(FIELDS.get(k, k)) + '</dt><dd>' + value(v, graph) + '</dd>' for k, v in data.items()) + '</dl>'
    if isinstance(data, list):
        return '<ul>' + ''.join('<li>' + value(v, graph) + '</li>' for v in data) + '</ul>' if data else '<span>Non déclaré</span>'
    return H(data) if data is not None else 'Non déclaré'


def context(model):
    p = model['baseline']
    return '<details class="reading-context"><summary>Contexte exact et limites</summary><p>Baseline <code>' + H(p['id']) + '</code>, révision ' + str(p['revision']) + '.</p><p>Empreinte : <code>' + H(p['digest']) + '</code>.</p><p>Les fiches rapprochent des liens typés explicites. Elles ne calculent ni ordre de livraison, ni responsabilité héritée, ni autorisation d’exécuter. Le public choisi ne filtre pas les données exportées.</p><a href="handoff.json">Télécharger les fiches et leurs sources exactes</a></details>'


def card(source, graph):
    kind = source['type'].removeprefix('air.')
    text = '<article class="handoff-source"><h3>' + source_link(source['reference'], source['name']) + '</h3><p class="question-state">' + H(kind) + ' · révision ' + str(source['reference']['revision']) + ' · ' + H(source['lifecycle']) + '</p>'
    if kind == 'VerificationCase': text += '<p><strong>Cas prévu.</strong> Les résultats éventuels sont présentés séparément avec leur niveau de preuve.</p>'
    if kind == 'VerificationRun': text += '<p><strong>Résultat consigné dans la baseline.</strong> Cette page ne réexécute pas la vérification et ne vaut pas réception du système réalisé.</p>'
    text += '<p>' + H(source['description']) + '</p>'
    fields = [(k, source['body'][k]) for k in PREVIEWS.get(kind, []) if k in source['body']]
    if fields:
        text += '<dl>' + ''.join('<dt>' + H(FIELDS.get(k, k)) + '</dt><dd>' + value(v, graph) + '</dd>' for k, v in fields) + '</dl>'
    text += '<p>' + source_link(source['reference'], 'Lire la déclaration complète et son empreinte') + '</p></article>'
    return text


def diagram_code(packet, sources):
    ids = [key(packet['target'])] + sorted({key(link['source']) for link in packet['links']} | {key(link['target']) for link in packet['links'] if link['resolved']})
    ids = list(dict.fromkeys(ids)); selected = ids[:24]
    code = ['flowchart TB']
    for k in selected:
        if k not in sources: continue
        source = sources[k]; code.append('  ' + anchor(source['reference']) + '[' + label(source['name'] + ' · ' + source['type'][4:]) + ']')
    drawn = []
    for link in packet['links']:
        if link['resolved'] and key(link['source']) in selected and key(link['target']) in selected:
            drawn.append(link)
    for link in drawn[:48]:
        relation = RELATIONS.get(link['selector'].split('/')[2], link['selector'])
        code.append('  ' + anchor(link['source']) + ' -->|' + label(relation) + '| ' + anchor(link['target']))
    return '\n'.join(code), len(ids) > 24 or len(drawn) > 48


def pages(model, graph, render_diagram, receipt_report=None):
    sources = {key(s['reference']): s for s in model['sources']}
    intro = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Transmission</nav>'
    body = intro + '<h1>Préparer la réalisation</h1><p class="intro">Choisissez un composant ou une équipe. Retrouvez ce qui est déclaré, ce qui sera à construire et les questions à résoudre avant de vous engager.</p>'
    body += '<p class="gate">' + H(GATE_LABELS.get(model['gate']['code'], model['gate']['code'])) + '. <a href="28-preparation-construction.html">Examiner les critères du dossier</a></p>'
    body += '<h2>Composants et unités de construction</h2><div class="handoff-list">'
    for packet in model['packets']:
        body += '<article><h3><a href="' + focus_path(packet['target']) + '">' + H(packet['name']) + '</a></h3><p>' + H(packet['type'][4:]) + ' · ' + str(len(packet['gaps'])) + ' point(s) à préciser.</p></article>'
    if not model['packets']: body += '<p>Aucun bloc, composant d’implantation ou unité de construction du namespace de ce dossier n’est déclaré. Définissez le périmètre de réalisation avec l’architecte.</p>'
    body += '</div><h2>Équipes déclarées</h2><div class="handoff-list">'
    for team in model['teams']:
        body += '<article><h3><a href="' + team_path(team['target']) + '">' + H(team['name']) + '</a></h3><p>' + str(len(team['assignments'])) + ' affectation(s) RACI, dont ' + str(len(team['unscoped_assignments'])) + ' sans sujet précis.</p></article>'
    if not model['teams']: body += '<p>Aucune équipe de ce dossier n’est déclarée. Le propriétaire d’un objet n’est pas une affectation de réalisation. Convenez des rôles et sujets RACI avec les équipes concernées.</p>'
    body += '</div><h2>Questions communes à la transmission</h2><ul><li><a href="06-organisation-realisation-raci.html">Organisation de réalisation</a></li><li><a href="07-organisation-exploitation.html">Organisation d’exploitation</a></li><li><a href="role-realisation.html">Parcours des équipes de réalisation</a></li></ul>' + context(model)
    if receipt_report is not None:
        from air.builder_handoff_html import section
        body += section(receipt_report)
    result = [('handoff.html', 'Préparer la réalisation', body)]
    for packet in model['packets']:
        source = sources[key(packet['target'])]; path = focus_path(packet['target']); diagram_path = 'diagram-' + path
        code, limited = diagram_code(packet, sources)
        note = '<p>Chaque flèche résume un lien déclaré ; le JSON conserve son champ source exact. Ce dessin ne représente ni une exécution ni un ordre de développement.' + (' Vue limitée à 24 objets et 48 liens ; la fiche et le JSON conservent le détail.' if limited else '') + '</p>'
        body = intro + '<h1>' + H(packet['name']) + '</h1><p class="intro">' + H(source['description']) + '</p><p>' + source_link(packet['target'], 'Ouvrir la définition exacte du sujet') + '</p><p><a href="handoff.html">Choisir un autre composant ou une équipe</a></p>'
        body += '<section class="handoff-gaps" id="handoff-gaps"><h2>Ce qui reste à préciser</h2><ul>' + ''.join('<li><strong>' + H(g['label']) + '</strong><p>' + H(g['next_action']) + '</p></li>' for g in packet['gaps']) + '</ul>'
        if not packet['gaps']: body += '<p>Aucun manque détecté par ces contrôles de présence. La présence des déclarations ne prouve ni complétude ni approbation.</p>'
        body += '</section><nav class="handoff-toc" aria-label="Sections de la fiche"><a href="#handoff-map">Voir le périmètre</a>' + ''.join('<a href="#handoff-' + s + '">' + H(title) + '</a>' for s, title in SECTIONS) + '</nav>'
        body += '<section id="handoff-map"><h2>Liens du périmètre</h2>' + note + render_diagram(code, diagram_path, 'Liens déclarés de ' + packet['name']) + '</section>'
        for section, title in SECTIONS:
            body += '<section id="handoff-' + section + '" class="handoff-section"><h2>' + H(title) + '</h2>'
            if packet['sections'][section]: body += ''.join(card(sources[key(ref)], graph) for ref in packet['sections'][section])
            else: body += '<p>Aucun objet lié dans cette section de la fiche. Consulter le sujet global du dossier avant de conclure à une absence.</p>'
            if section == 'delivery': body += '<p><a href="35-exigences-non-fonctionnelles.html">Examiner aussi les exigences de qualité du dossier</a>. Une exigence globale n’est pas attribuée automatiquement à ce composant.</p>'
            body += '</section>'
        if packet['unresolved']: body += '<h2>Références à résoudre</h2>' + value(packet['unresolved'], graph)
        body += context(model)
        result.append((path, packet['name'], body))
        result.append((diagram_path, 'Liens déclarés de ' + packet['name'], intro + '<h1>Liens déclarés de ' + H(packet['name']) + '</h1><p><a href="' + path + '#handoff-map">Revenir à la fiche et à ses questions</a></p>' + note + render_diagram(code, title='Liens déclarés du périmètre') + context(model)))
    for team in model['teams']:
        body = intro + '<h1>' + H(team['name']) + '</h1><p class="intro">Lire les activités et sujets attribués aux rôles de cette équipe.</p><p><a href="handoff.html">Revenir à la transmission</a></p>' + card(sources[key(team['target'])], graph)
        body += '<h2>Composants associés à des affectations explicites</h2><ul>' + ''.join('<li><a href="' + focus_path(ref) + '">' + H(sources[key(ref)]['name']) + '</a></li>' for ref in team['foci']) + '</ul>'
        if not team['foci']: body += '<p>Aucune affectation avec un sujet précis ne relie cette équipe à une fiche. Convenir des activités et de leurs sujets avant de répartir la réalisation.</p>'
        body += '<h2>Rôles et activités déclarés</h2>'
        body += ''.join(card(sources[key(ref)], graph) if key(ref) in sources else '<p>Rôle non résolu : ' + H(ref['id']) + ' r' + str(ref['revision']) + '.</p>' for ref in team['roles'])
        body += ''.join(card(sources[key(ref)], graph) for ref in team['assignments'])
        if team['unscoped_assignments']: body += '<p><strong>Affectations sans sujet précis :</strong> elles restent générales au dossier et ne sont pas attribuées à tous ses composants.</p>'
        if not team['assignments']: body += '<p>Aucune affectation RACI n’est déclarée pour les rôles de cette équipe. Définir les activités avec les responsables habilités.</p>'
        body += context(model); result.append((team_path(team['target']), team['name'], body))
    return result
