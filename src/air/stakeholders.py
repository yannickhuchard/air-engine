"""A source-bound stakeholder map. No inferred hire, consent or authorization."""
from collections import Counter
from html import escape
import hashlib
from air.access import ScopedStore
from air.core import record, digest
from air.editorial import prose
from air.expr import artifact_digest
from air.foundation import check_schema, exact, key, check_budget, TooLarge
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.stakeholders-map/1'
REQUEST = record({'baseline': SNAPSHOT, 'content': {'enum': ['JSON', 'HTML']}}, ['baseline'])
STATES = [('INVOLVED', 'Impliqués', '#16735d'), ('TO_INVOLVE', 'À mobiliser', '#255ca8'),
    ('MISSING', 'Manquants', '#a13c26'), ('UNASSESSED', 'À préciser', '#655578')]
STATE_LABELS = dict((s, label) for s, label, _ in STATES)
ACTION_LABELS = {'NONE': 'Aucune action de staffing', 'ASSIGN': 'Affectation interne', 'RECRUIT': 'Recrutement à prévoir',
    'PARTNER': 'Partenaire ou prestation', 'ASSESS': 'Mode de mobilisation à décider'}
KINDS = {'air.StakeholderParticipation', 'air.Stakeholder', 'air.Role', 'air.OrganizationUnit', 'air.Concern', 'air.RaciAssignment'}


def pin(o): return {**exact(o), 'digest': digest(o)}
def anchor(r): return 'stakeholder-' + hashlib.sha256((r['id'] + ':' + str(r['revision'])).encode()).hexdigest()[:16]
def sources(objects): return [o for o in objects if o['meta']['type'] in KINDS or o['meta']['type'] == 'air.Actor' and o['body']['kind'] in ('HUMAN', 'ORGANIZATION')]


def project(exported):
    objects = exported['objects']
    if len(objects) > 20000: raise TooLarge('Stakeholder map supports at most 20000 source objects')
    by = {key(o['meta']): o for o in objects}; used = set(); covered_roles = set(); covered_holders = set(); entries = []
    identity_names = {o['body']['identity_or_group']: o['meta']['name'] for o in objects if o['meta']['type'] == 'air.Stakeholder'}
    identity_names.update({o['meta']['id']: o['meta']['name'] for o in objects if o['meta']['type'] == 'air.Actor'})
    def resolved(r):
        o = by[key(r)]; used.add(key(r))
        return {**pin(o), 'name': o['meta']['name'], 'type': o['meta']['type']}
    def raci(role):
        return [{'reference': resolved(exact(o)), 'activity': o['body']['activity'], 'phase': o['body']['phase'],
            'responsibility': o['body']['responsibility']} for o in objects
            if o['meta']['type'] == 'air.RaciAssignment' and key(o['body']['role']) == key(role)]
    for o in sorted(objects, key=lambda o: key(o['meta'])):
        if o['meta']['type'] != 'air.StakeholderParticipation': continue
        b = o['body']; role = by[key(b['role'])]; covered_roles.add(key(b['role']))
        holders = [resolved(b['stakeholder'])] if b.get('stakeholder') else []
        covered_holders.update(key(h) for h in holders)
        entries.append({'id': anchor(exact(o)), 'reference': resolved(exact(o)), 'state': b['state'],
            'role': resolved(b['role']), 'holders': holders, 'scope': resolved(b['scope']), 'reason': b['reason'],
            'responsibilities': b['responsibilities'], 'role_responsibilities': role['body']['responsibilities'],
            'architecture_links': [resolved(r) for r in b['architecture_links']], 'raci': raci(b['role']),
            'staffing_action': b['staffing_action'], 'engagement_plan': b['engagement_plan'],
            'coordination_owner': b['coordination_owner'], 'coordination_owner_label': identity_names.get(b['coordination_owner'], b['coordination_owner'].rsplit(':', 1)[-1]),
            'needed_by': b.get('needed_by'), 'gaps': []})
    # Legacy objects are visible without fabricating project participation or vacancies.
    for o in sorted(objects, key=lambda o: (o['meta']['type'] != 'air.Role', key(o['meta']))):
        kind, b = o['meta']['type'], o['body']; r = exact(o)
        if kind == 'air.Role' and key(r) not in covered_roles:
            holders = [resolved(exact(a)) for a in objects if a['meta']['type'] == 'air.Actor' and a['body']['kind'] in ('HUMAN', 'ORGANIZATION') and r in a['body']['roles']]
            covered_holders.update(key(h) for h in holders)
            entries.append({'id': anchor(r), 'reference': resolved(r), 'state': 'UNASSESSED', 'role': resolved(r), 'holders': holders,
                'reason': None, 'responsibilities': [], 'role_responsibilities': b['responsibilities'], 'architecture_links': [], 'raci': raci(r),
                'staffing_action': 'ASSESS', 'engagement_plan': None, 'coordination_owner': None, 'needed_by': None,
                'gaps': ['PARTICIPATION_NOT_DOCUMENTED', 'PROJECT_REASON_NOT_DOCUMENTED'] + ([] if holders else ['ASSIGNMENT_NOT_DOCUMENTED'])})
        elif (kind == 'air.Stakeholder' or kind == 'air.Actor' and b['kind'] in ('HUMAN', 'ORGANIZATION')) and key(r) not in covered_holders:
            covered_holders.add(key(r))
            concerns = [resolved(c) for c in b.get('concerns', [])]
            entries.append({'id': anchor(r), 'reference': resolved(r), 'state': 'UNASSESSED', 'role': None, 'holders': [resolved(r)],
                'reason': None, 'declared_participation_role': b.get('participation_role'), 'responsibilities': [], 'role_responsibilities': [],
                'architecture_links': concerns, 'raci': [], 'staffing_action': 'ASSESS', 'engagement_plan': None,
                'coordination_owner': None, 'needed_by': None, 'gaps': ['PARTICIPATION_NOT_DOCUMENTED', 'PROJECT_RESPONSIBILITIES_NOT_DOCUMENTED']})
    entries.sort(key=lambda e: ([s for s, _, _ in STATES].index(e['state']), e['reference']['name'], e['reference']['id'], e['reference']['revision']))
    counts = Counter(e['state'] for e in entries)
    result = {'engine': ENGINE, 'baseline': {**exact(exported['baseline']), 'digest': exported['digest']} if 'baseline' in exported else None,
        'entries': entries, 'counts': {s: counts[s] for s, _, _ in STATES}, 'total': len(entries),
        'sources': [pin(by[k]) for k in sorted(used)],
        'checks': [{'code': 'STAKEHOLDER_PARTICIPATION', 'status': 'NOT_DOCUMENTED' if not entries else 'PARTIAL' if counts['UNASSESSED'] else 'DOCUMENTED',
            'label': 'Justification et responsabilités des parties prenantes documentées', 'approval_inferred': False}],
        'vacancies_are_declared': True, 'hiring_executed': False, 'participation_confirmed_externally': False,
        'authorization_granted': False, 'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINE'}
    check_budget(result)
    return {**result, 'projection_digest': artifact_digest(result)}


