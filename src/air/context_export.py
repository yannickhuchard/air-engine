"""Explicit destination-bound context exports. Never contacts a model or redacts by guesswork."""
from datetime import datetime, timezone
import hashlib
from air.access import Forbidden, ScopedStore
from air.builder_handoff import commit_guard
from air.core import record, TEXT, digest, reference_slots
from air.expr import artifact_digest
from air.foundation import check_schema, key, InvalidModel
from air.packages import reference
from air.projections import SNAPSHOT, snapshot
from air.completeness import context_budget

REQUEST = record({'baseline': SNAPSHOT,
    'roots': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
    'destination': {**TEXT, 'maxLength': 128}, 'purpose': {**TEXT, 'maxLength': 128},
    'idempotency_key': {**TEXT, 'maxLength': 128}})
ENGINE = 'air.context-export/1'


def prepare(store, principal, policy, request, settings=None):
    check_schema(request, REQUEST)
    document = policy.document or {}
    binding = document.get('subjects', {}).get(principal['subject'], {}).get('model_context')
    if binding and binding != {k: request[k] for k in ('destination', 'purpose')}:
        raise Forbidden('A model identity cannot change its configured destination or purpose')
    grants = document.get('subjects', {}).get(principal['subject'], {}).get('context_destinations', [])
    matches = [g for g in grants if g['id'] == request['destination'] and request['purpose'] in g['purposes']]
    if len(matches) != 1:
        raise Forbidden('A unique explicit destination and purpose grant is required')
    grant = matches[0]
    if datetime.fromisoformat(grant['expires_at']) <= datetime.now(timezone.utc):
        raise Forbidden('Context destination grant expired')
    # Read the pinned index internally, then authorize only the selected closure.
    # A non-selected restricted object must neither leak nor prevent minimization.
    exported = snapshot(store, request['baseline'])
    policy.require(principal, 'read', exported['baseline']['meta']['namespace'])
    ScopedStore(store, principal, policy).check_read(request['roots'])
    by = {key(o['meta']): o for o in exported['objects']}
    selected = {}; pending = list(request['roots'])
    while pending:
        ref = pending.pop(); k = key(ref)
        obj = by.get(k)
        if obj is None or ('digest' in ref and ref['digest'] != digest(obj)):
            raise InvalidModel('Context root or dependency is outside the exact baseline')
        if k in selected: continue
        policy.require(principal, 'export_context', obj['meta']['namespace'])
        if obj['meta']['classification']['level'] not in grant['classifications']:
            raise Forbidden('Context classification is outside the destination grant')
        selected[k] = obj
        if len(selected) > 4096: raise InvalidModel('Context closure exceeds 4096 objects')
        pending.extend(r for _, r, _ in reference_slots(obj))
    objects = [selected[k] for k in sorted(selected)]
    content = {'baseline': request['baseline'], 'objects': objects}
    context_budget(content, 1048576)
    summary = {'engine': ENGINE, 'request': {**request, 'roots': sorted(request['roots'], key=key)},
        'content_digest': artifact_digest(content), 'policy_digest': policy.digest,
        'references': [{**{f: o['meta'][f] for f in ('id', 'revision')}, 'digest': digest(o)} for o in objects],
        'classifications': sorted({o['meta']['classification']['level'] for o in objects}),
        'actor': principal['subject'], 'external_transfer_executed': False,
        'transformation': 'EXACT_SELECTED_REFERENCE_CLOSURE', 'secret_discovery_performed': False}
    identifier = 'urn:air:context-export:' + hashlib.sha256((principal['subject'] + '\0' + request['idempotency_key']).encode()).hexdigest()
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        if datetime.fromisoformat(grant['expires_at']) <= datetime.now(timezone.utc):
            raise Forbidden('Context destination grant expired before export')
        row = store._record_once(conn, identifier, 'context_export', exported['baseline']['meta']['namespace'],
            principal['subject'], summary)['record']
    return {'engine': ENGINE, 'receipt': reference(row), 'summary': summary, 'content': content,
        'external_transfer_executed': False, 'unmanaged_client_reads_controlled': False,
        'context_returned_to_authenticated_caller': True, 'destination_transport_attested': False,
        'limits': ['This grant applies to this explicit export workflow',
                   'Client file reads and existing read APIs remain subject to their own boundaries',
                   'An exported copy cannot be remotely revoked']}
