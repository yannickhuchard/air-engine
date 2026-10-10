"""Explicit contextual questions, including questions for objects never created."""
from copy import deepcopy
import rfc8785
from air.access import ScopedStore
from air.build_schema import CONTEXTS, CATALOGUE
from air.core import record, digest
from air.expr import artifact_digest, bounded
from air.foundation import check_schema, key, InvalidModel
from air.parsing import check_tree
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.completeness/1'
def context_budget(document, max_bytes=8388608):
    try:
        check_tree(document)
        if len(rfc8785.dumps(document)) > max_bytes: raise ValueError('Contextual report exceeds its byte budget')
    except (ValueError, RecursionError, UnicodeError) as exc: raise InvalidModel(str(exc)) from exc


def snapshot_budget(exported):
    if len(exported['objects']) > 20000: raise InvalidModel('Contextual snapshot exceeds 20,000 objects')
    context_budget(exported, 33554432)

REQUEST = record({'baseline': SNAPSHOT, 'profiles': {'type': 'array', 'items': {'enum': CONTEXTS},
    'minItems': 1, 'maxItems': 5, 'uniqueItems': True}}, ['baseline'])
# Questions are versioned with the catalogue, not inferred from existing types.
RULES = {
    'COMMON': [
        ('OUTCOMES', 'Quel résultat métier doit être obtenu ?', 'Goal', '23'),
        ('REQUIREMENTS', 'Quelles exigences faut-il satisfaire ?', 'Requirement', '02'),
        ('ACCEPTANCE', 'Qui reçoit le résultat et selon quels critères ?', 'AcceptanceCriterion', '32'),
        ('DECISIONS', 'Quels choix et conséquences sont retenus ?', 'Decision', '25'),
        ('RISKS', 'Quels risques et traitements sont prévus ?', 'Risk', '16'),
        ('DELIVERY', 'Quelles unités faut-il réaliser ?', 'ConstructionUnit', '26'),
        ('RESPONSIBILITY', 'Qui réalise et qui répond de la livraison ?', 'RaciAssignment', '06'),
        ('BUDGET', 'Quelle enveloppe, contingence et hypothèses financières ?', 'FinancialPlan', '17'),
        ('VERIFICATION', 'Comment vérifier le design et la réalisation future ?', 'VerificationCase', '13'),
        ('QUALITY', 'Quelles cibles de qualité mesurables ?', 'QualityRequirement', '35'),
    ],
    'DIGITAL_SERVICE': [
        ('PERSONAS', 'Quels utilisateurs et périmètres de parcours ?', 'JourneyCatalog', '03'),
        ('JOURNEYS', 'Quels parcours, y compris les échecs ?', 'CustomerJourney', '03'),
        ('BLOCKS', 'Quels blocs structurent le service ?', 'ArchitectureBlock', '09'),
        ('CONTRACTS', 'Quelles interfaces sont fournies et consommées ?', 'SemanticContract', '11'),
        ('INTERFACES', 'Quelles spécifications machine et exemples d’intégration ?', 'InterfaceSpecification', '11'),
        ('ZONES', 'Quelles frontières de confiance et contrôles ?', 'NetworkZone', '22'),
    ],
    'DATA_PLATFORM': [
        ('LOGICAL', 'Quel modèle logique et quelle autorité des données ?', 'DataEntity', '19'),
        ('PHYSICAL', 'Quel modèle physique, clés et contraintes ?', 'PhysicalTable', '20'),
        ('LIFECYCLE', 'Quelle propriété, rétention, migration et retour arrière ?', 'DataLifecycleSpecification', '20'),
        ('FLOWS', 'Quels flux et transformations de données ?', 'DataFlow', '10'),
    ],
    'PHYSICAL_SYSTEM': [
        ('EQUIPMENT', 'Quels équipements et caractéristiques attendues ?', 'Device', '26'),
        ('ACTORS', 'Quels opérateurs, machines et robots interviennent ?', 'Actor', '05'),
        ('PHYSICAL_USES', 'Où et comment le service est-il utilisé ?', 'UsagePoint', '03'),
        ('FAILURE', 'Quels dommages, pannes et modes de récupération ?', 'FailureMode', '16'),
        ('CONTROLS', 'Quels mécanismes de maîtrise des risques physiques ?', 'Control', '22'),
        ('SOURCING', 'Quelle consultation et sélection des fournisseurs ?', 'SourcingStrategy', '25'),
    ],
    'ORGANIZATIONAL_CHANGE': [
        ('WORK', 'Quels processus et changements du travail ?', 'Workflow', '04'),
        ('TEAMS', 'Quelles équipes et capacités concernées ?', 'OrganizationUnit', '06'),
        ('VALUE', 'Quelle chaîne de valeur est transformée ?', 'ValueStream', '14'),
    ],
    'REGULATED_ACTIVITY': [
        ('OBLIGATIONS', 'Quelles obligations et décisions d’applicabilité ?', 'Obligation', '34'),
        ('CONTROLS', 'Quels contrôles vérifient ces obligations ?', 'Control', '34'),
        ('MAPPING', 'Quels implémenteurs et cas pour chaque contrôle ?', 'ComplianceMapping', '34'),
    ],
}


