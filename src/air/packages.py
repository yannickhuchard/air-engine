"""Atomic local design packages; publication never grants construction authority."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from air.access import ScopedStore, Forbidden
from air.core import REF, TEXT, INSTANT, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, key
from air.projections import SNAPSHOT, snapshot
from air.reviews import record_key
from air.storage import Conflict, versions

RECORD_REF = record({'id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                     'digest': SNAPSHOT['properties']['digest']})
PREPARE = record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'package_id': {'type': 'string', 'format': 'uri', 'minLength': 1, 'maxLength': 512},
    'version': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647},
    'baseline': SNAPSHOT,
    'exports': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
    'imports': {'type': 'array', 'items': RECORD_REF, 'maxItems': 32, 'uniqueItems': True},
    'expires_at': INSTANT})
PUBLISH = record({'idempotency_key': PREPARE['properties']['idempotency_key'], 'preparation': RECORD_REF})
REVOKE = record({'publication': RECORD_REF, 'rationale': TEXT})
READ = record({'publication': RECORD_REF, 'purpose': {'enum': ['HISTORICAL', 'NEW_USE']}})


def reference(row):
    return {'id': row['id'], 'digest': row['request_digest']}


def identifier(kind, *parts):
    return 'urn:air:' + kind + ':' + artifact_digest(list(parts)).split(':')[1]


def lock_registry(conn):
    # A deliberately coarse invariant scope for this initial single-registry binding.
    # SQLite write() already holds BEGIN IMMEDIATE. PostgreSQL holds this row lock.
    conn.execute(select(versions.c.version).where(versions.c.id == 1).with_for_update()).scalar_one()


def required(store, conn, ref, kind):
    row = store._get_record(conn, ref['id'])
    if row is None or row['kind'] != kind: raise InvalidModel('Package record is unavailable')
    if row['request_digest'] != ref['digest']: raise Conflict('Package record digest differs')
    return row


def authorize_baseline(store, principal, policy, baseline_ref, publish=False):
    baseline = snapshot(ScopedStore(store, principal, policy), baseline_ref)
    namespaces = sorted({o['meta']['namespace'] for o in [baseline['baseline'], *baseline['objects']]})
    if publish:
        for namespace in namespaces: policy.require(principal, 'publish', namespace)
    return baseline, namespaces


def publication_tree(store, conn, principal, policy, ref, new_use, forbidden_package=None):
    pending, visited, selected = [ref], set(), {}
    reasons = []
    root = None
    while pending:
        current = pending.pop()
        witness = (current['id'], current['digest'])
        if witness in visited: continue
        visited.add(witness)
        if len(visited) > 256: raise InvalidModel('Package closure exceeds 256 publications')
        row = required(store, conn, current, 'package_publication')
        if root is None: root = row
        payload = row['payload'];manifest = payload['manifest']
        package_id = manifest['package_id']
        if forbidden_package == package_id: raise InvalidModel('Recursive package composition is forbidden')
        if package_id in selected and selected[package_id] != current:
            raise InvalidModel('Package closure selects conflicting versions of one package')
        selected[package_id] = current
        baseline, namespaces = authorize_baseline(store, principal, policy, manifest['baseline'])
        publisher = {'subject': row['actor'], 'role': payload['publisher_role']}
        if store._get_record(conn, identifier('package-revoked', row['id'])):
            reasons.append({'publication': current, 'reason': 'REVOKED'})
        if payload['policy_digest'] != policy.digest:
            reasons.append({'publication': current, 'reason': 'POLICY_CHANGED'})
        if not all(policy.allows(publisher, 'publish', scope) for scope in namespaces):
            reasons.append({'publication': current, 'reason': 'MANDATE_MISSING'})
        pending.extend(manifest['imports'])
    if new_use and reasons: raise InvalidModel('Package is unavailable for new use', {'reasons': reasons})
    return root, reasons


def prepare_package(store, principal, policy, request):
    check_schema(request, PREPARE)
    request = deepcopy(request)
    request['exports'].sort(key=key);request['imports'].sort(key=lambda r: r['id'])
    baseline, scopes = authorize_baseline(store, principal, policy, request['baseline'], True)
    members = {(m['id'], m['revision'], m['digest']) for m in baseline['baseline']['body']['members']}
    if any((r['id'], r['revision'], r['digest']) not in members for r in request['exports']):
        raise InvalidModel('Every package export must be an exact member of its closed baseline')
    if len({r['id'] for r in request['exports']}) != len(request['exports']):
        raise InvalidModel('Exports select one revision per identity')
    stage_id = record_key('package-stage', principal['subject'], request['idempotency_key'])
    payload = {'request': request, 'policy_digest': policy.digest}
    with store.write() as conn:
        lock_registry(conn)
        if store._get_record(conn, stage_id) is None:
            expires = datetime.fromisoformat(request['expires_at']);current = datetime.now(timezone.utc)
            if not current < expires <= current + timedelta(days=7):
                raise InvalidModel('Package preparation expires within seven days')
        for ref in request['imports']:
            publication_tree(store, conn, principal, policy, ref, True, request['package_id'])
        result = store._record_once(conn, stage_id, 'package_preparation', baseline['baseline']['meta']['namespace'], principal['subject'], payload)
    return {'preparation': reference(result['record']), 'created': result['created'], 'published': False,
            'expires_at': request['expires_at'], 'authorization_granted': False}


def publish_package(store, principal, policy, request):
    check_schema(request, PUBLISH)
    actor = principal['subject']
    retry_id = record_key('package-command', actor, request['idempotency_key'])
    with store.write() as conn:
        lock_registry(conn)
        stage = required(store, conn, request['preparation'], 'package_preparation')
        if stage['actor'] != actor: raise Forbidden('Only the preparer can commit this package')
        proposal = stage['payload']['request']
        baseline, scopes = authorize_baseline(store, principal, policy, proposal['baseline'], True)
        prior = store._get_record(conn, retry_id)
        if prior is not None:
            if prior['payload']['request'] != request: raise Conflict('Package idempotency key was reused')
            publication_tree(store, conn, principal, policy, prior['payload']['publication'], False)
            return {'publication': prior['payload']['publication'], 'created': False, 'published': True, 'authorization_granted': False}
        if stage['payload']['policy_digest'] != policy.digest:
            raise InvalidModel('Publication policy changed after preparation')
        if datetime.fromisoformat(proposal['expires_at']) <= datetime.now(timezone.utc):
            raise InvalidModel('Package preparation expired')
        # Validate the full import union, including diamonds selecting different versions.
        selected = {}
        for ref in proposal['imports']:
            publication_tree(store, conn, principal, policy, ref, True, proposal['package_id'])
            pending, seen = [ref], set()
            while pending:
                candidate = pending.pop()
                if candidate['id'] in seen: continue
                seen.add(candidate['id'])
                if len(seen) > 256: raise InvalidModel('Package closure budget exceeded')
                imported = required(store, conn, candidate, 'package_publication')['payload']['manifest']
                package_id = imported['package_id']
                if package_id in selected and selected[package_id] != candidate:
                    raise InvalidModel('Imports select conflicting versions of one package')
                selected[package_id] = candidate;pending.extend(imported['imports'])
        manifest = {k: proposal[k] for k in ('package_id', 'version', 'baseline', 'exports', 'imports')}
        manifest.update(format='air.local-package/1', visibility='BASELINE_CLOSURE',
                        evidence_class='DESIGN_DRAFT', semantic_compatibility='NOT_EXECUTED')
        publication_id = identifier('package', proposal['package_id'], proposal['version'])
        owner_id = identifier('package-owner', proposal['package_id'])
        owner = store._get_record(conn, owner_id)
        if owner is not None and owner['scope'] != stage['scope']:
            raise Forbidden('Package identity belongs to another namespace')
        if owner is None:
            store._record_once(conn, owner_id, 'package_identity', stage['scope'], actor, {'package_id': proposal['package_id']})
        payload = {'manifest': manifest, 'policy_digest': policy.digest, 'publisher_role': principal['role']}
        result = store._record_once(conn, publication_id, 'package_publication', stage['scope'], actor, payload)
        published = reference(result['record'])
        store._record_once(conn, retry_id, 'package_command', stage['scope'], actor,
                           {'request': request, 'publication': published})
        store._record_once(conn, identifier('package-event', publication_id, 'PUBLISHED'), 'package_event', stage['scope'], actor,
                           {'publication': published, 'event': 'PUBLISHED', 'aggregate': publication_id, 'sequence': 1})
    return {'publication': published, 'created': result['created'], 'published': True, 'authorization_granted': False}


def read_package(store, principal, policy, request):
    check_schema(request, READ)
    with store.engine.connect() as conn:
        row, reasons = publication_tree(store, conn, principal, policy, request['publication'], request['purpose'] == 'NEW_USE')
        return {'publication': reference(row), 'manifest': row['payload']['manifest'], 'publisher': row['actor'],
                'new_use_allowed': not reasons, 'ineffective_reasons': reasons,
                'authority_basis': 'AUTHENTICATED_LOCAL_REGISTRY', 'remote_signature_verified': False,
                'authorization_granted': False}


def revoke_package(store, principal, policy, request):
    check_schema(request, REVOKE)
    with store.write() as conn:
        lock_registry(conn)
        row, _ = publication_tree(store, conn, principal, policy, request['publication'], False)
        authorize_baseline(store, principal, policy, row['payload']['manifest']['baseline'], True)
        result = store._record_once(conn, identifier('package-revoked', row['id']), 'package_revocation', row['scope'], principal['subject'], request)
        store._record_once(conn, identifier('package-event', row['id'], 'REVOKED'), 'package_event', row['scope'], principal['subject'],
                           {'publication': request['publication'], 'event': 'REVOKED', 'aggregate': row['id'], 'sequence': 2})
    return {'revocation': reference(result['record']), 'created': result['created'], 'historical_manifest_retained': True}
