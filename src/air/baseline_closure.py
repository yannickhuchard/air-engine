"""Transitive closure of exact references inside pinned baselines: what a dependent baseline must contain.

A baseline is closed, so referencing one object of another project pulls in everything that object references.
This service computes that set from pinned source baselines, read through the caller's policy. It writes nothing:
the members it returns are a proposal for a baseline request, never a baseline.
"""
from collections import deque
from air.access import ScopedStore
from air.core import REF, record, reference_slots
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.baseline-closure/0.30'
MAX_MEMBERS = 4096
REQUEST = record({'roots': {'type': 'array', 'items': REF, 'minItems': 1, 'maxItems': 1024, 'uniqueItems': True},
                  'sources': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True}})


def compute_closure(store, principal, policy, request):
    check_schema(request, REQUEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel('Closure request exceeds its budget') from exc
    guarded = ScopedStore(store, principal, policy)
    pool, sources = {}, []
    for ref in sorted(request['sources'], key=key):
        exported = snapshot(guarded, ref)
        for obj in exported['objects']: pool.setdefault(key(exact(obj)), obj)
        sources.append({'baseline': ref, 'objects': len(exported['objects'])})
    roots = [{'id': r['id'], 'revision': r['revision']} for r in request['roots']]
    selected, unresolved, queue = {}, [], deque(roots)
    while queue:
        ref = queue.popleft();identity = key(ref)
        if identity in selected: continue
        obj = pool.get(identity)
        if obj is None:
            unresolved.append({'id': identity[0], 'revision': identity[1]})
            continue
        selected[identity] = obj
        if len(selected) > MAX_MEMBERS: raise InvalidModel('Closure exceeds 4096 members; narrow the roots or the sources')
        for _, link, _ in reference_slots(obj): queue.append(link)
        for link in obj['meta']['provenance']['source_refs']: queue.append(link)
    by_namespace, by_type = {}, {}
    for identity, obj in selected.items():
        by_namespace[obj['meta']['namespace']] = by_namespace.get(obj['meta']['namespace'], 0) + 1
        by_type[obj['meta']['type']] = by_type.get(obj['meta']['type'], 0) + 1
    missing_roots = [r for r in unresolved if key(r) in {key(x) for x in roots}]
    report = {'engine': ENGINE, 'sources': sources, 'roots': sorted(roots, key=key),
              'members': [{'id': i, 'revision': r} for i, r in sorted(selected)],
              'members_count': len(selected), 'roots_not_found': sorted(missing_roots, key=key),
              'by_namespace': [{'namespace': ns, 'objects': n} for ns, n in sorted(by_namespace.items())],
              'by_type': [{'type': t, 'objects': n} for t, n in sorted(by_type.items())],
              'unresolved_references': sorted({(r['id'], r['revision']) for r in unresolved}) and
                                      [{'id': i, 'revision': r} for i, r in sorted({(x['id'], x['revision']) for x in unresolved})],
              'complete': not unresolved, 'registry_written': False, 'baseline_created': False, 'authorization_granted': False}
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Closure report exceeds its budget') from exc
    return report