def pin(obj): return {**{f: obj['meta'][f] for f in ('id', 'revision')}, 'digest': digest(obj)}


def data_issues(spec, objects):
    index = {key(o['meta']): o for o in objects}
    table = index.get(key(spec['body']['table']))
    if not table or table['meta']['type'] != 'air.PhysicalTable': return ['TABLE_UNRESOLVED']
    issues = []
    columns = {c['name']: c for c in table['body']['columns']}
    primary = [c for c in columns.values() if c['primary_key']]
    if not primary: issues.append('PRIMARY_KEY_MISSING')
    if any(c['nullable'] for c in primary): issues.append('PRIMARY_KEY_NULLABLE')
    for names in spec['body']['unique_keys'] + [i['columns'] for i in spec['body']['indexes']]:
        if len(names) != len(set(names)) or set(names) - set(columns): issues.append('UNKNOWN_OR_DUPLICATE_COLUMN')
    return sorted(set(issues))


def project(exported, profiles=None):
    snapshot_budget(exported)
    meta = exported['baseline']['meta']; home = meta['namespace']
    owned = sorted([o for o in exported['objects'] if o['meta']['namespace'] == home], key=lambda o: key(o['meta']))
    contexts = [o for o in owned if o['meta']['type'] == 'air.DossierContext']
    selected = sorted(set(profiles or (contexts[0]['body']['profiles'] if len(contexts) == 1 else [])))
    context_state = 'PREVIEW' if profiles is not None else 'SELECTED' if len(contexts) == 1 else 'NOT_SELECTED' if not contexts else 'AMBIGUOUS'
    exclusions = contexts[0]['body']['exclusions'] if len(contexts) == 1 and profiles is None else []
    index = {key(o['meta']): o for o in exported['objects']}
    rows = []
    def row(code, question, topic, refs, issues=()):
        rows.append({'id': code, 'question': question, 'topic': topic,
            'status': 'PARTIAL' if issues else 'DOCUMENTED' if refs else 'NOT_DOCUMENTED',
            'sources': [pin(o) for o in refs], 'issues': list(issues), 'exclusion': None})
    for profile in ['COMMON'] + selected:
        for code, question, kind, topic in RULES[profile]:
            refs = [o for o in owned if o['meta']['type'] == 'air.' + kind]
            if profile == 'PHYSICAL_SYSTEM' and code == 'EQUIPMENT':
                refs = [o for o in refs if o['body'].get('kind') not in ('VIRTUAL_MACHINE', 'NODE_POOL', 'MANAGED_SERVICE')]
            if profile == 'PHYSICAL_SYSTEM' and code == 'PHYSICAL_USES':
                refs = [o for o in refs if o['body'].get('kind') in ('PHYSICAL', 'GEOGRAPHIC')]
            row(profile + '.' + code, question, topic, refs)
    for obj in owned:
        kind = obj['meta']['type']; b = obj['body']; suffix = artifact_digest(pin(obj)).split(':')[1]
        if kind == 'air.SemanticContract' and 'DIGITAL_SERVICE' in selected:
            from air.interface_contracts import specification_issues
            specs = [s for s in owned if s['meta']['type'] == 'air.InterfaceSpecification' and key(s['body']['contract']) == key(obj['meta'])]
            issues = []
            for spec in specs: issues += specification_issues(spec, exported['objects'])
            binding_keys = [key(s['body']['binding']) for s in specs]
            if len(binding_keys) != len(set(binding_keys)): issues.append('MULTIPLE_SPECIFICATIONS_FOR_BINDING')
            row('INTERFACE:' + suffix, 'Spécifier et vérifier toutes les opérations de « ' + obj['meta']['name'] + ' »', '11', specs, issues)
        if kind == 'air.PhysicalTable' and 'DATA_PLATFORM' in selected:
            specs = [s for s in owned if s['meta']['type'] == 'air.DataLifecycleSpecification' and key(s['body']['table']) == key(obj['meta'])]
            issues = ['MULTIPLE_LIFECYCLES'] if len(specs) > 1 else []
            for spec in specs: issues += data_issues(spec, exported['objects'])
            row('DATA:' + suffix, 'Préciser le cycle de vie de « ' + obj['meta']['name'] + ' »', '20', specs, issues)
        if kind == 'air.ConstructionUnit':
            cases = [index.get(key(r)) for r in b['acceptance']]
            issues = ['ACCEPTANCE_WITHOUT_CASES'] if any(not c or not c['body'].get('cases') or any(key(r) not in index for r in c['body']['cases']) for c in cases) else []
            row('UNIT:' + suffix, 'Planifier les cas de réception de « ' + obj['meta']['name'] + ' »', '32', [obj], issues)
            raci = [r for r in owned if r['meta']['type'] == 'air.RaciAssignment' and r['body']['phase'] == 'DELIVERY' and
                r['body'].get('subject') and key(r['body']['subject']) == key(obj['meta'])]
            missing = ['RESPONSIBILITY_' + role + '_MISSING' for role in ('R', 'A') if not any(r['body']['responsibility'] == role for r in raci)]
            row('RESPONSIBILITY:' + suffix, 'Affecter explicitement réalisation et responsabilité de « ' + obj['meta']['name'] + ' »', '06', raci, missing)
    known = {r['id'] for r in rows}
    exclusion_issues = []
    for exclusion in exclusions:
        decision = index.get(key(exclusion['decision']))
        if exclusion['check_id'] not in known:
            exclusion_issues.append({'code': 'UNKNOWN_EXCLUDED_CHECK', 'check_id': exclusion['check_id']}); continue
        target = next(r for r in rows if r['id'] == exclusion['check_id'])
        target['exclusion'] = {'reason': exclusion['reason'], 'decision': pin(decision) if decision else exclusion['decision'],
            'approval_verified': False}
        target['status'] = 'EXCLUSION_DECLARED'
    counts = {state: sum(r['status'] == state for r in rows) for state in ('DOCUMENTED', 'NOT_DOCUMENTED', 'PARTIAL', 'EXCLUSION_DECLARED', 'EXCLUDED_APPROVED')}
    state = ('CONTEXT_REQUIRED' if context_state in ('NOT_SELECTED', 'AMBIGUOUS') else
        'INCOMPLETE' if exclusion_issues or any(r['status'] != 'DOCUMENTED' for r in rows) else 'DOCUMENTED')
    report = {'engine': ENGINE, 'catalogue': CATALOGUE, 'baseline': {'id': meta['id'], 'revision': meta['revision'], 'digest': exported['digest']},
        'context_state': context_state, 'contexts': [pin(o) for o in contexts], 'profiles': selected,
        'available_profiles': CONTEXTS, 'result': state, 'checks': rows, 'counts': counts, 'exclusion_issues': exclusion_issues,
        'scope': 'DOCUMENTARY_PRESENCE_AND_EXPLICIT_RELATIONS', 'design_verified': False, 'ready_to_build': False,
        'launch_authorized': False, 'implementation_accepted': False, 'registry_written': False}
    context_budget(report)
    return {**report, 'report_digest': artifact_digest(report)}


