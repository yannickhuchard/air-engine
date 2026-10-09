"""Bitemporal reads: registry receipt time and declared validity are separate axes."""
from datetime import datetime
import json

from sqlalchemy import select

from air.access import ScopedStore
from air.core import INSTANT, URI, record
from air.expr import artifact_digest
from air.foundation import check_budget, check_schema, InvalidModel
from air.storage import identities, revisions

ENGINE = 'air.bitemporal/1'
MAX_REVISIONS = 4096
REQUEST = record({
    'ids': {'type': 'array', 'items': URI, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
    'known_at': INSTANT, 'valid_at': INSTANT,
})


def reconstruct(store, principal, policy, request):
    """Return a selection, never a closed baseline or an editorial acceptance.

    Highest revision wins only among revisions received by known_at and valid at
    valid_at. recorded_at supplied by an author cannot backdate registry knowledge.
    Access is evaluated under today's policy, including the selected references.
    """
    check_schema(request, REQUEST)
    known, valid = (datetime.fromisoformat(request[k]) for k in ('known_at', 'valid_at'))
    ids = sorted(request['ids'])
    with store.engine.connect() as conn:
        namespaces = conn.execute(select(identities.c.namespace).where(identities.c.id.in_(ids))).scalars()
        for namespace in namespaces:
            policy.require(principal, 'read', namespace)
        rows = conn.execute(select(revisions).where(revisions.c.id.in_(ids))
                            .order_by(revisions.c.id, revisions.c.revision)
                            .limit(MAX_REVISIONS + 1)).mappings().all()
    if len(rows) > MAX_REVISIONS:
        raise InvalidModel('Temporal reconstruction exceeds its revision budget; narrow the identifiers')
    selected = {}
    for row in rows:
        if datetime.fromisoformat(row['stored_at']) > known:
            continue
        obj = json.loads(row['payload'])
        period = obj['meta']['validity']
        if datetime.fromisoformat(period['start']) > valid:
            continue
        if period['end'] is not None and valid >= datetime.fromisoformat(period['end']):
            continue
        selected[row['id']] = {'object': obj, 'digest': row['digest'], 'received_at': row['stored_at']}
    refs = [{'id': identity, 'revision': row['object']['meta']['revision']}
            for identity, row in selected.items()]
    ScopedStore(store, principal, policy).check_read(refs)
    result = {'engine': ENGINE, 'known_at': request['known_at'], 'valid_at': request['valid_at'],
              'selection_policy': 'HIGHEST_RECEIVED_REVISION_VALID_AT_INSTANT',
              'objects': list(selected.values()), 'unavailable_ids': sorted(set(ids) - selected.keys()),
              'closed_baseline': False, 'history_rewritten': False,
              'authority_basis': 'CURRENT_ACCESS_POLICY', 'policy_digest': policy.digest,
              'request_digest': artifact_digest(request)}
    check_budget(result)
    result['report_digest'] = artifact_digest(result)
    return result
