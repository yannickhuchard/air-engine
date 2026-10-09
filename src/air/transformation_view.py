"""Global design-work graph at explicit pins, with declared status and closure gaps."""
from collections import Counter, defaultdict
from html import escape
from air.core import digest
from air.expr import artifact_digest
from air.foundation import exact, check_schema, TooLarge
from air.editorial import prose
from air import transformation_schema

ENGINE = 'air.transformation-view/1'
KINDS = ['air.TransformationProgramme', 'air.ArchitectureProject', 'air.ArchitectureTask', 'air.SourcingStrategy']
LABELS = {'air.TransformationProgramme': 'Programme', 'air.ArchitectureProject': 'Projet de conception',
          'air.ArchitectureTask': 'Tâche de conception', 'air.SourcingStrategy': 'Consultation fournisseur'}
COLORS = {'COMPLETED': '#15803d', 'DONE': '#15803d', 'CANCELLED': '#64748b', 'BLOCKED': '#b91c1c',
          'ACTIVE': '#1d4ed8', 'IN_PROGRESS': '#1d4ed8'}
STATUS_LABELS = {'COMPLETED': 'Terminé', 'DONE': 'Terminée', 'CANCELLED': 'Annulé', 'BLOCKED': 'Bloquée',
    'ACTIVE': 'En cours', 'IN_PROGRESS': 'En cours', 'PLANNED': 'Planifié', 'ON_HOLD': 'Suspendu', 'TODO': 'À faire',
    'DRAFT': 'Préparée', 'READY_TO_LAUNCH': 'Prête à lancer', 'LAUNCHED': 'Lancement déclaré', 'EVALUATING': 'En évaluation', 'SELECTED': 'Sélection déclarée'}
RESULT_LABELS = {'NOT_DOCUMENTED': 'Suivi à documenter', 'REVIEW_REQUIRED': 'Déclarations à revoir',
    'CONSISTENT_DECLARATIONS_AT_PINS': 'Déclarations cohérentes aux versions sélectionnées'}
RELATION_LABELS = {'CONTAINS_PROJECT': 'Contient le projet', 'CONTAINS_TASK': 'Contient la tâche', 'CHILD_OF_PROGRAMME': 'Rattaché au programme',
    'DEPENDS_ON_REFERENCE': 'Référence le projet', 'DEPENDS_ON_FINISH_TO_START': 'Attend la fin du projet',
    'TASK_DEPENDS_ON': 'Exige la tâche terminée', 'DELIVERS_DESIGN_WORK': 'Livre la consultation préparée'}
