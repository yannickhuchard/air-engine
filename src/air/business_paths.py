"""Explain declared business paths. Reference adjacency never becomes causality.

All traversal stays inside one authorized, pinned baseline. Lexical discovery
returns choices; it neither guesses an intention nor merges revisions/dossiers.
"""
from collections import defaultdict, deque
from copy import deepcopy
import re
import unicodedata
from air.access import ScopedStore
from air.core import REF, digest, record, reference_slots
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, InvalidModel, TooLarge
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.business-paths/1'
ROOT_TYPES = ['air.Workflow', 'air.CustomerJourney', 'air.ValueStream', 'air.Capability',
              'air.BusinessService', 'air.Function', 'air.ArchitectureBlock']
REQUEST = record({
    'baselines': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True},
    'query': {'type': 'string', 'minLength': 1, 'maxLength': 512},
    'start': record({'baseline': SNAPSHOT, 'object': REF}),
    'max_nodes': {'type': 'integer', 'minimum': 8, 'maximum': 512},
    'max_depth': {'type': 'integer', 'minimum': 1, 'maximum': 12},
    'max_paths': {'type': 'integer', 'minimum': 1, 'maximum': 64},
    'max_steps': {'type': 'integer', 'minimum': 1, 'maximum': 256},
}, ['baselines'])
REQUEST['oneOf'] = [{'required': ['query'], 'not': {'required': ['start']}},
                    {'required': ['start'], 'not': {'required': ['query']}}]

# Deliberately exclude scope, provenance and verification-reference hubs from
# the context traversal. They remain in source objects, not invented calls.
FIELDS = {
    'air.Workflow': ['steps', 'compensations'],
    'air.CustomerJourney': ['persona', 'steps'],
    'air.Touchpoint': ['usage_points', 'participants', 'architecture_links'],
    'air.UsagePoint': ['parent', 'architecture_links'],
    'air.ValueStream': ['stakeholder', 'stages'],
    'air.Capability': ['required_functions'],
    'air.BusinessService': ['beneficiaries', 'capabilities', 'service_commitments'],
    'air.Function': ['exceptions'],
    'air.SemanticContract': ['operations', 'participants', 'error_contract'],
    'air.ArchitectureBlock': ['functions', 'provided_contracts', 'required_contracts', 'owned_state'],
    'air.Port': ['block', 'contract', 'bindings'],
    'air.TechnicalBinding': ['contract', 'schema_mapping', 'channel_mapping', 'security_binding'],
    'air.DataFlow': ['source', 'destination', 'schema', 'transformations', 'controls'],
    'air.DataSchema': ['represents'], 'air.DataEntity': ['concept', 'ownership'],
    'air.Message': ['schema'], 'air.Event': ['payload_schema', 'delivery_contract'],
    'air.RuntimeComponent': ['realizes', 'stores'], 'air.Connection': ['source', 'target', 'flow'],
    'air.PhysicalTable': ['store', 'implements'],
}
REVERSE = {
    'air.Workflow': ['steps'], 'air.ValueStream': ['stages'],
    'air.SemanticContract': ['operations'], 'air.ArchitectureBlock': ['functions', 'provided_contracts', 'required_contracts'],
    'air.Port': ['block', 'contract'], 'air.TechnicalBinding': ['contract', 'channel_mapping'],
    'air.DataFlow': ['source', 'destination', 'transformations'], 'air.RuntimeComponent': ['realizes', 'stores'],
    'air.Connection': ['source', 'target', 'flow'], 'air.PhysicalTable': ['implements'],
}
LEAVES = {'air.Actor', 'air.FailureMode', 'air.Control', 'air.Concept', 'air.DataAuthority'}
STOP = set('donne moi le la les un une des du de d l et a au aux pour sur dans notre nos me the an of to in on give path chemin parcours mise jour update'.split())


def identity(ref): return ref['id'], ref['revision']


def tokens(text):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return set(re.findall(r'[a-z0-9]+', normalized)) - STOP


