"""P03: authentic, fresh and exact external reports; no promotion of arbitrary uploaded claims."""
import base64
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import subprocess
import sys
import rfc8785
import pytest
pytest.importorskip('cryptography')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from air import external_proofs as proof
from air import proof_runner, readiness
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.foundation import InvalidModel, exact
from air.reviews import create_review, read_review
from air.storage import Conflict, Store
from air.portability import export_registry, import_registry
from test_proof_qualification import context, pin
from test_construction import construction, get
from test_delivery_032 import frozen, obj


@pytest.fixture
def execution(store, context, tmp_path):
    c = context;settings, user, _, example, members, _, _, _, reviewer, old_policy, review = c
    document = deepcopy(old_policy.document)
    executor = 'urn:asteria:runner:test-lab'
    document['subjects'][executor] = {'attest': [example['meta']['namespace']]}
    policy = AccessPolicy(document)
    (tmp_path / 'access-policy.json').write_text(json.dumps(document), encoding='utf-8')
    env = obj(example, 'Environment', 'test-lab', {'stage': 'BUILD_TEST', 'purpose': 'Isolated synthetic acceptance', 'hosting': 'Local Python process'})
    store.put(env, 'architect')
    members = members + [env]
    baseline = frozen(store, example, members, 'urn:external:origin')
    case = next(o for o in members if o['meta']['type'] == 'air.VerificationCase' and o['body']['method'] == 'TEST')
    key = Ed25519PrivateKey.generate()
    suite = tmp_path / 'selected_suite.py'
    suite.write_text('import unittest\nclass Acceptance(unittest.TestCase):\n def test_frozen_contract(self): self.assertEqual(2 + 2, 4)\n', encoding='utf-8')
    checksum = 'sha256:' + hashlib.sha256(suite.read_bytes()).hexdigest()
    now = proof.clock()
    trust = {'key_id': 'lab-1', 'executor': executor, 'public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode(),
        'namespaces': [example['meta']['namespace']], 'not_before': proof.stamp(now - timedelta(seconds=10)),
        'expires_at': proof.stamp(now + timedelta(days=1)), 'max_age_seconds': 600,
        'suite_digests': [checksum], 'environments': [pin(env)]}
    proof.register_key(store, settings, trust)
    request = {'idempotency_key': 'external-challenge', 'baseline': baseline, 'case': pin(case), 'environment': pin(env),
        'run_id': 'urn:external:run', 'key_id': 'lab-1', 'suite_digest': checksum, 'ttl_seconds': 3600}
    challenge = proof.challenge(store, user, policy, settings, request)
    result = {'format': proof.ENGINE, 'adapter': proof.ADAPTER, 'challenge': challenge['challenge'],
        'nonce': challenge['binding']['nonce'], 'executor': executor, 'key_id': 'lab-1', 'suite_digest': checksum,
        'started_at': proof.stamp(proof.clock()), 'finished_at': proof.stamp(proof.clock()),
        'tests': [{'id': 'Acceptance.test_frozen_contract', 'status': 'PASS'}]}
    return {'c': c, 'settings': settings, 'user': user, 'members': members, 'example': example, 'policy': policy,
        'reviewer': reviewer, 'review': review, 'key': key, 'trust': trust, 'request': request,
        'challenge': challenge, 'result': result, 'suite': suite, 'env': env, 'case': case}


def sign(e, result=None):
    result = deepcopy(result or e['result'])
    return {'result': result, 'signature': base64.b64encode(e['key'].sign(rfc8785.dumps(result))).decode()}


def qualify(store, e, report=None, members=None):
    imported = proof.import_report(store, e['user'], e['policy'], e['settings'], {'attestation': report or sign(e)})
    run = imported['verification_run'];store.put(run, e['user']['subject'])
    baseline = frozen(store, e['example'], (members or e['members']) + [run], 'urn:external:reviewed')
    assert readiness.assess_readiness(store, e['user'], e['policy'], {'baseline': baseline})['proof']['verified_cases'] == 0
    request = {**e['review'], 'baseline': baseline, 'target': baseline, 'idempotency_key': 'external-review',
        'proof_assessments': [{'run': pin(run), 'scope': 'EXECUTED_TEST', 'rationale': 'Qualified test report and exact context inspected'}]}
    receipt = create_review(store, e['reviewer'], e['policy'], request)
    return baseline, request, receipt


def test_external_positive_authority_replay_and_registry_restore(store, execution, tmp_path):
    e = execution
    assert not proof.challenge(store, e['user'], e['policy'], e['settings'], e['request'])['created']
    baseline, request, receipt = qualify(store, e)
    again = proof.import_report(store, e['user'], e['policy'], e['settings'], {'attestation': sign(e)})
    assert not again['created']
    changed = deepcopy(e['result']);changed['tests'][0]['id'] += '-replay'
    with pytest.raises(Conflict): proof.import_report(store, e['user'], e['policy'], e['settings'], {'attestation': sign(e, changed)})
    report = readiness.assess_readiness(store, e['user'], e['policy'], {'baseline': baseline})
    assert report['proof']['verified_cases'] == 1 and report['proof']['runtime_execution_attested']
    assert not report['authorization_granted']
    q = read_review(store, e['user'], e['policy'], receipt['record']['id'])['proof_qualifications'][0]
    assert q['status'] == 'VERIFIED_EXTERNAL_TEST' and q['executor_claim_authenticated']
    bundle = tmp_path / 'transfer';export_registry(store, bundle, e['policy'].document)
    url = 'sqlite:///' + (tmp_path / 'restored.db').as_posix();import_registry(bundle, url)
    restored = Store(url)
    try: assert readiness.assess_readiness(restored, e['user'], e['policy'], {'baseline': baseline})['report_digest'] == report['report_digest']
    finally: restored.engine.dispose()


