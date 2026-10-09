"""P03/P04 reception on real isolated HTTP/CLI/MCP, using explicitly synthetic test suites."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from air.config import Settings
from air.core import DELIVERY_PROFILE, digest
from air.foundation import exact
from air.proof_runner import keygen
from air.external_proofs import clock, stamp

ROOT = Path(__file__).resolve().parents[1]


def qualify(call, case, objects, base, credential, home, port, session, output):
    def pin(obj): return {**exact(obj), 'digest': digest(obj)}
    def cli(command, path):
        args = [sys.executable, '-m', 'air', '--home', str(home), command, str(path)]
        if command not in ('proof-key-register', 'proof-key-revoke'): args += ['--port', str(port), '--credential', credential]
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, 'External proof CLI failed: ' + command
        return json.loads(result.stdout)
    def document(name, value):
        path = output / (case['id'] + '-' + name + '.json')
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return path
    function = next(o for o in objects if o['meta']['type'] == 'air.Function')
    source = next(o for o in objects if o['meta']['type'] == 'air.Source')
    def obj(kind, suffix, body):
        meta = deepcopy(function['meta']);meta.update(type='air.' + kind, id='urn:asteria:external:' + case['id'] + ':' + suffix,
            name='Recette synthétique ' + case['id'] + ' - ' + suffix)
        return {'meta': meta, 'body': body}
    test = obj('VerificationCase', 'case', {'target': exact(function), 'method': 'TEST', 'inputs': [],
        'oracle': 'Le test Python synthétique épinglé réussit, sans appeler ERP, atelier ou IAM réels.',
        'acceptance': 'Attestation du runner et avis indépendant sur ce seul test.', 'independence_basis': 'Runner et relecteur distincts'})
    env = obj('Environment', 'environment', {'stage': 'BUILD_TEST', 'purpose': 'Recette synthétique de l’adaptateur de preuve', 'hosting': 'Python local isolé'})
    call('/v1/draft-bundles', [test, env], credential)
    def freeze(suffix, members):
        meta = deepcopy(base['baseline']['meta']);meta['id'] += ':' + suffix
        frozen = call('/v1/baselines', {'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in members],
                                      'parent_baselines': [exact(base['baseline'])]}, credential)
        return {**exact(frozen['baseline']), 'digest': frozen['digest']}
    members = objects + [test, env];origin = freeze('external-origin', members)
    suite = ROOT / 'fixtures/enterprise/asteria/proofs' / {'D01': 'sav.py', 'D02': 'atelier.py', 'D03': 'identites.py'}[case['id']]
    key_directory = home / ('runner-' + case['id']);keygen(key_directory)
    checksum = 'sha256:' + hashlib.sha256(suite.read_bytes()).hexdigest()
    key_id = case['id'] + '-runner';current = clock()
    trust = {'key_id': key_id, 'executor': 'urn:asteria:runner:' + case['id'],
        **json.loads((key_directory / 'public.json').read_text()), 'namespaces': [test['meta']['namespace']],
        'not_before': stamp(current - timedelta(seconds=5)), 'expires_at': stamp(current + timedelta(days=1)),
        'max_age_seconds': 3600, 'suite_digests': [checksum], 'environments': [pin(env)]}
    cli('proof-key-register', document('trust', trust))
    request = {'idempotency_key': case['id'] + '-execution', 'baseline': origin, 'case': pin(test), 'environment': pin(env),
        'run_id': test['meta']['id'] + ':run', 'key_id': key_id, 'suite_digest': checksum, 'ttl_seconds': 3600}
    challenge = cli('proof-challenge', document('challenge-request', request))
    challenge_path = document('challenge', challenge)
    signed = output / (case['id'] + '-signed-result.json')
    result = subprocess.run([sys.executable, '-m', 'air.proof_runner', 'run', '--challenge', str(challenge_path),
        '--suite', str(suite), '--key', str(key_directory / 'private.json'), '--output', str(signed)],
        capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0 and json.loads(result.stdout)['all_passed']
    imported = cli('proof-import', signed)
    assert not cli('proof-import', signed)['created']
    tampered = json.loads(signed.read_text());tampered['attestation']['result']['tests'][0]['id'] += '-forged'
    call('/v1/proofs/import', tampered, credential, expected=(422,))
    run = imported['verification_run'];call('/v1/draft-bundles', [run], credential)
    baseline = freeze('external-reviewed', members + [run])
    review = {'idempotency_key': case['id'] + '-external-review', 'baseline': baseline, 'target': baseline,
        'outcome': 'ACCEPTED', 'rationale': 'Test synthétique signé réceptionné ; aucun scénario métier réel exécuté.',
        'evidence': [pin(source)], 'expires_at': stamp(clock() + timedelta(hours=1)),
        'proof_assessments': [{'run': pin(run), 'scope': 'EXECUTED_TEST', 'rationale': 'Signature, oracle et environnement synthétique examinés.'}]}
    receipt = call('/v1/reviews', review, 'reviewer.json')['record']['id']
    request = {'baseline': baseline};report = call('/v1/readiness/assess', request, credential)
    assert report['proof']['verified_cases'] == 1
    mcp = session.handle({'jsonrpc': '2.0', 'id': 41, 'method': 'tools/call', 'params': {'name': 'air_assess_readiness', 'arguments': request}})
    assert mcp['result']['structuredContent']['report_digest'] == report['report_digest']
    assert cli('readiness', document('external-readiness-request', request))['report_digest'] == report['report_digest']
    document('external-readiness', report)
    cli('proof-key-revoke', document('withdraw-executor', {'key_id': key_id, 'rationale': 'Recette du retrait de mandat.'}))
    withdrawn = call('/v1/readiness/assess', request, credential)
    assert withdrawn['proof']['verified_cases'] == 0
    return {'status': 'PASS_SCOPED', 'baseline': baseline, 'review_id': receipt, 'suite_digest': checksum,
        'synthetic_external_tests_executed': 1, 'business_runtime_tests_executed': False,
        'signed_report_imported': True, 'tampering_refused': True, 'idempotent': True,
        'cli_http_mcp_same_digest': True, 'executor_revocation_removes_qualification': True,
        'qualified_before_revocation': 1, 'qualified_after_revocation': 0, 'report_digest': report['report_digest']}