def descriptor(obj):
    return {'reference': {**exact(obj), 'digest': digest(obj)}, 'type': obj['meta']['type'],
            'name': obj['meta']['name'], 'description': obj['meta']['description'],
            'lifecycle': obj['meta']['lifecycle'], 'validity': obj['meta']['validity']}


def discover(exports, query):
    wanted = tokens(query)
    if not wanted: raise InvalidModel('Use specific business terms, or select an exact start object')
    found = []
    def text_values(value):
        if isinstance(value, str): yield value
        elif isinstance(value, list):
            for v in value: yield from text_values(v)
        elif isinstance(value, dict) and not ('id' in value and 'revision' in value):
            for k, v in value.items():
                if k not in ('binding', 'ast', 'language', 'language_version'): yield from text_values(v)
    for e in exports:
        for obj in sorted(e['objects'], key=lambda o: identity(exact(o))):
            if obj['meta']['type'] not in ROOT_TYPES: continue
            terms = tokens(' '.join([obj['meta']['name'], obj['meta']['description'], *text_values(obj['body'])]))
            if wanted <= terms:
                found.append({'baseline': {**exact(e['baseline']), 'digest': e['digest']},
                              **descriptor(obj), 'matched_terms': sorted(wanted)})
    return found


def workflow_projection(obj, max_paths=32, max_steps=64):
    """Bounded potential control paths, including cycles and join limitations."""
    body = obj['body'];outgoing = defaultdict(list)
    for flow in sorted(body['flows'], key=lambda f: f['id']): outgoing[flow['source']].append(flow)
    stack = [(s, [s], []) for s in reversed(sorted(body['start_steps']))]
    paths = [];truncated = False;expanded = 0
    while stack and len(paths) < max_paths and expanded < 8192:
        current, steps, flows = stack.pop();expanded += 1
        if current in steps[:-1]: outcome = 'CYCLE'
        elif not outgoing[current]: outcome = 'TERMINAL'
        elif len(steps) >= max_steps: outcome = 'STEP_LIMIT';truncated = True
        else:
            for flow in reversed(outgoing[current]):
                stack.append((flow['target'], steps + [flow['target']], flows + [flow['id']]))
            continue
        paths.append({'steps': steps, 'flows': flows, 'outcome': outcome})
    if stack: truncated = True
    reachable = set();pending = list(body['start_steps'])
    while pending:
        s = pending.pop()
        if s in reachable: continue
        reachable.add(s);pending.extend(f['target'] for f in outgoing[s] if f['target'] not in reachable)
    return {'source': descriptor(obj), 'steps': deepcopy(body['steps']), 'flows': deepcopy(body['flows']),
            'start_steps': body['start_steps'], 'termination_policy': body['termination_policy'],
            'compensations': body['compensations'], 'paths': paths, 'paths_truncated': truncated,
            'unreachable_steps': sorted(s['id'] for s in body['steps'] if s['id'] not in reachable),
            'conditions_evaluated': False, 'parallel_execution_reconstructed': False,
            'path_semantics': 'POTENTIAL_CONTROL_PATHS_IGNORING_CONDITIONS_AND_JOIN_SYNCHRONIZATION'}


