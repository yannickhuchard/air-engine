"""Customer journey map and service blueprint, with explicit evidence limits."""
from html import escape
from air.editorial import prose
from air.deliverables import mid


def h(value): return escape(prose(str(value)), quote=True)
def key(pin): return mid(pin['id'] + ':' + str(pin['revision']))
def links(items):
    unique = {(x['reference']['id'], x['reference']['revision']): x for x in items}
    return '<ul>' + ''.join('<li><a href="objects.html#' + key(x['reference']) + '">' + h(x['name']) + '</a></li>' for x in unique.values()) + '</ul>' if unique else '<span class="map-unknown">À documenter</span>'
def words(items): return '<ul>' + ''.join('<li>' + h(x) + '</li>' for x in items) + '</ul>' if items else '<span class="map-unknown">À documenter</span>'


def emotion(step):
    value = step.get('emotion', {'status': 'UNKNOWN'})
    if value['status'] == 'UNKNOWN': return '<span class="map-unknown">Émotion inconnue</span><small>Aucun score attribué</small>'
    label = 'Hypothèse à discuter' if value['status'] == 'HYPOTHESIS' else 'Observation déclarée, voir preuves'
    out = '<strong>' + h(value.get('label', '')) + '</strong><small>' + label + '</small>'
    if 'score' in value:
        score = value['score']
        out += '<span class="mood-scale" aria-label="Score émotionnel déclaré : ' + str(score) + ' sur 5">' + ''.join('<i class="' + ('filled' if n <= score else '') + '"></i>' for n in range(1, 6)) + '</span><small>' + str(score) + '/5, de très négatif à très positif</small>'
    out += '<p>' + h(value.get('rationale', '')) + '</p>'
    if value.get('evidence'): out += links(value['evidence'])
    return out


ROWS = [
    ('action', 'Action du persona', 'experience'), ('participants', 'Acteurs et intervenants', 'experience'),
    ('touchpoint', 'Touchpoints et canaux', 'experience'), ('usage_points', 'Digital, physique et géographie', 'experience'),
    ('thoughts', 'Pensées et attentes', 'experience'), ('emotion', 'Émotions et mood', 'experience'),
    ('pain_points', 'Irritants', 'experience'), ('opportunities', 'Opportunités', 'experience'),
    ('frontstage', 'Service visible (frontstage)', 'interaction'), ('backstage', 'Actions internes (backstage)', 'visibility'),
    ('support_processes', 'Processus de support', 'internal'), ('systems', 'Systèmes et blocs reliés', 'delivery'),
    ('outcome', 'Résultat et durée', 'delivery'), ('source', 'Traçabilité', 'delivery')]


def cell(j, step, field):
    if field == 'action': return h(step.get('action', step['name']))
    if field == 'participants': return links([j['persona'], *step['participants']])
    if field == 'touchpoint':
        out = h(step['touchpoint']) + '<small>' + h(step['channel']) + '</small>'
        return out + (links([step['touchpoint_object']]) if 'touchpoint_object' in step else '')
    if field == 'usage_points':
        labels = {'DIGITAL': 'Digital', 'PHYSICAL': 'Physique', 'GEOGRAPHIC': 'Géographique'}
        return ''.join('<div class="map-place"><strong>' + labels.get(p.get('kind'), 'Contexte à préciser') + '</strong>' + links([p]) + '<small>' + h(' · '.join(p.get(k, '') for k in ('city', 'country', 'location_description') if p.get(k))) + '</small></div>' for p in step['usage_points']) or '<span class="map-unknown">À documenter</span>'
    if field == 'emotion': return emotion(step)
    if field == 'systems':
        return ('<small>Systèmes explicitement déclarés</small>' + links(step['systems']) if step.get('systems') else '<small>Affectation système à préciser</small>') + ('<details><summary>Autres blocs associés au touchpoint</summary>' + links(step['linked_systems']) + '<p>Association documentaire, sans appel technique inféré.</p></details>' if step.get('linked_systems') else '')
    if field == 'outcome': return h(step.get('outcome', 'Résultat à préciser')) + '<small>Durée : ' + h(step.get('duration', 'non documentée')) + '</small>'
    if field == 'source': return links([j]) + '<code>' + h(step['selector']) + '</code>'
    return words(step.get(field, []))


