"""Optional P03 extension of the three isolated, entirely fictional Asteria journeys."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys

from air.core import DELIVERY_PROFILE, digest
from air.foundation import exact
from air.proofs import ENGINE


def qualify(call, case, objects, base, credential, home, port, session, output):
    def pin(obj): return {**exact(obj), 'digest': digest(obj)}
    function = next(o for o in objects if o['meta']['type'] == 'air.Function')
    evidence = next(o for o in objects if o['meta']['type'] == 'air.Evidence')
    meta = deepcopy(function['meta'])
    meta.update(id='urn:asteria:design-inspection:' + case['id'], type='air.VerificationCase',
                name='Inspection fictive de traçabilité - ' + case['title'])
    inspection = {'meta': meta, 'body': {'target': exact(function), 'method': 'INSPECTION', 'inputs': [],
        'oracle': 'La chaîne exigence, fonction, contrat et unité du dossier est présente dans la baseline.',
        'acceptance': 'Avis indépendant sur cette description de conception seulement.',
        'independence_basis': 'Relecteur distinct des auteurs du dossier et du rapport.'}}
    report = {'format': ENGINE, 'case': pin(inspection), 'method': 'INSPECTION', 'scope': 'DESIGN_ONLY',
        'result': 'PASS', 'summary': 'Inspection fictive de la description de ' + case['title'] +
        '. Les trois scénarios métier restent non exécutés.', 'runtime_execution_attested': False}
    artifact = call('/v1/artifacts/import', {'namespace': meta['namespace'],
        'idempotency_key': case['id'] + '-design-report', 'media_type': 'application/json',
        'content_base64': base64.b64encode(json.dumps(report, ensure_ascii=False).encode()).decode()}, credential)
    run_meta = deepcopy(meta);run_meta.update(id=meta['id'] + ':run', type='air.VerificationRun')
    run = {'meta': run_meta, 'body': {'case': exact(inspection), 'method': 'INSPECTION', 'result': 'PASS',
        'proof_level': 'INSPECTION', 'executed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'executor': 'urn:asteria:declared-inspector', 'summary': report['summary'], 'report': artifact['artifact_reference']}}
    call('/v1/draft-bundles', [inspection, run], credential)
    meta = deepcopy(base['baseline']['meta']);meta.update(id=meta['id'] + ':design-qualified')
    frozen = call('/v1/baselines', {'meta': meta, 'profile': DELIVERY_PROFILE,
        'members': [exact(o) for o in objects + [inspection, run]],
        'parent_baselines': [exact(base['baseline'])]}, credential)
    baseline = {**exact(frozen['baseline']), 'digest': frozen['digest']}
    request = {'baseline': baseline}
    before = call('/v1/readiness/assess', request, credential)
    assert before['proof']['qualified_design_cases'] == 0
    review = {'idempotency_key': case['id'] + '-design-review', 'baseline': baseline, 'target': baseline,
        'outcome': 'ACCEPTED', 'rationale': 'Avis fictif indépendant de conception, sans attestation de runtime.',
        'evidence': [pin(evidence)], 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z'),
        'proof_assessments': [{'run': pin(run), 'scope': 'DESIGN_ONLY', 'rationale': 'Rapport et oracle examinés explicitement.'}]}
    call('/v1/reviews', review, credential, expected=(403,))
    first = call('/v1/reviews', review, 'reviewer.json')['record']['id']
    assert not call('/v1/reviews', review, 'reviewer.json')['created']
    assert call('/v1/readiness/assess', request, credential)['proof']['qualified_design_cases'] == 1
    call('/v1/review-revocations', {'review_id': first, 'rationale': 'Exercice de retrait de la qualification.'}, 'reviewer.json')
    assert call('/v1/readiness/assess', request, credential)['proof']['qualified_design_cases'] == 0
    review['idempotency_key'] += '-renewed'
    active = call('/v1/reviews', review, 'reviewer.json')['record']['id']
    after = call('/v1/readiness/assess', request, credential)
    verification = next(c for c in after['criteria'] if c['code'] == 'VERIFICATION')
    assert verification['status'] == 'MET' and after['proof']['qualified_design_cases'] == 1
    assert after['proof']['verified_cases'] == 0 and not after['authorization_granted']
    replay = session.handle({'jsonrpc': '2.0', 'id': 30, 'method': 'tools/call',
        'params': {'name': 'air_assess_readiness', 'arguments': request}})
    assert replay['result']['structuredContent']['report_digest'] == after['report_digest']
    request_file = output / (case['id'] + '-readiness-request.json')
    request_file.write_text(json.dumps(request), encoding='utf-8')
    cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'readiness', str(request_file),
                          '--port', str(port), '--credential', credential], capture_output=True,
                         text=True, encoding='utf-8', timeout=60)
    assert cli.returncode == 0, 'CLI proof assessment failed'
    assert json.loads(cli.stdout)['report_digest'] == after['report_digest']
    pack = call('/v1/deliverables/compile', {'title': case['title'], 'baselines': [baseline]}, credential)
    texts = '\n'.join(f['content'] for f in pack['files'] if f['path'].endswith('.md'))
    assert active in texts and 'QUALIFIED_DESIGN_REVIEW' in texts
    (output / (case['id'] + '-design-readiness.json')).write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'status': 'PASS_SCOPED', 'baseline': baseline, 'review_ids': [first, active],
        'qualified_design_cases': 1, 'verified_runtime_cases': 0, 'verification_criterion': verification['status'],
        'self_review_refused': True, 'idempotent': True, 'revocation_removes_qualification': True,
        'cli_http_mcp_same_digest': True, 'deliverables_include_receipt': True,
        'runtime_execution_attested': False, 'report_digest': after['report_digest']}
