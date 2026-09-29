"""Signed external unittest reports, scoped by operator trust and a single-use AIR challenge.

No uploaded code is executed. A signature authenticates the trusted runner's attestation,
not the truth of arbitrary software or a production environment outside its pinned scope.
"""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
import rfc8785
from air.access import AccessPolicy, Forbidden, ScopedStore, NAMESPACES
from air.core import URI, TEXT, INSTANT, record, digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot
from air.packages import RECORD_REF, reference, lock_registry
from air.reviews import record_key
from air.storage import Conflict

ENGINE = 'air.external-test-proof/0.35'
ADAPTER = 'air.python-unittest/1'
CHECKSUM = SNAPSHOT['properties']['digest']
KEY_ID = {'type': 'string', 'pattern': '^[a-zA-Z0-9_.-]{1,128}$'}
KEY = record({'key_id': KEY_ID, 'executor': URI, 'public_key': {'type': 'string', 'maxLength': 64},
    'namespaces': NAMESPACES, 'not_before': INSTANT, 'expires_at': INSTANT,
    'max_age_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 2592000},
    'suite_digests': {'type': 'array', 'items': CHECKSUM, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
    'environments': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True}})
CHALLENGE = record({'idempotency_key': TEXT, 'baseline': SNAPSHOT, 'case': SNAPSHOT, 'environment': SNAPSHOT,
    'run_id': URI, 'key_id': KEY_ID, 'suite_digest': CHECKSUM,
    'ttl_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 86400}})
TEST = record({'id': {'type': 'string', 'minLength': 1, 'maxLength': 512},
               'status': {'enum': ['PASS', 'FAIL', 'ERROR', 'SKIP', 'EXPECTED_FAILURE', 'UNEXPECTED_SUCCESS']}})
RESULT = record({'format': {'const': ENGINE}, 'adapter': {'const': ADAPTER}, 'challenge': RECORD_REF,
    'nonce': {'type': 'string', 'pattern': '^[a-f0-9]{32}$'}, 'executor': URI, 'key_id': KEY_ID,
    'suite_digest': CHECKSUM, 'started_at': INSTANT, 'finished_at': INSTANT,
    'tests': {'type': 'array', 'minItems': 1, 'maxItems': 4096, 'items': TEST}})
ENVELOPE = record({'result': RESULT, 'signature': {'type': 'string', 'minLength': 88, 'maxLength': 88}})
IMPORT = record({'attestation': ENVELOPE})


def pin(obj): return {**exact(obj), 'digest': digest(obj)}
def clock(): return datetime.now(timezone.utc)
def instant(value): return datetime.fromisoformat(value)
def stamp(value): return value.isoformat().replace('+00:00', 'Z')
def key_record(key_id): return record_key('proof-key', 'local-operator', key_id)
def execution_id(challenge_id): return record_key('proof-execution', 'air', challenge_id)


def crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        return Ed25519PublicKey, InvalidSignature
    except ImportError as exc:
        raise InvalidModel('External proof verification requires the optional AIR proofs extra') from exc


def register_key(store, settings, request):
    """Trusted OS operator only; deliberately not exposed by HTTP or MCP."""
    check_schema(request, KEY)
    public, _ = crypto()
    try: public.from_public_bytes(base64.b64decode(request['public_key'], validate=True))
    except ValueError as exc: raise InvalidModel('Invalid Ed25519 public key') from exc
    if not request['namespaces'] or not instant(request['not_before']) < instant(request['expires_at']):
        raise InvalidModel('Trust scope and validity must be explicit')
    with store.write() as conn:
        lock_registry(conn)
        return store._record_once(conn, key_record(request['key_id']), 'proof_key', 'air.system', 'local-operator',
                                  {'format': ENGINE, 'instance_id': settings.instance_id, 'request': request})


def revoke_key(store, request):
    check_schema(request, record({'key_id': KEY_ID, 'rationale': TEXT}))
    if store.get_record(key_record(request['key_id'])) is None: raise InvalidModel('Unknown proof key')
    with store.write() as conn:
        lock_registry(conn)
        return store._record_once(conn, record_key('proof-key-revoked', 'air', request['key_id']), 'proof_key_revocation',
                                  'air.system', 'local-operator', request)


def trusted_key(store, policy, key_id, namespace, at=None):
    row = store.get_record(key_record(key_id))
    if row is None or row['kind'] != 'proof_key': raise InvalidModel('External executor is not trusted')
    if store.get_record(record_key('proof-key-revoked', 'air', key_id)): raise InvalidModel('External proof key was revoked')
    trust = row['payload']['request'];check_schema(trust, KEY)
    current = at or clock()
    if not instant(trust['not_before']) <= current < instant(trust['expires_at']):
        raise InvalidModel('External proof key is outside its validity window')
    if namespace not in trust['namespaces'] and '*' not in trust['namespaces']:
        raise Forbidden('External executor has no mandate for this namespace')
    policy.require({'subject': trust['executor'], 'role': 'editor'}, 'attest', namespace)
    return row, trust


def challenge(store, principal, policy, settings, request):
    check_schema(request, CHALLENGE)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    namespace = exported['baseline']['meta']['namespace']
    policy.require(principal, 'write', namespace)
    index = {key(exact(o)): o for o in exported['objects']}
    for field, kind in [('case', 'air.VerificationCase'), ('environment', 'air.Environment')]:
        obj = index.get(key(request[field]))
        if obj is None or obj['meta']['type'] != kind or pin(obj) != request[field]:
            raise InvalidModel('Execution challenge requires exact baseline members')
    case = index[key(request['case'])]
    if case['body']['method'] != 'TEST': raise InvalidModel('External unittest adapter only attests TEST cases')
    key_row, trust = trusted_key(store, policy, request['key_id'], namespace)
    if key_row['payload']['instance_id'] != settings.instance_id:
        raise InvalidModel('Trust registration belongs to another installation')
    if request['suite_digest'] not in trust['suite_digests'] or request['environment'] not in trust['environments']:
        raise InvalidModel('Suite or environment is outside the qualified executor mandate')
    identifier = record_key('proof-challenge', principal['subject'], request['idempotency_key'])
    from air.jobs import check_identity
    with store.write() as conn:
        lock_registry(conn);check_identity(store, conn, principal, settings)
        if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Proof policy changed')
        prior = store._get_record(conn, identifier)
        if prior:
            if prior['payload']['request'] != request: raise Conflict('Proof challenge idempotency key was reused')
            row = prior
        else:
            if store.get(request['run_id'], 1) is not None: raise Conflict('Execution run identifier is already stored')
            issued = clock()
            if issued + timedelta(seconds=request['ttl_seconds']) > instant(trust['expires_at']):
                raise InvalidModel('Challenge exceeds executor validity')
            payload = {'format': ENGINE, 'adapter': ADAPTER, 'request': request, 'instance_id': settings.instance_id,
                'key': reference(key_row), 'executor': trust['executor'], 'policy_digest': policy.digest,
                'nonce': uuid.uuid4().hex, 'issued_at': stamp(issued),
                'expires_at': stamp(issued + timedelta(seconds=request['ttl_seconds'])),
                'oracle_digest': oracle_digest(case)}
            row = store._record_once(conn, identifier, 'proof_challenge', namespace, principal['subject'], payload)['record']
    return {'challenge': reference(row), 'binding': row['payload'], 'created': prior is None,
            'external_execution_authorized': False}


def oracle_digest(case):
    from air.expr import artifact_digest
    return artifact_digest({k: case['body'][k] for k in ('oracle', 'acceptance', 'inputs')})


def verify(store, principal, policy, envelope):
    check_schema(envelope, ENVELOPE)
    result = envelope['result'];row = store.get_record(result['challenge']['id'])
    if row is None or row['kind'] != 'proof_challenge' or reference(row) != result['challenge']:
        raise InvalidModel('External proof challenge is unavailable or different')
    binding = row['payload'];req = binding['request']
    policy.require(principal, 'read', row['scope'])
    ScopedStore(store, principal, policy).check_read([req['baseline']])
    key_row, trust = trusted_key(store, policy, result['key_id'], row['scope'])
    if reference(key_row) != binding['key'] or binding['policy_digest'] != policy.digest:
        raise InvalidModel('Executor trust or policy differs from the challenge')
    if any(result[field] != expected for field, expected in (
        ('nonce', binding['nonce']), ('executor', binding['executor']), ('key_id', req['key_id']),
        ('suite_digest', req['suite_digest']), ('adapter', binding['adapter']))):
        raise InvalidModel('External attestation binding differs from the challenge')
    if req['environment'] not in trust['environments'] or result['suite_digest'] not in trust['suite_digests']:
        raise InvalidModel('Executor suite or environment mandate changed')
    public, signature_error = crypto()
    try:
        public.from_public_bytes(base64.b64decode(trust['public_key'], validate=True)).verify(
            base64.b64decode(envelope['signature'], validate=True), rfc8785.dumps(result))
    except (ValueError, signature_error) as exc: raise InvalidModel('External proof signature is invalid') from exc
    started, finished, current = instant(result['started_at']), instant(result['finished_at']), clock()
    if not instant(binding['issued_at']) <= started <= finished <= current < instant(binding['expires_at']):
        raise InvalidModel('External proof is expired, future dated or predates its challenge')
    if (current - finished).total_seconds() > trust['max_age_seconds']:
        raise InvalidModel('External measurement or execution evidence is stale')
    ids = [t['id'] for t in result['tests']]
    if len(ids) != len(set(ids)): raise InvalidModel('Duplicate external test identifiers')
    verdict = 'PASS' if all(t['status'] == 'PASS' for t in result['tests']) else 'FAIL' if any(
        t['status'] in ('FAIL', 'ERROR', 'UNEXPECTED_SUCCESS') for t in result['tests']) else 'INCONCLUSIVE'
    return row, verdict


def import_report(store, principal, policy, settings, request):
    from air import artifacts
    check_schema(request, IMPORT)
    envelope = request['attestation'];row, verdict = verify(store, principal, policy, envelope)
    if row['actor'] != principal['subject']: raise Forbidden('Execution challenge belongs to another subject')
    if row['payload']['instance_id'] != settings.instance_id: raise InvalidModel('Challenge belongs to another installation')
    binding = row['payload'];req = binding['request']
    policy.require(principal, 'write', row['scope'])
    data = rfc8785.dumps(envelope)
    if len(data) > artifacts.JSON_MAX_SIZE: raise InvalidModel('External report exceeds 512 KiB')
    prepared = artifacts._prepare(principal, policy, settings, {'namespace': row['scope'],
        'idempotency_key': execution_id(row['id']), 'media_type': 'application/json'}, data)
    meta = deepcopy(store.get(req['case']['id'], req['case']['revision'])['object']['meta'])
    meta.update(id=req['run_id'], revision=1, type='air.VerificationRun', name='External test: ' + meta['name'])
    with store.write() as conn:
        lock_registry(conn)
        # Recheck both revocation and current authority immediately before consuming the nonce.
        verify(store, principal, policy, envelope)
        artifact = artifacts._put_locked(store, conn, principal, policy, settings, prepared, data)
        run = {'meta': meta, 'body': {'case': exact(store.get(req['case']['id'], req['case']['revision'])['object']),
            'method': 'TEST', 'result': verdict, 'proof_level': 'EXECUTED_TEST',
            'executed_at': envelope['result']['finished_at'], 'executor': binding['executor'],
            'environment': {'id': req['environment']['id'], 'revision': req['environment']['revision']},
            'report': artifact['artifact_reference'], 'summary': str(len(envelope['result']['tests'])) + ' external tests: ' + verdict}}
        receipt = store._record_once(conn, execution_id(row['id']), 'proof_execution', row['scope'], principal['subject'],
            {'format': ENGINE, 'challenge': reference(row), 'report_digest': 'sha256:' + hashlib.sha256(data).hexdigest(),
             'run': run, 'verdict': verdict})
    return {'execution': reference(receipt['record']), 'created': receipt['created'], 'verification_run': run,
            'artifact': artifact['artifact_reference'], 'runtime_execution_attested': True, 'authorization_granted': False}


def assess(store, principal, policy, exported, run, raw):
    from air.parsing import parse
    envelope = parse(raw);challenge_row, verdict = verify(store, principal, policy, envelope)
    binding = challenge_row['payload'];req = binding['request']
    execution = store.get_record(execution_id(challenge_row['id']))
    if execution is None or execution['kind'] != 'proof_execution' or execution['payload']['run'] != run:
        raise InvalidModel('Run was not imported through the qualified external adapter')
    if execution['payload']['report_digest'] != 'sha256:' + hashlib.sha256(raw).hexdigest() or verdict != 'PASS':
        raise InvalidModel('External proof is not an intact passing execution')
    if principal['subject'] == binding['executor']: raise Forbidden('External executor cannot independently review its own proof')
    original = snapshot(ScopedStore(store, principal, policy), req['baseline'])
    current = {key(exact(o)): o for o in exported['objects']}
    if any(key(exact(o)) not in current or digest(current[key(exact(o))]) != digest(o) for o in original['objects']):
        raise InvalidModel('External execution inputs or environment changed')
    case = current[key(req['case'])]
    if pin(case) != req['case'] or oracle_digest(case) != binding['oracle_digest']:
        raise InvalidModel('External execution oracle changed')
    return {'status': 'VERIFIED_EXTERNAL_TEST', 'runtime_execution_attested': True,
            'executor_claim_authenticated': True, 'executor': binding['executor'], 'adapter': ADAPTER,
            'execution_receipt': reference(execution), 'challenge': reference(challenge_row),
            'suite_digest': req['suite_digest'], 'evidence_expires_at': binding['expires_at']}
