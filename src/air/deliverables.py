"""The implementation team's deliverables, derived from frozen baselines: one document per deliverable, Mermaid diagrams.

Every document cites the exact objects it was compiled from and says what is declared and what is verified. Nothing
is invented: a deliverable whose objects are absent says so, which is itself a gap to close.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import re
from air.access import ScopedStore
from air.atelier import collate, no_secret, product, render_json, render_text, toolchain
from air.core import TEXT, URI, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema
from air.projections import SNAPSHOT, snapshot
from air.temporal_site import COMPARISON
from air.branding import SELECTION as BRANDING_SELECTION
from air.editorial import prose

ENGINE = 'air.deliverables/0.32'
REQUEST = record({'title': {**TEXT, 'maxLength': 200},
                  'baselines': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True},
                  'implementation_root': URI, 'operations_root': URI, 'content': {'enum': ['FULL', 'DIGESTS']},
                  'directory': {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{0,62}$'},
                  'only': {'type': 'array', 'items': {'type': 'string', 'pattern': '^[0-9]{2}-[a-z0-9-]{1,62}$'}, 'minItems': 1, 'maxItems': 40, 'uniqueItems': True},
                  'title_en': {**TEXT, 'maxLength': 200}, 'client': {**TEXT, 'maxLength': 120}, 'provider': {**TEXT, 'maxLength': 120},
                  'projects': {'type': 'object', 'maxProperties': 32},
                  'website': {'type': 'boolean'},
                  'max_total_bytes': {'type': 'integer', 'minimum': 16777216, 'maximum': 67108864},
                  'branding': BRANDING_SELECTION,
                  'comparisons': {'type': 'array', 'items': COMPARISON, 'maxItems': 16}},
                 ['title', 'baselines'])
FILE_MAX = 2097152
TOTAL_MAX = 16777216
TOOLCHAIN = toolchain('air.deliverables-toolchain/0.32')
OPS = {'and': 'et', 'or': 'ou', 'not': 'non', 'eq': '=', 'ne': '≠', 'lt': '<', 'lte': '≤', 'gt': '>', 'gte': '≥', 'in': 'dans',
       'add': '+', 'sub': '−', 'mul': '×', 'div': '÷', 'length': 'longueur'}


# ------------------------------------------------------------------ helpers

def cell(value):
    return str(value).replace('|', '/').replace('\n', ' ').strip()


def mid(value):
    """A short, stable Mermaid node identifier from any object identifier."""
    return 'n' + hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:12]


def label(value):
    """Quoted Mermaid text: quotes and line breaks removed, cut at 120 characters inside the quotes."""
    return '"' + prose(value).replace('"', "'").replace('\n', ' ').replace('#', '№')[:120] + '"'


def expression_text(node):
    """AIR-Expr as a sentence an architect can read: gte(score, 80) becomes score ≥ 80."""
    if not isinstance(node, dict): return str(node)
    if 'literal' in node:
        value = node['literal'].get('value', node['literal'].get('state', '?'))
        if value is True and node['literal'].get('type') == 'Boolean': return 'toujours'
        return str(value) if not isinstance(value, list) else '[' + ', '.join(map(str, value)) + ']'
    if 'ref' in node: return node['ref']
    op = node.get('op')
    if op in ('every', 'some'): return ('chaque' if op == 'every' else 'un') + ' élément de ' + expression_text(node['over']) + ' : ' + expression_text(node['predicate'])
    args = node.get('args', [])
    if op in ('not', 'length'): return OPS[op] + '(' + expression_text(args[0]) + ')'
    if len(args) == 2: return '(' + expression_text(args[0]) + ' ' + OPS.get(op, op) + ' ' + expression_text(args[1]) + ')'
    return str(op)


class Graph:
    """The union of the pinned baselines: one object per identifier, the highest revision wins."""

    def __init__(self, exports):
        self.exports = exports
        self.by_id = {}
        self.by_ref = {}
        self.revision_conflicts = []
        revisions_by_id = defaultdict(set)
        for exported in exports:
            for obj in exported['objects']:
                self.by_ref[(obj['meta']['id'], obj['meta']['revision'])] = obj
                revisions_by_id[obj['meta']['id']].add(obj['meta']['revision'])
                current = self.by_id.get(obj['meta']['id'])
                if current is None or obj['meta']['revision'] > current['meta']['revision']: self.by_id[obj['meta']['id']] = obj
        for identity in sorted(self.by_id):
            revisions = sorted(revisions_by_id[identity])
            if len(revisions) > 1: self.revision_conflicts.append({'id': identity, 'revisions': revisions})
        self.by_type = defaultdict(list)
        for obj in sorted(self.by_id.values(), key=lambda o: o['meta']['id']): self.by_type[obj['meta']['type'][4:]].append(obj)

    def of(self, kind): return self.by_type.get(kind, [])

    def get(self, ref): return self.by_ref.get((ref.get('id'), ref.get('revision'))) if isinstance(ref, dict) else None

    def name(self, ref):
        obj = self.get(ref)
        return obj['meta']['name'] if obj else (ref['id'].rsplit(':', 1)[-1] if isinstance(ref, dict) else str(ref))


def src(objects):
    """The exact sources of a document, as its last section."""
    refs = sorted({(o['meta']['type'], o['meta']['id'], o['meta']['revision']) for o in objects})
    if not refs: return ['## Sources', '', 'Aucun objet du dossier ne porte ce livrable : c’est un manque à combler.']
    counts = Counter(t for t, _, _ in refs)
    lines = ['## Sources', '', 'Objets exacts du dossier : ' + ', '.join(str(n) + ' ' + t[4:] for t, n in sorted(counts.items())) + '.', '',
             '<details><summary>Liste des références</summary>', '']
    lines += ['- `' + i + '` r' + str(r) for _, i, r in refs[:400]]
    return lines + ([''] + ['… et ' + str(len(refs) - 400) + ' autres.'] if len(refs) > 400 else []) + ['', '</details>']


def table(headers, rows):
    if not rows: return ['Aucun élément déclaré.']
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] + \
           ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in rows]


def mermaid(lines):
    return ['```mermaid', *lines, '```']


# ------------------------------------------------------------------ deliverables

def d_graph(g):
    components = g.of('RuntimeComponent');connections = g.of('Connection')
    production = [c for c in components if (g.get(c['body']['environment']) or {}).get('body', {}).get('stage') == 'PRODUCTION']
    lines = ['Ce qui doit tourner à la fin, relié à ce qui le justifie : composant d’exécution en production, bloc d’architecture qu’il réalise,',
             'contrats fournis et requis. Le graphe est calculé depuis les baselines épinglées ; un bloc sans composant est un manque.', '']
    lines += ['## Composants en production et leurs connexions', '']
    diagram = ['flowchart LR']
    for c in production: diagram.append('  ' + mid(c['meta']['id']) + '[' + label(c['meta']['name'] + ' · ' + c['body']['kind']) + ']')
    ids = {c['meta']['id'] for c in production}
    for link in connections:
        if link['body']['source']['id'] in ids and link['body']['target']['id'] in ids:
            diagram.append('  ' + mid(link['body']['source']['id']) + ' -->|' + label(link['body']['protocol'] + (' 🔒' if link['body']['encrypted'] else '')) + '| ' + mid(link['body']['target']['id']))
    lines += mermaid(diagram) if production else ['_Aucun composant de production déclaré._']
    lines += ['', '## Blocs d’architecture, contrats et composants', '']
    diagram = ['flowchart TB']
    blocks = g.of('ArchitectureBlock')
    for b in blocks:
        diagram.append('  ' + mid(b['meta']['id']) + '[[' + label(b['meta']['name']) + ']]')
        for ref in b['body']['provided_contracts']: diagram.append('  ' + mid(b['meta']['id']) + ' -- fournit --> ' + mid(ref['id']) + '([' + label(g.name(ref)) + '])')
        for ref in b['body']['required_contracts']: diagram.append('  ' + mid(b['meta']['id']) + ' -. requiert .-> ' + mid(ref['id']))
    for c in production:
        for ref in c['body'].get('realizes', []):
            if (g.get(ref) or {}).get('meta', {}).get('type') == 'air.ArchitectureBlock':
                diagram.append('  ' + mid(c['meta']['id']) + '{{' + label(c['meta']['name']) + '}} == réalise ==> ' + mid(ref['id']))
    lines += mermaid(diagram) if blocks else ['_Aucun bloc déclaré._']
    realised = {r['id'] for c in production for r in c['body'].get('realizes', [])}
    missing = [b for b in blocks if b['meta']['id'] not in realised]
    lines += ['', '## Blocs sans composant de production', ''] + (table(['Bloc', 'Espace'], [[b['meta']['name'], b['meta']['namespace']] for b in missing]) if missing else ['Tous les blocs ont un composant de production.'])
    return 'Graphe du dossier', lines, production + connections + blocks


def d_value_stream(g):
    streams = g.of('ValueStream');lines = ['Du déclencheur à la valeur rendue, étape par étape, avec les capacités, fonctions et mesures de chaque étape.', '']
    for s in streams:
        lines += ['## ' + s['meta']['name'], '', '**Déclencheur :** ' + s['body']['trigger'] + '  ', '**Valeur :** ' + s['body']['value'] + '  ',
                  '**Pour :** ' + g.name(s['body']['stakeholder']), '']
        diagram = ['flowchart LR', '  start((' + label('Déclencheur') + '))']
        previous = 'start'
        for stage in s['body']['stages']:
            node = mid(s['meta']['id'] + stage['id']);diagram.append('  ' + node + '[' + label(stage['name'] + (' · ' + stage['lead_time'] if stage.get('lead_time') else '')) + ']')
            diagram.append('  ' + previous + ' --> ' + node);previous = node
        diagram += ['  value((' + label('Valeur') + '))', '  ' + previous + ' --> value']
        lines += mermaid(diagram) + ['']
        lines += table(['Étape', 'Capacités', 'Fonctions', 'Mesures'], [[st['name'], ', '.join(g.name(r) for r in st.get('capabilities', [])),
                        ', '.join(g.name(r) for r in st.get('functions', [])), ', '.join(g.name(r) for r in st.get('metrics', []))] for st in s['body']['stages']]) + ['']
    return 'Chaîne de valeur de bout en bout', lines, streams


def d_journeys(g):
    journeys = g.of('CustomerJourney');lines = ['Chaque parcours client, ses points de contact, et l’opération de système que chaque étape déclenche.', '']
    for j in journeys:
        lines += ['## ' + j['meta']['name'], '', '**Persona :** ' + g.name(j['body']['persona']) + '  ', '**But :** ' + j['body']['goal'], '']
        diagram = ['flowchart LR']
        previous = None
        for step in j['body']['steps']:
            node = mid(j['meta']['id'] + step['id']);diagram.append('  ' + node + '[' + label(step['name'] + ' · ' + step['channel']) + ']')
            if previous: diagram.append('  ' + previous + ' --> ' + node)
            if 'operation' in step: diagram.append('  ' + node + ' -.-> ' + mid(j['meta']['id'] + step['id'] + 'op') + '([' + label(g.name(step['operation']['contract']) + ' · ' + step['operation']['name']) + '])')
            previous = node
        lines += mermaid(diagram) + ['']
        lines += table(['Étape', 'Canal', 'Point de contact', 'Opération', 'Irritants'], [[s['name'], s['channel'], s['touchpoint'],
                        (g.name(s['operation']['contract']) + ' · ' + s['operation']['name']) if 'operation' in s else (g.name(s['function']) if 'function' in s else '-'),
                        '; '.join(s.get('pain_points', [])) or '-'] for s in j['body']['steps']]) + ['']
    from air import journey_catalog
    inventory = journey_catalog.project(g)
    lines += ['## Inventaire des personas et couverture des usages', '',
              'Périmètre déclaré, pas une preuve de recherche UX ou de conformité réglementaire.', '']
    lines += table(['Persona', 'Couverture', 'Justification', 'Parcours', 'Contextes requis', 'Contextes manquants'],
        [[p['name'], p['coverage'], p['rationale'], str(len(p['journeys'])), ', '.join(p['required_contexts']),
          ', '.join(p['missing_contexts']) or '-'] for p in inventory['personas']]) + ['']
    for j in inventory['journeys']:
        lines += ['### Carte d’expérience : ' + j['name'], '',
                  'Customer Journey Map complétée par un service blueprint. Les inconnues ne sont ni des scores neutres ni des observations.', '']
        lines += table(['Étape et phase', 'Action et pensées', 'Acteurs', 'Touchpoints', 'Systèmes déclarés', 'Émotion et statut', 'Service visible', 'Actions internes', 'Support', 'Opportunités'],
            [[st['name'] + ' / ' + st.get('phase', 'À préciser'), st.get('action', st['name']) + ' / ' + '; '.join(st.get('thoughts', [])),
              ', '.join(p['name'] for p in [j['persona'], *st['participants']]), st['touchpoint'], ', '.join(p['name'] for p in st['systems']) or 'À préciser',
              st['emotion'].get('label', 'Inconnue') + ' / ' + st['emotion']['status'] + (' / ' + str(st['emotion']['score']) + '/5' if 'score' in st['emotion'] else ''),
              '; '.join(st.get('frontstage', [])) or 'À préciser', '; '.join(st.get('backstage', [])) or 'À préciser',
              '; '.join(st.get('support_processes', [])) or 'À préciser', '; '.join(st.get('opportunities', [])) or 'À préciser'] for st in j['steps']]) + ['']
        lines += ['### Usages : ' + j['name'], ''] + table(['Étape', 'Intervenants', 'Usages et lieux', 'Liens architecture'],
            [[st['name'], ', '.join(p['name'] for p in st['participants']),
              '; '.join(p.get('kind', 'UNRESOLVED') + ' : ' + p['name'] + ' (' + p.get('status', 'UNRESOLVED') + ')' for p in st['usage_points']),
              '; '.join(a['name'] + ' : ' + a['selector'] for a in st['architecture_links'])] for st in j['steps']]) + ['']
    lines += ['## Checklist documentaire des parcours', ''] + table(['Contrôle', 'État', 'Lacunes'],
        [[c['label'], c['status'], str(c['gap_count'])] for c in inventory['checks']])
    return 'Parcours clients et points de contact', lines, journeys + g.of('JourneyCatalog') + g.of('Touchpoint') + g.of('UsagePoint') + g.of('Actor') + g.of('Stakeholder')


def d_processes(g):
    workflows = g.of('Workflow');lines = ['Les processus métier du dossier. Une condition gardée est exécutable (AIR-Expr) ; une condition en texte ne l’est pas.', '']
    for w in workflows:
        lines += ['## ' + w['meta']['name'], '', w['meta']['description'], '']
        diagram = ['flowchart LR']
        lanes = defaultdict(list)
        for step in w['body']['steps']: lanes[tuple(g.name(r) for r in step['participants'])].append(step)
        for index, (participants, steps) in enumerate(lanes.items()):
            diagram.append('  subgraph lane_' + mid(w['meta']['id'] + str(index)) + '[' + label(' / '.join(participants)) + ']')
            for step in steps:
                diagram.append('  ' + mid(w['meta']['id'] + step['id']) + '[' + label(step['name']) + ']')
            diagram.append('  end')
        for start in w['body']['start_steps']: diagram.append('  start_' + mid(w['meta']['id'])[2:] + '((début)) --> ' + mid(w['meta']['id'] + start))
        for flow in w['body']['flows']:
            text = expression_text(flow['guard']['ast']) if 'guard' in flow else flow['condition']
            diagram.append('  ' + mid(w['meta']['id'] + flow['source']) + ' -->|' + label(text) + '| ' + mid(w['meta']['id'] + flow['target']))
        lines += mermaid(diagram) + ['']
        lines += ['Le site fournit la vue BPMN 2.0 descriptive en couloirs, son layout et son XML. Le Mermaid ci-dessus reste une vue documentaire secondaire.', '']
        guarded = sum(1 for f in w['body']['flows'] if 'guard' in f)
        lines += ['Conditions exécutables : ' + str(guarded) + ' sur ' + str(len(w['body']['flows'])) + '. Fin : ' + w['body']['termination_policy'], '']
    models = g.of('OperatingModel')
    if models: lines += ['## Modèles opératoires', ''] + table(['Modèle', 'Services', 'Processus'], [[m['meta']['name'], ', '.join(g.name(r) for r in m['body']['services']), ', '.join(g.name(r) for r in m['body']['workflows'])] for m in models])
    return 'Processus métier', lines, workflows + models


def d_roles(g):
    roles = g.of('Role');actors = g.of('Actor')
    lines = ['Les rôles déclarés, ce qu’ils portent et l’autorité qui les fonde ; puis les acteurs qui les tiennent.', '']
    lines += table(['Rôle', 'Responsabilités', 'Compétences', 'Autorité'], [[r['meta']['name'], '; '.join(r['body']['responsibilities']),
                       '; '.join(c.get('competency', '') for c in r['body'].get('required_competencies', [])), g.name(r['body'].get('authority'))] for r in roles])
    lines += ['', '## Acteurs', ''] + table(['Acteur', 'Nature', 'Rôles'], [[a['meta']['name'], a['body']['kind'], ', '.join(g.name(r) for r in a['body'].get('roles', []))] for a in actors])
    return 'Liste des rôles', lines, roles + actors


def _organisation(g, root_id, phase, heading):
    units = g.of('OrganizationUnit');children = defaultdict(list)
    for u in units:
        if 'parent' in u['body']: children[u['body']['parent']['id']].append(u)
    tree = []
    def walk(unit):
        tree.append(unit)
        for child in children.get(unit['meta']['id'], []): walk(child)
    root = g.by_id.get(root_id) if root_id else None
    if root: walk(root)
    lines = [heading, '']
    if not root: lines += ['Racine d’organisation non déclarée pour cette phase' + (': `' + root_id + '`.' if root_id else '.'), '']
    else:
        diagram = ['flowchart TD']
        for u in tree:
            diagram.append('  ' + mid(u['meta']['id']) + '[' + label(u['meta']['name']) + ']')
            if 'parent' in u['body'] and u['body']['parent']['id'] in {t['meta']['id'] for t in tree}: diagram.append('  ' + mid(u['body']['parent']['id']) + ' --> ' + mid(u['meta']['id']))
        lines += mermaid(diagram) + [''] + table(['Unité', 'Mandat', 'Rôles'], [[u['meta']['name'], u['body']['mandate'], ', '.join(g.name(r) for r in u['body'].get('roles', []))] for u in tree]) + ['']
    raci = [r for r in g.of('RaciAssignment') if r['body']['phase'] == phase]
    roles = sorted({r['body']['role']['id'] for r in raci}, key=lambda i: g.name({'id': i}))
    activities = sorted({r['body']['activity'] for r in raci})
    cells = {(r['body']['activity'], r['body']['role']['id']): r['body']['responsibility'] for r in raci}
    lines += ['## Matrice RACI', '']
    lines += table(['Activité'] + [g.name({'id': r}) for r in roles], [[a] + [cells.get((a, r), '') for r in roles] for a in activities]) + ['']
    deciders = [[a, g.name({'id': r})] for (a, r), letter in sorted(cells.items()) if letter == 'A']
    lines += ['## Qui décide', '', 'Le rôle Accountable (A) de chaque activité est celui qui décide et répond du résultat.', ''] + table(['Activité', 'Décideur'], deciders)
    return lines, tree + raci


def d_delivery_org(g, root):
    lines, objs = _organisation(g, root, 'DELIVERY', 'Organisation de l’équipe de réalisation, sa matrice RACI et ses décideurs.')
    scopes = g.of('AuthorityScope')
    lines += ['', '## Périmètres d’autorité', ''] + table(['Titulaire', 'Décisions permises', 'Limites'], [[s['body']['principal'], '; '.join(s['body']['allowed_decisions']), '; '.join(s['body']['limits'])] for s in scopes])
    return 'Organisation de la réalisation et RACI', lines, objs + scopes


def d_operations_org(g, root):
    lines, objs = _organisation(g, root, 'OPERATIONS', 'Organisation des équipes d’exploitation une fois en production, et leur matrice RACI.')
    return 'Organisation de l’exploitation', lines, objs


def _environment_diagram(g, stage):
    environments = [e for e in g.of('Environment') if e['body']['stage'] == stage]
    env_ids = {e['meta']['id'] for e in environments}
    zones = [z for z in g.of('NetworkZone') if z['body']['environment']['id'] in env_ids]
    components = [c for c in g.of('RuntimeComponent') if c['body']['environment']['id'] in env_ids]
    ids = {c['meta']['id'] for c in components}
    links = [l for l in g.of('Connection') if l['body']['source']['id'] in ids or l['body']['target']['id'] in ids]
    if not components: return ['_Aucun composant déclaré pour ' + stage + '._'], environments + zones
    diagram = ['flowchart LR']
    for z in zones:
        diagram.append('  subgraph ' + mid(z['meta']['id']) + '[' + label(z['meta']['name'] + ' · ' + z['body']['trust_level']) + ']')
        for c in components:
            if c['body']['zone']['id'] == z['meta']['id']:
                tech = ', '.join(g.name(t) for t in c['body'].get('technologies', []))
                diagram.append('    ' + mid(c['meta']['id']) + '[' + label(c['meta']['name'] + ' · ' + c['body']['kind'] + (' · ' + tech if tech else '')) + ']')
        diagram.append('  end')
    for l in links:
        diagram.append('  ' + mid(l['body']['source']['id']) + ' -->|' + label(l['body']['protocol'] + (':' + str(l['body']['port']) if 'port' in l['body'] else '') + (' 🔒' if l['body']['encrypted'] else '')) + '| ' + mid(l['body']['target']['id']))
    return mermaid(diagram), environments + zones + components + links


def d_system(g):
    lines = ['Trois architectures : ce qu’il faut pour construire et tester, pour livrer, et ce qui tourne en production.', '']
    objs = []
    for stage, title in (('BUILD_TEST', 'Construire et tester'), ('RELEASE', 'Livrer'), ('PRODUCTION', 'Production')):
        diagram, used = _environment_diagram(g, stage);objs += used
        lines += ['## ' + title, ''] + diagram + ['']
    return 'Architectures système', lines, objs


def d_sequences(g):
    lines = ['Séquences d’interaction : chaque processus, du bloc qui réalise une étape au suivant ; puis chaque parcours client jusqu’à l’opération appelée.', '']
    realiser = {}
    for b in g.of('ArchitectureBlock'):
        for f in b['body']['functions']: realiser.setdefault(f['id'], b)
    provider = {}
    for b in g.of('ArchitectureBlock'):
        for c in b['body']['provided_contracts']: provider.setdefault(c['id'], b)
    objs = []
    for w in g.of('Workflow'):
        steps = {s['id']: s for s in w['body']['steps']}
        who = lambda sid: (realiser.get(steps[sid]['function']['id']) or {'meta': {'name': g.name(steps[sid]['function'])}})['meta']['name']
        diagram = ['sequenceDiagram']
        for name in dict.fromkeys(who(s) for s in steps): diagram.append('  participant ' + mid(name) + ' as ' + name[:60])
        for flow in w['body']['flows']:
            text = expression_text(flow['guard']['ast']) if 'guard' in flow else flow['condition']
            diagram.append('  ' + mid(who(flow['source'])) + '->>' + mid(who(flow['target'])) + ': ' + (steps[flow['target']]['name'] + ' si ' + text)[:110].replace(';', ','))
        lines += ['## ' + w['meta']['name'], ''] + mermaid(diagram) + ['']
        objs.append(w)
    for j in g.of('CustomerJourney'):
        persona = g.name(j['body']['persona'])
        diagram = ['sequenceDiagram', '  actor ' + mid(persona) + ' as ' + persona[:60]]
        for s in j['body']['steps']:
            if 'operation' in s:
                target = (provider.get(s['operation']['contract']['id']) or {'meta': {'name': g.name(s['operation']['contract'])}})['meta']['name']
                diagram.append('  ' + mid(persona) + '->>' + mid(target) + ': ' + (s['operation']['name'] + ' (' + s['channel'] + ')')[:110])
                diagram.append('  ' + mid(target) + '-->>' + mid(persona) + ': ' + s['name'][:80])
        if len(diagram) > 2: lines += ['## Parcours : ' + j['meta']['name'], ''] + mermaid(diagram) + ['']
        objs.append(j)
    return 'Diagrammes de séquence', lines, objs


def d_states(g):
    machines = g.of('StateMachine');lines = ['Les cycles de vie déclarés. Une garde est une règle exécutable, rejouable avec air_replay_state_machine.', '']
    for m in machines:
        diagram = ['stateDiagram-v2', '  [*] --> ' + m['body']['initial_state']]
        for t in m['body']['transitions']:
            guard = expression_text(t['guard']['ast']) if isinstance(t.get('guard'), dict) and 'ast' in t['guard'] else ''
            diagram.append('  ' + t['source'] + ' --> ' + t['target'] + ' : ' + (t['trigger'] + (' [' + guard + ']' if guard and guard != 'True' else ''))[:100].replace(':', ' '))
        for s in m['body']['states']:
            if s['terminal']: diagram.append('  ' + s['id'] + ' --> [*]')
        lines += ['## ' + m['meta']['name'], ''] + mermaid(diagram) + ['']
    return 'Diagrammes d’états', lines, machines


def d_decisions(g):
    rules = [r for r in g.of('BusinessRule') if 'expression' in r['body']]
    lines = ['Arbres de décision : les règles métier exécutables, puis les embranchements gardés des processus.', '']
    if rules:
        diagram = ['flowchart TD']
        for r in rules:
            node = mid(r['meta']['id'])
            diagram.append('  ' + node + '{' + label(expression_text(r['body']['expression']['ast'])) + '}')
            diagram.append('  ' + node + ' -->|oui| ' + node + 'y[' + label(r['body']['statement']) + ']')
            diagram.append('  ' + node + ' -->|non| ' + node + 'n[' + label('règle non applicable') + ']')
        lines += ['## Règles métier', ''] + mermaid(diagram) + ['']
    for w in g.of('Workflow'):
        guarded = [f for f in w['body']['flows'] if 'guard' in f]
        if not guarded: continue
        steps = {s['id']: s['name'] for s in w['body']['steps']}
        diagram = ['flowchart TD']
        for source in sorted({f['source'] for f in guarded}):
            node = mid(w['meta']['id'] + source + 'd');diagram.append('  ' + node + '{' + label('Après ' + steps[source]) + '}')
            for f in [x for x in guarded if x['source'] == source]:
                diagram.append('  ' + node + ' -->|' + label(expression_text(f['guard']['ast'])) + '| ' + mid(w['meta']['id'] + f['target']) + '[' + label(steps[f['target']]) + ']')
        lines += ['## Embranchements de ' + w['meta']['name'], ''] + mermaid(diagram) + ['']
    return 'Arbres de décision', lines, rules + g.of('Workflow')


def d_hypotheses(g):
    assumptions = g.of('Assumption');unknowns = g.of('Unknown')
    lines = ['Ce qui est tenu pour vrai sans preuve, ce que cela coûte si c’est faux, et comment le vérifier ; puis les questions ouvertes.', '']
    lines += table(['Hypothèse', 'Énoncé', 'Si fausse', 'Plan de validation', 'Échéance', 'État'],
                   [[a['meta']['name'], a['body']['statement'], a['body']['impact_if_false'], a['body']['validation_plan'], a['body']['review_due'][:10], a['body']['state']] for a in assumptions])
    lines += ['', '## Inconnues', ''] + table(['Question', 'Responsable', 'Politique', 'État'],
                   [[u['body']['question'], u['body']['resolution_owner'], u['body']['blocking_policy'], u['body']['state']] for u in unknowns])
    return 'Hypothèses', lines, assumptions + unknowns


def d_traceability(g):
    functions = defaultdict(list)
    for f in g.of('Function'):
        for r in f['body']['satisfies']: functions[r['id']].append(f)
    exposure = defaultdict(list)
    for c in g.of('SemanticContract'):
        for op in c['body']['operations']: exposure[op['function']['id']].append(c['meta']['name'] + ' · ' + op['name'])
    units = defaultdict(list)
    for u in g.of('ConstructionUnit'):
        for r in u['body']['realizes']: units[r['id']].append(u['meta']['name'])
    cases = defaultdict(list)
    for c in g.of('VerificationCase'): cases[c['body']['target']['id']].append(c)
    runs = defaultdict(list)
    for r in g.of('VerificationRun'): runs[r['body']['case']['id']].append(r)
    last = lambda case: sorted(runs.get(case['meta']['id'], []), key=lambda r: r['body']['executed_at'])[-1]['body'] if runs.get(case['meta']['id']) else None
    rows = []
    for req in g.of('Requirement'):
        fs = functions.get(req['meta']['id'], [])
        if not fs: rows.append([req['meta']['name'], req['body']['priority'], '-', '-', '-', '-', 'Aucune fonction'])
        for f in fs:
            contract_ops = exposure.get(f['meta']['id'], [])
            contract_units = [u for c in g.of('SemanticContract') for op in c['body']['operations'] if op['function']['id'] == f['meta']['id'] for u in units.get(c['meta']['id'], [])]
            realised = sorted(set(units.get(f['meta']['id'], []) + contract_units))
            fc = cases.get(f['meta']['id'], [])
            status = '; '.join(c['meta']['name'] + ' : ' + (('%s (%s)' % (last(c)['result'], last(c)['proof_level'])) if last(c) else 'non exécuté') for c in fc) or 'aucun cas'
            rows.append([req['meta']['name'], req['body']['priority'], f['meta']['name'], ', '.join(contract_ops) or '-', ', '.join(realised) or '-',
                         str(len(fc)), status])
    lines = ['Chaque exigence jusqu’à la fonction qui la satisfait, l’opération qui l’expose, le bloc de construction qui la réalise et le',
             'cas qui la vérifie, avec le résultat de sa dernière exécution.', ''] + table(['Exigence', 'Priorité', 'Fonction', 'Opérations', 'Unités de construction', 'Cas', 'Vérification'], rows)
    return 'Matrice de traçabilité exigences / construction', lines, g.of('Requirement') + g.of('Function') + g.of('ConstructionUnit') + g.of('VerificationCase') + g.of('VerificationRun')


def d_capabilities(g):
    capabilities = g.of('Capability');domains = {d['meta']['id']: d for d in g.of('Domain')}
    by_domain = defaultdict(list)
    for c in capabilities:
        context = g.get(c['body'].get('context')) if 'context' in c['body'] else None
        by_domain[(context or {}).get('meta', {}).get('name', 'Sans contexte')].append(c)
    lines = ['Les capacités métier, regroupées par contexte, avec les fonctions qui les rendent possibles.', '']
    if capabilities:
        diagram = ['flowchart LR']
        for group, items in sorted(by_domain.items()):
            diagram.append('  subgraph ' + mid(group) + '[' + label(group) + ']')
            for c in items: diagram.append('    ' + mid(c['meta']['id']) + '[' + label(c['meta']['name']) + ']')
            diagram.append('  end')
        lines += mermaid(diagram) + ['']
    lines += table(['Capacité', 'Aptitude', 'Fonctions requises'], [[c['meta']['name'], c['body']['ability'], ', '.join(g.name(r) for r in c['body']['required_functions'])] for c in capabilities])
    lines += ['', '## Domaines', ''] + table(['Domaine', 'Finalité'], [[d['meta']['name'], d['body']['purpose']] for d in domains.values()])
    return 'Carte des capacités métier', lines, capabilities + list(domains.values())


def d_gaps(g, gates):
    gaps = g.of('ArchitectureGap')
    lines = ['L’écart entre ce qui est décrit et ce qu’il faut pour construire : manques déclarés, puis critères de la porte « prêt à construire » non tenus.', '']
    lines += table(['Manque', 'Nature', 'Impact', 'Responsable'], [[x['meta']['name'], x['body']['missing_element_kind'], x['body']['impact'], x['body']['resolution_owner']] for x in gaps])
    for gate in gates:
        lines += ['', '## Porte « prêt à construire » - ' + gate['namespace'] + ' : ' + gate['result'], '']
        lines += table(['Critère', 'État', 'Pour le fermer'], [[r[0], r[1], r[3]] for r in map(_criterion_row, gate['criteria'])])
    return 'Analyse d’écarts', lines, gaps


def d_risks(g):
    assessments = g.of('RiskAssessment');risks = {r['meta']['id']: r for r in g.of('Risk')}
    rows, heat = [], Counter()
    for a in sorted(assessments, key=lambda a: -a['body']['likelihood'] * a['body']['impact']):
        b = a['body'];risk = risks.get(b['risk']['id']);score = b['likelihood'] * b['impact']
        residual = (b['residual_likelihood'] * b['residual_impact']) if 'residual_likelihood' in b else None
        heat[(b['likelihood'], b['impact'])] += 1
        rows.append([(risk or {}).get('meta', {}).get('name', b['risk']['id']), b['likelihood'], b['impact'], score, residual if residual is not None else '-',
                     b['status'], b['owner'], ', '.join(g.name(m) for m in b.get('mitigations', [])) or '-'])
    lines = ['Registre des risques : scénario, score (probabilité × impact, de 1 à 25), score résiduel après atténuation, propriétaire et mesures.', '']
    lines += table(['Risque', 'P', 'I', 'Score', 'Résiduel', 'État', 'Propriétaire', 'Atténuations'], rows)
    lines += ['', '## Carte de chaleur', '', 'Nombre de risques par probabilité (lignes) et impact (colonnes).', '']
    lines += table(['P \\ I', '1', '2', '3', '4', '5'], [[str(p)] + [str(heat[(p, i)] or '') for i in range(1, 6)] for p in range(5, 0, -1)])
    lines += ['', '## Journal d’audit', '']
    log = [[e['at'][:16].replace('T', ' '), (risks.get(a['body']['risk']['id']) or {}).get('meta', {}).get('name', '?'), e['event'], e['by']] for a in assessments for e in a['body']['log']]
    lines += table(['Date', 'Risque', 'Événement', 'Par'], sorted(log))
    lines += ['', '## Scénarios', ''] + table(['Risque', 'Scénario', 'Conséquences'], [[r['meta']['name'], r['body']['scenario'], '; '.join(r['body']['consequences'])] for r in risks.values()])
    return 'Journal des risques, cotation et atténuations', lines, assessments + list(risks.values())


def _months(start, end):
    y, m = map(int, start.split('-'));ye, me = map(int, end.split('-'))
    while (y, m) <= (ye, me):
        yield y;m += 1
        if m > 12: y, m = y + 1, 1


def d_finance(g):
    from air import financial_view
    view = financial_view.project(g)
    used = g.of('CostItem') + g.of('FinancialPlan') + g.of('Estimate')
    for row in view['rows']:
        used += [g.get(r) for r in row['sources'] if g.get(r)]
    for plan in view['plans']:
        used += [g.get(r) for r in plan['sources_exact'] if g.get(r)]
        if 'approval_source' in plan and g.get(plan['approval_source']): used.append(g.get(plan['approval_source']))
    lines = financial_view.lines(view)
    lines += ['', '## Charges estimées', ''] + table(['Cible', 'Mesure', 'Valeur', 'Unité', 'Classe de calibration'],
        [[g.name(e['body']['target']), e['body']['measure'], e['body']['value_or_distribution'].get('value', '?'),
          e['body']['value_or_distribution'].get('unit', ''), e['body']['calibration_class']] for e in g.of('Estimate')])
    return 'Dimension financière : plan et décomposition', lines, used


def d_ontology(g):
    concepts = g.of('Concept');relations = g.of('ConceptRelation')
    lines = ['L’ontologie du domaine : chaque notion, sa définition, son responsable, et ses relations typées.', '']
    if concepts:
        diagram = ['flowchart LR']
        for c in concepts: diagram.append('  ' + mid(c['meta']['id']) + '([' + label(c['meta']['name']) + '])')
        for r in relations:
            diagram.append('  ' + mid(r['body']['subject']['id']) + ' -->|' + r['body']['predicate'] + (' ' + r['body']['cardinality'] if 'cardinality' in r['body'] else '') + '| ' + mid(r['body']['object']['id']))
        lines += mermaid(diagram) + ['']
    lines += table(['Notion', 'Définition', 'Domaine', 'Responsable'], [[c['meta']['name'], c['body']['definition'], g.name(c['body']['domain']), c['body']['steward']] for c in concepts])
    contexts = g.of('ContextRelation')
    if contexts:
        lines += ['', '## Carte des contextes', ''] + mermaid(['flowchart LR'] + ['  ' + mid(r['body']['upstream']['id']) + '[' + label(g.name(r['body']['upstream'])) + '] -->|' + r['body']['pattern'] + '| ' + mid(r['body']['downstream']['id']) + '[' + label(g.name(r['body']['downstream'])) + ']' for r in contexts])
    return 'Ontologie', lines, concepts + relations + contexts


def d_logical(g):
    entities = g.of('DataEntity');relations = g.of('ConceptRelation')
    lines = ['Modèle logique : les agrégats et entités, leurs attributs et leurs relations, indépendamment de tout stockage.', '']
    if entities:
        diagram = ['erDiagram']
        for e in entities:
            name = mid(e['meta']['id'])
            diagram.append('  ' + name + '[' + label(e['meta']['name']) + '] {')
            identity = {f['name'] for f in e['body']['identity']}
            for a in e['body']['attributes']: diagram.append('    ' + a['value_type'] + ' ' + a['name'] + (' PK' if a['name'] in identity else '') + (' "requis"' if a['required'] else ''))
            diagram.append('  }')
        lines += mermaid(diagram) + ['']
    lines += table(['Entité', 'Notion', 'Autorité', 'Identité'], [[e['meta']['name'], g.name(e['body']['concept']), g.name(e['body']['ownership']), ', '.join(f['name'] for f in e['body']['identity'])] for e in entities])
    for e in entities:
        lines += ['', '## Attributs de ' + e['meta']['name'], ''] + table(['Attribut', 'Type logique', 'Requis', 'Identité', 'Description'],
            [[a['name'], a['value_type'], 'oui' if a['required'] else 'non', 'oui' if a['name'] in {f['name'] for f in e['body']['identity']} else 'non', a['description']]
             for a in e['body']['attributes']])
    lines += ['', '## Relations sémantiques déclarées', '', 'La cardinalité est celle déclarée sur la relation. La cardinalité inverse et les contraintes d’entité ne sont pas déduites du prédicat.', '']
    lines += table(['Sujet', 'Relation', 'Objet', 'Cardinalité déclarée'],
        [[g.name(r['body']['subject']), r['body']['predicate'], g.name(r['body']['object']), r['body'].get('cardinality', 'non déclarée')] for r in relations])
    if relations:
        semantic = ['flowchart LR']
        for r in relations:
            b = r['body']
            semantic.append('  ' + mid(b['subject']['id']) + '([' + label(g.name(b['subject'])) + ']) -->|' +
                label(b['predicate'] + ' · ' + b.get('cardinality', 'cardinalité non déclarée')) + '| ' + mid(b['object']['id']) + '([' + label(g.name(b['object'])) + '])')
        lines += ['', '## Relations entre concepts associés aux entités', ''] + mermaid(semantic)
    return 'Modèle logique de données', lines, entities + relations


def d_physical(g):
    tables = g.of('PhysicalTable');lines = ['Modèle physique : tables, colonnes, clés et index, par base de données d’exécution.', '']
    if tables:
        diagram = ['erDiagram']
        for t in tables:
            diagram.append('  ' + mid(t['meta']['id']) + '[' + label(t['body']['name']) + '] {')
            for c in t['body']['columns']:
                marks = ', '.join(x for x in ('PK' if c['primary_key'] else '', 'FK' if 'references' in c else '') if x)
                diagram.append('    ' + re.sub(r'[^A-Za-z0-9_]', '_', c['type'])[:30] + ' ' + c['name'] + (' ' + marks if marks else ''))
            diagram.append('  }')
        lines += mermaid(diagram) + ['']
    lines += table(['Table', 'Base', 'Entité logique', 'Colonnes', 'Index'], [[t['body']['name'], g.name(t['body']['store']), g.name(t['body']['implements']) if 'implements' in t['body'] else '-',
                   len(t['body']['columns']), '; '.join(t['body'].get('indexes', [])) or '-'] for t in tables])
    for t in tables:
        lines += ['', '## Colonnes de ' + t['body']['name'] + ' - ' + g.name(t['body']['store']), ''] + table(
            ['Colonne', 'Type physique déclaré', 'Nullable', 'Clé primaire', 'Référence exacte'],
            [[c['name'], c['type'], 'oui' if c['nullable'] else 'non', 'oui' if c['primary_key'] else 'non',
              (g.name(c['references']['table']) + '.' + c['references']['column'] + ' r' + str(c['references']['table']['revision'])) if 'references' in c else '-'] for c in t['body']['columns']])
    links = ['flowchart LR']
    for t in tables:
        for c in t['body']['columns']:
            if 'references' in c:
                target = g.get(c['references']['table'])
                if target:
                    links.append('  ' + mid(t['meta']['id']) + '[' + label(t['body']['name'] + ' · ' + g.name(t['body']['store'])) + '] -->|' +
                        label(c['name'] + ' référence ' + c['references']['column']) + '| ' + mid(target['meta']['id']) + '[' + label(target['body']['name'] + ' · ' + g.name(target['body']['store'])) + ']')
    if len(links) > 1: lines += ['', '## Références de colonnes', ''] + mermaid(links)
    lines += ['', 'Les types et index sont des déclarations. Aucun DDL, contrainte UNIQUE/CHECK, comportement de suppression ou migration n’est généré. Les multiplicités inverses des clés étrangères ne sont pas inventées.', '']
    return 'Modèle physique de données', lines, tables


def d_infrastructure(g):
    lines = ['Infrastructure et réseau par environnement : zones, composants, technologies, protocoles et ports.', '']
    objs = []
    for e in g.of('Environment'):
        diagram, used = _environment_diagram(g, e['body']['stage']);objs += used
        lines += ['## ' + e['meta']['name'] + ' (' + e['body']['stage'] + ') - ' + e['body']['hosting'], '', e['body']['purpose'], ''] + diagram + ['']
    links = g.of('Connection')
    lines += ['## Flux réseau', ''] + table(['Source', 'Cible', 'Protocole', 'Port', 'Chiffré', 'Authentification', 'Objet'],
                   [[g.name(l['body']['source']), g.name(l['body']['target']), l['body']['protocol'], l['body'].get('port', '-'), 'oui' if l['body']['encrypted'] else 'NON', l['body']['authentication'], l['body']['purpose']] for l in links])
    return 'Architecture d’infrastructure et de réseau', lines, objs + links


def d_security(g, gates):
    zones = g.of('NetworkZone');components = {c['meta']['id']: c for c in g.of('RuntimeComponent')}
    lines = ['Architecture de sécurité : zones de confiance, contrôles qui les protègent, et chaque traversée de zone avec son chiffrement.', '']
    order = ['PUBLIC', 'DMZ', 'INTERNAL', 'RESTRICTED', 'MANAGEMENT']
    diagram = ['flowchart LR']
    for z in sorted(zones, key=lambda z: order.index(z['body']['trust_level'])):
        diagram.append('  subgraph ' + mid(z['meta']['id']) + '[' + label(z['body']['trust_level'] + ' · ' + z['meta']['name']) + ']')
        for c in components.values():
            if c['body']['zone']['id'] == z['meta']['id']: diagram.append('    ' + mid(c['meta']['id']) + '[' + label(c['meta']['name']) + ']')
        diagram.append('  end')
    zone_of = {c['meta']['id']: c['body']['zone']['id'] for c in components.values()}
    crossings = []
    for l in g.of('Connection'):
        a, b = zone_of.get(l['body']['source']['id']), zone_of.get(l['body']['target']['id'])
        if a and b and a != b:
            diagram.append('  ' + mid(l['body']['source']['id']) + ' -->|' + label(('🔒 ' if l['body']['encrypted'] else '⚠ clair ') + l['body']['authentication']) + '| ' + mid(l['body']['target']['id']))
            crossings.append(l)
    lines += mermaid(diagram) + [''] if zones else ['_Aucune zone de confiance déclarée._', '']
    lines += ['## Contrôles par zone', ''] + table(['Zone', 'Niveau', 'Contrôles'], [[z['meta']['name'], z['body']['trust_level'], '; '.join(g.name(c) for c in z['body'].get('controls', [])) or '-'] for z in zones])
    lines += ['', '## Traversées de zones', ''] + table(['Source', 'Cible', 'Chiffré', 'Authentification'], [[g.name(l['body']['source']), g.name(l['body']['target']), 'oui' if l['body']['encrypted'] else 'NON', l['body']['authentication']] for l in crossings])
    for gate in gates:
        security = next((c for c in gate['criteria'] if c['code'] == 'SECURITY_ZONES'), None)
        if security: lines += ['', 'Porte (' + gate['namespace'] + ') : ' + security['status'] + '. ' + ('; '.join(i['issue'] for i in security['detail']['issues']) or 'Aucune traversée fautive.')]
    controls = g.of('Control')
    lines += ['', '## Contrôles', ''] + table(['Contrôle', 'Objectif', 'Mécanisme', 'Propriétaire'], [[c['meta']['name'], c['body']['objective'], c['body']['mechanism'], c['body']['owner']] for c in controls])
    return 'Architecture de sécurité et zones de confiance', lines, zones + crossings + controls


def d_goals(g):
    goals = g.of('Goal');intents = g.of('Intent')
    lines = ['Objectifs stratégiques reçus en entrée (importables comme socle partagé) et leurs cibles mesurables.', '']
    lines += table(['Objectif', 'Résultat attendu', 'Cibles', 'Horizon', 'Espace'], [[x['meta']['name'], x['body']['outcome'],
                   '; '.join(_target(g, t) for t in x['body'].get('targets', [])),
                   (x['body'].get('horizon') or {}).get('end', '-')[:10], x['meta']['namespace']] for x in goals])
    lines += ['', '## Intentions', ''] + table(['Intention', 'Changement voulu', 'Commanditaire'], [[i['meta']['name'], i['body']['desired_change'], i['body']['sponsor']] for i in intents])
    return 'Objectifs stratégiques', lines, goals + intents


def _target(g, target):
    value = target.get('value', {})
    shown = value.get('value', value.get('state', '?')) if isinstance(value, dict) else value
    return (g.name(target['metric']) if 'metric' in target else target.get('id', '')) + ' ' + {'EQ': '=', 'LTE': '≤', 'GTE': '≥'}.get(target.get('operator'), '?') + ' ' + str(shown) + (' ' + value.get('type', '') if isinstance(value, dict) else '')


def d_principles(g):
    principles = g.of('ArchitecturePrinciple')
    lines = ['Principes d’architecture reçus en entrée (importables comme socle partagé) : énoncé, raison, implications.', '']
    for p in principles:
        lines += ['## ' + p['meta']['name'], '', '**Énoncé :** ' + p['body']['statement'], '', '**Raison :** ' + p['body']['rationale'], '', '**Implications :**', '']
        lines += ['- ' + i for i in p['body']['implications']] + ['']
    return 'Principes d’architecture', lines or ['_Aucun principe._'], principles


def d_adr(g):
    decisions = g.of('Decision');lines = ['Registre des décisions d’architecture (ADR) : question, options, choix, raison, conséquences et conditions de révision.', '']
    for i, d in enumerate(decisions, 1):
        b = d['body']
        options = [g.name(a) if isinstance(a, dict) else str(a) for a in b.get('alternatives', [])]
        selection = b.get('selection');chosen = g.name(selection) if isinstance(selection, dict) else str(selection)
        lines += ['## ADR-%03d - %s' % (i, d['meta']['name']), '', '**Statut :** proposée (' + d['meta']['lifecycle'] + ')  ', '**Autorité :** ' + str(b.get('authority', '-')), '',
                  '**Question :** ' + b['question'], '', '**Options :**', ''] + ['- ' + o for o in options] + ['', '**Décision :** ' + chosen, '',
                  '**Raison :** ' + b['rationale'], '', '**Conséquences :**', ''] + ['- ' + c for c in b.get('consequences', [])] + ['', '**Réviser si :**', ''] + ['- ' + c for c in b.get('revisit_conditions', [])] + ['']
    strategies = g.of('SourcingStrategy')
    lines += ['## Stratégie de consultation et choix des fournisseurs', '',
        'La stratégie RFI/RFP est une décision d’architecture reliée au périmètre et au jalon de consultation. Les statuts sont déclarés ; le compilateur n’envoie aucune consultation.', '']
    if not strategies: lines += ['Aucune stratégie de consultation déclarée ; documenter le choix RFI/RFP ou la décision de ne pas consulter.', '']
    for s in strategies:
        b = s['body']
        lines += ['### ' + s['meta']['name'], '', '**Stratégie :** ' + b['strategy'] + '. **Statut déclaré :** ' + b['status'] + '.',
            '**Décision :** ' + g.name(b['decision']) + '. **Jalon :** ' + g.name(b['milestone']) + '.',
            '**Objectif :** ' + b['purpose'], '**Responsable :** ' + b['owner'], '', '**Critères de sélection :**', '']
        lines += ['- ' + c for c in b['criteria']] + ['', '**Éléments concernés :** ' + ', '.join(g.name(r) for r in b['architecture_links']),
            '**Preuves exactes :** ' + (', '.join(g.name(r) for r in b['evidence']) or 'Aucune preuve de lancement ou sélection reçue.'), '']
        if 'selected_supplier' in b: lines += ['**Fournisseur déclaré sélectionné :** ' + g.name(b['selected_supplier']), '']
    return 'Registre des décisions d’architecture', lines, decisions + strategies


def d_technologies(g):
    technologies = g.of('Technology');used = defaultdict(list)
    for c in g.of('RuntimeComponent'):
        for t in c['body'].get('technologies', []): used[t['id']].append(c['meta']['name'])
    lines = ['Registre des technologies, classé comme un radar : ADOPT, TRIAL, ASSESS, HOLD ; avec les composants qui les emploient.', '']
    for status in ('ADOPT', 'TRIAL', 'ASSESS', 'HOLD'):
        rows = [[t['meta']['name'], t['body']['category'], t['body']['version'], t['body']['license'], t['body'].get('vendor', '-'),
                 ', '.join(sorted(set(used.get(t['meta']['id'], [])))) or '-', g.name(t['body']['decision']) if 'decision' in t['body'] else '-'] for t in technologies if t['body']['status'] == status]
        lines += ['## ' + status, ''] + table(['Technologie', 'Catégorie', 'Version', 'Licence', 'Éditeur', 'Employée par', 'Décision'], rows) + ['']
    return 'Registre des technologies', lines, technologies


def d_planning(g):
    milestones = sorted(g.of('Milestone'), key=lambda m: m['body']['target_date'])
    lines = ['Jalons de réalisation, dépendances et critères de sortie.', '']
    if milestones:
        diagram = ['gantt', '  dateFormat YYYY-MM-DD', '  title Jalons']
        for m in milestones: diagram.append('  ' + m['meta']['name'][:60].replace(':', ' ') + ' : milestone, ' + mid(m['meta']['id']) + ', ' + m['body']['target_date'] + ', 0d')
        lines += mermaid(diagram) + ['']
    lines += table(['Jalon', 'Date', 'Dépend de', 'Livrables', 'Critères de sortie'], [[m['meta']['name'], m['body']['target_date'], ', '.join(g.name(r) for r in m['body'].get('depends_on', [])) or '-',
                   ', '.join(g.name(r) for r in m['body'].get('deliverables', [])) or '-', '; '.join(m['body']['exit_criteria'])] for m in milestones])
    return 'Planning et jalons', lines, milestones


def d_readiness(g, gates):
    lines = ['Synthèse opposable : pour chaque projet, la porte « prêt à construire » et le niveau de preuve atteint. Cette synthèse est',
             'calculée ; elle ne vaut ni revue humaine, ni signature, ni admission.', '']
    for gate in gates:
        lines += ['## ' + gate['namespace'] + ' - ' + gate['result'], '', 'Baseline `' + gate['baseline']['id'] + '` révision ' + str(gate['baseline']['revision']) + ', empreinte `' + gate['baseline']['digest'] + '`.', '']
        lines += table(['Critère', 'État', 'Détail', 'Pour le fermer'], [_criterion_row(c) for c in gate['criteria']]) + ['']
        proof = gate['proof']
        lines += ['Preuve : ' + str(proof['verified_cases']) + ' cas vérifiés sur ' + str(proof['cases']) + ' ; '
                  + str(proof['declared_model_passes']) + ' succès sur modèle déclaré et ' + str(proof['unverified_passes'])
                  + ' autres succès non qualifiés ; ' + str(proof['qualified_design_cases'])
                  + ' cas qualifiés pour la conception. Seuls les tests externes signés et explicitement qualifiés '
                  + 'attestent une exécution dans leur environnement et leur fenêtre exacts.', '']
    runs = g.of('VerificationRun')
    qualified = {(s['selected_run']['id'], s['selected_run']['revision']): s for gate in gates for c in gate['criteria']
                 if c['code'] == 'VERIFICATION' for s in c['detail']['cases_detail'] if 'selected_run' in s}
    lines += ['## Exécutions de vérification', ''] + table(['Cas', 'Méthode', 'Résultat déclaré', 'Niveau déclaré', 'Qualification et portée', 'Date', 'Résumé'],
                   [[g.name(r['body']['case']), r['body']['method'], r['body']['result'], r['body']['proof_level'],
                     qualified.get((r['meta']['id'], r['meta']['revision']), {}).get('status', 'Non établie dans cet extrait'),
                     r['body']['executed_at'][:16], r['body']['summary']] for r in runs])
    lines += [''] + ['- Reçu de qualification : `' + receipt + '`.' for receipt in sorted({ref for s in qualified.values() for ref in s['qualification_receipts']})]
    return 'Préparation à la construction et preuve', lines, runs


CRITERIA_FR = {
    'CONTEXTUAL_COMPLETENESS': ('Questions du contexte et contrats de construction', 'Choisir le contexte puis compléter les questions, les contrats et les exclusions déclarées'),
    'REFERENCE_CLOSURE': ('Fermeture des références', 'Ajouter ou corriger les révisions référencées'),
    'STRUCTURE': ('Structure MECE et DDD', 'Résoudre chaque violation nommée par air_inspect_architecture'),
    'CONSTRUCTION_CHAIN': ('Chaîne exigence, fonction, contrat, unité, cas', 'Fermer chaque diagnostic ; air_guide explique chaque code'),
    'EXTERNAL_DEPENDENCIES': ('Emprunts complets chez leur propriétaire', 'Le projet propriétaire ferme ses diagnostics, puis ce projet se réaligne'),
    'KNOWLEDGE': ('Aucune inconnue bloquante ni assertion contestée', 'Résoudre ou déclasser explicitement'),
    'GAPS': ('Manques levés ou acceptés par une décision approuvée', 'Lever le manque, ou faire approuver la décision qui l’accepte par une revue humaine de la révision'),
    'VERIFICATION': ('Cas de conception passés, tests planifiés', 'Exécuter chaque inspection, revue, analyse ou simulation calibrée ; planifier chaque test dans une unité'),
    'PLANNING': ('Unités estimées, coûts et jalons déclarés', 'Ajouter estimations, postes de coût et jalons'),
    'RUNTIME': ('Chaque bloc a un composant de production', 'Déclarer environnement, zone et composant de production'),
    'SECURITY_ZONES': ('Traversées de zones chiffrées', 'Chiffrer la traversée ou passer par une passerelle en DMZ'),
    'COMPLIANCE': ('Couverture déclarée des contrôles et exigences de qualité', 'Relier chaque contrôle et chaque exigence non fonctionnelle aux blocs prévus et aux cas de vérification ; ces liens ne prouvent pas la conformité du système réalisé'),
    'INDEPENDENT_REVIEW': ('Revue humaine indépendante de la révision exacte', 'Un relecteur authentifié revoit cette révision (air review)'),
}
STATUS_FR = {'MET': 'tenu', 'NOT_MET': 'NON TENU', 'NOT_APPLICABLE': 'sans objet'}


def _criterion_row(c):
    title, fix = CRITERIA_FR.get(c['code'], (c['title'], c['to_close'] or ''))
    return [title, STATUS_FR.get(c['status'], c['status']), _detail(c), (fix + (' - geste humain' if c.get('owner') == 'human' else '')) if c['status'] == 'NOT_MET' else '-']


def _detail(criterion):
    d = criterion['detail']
    if 'design_cases' in d:
        return '%d cas de conception dont %d ouverts (%s) ; %d tests d’acceptation, %d non planifiés' % (d['design_cases'], len(d['design_cases_open']),
            ', '.join(c['name'] for c in d['design_cases_open'][:6]) or 'aucun', d['build_acceptance_tests'], len(d['tests_not_planned_in_a_unit']))
    for field in ('by_status', 'by_code'):
        if field in d and d[field]: return ', '.join('%s %s' % (k, v) for k, v in d[field].items())
    if 'open' in d: return '%d déclaré(s), %d ouvert(s), %d accepté(s) en attente de revue' % (d['declared'], len(d['open']), len(d.get('accepted_pending_review', [])))
    if 'reason' in d:
        return {'No control or quality requirement applies to this project': 'Aucun contrôle ni exigence de qualité applicable n’est déclaré pour ce projet.',
                'This project owns no architecture block and no requirement': 'Ce projet ne possède aucun bloc d’architecture ni exigence.',
                'The baseline profile carries no construction types': 'Le profil de cette baseline ne porte pas de types de construction.'}.get(d['reason'], d['reason'])
    if 'design_cases' in d: return '%d cas de conception dont %d ouverts ; %d tests d’acceptation, %d non planifiés' % (
        d['design_cases'], len(d['design_cases_open']), d['build_acceptance_tests'], len(d['tests_not_planned_in_a_unit']))
    if 'blocks_without_runtime' in d: return str(len(d['blocks_without_runtime'])) + ' bloc(s) sans composant'
    if 'issues' in d: return str(len(d['issues'])) + ' traversée(s) fautive(s)'
    if 'receipts' in d: return str(len(d['receipts'])) + ' reçu(s) de revue'
    if 'received_as_input' in d: return '%d à couvrir dont %d reçus, %d couverts' % (d['subjects'], d['received_as_input'], d['mapped'])
    if 'unestimated' in d: return '%s unité(s), %s non estimée(s), %s coût(s), %s jalon(s)' % (d['units'], len(d['unestimated']), d['cost_items'], d['milestones'])
    return ', '.join('%s %s' % (k, v) for k, v in d.items() if isinstance(v, (int, str)))[:200] or '-'


def d_events(g):
    """Who publishes each domain event, on which channel, and who consumes it: read from ports and channel bindings."""
    events = g.of('Event');ports = g.of('Port')
    publishers, subscribers, channels = defaultdict(set), defaultdict(set), {}
    used = list(events)
    for port in ports:
        block = g.get(port['body']['block'])
        for ref in port['body'].get('bindings', []):
            binding = g.get(ref)
            if not binding or 'channel_mapping' not in binding['body']: continue
            used.append(binding)
            for m in binding['body']['channel_mapping']:
                eid = m['event']['id'];channels[eid] = m
                (publishers if m['action'] == 'PUBLISH' else subscribers)[eid].add(block['meta']['name'] if block else g.name(port['body']['block']))
        used.append(port)
    lines = ['Les événements du domaine : qui les publie, sur quel canal, avec quelle garantie, et qui les consomme.',
             'Lu dans les ports et les liaisons de canal ; un événement sans canal n’est ni publié ni consommable.', '']
    by_channel = defaultdict(list)
    for e in events: by_channel[channels[e['meta']['id']]['channel'] if e['meta']['id'] in channels else None].append(e)
    diagram = ['flowchart LR']
    blocks = sorted({b for s in list(publishers.values()) + list(subscribers.values()) for b in s})
    for b in blocks: diagram.append('  ' + mid('block' + b) + '[' + label(b) + ']')
    for channel, items in sorted(by_channel.items(), key=lambda kv: kv[0] or '~'):
        if channel is None: continue
        diagram.append('  subgraph ' + mid('channel' + channel) + '[' + label('canal ' + channel) + ']')
        for e in items: diagram.append('    ' + mid(e['meta']['id']) + '{{' + label(e['meta']['name']) + '}}')
        diagram.append('  end')
    for e in events:
        for b in sorted(publishers.get(e['meta']['id'], ())): diagram.append('  ' + mid('block' + b) + ' -- publie --> ' + mid(e['meta']['id']))
        for b in sorted(subscribers.get(e['meta']['id'], ())): diagram.append('  ' + mid(e['meta']['id']) + ' -. consomme .-> ' + mid('block' + b))
    lines += (mermaid(diagram) if channels else ['_Aucun canal d’événements déclaré._']) + ['']
    rows = []
    for e in events:
        m = channels.get(e['meta']['id'])
        rows.append([e['meta']['name'], e['body']['semantic_meaning'], ', '.join(sorted(publishers.get(e['meta']['id'], ()))) or '-',
                     m['channel'] if m else 'sans canal', ('%s, %s, clé %s' % (m['delivery'], m['ordering'], m['key']['name'])) if m and 'key' in m else (m['delivery'] if m else '-'),
                     ', '.join(sorted(subscribers.get(e['meta']['id'], ()))) or '-', g.name(e['body']['payload_schema'])])
    lines += table(['Événement', 'Sens', 'Publié par', 'Canal', 'Garantie', 'Consommé par', 'Schéma'], rows)
    silent = [e['meta']['name'] for e in events if e['meta']['id'] not in channels]
    lines += ['', '## Événements sans canal', ''] + (['- ' + s for s in silent] if silent else ['Tous les événements sont publiés sur un canal.'])
    return 'Diagramme des événements', lines, used


def d_navigation(g):
    maps = g.of('NavigationMap');lines = ['Le graphe de navigation de chaque interface : écrans, transitions et opérations appelées.', '']
    shape = {'PAGE': ('[', ']'), 'DIALOG': ('([', '])'), 'WIZARD_STEP': ('[/', '/]'), 'TOOL': ('[[', ']]'), 'NOTIFICATION': ('>', ']'),
             'REPORT': ('[(', ')]'), 'EXTERNAL_LINK': ('((', '))')}
    used = list(maps)
    for m in maps:
        app = g.get(m['body']['application']);used += [app] if app else []
        lines += ['## ' + m['meta']['name'], '', '**Application :** ' + g.name(m['body']['application']) + '  ',
                  '**Pour :** ' + (', '.join(g.name(p) for p in m['body'].get('personas', [])) or '-'), '']
        diagram = ['flowchart LR', '  ' + mid(m['meta']['id'] + 'start') + '((' + label('entrée') + '))']
        for s in m['body']['screens']:
            left, right = shape[s['kind']]
            diagram.append('  ' + mid(m['meta']['id'] + s['id']) + left + label(s['name']) + right)
        for e in m['body']['entry_screens']: diagram.append('  ' + mid(m['meta']['id'] + 'start') + ' --> ' + mid(m['meta']['id'] + e))
        for t_ in m['body']['transitions']:
            text = t_['trigger'] + (' si ' + expression_text(t_['guard']['ast']) if 'guard' in t_ else '')
            diagram.append('  ' + mid(m['meta']['id'] + t_['source']) + ' -->|' + label(text) + '| ' + mid(m['meta']['id'] + t_['target']))
        lines += mermaid(diagram) + ['']
        with_roles = any(s.get('roles') for s in m['body']['screens'])
        lines += table(['Écran', 'Type', 'Finalité'] + (['Rôles'] if with_roles else []) + ['Opérations appelées'],
                       [[s['name'], s['kind'], s['purpose']] + ([', '.join(g.name(r) for r in s.get('roles', [])) or '-'] if with_roles else [])
                        + [', '.join(g.name(o['contract']) + ' · ' + o['name'] for o in s.get('operations', [])) or '-'] for s in m['body']['screens']]) + ['']
    uis = [c for c in g.of('RuntimeComponent') if c['body']['kind'] == 'USER_INTERFACE']
    mapped = {m['body']['application']['id'] for m in maps}
    missing = [c['meta']['name'] for c in uis if c['meta']['id'] not in mapped]
    lines += ['## Interfaces sans graphe de navigation', ''] + (['- ' + x for x in missing] if missing else ['Chaque interface déclarée a son graphe.'])
    return 'Graphe de navigation des interfaces', lines, used


def d_devices(g):
    devices = g.of('Device');components = {c['meta']['id']: c for c in g.of('RuntimeComponent')}
    lines = ['Les équipements physiques et les machines, par environnement : nature, quantité, capacité, emplacement et ce qu’ils hébergent.', '']
    hosted = {r['id'] for d in devices for r in d['body'].get('hosts', [])}
    for env in g.of('Environment'):
        here = [d for d in devices if d['body']['environment']['id'] == env['meta']['id']]
        if not here: continue
        lines += ['## ' + env['meta']['name'] + ' (' + env['body']['stage'] + ')', '']
        diagram = ['flowchart TB']
        for d in here:
            diagram.append('  subgraph ' + mid(d['meta']['id']) + '[' + label('%s × %d · %s' % (d['meta']['name'], d['body']['quantity'], d['body']['kind'])) + ']')
            for r in d['body'].get('hosts', []): diagram.append('    ' + mid(d['meta']['id'] + r['id']) + '[' + label(g.name(r)) + ']')
            if not d['body'].get('hosts'): diagram.append('    ' + mid(d['meta']['id'] + 'none') + '[' + label('aucun composant') + ']')
            diagram.append('  end')
        lines += mermaid(diagram) + ['']
        spec = lambda s: ', '.join(x for x in (s.get('model', ''), '%d vCPU' % s['cpu_cores'] if 'cpu_cores' in s else '', '%d Gio RAM' % s['memory_gib'] if 'memory_gib' in s else '',
                                               '%d Gio disque' % s['storage_gib'] if 'storage_gib' in s else '', s.get('operating_system', '')) if x) or '-'
        lines += table(['Équipement', 'Nature', 'Qté', 'Capacité unitaire', 'Emplacement', 'Zone', 'Héberge', 'Responsable', 'État'],
                       [[d['meta']['name'], d['body']['kind'], d['body']['quantity'], spec(d['body'].get('specification', {})), d['body']['location'],
                         g.name(d['body']['zone']) if 'zone' in d['body'] else '-', ', '.join(g.name(r) for r in d['body'].get('hosts', [])) or '-',
                         d['body']['owner'] + (' / ' + d['body']['provider'] if 'provider' in d['body'] else ''), d['body']['status']] for d in here]) + ['']
    totals = Counter()
    for d in devices: totals[d['body']['kind']] += d['body']['quantity']
    lines += ['## Totaux par nature', ''] + table(['Nature', 'Quantité'], sorted(totals.items()))
    orphan = [c['meta']['name'] for c in components.values() if c['meta']['id'] not in hosted and c['body']['kind'] != 'EXTERNAL_SYSTEM']
    lines += ['', '## Composants sans équipement', ''] + (['- ' + x for x in orphan] if orphan else ['Chaque composant est placé sur un équipement.'])
    return 'Équipements physiques et machines', lines, devices


def _fmt(value, digits=0):
    if value is None: return '-'
    q = Decimal(1) if digits == 0 else Decimal(1).scaleb(-digits)
    return '{:,}'.format(Decimal(value).quantize(q)).replace(',', ' ')


def d_scenarios(g):
    from air.acceptance import walk
    objects = list(g.by_id.values());report = walk(objects, None, owned_only=False)
    scenarios = {r['scenario']['id']: r for r in report['scenarios']}
    lines = ['Les scénarios d’acceptation de premier ordre : ce qu’un utilisateur doit pouvoir faire, de bout en bout, sur les écrans',
             'conçus. Chaque scénario est rejoué sur le modèle (écrans, transitions, gardes, opérations) avant tout développement ;',
             'le même scénario devient ensuite le test d’acceptation et de non-régression du logiciel construit.', '']
    s = report['summary']
    lines += ['Rejeu de conception : **%d scénarios, %d conformes, %d en échec, %d indécis**.' % (s['scenarios'], s['pass'], s['fail'], s['inconclusive']), '']
    rows = []
    for o in g.of('AcceptanceScenario'):
        r = scenarios.get(o['meta']['id'], {});b = o['body']
        rows.append([o['meta']['name'], g.name(b['persona']), g.name(b['navigation']), ', '.join(b['suites']), b['priority'], r.get('verdict', '-'),
                     g.name(b['design_case']) if 'design_case' in b else '-', g.name(b['acceptance_case']) if 'acceptance_case' in b else '-'])
    lines += table(['Scénario', 'Persona', 'Interface', 'Suites', 'Priorité', 'Rejeu de conception', 'Cas de conception', 'Test d’acceptation'], rows) + ['']
    lines += ['## Couverture des graphes de navigation', '']
    lines += table(['Interface', 'Scénarios', 'Écrans couverts', 'Transitions couvertes', 'Écrans jamais visités', 'Transitions jamais prises', 'Opérations jamais appelées', 'Impasses'],
                   [[c['name'], c['scenarios'], '%d / %d' % (c['screens_covered'], c['screens']), '%d / %d' % (c['transitions_covered'], c['transitions']),
                     ', '.join(c['screens_uncovered']) or '-', ', '.join(c['transitions_uncovered']) or '-', ', '.join(c['operations_uncovered']) or '-',
                     ', '.join(c['dead_ends']) or '-'] for c in report['coverage']]) + ['']
    lines += ['## Couverture des parcours clients', ''] + table(['Parcours', 'Opérations', 'Exercées', 'Non exercées'],
        [[j['name'], j['operations'], j['operations_exercised'], ', '.join(j['not_exercised']) or '-'] for j in report['journeys']]) + ['']
    for o in g.of('AcceptanceScenario'):
        r = scenarios.get(o['meta']['id'], {});b = o['body'];status = {x['step']: x for x in r.get('steps', [])}
        lines += ['## ' + o['meta']['name'] + ' - ' + r.get('verdict', '-'), '', '**Objectif :** ' + b['goal'] + '  ', '**Persona :** ' + g.name(b['persona']), '']
        if b.get('preconditions'): lines += ['**Préconditions :**', ''] + ['- ' + x for x in b['preconditions']] + ['']
        diagram = ['flowchart LR']
        for i, st in enumerate(b['steps']):
            node = mid(o['meta']['id'] + st['id'])
            diagram.append('  ' + node + '[' + label(str(i + 1) + '. ' + st['screen'] + ' · ' + st['action']) + ']')
            if i: diagram.append('  ' + mid(o['meta']['id'] + b['steps'][i - 1]['id']) + ' --> ' + node)
        lines += mermaid(diagram) + ['']
        lines += table(['Étape', 'Écran', 'Action', 'Opération', 'Résultat attendu', 'Rejeu'],
                       [[st['id'], st['screen'], st['action'], (g.name(st['operation']['contract']) + ' · ' + st['operation']['name']) if 'operation' in st else '-',
                         st['expected'], status.get(st['id'], {}).get('status', '-') + ((' : ' + status[st['id']]['issue']) if status.get(st['id'], {}).get('issue') else '')]
                        for st in b['steps']]) + ['']
    return 'Scénarios d’acceptation de premier ordre', lines, g.of('AcceptanceScenario') + g.of('NavigationMap')


def d_regression(g):
    from air.acceptance import walk
    report = walk(list(g.by_id.values()), None, owned_only=False);verdict = {r['scenario']['id']: r['verdict'] for r in report['scenarios']}
    unit_of_case = {}
    for u in g.of('ConstructionUnit'):
        for cr in u['body']['acceptance']:
            crit = g.get(cr)
            for c in (crit or {}).get('body', {}).get('cases', []): unit_of_case.setdefault(c['id'], u['meta']['name'])
    rows, n = [], 0
    order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    for o in sorted(g.of('AcceptanceScenario'), key=lambda o: (order[o['body']['priority']], o['meta']['name'])):
        b = o['body']
        if 'REGRESSION' not in b['suites'] and 'SMOKE' not in b['suites']: continue
        n += 1
        rows.append(['NR-%03d' % n, o['meta']['name'], 'Parcours utilisateur', b['priority'], '; '.join(b.get('preconditions', [])) or '-',
                     b['steps'][-1]['expected'], verdict.get(o['meta']['id'], '-'), ', '.join(x for x in b['suites'] if x != 'ACCEPTANCE')])
    for c in sorted(g.of('VerificationCase'), key=lambda c: c['meta']['name']):
        if c['body']['method'] != 'TEST': continue
        n += 1
        rows.append(['NR-%03d' % n, c['meta']['name'], 'Contrat ou exigence', '-', '; '.join(c['body'].get('inputs', []) if isinstance(c['body'].get('inputs'), list) and all(isinstance(x, str) for x in c['body'].get('inputs', [])) else []) or '-',
                     c['body']['oracle'], 'à exécuter après construction', unit_of_case.get(c['meta']['id'], 'non planifié')])
    lines = ['Le socle de non-régression de premier ordre : les parcours critiques rejoués à chaque livraison et les tests de contrat qui',
             'protègent chaque exigence. Les parcours ont déjà été rejoués sur le modèle ; tous s’exécuteront sur le logiciel construit.', '']
    lines += table(['Réf.', 'Test', 'Nature', 'Priorité', 'Préconditions', 'Résultat attendu', 'État', 'Suite ou unité'], rows)
    return 'Tests de non-régression du socle', lines, g.of('AcceptanceScenario') + [c for c in g.of('VerificationCase') if c['body']['method'] == 'TEST']


def d_compliance(g):
    from air.delivery_calc import compliance
    rows = compliance(list(g.by_id.values()), g.by_id)
    units = g.of('ConstructionUnit')
    lines = ['La matrice de conformité : chaque contrôle et chaque exigence non fonctionnelle, reçus du socle ou propres au projet, face',
             'aux blocs de construction qui les implémentent. Une ligne sans implémentation est un manque à combler avant de construire.', '']
    unit_names = [u['meta']['name'] for u in units]
    header = ['Exigence ou contrôle', 'Nature', 'Origine', 'État'] + [n.replace(' build', '').replace(' service', '') for n in unit_names] + ['Autres implémentations', 'Vérification']
    body = []
    for r in rows:
        impl = {name for kind, name in r['implementers'] if kind == 'ConstructionUnit'}
        others = ', '.join(name for kind, name in r['implementers'] if kind != 'ConstructionUnit') or '-'
        body.append([r['name'], 'Contrôle' if r['kind'] == 'Control' else 'ENF', r['namespace'], r['status']] + ['●' if n in impl else '' for n in unit_names]
                    + [others, ', '.join(r['verification']) or '-'])
    lines += table(header, body) + ['']
    crossed = [(r, ns, to) for r in rows for ns, to in r['delegated'].items()]
    technical = [(r, ns, o) for r in rows for ns, o in r['ownership'].items() if o['scope'] == 'TECHNICAL']
    lines += ['## Portée : bloc métier ou composant technique', '',
              'Une exigence portée par un bloc ou une unité l’est comme comportement ; portée seulement par des composants, équipements,',
              'connexions ou zones, elle l’est comme infrastructure et demande un rôle responsable nommé.', '']
    lines += table(['Exigence ou contrôle', 'Projet', 'Portée', 'Responsable'],
                   [[r['name'], ns, {'BUSINESS': 'bloc métier', 'TECHNICAL': 'composant technique', 'BOTH': 'les deux', 'NONE': '-'}[o['scope']],
                     ', '.join(o['accountable']) or ('**aucun responsable nommé**' if o['scope'] == 'TECHNICAL' else '-')]
                    for r in rows for ns, o in r['ownership'].items()]) + ['']
    lines += ['Portées seulement par l’infrastructure : ' + str(len(technical)) + ', dont ' + str(sum(1 for _, _, o in technical if not o['accountable']))
              + ' sans responsable nommé.', '']
    lines += ['## Responsabilités croisées', '', 'Un projet peut déclarer une exigence sans objet chez lui, par une décision : elle doit alors être implémentée par un autre projet.', '']
    lines += table(['Exigence ou contrôle', 'Sans objet dans', 'Implémentée par'],
                   [[r['name'], ns, (', '.join(to) + ('' if r['delegation_confirmed'] else ' (déclaré, non vérifié dans ces baselines)')) if to else '**aucun projet - manque**']
                    for r, ns, to in crossed]) if crossed else ['Aucune.']
    lines += ['']
    missing = [r for r in rows if r['status'] == 'UNMAPPED' or any(not to for to in r['delegated'].values())]
    lines += ['## Non couverts', ''] + (['- ' + r['name'] + ' (' + r['namespace'] + ')' for r in missing] if missing else ['Chaque contrôle et chaque exigence a une implémentation déclarée.'])
    from air import journey_catalog
    coverage = journey_catalog.project(g)
    lines += ['', '## Checklist documentaire des parcours et usages', '',
              'Ces contrôles de couverture du dossier ne certifient pas la conformité réglementaire, une recherche UX ou une réception terrain.', '']
    lines += table(['Contrôle', 'État', 'Lacunes'], [[c['label'], c['status'], str(c['gap_count'])] for c in coverage['checks']])
    return 'Matrice de conformité', lines, [r['subject'] for r in rows] + g.of('ComplianceMapping') + g.of('JourneyCatalog') + g.of('CustomerJourney') + g.of('Touchpoint') + g.of('UsagePoint')


def d_nfr(g):
    from air.delivery_calc import compliance
    status = {r['subject']['meta']['id']: r for r in compliance(list(g.by_id.values()), g.by_id)}
    nfrs = g.of('QualityRequirement')
    def target(b):
        if 'target' not in b: return '-'
        tg = b['target'];v = tg['value'].get('value', tg['value'].get('state', '?'))
        return {'EQ': '=', 'LTE': '≤', 'GTE': '≥'}[tg['operator']] + ' ' + str(v) + ' ' + tg['unit']
    lines = ['Les exigences non fonctionnelles reçues en entrée et leur prise en compte : cible mesurable, méthode de vérification,',
             'blocs qui les implémentent.', '']
    lines += table(['Catégorie', 'Exigence', 'Cible', 'Priorité', 'Source', 'Vérification', 'Implémentée par', 'État'],
                   [[q['body']['category'], q['body']['statement'], target(q['body']), q['body']['priority'], q['body'].get('source', '-'), q['body']['verification_method'],
                     ', '.join(n for _, n in status.get(q['meta']['id'], {}).get('implementers', [])) or '-', status.get(q['meta']['id'], {}).get('status', 'UNMAPPED')]
                    for q in sorted(nfrs, key=lambda q: (q['body']['category'], q['meta']['name']))])
    project = [r for r in g.of('Requirement') if r['body']['kind'] in ('QUALITY', 'CONSTRAINT')]
    lines += ['', '## Exigences qualité et contraintes des projets', ''] + table(['Exigence', 'Nature', 'Priorité', 'Énoncé'],
        [[r['meta']['name'], r['body']['kind'], r['body']['priority'], r['body']['statement']] for r in project])
    return 'Exigences non fonctionnelles', lines, nfrs + project


def d_ai_estimate(g):
    from air.delivery_calc import estimates, single_currency
    rows = estimates(list(g.by_id.values()), g.by_id)
    lines = ['L’effort de construction sans IA et avec un IDE agentique, là où l’IA s’applique : gain de temps par activité et par unité,',
             'durée, et coût des abonnements des personnes qui construisent. Les réductions sont des hypothèses de planification à',
             'calibrer sur les premières itérations.', '']
    if not rows: return 'Estimation avec et sans IA', lines + ['_Aucune estimation avec IA déclarée._'], []
    cur = single_currency(r['currency'] for r in rows) or ''
    table_rows = [[r['unit'], _fmt(r['without_ai_pd']), _fmt(r['with_ai_pd']), '%s (%s %%)' % (_fmt(r['delta_pd']), _fmt(r['delta_ratio'] * 100)),
                   _fmt(r['months_without_ai'], 1), _fmt(r['months_with_ai'], 1), r['workers'], r['ai_seats'], _fmt(r['subscription']) + ' ' + (r['currency'] or cur), r['confidence']]
                  for r in rows]
    tot = lambda k: sum(r[k] for r in rows)
    without, with_ai = tot('without_ai_pd'), tot('with_ai_pd')
    table_rows.append(['**Total**', '**' + _fmt(without) + '**', '**' + _fmt(with_ai) + '**', '**%s (%s %%)**' % (_fmt(without - with_ai), _fmt((without - with_ai) / without * 100 if without else 0)),
                       '', '', '', '', '**' + _fmt(tot('subscription')) + ' ' + cur + '**', ''])
    lines += table(['Unité', 'Sans IA (j.h)', 'Avec IA (j.h)', 'Gain (j.h, %)', 'Durée sans IA (mois)', 'Durée avec IA (mois)', 'Équipe', 'Sièges IA', 'Abonnements IA', 'Confiance'], table_rows) + ['']
    names = [r['unit'].replace(' service build', '').replace(' build', '')[:18] for r in rows]
    top = int(max(float(r['without_ai_pd']) for r in rows) * 1.15) + 1
    lines += ['## Effort par unité, sans IA puis avec IA', ''] + mermaid(['xychart-beta', '  title "Effort par unité (j.h) - sans IA puis avec IA"',
        '  x-axis [' + ', '.join('"' + n.replace('"', "'") + '"' for n in names) + ']', '  y-axis "jours-homme" 0 --> ' + str(top),
        '  bar [' + ', '.join(str(float(r['without_ai_pd'])) for r in rows) + ']', '  bar [' + ', '.join(str(float(r['with_ai_pd'])) for r in rows) + ']']) + ['']
    by_activity = defaultdict(lambda: [Decimal(0), Decimal(0), False])
    for r in rows:
        for a in r['activities']:
            x = by_activity[a['activity']];x[0] += Decimal(a['effort_pd']);x[1] += Decimal(a['ai_effort_pd'] if a['ai_applicable'] else a['effort_pd']);x[2] = x[2] or a['ai_applicable']
    lines += ['## Gain par activité', ''] + table(['Activité', 'Sans IA (j.h)', 'Avec IA (j.h)', 'Gain', 'IA applicable'],
        [[k, _fmt(v[0]), _fmt(v[1]), _fmt((v[0] - v[1]) / v[0] * 100 if v[0] else 0) + ' %', 'oui' if v[2] else 'non'] for k, v in sorted(by_activity.items())]) + ['']
    plans = g.of('AgenticToolPlan')
    lines += ['## Plans d’IDE agentique', ''] + table(['Plan', 'Éditeur', 'Prix', 'Politique de données', 'Statut'],
        [[p['body']['product'] + ' - ' + p['body']['plan'], p['body']['vendor'], p['body']['price']['value'] + ' ' + p['body']['price']['currency'] + ' / siège / mois',
          p['body']['data_policy'], p['body']['status']] for p in plans]) + ['']
    lines += ['## Hypothèses', ''] + ['- ' + r['unit'] + ' : ' + r['basis'] for r in rows]
    return 'Estimation avec et sans IA', lines, [r['estimate'] for r in rows] + plans


def d_roadmaps(g):
    from air.delivery_calc import chosen_by_project, estimates, roadmaps
    rows = roadmaps(list(g.by_id.values()), g.by_id, estimates(list(g.by_id.values()), g.by_id))
    lines = ['Les feuilles de route possibles de chaque projet, comparées sur le calendrier, le chemin critique, l’effort, le coût et le recours',
             'à l’IA, par rapport à la feuille de route de référence sans IA ; puis la recommandation et la décision qui la retient.', '']
    if not rows: return 'Feuilles de route et alternatives', lines + ['_Aucune feuille de route déclarée._'], []
    chosen = chosen_by_project(rows);money = lambda v, r: (_fmt(v) + ' ' + (r['currency'] or '')) if v is not None else '-'
    from air.delivery_calc import programme
    prog = programme(rows)
    lines += ['## Programme', '']
    lines += table(['Projet', 'Feuille de route', 'Statut', 'Début', 'Fin', 'Durée (mois)', 'Coût total'],
                   [[ns, r['name'], r['status'], r['start'], r['end'], _fmt(r['months'], 1), money(r['total_cost'], r)] for ns, r in sorted(chosen.items())]
                   + [[ns, '_à choisir_', '-', '-', '-', '-', '-'] for ns in sorted({r['namespace'] for r in rows} - set(chosen))]) + ['']
    kind_fr = {'FINISH_TO_START': 'fin → début', 'START_TO_START': 'début → début', 'FINISH_TO_FINISH': 'fin → fin'}
    lines += ['### Dépendances entre projets', '']
    lines += table(['Projet', 'Phase', 'Attend', 'Type', 'Dates tenues', 'Feuille de route retenue'],
                   [[d['from_namespace'], d['phase_name'], '%s · %s · %s (%s → %s)' % (d['namespace'] or '?', d['roadmap_name'], d['target_name'] or d['target_phase'],
                                                                                     d['target_start'] or '?', d['target_end'] or '?'),
                     kind_fr[d['kind']], 'oui' if d['satisfied'] else '**non**' if d['satisfied'] is False else '**phase absente**',
                     'oui' if d['target_chosen'] else '**non**'] for d in prog['dependencies']]) if prog['dependencies'] else ['_Aucune dépendance déclarée entre projets._']
    lines += ['']
    if prog['critical_path']:
        lines += ['**Chemin critique du programme** : ' + ' → '.join('%s · %s' % (c['namespace'], c['name']) for c in prog['critical_path'])
                  + ' ; fin le ' + prog['end'] + '.', '']
    for i in prog['issues']:
        lines += ['- **' + {'DATES': 'Dates incompatibles', 'NOT_THE_CHOSEN_ROADMAP': 'Dépend d’une feuille de route non retenue', 'PHASE_UNKNOWN': 'Phase inconnue'}[i['code']]
                  + '** : ' + i['from_namespace'] + ' · ' + i['phase_name'] + ' attend ' + (i['namespace'] or '?') + ' · ' + i['roadmap_name'] + ' · ' + i['target_phase'] + '.']
    if prog['issues']: lines += ['']
    for ns in sorted({r['namespace'] for r in rows}):
        mine = [r for r in rows if r['namespace'] == ns]
        lines += ['## Projet ' + ns, '']
        lines += table(['Feuille de route', 'IA', 'Début', 'Fin', 'Durée (mois)', 'Écart de durée', 'Chemin critique', 'Effort (j.h)', 'Main-d’œuvre', 'Abonnements IA', 'Coût total', 'Écart de coût', 'Équipe max', 'Statut'],
                       [[r['name'], 'oui' if r['uses_ai'] else 'non', r['start'], r['end'], _fmt(r['months'], 1),
                         (_fmt(r['delta_months'], 1) + ' mois') if r['delta_months'] is not None else 'référence', ' → '.join(r['critical_path']),
                         _fmt(r['effort_pd']), money(r['labour_cost'], r), money(r['subscription'], r), money(r['total_cost'], r),
                         money(r['delta_cost'], r) if r['delta_cost'] is not None else 'référence', r['peak_team'], r['status']] for r in mine]) + ['']
        if ns in chosen:
            r = chosen[ns]
            lines += ['**' + ('Retenue' if r['status'] == 'SELECTED' else 'Recommandée') + ' : ' + r['name'] + '.** ' + r['rationale'], '']
            if r['roadmap']['body'].get('decision'): lines += ['Décision : ' + g.name(r['roadmap']['body']['decision']) + '.', '']
        else:
            lines += ['_Aucune feuille de route recommandée ni retenue pour ce projet._', '']
        for r in mine:
            diagram = ['gantt', '  dateFormat YYYY-MM-DD', '  title ' + r['name'].replace(':', ' ')]
            for ph in r['phases']:
                tag = 'crit, ' if ph['id'] in r['critical_path'] else ''
                diagram += ['  section ' + ph['name'][:40].replace(':', ' '), '  ' + ph['objective'][:50].replace(':', ' ').replace('#', '') + ' : ' + tag + mid(r['name'] + ph['id']) + ', ' + ph['start'] + ', ' + ph['end']]
            lines += ['### ' + r['name'] + ' - ' + r['status'], '', r['strategy'], ''] + mermaid(diagram) + ['']
            lines += table(['Phase', 'Objectif', 'Du', 'Au', 'Équipe', 'Unités', 'Dépend de', 'Critères de sortie'],
                           [[ph['name'], ph['objective'], ph['start'], ph['end'], ph['team_size'], ', '.join(g.name(u) for u in ph.get('units', [])) or '-',
                             ', '.join(ph.get('depends_on', [])) or '-', '; '.join(ph.get('exit_criteria', [])) or '-'] for ph in r['phases']]) + ['']
    return 'Feuilles de route et alternatives', lines, [r['roadmap'] for r in rows]


DECK = '00-presentation-direction'
CATALOGUE = [
    ('01-graphe-dossier', d_graph), ('02-chaine-de-valeur', d_value_stream), ('03-parcours-clients', d_journeys), ('04-processus-metier', d_processes),
    ('05-roles', d_roles), ('06-organisation-realisation-raci', 'delivery_org'), ('07-organisation-exploitation', 'operations_org'),
    ('08-architectures-systeme', d_system), ('09-sequences', d_sequences), ('10-etats', d_states), ('11-arbres-de-decision', d_decisions),
    ('12-hypotheses', d_hypotheses), ('13-tracabilite', d_traceability), ('14-carte-capacites', d_capabilities), ('15-analyse-ecarts', 'gaps'),
    ('16-risques', d_risks), ('17-plan-financier', d_finance), ('18-ontologie', d_ontology), ('19-modele-logique', d_logical),
    ('20-modele-physique', d_physical), ('21-infrastructure-reseau', d_infrastructure), ('22-securite-zones', 'security'),
    ('23-objectifs-strategiques', d_goals), ('24-principes', d_principles), ('25-adr', d_adr), ('26-registre-technologies', d_technologies),
    ('27-planning-jalons', d_planning), ('28-preparation-construction', 'readiness'),
    ('29-evenements', d_events), ('30-navigation-interfaces', d_navigation), ('31-equipements-machines', d_devices),
    ('32-scenarios-acceptation', d_scenarios), ('33-tests-non-regression', d_regression), ('34-matrice-conformite', d_compliance),
    ('35-exigences-non-fonctionnelles', d_nfr), ('36-estimation-ia', d_ai_estimate), ('37-feuilles-de-route', d_roadmaps),
]


def build_topics(g, gates, request):
    topics = []
    for name, builder in CATALOGUE:
        if request.get('only') and name not in request['only']: continue
        if builder == 'delivery_org': title, lines, used = d_delivery_org(g, request.get('implementation_root'))
        elif builder == 'operations_org': title, lines, used = d_operations_org(g, request.get('operations_root'))
        elif builder == 'gaps': title, lines, used = d_gaps(g, gates)
        elif builder == 'security': title, lines, used = d_security(g, gates)
        elif builder == 'readiness': title, lines, used = d_readiness(g, gates)
        else: title, lines, used = builder(g)
        topics.append({'name': name, 'title': title, 'lines': lines, 'used': used})
    return topics


def compile_deliverables(store, principal, policy, request):
    check_schema(request, REQUEST)
    if request.get('comparisons') and (request.get('only') or not request.get('website', True)):
        raise InvalidModel('Explicit comparisons require the complete static website')
    guarded = ScopedStore(store, principal, policy)
    exports = [snapshot(guarded, ref) for ref in request['baselines']]
    if sum(len(e['objects']) for e in exports) > 20000: raise InvalidModel('Deliverables context exceeds 20,000 objects; pin fewer baselines')
    from air.readiness import assess_readiness
    gates = [assess_readiness(store, principal, policy, {'baseline': ref}) for ref in request['baselines']]
    g = Graph(exports)
    directory = request.get('directory', 'livrables')
    pins = ['- `' + ref['id'] + '` révision ' + str(ref['revision']) + ' - `' + ref['digest'] + '`' for ref in request['baselines']]
    header = lambda title: ['# ' + title, '', '_' + request['title'] + ' - compilé par ' + ENGINE + ' depuis les baselines épinglées ; ne pas modifier à la main._', '']
    files, index_rows = [], []
    from air import management_summary
    known = {name for name, _ in CATALOGUE} | {DECK, management_summary.NAME}
    unknown = sorted(set(request.get('only', [])) - known)
    if unknown: raise InvalidModel('Unknown deliverable: ' + ', '.join(unknown) + '. Known: ' + ', '.join(sorted(known)))
    if not request.get('only') or management_summary.NAME in request['only']:
        summaries = [management_summary.project(e, gate) for e, gate in zip(exports, gates)]
        files.append(product(directory + '/' + management_summary.NAME + '.md', 'text/markdown', render_text(header('Management Summary') + [line for view in summaries for line in management_summary.lines(view)]), 'GENERATED', FILE_MAX))
        files.append(product(directory + '/' + management_summary.NAME + '.json', 'application/json', render_json({'engine': management_summary.ENGINE, 'dossiers': summaries, 'revision_policy': 'SEPARATE_EXACT_BASELINES'}), 'GENERATED', FILE_MAX))
        index_rows.append(['[Management Summary](' + management_summary.NAME + '.md)', 'chaque baseline exacte séparément'])
    for topic in build_topics(g, gates, request):
        name, title, lines, used = (topic[k] for k in ('name', 'title', 'lines', 'used'))
        content = render_text(header(title) + lines + [''] + src(used))
        files.append(product(directory + '/' + name + '.md', 'text/markdown', content, 'GENERATED', FILE_MAX))
        index_rows.append(['[' + title + '](' + name + '.md)', len({o['meta']['id'] for o in used}) or 'aucun - manque'])
    website = not request.get('only') and request.get('website', True)
    if 'branding' in request and not website:
        raise InvalidModel('Branding requires the full static website; remove only or enable website')
    site_manifest = None
    if not request.get('only') or any(n[:2] in ('18', '19', '20') for n in request['only']):
        from air.model_export import export_model
        import json
        model = export_model(store, principal, policy, exports)
        files.append(product(directory + '/architecture-model.json', 'application/json', json.dumps(model, ensure_ascii=False, separators=(',', ':')) + '\n', 'GENERATED', TOTAL_MAX))
    if website:
        from air.architecture_site import compile_site
        from air.branding import selection as select_branding
        brands = select_branding(request, request['baselines'], store, principal, policy)
        from air.interface_contracts import compile_members
        from air import completeness
        suites = {e['digest']: compile_members(store, principal, policy, e, 'FULL') for e in exports}
        contexts = {e['digest']: completeness.apply_exclusion_reviews(store, principal, policy,
            completeness.attach_interfaces(completeness.project(e), suites[e['digest']])) for e in exports}
        from air import builder_handoff
        receipts = {e['digest']: builder_handoff.assess(store, principal, policy, {'baseline': ref})
            for e, ref in zip(exports, request['baselines'])}
        from air import evidence_impact
        evidence_reports = {e['digest']: evidence_impact.for_site(store, principal, policy, e) for e in exports}
        site_files, site_manifest = compile_site(exports, gates, request, lambda graph, local_gates: build_topics(graph, local_gates, request), render_json(model), brands, suites, contexts, receipts, evidence_reports)
        files.extend(site_files)
    warnings = (['## Révisions divergentes dans la synthèse', '',
        'Les documents Markdown de synthèse regroupent les objets par identifiant et retiennent la plus haute révision. Ils ne sont pas une comparaison existant/cible.',
        'Le site et architecture-model.json conservent séparément chaque dossier exact. Divergences :', ''] +
        ['- `' + c['id'] + '` : révisions ' + ', '.join(map(str, c['revisions'])) for c in g.revision_conflicts] + ['']) if g.revision_conflicts else []
    readme = render_text(header(request['title']) + ([
        '**[Ouvrir le site des dossiers d’architecture](site/index.html)** - navigation par sujet, diagrammes et objets exacts.', '',
    ] if website else []) + ['**[Commencer par le Management Summary](00-management-summary.md)** - décisions, financement, risques et prochaines conditions.', ''] + warnings + [
        'Dossier de livrables de l’équipe de réalisation, dérivé du graphe d’architecture AIR. Chaque document cite ses objets exacts ;',
        'un document vide signale ce qui manque au dossier. Les diagrammes sont en Mermaid.', '', '## Baselines épinglées', '', *pins, '',
        '## Portes « prêt à construire »', '', *['- ' + gate['namespace'] + ' : **' + gate['result'] + '**' + (' - bloquants : ' + ', '.join(gate['blocking']) if gate['blocking'] else '') for gate in gates], '',
        '## Livrables', '', *table(['Livrable', 'Objets sources'], index_rows), '',
        '## Ce que ce dossier n’est pas', '',
        '- Une preuve de comportement réel : les qualifications indépendantes portent sur la conception ou le modèle ; elles n’attestent aucun test du système exécuté.',
        '- Une approbation, une signature ou une admission : ce sont des actes humains authentifiés distincts.',
        '- Un document juridique : son usage contractuel relève d’un conseil juridique.'])
    if not request.get('only') or DECK in request['only']:
        from air.presentation import build
        deck_request = {k: request[k] for k in ('title', 'title_en', 'client', 'provider', 'projects', 'baselines') if k in request}
        from air.presentation import REQUEST as DECK_REQUEST
        check_schema(deck_request, DECK_REQUEST)
        slides, deck = build(g, gates, deck_request)
        files.append(product(directory + '/' + DECK + '.html', 'text/html', deck, 'GENERATED', FILE_MAX))
        index_rows.insert(0, ['[Présentation de direction (' + str(len(slides)) + ' planches)](' + DECK + '.html)', 'toutes les baselines épinglées'])
    if not request.get('only'): files.append(product(directory + '/README.md', 'text/markdown', readme, 'GENERATED', FILE_MAX))
    manifest = {'engine': ENGINE, 'title': request['title'], 'baselines': request['baselines'], 'gates': [{'namespace': x['namespace'], 'result': x['result'], 'blocking': x['blocking']} for x in gates],
                'deliverables': [name for name, _ in CATALOGUE], 'generator_version': TOOLCHAIN['air_version'],
                'website': site_manifest, 'projection_conflicts': g.revision_conflicts,
                # what this generation wrote: a later run replaces these files unless they were edited by hand
                'files': [{'path': f['path'], 'content_digest': f['content_digest']} for f in sorted(files, key=lambda f: f['path'])]}
    if not request.get('only'): files.append(product(directory + '/manifest.json', 'application/json', render_json(manifest), 'GENERATED', FILE_MAX))
    # This fixed third-party source cannot contain a generated identity token.
    # Its hash is verified below; token-shaped library symbols are not credentials.
    vendor_path = directory + '/site/assets/mermaid-12.1.0.js'
    for f in files:
        if f['path'] == vendor_path:
            from importlib import resources
            import json
            expected = json.loads(resources.files('air').joinpath('assets/mermaid-provenance.json').read_text(encoding='utf-8'))['sha256']
            if f['content_digest'] != 'sha256:' + expected: raise InvalidModel('Offline diagram renderer integrity differs')
    no_secret([f for f in files if f['path'] != vendor_path])
    ordered, total, file_set_digest = collate(files, request.get('max_total_bytes', TOTAL_MAX))
    if request.get('content') == 'DIGESTS': ordered = [{k: v for k, v in item.items() if k != 'content'} for item in ordered]
    report = {'engine': ENGINE, 'title': request['title'], 'baselines': request['baselines'], 'files': ordered, 'file_set_digest': file_set_digest,
              'total_size': total, 'gates': manifest['gates'], 'deliverables': len(CATALOGUE), 'registry_written': False, 'authorization_granted': False,
              'generator': TOOLCHAIN, 'request_digest': artifact_digest(request), 'website': site_manifest,
              'projection_conflicts': g.revision_conflicts}
    report['report_digest'] = artifact_digest(report)
    return report