def curve(j):
    """Never bridge an unknown score, or combine observed and hypothetical points."""
    steps = j['steps']
    if not any(s.get('emotion', {}).get('status') != 'UNKNOWN' and 'score' in s.get('emotion', {}) for s in steps):
        return '<p class="mood-empty">Courbe émotionnelle à documenter : aucun score déclaré pour ces ' + str(len(steps)) + ' étapes. Aucun score neutre n’a été substitué.</p>'
    width = max(620, len(steps) * 240); pad = 120; height = 182
    positions = [pad + i * (width - 2 * pad) / max(1, len(steps) - 1) for i in range(len(steps))]
    out = '<div class="mood-chart table-wrap" tabindex="0" role="region" aria-label="Courbe émotionnelle, faire défiler horizontalement"><svg role="img" aria-label="Émotions déclarées par étape ; les inconnues ne sont pas interpolées" viewBox="0 0 ' + str(width) + ' ' + str(height) + '" style="width:' + str(width) + 'px"><title>Émotions : 1 très négatif, 5 très positif. Trait discontinu pour une hypothèse.</title>'
    for score in (1, 3, 5):
        y = 132 - (score - 1) * 25
        out += f'<path d="M 20 {y} H {width-20}" class="mood-guide"/><text x="25" y="{y-4}">{score}/5</text>'
    previous = None
    for i, (step, x) in enumerate(zip(steps, positions)):
        e = step.get('emotion', {}); score = e.get('score')
        if e.get('status') == 'UNKNOWN' or score is None:
            out += f'<text x="{x}" y="87" text-anchor="middle">Non renseigné</text>'; previous = None
        else:
            y = 132 - (score - 1) * 25; status = e['status']; style = 'mood-hypothesis' if status == 'HYPOTHESIS' else 'mood-observed'
            if previous and previous[2] == status:
                out += f'<path d="M {previous[0]} {previous[1]} L {x} {y}" class="{style}"/>'
            out += f'<circle cx="{x}" cy="{y}" r="6" class="{style}"><title>' + h(step['name'] + ' : ' + str(score) + '/5, ' + status) + '</title></circle>'
            previous = (x, y, status)
        out += f'<text x="{x}" y="165" text-anchor="middle">Étape {i+1}</text>'
    return out + '</svg></div>'


def render(j, focused=False):
    from air import journey_visual
    unique = key(j['reference']); state = {'AS_IS': 'État actuel déclaré', 'TO_BE': 'Expérience cible proposée'}.get(j.get('view_state'), 'État actuel ou cible à préciser')
    body = '<section class="journey-map" id="map-' + unique + '"><h2>Customer Journey Map et service blueprint</h2><p>' + state + '. ' + h(j.get('scenario', 'Scénario à préciser')) + '</p><p>Persona principal :</p>' + links([j['persona']]) + '<p>Les pensées et actions de service sont déclaratives. Les émotions observées exigent des sources ; une case inconnue reste inconnue.</p>'
    if not focused: body += '<p><a href="journey-' + unique + '.html">Ouvrir la carte complète et ses sources</a></p>'
    body += journey_visual.figure(j, compact=not focused)
    body += curve(j) + '<div class="journey-mobile"><h3>Lire chaque étape</h3>'
    for i, s in enumerate(j['steps']):
        body += '<details' + (' open' if i == 0 else '') + '><summary>' + str(i + 1) + '. ' + h(s['name']) + '</summary><dl>' + ''.join('<dt>' + h(label) + '</dt><dd>' + cell(j, s, field) + '</dd>' for field, label, _ in ROWS) + '</dl></details>'
    body += '</div><p class="map-reading-hint">Comparer les étapes de gauche à droite et les dimensions de haut en bas. Faire défiler la carte horizontalement ; les libellés restent visibles. Sur mobile, lire d’abord les fiches de chaque étape.</p><div class="table-wrap journey-matrix" tabindex="0" role="region" aria-label="Carte comparative des étapes"><table><caption>' + h(j['name']) + '</caption><thead><tr><th scope="col">Dimension</th>'
    for i, s in enumerate(j['steps']):
        body += '<th scope="col"><span class="map-phase">' + h(s.get('phase', 'Phase à préciser')) + '</span><span class="map-step">' + str(i + 1) + '. ' + h(s['name']) + '</span></th>'
    body += '</tr></thead><tbody>'
    for field, label, group in ROWS:
        body += '<tr class="map-row-' + group + '"><th scope="row">' + h(label) + '</th>' + ''.join('<td>' + cell(j, s, field) + '</td>' for s in j['steps']) + '</tr>'
    body += '</tbody></table></div><p class="map-legend">Ligne d’interaction avant le service visible. Ligne de visibilité avant les actions internes. Ligne d’interaction interne avant les processus de support. Ces séparations décrivent le modèle proposé, pas une observation du service.</p>'
    missing = sum(bool(s.get('experience_missing')) for s in j['steps'])
    return body + '<p>' + str(missing) + ' étape(s) comportent des dimensions d’expérience à documenter. Ce constat est distinct de la checklist des liens et des douze critères de préparation à construire.</p></section>'
