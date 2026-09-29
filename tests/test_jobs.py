from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import time
import pytest
from sqlalchemy import select, update
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.expr import artifact_digest
from air.foundation import InvalidModel
from air.jobs import submit, claim, execute_claim, finish, get_job, cancel, run_next
from air.portability import export_registry, import_home
from air.storage import Conflict, Store, job_heads, service_records, versions, AUTHORITY_TABLES, RENEWAL_TABLES
from test_planning import prepare


def setup(store, tmp_path):
    args = prepare(store)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='jobs-test')
    credential = store.create_token('planner', 'reader')
    principal = store.authenticate(credential['access_token'], True)
    principal['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy()
    return settings, principal, policy, {'idempotency_key': 'plan-1', 'operation': 'plan', 'arguments': args}, credential


def test_completed_calculation_can_conclude_violated_and_retries_do_not_duplicate(store, tmp_path):
    settings, principal, policy, request, credential = setup(store, tmp_path)
    job = submit(store, principal, policy, settings, request)
    assert job['created'] and not submit(store, principal, policy, settings, request)['created']
    assert run_next(store, settings)['status'] == 'SUCCEEDED'
    assert not run_next(store, settings)['processed']
    view = get_job(store, principal, policy, {'job': job['job']})
    assert view['status'] == 'SUCCEEDED' and view['result']['outcome']['result'] == 'VIOLATED'
    assert view['result']['outcome']['proposed']['total_shortfall_FTE_weeks'] == '4'
    assert not view['result']['external_effects']
    with store.engine.connect() as conn:
        records = conn.execute(select(service_records.c.payload)).scalars().all()
    assert credential['access_token'] not in ''.join(records)
    changed = deepcopy(request);changed['arguments']['strategy'] = 'SERIAL_EARLIEST_FEASIBLE'
    with pytest.raises(Conflict): submit(store, principal, policy, settings, changed)
    assert not cancel(store, principal, policy, {'job': job['job']})['changed']


def test_concurrent_submission_and_claim_have_one_owner(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(store, principal, policy, settings, request), range(2)))
    assert sum(r['created'] for r in results) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        assignments = list(pool.map(lambda _: claim(store), range(2)))
    assert sum(a is not None for a in assignments) == 1


def test_expired_lease_replays_and_old_worker_cannot_publish(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    job = submit(store, principal, policy, settings, request)
    abandoned = claim(store, 'worker-crashed')
    with store.write() as conn:
        conn.execute(update(job_heads).where(job_heads.c.id == job['job']['id']).values(lease_until=0))
    replacement = claim(store, 'worker-recovery')
    assert replacement['attempt'] == 2
    assert finish(store, settings, abandoned, 'SUCCEEDED', {'should_never': 'appear'}) == {'status': 'STALE_CLAIM', 'accepted': False}
    assert execute_claim(store, settings, replacement)['accepted']
    assert get_job(store, principal, policy, {'job': job['job']})['result']['attempt'] == 2
    assert not execute_claim(store, settings, replacement)['accepted']


def test_running_cancellation_fences_completion_and_is_idempotent(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    job = submit(store, principal, policy, settings, request)
    assignment = claim(store)
    assert cancel(store, principal, policy, {'job': job['job']})['changed']
    assert not execute_claim(store, settings, assignment)['accepted']
    assert not cancel(store, principal, policy, {'job': job['job']})['changed']
    assert get_job(store, principal, policy, {'job': job['job']})['status'] == 'CANCELLED'
    assert not run_next(store, settings)['processed']


def test_original_token_revocation_blocks_deferred_execution(store, tmp_path):
    settings, principal, policy, request, credential = setup(store, tmp_path)
    job = submit(store, principal, policy, settings, request)
    store.revoke_token(credential['token_id'])
    assert run_next(store, settings)['status'] == 'FAILED'
    assert get_job(store, principal, policy, {'job': job['job']})['result']['outcome']['code'] == 'AUTHORIZATION_REVOKED'


def test_policy_loss_hides_result_and_prevents_worker_publication(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    job = submit(store, principal, policy, settings, request)
    assignment = claim(store)
    revoked = {'version': '2', 'subjects': {}}
    (tmp_path / 'access-policy.json').write_text(json.dumps(revoked), encoding='utf-8')
    assert execute_claim(store, settings, assignment)['status'] == 'FAILED'
    with pytest.raises(Forbidden): get_job(store, principal, AccessPolicy(revoked), {'job': job['job']})
    # An owner can still stop a nonterminal job even after losing source access.
    with pytest.raises(Forbidden): get_job(store, {'subject': 'other', 'role': 'admin'}, policy, {'job': job['job']})


def test_attempts_are_bounded_and_schema_two_migration_preserves_objects(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    before = store.counts()
    with store.write() as conn:
        for table in reversed((*AUTHORITY_TABLES, *RENEWAL_TABLES)): table.drop(conn)
        job_heads.drop(conn);conn.execute(update(versions).values(version=2))
    store.migrate();store.migrate()
    assert store.counts() == before
    job = submit(store, principal, policy, settings, request)
    for _ in range(3):
        assert claim(store)
        with store.write() as conn: conn.execute(update(job_heads).where(job_heads.c.id == job['job']['id']).values(lease_until=0))
    assert claim(store)['terminal']
    assert get_job(store, principal, policy, {'job': job['job']})['result']['outcome']['code'] == 'ATTEMPTS_EXHAUSTED'


def test_api_requires_live_identity_and_worker_runs_automatically(store, tmp_path):
    settings, principal, policy, request, credential = setup(store, tmp_path)
    headers = {'Authorization': 'Bearer ' + credential['access_token']}
    with TestClient(create_app(settings)) as client:
        assert client.post('/v1/jobs', json=request).status_code == 401
        queued = client.post('/v1/jobs', json=request, headers=headers)
        assert queued.status_code == 200
        pin = {'job': queued.json()['job']}
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            view = client.post('/v1/jobs/read', json=pin, headers=headers).json()
            if view['status'] in ('SUCCEEDED', 'FAILED'): break
            time.sleep(.1)
        assert view['status'] == 'SUCCEEDED'
        forged = {**request, 'operation': 'shell'}
        assert client.post('/v1/jobs', json=forged, headers=headers).status_code == 422
        store.revoke_token(credential['token_id'])
        assert client.post('/v1/jobs/read', json=pin, headers=headers).status_code == 401


def test_transferred_queue_cannot_reuse_source_authorization(store, tmp_path):
    settings, principal, policy, request, _ = setup(store, tmp_path)
    queued = submit(store, principal, policy, settings, request)
    folder = tmp_path / 'job-transfer';export_registry(store, folder)
    target_home = tmp_path / 'recovered';import_home(folder, target_home)
    recovered_settings = Settings.load(target_home)
    recovered = Store(recovered_settings.database_url)
    try:
        assert run_next(recovered, recovered_settings)['status'] == 'FAILED'
        status = get_job(recovered, principal, AccessPolicy(), {'job': queued['job']})
        assert status['result']['outcome']['code'] == 'AUTHORIZATION_REVOKED'
        assert get_job(store, principal, policy, {'job': queued['job']})['status'] == 'QUEUED'
    finally: recovered.engine.dispose()