def assess(store, principal, policy, request):
    check_schema(request, REQUEST); bounded(request)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    from air.interface_contracts import inspect_members
    model = attach_interfaces(project(exported, request.get('profiles')), inspect_members(store, principal, policy, exported))
    return apply_exclusion_reviews(store, principal, policy, model) if 'profiles' not in request else model


def attach_interfaces(model, reports):
    result = deepcopy(model); result.pop('report_digest', None)
    result['interfaces'] = [{k: r[k] for k in ('specification', 'result', 'diagnostic') if k in r} for r in reports]
    for report in reports:
        if report['result'] == 'PASS_DESIGN_EXAMPLES': continue
        for check in result['checks']:
            if check['id'].startswith('INTERFACE:') and report['specification'] in check['sources']:
                check['status'] = 'PARTIAL'; check['issues'].append('INTERFACE_COMPILATION:' + report['result'])
    result['counts'] = {state: sum(c['status'] == state for c in result['checks']) for state in result['counts']}
    if result['result'] == 'DOCUMENTED' and any(c['status'] != 'DOCUMENTED' for c in result['checks']): result['result'] = 'INCOMPLETE'
    context_budget(result)
    return {**result, 'report_digest': artifact_digest(result)}


def apply_exclusion_reviews(store, principal, policy, model):
    """Reuse revocable authority. No acceptance inferred from a Decision field."""
    from air.access import Forbidden, NotFound
    from air.foundation import InvalidModel
    from air.storage import Conflict
    from air.reviews import read_review
    result = deepcopy(model); result.pop('report_digest', None)
    if not any(c['exclusion'] for c in model['checks']) or not model['baseline']['digest']:
        return {**result, 'report_digest': artifact_digest(result)}
    home = store.get(model['baseline']['id'], model['baseline']['revision'])['object']['meta']['namespace']
    accepted = []; rejected = False; unreadable = False
    for record in store.reviews_of(model['baseline']['id'], home):
        stored = store.get_record(record['receipt'])
        request = stored['payload']['request']
        if request['baseline'] != model['baseline'] or request['target'] != model['baseline']: continue
        try: review = read_review(store, principal, policy, record['receipt'])
        except (Forbidden, NotFound, InvalidModel, Conflict): unreadable = True; continue
        if not review['effective']: continue
        if review['outcome'] == 'REJECTED': rejected = True
        elif review['outcome'] == 'ACCEPTED': accepted.append(record['receipt'])
    for check in result['checks']:
        if check['status'] == 'EXCLUSION_DECLARED' and accepted and not rejected and not unreadable:
            check['status'] = 'EXCLUDED_APPROVED'
            check['exclusion'].update(approval_verified=True, receipts=sorted(accepted),
                basis='EFFECTIVE_ACCEPTANCE_OF_EXACT_BASELINE_CONTAINING_CONTEXT_AND_DECISION')
    result['counts'] = {state: sum(c['status'] == state for c in result['checks']) for state in result['counts']}
    if result['context_state'] == 'SELECTED' and not result['exclusion_issues']:
        result['result'] = 'DOCUMENTED' if all(c['status'] in ('DOCUMENTED', 'EXCLUDED_APPROVED') for c in result['checks']) else 'INCOMPLETE'
    result['exclusion_review'] = {'effective_acceptances': len(accepted), 'effective_rejection': rejected, 'unreadable': unreadable}
    context_budget(result)
    return {**result, 'report_digest': artifact_digest(result)}
