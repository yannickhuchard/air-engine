"""Source-linked architecture stories from one exact, already authorized design.

Narrative reveal is presentation, never business execution or simulation evidence.
"""
from copy import deepcopy
from air.core import digest
from air.expr import artifact_digest
from air.foundation import exact

ENGINE = 'air.architecture-story/1'
PHASES = [
    ('purpose', 'Pourquoi changer ?', 'Le besoin et les résultats attendus', {
        'Intent': ['desired_change'], 'Goal': ['outcome'], 'ValueStream': ['trigger', 'value']}),
    ('mechanism', 'Comment le parcours est-il conçu ?', 'Les mécanismes déclarés et leurs branches potentielles', {
        'Workflow': ['steps', 'flows', 'termination_policy'], 'ArchitectureBlock': ['functions'],
        'RuntimeComponent': ['kind', 'responsibility', 'realizes']}),
    ('data', 'Que signifient les données ?', 'Relier les concepts aux modèles logiques et physiques', {
        'Concept': ['definition'], 'DataEntity': ['concept', 'attributes', 'identity'],
        'PhysicalTable': ['store', 'name', 'columns']}),
    ('choices', 'Pourquoi ces choix ?', 'Les décisions et leurs conséquences déclarées', {
        'Decision': ['question', 'selection', 'rationale', 'consequences', 'revisit_conditions'],
        'Risk': ['scenario', 'treatment'], 'Assumption': ['statement'], 'Unknown': ['question']}),
    ('evolution', 'Quelle évolution est proposée ?', 'Les jalons et feuilles de route restent des plans', {
        'Milestone': ['target_date', 'exit_criteria'], 'Roadmap': ['phases']}),
    ('next', 'Que faut-il encore décider ou vérifier ?', 'La préparation à la réalisation et ses limites', {
        'ArchitectureGap': ['impact', 'remediation'], 'Requirement': ['statement'],
        'AcceptanceScenario': ['intent', 'expected_outcome']}),
]


def project(exported, gate, path_results=(), comparisons=()):
    """No discovery outside exported. Every excerpt cites a field and exact object."""
    pin = {**exact(exported['baseline']), 'digest': exported['digest']}
    objects = sorted(exported['objects'], key=lambda o: (o['meta']['type'], o['meta']['name'], o['meta']['id'], o['meta']['revision']))
    phases = []
    for name, title, explanation, types in PHASES:
        selected = [o for o in objects if o['meta']['type'][4:] in types]
        entries = []
        for obj in selected[:12]:
            kind = obj['meta']['type'][4:]
            entries.append({'source': {**exact(obj), 'digest': digest(obj), 'type': obj['meta']['type'], 'name': obj['meta']['name']},
                'description': obj['meta']['description'],
                'fields': [{'selector': '/body/' + f, 'value': deepcopy(obj['body'][f])} for f in types[kind] if f in obj['body']]})
        phases.append({'id': name, 'title': title, 'explanation': explanation,
            'entries': entries, 'total_entries': len(selected), 'omitted_entries': max(0, len(selected)-12),
            'empty': not selected, 'presentation_only': True})
    paths = []; path_limits = []
    for result in path_results:
        if result['root']['type'] != 'air.Workflow': continue
        for workflow in result['workflows']:
            if workflow['relationship_to_root'] != 'SELECTED_WORKFLOW': continue
            steps = {s['id']: s for s in workflow['steps']}
            path_limits.append({'source': deepcopy(workflow['source']),
                'paths_truncated': workflow['paths_truncated'],
                'omitted_by_story': max(0, len(workflow['paths']) - 2),
                'gaps': deepcopy(result['gaps'])})
            for path in workflow['paths'][:2]:
                paths.append({'source': deepcopy(workflow['source']), 'steps': [deepcopy(steps[s]) for s in path['steps']],
                              'flows': [deepcopy(f) for f in workflow['flows'] if f['id'] in path['flows']],
                              'outcome': path['outcome'], 'conditions_evaluated': False,
                              'semantics': workflow['path_semantics'], 'parallel_execution_reconstructed': False})
    matching = [c for c in comparisons if c['before'] == pin or c['after'] == pin]
    model = {'engine': ENGINE, 'baseline': pin, 'name': exported['baseline']['meta']['name'],
        'namespace': exported['baseline']['meta']['namespace'], 'phases': phases,
        'potential_paths': paths[:8], 'omitted_potential_paths': max(0, len(paths)-8),
        'path_limits': path_limits,
        'comparisons': [{'title': c['title'], 'before': c['before'], 'after': c['after'],
            'summary': c['summary'], 'comparison_digest': c['comparison_digest'],
            'semantic_compatibility': c['semantic_compatibility']} for c in matching],
        'readiness': {'result': gate['result'], 'blocking': deepcopy(gate.get('blocking', [])),
                      'source': 'AIR_READINESS_FOR_THIS_EXACT_BASELINE'},
        'trailer': {'structure': ['HOOK', 'REVEAL', 'HIGHLIGHTS', 'OUTRO'],
            'phase_ids': ['purpose', 'mechanism', 'choices', 'next'], 'duration_seconds': 24,
            'timings': [0, 5, 12, 19, 24], 'format': 'BRAG', 'execution_trace': False},
        'registry_written': False, 'authorization_granted': False, 'business_execution_performed': False,
        'simulation_performed': False, 'scope': 'ONE_EXACT_BASELINE',
        'limitations': ['Narrative order is not a deployment plan or an execution trace.',
            'Only declared facts and explicitly pinned comparisons are shown.',
            'Guards and causal completeness are not evaluated by the animation.',
            'Missing fields, omitted entries and readiness blockers remain visible.']}
    model['story_digest'] = artifact_digest(model)
    return model


def verify(model):
    """Verify the self-contained story before optional video authoring."""
    if model.get('engine') != ENGINE:
        raise ValueError('Unsupported architecture story engine')
    raw = deepcopy(model); claimed = raw.pop('story_digest', None)
    if artifact_digest(raw) != claimed:
        raise ValueError('Architecture story digest mismatch')
    return model


def video_freshness(model, receipt, branding_digest=None):
    verify(model)
    if branding_digest is not None and receipt.get('branding_digest') != branding_digest: return 'STALE'
    return 'CURRENT' if receipt.get('baseline') == model['baseline'] and receipt.get('story_digest') == model['story_digest'] else 'STALE'
