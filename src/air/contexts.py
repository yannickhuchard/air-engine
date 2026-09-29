"""Immutable observations of explicit local contributions and bounded reconciliation."""
from copy import deepcopy
from air.access import ScopedStore
from air.core import TEXT, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact
from air.packages import RECORD_REF, lock_registry, publication_tree, reference, required
from air.projections import changes, snapshot
from air.reviews import record_key
from air.storage import Conflict, now

ENGINE = 'air.context-reconciliation/0.8'
REQUEST = record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'publications': {'type': 'array', 'items': RECORD_REF, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True},
    'purpose': TEXT})
READ = record({'context': RECORD_REF})


def check_context_access(store, principal, policy, row):
    guarded = ScopedStore(store, principal, policy)
    for contribution in row['payload']['contributions']:
        snapshot(guarded, contribution['manifest']['baseline'])


def create_context(store, principal, policy, request):
    check_schema(request, REQUEST)
    request = deepcopy(request);request['publications'].sort(key=lambda r: (r['id'], r['digest']))
    record_id = record_key('context', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        lock_registry(conn)
        prior = store._get_record(conn, record_id)
        if prior is not None:
            if prior['payload']['request'] != request: raise Conflict('Context idempotency key was reused')
            check_context_access(store, principal, policy, prior)
            return {'context': reference(prior), 'snapshot': prior['payload'], 'created': False, 'authorization_granted': False}
        pending, visited, contributions = list(request['publications']), set(), []
        while pending:
            ref = pending.pop()
            witness = (ref['id'], ref['digest'])
            if witness in visited: continue
            visited.add(witness)
            if len(visited) > 256: raise InvalidModel('Context closure exceeds 256 publications')
            row, reasons = publication_tree(store, conn, principal, policy, ref, False)
            manifest = row['payload']['manifest']
            contributions.append({'publication': ref, 'manifest': manifest, 'namespace': row['scope'],
                'publisher': row['actor'], 'published_at': row['created_at'], 'new_use_allowed_at_observation': not reasons,
                'ineffective_reasons_at_observation': reasons})
            pending.extend(manifest['imports'])
        contributions.sort(key=lambda c: c['publication']['id'])
        payload = {'engine': ENGINE, 'request': request, 'observed_at': now(), 'policy_digest': policy.digest,
            'contributions': contributions, 'coverage': {'mode': 'EXPLICIT_PUBLICATIONS_AND_IMPORTS',
                'whole_enterprise_complete': False, 'remote_sources_consulted': False, 'business_freshness': 'NOT_EVALUATED'},
            'authorization_granted': False}
        from air.expr import bounded
        try: bounded(payload)
        except ValueError as exc: raise InvalidModel('Context snapshot exceeds the 1 MiB budget') from exc
        result = store._record_once(conn, record_id, 'context_snapshot', contributions[0]['namespace'], principal['subject'], payload)
    return {'context': reference(result['record']), 'snapshot': result['record']['payload'], 'created': result['created'], 'authorization_granted': False}


def read_context(store, principal, policy, request):
    check_schema(request, READ)
    with store.engine.connect() as conn:
        row = required(store, conn, request['context'], 'context_snapshot')
        check_context_access(store, principal, policy, row)
        return {'context': reference(row), 'snapshot': row['payload'], 'historical': True,
                'current_policy_matches_observation': row['payload']['policy_digest'] == policy.digest,
                'authorization_granted': False}


def reconcile(store, principal, policy, request):
    context = read_context(store, principal, policy, request)
    payload = context['snapshot']
    if payload['engine'] != ENGINE: raise InvalidModel('Historical context needs its declared reconciliation engine')
    guarded = ScopedStore(store, principal, policy)
    selected, objects, observations, seen_observations = {}, {}, [], set()
    for contribution in payload['contributions']:
        publication = contribution['publication']
        baseline = snapshot(guarded, contribution['manifest']['baseline'])
        if not contribution['new_use_allowed_at_observation']:
            observations.append({'code': 'CONTRIBUTION_UNAVAILABLE', 'publication': publication,
                'reasons': contribution['ineffective_reasons_at_observation'], 'resolution': 'REVIEW_REQUIRED'})
        for obj in baseline['objects']:
            object_id = obj['meta']['id'];ref = exact(obj)
            selected.setdefault(object_id, {}).setdefault(obj['meta']['revision'], []).append(publication)
            objects[(object_id, obj['meta']['revision'])] = obj
            if len(objects) > 4096: raise InvalidModel('Reconciliation exceeds 4096 object revisions')
            marker = (object_id, obj['meta']['revision'])
            if marker in seen_observations: continue
            seen_observations.add(marker)
            body = obj['body']
            if obj['meta']['type'] == 'air.Assertion' and body['epistemic_status'] == 'CONTESTED':
                observations.append({'code': 'CONTESTED_ASSERTION', 'object': ref, 'resolution': 'REVIEW_REQUIRED'})
            if obj['meta']['type'] == 'air.Unknown' and body['state'] != 'RESOLVED':
                observations.append({'code': 'OPEN_UNKNOWN', 'object': ref, 'blocking_policy': body['blocking_policy'], 'resolution': 'REVIEW_REQUIRED'})
    divergences = []
    for object_id, revisions in sorted(selected.items()):
        ordered = sorted(revisions)
        if len(ordered) <= 1: continue
        comparisons = []
        for before, after in zip(ordered, ordered[1:]):
            comparisons.append({'before': {'id': object_id, 'revision': before}, 'after': {'id': object_id, 'revision': after},
                'changes': changes(objects[(object_id, before)], objects[(object_id, after)])})
        divergences.append({'code': 'SHARED_IDENTITY_VERSION_DIVERGENCE', 'id': object_id,
            'versions': [{'revision': revision, 'contributions': revisions[revision]} for revision in ordered],
            'comparisons': comparisons, 'semantic_compatibility': 'NOT_EXECUTED', 'resolution': 'REVIEW_REQUIRED'})
    report = {'engine': ENGINE, 'context': request['context'], 'observed_at': payload['observed_at'],
        'coverage': payload['coverage'], 'object_revisions_examined': len(objects), 'divergences': divergences,
        'observations': observations, 'result': 'UNKNOWN', 'decision': 'REVIEW_REQUIRED',
        'checks_not_executed': ['semantic-contract-compatibility', 'committed-capacity-overlap', 'authority-arbitration', 'external-data-boundaries'],
        'source_mutations': False, 'authorization_granted': False}
    import rfc8785
    if len(rfc8785.dumps(report)) > 8 * 1024 * 1024: raise InvalidModel('Reconciliation output exceeds 8 MiB')
    return {**report, 'digest': artifact_digest(report)}
