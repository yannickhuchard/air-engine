from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from air import artifacts, ci_evidence, delivery_assurance
from air.access import AccessPolicy
from air.core import BUILD_PROFILE, digest
from air.foundation import exact, InvalidModel
from test_build_design import design, model  # noqa: F401


@pytest.fixture
def ci_case(store, design):
    objects, user, _, settings, base = design
    source = model.obj('Source', 'repository', {'kind': 'CODE', 'locator': 'https://repo.example.invalid/quote.git',
        'source_revision': 'a' * 40, 'captured_at': '2026-10-01T00:00:00Z', 'access_policy': 'Fictional test', 'retention_policy': 'Retained fixture'})
    environment = model.obj('Environment', 'test-build', {'stage': 'BUILD_TEST', 'purpose': 'Fictional CI fixture', 'hosting': 'Isolated Python process'})
    store.put_bundle([source, environment], user['subject'])
    meta = deepcopy(store.get(base['baseline']['id'], base['baseline']['revision'])['object']['meta']); meta['revision'] += 1
    frozen = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in [*objects, source, environment]],
        'parent_baselines': [{'id': meta['id'], 'revision': meta['revision'] - 1}]}, user['subject'])
    case = next(o for o in objects if o['meta']['type'] == 'air.VerificationCase')
    policy = AccessPolicy()
    build = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
        'media_type': 'application/octet-stream', 'idempotency_key': 'build'}, b'fictional-build-bytes')
    finished = datetime.now(timezone.utc) - timedelta(seconds=1)
    report = {'format': 'air.ci-ledger/1', 'repository': source['body']['locator'], 'executor': 'urn:fixture:declared-ci-runner', 'source_revision': 'a' * 40,
        'build_artifact': build['artifact'], 'build_digest': build['content_digest'],
        'started_at': (finished - timedelta(seconds=1)).isoformat().replace('+00:00', 'Z'),
        'finished_at': finished.isoformat().replace('+00:00', 'Z'), 'run_url': 'https://ci.example.invalid/run/1',
        'tests': [{'id': 'quote-contract', 'status': 'PASS'}]}
    pin = lambda o: {**exact(o), 'digest': digest(o)}
    request = {'baseline': pin(frozen['baseline']), 'source': pin(source), 'case': pin(case), 'environment': pin(environment),
        'object_id': 'urn:ci:evidence:1', 'idempotency_key': 'ci'}
    return request, report, user, policy, settings


def retain(store, c, report):
    request, _, user, policy, settings = c
    artifact = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE, 'media_type': 'application/json',
        'idempotency_key': 'report-' + str(len(store.audit_log()))}, json.dumps(report).encode())
    return {**request, 'report': artifact['artifact']}


def test_import_binds_build_commit_and_retained_report_without_inventing_qualification(store, ci_case):
    _, report, user, policy, settings = ci_case
    request = retain(store, ci_case, report)
    result = ci_evidence.ingest(store, user, policy, request, settings)
    assert result == ci_evidence.ingest(store, user, policy, request, settings)
    assert result['object']['body']['result'] == 'PASS'
    assert result['object']['body']['executor'] == report['executor']
    assert store.get_record(result['receipt']['id'])['actor'] == user['subject']
    assert not result['execution_authenticity_verified'] and not result['external_job_executed']
    assert delivery_assurance.evidence_state(store, user, policy, result['object']) == 'PASS_RECORDED_NOT_INDEPENDENTLY_QUALIFIED'


@pytest.mark.parametrize('change,expected', [('revision', 'source revision'), ('build', 'build digest'), ('future', 'window'), ('duplicate', 'Duplicate')])
def test_inconsistent_ci_binding_cannot_create_evidence(store, ci_case, change, expected):
    _, report, user, policy, settings = ci_case
    if change == 'revision': report['source_revision'] = 'b' * 40
    elif change == 'build': report['build_digest'] = 'sha256:' + '0' * 64
    elif change == 'future': report['finished_at'] = '2099-01-01T00:00:00Z'
    else: report['tests'] *= 2
    request = retain(store, ci_case, report); before = store.counts()
    with pytest.raises(InvalidModel, match=expected): ci_evidence.ingest(store, user, policy, request, settings)
    assert store.counts() == before


@pytest.mark.parametrize('status,result', [('FAIL', 'FAIL'), ('ERROR', 'FAIL'), ('SKIP', 'INCONCLUSIVE')])
def test_ci_status_is_derived_from_every_result(store, ci_case, status, result):
    _, report, user, policy, settings = ci_case
    report['tests'].append({'id': 'negative-path', 'status': status})
    request = retain(store, ci_case, report)
    assert ci_evidence.ingest(store, user, policy, request, settings)['object']['body']['result'] == result


def test_corrupted_retained_build_bytes_cannot_be_accepted_from_manifest_metadata_alone(store, ci_case):
    from air.storage import artifact_chunks
    _, report, user, policy, settings = ci_case
    request = retain(store, ci_case, report)
    with store.write() as conn:
        conn.execute(artifact_chunks.update().where(artifact_chunks.c.digest == report['build_digest'].split(':')[1])
                     .values(payload=b'corrupted build bytes'))
    before = store.counts()
    with pytest.raises(InvalidModel): ci_evidence.ingest(store, user, policy, request, settings)
    assert store.counts() == before
