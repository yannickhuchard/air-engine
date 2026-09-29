"""Delivery profile: what shall run, where, at what cost, who decides, and the executed proof that it is ready.

Every type here is a declaration or a recorded execution; none of them deploys, pays, grants or runs anything.
"""
import re
from air.expr import Program, bounded, typed, wire, ExprError
from air.knowledge_schema import literal_values

PROFILE = 'air.delivery/0.32'
NAMES = ['VerificationRun', 'PerformanceModel', 'SimulationScenario', 'Milestone', 'Environment', 'NetworkZone',
         'RuntimeComponent', 'Connection', 'Technology', 'PhysicalTable', 'CostItem', 'ValueStream', 'CustomerJourney',
         'ArchitecturePrinciple', 'RaciAssignment', 'RiskAssessment', 'ConceptRelation', 'ContextRelation', 'NavigationMap', 'Device',
         'AcceptanceScenario', 'QualityRequirement', 'ComplianceMapping', 'AgenticToolPlan', 'DeliveryEstimate', 'Roadmap']
IDENTIFIER = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'}
MS = {'type': 'integer', 'minimum': 0, 'maximum': 86400000}
MONTH = {'type': 'string', 'pattern': r'^20[0-9]{2}-(0[1-9]|1[0-2])$'}
DAY = {'type': 'string', 'pattern': r'^20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'}
DECIMAL = {'type': 'string', 'pattern': r'^(0|[1-9][0-9]{0,14})(\.[0-9]{1,4})?$'}
RUNTIME_KINDS = ['SERVICE', 'GATEWAY', 'USER_INTERFACE', 'DATABASE', 'MESSAGE_BROKER', 'CACHE', 'BATCH', 'IDENTITY_PROVIDER',
                 'OBSERVABILITY', 'CI_CD', 'ARTIFACT_REPOSITORY', 'SECRET_STORE', 'EXTERNAL_SYSTEM', 'TEST_HARNESS']
PROOF_LEVELS = {'TEST': ['EXECUTED_TEST'], 'SIMULATION': ['CALIBRATED_SIMULATION', 'DECLARED_MODEL_SIMULATION'],
                'ANALYSIS': ['ANALYSIS'], 'INSPECTION': ['INSPECTION'], 'REVIEW': ['REVIEW']}
SCREEN_KINDS = ['PAGE', 'DIALOG', 'WIZARD_STEP', 'TOOL', 'NOTIFICATION', 'REPORT', 'EXTERNAL_LINK']
DEVICE_KINDS = ['PHYSICAL_SERVER', 'VIRTUAL_MACHINE', 'NODE_POOL', 'MANAGED_SERVICE', 'NETWORK_APPLIANCE', 'SECURITY_APPLIANCE', 'STORAGE',
                'WORKSTATION', 'MOBILE_DEVICE', 'PERIPHERAL', 'IOT_DEVICE']
NFR_CATEGORIES = ['PERFORMANCE', 'AVAILABILITY', 'RECOVERABILITY', 'SCALABILITY', 'SECURITY', 'PRIVACY', 'ACCESSIBILITY', 'USABILITY',
                  'OPERABILITY', 'MAINTAINABILITY', 'PORTABILITY', 'COMPLIANCE', 'SUSTAINABILITY']
ACTIVITIES = ['ANALYSIS', 'DESIGN', 'CODE', 'UNIT_TEST', 'INTEGRATION_TEST', 'ACCEPTANCE_TEST', 'DOCUMENTATION', 'REVIEW', 'DEPLOYMENT',
              'DATA_MIGRATION', 'INFRASTRUCTURE', 'SECURITY_HARDENING']
IMPLEMENTERS = ['air.ConstructionUnit', 'air.ArchitectureBlock', 'air.RuntimeComponent', 'air.Device', 'air.Connection', 'air.NetworkZone']
DISTRIBUTION_FIELDS = {'FIXED': {'value'}, 'UNIFORM': {'min', 'max'}, 'TRIANGULAR': {'min', 'mode', 'max'}, 'LOGNORMAL': {'median', 'p95'}}