def project_path(exported, root, max_nodes=256, max_depth=6, max_paths=32, max_steps=64):
    """Pure calculation, also used to render the static site's exact dossiers."""
    objects = {identity(exact(o)): o for o in exported['objects']}
    if identity(root) not in objects: raise InvalidModel('Start object is absent from the selected baseline')
    if objects[identity(root)]['meta']['type'] not in ROOT_TYPES: raise InvalidModel('Start object type is not a supported business-path root')
    adjacency = defaultdict(list);edges = []
    refs = {k: {**exact(o), 'digest': digest(o)} for k, o in objects.items()}
    for k, obj in sorted(objects.items()):
        kind = obj['meta']['type']
        for field, ref, _ in reference_slots(obj):
            parts = field.split('/')
            if len(parts) < 2 or parts[0] != 'body' or parts[1] not in FIELDS.get(kind, []): continue
            target = identity(ref)
            category = 'REALIZATION' if (kind == 'air.RuntimeComponent' and parts[1] == 'realizes') or (kind == 'air.ArchitectureBlock' and parts[1] == 'functions') else 'REFERENCE'
            if kind == 'air.SemanticContract' and parts[1] == 'operations': category = 'OPERATION_BINDING'
            edge = {'source': exact(obj), 'target': deepcopy(ref), 'kind': category,
                    'evidence': refs[k], 'selector': '/' + field}
            index = len(edges);edges.append(edge);adjacency[k].append((target, index))
            if len(edges) > 32768: raise TooLarge('Business-path graph exceeds 32768 reference edges')
            if parts[1] in REVERSE.get(kind, []): adjacency[target].append((k, index))
    selected = set();queue = deque([(identity(root), 0)]);truncated = False;frontier = set();gaps = []
    while queue:
        k, depth = queue.popleft()
        if k in selected: continue
        if k not in objects:
            gaps.append({'code': 'EXACT_REFERENCE_MISSING', 'reference': {'id': k[0], 'revision': k[1]}});continue
        if len(selected) >= max_nodes: truncated = True;break
        selected.add(k)
        if objects[k]['meta']['type'] in LEAVES: continue
        for target, _ in adjacency[k]:
            if target in selected: continue
            if depth >= max_depth: frontier.add(target)
            else: queue.append((target, depth + 1))
    truncated = truncated or bool(frontier - selected)
    chosen = [objects[k] for k in sorted(selected)]
    graph_edges = [e for e in edges if identity(e['source']) in selected and identity(e['target']) in selected]
    workflows = [workflow_projection(o, max_paths, max_steps) for o in chosen if o['meta']['type'] == 'air.Workflow']
    for w in workflows:
        w['relationship_to_root'] = 'SELECTED_WORKFLOW' if identity(w['source']['reference']) == identity(root) else 'REFERENCE_ASSOCIATION_NOT_CAUSAL_CONTINUATION'
        if w['relationship_to_root'] != 'SELECTED_WORKFLOW':
            gaps.append({'code': 'WORKFLOW_ASSOCIATION_IS_NOT_CAUSAL_CONTINUATION', 'source': w['source']['reference']})
        for flow in w['flows']:
            if 'guard' not in flow and flow['binding'] == 'air.workflow-flow/0.22':
                gaps.append({'code': 'CONDITION_NOT_FORMALIZED', 'source': w['source']['reference'], 'flow': flow['id'], 'condition': flow['condition']})
        if w['paths_truncated']: gaps.append({'code': 'CONTROL_PATHS_TRUNCATED', 'source': w['source']['reference']})
        if any(s.get('join') == 'ALL' for s in w['steps']): gaps.append({'code': 'PARALLEL_JOIN_REQUIRES_SIMULATION', 'source': w['source']['reference']})
        if w['compensations']: gaps.append({'code': 'COMPENSATION_ORDER_UNDECLARED', 'source': w['source']['reference']})
        if w['unreachable_steps']: gaps.append({'code': 'UNREACHABLE_STEPS', 'source': w['source']['reference'], 'steps': w['unreachable_steps']})
    for obj in chosen:
        k = identity(exact(obj));kind = obj['meta']['type']
        if kind == 'air.Function':
            if not any(objects.get(s, {}).get('meta', {}).get('type') == 'air.ArchitectureBlock' for s, i in adjacency[k]):
                gaps.append({'code': 'FUNCTION_COMPONENT_UNDECLARED', 'source': descriptor(obj)['reference']})
            if not any(objects.get(s, {}).get('meta', {}).get('type') == 'air.SemanticContract' for s, i in adjacency[k]):
                gaps.append({'code': 'FUNCTION_OPERATION_UNDECLARED', 'source': descriptor(obj)['reference']})
            if obj['body']['exceptions']: gaps.append({'code': 'ERROR_REFERENCE_IS_NOT_CONTROL_FLOW', 'source': descriptor(obj)['reference']})
        if kind == 'air.ArchitectureBlock' and not any(objects.get(s, {}).get('meta', {}).get('type') == 'air.DataFlow' for s, i in adjacency[k]):
            gaps.append({'code': 'COMPONENT_DATA_FLOW_UNDECLARED', 'source': descriptor(obj)['reference']})
    if truncated: gaps.append({'code': 'CONTEXT_TRUNCATED', 'limits': {'max_nodes': max_nodes, 'max_depth': max_depth}})
    def declarations(kind): return [{'source': descriptor(o), 'declared': deepcopy(o['body'])} for o in chosen if o['meta']['type'] == kind]
    # Data flows carry direction and exact evidence. A Connection is a design
    # topology declaration, not a business call or a proven data-flow link.
    for o in chosen:
        if o['meta']['type'] == 'air.DataFlow' and identity(o['body']['source']) in selected and identity(o['body']['destination']) in selected:
            graph_edges.append({'source': o['body']['source'], 'target': o['body']['destination'], 'kind': 'DECLARED_DATA_FLOW',
                                'evidence': descriptor(o)['reference'], 'selector': '/body', 'purpose': o['body']['purpose']})
    if not workflows: gaps.append({'code': 'ORDERED_WORKFLOW_UNDECLARED_FOR_CONTEXT', 'source': refs[identity(root)]})
    return {'root': descriptor(objects[identity(root)]),
            'status': 'PARTIAL_DECLARATIONS' if gaps else 'RESOLVED_DECLARATIONS',
            'context_graph': {'nodes': [{**descriptor(o), 'declared': deepcopy(o['body'])} for o in chosen], 'edges': graph_edges, 'truncated': truncated,
                              'semantics': 'DECLARED_ASSOCIATIONS_NOT_AN_EXECUTION_SEQUENCE'},
            'workflows': workflows, 'journeys': declarations('air.CustomerJourney'), 'value_streams': declarations('air.ValueStream'),
            'contracts': declarations('air.SemanticContract'), 'bindings': declarations('air.TechnicalBinding'),
            'data_flows': declarations('air.DataFlow'), 'connections': declarations('air.Connection'),
            'events': declarations('air.Event'), 'gaps': gaps,
            'causality_verified': False, 'business_execution_performed': False, 'conditions_evaluated': False,
            'registry_written': False, 'authorization_granted': False}


