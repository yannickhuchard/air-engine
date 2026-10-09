"""Descriptive BPMN 2.0 with deterministic lanes and preserved AIR witnesses.

The exported process is not executable. AIR expressions are documentary guard
text, not an expression language supported by a third-party BPMN engine.
"""
from collections import defaultdict, deque
from html import escape
import json
from xml.etree import ElementTree as ET
from air.core import digest
from air.foundation import exact
from air.expr import artifact_digest
from air.editorial import prose
from air.deliverables import mid, expression_text

ENGINE = 'air.process-diagrams/1'
NS = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL', 'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
      'dc': 'http://www.omg.org/spec/DD/20100524/DC', 'di': 'http://www.omg.org/spec/DD/20100524/DI',
      'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
for prefix, uri in NS.items(): ET.register_namespace(prefix, uri)
def h(v): return escape(prose(str(v)), quote=True)
def anchor(pin): return mid(pin['id'] + ':' + str(pin['revision']))
def sub(parent, tag, **attributes):
    prefix, name = tag.split(':'); return ET.SubElement(parent, '{' + NS[prefix] + '}' + name, {k: str(v) for k, v in attributes.items()})


def ranks(ids, flows):
    """Iterative SCC condensation, then longest-path layers; cycles are retained."""
    adj = {k: [] for k in ids}; reverse = {k: [] for k in ids}
    for f in flows: adj[f['source']].append(f['target']); reverse[f['target']].append(f['source'])
    seen = set(); finish = []
    for root in sorted(ids):
        if root in seen: continue
        stack = [(root, False)]
        while stack:
            node, closing = stack.pop()
            if closing: finish.append(node); continue
            if node in seen: continue
            seen.add(node); stack.append((node, True)); stack.extend((k, False) for k in sorted(adj[node], reverse=True) if k not in seen)
    components = []; owner = {}
    for root in reversed(finish):
        if root in owner: continue
        members = []; stack = [root]; index = len(components)
        while stack:
            node = stack.pop()
            if node in owner: continue
            owner[node] = index; members.append(node); stack.extend(reverse[node])
        components.append(sorted(members))
    edges = {i: set() for i in range(len(components))}; incoming = defaultdict(int)
    for f in flows:
        a, b = owner[f['source']], owner[f['target']]
        if a != b and b not in edges[a]: edges[a].add(b); incoming[b] += 1
    queue = deque(sorted(i for i in edges if not incoming[i])); level = defaultdict(int)
    while queue:
        here = queue.popleft()
        for nxt in sorted(edges[here]):
            level[nxt] = max(level[nxt], level[here] + len(components[here])); incoming[nxt] -= 1
            if not incoming[nxt]: queue.append(nxt)
    return {node: level[i] + n for i, component in enumerate(components) for n, node in enumerate(component)}, [c for c in components if len(c) > 1 or c[0] in adj[c[0]]]


