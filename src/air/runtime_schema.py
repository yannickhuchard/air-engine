"""Explicit runtime observation subset of white paper A.12, with partial coverage."""
from datetime import datetime
from air.expr import typed, wire, ExprError

PROFILE = 'air.runtime/0.12'
NAMES = ['RuntimeObservation', 'Drift', 'Incident']


def bodies(record, text, ref, refs, nonempty, instant, artifact):
    period = record({'start': instant, 'end': instant})
    value = record({'type': text, 'state': {'enum': ['KNOWN', 'UNKNOWN', 'CONFLICTING']}, 'value': {}}, ['type'])
    coverage = record({'scope': ref, 'included': nonempty, 'excluded': refs,
        'completeness': {'const': 'PARTIAL'}, 'limitations': {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 256}})
    artifact = {**artifact, 'properties': {**artifact['properties'], 'media_type': text}}
    return {
        'air.RuntimeObservation': record({'instance_or_scope': ref, 'metric_or_signal': {'oneOf': [text, ref]}, 'window': period,
            'value_or_artifact': {'oneOf': [value, artifact]}, 'coverage': coverage}),
        'air.Drift': record({'expected': ref, 'observed': nonempty, 'comparison_method': text, 'impact': text,
            'treatment': ref}, ['expected', 'observed', 'comparison_method', 'impact']),
        'air.Incident': record({'affected_scope': ref, 'occurrence': period, 'description': text,
            'observations': refs, 'resolution': text, 'learning': refs}, ['affected_scope', 'occurrence', 'description', 'observations', 'learning']),
    }


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.RuntimeObservation':
        yield 'body/instance_or_scope', body['instance_or_scope'], ['air.Scope']
        if isinstance(body['metric_or_signal'], dict): yield 'body/metric_or_signal', body['metric_or_signal'], ['air.Metric']
        yield 'body/coverage/scope', body['coverage']['scope'], ['air.Scope']
        for field in ('included', 'excluded'):
            for ref in body['coverage'][field]: yield 'body/coverage/' + field, ref, data_types
        value = body['value_or_artifact']
        if 'type' in value:
            try: typed(value)
            except ExprError: return
        if value.get('state', 'KNOWN') == 'KNOWN' and value.get('type') == 'Reference':
            yield 'body/value_or_artifact/value', value['value'], data_types
        if value.get('type') == 'Collection[Reference]' and value.get('state', 'KNOWN') == 'KNOWN':
            for item in value['value']:
                if item.get('state', 'KNOWN') == 'KNOWN': yield 'body/value_or_artifact/value', item['value'], data_types
    elif kind == 'air.Drift':
        yield 'body/expected', body['expected'], data_types
        for ref in body['observed']: yield 'body/observed', ref, ['air.RuntimeObservation']
        if 'treatment' in body: yield 'body/treatment', body['treatment'], ['air.Contribution', 'air.Decision']
    elif kind == 'air.Incident':
        yield 'body/affected_scope', body['affected_scope'], ['air.Scope']
        for ref in body['observations']: yield 'body/observations', ref, ['air.RuntimeObservation']
        for ref in body['learning']: yield 'body/learning', ref, data_types


def local_issues(obj):
    kind, body = obj['meta']['type'], obj['body']
    field = {'air.RuntimeObservation': 'window', 'air.Incident': 'occurrence'}.get(kind)
    if field and datetime.fromisoformat(body[field]['end']) <= datetime.fromisoformat(body[field]['start']):
        yield 'AIR_RUNTIME_WINDOW', 'Observation and incident windows must be nonempty [start, end) intervals'
    if kind == 'air.RuntimeObservation':
        if not obj['meta']['provenance']['source_refs']: yield 'AIR_RUNTIME_PROVENANCE', 'A runtime observation requires an exact source reference'
        coverage = body['coverage']
        identity = lambda ref: (ref['id'], ref['revision'])
        if coverage['scope'] != body['instance_or_scope']: yield 'AIR_RUNTIME_COVERAGE', 'The coverage scope must be the observed scope'
        if {identity(r) for r in coverage['included']} & {identity(r) for r in coverage['excluded']}:
            yield 'AIR_RUNTIME_COVERAGE', 'A reference cannot be both covered and excluded'
        value = body['value_or_artifact']
        if 'type' in value:
            try: typed(value)
            except ExprError as error: yield error.code, str(error)


def canonicalize(obj):
    kind, body = obj['meta']['type'], obj['body']
    key = lambda ref: (ref['id'], ref['revision'])
    if kind == 'air.RuntimeObservation':
        for field in ('included', 'excluded'): body['coverage'][field].sort(key=key)
        value = body['value_or_artifact']
        if 'type' in value: body['value_or_artifact'] = wire(typed(value))
    for field in {'air.Drift': ['observed'], 'air.Incident': ['observations', 'learning']}.get(kind, []): body[field].sort(key=key)
