"""Durable pure calculations with leases, fenced completion and revocable identity."""
from copy import deepcopy
import time
import uuid
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import OperationalError
from air.access import AccessPolicy, ScopedStore, Forbidden
from air.core import record
from air.expr import artifact_digest, bounded
from air.foundation import InvalidModel, check_schema
from air.packages import RECORD_REF, identifier, reference, required, lock_registry
from air.projections import snapshot
from air.reviews import record_key
from air.storage import Conflict, job_heads, tokens
from air import planning, experiments, contexts

OPERATIONS = {'plan': (planning.REQUEST, planning.ENGINE), 'simulate': (experiments.REQUEST, experiments.ENGINE),
              'reconcile': (contexts.READ, contexts.ENGINE)}
REQUEST = {'oneOf': [record({'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'operation': {'const': operation}, 'arguments': definition[0]}) for operation, definition in OPERATIONS.items()]}
LOOKUP = record({'job': RECORD_REF})
TERMINAL = ('SUCCEEDED', 'FAILED', 'CANCELLED')
LEASE_SECONDS = 60


def check_inputs(store, principal, policy, operation, args):
    bounded(args)
    check_schema(args, OPERATIONS[operation][0])
    guarded = ScopedStore(store, principal, policy)
    if operation == 'reconcile':
        result = contexts.read_context(store, principal, policy, args)
        return result['snapshot']['contributions'][0]['namespace']
    if operation == 'simulate':
        baseline = snapshot(guarded, args['baseline'])
        refs = [args['model']['function']] + [s['verification_case'] for s in args['scenarios']]
    else:
        baseline = snapshot(guarded, args['demands'][0]['baseline'])
        refs = [pin for pool in args['pools'] for pin in (pool['scope'], pool['source'])]
        refs.extend(pin for demand in args['demands'] for pin in (demand['baseline'], demand['unit']))
        refs.extend(pin for dependency in args['dependencies'] for pin in (dependency['before'], dependency['after']))
        refs.extend(args['priority_order'])
    guarded.check_read(refs)
    return baseline['baseline']['meta']['namespace']


def check_identity(store, conn, principal, settings):
    binding = principal.get('authorization')
    if not isinstance(binding, dict) or binding.get('mode') != settings.auth_mode or binding.get('instance_id') != settings.instance_id:
        raise Forbidden('Job authorization belongs to a different installation or authentication mode')
    if binding.get('expires_at', 0) <= int(time.time()): raise Forbidden('Job authorization expired')
    if binding['mode'] == 'local':
        row = conn.execute(select(tokens.c.subject, tokens.c.role, tokens.c.expires_at, tokens.c.revoked).where(tokens.c.id == binding.get('token_id')).with_for_update()).mappings().first()
        if row is None or row['revoked'] or row['expires_at'] <= int(time.time()) or row['subject'] != principal['subject'] or row['role'] != principal['role']:
            raise Forbidden('Original job token was revoked or changed')
    else:
        if binding.get('configuration_digest') != artifact_digest(settings.oidc) or settings.oidc.get('subjects', {}).get(principal['subject']) != principal['role']:
            raise Forbidden('OIDC job authorization changed')


def submit(store, principal, policy, settings, request):
    check_schema(request, REQUEST)
    request = deepcopy(request)
    scope = check_inputs(store, principal, policy, request['operation'], request['arguments'])
    job_id = record_key('job', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        lock_registry(conn)
        prior = store._get_record(conn, job_id)
        if prior is not None:
            if prior['payload']['request'] != request: raise Conflict('Job idempotency key was reused')
            return {'job': reference(prior), 'created': False, 'authorization_granted': False}
        check_identity(store, conn, principal, settings)
        identity = {k: deepcopy(principal[k]) for k in ('subject', 'role', 'authorization')}
        from air.quotas import job as check_quota
        check_quota(conn, principal['subject'])
        payload = {'request': request, 'principal': identity, 'policy_digest': policy.digest,
                   'engine': OPERATIONS[request['operation']][1], 'external_effects': False}
        result = store._record_once(conn, job_id, 'job_request', scope, principal['subject'], payload)
        store.insert_once(conn, job_heads, {'id': job_id, 'status': 'QUEUED', 'attempt': 0, 'lease_until': None,
            'claim_id': None, 'result_id': None, 'created_epoch': int(time.time())}, ['id'])
    return {'job': reference(result['record']), 'created': result['created'], 'authorization_granted': False}


def owner_job(store, conn, principal, ref):
    job = required(store, conn, ref, 'job_request')
    if job['actor'] != principal['subject']: raise Forbidden('Job belongs to another subject')
    return job


def get_job(store, principal, policy, request):
    check_schema(request, LOOKUP)
    with store.engine.connect() as conn:
        job = owner_job(store, conn, principal, request['job'])
        check_inputs(store, principal, policy, job['payload']['request']['operation'], job['payload']['request']['arguments'])
        state = conn.execute(select(job_heads).where(job_heads.c.id == job['id'])).mappings().one()
        result = store._get_record(conn, state['result_id']) if state['result_id'] else None
        return {'job': reference(job), 'status': state['status'], 'attempt': state['attempt'],
            'lease_until': state['lease_until'], 'result': result['payload'] if result else None,
            'authorization_granted': False}


def terminal(store, conn, job, state, status, outcome, actor='air-worker'):
    record_id = identifier('job-result', job['id'])
    payload = {'job': reference(job), 'status': status, 'attempt': state['attempt'],
               'outcome': outcome, 'external_effects': False}
    result = store._record_once(conn, record_id, 'job_result', job['scope'], actor, payload)
    conn.execute(update(job_heads).where(job_heads.c.id == job['id']).values(status=status,
                 lease_until=None, result_id=record_id))
    return result


def cancel(store, principal, policy, request):
    check_schema(request, LOOKUP)
    with store.write() as conn:
        job = owner_job(store, conn, principal, request['job'])
        state = conn.execute(select(job_heads).where(job_heads.c.id == job['id']).with_for_update()).mappings().one()
        if state['status'] in TERMINAL:
            return {'job': reference(job), 'status': state['status'], 'cancelled': state['status'] == 'CANCELLED', 'changed': False}
        store._record_once(conn, identifier('job-cancel', job['id']), 'job_cancellation', job['scope'], principal['subject'], {'job': reference(job)})
        terminal(store, conn, job, state, 'CANCELLED', {'code': 'CANCELLED_BY_REQUESTER'}, principal['subject'])
    return {'job': reference(job), 'status': 'CANCELLED', 'cancelled': True, 'changed': True}


def claim(store, worker_id=None):
    worker_id = worker_id or str(uuid.uuid4())
    current = int(time.time())
    with store.write() as conn:
        ready = or_(job_heads.c.status == 'QUEUED', and_(job_heads.c.status == 'RUNNING', job_heads.c.lease_until <= current))
        state = conn.execute(select(job_heads).where(ready).order_by(job_heads.c.created_epoch, job_heads.c.id)
            .limit(1).with_for_update(skip_locked=True)).mappings().first()
        if state is None: return None
        job = store._get_record(conn, state['id'])
        if state['attempt'] >= 3:
            terminal(store, conn, job, state, 'FAILED', {'code': 'ATTEMPTS_EXHAUSTED'})
            return {'terminal': True, 'job': reference(job)}
        attempt = state['attempt'] + 1
        claim_id = identifier('job-claim', job['id'], attempt)
        lease_until = current + LEASE_SECONDS
        payload = {'job': reference(job), 'attempt': attempt, 'worker': worker_id, 'lease_until': lease_until}
        receipt = store._record_once(conn, claim_id, 'job_claim', job['scope'], 'air-worker', payload)
        conn.execute(update(job_heads).where(job_heads.c.id == job['id']).values(status='RUNNING', attempt=attempt,
                     lease_until=lease_until, claim_id=claim_id))
        return {'job': job, 'claim': reference(receipt['record']), 'attempt': attempt, 'lease_until': lease_until}


def finish(store, settings, assignment, status, outcome):
    job = assignment['job'];principal = job['payload']['principal']
    with store.write() as conn:
        state = conn.execute(select(job_heads).where(job_heads.c.id == job['id']).with_for_update()).mappings().one()
        if state['status'] in TERMINAL: return {'status': state['status'], 'accepted': False}
        if state['claim_id'] != assignment['claim']['id'] or state['attempt'] != assignment['attempt'] or state['lease_until'] <= int(time.time()):
            return {'status': 'STALE_CLAIM', 'accepted': False}
        if status == 'SUCCEEDED':
            try:
                policy = AccessPolicy.load(settings.home)
                check_identity(store, conn, principal, settings)
                if policy.digest != job['payload']['policy_digest']: raise Forbidden('Job policy changed')
                req = job['payload']['request'];check_inputs(store, principal, policy, req['operation'], req['arguments'])
            except (Forbidden, InvalidModel):
                status, outcome = 'FAILED', {'code': 'AUTHORIZATION_OR_CONTEXT_CHANGED'}
        bounded(outcome)
        terminal(store, conn, job, state, status, outcome)
        return {'status': status, 'accepted': True}


def calculate_claim(store, settings, assignment):
    job = assignment['job'];payload = job['payload'];request = payload['request']
    principal = payload['principal']
    try:
        policy = AccessPolicy.load(settings.home)
        with store.engine.connect() as conn: check_identity(store, conn, principal, settings)
        if policy.digest != payload['policy_digest']: raise Forbidden('Job policy changed')
        if payload['engine'] != OPERATIONS[request['operation']][1]: raise InvalidModel('Job needs its declared engine')
        check_inputs(store, principal, policy, request['operation'], request['arguments'])
        guarded = ScopedStore(store, principal, policy)
        if request['operation'] == 'plan': result = planning.plan(guarded, request['arguments'])
        elif request['operation'] == 'simulate': result = experiments.simulate(guarded, request['arguments'])
        else: result = contexts.reconcile(store, principal, policy, request['arguments'])
        return 'SUCCEEDED', result
    except Forbidden:
        return 'FAILED', {'code': 'AUTHORIZATION_REVOKED'}
    except (InvalidModel, Conflict, ValueError):
        return 'FAILED', {'code': 'INPUT_OR_ENGINE_REJECTED'}
    except OperationalError:
        raise  # Leave the lease recoverable; never invent a successful completion.
    except Exception:
        return 'FAILED', {'code': 'CALCULATION_FAILED'}


def execute_claim(store, settings, assignment):
    status,outcome = calculate_claim(store,settings,assignment)
    return finish(store,settings,assignment,status,outcome)


def run_next(store, settings):
    from air.job_budget import calculate, limits
    limits()  # Reject invalid configuration before claiming durable work.
    assignment = claim(store)
    if assignment is None: return {'processed': False}
    if assignment.get('terminal'): return {'processed': True, 'status': 'FAILED'}
    status,outcome = calculate(settings,assignment)
    return {'processed': True, **finish(store,settings,assignment,status,outcome)}


def verify_heads(store, conn):
    """Validate imported mutable projections against their immutable request/result."""
    for state in conn.execute(select(job_heads)).mappings():
        job = store._get_record(conn, state['id'])
        if job is None or job['kind'] != 'job_request': raise ValueError('Job state lacks its immutable request')
        if state['status'] == 'QUEUED' and (state['attempt'] != 0 or state['claim_id'] is not None or state['lease_until'] is not None):
            raise ValueError('Queued job has inconsistent execution state')
        if state['status'] in TERMINAL:
            if state['lease_until'] is not None: raise ValueError('Terminal job retains an active lease')
            result = store._get_record(conn, state['result_id']) if state['result_id'] else None
            if result is None or result['kind'] != 'job_result' or result['payload']['status'] != state['status'] or result['payload']['job'] != reference(job) or result['payload']['attempt'] != state['attempt']:
                raise ValueError('Job result disagrees with its projection')
        elif state['result_id'] is not None: raise ValueError('Nonterminal job already has a result')
        if state['status'] == 'RUNNING':
            claim_row = store._get_record(conn, state['claim_id']) if state['claim_id'] else None
            if claim_row is None or claim_row['kind'] != 'job_claim' or claim_row['payload']['job'] != reference(job) or claim_row['payload']['attempt'] != state['attempt'] or claim_row['payload']['lease_until'] != state['lease_until']:
                raise ValueError('Running job lacks its exact claim')