def project(g, workflow):
    body = workflow['body']; witness = {**exact(workflow), 'digest': digest(workflow)}; uid = anchor(witness)
    steps = sorted(body['steps'], key=lambda s: s['id']); flows = sorted(body['flows'], key=lambda f: f['id'])
    levels, cycles = ranks([s['id'] for s in steps], flows)
    groups = defaultdict(list)
    for s in steps:
        group = tuple(sorted((r['id'], r['revision']) for r in s['participants'])); groups[group].append(s)
    lanes = []; nodes = []; incoming = defaultdict(list); outgoing = defaultdict(list)
    for f in flows: outgoing[f['source']].append(f); incoming[f['target']].append(f)
    maxcol = max(levels.values(), default=0); width = 720 + (maxcol + 1) * 420; lane_y = 75; by_step = {}; endpoints = {}
    for li, (group, members) in enumerate(sorted(groups.items())):
        names = [g.name({'id': name, 'revision': rev}) for name, rev in group]
        used = defaultdict(int); slots = {}
        for s in sorted(members, key=lambda s: (levels[s['id']], s['id'])):
            col = levels[s['id']]; slots[s['id']] = used[col]; used[col] += 1
        height = max(220, max(used.values(), default=1) * 160 + 60)
        lane = {'id': uid + '_lane_' + str(li), 'name': ' / '.join(names) or 'Participants à préciser', 'participants': [{'id': a, 'revision': b} for a, b in group], 'x': 40, 'y': lane_y, 'width': width-70, 'height': height, 'nodes': []}
        lanes.append(lane)
        for s in members:
            sid = uid + '_' + mid(s['id']); x = 300 + levels[s['id']] * 420; y = lane_y + 55 + slots[s['id']] * 160
            task = {'id': sid, 'kind': 'task', 'name': prose(s['name']), 'x': x, 'y': y, 'width': 200, 'height': 85, 'step': s['id'], 'function': s['function'], 'source': witness, 'selector': '/body/steps/' + str(body['steps'].index(s)), 'lane': lane['id']}
            nodes.append(task); lane['nodes'].append(sid); by_step[s['id']] = task; first = last = sid
            if len(incoming[s['id']]) > 1:
                kind = 'parallelGateway' if s.get('join', 'ANY') == 'ALL' else 'exclusiveGateway'
                join = {**task, 'id': sid + '_join', 'kind': kind, 'name': 'Tous reçus' if kind == 'parallelGateway' else 'Arrivée', 'direction': 'Converging', 'x': x-70, 'y': y+20, 'width': 45, 'height': 45}
                nodes.append(join); lane['nodes'].append(join['id']); first = join['id']
            if len(outgoing[s['id']]) > 1:
                split = {**task, 'id': sid + '_split', 'kind': 'inclusiveGateway', 'name': 'Flux admissibles', 'direction': 'Diverging', 'x': x+230, 'y': y+20, 'width': 45, 'height': 45}
                nodes.append(split); lane['nodes'].append(split['id']); last = split['id']
            endpoints[s['id']] = (first, last)
        lane_y += height
    edges = []; node_index = {n['id']: n for n in nodes}
    def connect(identity, source, target, name='', selector='', guard=None):
        a, b = node_index[source], node_index[target]; sy = a['y'] + a['height']/2; ty = b['y'] + b['height']/2
        sx = a['x']+a['width']; tx = b['x']; returning = tx <= sx
        if returning:
            corridor = lane_y + 40 + sum(e['returning'] for e in edges) * 55
            points = [[sx,sy],[sx+18,sy],[sx+18,corridor],[tx-18,corridor],[tx-18,ty],[tx,ty]]; lx = (sx+tx)/2; ly = corridor-38
        else:
            offset = 16 + len(outgoing.get(a.get('step'), [])) * 3
            mx = sx + min((tx-sx)/2, offset + 30)
            points = [[sx,sy],[mx,sy],[mx,ty],[tx,ty]] if sy != ty else [[sx,sy],[tx,ty]]; lx = (sx+tx)/2; ly = min(sy,ty)-45
        edge = {'id': identity, 'source': source, 'target': target, 'name': prose(name), 'waypoints': points, 'label': {'x': lx-65, 'y': ly, 'width': 130, 'height': 38}, 'returning': returning, 'witness': witness, 'selector': selector}
        if guard is not None: edge['air_guard'] = guard
        edges.append(edge)
    for step in steps:
        task = by_step[step['id']]; first, last = endpoints[step['id']]
        if first != task['id']: connect(task['id']+'_joined',first,task['id'])
        if last != task['id']: connect(task['id']+'_split_flow',task['id'],last)
    for i, flow in enumerate(flows):
        connect(uid+'_flow_'+mid(flow['id']), endpoints[flow['source']][1], endpoints[flow['target']][0],
            expression_text(flow['guard']['ast']) if 'guard' in flow else flow['condition'], '/body/flows/' + str(body['flows'].index(flow)), flow.get('guard'))
    for step in steps:
        task = by_step[step['id']]; lane = next(l for l in lanes if l['id'] == task['lane'])
        if step['id'] in body['start_steps']:
            n = {**task, 'id': task['id']+'_start', 'kind': 'startEvent', 'name': 'Début', 'x': task['x']-145, 'y': task['y']+25, 'width': 36, 'height': 36}
            nodes.append(n); node_index[n['id']] = n; lane['nodes'].append(n['id']); connect(n['id']+'_flow',n['id'],endpoints[step['id']][0])
        if not outgoing[step['id']]:
            n = {**task, 'id': task['id']+'_end', 'kind': 'endEvent', 'name': 'Fin', 'x': task['x']+300, 'y': task['y']+25, 'width': 36, 'height': 36}
            nodes.append(n); node_index[n['id']] = n; lane['nodes'].append(n['id']); connect(n['id']+'_flow',task['id'],n['id'])
    height = max([lane_y+80] + [p[1]+70 for e in edges for p in e['waypoints']])
    value = {'engine': ENGINE, 'reference': witness, 'name': workflow['meta']['name'], 'description': workflow['meta']['description'],
        'lanes': lanes, 'nodes': nodes, 'edges': edges, 'width': width, 'height': height, 'cycles': cycles,
        'termination_policy': body['termination_policy'], 'compensations': body['compensations'], 'executable': False,
        'semantics': 'DESCRIPTIVE_BPMN_SUBSET_NOT_ENGINE_EQUIVALENCE', 'layout': 'SCC_LONGEST_PATH_LANES',
        'steps': [{**s, 'function_name': g.name(s['function']), 'participant_names': [g.name(r) for r in s['participants']]} for s in steps]}
    return {**value, 'projection_digest': artifact_digest(value)}