def bodies(record, text, uri, ref, refs, nonempty, instant, artifact_ref):
    optional = {**refs, 'maxItems': 256}
    short = {**text, 'maxLength': 256}
    texts = {'type': 'array', 'items': text, 'maxItems': 64}
    typed_value = {'type': 'object', 'required': ['type'], 'properties': {'type': {'type': 'string', 'maxLength': 64}}}
    expression = record({'language': {'const': 'AIR-Expr'}, 'language_version': {'const': '0.1'}, 'ast': {'type': 'object'},
        'result_type': {'const': 'Boolean'}, 'required_inputs': {'type': 'array', 'items': record({'name': text, 'type': text}), 'maxItems': 256}},
        ['language', 'language_version', 'ast', 'result_type'])
    distribution = record({'kind': {'enum': sorted(DISTRIBUTION_FIELDS)}, 'value': MS, 'min': MS, 'mode': MS, 'max': MS,
                           'median': MS, 'p95': MS}, ['kind'])
    return {
        'air.VerificationRun': record({'case': ref, 'method': {'enum': sorted(PROOF_LEVELS)}, 'result': {'enum': ['PASS', 'FAIL', 'INCONCLUSIVE']},
            'proof_level': {'enum': sorted({v for values in PROOF_LEVELS.values() for v in values})}, 'executed_at': instant,
            'executor': uri, 'summary': text, 'evidence': optional, 'report': artifact_ref, 'environment': ref, 'scenario': ref},
            ['case', 'method', 'result', 'proof_level', 'executed_at', 'executor', 'summary']),
        'air.PerformanceModel': record({'workflow': ref, 'basis': text,
            'steps': {'type': 'array', 'minItems': 1, 'maxItems': 256, 'items': record({'step': IDENTIFIER, 'distribution': distribution,
                'calibrated_from': optional}, ['step', 'distribution'])}}, ['workflow', 'basis', 'steps']),
        'air.SimulationScenario': record({'workflow': ref, 'performance_model': ref,
            'measure': record({'from_step': IDENTIFIER, 'to_step': IDENTIFIER}),
            'target': record({'percentile': {'type': 'integer', 'minimum': 50, 'maximum': 100}, 'max_ms': MS}),
            'goal': ref, 'verification_case': ref,
            'classes': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': record({'name': IDENTIFIER,
                'weight': {'type': 'integer', 'minimum': 1, 'maximum': 1000}, 'start_step': IDENTIFIER,
                'context': {'type': 'object', 'maxProperties': 128, 'additionalProperties': typed_value}}, ['name', 'weight', 'context'])},
            'runs': {'type': 'integer', 'minimum': 1, 'maximum': 20000}, 'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2147483647}},
            ['workflow', 'performance_model', 'measure', 'target', 'classes', 'runs', 'seed']),
        'air.Milestone': record({'target_date': DAY, 'exit_criteria': {**texts, 'minItems': 1}, 'deliverables': optional,
            'depends_on': optional}, ['target_date', 'exit_criteria']),
        'air.Environment': record({'stage': {'enum': ['BUILD_TEST', 'RELEASE', 'PRODUCTION']}, 'purpose': text, 'hosting': short},
            ['stage', 'purpose', 'hosting']),
        'air.NetworkZone': record({'environment': ref, 'trust_level': {'enum': ['PUBLIC', 'DMZ', 'INTERNAL', 'RESTRICTED', 'MANAGEMENT']},
            'purpose': text, 'controls': optional}, ['environment', 'trust_level', 'purpose']),
        'air.RuntimeComponent': record({'kind': {'enum': RUNTIME_KINDS}, 'environment': ref, 'zone': ref, 'responsibility': text,
            'realizes': optional, 'technologies': optional, 'stores': optional,
            'replicas': {'type': 'integer', 'minimum': 1, 'maximum': 10000}}, ['kind', 'environment', 'zone', 'responsibility']),
        'air.Connection': record({'source': ref, 'target': ref, 'protocol': {**text, 'maxLength': 32},
            'port': {'type': 'integer', 'minimum': 1, 'maximum': 65535}, 'encrypted': {'type': 'boolean'}, 'authentication': short,
            'purpose': text, 'flow': ref}, ['source', 'target', 'protocol', 'encrypted', 'authentication', 'purpose']),
        'air.Technology': record({'category': {'enum': ['LANGUAGE', 'FRAMEWORK', 'RUNTIME', 'DATABASE', 'MESSAGING', 'CLOUD_SERVICE', 'TOOL',
                                                        'LIBRARY', 'PLATFORM', 'SECURITY', 'OBSERVABILITY']},
            'version': {**text, 'maxLength': 64}, 'license': {**text, 'maxLength': 128}, 'vendor': {**text, 'maxLength': 128},
            'status': {'enum': ['ADOPT', 'TRIAL', 'ASSESS', 'HOLD']}, 'decision': ref}, ['category', 'version', 'license', 'status']),
        'air.PhysicalTable': record({'store': ref, 'implements': ref, 'name': {'type': 'string', 'pattern': '^[a-z][a-z0-9_]{0,62}$'},
            'columns': {'type': 'array', 'minItems': 1, 'maxItems': 256, 'items': record({
                'name': {'type': 'string', 'pattern': '^[a-z][a-z0-9_]{0,62}$'}, 'type': {**text, 'maxLength': 64},
                'nullable': {'type': 'boolean'}, 'primary_key': {'type': 'boolean'},
                'references': record({'table': ref, 'column': {'type': 'string', 'pattern': '^[a-z][a-z0-9_]{0,62}$'}})},
                ['name', 'type', 'nullable', 'primary_key'])},
            'indexes': {'type': 'array', 'items': {**text, 'maxLength': 256}, 'maxItems': 64}}, ['store', 'name', 'columns']),
        'air.CostItem': record({'nature': {'enum': ['CAPEX', 'OPEX']},
            'category': {'enum': ['LABOUR', 'LICENCE', 'INFRASTRUCTURE', 'SERVICE', 'TRAINING', 'CONTINGENCY', 'OTHER']},
            'amount': record({'value': DECIMAL, 'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}}),
            'recurrence': {'enum': ['ONCE', 'MONTHLY', 'YEARLY']}, 'start': MONTH, 'end': MONTH, 'basis': text,
            'confidence': {'enum': ['LOW', 'MEDIUM', 'HIGH']}, 'related': optional, 'estimate': ref},
            ['nature', 'category', 'amount', 'recurrence', 'start', 'basis', 'confidence']),
        'air.ValueStream': record({'trigger': text, 'value': text, 'stakeholder': ref,
            'stages': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': record({'id': IDENTIFIER, 'name': short,
                'capabilities': optional, 'functions': optional, 'metrics': optional, 'lead_time': short}, ['id', 'name'])}},
            ['trigger', 'value', 'stakeholder', 'stages']),
        'air.CustomerJourney': record({'persona': ref, 'goal': text,
            'steps': {'type': 'array', 'minItems': 1, 'maxItems': 128, 'items': record({'id': IDENTIFIER, 'name': short,
                'channel': {'enum': ['WEB', 'MOBILE', 'PHONE', 'EMAIL', 'AGENT_MCP', 'BACK_OFFICE', 'PARTNER_API', 'PAPER', 'IN_PERSON']},
                'touchpoint': text, 'function': ref, 'operation': record({'contract': ref, 'name': {**text, 'maxLength': 128}}),
                'pain_points': texts}, ['id', 'name', 'channel', 'touchpoint'])}}, ['persona', 'goal', 'steps']),
        'air.ArchitecturePrinciple': record({'statement': text, 'rationale': text, 'implications': {**texts, 'minItems': 1},
            'applies_to': optional}, ['statement', 'rationale', 'implications']),
        'air.RaciAssignment': record({'activity': short, 'phase': {'enum': ['DELIVERY', 'OPERATIONS']}, 'role': ref,
            'responsibility': {'enum': ['R', 'A', 'C', 'I']}, 'subject': ref}, ['activity', 'phase', 'role', 'responsibility']),
        'air.RiskAssessment': record({'risk': ref, 'likelihood': {'type': 'integer', 'minimum': 1, 'maximum': 5},
            'impact': {'type': 'integer', 'minimum': 1, 'maximum': 5}, 'owner': short,
            'status': {'enum': ['OPEN', 'MITIGATING', 'ACCEPTED', 'CLOSED']}, 'mitigations': optional,
            'residual_likelihood': {'type': 'integer', 'minimum': 1, 'maximum': 5}, 'residual_impact': {'type': 'integer', 'minimum': 1, 'maximum': 5},
            'log': {'type': 'array', 'minItems': 1, 'maxItems': 256, 'items': record({'at': instant, 'event': text, 'by': short})}},
            ['risk', 'likelihood', 'impact', 'owner', 'status', 'log']),
        'air.ConceptRelation': record({'subject': ref, 'predicate': {'enum': ['IS_A', 'PART_OF', 'HAS', 'REFERS_TO', 'DERIVED_FROM',
                                                                              'GOVERNED_BY', 'ASSOCIATED_WITH']},
            'object': ref, 'cardinality': {'type': 'string', 'pattern': r'^(0|1|\*)\.\.(1|\*)$'}}, ['subject', 'predicate', 'object']),
        'air.NavigationMap': record({'application': ref, 'personas': optional,
            'entry_screens': {'type': 'array', 'items': IDENTIFIER, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True},
            'screens': {'type': 'array', 'minItems': 1, 'maxItems': 256, 'items': record({'id': IDENTIFIER, 'name': short,
                'kind': {'enum': SCREEN_KINDS}, 'purpose': text, 'roles': optional,
                'operations': {'type': 'array', 'maxItems': 64, 'items': record({'contract': ref, 'name': {**text, 'maxLength': 128}})}},
                ['id', 'name', 'kind', 'purpose'])},
            'transitions': {'type': 'array', 'maxItems': 1024, 'items': record({'id': IDENTIFIER, 'source': IDENTIFIER, 'target': IDENTIFIER,
                'trigger': short, 'guard': expression}, ['id', 'source', 'target', 'trigger'])}},
            ['application', 'entry_screens', 'screens', 'transitions']),
        'air.Device': record({'kind': {'enum': DEVICE_KINDS}, 'environment': ref, 'zone': ref, 'location': short,
            'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 100000}, 'owner': short, 'provider': short,
            'specification': record({'model': short, 'cpu_cores': {'type': 'integer', 'minimum': 1, 'maximum': 100000},
                'memory_gib': {'type': 'integer', 'minimum': 1, 'maximum': 1000000}, 'storage_gib': {'type': 'integer', 'minimum': 1, 'maximum': 100000000},
                'operating_system': short}, []),
            'hosts': optional, 'redundancy': short, 'status': {'enum': ['PLANNED', 'ORDERED', 'INSTALLED', 'RETIRED']}, 'cost_items': optional},
            ['kind', 'environment', 'location', 'quantity', 'owner', 'status']),
        'air.AcceptanceScenario': record({'navigation': ref, 'persona': ref, 'journey': ref, 'goal': text,
            'suites': {'type': 'array', 'items': {'enum': ['ACCEPTANCE', 'REGRESSION', 'SMOKE']}, 'minItems': 1, 'maxItems': 3, 'uniqueItems': True},
            'priority': {'enum': ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']},
            'context': {'type': 'object', 'maxProperties': 64, 'additionalProperties': typed_value},
            'preconditions': texts,
            'steps': {'type': 'array', 'minItems': 1, 'maxItems': 128, 'items': record({'id': IDENTIFIER, 'screen': IDENTIFIER, 'action': short,
                'via': IDENTIFIER, 'operation': record({'contract': ref, 'name': {**text, 'maxLength': 128}}), 'expected': text,
                'quality': optional}, ['id', 'screen', 'action', 'expected'])},
            'quality_requirements': optional, 'design_case': ref, 'acceptance_case': ref, 'simulation': ref},
            ['navigation', 'persona', 'goal', 'suites', 'priority', 'steps']),
        'air.QualityRequirement': record({'category': {'enum': NFR_CATEGORIES}, 'statement': text, 'priority': {'enum': ['MUST', 'SHOULD', 'MAY']},
            'target': record({'metric': ref, 'operator': {'enum': ['EQ', 'LTE', 'GTE']}, 'value': typed_value, 'unit': {**text, 'maxLength': 32}},
                             ['operator', 'value', 'unit']),
            'scope': ref, 'source': short, 'verification_method': {'enum': ['TEST', 'ANALYSIS', 'INSPECTION', 'SIMULATION', 'MONITORING', 'REVIEW']}},
            ['category', 'statement', 'priority', 'verification_method']),
        'air.ComplianceMapping': record({'subject': ref, 'status': {'enum': ['PLANNED', 'IMPLEMENTED', 'VERIFIED', 'NOT_APPLICABLE']},
            'implemented_by': optional, 'mechanism': text, 'verification': optional, 'decision': ref, 'evidence': texts, 'accountable': ref,
            'delegated_to': {'type': 'string', 'pattern': '^[a-z][a-z0-9_.-]{0,127}$'}},
            ['subject', 'status', 'mechanism']),
        'air.AgenticToolPlan': record({'vendor': short, 'product': short, 'plan': short,
            'price': record({'value': DECIMAL, 'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}}),
            'per': {'enum': ['SEAT_MONTH']}, 'capabilities': texts, 'data_policy': text, 'status': {'enum': ['ADOPT', 'TRIAL', 'ASSESS', 'HOLD']},
            'technology': ref}, ['vendor', 'product', 'plan', 'price', 'per', 'data_policy', 'status']),
        'air.DeliveryEstimate': record({'unit': ref, 'baseline_estimate': ref, 'plan': ref,
            'activities': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': record({'activity': {'enum': ACTIVITIES}, 'effort_pd': DECIMAL,
                'ai_applicable': {'type': 'boolean'}, 'ai_effort_pd': DECIMAL, 'rationale': text}, ['activity', 'effort_pd', 'ai_applicable', 'rationale'])},
            'team': record({'workers': {'type': 'integer', 'minimum': 1, 'maximum': 1000}, 'ai_seats': {'type': 'integer', 'minimum': 0, 'maximum': 1000},
                            'days_per_month': {'type': 'integer', 'minimum': 1, 'maximum': 31}}, ['workers', 'ai_seats']),
            'confidence': {'enum': ['LOW', 'MEDIUM', 'HIGH']}, 'basis': text}, ['unit', 'activities', 'team', 'confidence', 'basis']),
        'air.Roadmap': record({'strategy': text, 'uses_ai': {'type': 'boolean'}, 'plan': ref,
            'day_rate': record({'value': DECIMAL, 'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}}),
            'phases': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': record({'id': IDENTIFIER, 'name': short, 'objective': text,
                'start': DAY, 'end': DAY, 'units': optional, 'milestones': optional,
                'depends_on': {'type': 'array', 'items': IDENTIFIER, 'maxItems': 64, 'uniqueItems': True},
                'external_depends_on': {'type': 'array', 'maxItems': 32, 'items': record({'roadmap': ref, 'phase': IDENTIFIER,
                    'kind': {'enum': ['FINISH_TO_START', 'START_TO_START', 'FINISH_TO_FINISH']}}, ['roadmap', 'phase'])},
                'team_size': {'type': 'integer', 'minimum': 1, 'maximum': 1000}, 'exit_criteria': texts},
                ['id', 'name', 'objective', 'start', 'end', 'team_size'])},
            'risks': optional, 'assumptions': optional, 'status': {'enum': ['PROPOSED', 'RECOMMENDED', 'SELECTED', 'REJECTED']},
            'rationale': text, 'decision': ref}, ['strategy', 'uses_ai', 'phases', 'status', 'rationale']),
        'air.ContextRelation': record({'upstream': ref, 'downstream': ref, 'pattern': {'enum': ['CUSTOMER_SUPPLIER', 'CONFORMIST',
            'ANTI_CORRUPTION_LAYER', 'SHARED_KERNEL', 'OPEN_HOST_SERVICE', 'PUBLISHED_LANGUAGE', 'PARTNERSHIP', 'SEPARATE_WAYS']},
            'contract': ref, 'notes': text}, ['upstream', 'downstream', 'pattern']),
    }


