"""Exact-baseline graph data for the offline 2D explorer.

Every declared reference remains a reference. Directed flow/topology/control
projections carry their source object and selector; they grant no execution.
"""
from copy import deepcopy
import hashlib
import json
from air.core import digest, reference_slots
from air.foundation import exact, TooLarge
from air.expr import artifact_digest

ENGINE = 'air.graph-explorer/1'
GROUPS = {
    'business': ('Besoins et acteurs', ['Intent', 'Goal', 'Metric', 'Actor', 'Stakeholder', 'Concern', 'Capability', 'BusinessService', 'Product', 'ValueStream', 'CustomerJourney', 'JourneyCatalog', 'Touchpoint', 'UsagePoint']),
    'behavior': ('Fonctions et processus', ['Function', 'Workflow', 'BusinessRule', 'StateMachine', 'FailureMode']),
    'interface': ('Contrats et échanges', ['SemanticContract', 'Port', 'TechnicalBinding', 'DataFlow', 'NavigationMap']),
    'component': ('Composants et implantation', ['ArchitectureBlock', 'RuntimeComponent', 'Connection', 'Device', 'Environment', 'NetworkZone', 'Technology']),
    'data': ('Données et ontologie', ['Concept', 'ConceptRelation', 'DataEntity', 'DataSchema', 'Message', 'Event', 'PhysicalTable', 'DataAuthority', 'Domain', 'ContextRelation']),
    'governance': ('Choix et réalisation', ['Decision', 'ArchitecturePrinciple', 'Requirement', 'AcceptanceCriterion', 'ConstructionUnit', 'Role', 'OrganizationUnit', 'AuthorityScope', 'RaciAssignment', 'Control', 'Constraint', 'Policy', 'Obligation', 'Risk', 'RiskAssessment', 'Waiver', 'Milestone', 'Roadmap', 'Estimate', 'DeliveryEstimate', 'CostItem', 'QualityRequirement', 'ComplianceMapping', 'AgenticToolPlan']),
    'design-work': ('Programmes et travaux de conception', ['TransformationProgramme', 'ArchitectureProject', 'ArchitectureTask', 'SourcingStrategy']),
    'evidence': ('Sources et vérification', []),
}
KINDS = {'REFERENCE': 'Référence', 'CONTEXT': 'Périmètre', 'PROVENANCE': 'Provenance',
         'REALIZATION': 'Réalisation déclarée', 'OPERATION_BINDING': 'Opération de contrat',
         'DATA_FLOW': 'Flux de données déclaré', 'CONNECTION': 'Connexion prévue',
         'CONCEPT_RELATION': 'Relation de concepts', 'CONTROL_FLOW': 'Branche de workflow',
         'COMPOSITION': 'Étape du workflow', 'FUNCTION_BINDING': 'Fonction de l’étape'}


def refkey(ref): return ref['id'], ref['revision']


def node_id(ref, step=None):
    text = json.dumps([ref['id'], ref['revision'], step], ensure_ascii=False, separators=(',', ':'))
    return 'g' + hashlib.sha256(text.encode()).hexdigest()[:24]


def family(kind):
    return next((name for name, (_, kinds) in GROUPS.items() if kind.removeprefix('air.') in kinds), 'evidence')


