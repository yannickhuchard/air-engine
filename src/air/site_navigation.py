"""One reading hierarchy for the sidebar, chapter pages and dossier overview.

Reading order is presentation only. It never changes readiness or model revisions.
"""
from dataclasses import dataclass
from html import escape as H

ENGINE = 'air.reading-navigation/1'

# A topic number appears once. Tuples are complementary generated views, not
# duplicate ownership of the topic. Their URLs and the canonical topic IDs stay stable.
STAGES = [
    ('cadrage', 'Cadrer la demande', 'Pourquoi ce projet, pour qui et avec quels moyens ?', [
        ('Valeur et périmètre', ['23', '02', '14']),
        ('Parties prenantes', ['38', '05']),
        ('Finance', [('finance', 'Budget, coûts et contingence'), '17']),
    ]),
    ('usages', 'Décrire les usages', 'Ce qui change pour les clients, les équipes et leurs activités.', [
        ('Expérience client', [('journeys', 'Cartes des parcours clients'), '03', '30']),
        ('Processus et règles métier', [('processes', 'Lire les processus en couloirs'), '04', '11', ('business-paths', 'Suivre un chemin de bout en bout')]),
    ]),
    ('solution', 'Concevoir la solution', 'Les choix, les responsabilités des composants et leurs interactions.', [
        ('Principes et décisions', ['24', '25']),
        ('Application et intégration', [('graph', 'Explorer le graphe d’architecture'), '01', '09', '10', '29']),
    ]),
    ('donnees', 'Structurer les données', 'Du langage partagé aux données logiques puis à leur stockage.', [
        ('Sémantique et information', ['18']),
        ('Modèles de données', ['19', '20']),
    ]),
    ('qualite', 'Maîtriser la qualité et les risques', 'Les engagements, protections et incertitudes à traiter.', [
        ('Qualité, sécurité et contrôles', ['35', '22', '34']),
        ('Risques, hypothèses et écarts', ['16', '12', '15']),
    ]),
    ('construction', 'Préparer la construction', 'Ce que les équipes devront construire, organiser et exploiter.', [
        ('Technologies et déploiement', ['26', '08', '21', '31']),
        ('Organisation et transmission', [('handoff', 'Dossier de transmission aux équipes'), '06', '07']),
        ('Trajectoire et effort', ['37', '27', '36']),
    ]),
    ('validation', 'Vérifier et piloter', 'Les critères de réception, les preuves et le travail encore à suivre.', [
        ('Vérification et réception', ['13', ('traceability', 'Du besoin aux livrables : Sankey'), '32', '33', ('verification', 'Vérifications et impact des changements'), ('completeness', 'Complétude et contrats de construction'), '28']),
        ('Suivi de la transformation', [('news', 'News, décisions et questions ouvertes'), ('delivery-dashboard', 'Livraison, retards et blocages'), ('transformation', 'Programmes, projets et tâches')]),
    ]),
]

INTRO = [('index', 'Vue d’ensemble du dossier'), ('management-summary', 'Synthèse pour le management'), ('story', 'Récit de l’architecture')]
AUDIENCES = [('role-metier', 'Présenter au métier'), ('role-comex', 'Arbitrer au COMEX'), ('role-realisation', 'Transmettre aux équipes')]
TOOLS = [('questions', 'Rechercher une réponse'), ('cooperate', 'Travailler avec un assistant'), ('completion', 'Progression avec un agent'), ('objects', 'Objets, définitions et sources'), ('../../timeline', 'Comparer les états et les dates')]
AUDIENCE_QUESTIONS = {
    'cadrage': ('Quel problème veut-on résoudre, pour qui et avec quelle valeur ?', 'Quel périmètre, quels interlocuteurs et quelle enveloppe faut-il prendre en compte ?'),
    'usages': ('Comment le service changera-t-il les parcours et le travail quotidien ?', 'Quels parcours, points de contact, règles et cas particuliers faut-il couvrir ?'),
    'solution': ('Comment la solution répond-elle au besoin et pourquoi ces choix ?', 'Quels composants et contrats portent les responsabilités et comment coopèrent-ils ?'),
    'donnees': ('Quelles informations partage-t-on et que signifient-elles ?', 'Quels modèles logiques, identités et structures de stockage faut-il implémenter ?'),
    'qualite': ('Quels engagements et risques devons-nous accepter ou revoir ?', 'Quels niveaux de qualité, protections et comportements en échec faut-il vérifier ?'),
    'construction': ('Qui réalisera le changement et selon quelle trajectoire ?', 'Que faut-il construire, livrer et préparer pour l’exploitation, avec quelles dépendances ?'),
    'validation': ('Quelles décisions et preuves permettent de poursuivre le projet ?', 'Quels critères de réception, tests et réserves doivent accompagner la transmission ?'),
}


@dataclass(frozen=True)
class Navigation:
    html: str
    context: str


