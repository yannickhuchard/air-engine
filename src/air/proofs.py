"""Explicit, independently reviewed design evidence; never a claim of runtime execution.

Qualification is carried by a review of the exact baseline. The review service supplies
authority, independence, expiry and revocation; this module binds and checks its evidence.
"""
import json
from air.core import TEXT, digest, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.parsing import pairs
from air.parsing import parse
from air.projections import SNAPSHOT

ENGINE = 'air.design-proof/0.34'
ASSESSMENTS = {'type': 'array', 'minItems': 1, 'maxItems': 16, 'items': record({
    'run': SNAPSHOT, 'scope': {'enum': ['DESIGN_ONLY', 'MODEL_ONLY', 'EXECUTED_TEST']}, 'rationale': TEXT})}
DESIGN_QUALIFIED = {'QUALIFIED_DESIGN_REVIEW', 'QUALIFIED_MODEL_REPLAY'}
QUALIFIED = DESIGN_QUALIFIED | {'VERIFIED_EXTERNAL_TEST'}
DESIGN_REPORT = record({'format': {'const': ENGINE}, 'case': SNAPSHOT,
    'method': {'enum': ['ANALYSIS', 'INSPECTION', 'REVIEW']}, 'scope': {'const': 'DESIGN_ONLY'},
    'result': {'const': 'PASS'}, 'summary': TEXT, 'runtime_execution_attested': {'const': False}})


def _pin(obj):
    return {**exact(obj), 'digest': digest(obj)}


def assess(store, principal, policy, exported, request):
    """Validate explicit review assessments and compute immutable, JSON-safe bindings.

    Called both when recording and when reading an effective review. A readable blob
    proves its integrity, not its claims; only an independent design opinion is granted.
    """
    from air import artifacts
    assessments = request.get('proof_assessments', [])
    if not assessments: return []
    check_schema(assessments, ASSESSMENTS)
    if request['target'] != request['baseline'] or request['outcome'] != 'ACCEPTED':
        raise InvalidModel('Proof assessments require an accepted review of the exact baseline')
    index = {key(exact(o)): o for o in exported['objects']}
    for evidence in request['evidence']:
        obj = index.get(key(evidence))
        if obj is None or _pin(obj) != evidence:
            raise InvalidModel('Qualified review evidence must be pinned inside the baseline')
    result, cases = [], set()
    for assessment in assessments:
        run = index.get(key(assessment['run']))
        if run is None or run['meta']['type'] != 'air.VerificationRun' or _pin(run) != assessment['run']:
            raise InvalidModel('The assessed run must be an exact digest-pinned baseline member')
        body = run['body'];case = index.get(key(body['case']))
        if case is None or case['meta']['type'] != 'air.VerificationCase' or body['method'] != case['body']['method']:
            raise InvalidModel('The assessed run must use the exact case and method')
        if key(exact(case)) in cases: raise InvalidModel('A review must select exactly one run per assessed case')
        cases.add(key(exact(case)))
        if body['result'] != 'PASS': raise InvalidModel('A failed or inconclusive run cannot be qualified as a passing design assessment')
        method = body['method']
        expected_scope = 'EXECUTED_TEST' if method == 'TEST' else 'MODEL_ONLY' if method == 'SIMULATION' else 'DESIGN_ONLY'
        if assessment['scope'] != expected_scope: raise InvalidModel('Qualification scope does not match the verification method')
        report = body.get('report')
        if report is None: raise InvalidModel('Design evidence requires an immutable report artifact')
        lookup = {'artifact': {'id': report['locator'], 'digest': 'sha256:' + report['digest']['value']}}
        descriptor = artifacts.describe(store, principal, policy, lookup)
        if descriptor['artifact_reference'] != report or descriptor['size'] > artifacts.JSON_MAX_SIZE:
            raise InvalidModel('The exact evidence report must not exceed 512 KiB')
        descriptor, raw = artifacts.download(store, principal, policy, lookup)
        if method not in ('SIMULATION', 'TEST'):
            try: content = parse(raw)
            except ValueError as exc: raise InvalidModel('Malformed design report') from exc
            check_schema(content, DESIGN_REPORT)
            if content['case'] != _pin(case) or content['method'] != method:
                raise InvalidModel('Design report names a different case, oracle or method')
        publisher = store.get_record(report['locator'])
        entry = {'engine': ENGINE, 'baseline': request['baseline'], 'run': _pin(run), 'case': _pin(case),
            'method': method, 'scope': expected_scope, 'status': 'QUALIFIED_DESIGN_REVIEW',
            'report': report, 'report_publisher': publisher['payload']['identity'],
            'evidence': request['evidence'], 'oracle_digest': artifact_digest({
                'oracle': case['body']['oracle'], 'acceptance': case['body']['acceptance'], 'inputs': case['body']['inputs']}),
            'rationale': assessment['rationale'], 'runtime_execution_attested': False,
            'executor_claim': body['executor'], 'executor_claim_authenticated': False}
        if 'environment' in body:
            environment = index.get(key(body['environment']))
            if environment is None or environment['meta']['type'] != 'air.Environment':
                raise InvalidModel('The assessment environment must be an exact baseline member')
            entry['environment'] = _pin(environment)
        if method == 'TEST':
            from air.external_proofs import assess as assess_external
            entry.update(assess_external(store, principal, policy, exported, run, raw))
        if method == 'SIMULATION':
            from air.readiness import simulate_scenario, _members, SIMULATION_ENGINE
            try:
                if descriptor['media_type'] != 'application/json': raise InvalidModel('Simulation reports must be JSON artifacts')
                saved = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)
                if not isinstance(saved, dict) or saved.get('engine') != SIMULATION_ENGINE:
                    raise InvalidModel('Unsupported simulation report engine')
                origin = saved['baseline'];scenario = saved['scenario']
                check_schema(origin, SNAPSHOT);check_schema(scenario, SNAPSHOT)
                old, _ = _members(store, principal, policy, origin)
                # No changed input may inherit a result, even if its name is unchanged.
                for obj in old['objects']:
                    current = index.get(key(exact(obj)))
                    if current is None or digest(current) != digest(obj):
                        raise InvalidModel('Simulation inputs differ from the reviewed baseline')
                if key(scenario) != key(body['scenario']): raise InvalidModel('Run and report name different scenarios')
                scenario_obj = index[key(scenario)]
                if key(scenario_obj['body']['verification_case']) != key(body['case']):
                    raise InvalidModel('The simulation does not exercise the assessed case')
                reproduced = simulate_scenario(store, principal, policy, {'baseline': origin, 'scenario': scenario})
                if artifact_digest(saved) != artifact_digest(reproduced):
                    raise InvalidModel('Simulation report differs from the result reproduced by AIR')
                if reproduced['verdict'] != 'PASS' or reproduced['proof_level'] != body['proof_level']:
                    raise InvalidModel('The reproduced verdict or qualification differs from the run')
            except (KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
                raise InvalidModel('Simulation evidence could not be reproduced: ' + str(exc)) from exc
            entry.update(status='QUALIFIED_MODEL_REPLAY' if reproduced['model_qualification'] == 'CALIBRATED' else 'REPLAYED_DECLARED_MODEL',
                simulation_engine=SIMULATION_ENGINE, reproduced_report_digest=reproduced['report_digest'],
                model_qualification=reproduced['model_qualification'],
                measurement_provenance_automatically_qualified=False,
                measurement_freshness_automatically_qualified=False)
        result.append(entry)
    return result