# field → permitted target types; lists and single references alike
REFERENCE_FIELDS = {
    'air.VerificationRun': {'case': ['air.VerificationCase'], 'evidence': ['air.Evidence'], 'environment': ['air.Environment'],
                            'scenario': ['air.SimulationScenario']},
    'air.PerformanceModel': {'workflow': ['air.Workflow']},
    'air.SimulationScenario': {'workflow': ['air.Workflow'], 'performance_model': ['air.PerformanceModel'], 'goal': ['air.Goal'],
                               'verification_case': ['air.VerificationCase']},
    'air.Milestone': {'deliverables': ['air.ConstructionUnit', 'air.RuntimeComponent', 'air.RequiredOutput'], 'depends_on': ['air.Milestone']},
    'air.NetworkZone': {'environment': ['air.Environment'], 'controls': ['air.Control']},
    'air.RuntimeComponent': {'environment': ['air.Environment'], 'zone': ['air.NetworkZone'], 'realizes': ['air.ArchitectureBlock', 'air.ConstructionUnit'],
                             'technologies': ['air.Technology'], 'stores': ['air.DataEntity']},
    'air.Connection': {'source': ['air.RuntimeComponent'], 'target': ['air.RuntimeComponent'], 'flow': ['air.DataFlow']},
    'air.Technology': {'decision': ['air.Decision']},
    'air.PhysicalTable': {'store': ['air.RuntimeComponent'], 'implements': ['air.DataEntity']},
    'air.CostItem': {'estimate': ['air.Estimate']},
    'air.ValueStream': {'stakeholder': ['air.Stakeholder', 'air.Actor']},
    'air.CustomerJourney': {'persona': ['air.Actor', 'air.Stakeholder']},
    'air.RaciAssignment': {'role': ['air.Role']},
    'air.RiskAssessment': {'risk': ['air.Risk'], 'mitigations': ['air.Control']},
    'air.ConceptRelation': {'subject': ['air.Concept'], 'object': ['air.Concept']},
    'air.ContextRelation': {'upstream': ['air.Domain'], 'downstream': ['air.Domain'], 'contract': ['air.SemanticContract']},
    'air.NavigationMap': {'application': ['air.RuntimeComponent'], 'personas': ['air.Actor', 'air.Stakeholder']},
    'air.Device': {'environment': ['air.Environment'], 'zone': ['air.NetworkZone'], 'hosts': ['air.RuntimeComponent'], 'cost_items': ['air.CostItem']},
    'air.AcceptanceScenario': {'navigation': ['air.NavigationMap'], 'persona': ['air.Actor', 'air.Stakeholder'], 'journey': ['air.CustomerJourney'],
                               'quality_requirements': ['air.QualityRequirement'], 'design_case': ['air.VerificationCase'],
                               'acceptance_case': ['air.VerificationCase'], 'simulation': ['air.SimulationScenario']},
    'air.QualityRequirement': {'scope': ['air.Scope']},
    'air.ComplianceMapping': {'subject': ['air.Control', 'air.QualityRequirement'], 'implemented_by': IMPLEMENTERS,
                              'verification': ['air.VerificationCase'], 'decision': ['air.Decision'], 'accountable': ['air.Role']},
    'air.AgenticToolPlan': {'technology': ['air.Technology']},
    'air.DeliveryEstimate': {'unit': ['air.ConstructionUnit'], 'baseline_estimate': ['air.Estimate'], 'plan': ['air.AgenticToolPlan']},
    'air.Roadmap': {'plan': ['air.AgenticToolPlan'], 'risks': ['air.Risk'], 'assumptions': ['air.Assumption'], 'decision': ['air.Decision']},
}


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    for field, targets in REFERENCE_FIELDS.get(kind, {}).items():
        if field not in body: continue
        for reference in body[field] if isinstance(body[field], list) else [body[field]]:
            yield 'body/' + field, reference, targets
    free = {'air.Milestone': [], 'air.CostItem': ['related'], 'air.ArchitecturePrinciple': ['applies_to'], 'air.RaciAssignment': ['subject']}
    for field in free.get(kind, []):
        if field in body:
            for reference in body[field] if isinstance(body[field], list) else [body[field]]:
                yield 'body/' + field, reference, data_types
    if kind == 'air.PerformanceModel':
        for step in body['steps']:
            for reference in step.get('calibrated_from', []):
                yield 'body/steps/' + step['step'] + '/calibrated_from', reference, ['air.RuntimeObservation']
    elif kind == 'air.ValueStream':
        for stage in body['stages']:
            for field, targets in (('capabilities', ['air.Capability']), ('functions', ['air.Function']), ('metrics', ['air.Metric'])):
                for reference in stage.get(field, []): yield 'body/stages/' + stage['id'] + '/' + field, reference, targets
    elif kind == 'air.CustomerJourney':
        for step in body['steps']:
            if 'function' in step: yield 'body/steps/' + step['id'] + '/function', step['function'], ['air.Function']
            if 'operation' in step: yield 'body/steps/' + step['id'] + '/operation/contract', step['operation']['contract'], ['air.SemanticContract']
    elif kind == 'air.NavigationMap':
        for screen in body['screens']:
            for reference in screen.get('roles', []): yield 'body/screens/' + screen['id'] + '/roles', reference, ['air.Role']
            for op in screen.get('operations', []): yield 'body/screens/' + screen['id'] + '/operations/contract', op['contract'], ['air.SemanticContract']
    elif kind == 'air.AcceptanceScenario':
        for step in body['steps']:
            if 'operation' in step: yield 'body/steps/' + step['id'] + '/operation/contract', step['operation']['contract'], ['air.SemanticContract']
            for reference in step.get('quality', []): yield 'body/steps/' + step['id'] + '/quality', reference, ['air.QualityRequirement']
    elif kind == 'air.QualityRequirement' and 'target' in body and 'metric' in body['target']:
        yield 'body/target/metric', body['target']['metric'], ['air.Metric']
    elif kind == 'air.Roadmap':
        for phase in body['phases']:
            for reference in phase.get('units', []): yield 'body/phases/' + phase['id'] + '/units', reference, ['air.ConstructionUnit']
            for reference in phase.get('milestones', []): yield 'body/phases/' + phase['id'] + '/milestones', reference, ['air.Milestone']
            for dependency in phase.get('external_depends_on', []): yield 'body/phases/' + phase['id'] + '/external_depends_on', dependency['roadmap'], ['air.Roadmap']
    elif kind == 'air.PhysicalTable':
        for column in body['columns']:
            if 'references' in column: yield 'body/columns/' + column['name'] + '/references', column['references']['table'], ['air.PhysicalTable']