def query(store, principal, policy, request):
    check_schema(request, REQUEST)
    result = project(snapshot(ScopedStore(store, principal, policy), request['baseline']))
    if request.get('content') == 'HTML': result = {**result, 'html': render(result)}
    check_budget(result)
    return result


def render(model, object_links=None):
    h = lambda v: escape(prose(str(v)), quote=True)
    links = object_links or {}
    def link(r):
        if not r: return 'Rôle à préciser'
        url = links.get(key(r)); label = h(r.get('name', r['id']))
        return '<a href="' + h(url) + '">' + label + '</a>' if url else label
    out = '<section class="stakeholders-map" data-stakeholders-map><h1>Carte des parties prenantes</h1><p class="intro">Identifier les bonnes contributions, comprendre leurs responsabilités et préparer leur mobilisation.</p>'
    if not model['entries']:
        return out + '<p>Aucune partie prenante ni rôle documenté. Identifier les contributions nécessaires puis déclarer leur participation, leurs responsabilités et les rôles encore à pourvoir.</p></section>'
    out += '<div class="stakeholder-tools" data-stakeholder-tools hidden><div class="stakeholder-filters" role="group" aria-label="Filtrer par état de participation"><button type="button" data-stakeholder-filter="" aria-pressed="true">Toutes <span>' + str(model['total']) + '</span></button>'
    out += ''.join('<button type="button" data-stakeholder-filter="' + s + '" data-state="' + s + '" aria-pressed="false"><span class="stakeholder-dot" aria-hidden="true"></span>' + h(label) + ' <span>' + str(model['counts'][s]) + '</span></button>' for s, label, _ in STATES)
    out += '</div><label class="stakeholder-search">Rechercher une contribution<input type="search" data-stakeholder-search placeholder="Rôle, personne, responsabilité…" autocomplete="off"></label></div>'
    out += '<p class="stakeholder-results" data-stakeholder-count role="status" aria-live="polite">' + str(model['total']) + ' contribution(s). Une personne peut tenir plusieurs rôles.</p>'
    out += '<div class="stakeholder-workspace"><div class="stakeholder-canvas"><div class="stakeholder-project"><span>Projet d’architecture</span><small>Contributions au projet, sans lien hiérarchique</small></div><svg class="stakeholder-branches" viewBox="0 0 1000 24" preserveAspectRatio="none" aria-hidden="true"><path d="M500 0 V12 M250 24 V12 H750 V24"/></svg><div class="stakeholder-groups">'
    for state, label, _ in STATES:
        members = [e for e in model['entries'] if e['state'] == state]
        if not members: continue
        out += '<section class="stakeholder-group" data-stakeholder-group="' + state + '" data-state="' + state + '"><h2><span class="stakeholder-dot" aria-hidden="true"></span>' + h(label) + '<span class="stakeholder-group-count">' + str(len(members)) + '</span></h2><div class="stakeholder-nodes">'
        for e in members:
            title = e['role']['name'] if e['role'] else e['reference']['name']
            holder = ', '.join(p['name'] for p in e['holders']) or ('Rôle vacant, personne à identifier' if state == 'MISSING' else 'Affectation à documenter')
            search = ' '.join([title, holder, e['reason'] or '', e['engagement_plan'] or '', *e['responsibilities'], *e['role_responsibilities']])
            out += '<a href="#' + e['id'] + '" class="stakeholder-node" data-stakeholder-target="' + e['id'] + '" data-search="' + h(search) + '" data-state="' + state + '"><strong>' + h(title) + '</strong><span class="stakeholder-holder">' + h(holder) + '</span><span class="stakeholder-node-action">Voir la contribution<span aria-hidden="true">↗</span></span></a>'
        out += '</div></section>'
    out += '</div><div class="stakeholder-empty" data-stakeholder-empty hidden><h2>Aucune contribution trouvée</h2><p>Essayer un autre terme ou afficher tous les états.</p><button type="button" data-stakeholder-reset>Effacer les filtres</button></div></div><div class="stakeholder-inspector"><button type="button" class="stakeholder-back" data-stakeholder-back hidden>Revenir à la carte</button><div class="stakeholder-details">'
    for e in model['entries']:
        title = e['role']['name'] if e['role'] else e['reference']['name']
        out += '<details open id="' + e['id'] + '" data-stakeholder-state="' + e['state'] + '" data-state="' + e['state'] + '"><summary><span class="stakeholder-state-label"><span class="stakeholder-dot" aria-hidden="true"></span>' + h(STATE_LABELS[e['state']]) + '</span><strong>' + h(title) + '</strong></summary><div><p class="stakeholder-identity">' + (', '.join(link(p) for p in e['holders']) or ('Rôle vacant explicitement déclaré, sans personne affectée.' if e['state'] == 'MISSING' else 'Affectation non documentée ; besoin à examiner.')) + '</p>'
        out += '<h3>Pourquoi cette contribution ?</h3><p>' + h(e['reason'] or 'Justification de la participation au projet à documenter.') + '</p><h3>Responsabilités dans ce projet</h3><ul>'
        out += ''.join('<li>' + h(r) + '</li>' for r in e['responsibilities']) or '<li>Responsabilités de projet à préciser.</li>'
        out += '</ul>'
        if e['role_responsibilities']: out += '<p>Responsabilités générales du rôle : ' + h('; '.join(e['role_responsibilities'])) + '.</p>'
        if e['raci']: out += '<p>RACI déclaré : ' + '; '.join(link(r['reference']) + ' (' + h(r['phase'] + ', ' + r['responsibility'] + ', ' + r['activity']) + ')' for r in e['raci']) + '.</p>'
        out += '<div class="stakeholder-next"><h3>Prochaine action de mobilisation</h3><p><strong>' + h(ACTION_LABELS[e['staffing_action']]) + '</strong></p><p>' + h(e['engagement_plan'] or 'Plan à documenter.') + '</p><dl><dt>Coordination</dt><dd>' + h(e.get('coordination_owner_label') or 'À désigner') + '</dd><dt>Participation attendue</dt><dd>' + h(e['needed_by'] or 'Date à préciser') + '</dd></dl></div>'
        out += '<h3>Éléments d’architecture concernés</h3><p>' + (', '.join(link(r) for r in e['architecture_links']) or 'Liens au projet à documenter') + '.</p><p class="stakeholder-source">Source versionnée : ' + link(e['reference']) + '.</p></div></details>'
    out += '</div></div></div><p class="stakeholder-note">Les états décrivent cette version du dossier. « À préciser » ne signifie pas « poste vacant ». La carte ne prouve ni engagement effectif ni embauche et n’accorde aucun droit.</p></section>'
    return out