@pytest.mark.parametrize('fault', ['signature', 'executor', 'key', 'nonce', 'suite', 'engine', 'future', 'old', 'empty', 'duplicate', 'challenge', 'revoked', 'mandate'])
def test_untrusted_external_claims_are_refused(store, execution, fault):
    e = execution;result = deepcopy(e['result'])
    if fault == 'executor': result['executor'] = 'urn:attacker'
    if fault == 'key': result['key_id'] = 'unknown'
    if fault == 'nonce': result['nonce'] = '0' * 32
    if fault == 'suite': result['suite_digest'] = 'sha256:' + '0' * 64
    if fault == 'engine': result['adapter'] = 'unknown/1'
    if fault == 'future': result['finished_at'] = proof.stamp(proof.clock() + timedelta(hours=1))
    if fault == 'old': result['started_at'] = proof.stamp(proof.clock() - timedelta(hours=1))
    if fault == 'empty': result['tests'] = []
    if fault == 'duplicate': result['tests'] *= 2
    if fault == 'challenge': result['challenge']['digest'] = 'sha256:' + '0' * 64
    envelope = sign(e, result)
    if fault == 'signature': envelope['signature'] = base64.b64encode(b'x' * 64).decode()
    if fault == 'revoked': proof.revoke_key(store, {'key_id': 'lab-1', 'rationale': 'Withdraw executor'})
    if fault == 'mandate':
        doc = deepcopy(e['policy'].document);doc['subjects'][e['trust']['executor']]['attest'] = [];e['policy'] = AccessPolicy(doc)
    with pytest.raises((InvalidModel, Forbidden)):
        proof.import_report(store, e['user'], e['policy'], e['settings'], {'attestation': envelope})
    assert store.get_record(proof.execution_id(e['challenge']['challenge']['id'])) is None


@pytest.mark.parametrize('fault', ['revoke', 'expire', 'key_expire', 'freshness', 'policy', 'oracle', 'environment'])
def test_effective_proof_is_lost_when_its_context_or_authority_changes(store, execution, monkeypatch, fault):
    e = execution
    if fault in ('oracle', 'environment'):
        old = e['case'] if fault == 'oracle' else e['env'];changed = deepcopy(old);changed['meta']['revision'] = 2
        if fault == 'oracle': changed['body']['oracle'] += ' new oracle'
        else: changed['body']['hosting'] = 'Different host'
        store.put(changed, 'architect')
        # Keep closure valid: adding an additional revision is impossible, so an altered run is refused before review.
        imported = proof.import_report(store, e['user'], e['policy'], e['settings'], {'attestation': sign(e)})
        run = imported['verification_run'];run['body']['case' if fault == 'oracle' else 'environment'] = exact(changed)
        from air.external_proofs import assess
        exported = {'objects': e['members'] + [changed]}
        with pytest.raises(InvalidModel): assess(store, e['reviewer'], e['policy'], exported, run, rfc8785.dumps(sign(e)))
        return
    baseline, request, receipt = qualify(store, e)
    if fault == 'revoke': proof.revoke_key(store, {'key_id': 'lab-1', 'rationale': 'Withdrawal'})
    if fault in ('expire', 'freshness', 'key_expire'):
        original = proof.clock()
        monkeypatch.setattr(proof, 'clock', lambda: original + timedelta(seconds={'expire': 3601, 'freshness': 601, 'key_expire': 172800}[fault]))
    if fault == 'policy':
        doc = deepcopy(e['policy'].document);doc['subjects'][e['trust']['executor']]['attest'] = [];e['policy'] = AccessPolicy(doc)
    assert not read_review(store, e['user'], e['policy'], receipt['record']['id'])['effective']
    assert readiness.assess_readiness(store, e['user'], e['policy'], {'baseline': baseline})['proof']['verified_cases'] == 0


@pytest.mark.parametrize('status', ['FAIL', 'ERROR', 'SKIP', 'EXPECTED_FAILURE', 'UNEXPECTED_SUCCESS'])
def test_nonpassing_or_unexecuted_test_is_never_verified(store, execution, status):
    result = deepcopy(execution['result']);result['tests'][0]['status'] = status
    with pytest.raises(InvalidModel): qualify(store, execution, sign(execution, result))


def test_real_external_runner_and_authenticated_api(store, execution, tmp_path):
    e = execution
    challenge = tmp_path / 'challenge.json';challenge.write_text(json.dumps(e['challenge']), encoding='utf-8')
    key = tmp_path / 'key.json';key.write_text(json.dumps({'private_key': base64.b64encode(e['key'].private_bytes_raw()).decode()}), encoding='utf-8')
    output = tmp_path / 'signed.json'
    completed = subprocess.run([sys.executable, '-m', 'air.proof_runner', 'run', '--challenge', str(challenge),
        '--suite', str(e['suite']), '--key', str(key), '--output', str(output)], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['all_passed']
    token = e['c'][2]
    with TestClient(create_app(e['settings'], run_worker=False)) as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        imported = client.post('/v1/proofs/import', json=json.loads(output.read_text()), headers=headers)
        assert imported.status_code == 200 and imported.json()['verification_run']['body']['result'] == 'PASS'
        assert token['access_token'] not in imported.text and key.read_text() not in completed.stdout
        forged = client.post('/v1/proofs/challenges', json={**e['request'], 'executor': 'urn:attacker'}, headers=headers)
        assert forged.status_code == 422
