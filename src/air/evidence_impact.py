"""Targeted applicability analysis, without mutating historical proof or review records."""
from collections import deque
from air.access import ScopedStore
from air.core import record, digest, reference_slots
from air.expr import artifact_digest
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot, changes
from air.completeness import snapshot_budget, context_budget

ENGINE = 'air.evidence-impact/1'
TYPES = {'air.VerificationRun', 'air.VerificationCase', 'air.SimulationScenario', 'air.Evidence'}
REQUEST = record({'before': SNAPSHOT, 'after': SNAPSHOT,
    'targets': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True}}, ['before', 'after'])


def pin(obj): return {**exact(obj), 'digest': digest(obj)}


def compare(store, principal, policy, request):
    check_schema(request, REQUEST)
    guarded = ScopedStore(store, principal, policy)
    before, after = [snapshot(guarded, request[k]) for k in ('before', 'after')]
    for exported in (before, after): snapshot_budget(exported)
    old = {key(exact(o)): o for o in before['objects']}
    new = {key(exact(o)): o for o in after['objects']}
    pins = {identity: pin(obj) for identity, obj in {**old, **new}.items()}
    successors_by_id = {}
    for obj in new.values(): successors_by_id.setdefault(obj['meta']['id'], []).append(obj)
    old_ids, new_ids = {}, {}
    for index, groups in ((old, old_ids), (new, new_ids)):
        for identity, obj in index.items(): groups.setdefault(obj['meta']['id'], set()).add((obj['meta']['revision'], pins[identity]['digest']))
    changed = {identity for identity in old_ids.keys() | new_ids.keys() if old_ids.get(identity) != new_ids.get(identity)}
    profile_changed = before['baseline']['body']['profiles'] != after['baseline']['body']['profiles']
    targets = request.get('targets', [pins[identity] for identity, o in old.items() if o['meta']['type'] in TYPES])
    if len(targets) > 256: raise InvalidModel('More than 256 evidence targets; select an explicit subset')
    results = []
    traversed = 0
    for target in sorted(targets, key=key):
        root = old.get(key(target))
        if root is None or pins[key(target)] != target or root['meta']['type'] not in TYPES:
            raise InvalidModel('Evidence targets must be exact proof-related members of the source baseline')
        queue = deque([(key(target), [])]); seen = set(); witnesses = []; unresolved = []
        while queue:
            identity, path = queue.popleft()
            if identity in seen: continue
            seen.add(identity); traversed += 1
            if traversed > 100000: raise InvalidModel('Evidence dependency traversal exceeds 100000 nodes; narrow targets')
            obj = old.get(identity)
            if obj is None:
                unresolved.append({'reference': {'id': identity[0], 'revision': identity[1]}, 'path': path}); continue
            if identity[0] in changed:
                successors = sorted(successors_by_id.get(identity[0], []), key=lambda o: key(exact(o)))
                witnesses.append({'dependency': pins[identity], 'path': path, 'selected_after': [pins[key(exact(o))] for o in successors],
                    'change': 'REMOVED' if not successors else 'RESELECTED',
                    'body_changes': changes(obj['body'], successors[0]['body']) if len(successors) == 1 else [],
                    'ambiguous_successor': len(successors) > 1})
            for field, ref, _ in sorted(reference_slots(obj), key=lambda item: (item[0], key(item[1]))):
                if len(path) >= 64: raise InvalidModel('Evidence dependency path exceeds 64 steps; narrow targets')
                queue.append((key(ref), path + [{'from': exact(obj), 'field': field, 'to': ref}]))
        status = ('IMPACTED' if witnesses or profile_changed else 'INCONCLUSIVE_DEPENDENCIES' if unresolved else 'NO_DECLARED_IMPACT')
        same_baseline = request['before'] == request['after']
        results.append({'target': target, 'name': root['meta']['name'], 'type': root['meta']['type'],
            'declared_result': root['body'].get('result'), 'status': status,
            'changed_dependencies': witnesses, 'unresolved_dependencies': unresolved,
            'dependencies_examined': len(seen), 'profile_changed': profile_changed,
            'applicability': 'SAME_BASELINE_NOT_REQUALIFIED' if same_baseline else 'REQUALIFICATION_REQUIRED',
            'next_action': 'Rejouer ou réinspecter les dépendances modifiées et obtenir la revue requise' if status == 'IMPACTED'
                else 'Compléter les dépendances manquantes' if unresolved else 'Relire l’applicabilité à la nouvelle baseline ; aucun avis reconduit automatiquement'})
        context_budget(results, 4 * 1048576)
    report = {'engine': ENGINE, 'before': request['before'], 'after': request['after'],
        'changed_object_ids': sorted(changed), 'profile_changed': profile_changed, 'evidence': results,
        'summary': {s: sum(r['status'] == s for r in results) for s in ('IMPACTED', 'INCONCLUSIVE_DEPENDENCIES', 'NO_DECLARED_IMPACT')},
        'coverage': 'Selected source-baseline proof objects and their declared reference closure only',
        'proofs_automatically_carried': False, 'historical_records_modified': False,
        'runtime_executed': False, 'authorization_granted': False}
    report['report_digest'] = artifact_digest(report)
    return report


def declared_site(exported):
    """Pure declaration view when no registry comparison was supplied."""
    baseline = {**exact(exported['baseline']), 'digest': exported['digest']}
    inventory = [{'reference': pin(o), 'name': o['meta']['name'], 'type': o['meta']['type'],
        'result': o['body'].get('result'), 'summary': o['body'].get('summary', '')}
        for o in sorted(exported['objects'], key=lambda o: key(exact(o)))
        if o['meta']['type'] in ('air.VerificationRun', 'air.VerificationCase')]
    comparisons = [{'before': ref, 'after': baseline, 'status': 'BLOCKED',
        'diagnostic': 'Comparaison non exécutée dans cette projection sans registre.'}
        for ref in exported['baseline']['body'].get('parent_baselines', [])]
    return {'engine': ENGINE, 'baseline': baseline, 'inventory': inventory, 'comparisons': comparisons,
        'qualification_granted': False, 'historical_records_modified': False, 'authorization_granted': False}


def for_site(store, principal, policy, exported):
    """Compare explicitly registered parents; do not substitute the latest revision."""
    report = declared_site(exported)
    baseline = report['baseline']; comparisons = []
    parents = exported['baseline']['body'].get('parent_baselines', [])
    if len(parents) > 8: raise InvalidModel('Proof site compares at most eight explicitly declared parent baselines')
    for ref in sorted(parents, key=key):
        old = ScopedStore(store, principal, policy).export_baseline(ref)
        origin = {**ref, 'digest': old['digest']}
        try: result = compare(store, principal, policy, {'before': origin, 'after': baseline})
        except InvalidModel as exc: result = {'before': origin, 'after': baseline, 'status': 'BLOCKED', 'diagnostic': str(exc)}
        comparisons.append(result)
    report['comparisons'] = comparisons
    context_budget(report, 8 * 1048576)
    return {**report, 'report_digest': artifact_digest(report)}