def bpmn(view):
    uid = anchor(view['reference']); root = ET.Element('{' + NS['bpmn'] + '}definitions', {'id': uid+'_definitions', 'targetNamespace': 'urn:air:descriptive-bpmn', 'exporter': 'AIR', 'exporterVersion': ENGINE})
    process = sub(root, 'bpmn:process', id=uid+'_process', name=prose(view['name']), isExecutable='false')
    sub(process, 'bpmn:documentation').text = json.dumps({'source': view['reference'], 'semantics': view['semantics'], 'termination_policy': prose(view['termination_policy']), 'compensations': view['compensations']}, ensure_ascii=False)
    lanes = sub(process, 'bpmn:laneSet', id=uid+'_lanes')
    for lane in view['lanes']:
        node = sub(lanes, 'bpmn:lane', id=lane['id'], name=prose(lane['name']))
        for ref in lane['nodes']: sub(node, 'bpmn:flowNodeRef').text = ref
    for n in view['nodes']:
        attrs = {'id': n['id'], 'name': prose(n['name'])}
        if 'direction' in n: attrs['gatewayDirection'] = n['direction']
        node = sub(process, 'bpmn:'+n['kind'], **attrs)
        sub(node, 'bpmn:documentation').text = json.dumps({'source': n['source'], 'selector': n['selector'], 'function': n['function']})
        for edge in view['edges']:
            if edge['target'] == n['id']: sub(node, 'bpmn:incoming').text = edge['id']
        for edge in view['edges']:
            if edge['source'] == n['id']: sub(node, 'bpmn:outgoing').text = edge['id']
    for e in view['edges']:
        node = sub(process, 'bpmn:sequenceFlow', id=e['id'], sourceRef=e['source'], targetRef=e['target'], name=e['name'])
        sub(node, 'bpmn:documentation').text = json.dumps({'witness': e['witness'], 'selector': e['selector'], 'air_guard': e.get('air_guard'), 'not_executable': True}, ensure_ascii=False)
    plane = sub(sub(root, 'bpmndi:BPMNDiagram', id=uid+'_diagram'), 'bpmndi:BPMNPlane', id=uid+'_plane', bpmnElement=uid+'_process')
    for n in [*view['lanes'], *view['nodes']]:
        shape = sub(plane, 'bpmndi:BPMNShape', id=n['id']+'_di', bpmnElement=n['id'], **({'isHorizontal':'true'} if n in view['lanes'] else {}))
        sub(shape, 'dc:Bounds', **{k:n[k] for k in ('x','y','width','height')})
    for e in view['edges']:
        edge = sub(plane, 'bpmndi:BPMNEdge', id=e['id']+'_di', bpmnElement=e['id'])
        for x,y in e['waypoints']: sub(edge,'di:waypoint',x=x,y=y)
        if e['name']: sub(sub(edge,'bpmndi:BPMNLabel'),'dc:Bounds',**e['label'])
    return ET.tostring(root, encoding='unicode', xml_declaration=True) + '\n'