from air.core import record, TEXT
from air.projections import SNAPSHOT
QUERY = record({'baselines': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
    'types': {'type': 'array', 'items': {'enum': KINDS}, 'maxItems': 4, 'uniqueItems': True},
    'statuses': {'type': 'array', 'items': {'enum': ['PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED', 'TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'DRAFT', 'READY_TO_LAUNCH', 'LAUNCHED', 'EVALUATING', 'SELECTED']}, 'maxItems': 14, 'uniqueItems': True},
    'owner': TEXT, 'offset': {'type': 'integer', 'minimum': 0, 'maximum': 10000},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200}}, ['baselines'])


def query(store, principal, policy, request):
    """Authorize every pin before applying filters; no discovery of other clients."""
    from air.access import ScopedStore
    from air.projections import snapshot
    from air.expr import bounded, ExprError
    check_schema(request, QUERY)
    guarded = ScopedStore(store, principal, policy)
    v = project([snapshot(guarded, pin) for pin in request['baselines']])
    nodes = [n for n in v['nodes'] if (not request.get('types') or n['type'] in request['types'])
        and (not request.get('statuses') or n['status'] in request['statuses'])
        and (not request.get('owner') or n['owner'] == request['owner'])]
    offset = request.get('offset', 0); page = nodes[offset:offset + request.get('limit', 50)]
    visible = {n['id'] for n in page}
    edges = [e for e in v['edges'] if e['source'] in visible and e['target'] in visible]
    result = {k: x for k, x in v.items() if k not in ('nodes', 'edges')}
    result.update(nodes=page, edges=edges, total_matching=len(nodes), offset=offset,
        next_offset=offset + len(page) if offset + len(page) < len(nodes) else None,
        omitted_edges=len(v['edges']) - len(edges), totals_scope='ALL_AUTHORIZED_PINS_BEFORE_FILTERS',
        projection_digest_scope='COMPLETE_GRAPH_BEFORE_FILTERS', request_digest=artifact_digest(request))
    result['report_digest'] = artifact_digest(result)
    try: bounded(result)
    except ExprError as exc: raise TooLarge('Transformation query exceeds its response budget; reduce the limit') from exc
    return result


def project(exports):
    by_ref = {}; holders = {}; pins = []
    for e in sorted(exports, key=lambda e: (e['baseline']['meta']['id'], e['baseline']['meta']['revision'], e['digest'])):
        pin = {**exact(e['baseline']), 'digest': e['digest']};pins.append(pin)
        for o in e['objects']:
            if o['meta']['type'] not in KINDS: continue
            key = (o['meta']['id'], o['meta']['revision'])
            by_ref[key] = o; holders.setdefault(key, []).append(pin)
            if len(by_ref) > 10000: raise TooLarge('Transformation supports at most 10000 design-work objects at selected pins')
    from air.deliverables import mid
    nodes = []
    for key, o in sorted(by_ref.items()):
        b = o['body']; node = {'id': mid(o['meta']['id'] + ':' + str(o['meta']['revision'])),
            'reference': {**exact(o), 'digest': digest(o)}, 'name': o['meta']['name'], 'type': o['meta']['type'],
            'namespace': o['meta']['namespace'], 'status': b['status'], 'purpose': b['purpose'],
            'owner': b['owner'], 'baselines': sorted(holders[key], key=lambda p: (p['id'], p['revision'])),
            'declared': b, 'completion_attested': False}
        nodes.append(node)
    node_by_ref = {(n['reference']['id'], n['reference']['revision']): n for n in nodes}
    edges, gaps = [], []
    for _, o in sorted(by_ref.items()):
        kind, b = o['meta']['type'], o['body']; origin = node_by_ref[(o['meta']['id'], o['meta']['revision'])]
        refs = []
        if kind == 'air.TransformationProgramme':
            refs += [(r, 'CONTAINS_PROJECT', 'projects/' + str(i)) for i, r in enumerate(b['projects'])]
            if b.get('parent'): refs += [(b['parent'], 'CHILD_OF_PROGRAMME', 'parent')]
        elif kind == 'air.ArchitectureProject':
            refs += [(r, 'CONTAINS_TASK', 'tasks/' + str(i)) for i, r in enumerate(b['tasks'])]
            refs += [(d['project'], 'DEPENDS_ON_' + d['kind'], 'depends_on/' + str(i) + '/project') for i, d in enumerate(b['depends_on'])]
        elif kind == 'air.ArchitectureTask':
            refs += [(r, 'TASK_DEPENDS_ON', 'depends_on/' + str(i)) for i, r in enumerate(b['depends_on'])]
            refs += [(r, 'DELIVERS_DESIGN_WORK', 'deliverables/' + str(i)) for i, r in enumerate(b['deliverables']) if (r['id'], r['revision']) in node_by_ref]
        for r, relation, field in refs:
            target = node_by_ref.get((r['id'], r['revision']))
            if not target:
                gaps.append({'code': 'WORK_REFERENCE_OUTSIDE_PINS', 'source': origin['reference'], 'target': r, 'field': field});continue
            edges.append({'source': origin['id'], 'target': target['id'], 'relation': relation,
                'witness': origin['reference'], 'selector': '/body/' + field})
    # Structural references have already been authorized in snapshots. These
    # projection checks prevent a terminal declaration hiding unfinished work.
    all_objects = [o for e in exports for o in [e['baseline'], *e['objects']]]
    all_by_ref = {(o['meta']['id'], o['meta']['revision']): o for o in all_objects}
    unique = [o for _, o in sorted(all_by_ref.items())]
    for code, location, detail in transformation_schema.graph_issues(unique, all_by_ref):
        gaps.append({'code': code, 'id': location, 'detail': detail})
    for o in unique:
        for code, detail in transformation_schema.local_issues(o):
            gaps.append({'code': code, 'id': o['meta']['id'], 'detail': detail})
    revisions = {}
    for n in nodes: revisions.setdefault(n['reference']['id'], set()).add(n['reference']['revision'])
    for identity, values in sorted(revisions.items()):
        if len(values) > 1: gaps.append({'code': 'WORK_REVISION_DIVERGENCE', 'id': identity, 'revisions': sorted(values)})
    counts = Counter(n['status'] for n in nodes if n['type'] == 'air.ArchitectureTask')
    states = {n['status'] for n in nodes if n['type'] in ('air.ArchitectureProject', 'air.TransformationProgramme')}
    overall = 'NOT_DOCUMENTED' if not states else 'REVIEW_REQUIRED' if gaps else 'COMPLETED' if states == {'COMPLETED'} else 'CANCELLED' if states == {'CANCELLED'} else 'CLOSED_MIXED' if states <= set(transformation_schema.TERMINAL) else 'ACTIVE' if 'ACTIVE' in states else 'ON_HOLD' if 'ON_HOLD' in states else 'PLANNED'
    result = {'engine': ENGINE, 'baselines': pins, 'nodes': nodes, 'edges': sorted(edges, key=lambda e: (e['source'], e['relation'], e['target'], e['selector'])),
        'gaps': gaps, 'totals': {'programmes': sum(n['type'] == KINDS[0] for n in nodes), 'projects': sum(n['type'] == KINDS[1] for n in nodes),
            'tasks': sum(counts.values()), 'active_tasks': sum(counts[s] for s in ('TODO', 'IN_PROGRESS', 'BLOCKED')),
            'done_tasks': counts['DONE'], 'cancelled_tasks': counts['CANCELLED']},
        'result': 'NOT_DOCUMENTED' if not nodes else 'REVIEW_REQUIRED' if gaps else 'CONSISTENT_DECLARATIONS_AT_PINS',
        'declared_work_status': overall,
        'status_scope': 'DECLARED_ARCHITECTURE_DESIGN_WORK_NOT_BUSINESS_IMPLEMENTATION',
        'completion_attested': False, 'registry_written': False, 'single_instance': True, 'federation_implemented': False,
        'refresh_policy': 'REGENERATE_FROM_EXACT_BASELINES'}
    return {**result, 'projection_digest': artifact_digest(result)}


def preview(view, href='transformation.html'):
    h = lambda x: escape(prose(str(x)), quote=True)
    t = view['totals']
    return '<section class="transformation-preview"><h2>Programmes, projets et tâches</h2><p>' + str(t['programmes']) + ' programme(s), ' + str(t['projects']) + ' projet(s) de conception, ' + str(t['active_tasks']) + ' tâche(s) active(s).</p><p>' + ('Suivi à documenter.' if view['result'] == 'NOT_DOCUMENTED' else 'Statuts déclarés aux baselines sélectionnées ; la clôture de conception reste distincte de la réalisation métier.') + '</p><a href="' + h(href) + '">Ouvrir la vue de transformation et ses dépendances</a></section>'


def html(view, object_links=None, standalone=False):
    h = lambda x: escape(prose(str(x)), quote=True)
    object_links = object_links or {}
    nodes = sorted(view['nodes'], key=lambda n: (KINDS.index(n['type']), n['reference']['id'], n['reference']['revision']))
    by_id = {n['id']: n for n in nodes}; edges_by_source = defaultdict(list)
    for e in view['edges']: edges_by_source[e['source']].append(e)
    out = '<section class="transformation-view"><h1>Piloter la transformation</h1><p class="intro">Programmes, projets et travaux de conception aux versions exactes sélectionnées.</p>'
    out += '<p><strong>' + str(view['totals']['projects']) + ' projet(s), ' + str(view['totals']['active_tasks']) + ' tâche(s) active(s)</strong>. Statut global déclaré : ' + h(STATUS_LABELS.get(view['declared_work_status'], 'Terminé avec annulations' if view['declared_work_status'] == 'CLOSED_MIXED' else RESULT_LABELS.get(view['declared_work_status'], view['declared_work_status']))) + '. ' + h(RESULT_LABELS[view['result']]) + '.</p>'
    out += '<p>Les statuts sont déclarés et sourcés. Clôture de conception, préparation à construire et réalisation métier restent distinctes. Une clôture n’est pas déduite du score 12/12.</p>'
    if not nodes: out += '<p>Aucun programme, projet ou suivi de tâche déclaré. Créer les objets typés pour construire cette vue.</p>'
    visible = nodes[:90]; positions = {}
    columns = {KINDS[0]: 25, KINDS[1]: 340, KINDS[2]: 655, KINDS[3]: 970}
    counters = Counter()
    for n in visible:
        positions[n['id']] = (columns[n['type']], 35 + counters[n['type']] * 74);counters[n['type']] += 1
    height = max([110, *[y + 80 for x, y in positions.values()]])
    out += '<div class="transformation-map"><svg viewBox="0 0 1280 ' + str(height) + '" role="img" aria-label="Graphe des programmes, projets et tâches ; liste descriptive complète ci-dessous"><defs><marker id="work-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10Z" fill="#64748b"/></marker></defs>'
    for e in view['edges']:
        if e['source'] not in positions or e['target'] not in positions: continue
        x, y = positions[e['source']]; a, b = positions[e['target']]
        if a > x:
            route = 'M' + str(x + 270) + ' ' + str(y + 28) + ' C' + str(x + 292) + ' ' + str(y + 28) + ' ' + str(a - 22) + ' ' + str(b + 28) + ' ' + str(a) + ' ' + str(b + 28)
        else:
            route = 'M' + str(x) + ' ' + str(y + 28) + ' C' + str(x - 20) + ' ' + str(y + 28) + ' ' + str(a - 20) + ' ' + str(b + 28) + ' ' + str(a) + ' ' + str(b + 28)
        out += '<path d="' + route + '" stroke="#64748b" fill="none" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#work-arrow)"><title>' + h(RELATION_LABELS[e['relation']]) + '</title></path>'
    for n in visible:
        x, y = positions[n['id']]
        out += '<a href="#' + n['id'] + '"><title>' + h(n['name']) + '</title><rect x="' + str(x) + '" y="' + str(y) + '" width="270" height="55" rx="8" fill="#fff" stroke="' + COLORS.get(n['status'], '#92400e') + '"/><text x="' + str(x + 10) + '" y="' + str(y + 21) + '" fill="#0f172a" font-size="15">' + h(n['name'][:25] + ('…' if len(n['name']) > 25 else '')) + '</text><text x="' + str(x + 10) + '" y="' + str(y + 42) + '" fill="#475569" font-size="13">' + h(STATUS_LABELS.get(n['status'], n['status'])) + '</text></a>'
    out += '</svg></div><p>Flèche discontinue : programme vers projet ou projet vers tâche ; une dépendance pointe vers son prérequis. Survoler le lien pour lire la relation. Les libellés distinguent terminé, annulé et actif.</p>'
    if len(nodes) > len(visible): out += '<p>Le graphe montre 90 objets sur ' + str(len(nodes)) + '. La liste et le JSON conservent la portée complète.</p>'
    out += '<h2>Liste complète et sources</h2>'
    for n in nodes:
        r = n['reference'];link = object_links.get((r['id'], r['revision']))
        out += '<details id="' + n['id'] + '"><summary>' + h(n['name']) + ' : ' + h(STATUS_LABELS.get(n['status'], n['status'])) + '</summary><p>' + h(n['purpose']) + '</p><p>' + h(LABELS[n['type']]) + '. Responsable déclaré : ' + h(n['owner']) + '.</p><p><code>' + h(r['id']) + '</code> r' + str(r['revision']) + ' ; <code>' + h(r['digest']) + '</code>.</p>'
        if link: out += '<p><a href="' + h(link) + '">Lire la déclaration complète dans le dossier</a></p>'
        outgoing = edges_by_source[n['id']]
        if outgoing:
            out += '<ul>' + ''.join('<li>' + h(RELATION_LABELS[e['relation']]) + ' : <a href="#' + e['target'] + '">' + h(by_id[e['target']]['name']) + '</a> ; témoin <code>' + h(e['selector']) + '</code>.</li>' for e in outgoing) + '</ul>'
        for pin in n['baselines']: out += '<p>Baseline <code>' + h(pin['id']) + '</code> r' + str(pin['revision']) + ' ; <code>' + h(pin['digest']) + '</code>.</p>'
        out += '</details>'
    out += '<h2>Points à examiner</h2><ul>' + ''.join('<li>' + h(g['code']) + ' : ' + h(g.get('detail', g.get('id', g.get('field', '')))) + '</li>' for g in view['gaps']) + '</ul>'
    out += '<p><a href="transformation.json">Télécharger le graphe, les relations et leurs témoins exacts</a></p><p>Régénérer après une évolution. Les installations autonomes de plusieurs clients ne sont pas fédérées automatiquement.</p></section>'
    if standalone:
        return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>Projet d’architecture : transformation</title><style>body{font:16px system-ui;background:#f5f7fb;color:#14213d;max-width:1200px;margin:auto;padding:2rem}a{color:#154db6}summary{padding:1rem 0;cursor:pointer;min-height:24px}details{border-bottom:1px solid #cbd5e1}code{overflow-wrap:anywhere}.transformation-map{overflow:auto;background:white;border-radius:1rem;border:1px solid #cbd5e1}.transformation-map svg{display:block;width:100%;min-width:1050px}p{max-width:85ch;line-height:1.6}@media(max-width:600px){body{padding:1rem}}@media print{.transformation-map{overflow:visible}}</style></head><body>' + out + '</body></html>'
    return out