def project_graph(exported):
    objects = sorted(exported['objects'], key=lambda o: refkey(exact(o)))
    if len(objects) > 1000: raise TooLarge('Graph explorer supports at most 1000 baseline objects')
    by_ref = {refkey(exact(o)): o for o in objects}
    nodes, edges, gaps = [], [], []
    refs = {k: {**exact(o), 'digest': digest(o)} for k, o in by_ref.items()}
    def add_node(node):
        if len(nodes) >= 4096: raise TooLarge('Graph explorer exceeds 4096 object/step nodes; split the dossier or disable website')
        nodes.append(node)
    def edge(source, target, kind, source_obj, selector, label, declared=None, occurrence=None):
        if len(edges) >= 16384: raise TooLarge('Graph explorer exceeds 16384 relations; split the dossier or disable website')
        data = {'source': source, 'target': target, 'kind': kind, 'label': label,
                'evidence': refs[refkey(exact(source_obj))], 'selector': selector}
        if declared is not None: data['declared'] = deepcopy(declared)
        if occurrence is not None: data['occurrence'] = occurrence
        identity = [source, target, kind, selector, exact(source_obj), occurrence]
        data['id'] = 'e' + hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:24]
        edges.append(data)
    for obj in objects:
        ref = exact(obj);kind = obj['meta']['type']
        add_node({'id': node_id(ref), 'reference': refs[refkey(ref)], 'type': kind, 'family': family(kind),
                  'name': obj['meta']['name'], 'description': obj['meta']['description'],
                  'lifecycle': obj['meta']['lifecycle'], 'validity': obj['meta']['validity'], 'local_step': False})
        for ordinal, (field, target, _) in enumerate(reference_slots(obj)):
            if refkey(target) not in by_ref:
                gaps.append({'code': 'EXACT_REFERENCE_MISSING', 'source': ref, 'selector': field, 'target': target});continue
            parts = field.split('/');top = parts[1] if len(parts) > 1 else ''
            relation = 'PROVENANCE' if parts[0] == 'meta' else 'CONTEXT' if top in ('scope', 'subject_scope', 'data_scope', 'context', 'boundary', 'includes', 'excludes', 'domain', 'affected_scope') else 'REFERENCE'
            if top == 'realizes' or (kind == 'air.ArchitectureBlock' and top == 'functions'): relation = 'REALIZATION'
            if kind == 'air.SemanticContract' and top == 'operations': relation = 'OPERATION_BINDING'
            edge(node_id(ref), node_id(target), relation, obj, '/' + field, field, occurrence=ordinal)
        if kind == 'air.Workflow':
            for i, step in enumerate(obj['body']['steps']):
                step_id = node_id(ref, step['id'])
                add_node({'id': step_id, 'reference': refs[refkey(ref)], 'type': 'air.WorkflowStep', 'family': 'behavior',
                          'name': step['name'], 'description': 'Étape ' + step['id'] + ' du workflow ' + obj['meta']['name'],
                          'local_step': True, 'step': step['id'], 'lifecycle': obj['meta']['lifecycle'],
                          'declared': deepcopy(step), 'validity': obj['meta']['validity']})
                edge(node_id(ref), step_id, 'COMPOSITION', obj, '/body/steps/' + str(i), 'contient l’étape')
                if refkey(step['function']) in by_ref:
                    edge(step_id, node_id(step['function']), 'FUNCTION_BINDING', obj, '/body/steps/' + str(i) + '/function', 'fonction prévue')
            for i, flow in enumerate(obj['body']['flows']):
                edge(node_id(ref, flow['source']), node_id(ref, flow['target']), 'CONTROL_FLOW', obj,
                     '/body/flows/' + str(i), flow['condition'], flow)
        if kind in ('air.DataFlow', 'air.Connection', 'air.ConceptRelation'):
            fields = ('subject', 'object') if kind == 'air.ConceptRelation' else ('source', 'target') if kind == 'air.Connection' else ('source', 'destination')
            source, target = (obj['body'][f] for f in fields)
            if refkey(source) in by_ref and refkey(target) in by_ref:
                label = obj['body'].get('predicate', obj['body'].get('purpose', obj['meta']['name']))
                if kind == 'air.ConceptRelation': label += ' · ' + obj['body'].get('cardinality', 'cardinalité non déclarée')
                edge(node_id(source), node_id(target), {'air.DataFlow': 'DATA_FLOW', 'air.Connection': 'CONNECTION', 'air.ConceptRelation': 'CONCEPT_RELATION'}[kind], obj, '/body', label, obj['body'])
    result = {'engine': ENGINE, 'baseline': {**exact(exported['baseline']), 'digest': exported['digest']},
              'nodes': nodes, 'edges': edges, 'gaps': gaps,
              'families': [{'id': k, 'label': v[0]} for k, v in GROUPS.items()],
              'relation_kinds': KINDS, 'causality_verified': False, 'conditions_evaluated': False,
              'business_execution_performed': False, 'authorization_granted': False,
              'registry_written': False, 'scope': 'ONE_EXACT_BASELINE',
              'limits': {'object_nodes': 1000, 'all_nodes': 4096, 'edges': 16384}}
    result['graph_digest'] = artifact_digest(result)
    return result