def fallback(view):
    """Full readable layout on disk, without JavaScript or a renderer."""
    uid = anchor(view['reference']); out = f'<div class="process-fallback table-wrap" tabindex="0" role="region" aria-label="Processus complet, faire défiler horizontalement"><svg viewBox="0 0 {view["width"]} {view["height"]}" style="width:{view["width"]}px" role="img" aria-label="Processus en couloirs de participation"><title>' + h(view['name']) + f'</title><defs><marker id="{uid}-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#405a70"/></marker></defs>'
    for lane in view['lanes']:
        out += f'<rect x="{lane["x"]}" y="{lane["y"]}" width="{lane["width"]}" height="{lane["height"]}" class="process-lane"/><text x="60" y="{lane["y"]+27}">' + h(lane['name']) + '</text>'
    for e in view['edges']:
        out += '<polyline points="' + ' '.join(str(x)+','+str(y) for x,y in e['waypoints']) + f'" class="process-edge" marker-end="url(#{uid}-arrow)"><title>' + h(e['name']) + '</title></polyline>'
        if e['name']:
            import textwrap
            label = prose(e['name']); short = label[:65] + ('…' if len(label) > 65 else '')
            out += '<text class="process-edge-label" x="' + str(e['label']['x']) + '" y="' + str(e['label']['y']+12) + '"><title>' + h(label) + '</title>'
            for i, line in enumerate(textwrap.wrap(short, 24)):
                out += '<tspan x="' + str(e['label']['x']) + '" dy="' + ('0' if i == 0 else '14') + '">' + h(line) + '</tspan>'
            out += '</text>'
    for n in view['nodes']:
        x,y,w,height = (n[k] for k in ('x','y','width','height')); kind = n['kind']
        out += '<a href="objects.html#' + anchor(n['function']) + '"><title>' + h(n['name']) + '</title>'
        if kind == 'task':
            out += f'<rect x="{x}" y="{y}" width="{w}" height="{height}" rx="9" class="process-task"/>'
            import textwrap
            label = prose(n['name']); shown = label[:90] + ('…' if len(label) > 90 else '')
            for i,line in enumerate(textwrap.wrap(shown, 24)[:4]):
                out += f'<text x="{x+12}" y="{y+23+i*18}">' + h(line) + '</text>'
        elif 'Gateway' in kind:
            out += f'<polygon points="{x+w/2},{y} {x+w},{y+height/2} {x+w/2},{y+height} {x},{y+height/2}" class="process-gateway"/><text x="{x+w/2}" y="{y+height/2+6}" text-anchor="middle">' + ('+' if kind=='parallelGateway' else '○' if kind=='inclusiveGateway' else '×') + '</text>'
        else: out += f'<circle cx="{x+w/2}" cy="{y+height/2}" r="{w/2}" class="process-event" stroke-width="{3 if kind=="endEvent" else 1.5}"/>'
        out += '</a>'
    return out + '</svg></div>'