def query_paths(store, principal, policy, request):
    check_schema(request, REQUEST)
    scoped = ScopedStore(store, principal, policy)
    # Authorize all requested baselines before discovering names. No partial
    # answer can disclose the accessible part of an unauthorized project.
    exports = [snapshot(scoped, ref) for ref in request['baselines']]
    if sum(len(e['objects']) for e in exports) > 16000: raise TooLarge('Business-path context exceeds 16000 objects')
    report = {'engine': ENGINE, 'request_digest': artifact_digest(request), 'baselines': request['baselines'],
              'discovery': 'LEXICAL_ALL_MEANINGFUL_TERMS_NO_SEMANTIC_INFERENCE',
              'candidates': [], 'result': None, 'registry_written': False, 'business_execution_performed': False}
    if 'query' in request:
        candidates = discover(exports, request['query'])
        report['candidate_count'] = len(candidates);report['candidates'] = candidates[:64]
        report['candidates_truncated'] = len(candidates) > 64
        report['status'] = 'NOT_FOUND' if not candidates else 'AMBIGUOUS' if len(candidates) != 1 else 'SELECTED'
        selected = candidates[0] if len(candidates) == 1 else None
        if selected: start = {'baseline': selected['baseline'], 'object': {k: selected['reference'][k] for k in ('id', 'revision')}}
    else:
        start = request['start'];selected = start;report['status'] = 'SELECTED'
        if start['baseline'] not in request['baselines']: raise InvalidModel('Start baseline must be one of the requested exact baselines')
    if selected:
        e = next(e for e in exports if {**exact(e['baseline']), 'digest': e['digest']} == start['baseline'])
        limits = {k: request[k] for k in ('max_nodes', 'max_depth', 'max_paths', 'max_steps') if k in request}
        report['result'] = {'baseline': start['baseline'], **project_path(e, start['object'], **limits)}
        report['status'] = report['result']['status']
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise TooLarge('Business-path report exceeds its budget; select one root and lower traversal limits') from exc
    return report