def local_issues(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.VerificationRun':
        if body['proof_level'] not in PROOF_LEVELS[body['method']]:
            yield 'AIR_RUN_PROOF_LEVEL', 'The proof level must match the method: ' + ', '.join(PROOF_LEVELS[body['method']])
        if body['method'] in ('TEST', 'SIMULATION') and 'report' not in body:
            yield 'AIR_RUN_REPORT', 'An executed test or simulation keeps its report as an artifact'
        if body['method'] == 'SIMULATION' and 'scenario' not in body:
            yield 'AIR_RUN_SCENARIO', 'A simulation run names the exact scenario it executed'
    elif kind == 'air.PerformanceModel':
        steps = [s['step'] for s in body['steps']]
        if len(set(steps)) != len(steps): yield 'AIR_PERFORMANCE_STEP', 'A workflow step has one duration model'
        for step in body['steps']:
            d = step['distribution'];given = set(d) - {'kind'}
            if given != DISTRIBUTION_FIELDS[d['kind']]:
                yield 'AIR_PERFORMANCE_DISTRIBUTION', step['step'] + ': ' + d['kind'] + ' takes exactly ' + ', '.join(sorted(DISTRIBUTION_FIELDS[d['kind']]))
            elif d['kind'] == 'UNIFORM' and d['min'] > d['max'] or d['kind'] == 'TRIANGULAR' and not d['min'] <= d['mode'] <= d['max'] \
                    or d['kind'] == 'LOGNORMAL' and not 0 < d['median'] <= d['p95']:
                yield 'AIR_PERFORMANCE_DISTRIBUTION', step['step'] + ': parameters are out of order'
    elif kind == 'air.SimulationScenario':
        names = [c['name'] for c in body['classes']]
        if len(set(names)) != len(names): yield 'AIR_SCENARIO_CLASS', 'Scenario class names are unique'
    elif kind == 'air.PhysicalTable':
        names = [c['name'] for c in body['columns']]
        if len(set(names)) != len(names): yield 'AIR_TABLE_COLUMN', 'Column names are unique within a table'
        if not any(c['primary_key'] for c in body['columns']): yield 'AIR_TABLE_KEY', 'A table declares a primary key'
    elif kind == 'air.CostItem':
        if 'end' in body and body['end'] < body['start']: yield 'AIR_COST_PERIOD', 'A cost ends after it starts'
        if body['recurrence'] == 'ONCE' and 'end' in body: yield 'AIR_COST_PERIOD', 'A one-off cost has no end month'
    elif kind == 'air.ValueStream' or kind == 'air.CustomerJourney':
        ids = [s['id'] for s in body['stages' if kind == 'air.ValueStream' else 'steps']]
        if len(set(ids)) != len(ids): yield 'AIR_STEP_ID', 'Stage and step identifiers are unique'
    elif kind == 'air.Connection':
        if body['source'] == body['target']: yield 'AIR_CONNECTION_SELF', 'A connection links two distinct components'
    elif kind == 'air.ContextRelation':
        if body['upstream'] == body['downstream']: yield 'AIR_CONTEXT_SELF', 'A context relation links two distinct domains'
    elif kind == 'air.NavigationMap':
        screens = [s['id'] for s in body['screens']];moves = [m['id'] for m in body['transitions']]
        if len(set(screens)) != len(screens) or len(set(moves)) != len(moves):
            yield 'AIR_NAVIGATION_ID', 'Screen and transition identifiers are unique'
        known = set(screens)
        if not set(body['entry_screens']) <= known or any(m['source'] not in known or m['target'] not in known for m in body['transitions']):
            yield 'AIR_NAVIGATION_LOCAL_REFERENCE', 'Entry screens and transition ends name declared screens'
        reached, frontier = set(body['entry_screens']) & known, list(set(body['entry_screens']) & known)
        while frontier:
            here = frontier.pop()
            for m in body['transitions']:
                if m['source'] == here and m['target'] in known and m['target'] not in reached: reached.add(m['target']);frontier.append(m['target'])
        unreachable = sorted(known - reached)
        if unreachable: yield 'AIR_NAVIGATION_UNREACHABLE', 'Screens no entry screen leads to: ' + ', '.join(unreachable)
        for m in body['transitions']:
            if 'guard' in m:
                try: bounded(m['guard']);Program(m['guard'])
                except ExprError as exc: yield exc.code, str(exc) + ' at body/transitions/' + m['id'] + '/guard'
    elif kind == 'air.Device':
        if 'hosts' in body and body['kind'] in ('PERIPHERAL', 'NETWORK_APPLIANCE') and body['hosts']:
            yield 'AIR_DEVICE_HOSTS', 'A peripheral or network appliance hosts no runtime component'
    elif kind == 'air.AcceptanceScenario':
        ids = [s['id'] for s in body['steps']]
        if len(set(ids)) != len(ids): yield 'AIR_SCENARIO_STEP', 'Scenario step identifiers are unique'
    elif kind == 'air.ComplianceMapping':
        if body['status'] == 'NOT_APPLICABLE' and 'decision' not in body:
            yield 'AIR_COMPLIANCE_JUSTIFICATION', 'A control or requirement declared not applicable cites the decision that says so'
        if 'delegated_to' in body and body['status'] != 'NOT_APPLICABLE':
            yield 'AIR_COMPLIANCE_DELEGATION', 'Only a requirement declared not applicable here is delegated to another project'
        if body['status'] != 'NOT_APPLICABLE' and not body.get('implemented_by'):
            yield 'AIR_COMPLIANCE_IMPLEMENTER', 'A planned control or requirement names the construction blocks that implement it'
    elif kind == 'air.DeliveryEstimate':
        seen = [a['activity'] for a in body['activities']]
        if len(set(seen)) != len(seen): yield 'AIR_ESTIMATE_ACTIVITY', 'An activity appears once per estimate'
        for a in body['activities']:
            if a['ai_applicable'] != ('ai_effort_pd' in a):
                yield 'AIR_ESTIMATE_AI', a['activity'] + ': an AI-assisted effort is given exactly when AI applies'
            elif a['ai_applicable'] and float(a['ai_effort_pd']) > float(a['effort_pd']):
                yield 'AIR_ESTIMATE_AI', a['activity'] + ': the AI-assisted effort does not exceed the effort without AI'
        if any(a['ai_applicable'] for a in body['activities']) and ('plan' not in body or body['team']['ai_seats'] < 1):
            yield 'AIR_ESTIMATE_AI', 'An AI-assisted estimate names its agentic tool plan and at least one seat'
    elif kind == 'air.Roadmap':
        ids = [ph['id'] for ph in body['phases']];by_id = {ph['id']: ph for ph in body['phases']}
        if len(set(ids)) != len(ids): yield 'AIR_ROADMAP_PHASE', 'Phase identifiers are unique'
        for ph in body['phases']:
            if ph['end'] < ph['start']: yield 'AIR_ROADMAP_PHASE', ph['id'] + ' ends before it starts'
            for dep in ph.get('depends_on', []):
                if dep not in by_id: yield 'AIR_ROADMAP_DEPENDENCY', ph['id'] + ' depends on an unknown phase ' + dep
                elif by_id[dep]['end'] > ph['start']: yield 'AIR_ROADMAP_DEPENDENCY', ph['id'] + ' starts before ' + dep + ' ends'
        if body['uses_ai'] and 'plan' not in body: yield 'AIR_ROADMAP_AI', 'An AI-assisted roadmap names its agentic tool plan'
    elif kind == 'air.RiskAssessment':
        if ('residual_likelihood' in body) != ('residual_impact' in body):
            yield 'AIR_RISK_RESIDUAL', 'Residual likelihood and impact are declared together'


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    accountable = {}
    for obj in objects:
        body, kind, location = obj['body'], obj['meta']['type'], obj['meta']['id']
        if kind == 'air.VerificationRun':
            case = by_ref.get(key(body['case']))
            if case and case['meta']['type'] == 'air.VerificationCase' and case['body']['method'] != body['method']:
                yield 'AIR_RUN_METHOD', location, 'A run uses the method its verification case declares'
        elif kind == 'air.PerformanceModel':
            workflow = by_ref.get(key(body['workflow']))
            if workflow and workflow['meta']['type'] == 'air.Workflow':
                known = {s['id'] for s in workflow['body']['steps']}
                unknown = sorted({s['step'] for s in body['steps']} - known)
                if unknown: yield 'AIR_PERFORMANCE_STEP', location, 'Steps absent from the workflow: ' + ', '.join(unknown)
        elif kind == 'air.SimulationScenario':
            model = by_ref.get(key(body['performance_model']));workflow = by_ref.get(key(body['workflow']))
            if model and model['meta']['type'] == 'air.PerformanceModel' and key(model['body']['workflow']) != key(body['workflow']):
                yield 'AIR_SCENARIO_MODEL', location, 'The performance model describes the same exact workflow'
            if workflow and workflow['meta']['type'] == 'air.Workflow':
                known = {s['id'] for s in workflow['body']['steps']}
                for field in ('from_step', 'to_step'):
                    if body['measure'][field] not in known:
                        yield 'AIR_SCENARIO_MEASURE', location, 'Measured step is absent from the workflow: ' + body['measure'][field]
                for cls in body['classes']:
                    if 'start_step' in cls and cls['start_step'] not in workflow['body']['start_steps']:
                        yield 'AIR_SCENARIO_START', location, 'Class ' + cls['name'] + ' starts at a step that is not a start step of the workflow'
        elif kind == 'air.RuntimeComponent':
            zone = by_ref.get(key(body['zone']))
            if zone and zone['meta']['type'] == 'air.NetworkZone' and key(zone['body']['environment']) != key(body['environment']):
                yield 'AIR_RUNTIME_ZONE', location, 'A component sits in a zone of its own environment'
        elif kind == 'air.NavigationMap':
            app = by_ref.get(key(body['application']))
            if app and app['meta']['type'] == 'air.RuntimeComponent' and app['body']['kind'] not in ('USER_INTERFACE', 'GATEWAY'):
                yield 'AIR_NAVIGATION_APPLICATION', location, 'A navigation map belongs to a user interface (or an MCP gateway serving tools)'
            for screen in body['screens']:
                for op in screen.get('operations', []):
                    contract = by_ref.get(key(op['contract']))
                    if contract and contract['meta']['type'] == 'air.SemanticContract' and op['name'] not in {o['name'] for o in contract['body']['operations']}:
                        yield 'AIR_NAVIGATION_OPERATION', location, 'Screen ' + screen['id'] + ' calls ' + op['name'] + ', which ' + contract['meta']['name'] + ' does not offer'
        elif kind == 'air.Device':
            zone = by_ref.get(key(body['zone'])) if 'zone' in body else None
            if zone and zone['meta']['type'] == 'air.NetworkZone' and key(zone['body']['environment']) != key(body['environment']):
                yield 'AIR_DEVICE_ZONE', location, 'A device sits in a zone of its own environment'
            for ref in body.get('hosts', []):
                hosted = by_ref.get(key(ref))
                if hosted and hosted['meta']['type'] == 'air.RuntimeComponent' and key(hosted['body']['environment']) != key(body['environment']):
                    yield 'AIR_DEVICE_HOST', location, 'A device hosts only components of its environment: ' + hosted['meta']['name']
        elif kind == 'air.AcceptanceScenario':
            navigation = by_ref.get(key(body['navigation']))
            if navigation and navigation['meta']['type'] == 'air.NavigationMap':
                screens = {s['id']: s for s in navigation['body']['screens']}
                for step in body['steps']:
                    if step['screen'] not in screens:
                        yield 'AIR_SCENARIO_SCREEN', location, 'Step ' + step['id'] + ' is on screen ' + step['screen'] + ', absent from ' + navigation['meta']['name']
        elif kind == 'air.Roadmap':
            for phase in body['phases']:
                for dependency in phase.get('external_depends_on', []):
                    other = by_ref.get(key(dependency['roadmap']))
                    if not other or other['meta']['type'] != 'air.Roadmap': continue
                    if other['meta']['namespace'] == obj['meta']['namespace']:
                        yield 'AIR_ROADMAP_EXTERNAL', location, phase['id'] + ': a dependency inside the project is written in depends_on';continue
                    target = next((p for p in other['body']['phases'] if p['id'] == dependency['phase']), None)
                    if target is None:
                        yield 'AIR_ROADMAP_EXTERNAL', location, phase['id'] + ' waits for ' + dependency['phase'] + ', absent from ' + other['meta']['name'];continue
                    kind_ = dependency.get('kind', 'FINISH_TO_START')
                    late = {'FINISH_TO_START': phase['start'] < target['end'], 'START_TO_START': phase['start'] < target['start'],
                            'FINISH_TO_FINISH': phase['end'] < target['end']}[kind_]
                    if late:
                        yield 'AIR_ROADMAP_EXTERNAL', location, (phase['id'] + ' (' + phase['start'] + ' → ' + phase['end'] + ') breaks ' + kind_ + ' with '
                                                                 + other['meta']['name'] + ' / ' + target['id'] + ' (' + target['start'] + ' → ' + target['end'] + ')')
        elif kind == 'air.DeliveryEstimate' and 'baseline_estimate' in body:
            estimate = by_ref.get(key(body['baseline_estimate']))
            if estimate and estimate['meta']['type'] == 'air.Estimate' and estimate['body']['target']['id'] != body['unit']['id']:
                yield 'AIR_ESTIMATE_TARGET', location, 'The estimate without AI targets the same construction unit'
        elif kind == 'air.RaciAssignment' and body['responsibility'] == 'A':
            accountable.setdefault((body['phase'], body['activity']), []).append(location)
    for (phase, activity), holders in sorted(accountable.items()):
        if len(holders) > 1:
            yield 'AIR_RACI_ACCOUNTABLE', holders[0], phase + ' activity "' + activity + '" has more than one Accountable role'
    activities = {(o['body']['phase'], o['body']['activity']) for o in objects if o['meta']['type'] == 'air.RaciAssignment'}
    for phase, activity in sorted(activities - set(accountable)):
        first = next(o['meta']['id'] for o in objects if o['meta']['type'] == 'air.RaciAssignment' and (o['body']['phase'], o['body']['activity']) == (phase, activity))
        yield 'AIR_RACI_ACCOUNTABLE', first, phase + ' activity "' + activity + '" has no Accountable role'


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type'];key = lambda r: (r['id'], r['revision'])
    if kind[4:] not in NAMES: return
    for field, value in list(body.items()):
        if isinstance(value, list) and value and all(isinstance(v, dict) and set(v) == {'id', 'revision'} for v in value):
            value.sort(key=key)
    if kind == 'air.PerformanceModel':
        body['steps'].sort(key=lambda s: s['step'])
        for step in body['steps']:
            if 'calibrated_from' in step: step['calibrated_from'].sort(key=key)
    elif kind == 'air.ValueStream':
        for stage in body['stages']:
            for field in ('capabilities', 'functions', 'metrics'):
                if field in stage: stage[field].sort(key=key)
    elif kind == 'air.AcceptanceScenario':
        body['suites'].sort()
    elif kind == 'air.NavigationMap':
        body['entry_screens'].sort()
        for screen in body['screens']:
            if 'roles' in screen: screen['roles'].sort(key=key)
        for move in body['transitions']:
            if 'guard' in move:
                if 'required_inputs' in move['guard']: move['guard']['required_inputs'].sort(key=lambda p: p['name'])
                for value in literal_values(move['guard']):
                    normalized = wire(typed(value));value.clear();value.update(normalized)
    # Journey steps, value-stream stages, columns, risk logs, screens and transitions keep their declared order: it is meaning.