def figure(view, focused=False):
    uid = anchor(view['reference']); filename = 'process-'+uid
    # Embedded XML is data, not script or fetched content. Direct file: works.
    payload = json.dumps({'xml': bpmn(view), 'source': view['reference'], 'height': view['height']}, ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    body = '<figure class="process-diagram"><figcaption>' + h(view['name']) + (' <a href="'+filename+'.html">Ouvrir le processus complet</a>' if not focused else '') + '</figcaption><p>Couloirs : participants déclarés. Rectangle : activité. Cercle : début ou fin. Losange ○ : plusieurs flux admissibles ; × : arrivée quelconque ; + : toutes les arrivées attendues.</p><p>Glisser pour se déplacer. Les boutons règlent l’échelle ; la liste complète reste disponible sous le dessin.</p><div class="process-tools" hidden><button type="button" data-bpmn-zoom="in">Agrandir</button><button type="button" data-bpmn-zoom="out">Réduire</button><button type="button" data-bpmn-zoom="fit">Vue d’ensemble</button><button type="button" data-bpmn-zoom="read">Taille de lecture</button></div><p class="process-status" role="status">Dessin statique complet ; lecture sans JavaScript disponible.</p><div class="process-viewer" hidden></div>' + fallback(view) + '<script type="application/json" class="bpmn-data">' + payload + '</script><p><a href="'+filename+'.bpmn" download>Exporter BPMN 2.0 avec son layout</a> · <a href="'+filename+'.json">Layout et sources exactes</a></p></figure>'
    return body


def focus(view):
    out = '<h1>' + h(view['name']) + '</h1><p class="intro">' + h(view['description']) + '</p>' + figure(view, True)
    out += '<p>BPMN descriptif non exécutable. Les expressions AIR restent dans la documentation XML ; aucune équivalence avec un moteur BPMN n’est certifiée. Les compensations et la terminaison restent des déclarations AIR.</p><p>Fin : ' + h(view['termination_policy']) + '</p><h2>Activités, acteurs et fonctions</h2><ol class="process-steps">'
    for s in sorted(view['steps'], key=lambda s: (next(n['x'] for n in view['nodes'] if n['kind']=='task' and n['step']==s['id']), s['id'])):
        out += '<li><strong>' + h(s['name']) + '</strong><p>Participants : ' + h(', '.join(s['participant_names'])) + '</p><p>Fonction : <a href="objects.html#' + anchor(s['function']) + '">' + h(s['function_name']) + '</a></p></li>'
    out += '</ol><h2>Conditions complètes de chaque branche</h2><ul>'
    nodes = {n['id']:n for n in view['nodes']}
    step_names = {s['id']:s['name'] for s in view['steps']}
    for e in view['edges']:
        if e['selector']:
            out += '<li>' + h(step_names[nodes[e['source']]['step']]) + ' vers ' + h(step_names[nodes[e['target']]['step']]) + ' : <strong>' + h(e['name']) + '</strong><p>Source : <a href="objects.html#' + anchor(e['witness']) + '">' + h(view['name']) + '</a>, <code>' + h(e['selector']) + '</code>.</p></li>'
    return out + '</ul><p>' + str(len(view['cycles'])) + ' cycle(s) conservé(s). Les branches ne sont pas une liste séquentielle d’exécution.</p>'


def index(views):
    return '<h1>Processus et responsabilités</h1><p class="intro">Lire les activités, les participants et les conditions de chaque branche dans un diagramme BPMN descriptif.</p><div class="process-index">' + ''.join('<article><h2><a href="process-' + anchor(v['reference']) + '.html">' + h(v['name']) + '</a></h2><p>' + h(v['description']) + '</p><p>' + str(len(v['steps'])) + ' activités, ' + str(len(v['lanes'])) + ' couloirs. Sources et export BPMN disponibles.</p></article>' for v in views) + '</div>' + ('<p>Aucun processus déclaré.</p>' if not views else '')
