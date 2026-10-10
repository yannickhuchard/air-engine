"""Exact fictional reference model, schemas supplied by retained artifacts."""
from copy import deepcopy
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
NAMESPACE = 'reference.build_design'


def ref(name): return {'id': 'urn:air:build-demo:' + name, 'revision': 1}


def obj(kind, name, body):
    return {'meta': {'id': ref(name)['id'], 'type': 'air.' + kind, 'revision': 1, 'name': name,
        'description': 'Référence fictive : ' + name, 'namespace': NAMESPACE, 'owner': 'urn:identity:asteria:architect',
        'classification': {'level': 'PUBLIC'}, 'lifecycle': 'DRAFT', 'recorded_at': '2026-10-10T00:00:00Z',
        'validity': {'start': '2026-10-10T00:00:00Z', 'end': None},
        'provenance': {'recorded_by': 'urn:identity:asteria:architect', 'method': 'Fictional design fixture', 'source_refs': []}}, 'body': body}


def schemas(): return {name: json.loads((ROOT / (name + '.schema.json')).read_text(encoding='utf-8')) for name in ('request', 'response')}


def expression(ast, inputs):
    return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
        'required_inputs': [{'name': i['name'], 'type': i['type']} for i in inputs], 'ast': ast}


def condition(name, phase, ast, inputs):
    return {'name': name, 'phase': phase, 'description': name, 'inputs': inputs, 'expression': expression(ast, inputs)}


def call(op, *args): return {'op': op, 'args': list(args)}
def lit(t, v): return {'literal': {'type': t, 'value': v}}
def var(name): return {'ref': name}
def input(name, type, side, pointer): return {'name': name, 'type': type, 'side': side, 'pointer': pointer}


def specification():
    q = input('q', 'Integer', 'REQUEST', '/quantity')
    total = input('total', 'Integer', 'RESPONSE', '/total_minor')
    received = input('received', 'Integer', 'RESPONSE', '/quantity')
    currency = input('currency', 'Text', 'RESPONSE', '/currency')
    s = schemas()
    return obj('InterfaceSpecification', 'quote-specification', {'contract': ref('quote-contract'), 'binding': ref('http'), 'version': '1.0.0',
        'compatibility': {'strategy': 'STRICT', 'breaking_change_policy': 'Nouvelle version et revue des consommateurs avant une rupture.'},
        'operations': [{'name': 'Quote', 'request_schema': s['request'], 'response_schema': s['response'],
            'conditions': [condition('Quantité admissible', 'PRE', call('and', call('gte', var('q'), lit('Integer', 1)), call('lte', var('q'), lit('Integer', 100))), [q]),
                condition('Prix en centimes', 'POST', call('eq', var('total'), call('mul', var('q'), lit('Integer', 125))), [q, total]),
                condition('Devise et quantité préservées', 'INVARIANT', call('and', call('eq', var('q'), var('received')), call('eq', var('currency'), lit('Text', 'EUR'))), [q, received, currency])],
            'authorization': {'mode': 'PUBLIC', 'roles': [], 'basis': 'Calcul fictif sans donnée personnelle ; aucune mise en production autorisée.'},
            'idempotency': {'mode': 'REQUIRED', 'header': 'Idempotency-Key', 'window_seconds': 300, 'replay': 'SAME_RESPONSE', 'basis': 'Même clé et même requête : réponse identique ; charge différente : conflit. Fenêtre à réaliser.'},
            'concurrency': {'mode': 'SERIALIZED', 'basis': 'Les clés seront arbitrées atomiquement par le futur fournisseur.'},
            'timeout_ms': 2000, 'retry': {'max_attempts': 3, 'backoff_ms': 100, 'statuses': [503, 504]},
            'compensation': {'mode': 'NOT_REQUIRED', 'basis': 'Calcul pur sans engagement commercial ni paiement.'},
            'examples': [{'name': 'Deux unités', 'kind': 'EXCHANGE_VALID', 'request': {'quantity': 2}, 'response': {'quantity': 2, 'total_minor': 250, 'currency': 'EUR'}},
                {'name': 'Prix incorrect', 'kind': 'EXCHANGE_INVALID', 'request': {'quantity': 2}, 'response': {'quantity': 2, 'total_minor': 251, 'currency': 'EUR'}},
                {'name': 'Quantité nulle', 'kind': 'REQUEST_INVALID', 'request': {'quantity': 0}},
                {'name': 'Cent unités', 'kind': 'REQUEST_VALID', 'request': {'quantity': 100}}]}]})


