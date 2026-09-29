"""Qualified design opinion and reproducible model evidence never attest runtime execution."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from air import artifacts, readiness
from air.proofs import ENGINE
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import digest, validate
from air.foundation import InvalidModel, exact
from air.portability import export_registry, import_registry
from air.reviews import create_review, read_review, revoke_review
from air.storage import Store, Conflict, artifact_chunks
from test_artifacts import setup
from test_construction import construction, get
from test_delivery_032 import obj, frozen, delivery_model


def pin(o): return {**exact(o), 'digest': digest(o)}


def design_report(store, user, settings, case, name='design-report'):
    report = {'format': ENGINE, 'case': pin(case), 'method': case['body']['method'], 'scope': 'DESIGN_ONLY',
        'result': 'PASS', 'summary': 'Synthetic design assessment; no runtime execution.', 'runtime_execution_attested': False}
    return artifacts.put(store, user, AccessPolicy(), settings, {'namespace': case['meta']['namespace'],
        'idempotency_key': name, 'media_type': 'application/json'}, json.dumps(report).encode())['artifact_reference']


@pytest.fixture
def context(store, tmp_path, construction):
    settings, user, token, default, _ = setup(store, tmp_path)
    example = {'meta': deepcopy(get(construction, 'Function')['meta'])}
    case = obj(example, 'VerificationCase', 'independent-analysis', {'target': exact(get(construction, 'Function')),
        'method': 'ANALYSIS', 'inputs': [], 'oracle': 'Design consistency inspected',
        'acceptance': 'Independent design opinion', 'independence_basis': 'Independent reviewer'})
    artifact = design_report(store, user, settings, case)
    run = obj(example, 'VerificationRun', 'analysis-run', {'case': exact(case), 'method': 'ANALYSIS', 'result': 'PASS',
        'proof_level': 'ANALYSIS', 'executed_at': '2026-09-25T00:00:00Z', 'executor': 'urn:claimed:analyst',
        'summary': 'Design inspected', 'report': artifact})
    assert validate([case, run])['valid'], validate([case, run])['diagnostics']
    store.put_bundle(construction, 'architect');store.put_bundle([case, run], user['subject'])
    members = construction + [case, run]
    baseline = frozen(store, example, members, 'urn:proof:baseline')
    reviewer = {'subject': 'independent-reviewer', 'role': 'editor'}
    policy = AccessPolicy({'version': 'proof-1', 'subjects': {
        user['subject']: {'read': ['*'], 'write': ['*'], 'review': ['*']},
        reviewer['subject']: {'read': ['*'], 'review': ['*']}}})
    request = {'idempotency_key': 'qualified-design', 'baseline': baseline, 'target': baseline,
        'outcome': 'ACCEPTED', 'rationale': 'Explicit independent design assessment, not a runtime execution.',
        'evidence': [pin(get(construction, 'Source'))],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z'),
        'proof_assessments': [{'run': pin(run), 'scope': 'DESIGN_ONLY', 'rationale': 'Report covers this exact design oracle.'}]}
    return settings, user, token, example, members, case, run, baseline, reviewer, policy, request


def gate(store, c, baseline=None, policy=None):
    return readiness.assess_readiness(store, c[1], policy or c[9], {'baseline': baseline or c[7]})


def test_positive_design_qualification_is_explicit_independent_and_idempotent(store, context):
    c = context;_, user, _, _, _, case, run, _, reviewer, policy, request = c
    before = gate(store, c)
    assert before['proof']['qualified_design_cases'] == 0
    first = create_review(store, reviewer, policy, request)
    second = create_review(store, reviewer, policy, request)
    assert first['created'] and not second['created'] and first['record'] == second['record']
    reviewed = read_review(store, user, policy, first['record']['id'])
    [q] = reviewed['proof_qualifications']
    assert reviewed['effective'] and q['run'] == pin(run) and q['case'] == pin(case)
    assert not q['runtime_execution_attested'] and not q['executor_claim_authenticated']
    after = gate(store, c)
    verification = next(x for x in after['criteria'] if x['code'] == 'VERIFICATION')
    assert verification['status'] == 'MET' and after['proof']['qualified_design_cases'] == 1
    assert after['proof']['verified_cases'] == 0 and not after['authorization_granted']
    with pytest.raises(Forbidden): create_review(store, user, policy, {**request, 'idempotency_key': 'self'})
    changed = deepcopy(request);changed['proof_assessments'][0]['rationale'] = 'Changed opinion'
    with pytest.raises(Conflict): create_review(store, reviewer, policy, changed)


@pytest.mark.parametrize('change', ['revoked', 'expired', 'policy', 'mandate', 'new_baseline', 'rejected'])
def test_qualification_loses_effect_with_its_authority_or_context(store, context, monkeypatch, change):
    c = context;_, _, _, example, members, _, _, baseline, reviewer, policy, request = c
    receipt = create_review(store, reviewer, policy, request)['record']['id']
    if change == 'revoked': revoke_review(store, reviewer, policy, {'review_id': receipt, 'rationale': 'Withdraw opinion'})
    if change == 'expired':
        class Future(datetime):
            @classmethod
            def now(cls, tz=None): return datetime.now(tz) + timedelta(days=2)
        monkeypatch.setattr('air.reviews.datetime', Future)
    if change in ('policy', 'mandate'):
        document = deepcopy(policy.document)
        if change == 'policy': document['version'] = 'proof-2'
        else: document['subjects'][reviewer['subject']]['review'] = []
        policy = AccessPolicy(document)
    if change == 'new_baseline': baseline = frozen(store, example, members, 'urn:proof:new-baseline')
    if change == 'rejected':
        reject = {k: v for k, v in request.items() if k != 'proof_assessments'}
        create_review(store, reviewer, policy, {**reject, 'idempotency_key': 'reject', 'outcome': 'REJECTED'})
    report = gate(store, c, baseline, policy)
    assert report['proof']['qualified_design_cases'] == 0
    assert next(x for x in report['criteria'] if x['code'] == 'VERIFICATION')['status'] == 'NOT_MET'


@pytest.mark.parametrize('fault', ['missing_report', 'wrong_digest', 'failed', 'inconclusive', 'runtime_test', 'wrong_scope', 'duplicate_case', 'stale_report'])
def test_unqualified_or_incompatible_claims_are_refused(store, context, fault):
    c = context;settings, user, _, example, members, case, run, _, reviewer, policy, request = c
    case, run, request = deepcopy(case), deepcopy(run), deepcopy(request)
    case['meta']['id'] += '-bad';run['meta']['id'] += '-bad';run['body']['case'] = exact(case)
    if fault == 'missing_report': run['body'].pop('report')
    if fault in ('failed', 'inconclusive'): run['body']['result'] = fault.upper().replace('FAILED', 'FAIL')
    if fault == 'runtime_test':
        case['body']['method'] = 'TEST';run['body'].update(method='TEST', proof_level='EXECUTED_TEST')
    if fault not in ('missing_report', 'stale_report'): run['body']['report'] = design_report(store, user, settings, case, 'bad-case-report')
    store.put_bundle([case, run], 'architect')
    baseline = frozen(store, example, members + [case, run], 'urn:proof:invalid')
    request.update(baseline=baseline, target=baseline)
    request['proof_assessments'] = [{'run': pin(run), 'scope': 'DESIGN_ONLY', 'rationale': 'Synthetic check'}]
    if fault == 'wrong_digest': request['proof_assessments'][0]['run']['digest'] = 'sha256:' + '0' * 64
    if fault == 'wrong_scope': request['proof_assessments'][0]['scope'] = 'MODEL_ONLY'
    if fault == 'duplicate_case': request['proof_assessments'].append(deepcopy(request['proof_assessments'][0]))
    with pytest.raises(InvalidModel): create_review(store, reviewer, policy, request)


def test_competing_qualified_runs_require_explicit_resolution_not_client_dates(store, context):
    c = context;_, _, _, example, members, _, run, _, reviewer, policy, request = c
    other = deepcopy(run);other['meta']['id'] += '-other';other['body']['executed_at'] = '2099-01-01T00:00:00Z'
    store.put(other, 'architect')
    baseline = frozen(store, example, members + [other], 'urn:proof:competing')
    first = {**request, 'baseline': baseline, 'target': baseline}
    receipt = create_review(store, reviewer, policy, first)['record']['id']
    assert gate(store, c, baseline)['proof']['qualified_design_cases'] == 1, 'a future declared date cannot supersede the reviewed selection'
    second = {**first, 'idempotency_key': 'competing', 'proof_assessments': [{**first['proof_assessments'][0], 'run': pin(other)}]}
    create_review(store, reviewer, policy, second)
    report = gate(store, c, baseline)
    states = next(x for x in report['criteria'] if x['code'] == 'VERIFICATION')['detail']['by_status']
    assert states['CONFLICTING_QUALIFICATIONS'] == 1 and report['proof']['qualified_design_cases'] == 0
    revoke_review(store, reviewer, policy, {'review_id': receipt, 'rationale': 'Superseded explicitly'})
    assert gate(store, c, baseline)['proof']['qualified_design_cases'] == 1


def test_proof_is_integrity_checked_on_read_and_survives_registry_restore(store, context, tmp_path):
    c = context;_, user, _, _, _, _, _, _, reviewer, policy, request = c
    receipt = create_review(store, reviewer, policy, request)['record']['id']
    package = tmp_path / 'transfer'
    export_registry(store, package, policy.document)
    url = 'sqlite:///' + (tmp_path / 'restored.db').as_posix()
    import_registry(package, url)
    restored = Store(url)
    try:
        assert gate(restored, c)['proof']['qualified_design_cases'] == 1
        assert read_review(restored, user, policy, receipt)['effective']
    finally: restored.engine.dispose()
    checksum = c[6]['body']['report']['digest']['value']
    with store.write() as conn:
        conn.execute(update(artifact_chunks).where(artifact_chunks.c.digest == checksum).values(payload=b'corrupted test blob'))
    assert 'PROOF_UNAVAILABLE' in read_review(store, user, policy, receipt)['ineffective_reasons']
    assert gate(store, c)['proof']['qualified_design_cases'] == 0


def test_the_existing_review_api_uses_the_same_qualification_service(store, context, tmp_path):
    c = context;settings, _, _, _, _, _, _, baseline, reviewer, policy, request = c
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    credential = store.create_token(reviewer['subject'], 'editor')
    with TestClient(create_app(settings, run_worker=False)) as client:
        headers = {'Authorization': 'Bearer ' + credential['access_token']}
        response = client.post('/v1/reviews', json=request, headers=headers)
        assert response.status_code == 200
        report = client.post('/v1/readiness/assess', json={'baseline': baseline}, headers=headers)
        assert report.status_code == 200 and report.json()['proof']['qualified_design_cases'] == 1
        from air.mcp import PROTOCOL
        mcp = client.post('/mcp', headers={**headers, 'Host': '127.0.0.1:8740',
            'Accept': 'application/json, text/event-stream', 'mcp-protocol-version': PROTOCOL},
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': 'air_assess_readiness', 'arguments': {'baseline': baseline}}})
        assert mcp.status_code == 200
        assert mcp.json()['result']['structuredContent']['report_digest'] == report.json()['report_digest']
        forged = {**request, 'actor': 'somebody-else'}
        assert client.post('/v1/reviews', json=forged, headers=headers).status_code == 422


@pytest.mark.parametrize('fault', ['none', 'declared', 'altered_report', 'changed_inputs', 'unknown_engine', 'engine_changed_after_review'])
def test_simulation_evidence_is_reproduced_on_unchanged_exact_inputs(store, context, monkeypatch, fault):
    c = context;settings, user, _, example, members, _, _, _, reviewer, policy, request = c
    extra = delivery_model(example, members)
    observations = []
    if fault != 'declared':
        scope = exact(get(members, 'Scope'))
        for step in extra[1]['body']['steps']:
            observation = obj(example, 'RuntimeObservation', 'duration-' + step['step'], {'instance_or_scope': scope,
                'metric_or_signal': 'latency p95 ' + step['step'],
                'window': {'start': '2026-09-24T00:00:00Z', 'end': '2026-09-25T00:00:00Z'},
                'value_or_artifact': {'type': 'Quantity[ms]', 'value': '100'},
                'coverage': {'scope': scope, 'included': [scope], 'excluded': [], 'completeness': 'PARTIAL',
                             'limitations': ['Synthetic measurements for a model, not a runtime attestation']}})
            observation['meta']['provenance']['source_refs'] = [exact(get(members, 'Source'))]
            observations.append(observation)
            step.update(distribution={'kind': 'FIXED', 'value': 100}, calibrated_from=[exact(observation)])
    store.put_bundle(extra + observations, 'architect')
    origin_members = members + extra + observations
    origin = frozen(store, example, origin_members, 'urn:proof:simulation-origin')
    recorded = readiness.record_simulation(store, user, AccessPolicy(), settings, {'baseline': origin,
        'scenario': pin(extra[3]), 'run_id': 'urn:proof:simulation-run', 'idempotency_key': 'model-run'})
    run = recorded['verification_run']
    if fault in ('altered_report', 'unknown_engine'):
        false = deepcopy(recorded['report'])
        if fault == 'altered_report': false['latency_ms']['p95'] = 0
        else: false['engine'] = 'unknown-simulation-engine'
        changed = artifacts.put(store, user, AccessPolicy(), settings, {'namespace': example['meta']['namespace'],
            'idempotency_key': 'false-report', 'media_type': 'application/json'}, json.dumps(false).encode())
        run['body']['report'] = changed['artifact_reference']
    if fault == 'changed_inputs':
        revised = deepcopy(extra[1]);revised['meta']['revision'] = 2;revised['body']['basis'] = 'Changed assumptions'
        scenario = deepcopy(extra[3]);scenario['meta']['revision'] = 2;scenario['body']['performance_model'] = exact(revised)
        store.put_bundle([revised, scenario], 'architect')
        origin_members = [o for o in origin_members if o['meta']['id'] not in (revised['meta']['id'], scenario['meta']['id'])] + [revised, scenario]
        run['body']['scenario'] = exact(scenario)
    store.put(run, user['subject'])
    baseline = frozen(store, example, origin_members + [run], 'urn:proof:simulation-reviewed')
    reviewed = {**request, 'idempotency_key': 'model-review', 'baseline': baseline, 'target': baseline,
        'proof_assessments': [{'run': pin(run), 'scope': 'MODEL_ONLY', 'rationale': 'Explicit assessment of the numerical model and its limits'}]}
    if fault in ('altered_report', 'changed_inputs', 'unknown_engine'):
        with pytest.raises(InvalidModel): create_review(store, reviewer, policy, reviewed)
    else:
        receipt = create_review(store, reviewer, policy, reviewed)['record']['id']
        [q] = read_review(store, user, policy, receipt)['proof_qualifications']
        assert q['status'] == ('REPLAYED_DECLARED_MODEL' if fault == 'declared' else 'QUALIFIED_MODEL_REPLAY')
        assert not q['runtime_execution_attested']
        assert gate(store, c, baseline)['proof']['qualified_design_cases'] == (0 if fault == 'declared' else 1)
        if fault == 'engine_changed_after_review':
            monkeypatch.setattr(readiness, 'SIMULATION_ENGINE', 'unsupported-new-engine')
            assert not read_review(store, user, policy, receipt)['effective']
            assert gate(store, c, baseline)['proof']['qualified_design_cases'] == 0


def test_qualified_evidence_must_belong_to_the_reviewed_baseline(store, context):
    c = context;_, _, _, _, members, _, _, _, reviewer, policy, request = c
    outside = deepcopy(get(members, 'Source'));outside['meta']['id'] += ':outside'
    store.put(outside, 'architect')
    with pytest.raises(InvalidModel, match='inside the baseline'):
        create_review(store, reviewer, policy, {**request, 'evidence': [pin(outside)]})
