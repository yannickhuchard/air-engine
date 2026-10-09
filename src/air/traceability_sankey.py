"""Sankey of explicit reference joins. Width is normalized trace paths, never money."""
from collections import defaultdict
from fractions import Fraction
from air.core import digest
from air.expr import artifact_digest
from air.foundation import exact, TooLarge

ENGINE = 'air.traceability-sankey/1'
MAX_PATHS = 20000


def project(g):
    nodes = {}; paths = []; gaps = []; exclusions = []
    key = lambda r: (r['id'], r['revision'])

    def node(o, layer, suffix='', label=None, kind=None):
        ref = exact(o); identity = artifact_digest({'reference': ref, 'suffix': suffix, 'layer': layer})
        nodes.setdefault(identity, {'id': identity, 'layer': layer, 'name': label or o['meta']['name'],
            'kind': kind or o['meta']['type'][4:], 'reference': ref, 'object_digest': digest(o), 'field': suffix or None})
        return identity

    def missing(req, layer, label):
        identity = artifact_digest({'gap': exact(req), 'layer': layer, 'label': label})
        nodes.setdefault(identity, {'id': identity, 'layer': layer, 'name': label, 'kind': 'GAP', 'reference': None})
        return identity

    def evidence(o, field, target, status=None):
        return {'source': exact(o), 'source_digest': digest(o), 'field': field, 'target': target, 'status': status}

    def refs(o, field, target):
        return [evidence(o, 'body/' + field + '/' + str(i), r) for i, r in enumerate(o['body'].get(field, [])) if key(r) == key(exact(target))]

    blocks = g.of('ArchitectureBlock'); units = g.of('ConstructionUnit')
    runtimes = [r for r in g.of('RuntimeComponent') if g.get(r['body']['environment']) and g.get(r['body']['environment'])['body']['stage'] == 'PRODUCTION']

    unit_cache = {}
    def unit_blocks(unit):
        identity = key(exact(unit))
        if identity in unit_cache: return unit_cache[identity]
        result = []
        for b in blocks:
            for fref in unit['body']['realizes']:
                f = g.get(fref)
                if f and f['meta']['type'] == 'air.Function' and refs(b, 'functions', f):
                    result.append((b, refs(unit, 'realizes', f) + refs(b, 'functions', f)))
            for runtime in runtimes:
                if refs(runtime, 'realizes', unit) and refs(runtime, 'realizes', b):
                    result.append((b, refs(runtime, 'realizes', unit) + refs(runtime, 'realizes', b)))
        unit_cache[identity] = result
        return result

    def target_blocks(target):
        if target['meta']['type'] == 'air.ArchitectureBlock': return [(target, [])]
        if target['meta']['type'] == 'air.ConstructionUnit': return unit_blocks(target)
        if target['meta']['type'] == 'air.RuntimeComponent':
            result = []
            for r in target['body'].get('realizes', []):
                obj = g.get(r)
                if obj and obj['meta']['type'] in ('air.ArchitectureBlock', 'air.ConstructionUnit'):
                    result += [(b, refs(target, 'realizes', obj) + ev) for b, ev in target_blocks(obj)]
            return result
        if target['meta']['type'] == 'air.Device':
            return [(b, refs(target, 'hosts', g.get(r)) + ev) for r in target['body'].get('hosts', []) if g.get(r)
                for b, ev in target_blocks(g.get(r))]
        return []

    requirements = g.of('Requirement') + g.of('QualityRequirement')
    for req in requirements:
        applicable = [m for m in g.of('ComplianceMapping') if key(m['body']['subject']) == key(exact(req))]
        if applicable and all(m['body']['status'] == 'NOT_APPLICABLE' for m in applicable):
            exclusions.append({'reference': exact(req), 'mappings': [exact(m) for m in applicable], 'reason': 'NOT_APPLICABLE_DECLARED'})
            continue
        rid = node(req, 0, kind='FUNCTIONAL' if req['body'].get('kind') == 'FUNCTIONAL' else 'NON_FUNCTIONAL')
        seeds = []
        for f in g.of('Function'):
            if refs(f, 'satisfies', req):
                for block in blocks:
                    if refs(block, 'functions', f): seeds.append((block, refs(f, 'satisfies', req) + refs(block, 'functions', f)))
        for unit in units:
            if refs(unit, 'justified_by', req): seeds += [(b, refs(unit, 'justified_by', req) + ev) for b, ev in unit_blocks(unit)]
        for mapping in applicable:
            if mapping['body']['status'] == 'NOT_APPLICABLE': continue
            for i, ref in enumerate(mapping['body'].get('implemented_by', [])):
                target = g.get(ref)
                if target:
                    seeds += [(b, [evidence(mapping, 'body/subject', exact(req), mapping['body']['status']),
                        evidence(mapping, 'body/implemented_by/' + str(i), ref, mapping['body']['status'])] + ev) for b, ev in target_blocks(target)]
        branches = []
        # Same block reached by multiple declared joins: retain every witness, one visual branch.
        grouped = defaultdict(list)
        for b, ev in seeds: grouped[key(exact(b))].extend(ev)
        for bkey, seed in sorted(grouped.items()):
            block = g.by_ref[bkey]; bid = node(block, 1); targets = 0; deliveries = 0
            for unit in units:
                associations = [ev for b, ev in unit_blocks(unit) if key(exact(b)) == bkey]
                if not associations: continue
                # Sharing a block does not make an unrelated functional unit
                # a delivery of this requirement. Retain the exact function or justification.
                if req['meta']['type'] == 'air.Requirement' and req['body'].get('kind') == 'FUNCTIONAL':
                    satisfies = any(g.get(r) and g.get(r)['meta']['type'] == 'air.Function'
                        and refs(g.get(r), 'satisfies', req) and refs(block, 'functions', g.get(r)) for r in unit['body']['realizes'])
                    if not refs(unit, 'justified_by', req) and not satisfies: continue
                deliveries += 1
                uid = node(unit, 2); witnesses = seed + [e for ev in associations for e in ev]
                for i, output in enumerate(unit['body']['outputs']):
                    oid = node(unit, 3, 'body/outputs/' + str(i), output['name'], output['kind'])
                    branches.append(([rid, bid, uid, oid], witnesses + [evidence(unit, 'body/outputs/' + str(i), output)], 'DECLARED_DELIVERABLE_OUTPUT'));targets += 1
                for runtime in runtimes:
                    if refs(runtime, 'realizes', unit):
                        branches.append(([rid, bid, uid, node(runtime, 3)], witnesses + refs(runtime, 'realizes', unit), 'PLANNED_PRODUCTION_COMPONENT'));targets += 1
                if not unit['body']['outputs'] and not any(refs(r, 'realizes', unit) for r in runtimes):
                    branches.append(([rid, bid, uid, missing(req, 3, 'Sortie non tracée')], witnesses, 'GAP'));targets += 1
                    gaps.append({'requirement': exact(req), 'block': exact(block), 'unit': exact(unit), 'reason': 'OUTPUT_MISSING'})
            if not deliveries:
                gaps.append({'requirement': exact(req), 'block': exact(block), 'reason': 'CONSTRUCTION_UNIT_MISSING'})
            for runtime in runtimes:
                if refs(runtime, 'realizes', block):
                    branches.append(([rid, bid, node(runtime, 3)], seed + refs(runtime, 'realizes', block), 'PLANNED_PRODUCTION_COMPONENT'));targets += 1
            if not targets:
                branches.append(([rid, bid, missing(req, 2, 'Livraison non tracée'), missing(req, 3, 'Cible non tracée')], seed, 'GAP'))
                gaps.append({'requirement': exact(req), 'block': exact(block), 'reason': 'DELIVERY_AND_TARGET_MISSING'})
        if not branches:
            branches.append(([rid] + [missing(req, i, label) for i, label in enumerate(['Bloc non tracé', 'Livraison non tracée', 'Cible non tracée'], 1)], [], 'GAP'))
            gaps.append({'requirement': exact(req), 'reason': 'ARCHITECTURE_BLOCK_MISSING'})
        if len(paths) + len(branches) > MAX_PATHS: raise TooLarge('Sankey exceeds 20000 trace paths; split the dossier')
        weight = Fraction(1, len(branches))
        for chain, witnesses, status in branches:
            unique = {artifact_digest(e): e for e in witnesses}
            paths.append({'nodes': chain, 'weight': {'numerator': weight.numerator, 'denominator': weight.denominator},
                'evidence': [unique[k] for k in sorted(unique)], 'status': status})
    flows = defaultdict(Fraction)
    for path in paths:
        w = Fraction(**path['weight'])
        for a, b in zip(path['nodes'], path['nodes'][1:]): flows[(a, b)] += w
    result = {'engine': ENGINE, 'nodes': sorted(nodes.values(), key=lambda n: (n['layer'], n['name'], n['id'])), 'paths': paths,
        'links': [{'source': a, 'target': b, 'value': {'numerator': w.numerator, 'denominator': w.denominator}} for (a, b), w in sorted(flows.items())],
        'gaps': gaps, 'exclusions': exclusions, 'requirements': len(requirements),
        'weight_semantics': 'ONE_UNIT_PER_APPLICABLE_REQUIREMENT_SPLIT_EQUALLY_OVER_DECLARED_TRACE_PATHS',
        'relation_semantics': 'EXPLICIT_REFERENCE_JOINS_NOT_EXECUTION_PROOF', 'business_execution_performed': False}
    result['projection_digest'] = artifact_digest(result)
    return result
