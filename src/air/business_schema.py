"""Explicit draft intentions, goals, stakeholders, capabilities and business services."""
from datetime import datetime
from air.expr import typed, wire, ExprError

PROFILE = 'air.business/0.15'
NAMES = ['Metric', 'Goal', 'Intent', 'Concern', 'Stakeholder', 'Capability', 'BusinessService', 'Product']


def bodies(record, text, uri, ref, refs, nonempty, instant):
    unit = {'type': 'string', 'pattern': '^(?:1|[A-Za-z][A-Za-z0-9_/-]{0,31})$'}
    value = record({'type': text, 'state': {'enum': ['KNOWN', 'UNKNOWN', 'CONFLICTING']}, 'value': {}}, ['type'])
    target = record({'id': {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'}, 'metric': ref,
        'operator': {'enum': ['EQ', 'LTE', 'GTE']}, 'value': value, 'unit': unit, 'context': ref})
    return {
        'air.Metric': record({'definition': text, 'unit': unit, 'aggregation': text, 'population': text,
            'window': {'type': 'string', 'pattern': '^PT[1-9][0-9]{0,7}S$'}, 'collection_method': text},
            ['definition', 'unit', 'aggregation', 'population', 'collection_method']),
        'air.Goal': record({'outcome': text, 'measures': nonempty, 'targets': {'type': 'array', 'items': target, 'minItems': 1, 'maxItems': 32},
            'horizon': record({'start': instant, 'end': instant})}, ['outcome', 'measures', 'targets']),
        'air.Intent': record({'desired_change': text, 'sponsor': uri, 'scope': ref, 'goals': nonempty}),
        'air.Concern': record({'question': text, 'scope': ref, 'addressed_by': {**refs, 'maxItems': 256}}),
        'air.Stakeholder': record({'identity_or_group': uri, 'concerns': nonempty, 'participation_role': text}),
        'air.Capability': record({'ability': text, 'outcomes': refs, 'required_functions': nonempty, 'context': ref, 'maturity_evidence': refs}),
        'air.BusinessService': record({'beneficiaries': nonempty, 'value_proposition': text, 'capabilities': nonempty, 'service_commitments': nonempty}),
        'air.Product': record({'offer': text, 'market_scope': ref, 'services': refs, 'lifecycle_owner': uri}),
    }

MANY = {
    'air.Goal': {'measures': ['air.Metric']}, 'air.Intent': {'goals': ['air.Goal']},
    'air.Concern': {'addressed_by': ['air.Viewpoint']}, 'air.Stakeholder': {'concerns': ['air.Concern']},
    'air.Capability': {'outcomes': ['air.Goal'], 'required_functions': ['air.Function']},
    'air.BusinessService': {'beneficiaries': ['air.Actor'], 'capabilities': ['air.Capability'], 'service_commitments': ['air.SemanticContract']},
    'air.Product': {'services': ['air.BusinessService']},
}
ONE = {'air.Intent': {'scope': ['air.Scope']}, 'air.Concern': {'scope': ['air.Scope']},
       'air.Capability': {'context': ['air.Scope']}, 'air.Product': {'market_scope': ['air.Scope']}}


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    for field, kinds in MANY.get(kind, {}).items():
        for ref in body[field]: yield 'body/' + field, ref, kinds
    for field, kinds in ONE.get(kind, {}).items(): yield 'body/' + field, body[field], kinds
    if kind == 'air.Capability':
        for ref in body['maturity_evidence']: yield 'body/maturity_evidence', ref, data_types
    if kind == 'air.Goal':
        for target in body['targets']:
            yield 'body/targets/' + target['id'] + '/metric', target['metric'], ['air.Metric']
            yield 'body/targets/' + target['id'] + '/context', target['context'], ['air.Scope']


def target_issues(target):
    try: value = typed(target['value'])
    except ExprError as exc:
        yield exc.code, str(exc);return
    if value.type not in ('Boolean', 'Decimal') and not value.type.startswith('Quantity['):
        yield 'AIR_GOAL_VALUE', 'Goal targets support Boolean, Decimal or Quantity values only';return
    unit = value.type[9:-1] if value.type.startswith('Quantity[') else '1'
    if target['unit'] != unit: yield 'AIR_GOAL_UNIT', 'Target unit differs from its exact value type'
    if value.type == 'Boolean' and target['operator'] != 'EQ': yield 'AIR_GOAL_OPERATOR', 'Boolean targets require equality'


def local_issues(obj):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.Metric' and 'window' in body and int(body['window'][2:-1]) > 31622400:
        yield 'AIR_METRIC_WINDOW', 'Metric sample windows are bounded to 366 days'
    if kind == 'air.Goal':
        ids = [target['id'] for target in body['targets']]
        if len(set(ids)) != len(ids): yield 'AIR_GOAL_TARGET_ID', 'Goal target identifiers must be unique'
        measures = {(ref['id'], ref['revision']) for ref in body['measures']}
        for target in body['targets']:
            yield from target_issues(target)
            if (target['metric']['id'], target['metric']['revision']) not in measures:
                yield 'AIR_GOAL_METRIC', 'Every target metric must occur in the exact measures set'
        if 'horizon' in body and datetime.fromisoformat(body['horizon']['end']) <= datetime.fromisoformat(body['horizon']['start']):
            yield 'AIR_GOAL_HORIZON', 'Goal horizons must be nonempty [start, end) intervals'


def graph_issues(obj, by_ref):
    if obj['meta']['type'] == 'air.Goal':
        for target in obj['body']['targets']:
            ref = target['metric'];metric = by_ref.get((ref['id'], ref['revision']))
            if metric and metric['meta']['type'] == 'air.Metric' and metric['body']['unit'] != target['unit']:
                yield 'AIR_GOAL_METRIC_UNIT', 'Target unit differs from the pinned metric unit'


def canonicalize(obj):
    body, kind = obj['body'], obj['meta']['type']
    for field in MANY.get(kind, {}): body[field].sort(key=lambda ref: (ref['id'], ref['revision']))
    if kind == 'air.Capability': body['maturity_evidence'].sort(key=lambda ref: (ref['id'], ref['revision']))
    if kind == 'air.Goal':
        body['targets'].sort(key=lambda target: target['id'])
        for target in body['targets']: target['value'] = wire(typed(target['value']))
