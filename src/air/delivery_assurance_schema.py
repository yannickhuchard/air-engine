"""Explicit scoped exit criteria and trace witnesses, not a new approval authority."""
NAMES = ['ScopeGate', 'TraceabilityLink', 'OperationalEvidence']
LAYERS = [
    ['air.Requirement', 'air.QualityRequirement'],
    ['air.BusinessRule', 'air.Constraint', 'air.Policy', 'air.Control'],
    ['air.DataEntity', 'air.DataSchema', 'air.PhysicalTable'],
    ['air.SemanticContract', 'air.InterfaceSpecification'],
    ['air.VerificationCase'],
    ['air.VerificationRun', 'air.OperationalEvidence'],
]


def bodies(record, text, uri, ref, refs, nonempty, instant, artifact):
    metric = record({'name': {'enum': ['RTO', 'RPO', 'ACKNOWLEDGEMENT', 'RECOVERY']},
        'observed_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 31536000},
        'target_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 31536000}})
    return {
        'air.ScopeGate': record({'scope': ref, 'purpose': text, 'members': nonempty,
            'requirements': nonempty, 'depends_on': refs, 'review_required': {'type': 'boolean'},
            'verification_policy': {'enum': ['DESIGN_CONTRACTS', 'RECORDED_TESTS']} }),
        'air.TraceabilityLink': record({'source': ref, 'target': ref, 'rationale': text}),
        'air.OperationalEvidence': record({'case': ref,
            'kind': {'enum': ['CI_CD', 'RECOVERY_TEST', 'RTO_RPO', 'ON_CALL_EXERCISE']},
            'result': {'enum': ['PASS', 'FAIL', 'INCONCLUSIVE']}, 'executed_at': instant,
            'executor': uri, 'environment': ref, 'report': artifact,
            'run_url': {**uri, 'pattern': '^https://[^\\s]+$'}, 'source_revision': text,
            'summary': text, 'metrics': {'type': 'array', 'items': metric, 'maxItems': 8}},
            ['case', 'kind', 'result', 'executed_at', 'executor', 'environment', 'report', 'summary', 'metrics']),
    }


def slots(obj, data_types):
    b, kind = obj['body'], obj['meta']['type']
    if kind == 'air.ScopeGate':
        yield 'body/scope', b['scope'], ['air.Scope']
        for field, allowed in [('members', data_types), ('requirements', LAYERS[0]), ('depends_on', ['air.ScopeGate'])]:
            for i, r in enumerate(b[field]): yield 'body/' + field + '/' + str(i), r, allowed
    elif kind == 'air.TraceabilityLink':
        for field in ('source', 'target'): yield 'body/' + field, b[field], [k for group in LAYERS for k in group]
    elif kind == 'air.OperationalEvidence':
        yield 'body/case', b['case'], ['air.VerificationCase']
        yield 'body/environment', b['environment'], ['air.Environment']


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    for o in objects:
        b, kind = o['body'], o['meta']['type']; identity = o['meta']['id']
        if kind == 'air.TraceabilityLink':
            source, target = [by_ref.get(key(b[f])) for f in ('source', 'target')]
            if source and target and not any(source['meta']['type'] in a and target['meta']['type'] in z for a, z in zip(LAYERS, LAYERS[1:])):
                yield 'AIR_TRACE_LAYER', identity, 'Traceability links connect adjacent requirement, rule, data, API, test and evidence layers in that order'
        if kind == 'air.ScopeGate':
            members = {key(r) for r in b['members']}
            if any(key(r) not in members for r in b['requirements']):
                yield 'AIR_GATE_MEMBERS', identity, 'Every gate requirement belongs to its explicit members'
            if any(by_ref.get(key(r), {}).get('meta', {}).get('type') == 'air.ScopeGate' for r in b['members']):
                yield 'AIR_GATE_MEMBERS', identity, 'Gate dependencies use depends_on, never members'
            queue = list(b['depends_on']); seen = set()
            while queue:
                r = queue.pop(); k = key(r)
                if k == key(o['meta']):
                    yield 'AIR_GATE_CYCLE', identity, 'Scope gate prerequisites must be acyclic'; break
                if k in seen: continue
                seen.add(k); dependency = by_ref.get(k)
                if dependency and dependency['meta']['type'] == 'air.ScopeGate': queue.extend(dependency['body']['depends_on'])
        if kind == 'air.OperationalEvidence':
            case = by_ref.get(key(b['case']))
            if case and case['body'].get('method') != 'TEST':
                yield 'AIR_OPERATIONAL_CASE', identity, 'Operational test evidence references a TEST verification case'
            names = [m['name'] for m in b['metrics']]
            if len(names) != len(set(names)): yield 'AIR_OPERATIONAL_METRICS', identity, 'Metrics are unique by name'
            if b['kind'] == 'RTO_RPO' and not {'RTO', 'RPO'} <= set(names):
                yield 'AIR_OPERATIONAL_METRICS', identity, 'RTO_RPO records both measured RTO and measured RPO'
            if b['kind'] == 'CI_CD' and not all(b.get(f) for f in ('run_url', 'source_revision')):
                yield 'AIR_OPERATIONAL_SOURCE', identity, 'CI/CD evidence identifies the pipeline run and source revision'
            if b['result'] == 'PASS' and any(m['observed_seconds'] > m['target_seconds'] for m in b['metrics']):
                yield 'AIR_OPERATIONAL_RESULT', identity, 'A PASS cannot exceed a declared recovery or response target'