def stages(topics):
    by = {topic['name'][:2]: topic for topic in topics}
    result = []
    for index, (ident, title, purpose, dimensions) in enumerate(STAGES, 1):
        groups = []
        for label, items in dimensions:
            entries = []
            for item in items:
                if isinstance(item, tuple):
                    name, text = item
                    entries.append({'key': name, 'href': name + '.html', 'label': text, 'topic': False})
                elif item in by:
                    topic = by[item]
                    entries.append({'key': topic['name'], 'href': topic['name'] + '.html', 'label': topic['title'], 'topic': True})
            if entries: groups.append({'label': label, 'entries': entries})
        result.append({'id': ident, 'number': index, 'title': title, 'purpose': purpose,
                       'key': 'lecture-' + ident, 'href': 'lecture-' + ident + '.html', 'dimensions': groups})
    return result


def canonical(active):
    if active.startswith(('handoff-', 'diagram-handoff')): return 'handoff'
    return active or 'index'


def anchor(key, label, active, css=''):
    return '<a ' + ('class="' + css + '" ' if css else '') + ('aria-current="page" ' if key == active else '') + 'href="' + H(key + '.html', quote=True) + '">' + H(label) + '</a>'


def context(sequence, current, dimension=None):
    index = sequence.index(current)
    out = '<nav class="reading-position" aria-label="Progression de lecture"><div><span>Lecture du dossier, partie ' + str(current['number']) + ' sur ' + str(len(sequence)) + '</span><a href="' + current['href'] + '">' + H(current['title']) + '</a>'
    if dimension: out += '<small>Dimension : ' + H(dimension) + '</small>'
    out += '</div><div class="reading-neighbours">'
    if index:
        previous = sequence[index - 1]
        out += '<a rel="prev" href="' + previous['href'] + '"><small>Partie précédente</small>' + H(previous['title']) + '</a>'
    if index + 1 < len(sequence):
        following = sequence[index + 1]
        out += '<a rel="next" href="' + following['href'] + '"><small>Partie suivante</small>' + H(following['title']) + '</a>'
    return out + '</div></nav>'


def render(topics, roles, active=''):
    active = canonical(active)
    sequence = stages(topics)
    current = next((stage for stage in sequence if stage['key'] == active or any(entry['key'] == active for group in stage['dimensions'] for entry in group['entries'])), None)
    dimension = next((group['label'] for group in current['dimensions'] if any(entry['key'] == active for entry in group['entries'])), None) if current else None
    out = '<div class="dossier-navigation"><div class="nav-introduction">' + ''.join(anchor(k, label, active, 'dossier-home') for k, label in INTRO) + '</div>'
    out += '<div class="nav-audiences"><p>Choisir ma lecture</p><ul>' + ''.join('<li>' + anchor(key, label, active) + '</li>' for key, label in AUDIENCES) + '</ul></div><p class="nav-sequence-label">Du besoin à la réalisation</p><ol class="nav-stages">'
    for stage in sequence:
        opened = stage == current
        out += '<li><details class="nav-stage" data-nav-stage="' + stage['id'] + '"' + (' open data-nav-active="true"' if opened else '') + '><summary><span class="nav-step-number">' + str(stage['number']) + '</span><span>' + H(stage['title']) + '</span></summary>'
        out += anchor(stage['key'], 'Comprendre cette partie', active, 'nav-stage-overview')
        for group in stage['dimensions']:
            out += '<div class="nav-dimension"><h3>' + H(group['label']) + '</h3><ul>' + ''.join('<li>' + anchor(entry['key'], entry['label'], active) + '</li>' for entry in group['entries']) + '</ul></div>'
        out += '</details></li>'
    extra_roles = [('role-' + role, label) for role, label, _, _ in roles if 'role-' + role not in {key for key, _ in AUDIENCES}]
    out += '</ol><details class="nav-resources"' + (' open' if any(key == active for key, _ in TOOLS + extra_roles) else '') + '><summary>Outils, autres lecteurs et sources</summary><ul>' + ''.join('<li>' + anchor(key, label, active) + '</li>' for key, label in extra_roles + TOOLS) + '</ul></details></div>'
    return Navigation(out, context(sequence, current, dimension) if current else '')


def overview(topics):
    return '<section class="reading-outline"><h2>Du besoin à la réalisation</h2><p>Un fil de lecture commun pour présenter le projet et préparer sa construction. Revenez sur une partie à chaque nouvelle décision.</p><ol>' + ''.join('<li><a href="' + stage['href'] + '">' + H(stage['title']) + '</a><p>' + H(stage['purpose']) + '</p></li>' for stage in stages(topics)) + '</ol></section>'


def chapter(stage):
    business, builders = AUDIENCE_QUESTIONS[stage['id']]
    out = '<h1>' + H(stage['title']) + '</h1><p class="intro">' + H(stage['purpose']) + '</p><div class="reading-audience-hints"><p><strong>À expliquer au métier :</strong> ' + H(business) + '</p><p><strong>À préciser pour les équipes de réalisation :</strong> ' + H(builders) + '</p></div>'
    for group in stage['dimensions']:
        out += '<section class="reading-dimension"><h2>' + H(group['label']) + '</h2><ul>' + ''.join('<li><a href="' + entry['href'] + '">' + H(entry['label']) + '</a></li>' for entry in group['entries']) + '</ul></section>'
    return out
