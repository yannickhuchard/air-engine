"""Exact-baseline implementation reading, using explicit typed associations only.

Packets are navigation projections, never assignments, approvals or test runs.
"""
from copy import deepcopy
from air.core import digest
from air.expr import artifact_digest
from air.foundation import TooLarge

ENGINE = 'air.site-handoff/1'
FOCUS_TYPES = ('air.ArchitectureBlock', 'air.RuntimeComponent', 'air.ConstructionUnit')
SECTIONS = (
    ('design', 'Ce qui est à réaliser'), ('contracts', 'Contrats à fournir et à utiliser'),
    ('data', 'Données et stockage'), ('dependencies', 'Dépendances déclarées'),
    ('responsibilities', 'Responsabilités déclarées'), ('acceptance', 'Critères d’acceptation'),
    ('verification', 'Vérifications prévues et résultats consignés'),
    ('delivery', 'Jalons, estimations et qualité'), ('context', 'Contexte et décisions'),
)


def key(ref):
    return ref['id'], ref['revision']


def project(export, gate):
    meta = export['baseline']['meta']
    objects = sorted(export['objects'], key=lambda o: (o['meta']['id'], o['meta']['revision']))
    if len(objects) > 1000:
        raise TooLarge('Handoff supports at most 1000 baseline objects')
    index = {key(o['meta']): o for o in objects}
    of = lambda kind: [o for o in objects if o['meta']['type'] == 'air.' + kind]
    foci = [o for o in objects if o['meta']['type'] in FOCUS_TYPES and o['meta']['namespace'] == meta['namespace']]
    teams = [o for o in of('OrganizationUnit') if o['meta']['namespace'] == meta['namespace']]
    if len(foci) > 128 or len(teams) > 64:
        raise TooLarge('Handoff supports at most 128 component/unit foci and 64 teams per dossier')
    sources = {}

    def pin(obj):
        return {'id': obj['meta']['id'], 'revision': obj['meta']['revision'], 'digest': digest(obj)}

    def retain(obj):
        sources[key(obj['meta'])] = {
            'reference': pin(obj), 'name': obj['meta']['name'], 'type': obj['meta']['type'],
            'description': obj['meta']['description'], 'lifecycle': obj['meta']['lifecycle'],
            'body': deepcopy(obj['body']),
        }
        return pin(obj)

    packets = []
    for target in foci:
        groups = {s: {} for s, _ in SECTIONS}; links = {}; unresolved = {}; scope = set()

        def add(obj, section):
            if obj:
                groups[section][key(obj['meta'])] = retain(obj)
                return obj

        def follow(source, field, section, many=False):
            value = source['body'].get(field, [] if many else None)
            refs = value if many else [value] if value else []
            found = []
            for i, ref in enumerate(refs):
                selector = '/body/' + field + ('/' + str(i) if many else '')
                obj = index.get(key(ref)); add(obj, section); retain(source)
                links[(key(source['meta']), selector)] = {
                    'source': pin(source), 'selector': selector, 'target': deepcopy(ref), 'resolved': bool(obj)}
                if obj: found.append(obj)
                else: unresolved[key(ref)] = deepcopy(ref)
            return found

        def operation_function(contract, operation, i):
            ref = operation['function']; obj = index.get(key(ref)); retain(contract)
            links[(key(contract['meta']), '/body/operations/' + str(i) + '/function')] = {
                'source': pin(contract), 'selector': '/body/operations/' + str(i) + '/function',
                'target': deepcopy(ref), 'resolved': bool(obj)}
            if obj: add(obj, 'design')
            else: unresolved[key(ref)] = deepcopy(ref)

        def inverse(kind, field, selected, section, many=False):
            found = []
            for obj in of(kind):
                refs = obj['body'].get(field, []) if many else [obj['body'].get(field)]
                if any(ref and key(ref) in selected for ref in refs):
                    add(obj, section); follow(obj, field, section, many); found.append(obj)
            return found

        add(target, 'design')
        blocks = [target] if target['meta']['type'] == 'air.ArchitectureBlock' else []
        units = [target] if target['meta']['type'] == 'air.ConstructionUnit' else []
        runtimes = [target] if target['meta']['type'] == 'air.RuntimeComponent' else []
        if runtimes:
            blocks += [o for o in follow(target, 'realizes', 'design', True) if o['meta']['type'] == 'air.ArchitectureBlock']
        if units:
            blocks += [o for o in follow(target, 'realizes', 'design', True) if o['meta']['type'] == 'air.ArchitectureBlock']
        block_keys = {key(o['meta']) for o in blocks}
        runtimes += inverse('RuntimeComponent', 'realizes', block_keys, 'design', True)
        for block in blocks:
            for field, section in [('functions', 'design'), ('provided_contracts', 'contracts'),
                                   ('required_contracts', 'contracts'), ('owned_state', 'data')]:
                follow(block, field, section, True)
        if units: follow(target, 'realizes', 'design', True)
        for obj in list(groups['design'].values()):
            source = index[key(obj)]
            if source['meta']['type'] == 'air.SemanticContract': add(source, 'contracts')
        direct_design = {key(o['meta']) for o in blocks}
        for block in blocks:
            direct_design.update(key(r) for field in ('functions', 'provided_contracts') for r in block['body'].get(field, []))
        if not units:
            units += inverse('ConstructionUnit', 'realizes', direct_design, 'design', True)
        # One bounded construction association, not an arbitrary transitive closure.
        for unit in {key(o['meta']): o for o in units}.values():
            for obj in follow(unit, 'realizes', 'design', True):
                if obj['meta']['type'] == 'air.SemanticContract': add(obj, 'contracts')
            follow(unit, 'justified_by', 'acceptance', True)
            follow(unit, 'acceptance', 'acceptance', True)
            follow(unit, 'estimate', 'delivery')
        ports = inverse('Port', 'block', block_keys, 'contracts')
        for port in ports:
            follow(port, 'contract', 'contracts'); follow(port, 'bindings', 'contracts', True)
        for k in list(groups['contracts']):
            contract = index[k]
            if contract['meta']['type'] == 'air.SemanticContract':
                for i, operation in enumerate(contract['body']['operations']):
                    # A required interface describes a dependency; its provider's
                    # functions do not become this consumer's construction scope.
                    if not any(key(r) == k for block in blocks for r in block['body'].get('required_contracts', [])):
                        operation_function(contract, operation, i)
        for runtime in {key(o['meta']): o for o in runtimes}.values():
            for field in ('environment', 'zone'): follow(runtime, field, 'context')
            follow(runtime, 'technologies', 'context', True); follow(runtime, 'stores', 'data', True)
        runtime_keys = {key(o['meta']) for o in runtimes}
        for field in ('source', 'target'):
            connections = inverse('Connection', field, runtime_keys, 'dependencies')
            for connection in connections:
                follow(connection, 'source', 'dependencies'); follow(connection, 'target', 'dependencies')
        tables = inverse('PhysicalTable', 'store', runtime_keys, 'data')
        for table in tables: follow(table, 'implements', 'data')
        for ref in list(groups['design'].values()):
            obj = index[key(ref)]
            if obj['meta']['type'] == 'air.Function':
                follow(obj, 'satisfies', 'acceptance', True)
                follow(obj, 'exceptions', 'context', True)
        # Criteria and their planned cases remain declarations, even if runs exist.
        for ref in list(groups['acceptance'].values()):
            obj = index[key(ref)]
            if obj['meta']['type'] == 'air.Requirement': follow(obj, 'acceptance', 'acceptance', True)
        for ref in list(groups['acceptance'].values()):
            obj = index[key(ref)]
            if obj['meta']['type'] == 'air.AcceptanceCriterion': follow(obj, 'cases', 'verification', True)
        scope = set(groups['design']) | set(groups['contracts']) | set(groups['data']) | set(groups['acceptance'])
        inverse('VerificationCase', 'target', scope, 'verification')
        case_keys = {k for k in groups['verification'] if index[k]['meta']['type'] == 'air.VerificationCase'}
        runs = inverse('VerificationRun', 'case', case_keys, 'verification')
        for run in runs: follow(run, 'evidence', 'verification', True)
        inverse('Milestone', 'deliverables', scope, 'delivery', True)
        inverse('DeliveryEstimate', 'unit', set(groups['design']), 'delivery')
        inverse('QualityRequirement', 'scope', scope, 'delivery')
        inverse('Decision', 'basis', scope, 'context', True)
        racis = inverse('RaciAssignment', 'subject', scope, 'responsibilities')
        for raci in racis:
            roles = follow(raci, 'role', 'responsibilities')
            inverse('OrganizationUnit', 'roles', {key(o['meta']) for o in roles}, 'responsibilities', True)
        gaps = []

        def gap(code, label, action):
            gaps.append({'code': code, 'label': label, 'next_action': action})

        if not units: gap('CONSTRUCTION_UNIT', 'Unité de construction non liée', 'Déclarer ce qui doit être livré et sa relation de réalisation.')
        if not groups['contracts']: gap('CONTRACTS', 'Contrats non liés', 'Confirmer les interfaces à fournir et à consommer avec les équipes partenaires.')
        for phase, label in [('DELIVERY', 'réalisation'), ('OPERATIONS', 'l’exploitation')]:
            for responsibility, verb in [('R', 'réaliser'), ('A', 'répondre de l’activité')]:
                if not any(r['body']['phase'] == phase and r['body']['responsibility'] == responsibility for r in racis):
                    gap(phase + '_' + responsibility, 'RACI ' + responsibility + ' de ' + label + ' non liée',
                        'Convenir avec les équipes du rôle chargé de ' + verb + ' et préciser le sujet de l’affectation.')
        criteria = [index[k] for k in groups['acceptance'] if index[k]['meta']['type'] == 'air.AcceptanceCriterion']
        if not criteria: gap('ACCEPTANCE', 'Critères d’acceptation non liés', 'Définir les conditions vérifiables de réception avec les responsables habilités.')
        for criterion in criteria:
            if not any(key(r) in index for r in criterion['body'].get('cases', [])):
                gap('CRITERION_CASES', 'Cas non lié pour « ' + criterion['meta']['name'] + ' »', 'Déclarer le cas et sa cible pour ce critère précis.')
        if not case_keys: gap('VERIFICATION', 'Cas de vérification non liés', 'Déclarer cibles, entrées, oracles et méthode de vérification.')
        if not runs: gap('RUNS', 'Aucun résultat de vérification consigné', 'Préparer les vérifications du design ; distinguer les futurs tests sur le système réalisé.')
        for kind, code, label, action in [
            ('Milestone', 'MILESTONES', 'Jalons non liés', 'Convenir des livrables, dépendances et critères de sortie avant de fixer des engagements.'),
            ('QualityRequirement', 'QUALITY', 'Exigences de qualité non liées à ce périmètre', 'Préciser les niveaux de qualité et leur périmètre exact ; consulter aussi le sujet qualité du dossier.'),
            ('Estimate', 'ESTIMATE', 'Estimation de construction non liée', 'Documenter la base d’effort et ses hypothèses sans inventer une durée.')]:
            if not any(index[k]['meta']['type'] == 'air.' + kind for k in groups['delivery']): gap(code, label, action)
        if unresolved: gap('UNRESOLVED_REFERENCE', 'Références absentes de cette baseline', 'Résoudre les références exactes signalées avant de transmettre le dossier.')
        packets.append({'target': retain(target), 'name': target['meta']['name'], 'type': target['meta']['type'],
                        'sections': {s: [v for _, v in sorted(groups[s].items())] for s, _ in SECTIONS},
                        'scope': [dict(id=i, revision=r) for i, r in sorted(scope)],
                        'links': [v for _, v in sorted(links.items())], 'unresolved': [v for _, v in sorted(unresolved.items())],
                        'gaps': gaps, 'complete_or_approved': False})
    team_packets = []
    for team in teams:
        roles = team['body'].get('roles', [])
        role_keys = {key(r) for r in roles}
        assignments = [o for o in of('RaciAssignment') if key(o['body']['role']) in role_keys]
        team_packets.append({'target': retain(team), 'name': team['meta']['name'],
                             'roles': [retain(index[key(r)]) if key(r) in index else deepcopy(r) for r in roles],
                             'assignments': [retain(r) for r in assignments],
                             'foci': [p['target'] for p in packets if any(r['body'].get('subject') and key(r['body']['subject']) in {key(s) for s in p['scope']} for r in assignments)],
                             'unscoped_assignments': [pin(r) for r in assignments if 'subject' not in r['body']],
                             'complete_or_approved': False})
    result = {'engine': ENGINE, 'baseline': {'id': meta['id'], 'revision': meta['revision'], 'digest': export['digest']},
              'gate': {'code': gate['result']}, 'packets': packets, 'teams': team_packets,
              'sources': [v for _, v in sorted(sources.items())],
              'association_policy': 'EXPLICIT_TYPED_LINKS_ONE_CONSTRUCTION_ASSOCIATION_EXACT_REVISIONS',
              'unscoped_responsibilities_are_component_assignments': False,
              'business_execution_performed': False, 'audience_is_access_control': False}
    return {**result, 'projection_digest': artifact_digest(result)}