def objects(artifacts):
    scope = obj('Scope', 'scope', {'includes': [], 'excludes': [], 'boundary_description': 'Comparaison fictive de fournisseur et consommateur de devis.'})
    source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': 'urn:air:fiction:build-demo', 'captured_at': '2026-10-10T00:00:00Z', 'access_policy': 'Public fictional', 'retention_policy': 'Reference fixture'})
    criterion = obj('AcceptanceCriterion', 'acceptance', {'condition': '125 centimes EUR par unité admissible.', 'verification_method': 'TEST', 'acceptance_authority': 'urn:identity:asteria:reviewer', 'cases': [ref('case')]})
    requirement = obj('Requirement', 'requirement', {'statement': 'Calculer un devis cohérent pour 1 à 100 unités.', 'kind': 'FUNCTIONAL', 'priority': 'MUST', 'applicability': 'Référence fictive', 'acceptance': [ref('acceptance')], 'source': [ref('source')]})
    function = obj('Function', 'quote', {'kind': 'SOFTWARE', 'inputs': [{'name': 'quantity', 'data_type': 'Integer', 'description': 'Nombre d’unités'}],
        'outputs': [{'name': 'total_minor', 'data_type': 'Integer', 'description': 'Montant en centimes EUR'}], 'preconditions': ['1 <= quantity <= 100'], 'postconditions': ['total_minor = quantity * 125'],
        'effects': [], 'exceptions': [], 'atomic': True, 'satisfies': [ref('requirement')]})
    client = deepcopy(function); client['meta'].update(id=ref('request-quote')['id'], name='request-quote')
    client['body']['postconditions'] = ['Le devis reçu est cohérent avec la quantité demandée.']
    actor = obj('Actor', 'requester', {'kind': 'SOFTWARE', 'roles': [], 'boundary': ref('scope')})
    contract = obj('SemanticContract', 'quote-contract', {'operations': [{'name': 'Quote', 'function': ref('quote')}], 'participants': [{'actor': ref('requester'), 'role': 'consumer'}],
        'authorization': 'Fictional public computation only', 'state_effects': [], 'error_contract': [], 'quality': [], 'compatibility_policy': 'Exact contract version'})
    case = obj('VerificationCase', 'case', {'target': ref('quote-contract'), 'method': 'TEST', 'inputs': [], 'oracle': 'Total = quantité * 125 ; quantité et EUR préservés.', 'acceptance': 'Échanges valides et invalides attendus.', 'independence_basis': 'Prototypes séparés, pas une revue humaine.'})
    control = obj('Control', 'control', {'objective': 'Ne pas confondre prototype et production', 'mechanism': 'Réception explicite ultérieure', 'scope': ref('scope'), 'owner': 'urn:identity:asteria:architect', 'verification': [ref('case')], 'evidence_requirements': ['Exact pinned contract']})
    schema_objects = [obj('DataSchema', name + '-schema', {'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': artifacts[name], 'represents': [], 'compatibility_policy': 'Strict pinned schema'}) for name in ('request', 'response')]
    blocks = [obj('ArchitectureBlock', name, {'kind': 'MODULE' if name == 'provider' else 'ADAPTER', 'responsibilities': ['Fournir le devis' if name == 'provider' else 'Demander le devis'],
        'functions': [ref('quote' if name == 'provider' else 'request-quote')], 'provided_contracts': [ref('quote-contract')] if name == 'provider' else [],
        'required_contracts': [ref('quote-contract')] if name == 'consumer' else [], 'owned_state': []}) for name in ('provider', 'consumer')]
    binding = obj('TechnicalBinding', 'http', {'contract': ref('quote-contract'), 'protocol': 'HTTP', 'protocol_version': '1.1', 'security_binding': [ref('control')],
        'schema_mapping': [{'binding': 'air.http-json-mapping/0.30', 'operation': 'Quote', 'method': 'POST', 'path': '/quotes', 'request_schema': ref('request-schema'), 'request_required': True,
            'response_schema': ref('response-schema'), 'response_status': '200', 'parameters': [{'name': 'Idempotency-Key', 'in': 'header', 'required': True, 'type': 'string'}], 'errors': []}]})
    ports = [obj('Port', side + '-port', {'block': ref(side), 'direction': 'PROVIDED' if side == 'provider' else 'REQUIRED', 'contract': ref('quote-contract'), 'bindings': [ref('http')]}) for side in ('provider', 'consumer')]
    flow = obj('DataFlow', 'request-flow', {'source': ref('consumer-port'), 'destination': ref('provider-port'), 'schema': ref('request-schema'), 'purpose': 'Obtenir un devis fictif', 'transformations': [], 'controls': [ref('control')]})
    units = [obj('ConstructionUnit', side + '-unit', {'realizes': [ref('quote' if side == 'provider' else 'request-quote')], 'work_kind': 'SOFTWARE',
        'outputs': [{'name': side, 'kind': 'Prototype', 'description': 'Prototype de contrat à réaliser, sans service métier en production.'}], 'acceptance': [ref('acceptance')],
        'justified_by': [ref('requirement')], 'resource_demand': [], 'estimate': ref(side + '-estimate')}) for side in ('provider', 'consumer')]
    estimates = [obj('Estimate', side + '-estimate', {'target': ref(side + '-unit'), 'measure': 'effort', 'value_or_distribution': {'value': '1', 'unit': 'person_day'}, 'basis': ['Hypothèse fictive'], 'scope_assumptions': [], 'calibration_class': 'Uncalibrated'}) for side in ('provider', 'consumer')]
    context = obj('DossierContext', 'context', {'scope': ref('scope'), 'catalogue': 'air.completeness-catalogue/1', 'profiles': ['DIGITAL_SERVICE'], 'rationale': 'Deux composants numériques stateless de référence.', 'exclusions': []})
    return [scope, source, criterion, requirement, function, client, actor, contract, case, control, *schema_objects, *blocks, binding, *ports, flow, *units, *estimates, context, specification()]
