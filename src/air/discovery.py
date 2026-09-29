"""Authorized local package discovery with opaque, stable snapshot pagination."""
from copy import deepcopy
from sqlalchemy import select
from air.access import Forbidden
from air.core import record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema
from air.packages import RECORD_REF, identifier, lock_registry, publication_tree, reference, required
from air.storage import service_records

REQUEST = record({'namespace': {'type': 'string', 'pattern': '^[a-z][a-z0-9_.-]{0,127}$'},
    'include_unavailable': {'type': 'boolean'},
    'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 20},
    'cursor': {'anyOf': [RECORD_REF, {'type': 'null'}]}})
SCAN_BUDGET = 100


def discover(store, principal, policy, request):
    check_schema(request, REQUEST)
    scope, actor = request['namespace'], principal['subject']
    policy.require(principal, 'read', scope)
    query = {k: request[k] for k in ('namespace', 'include_unavailable', 'page_size')}
    with store.write() as conn:
        lock_registry(conn)
        if request['cursor'] is None:
            ids = list(conn.execute(select(service_records.c.id).where(service_records.c.kind == 'package_publication',
                service_records.c.scope == scope).order_by(service_records.c.id).limit(10001)).scalars())
            if len(ids) > 10000: raise InvalidModel('Discovery namespace exceeds the 10000 publication snapshot budget')
            payload = {'query': query, 'policy_digest': policy.digest, 'ids': ids}
            snapshot_id = identifier('discovery', actor, artifact_digest(payload))
            source = store._record_once(conn, snapshot_id, 'discovery_snapshot', scope, actor, payload)['record']
            offset = 0
        else:
            cursor = required(store, conn, request['cursor'], 'discovery_cursor')
            if cursor['actor'] != actor or cursor['scope'] != scope: raise Forbidden('Discovery cursor belongs to another subject or namespace')
            source = required(store, conn, cursor['payload']['snapshot'], 'discovery_snapshot')
            if source['actor'] != actor: raise Forbidden('Discovery snapshot belongs to another subject')
            if source['payload']['query'] != query or source['payload']['policy_digest'] != policy.digest:
                raise InvalidModel('Discovery query or policy changed; start a new discovery')
            offset = cursor['payload']['offset'];ids = source['payload']['ids']
        results, scanned = [], 0
        while offset < len(ids) and scanned < SCAN_BUDGET and len(results) < request['page_size']:
            record_id = ids[offset];offset += 1;scanned += 1
            row = store._get_record(conn, record_id)
            if row is None: raise InvalidModel('Discovery snapshot source is no longer retained')
            try:
                publication, reasons = publication_tree(store, conn, principal, policy, reference(row), False)
            except Forbidden:
                continue
            if reasons and not request['include_unavailable']: continue
            manifest = publication['payload']['manifest']
            results.append({'publication': reference(row), 'package_id': manifest['package_id'], 'version': manifest['version'],
                'baseline': manifest['baseline'], 'new_use_allowed': not reasons, 'ineffective_reasons': reasons})
        continuation = None
        if offset < len(ids):
            payload = {'snapshot': reference(source), 'offset': offset}
            cursor_id = identifier('discovery-cursor', actor, artifact_digest(payload))
            continuation = reference(store._record_once(conn, cursor_id, 'discovery_cursor', scope, actor, payload)['record'])
    return {'packages': results, 'next_cursor': continuation, 'snapshot_observed_at': source['created_at'],
            'coverage': 'ONE_EXPLICIT_NAMESPACE_WITH_CURRENT_CLOSURE_ACCESS',
            'new_publications_included_after_first_page': False, 'status_rechecked_on_each_page': True,
            'authorization_granted': False}
