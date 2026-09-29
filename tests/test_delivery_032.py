"""Tranche 32: ready to build as a result, and simulations that say how much they prove."""
from copy import deepcopy
import pytest
from air import agent, readiness
from air.access import AccessPolicy
from air.config import Settings
from air.core import DELIVERY_PROFILE, digest, validate
from air.foundation import exact, validate_graph
from test_architecture import prepare as prepare_architecture, find

POLICY = AccessPolicy()


def obj(example, kind, name, body, revision=1):
    meta = deepcopy(example['meta']);meta.update(id='urn:delivery:' + name, type='air.' + kind, name=name, revision=revision)
    return {'meta': meta, 'body': body}


def expression(op, name, value):
    return {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
            'required_inputs': [{'name': name, 'type': 'Integer'}], 'ast': {'op': op, 'args': [{'ref': name}, {'literal': {'type': 'Integer', 'value': value}}]}}


def delivery_model(example, objects):
    """A fraud-like cycle: sense, assess, act when the score is 50 or more, escalate at 80 or more."""
    function = exact(find(objects, 'Function'));actor = exact(find(objects, 'Actor'))
    step = lambda sid: {'binding': 'air.workflow-step/0.22', 'id': sid, 'name': sid, 'function': function, 'participants': [actor]}
    flow = lambda fid, s, t, cond, guard=None: {'binding': 'air.workflow-flow/0.32', 'id': fid, 'source': s, 'target': t, 'condition': cond,
                                                **({'guard': guard} if guard else {})}
    workflow = obj(example, 'Workflow', 'cycle', {'steps': [step('sense'), step('assess'), step('act'), step('escalate')],
        'flows': [flow('f1', 'sense', 'assess', 'Every signal'), flow('f2', 'assess', 'act', 'Score 50 or more', expression('gte', 'score', 50)),
                  flow('f3', 'act', 'escalate', 'Score 80 or more', expression('gte', 'score', 80))],
        'start_steps': ['sense'], 'termination_policy': 'Ends when no guard holds', 'compensations': []})
    model = obj(example, 'PerformanceModel', 'model', {'workflow': exact(workflow), 'basis': 'Declared budgets per step',
        'steps': [{'step': 'sense', 'distribution': {'kind': 'TRIANGULAR', 'min': 50, 'mode': 120, 'max': 200}},
                  {'step': 'assess', 'distribution': {'kind': 'LOGNORMAL', 'median': 400, 'p95': 900}},
                  {'step': 'act', 'distribution': {'kind': 'UNIFORM', 'min': 100, 'max': 300}},
                  {'step': 'escalate', 'distribution': {'kind': 'FIXED', 'value': 1000}}]})
    case = obj(example, 'VerificationCase', 'latency-case', {'target': function, 'method': 'SIMULATION', 'inputs': [],
        'oracle': 'p95 from sense to act at most 2000 ms', 'acceptance': 'Simulation verdict PASS', 'independence_basis': 'Seeded model'})
    scenario = obj(example, 'SimulationScenario', 'latency', {'workflow': exact(workflow), 'performance_model': exact(model),
        'measure': {'from_step': 'sense', 'to_step': 'act'}, 'target': {'percentile': 95, 'max_ms': 2000}, 'verification_case': exact(case),
        'classes': [{'name': 'low', 'weight': 70, 'context': {'score': {'type': 'Integer', 'value': 10}}},
                    {'name': 'medium', 'weight': 20, 'context': {'score': {'type': 'Integer', 'value': 60}}},
                    {'name': 'high', 'weight': 10, 'context': {'score': {'type': 'Integer', 'value': 90}}}],
        'runs': 2000, 'seed': 7})
    return [workflow, model, case, scenario]


def frozen(store, example, members, name='urn:delivery:baseline'):
    meta = deepcopy(example['meta']);meta.update(id=name, type='air.Baseline')
    result = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fixture')
    return {**exact(result['baseline']), 'digest': result['digest']}


@pytest.fixture
def delivery(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    extra = delivery_model(example, objects)
    store.put_bundle(extra, 'fixture')
    return objects + extra, user, frozen(store, example, objects + extra), extra


def test_the_simulation_is_seeded_guarded_and_honest_about_its_model(store, delivery):
    members, user, baseline, extra = delivery
    scenario = {**exact(extra[3]), 'digest': digest(extra[3])}
    first = readiness.simulate_scenario(store, user, POLICY, {'baseline': baseline, 'scenario': scenario})
    assert first == readiness.simulate_scenario(store, user, POLICY, {'baseline': baseline, 'scenario': scenario}), 'same seed, same report'
    assert first['verdict'] == 'PASS' and first['observed_at_target_percentile'] <= 2000
    assert first['model_qualification'] == 'DECLARED' and first['proof_level'] == 'DECLARED_MODEL_SIMULATION'
    classes = {c['name']: c for c in first['classes']}
    assert classes['low']['measure_not_reached'] == classes['low']['runs'], 'a low score never reaches act'
    assert all('escalate' in path for path in classes['high']['paths']) and not any('escalate' in p for p in classes['medium']['paths'])
    assert first['unguarded_flows'] == ['f1'] and first['latency_ms']['measured_runs'] == classes['medium']['runs'] + classes['high']['runs']


def test_a_recorded_run_counts_as_declared_model_proof_until_calibrated(store, tmp_path, example, delivery):
    members, user, baseline, extra = delivery
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test')
    user['authorization']['instance_id'] = settings.instance_id
    recorded = readiness.record_simulation(store, user, POLICY, settings, {'baseline': baseline, 'scenario': {**exact(extra[3]), 'digest': digest(extra[3])},
                                                                           'run_id': 'urn:delivery:run-1', 'idempotency_key': 'run-1'})
    run = recorded['verification_run']
    assert validate(run)['valid'] and run['body']['proof_level'] == 'DECLARED_MODEL_SIMULATION' and run['body']['result'] == 'PASS'
    assert not recorded['registry_written'] and recorded['artifact_stored']
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': baseline, 'objects': [run], 'include_bundle': True})
    store.put_bundle(rebased['objects'], 'architect');after = store.create_baseline(rebased['baseline_request'], 'architect')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': {**exact(after['baseline']), 'digest': after['digest']}})
    verification = next(c for c in gate['criteria'] if c['code'] == 'VERIFICATION')
    statuses = {c['name']: c['status'] for c in verification['detail']['cases_detail']}
    assert statuses['latency-case'] == 'PASS_ON_DECLARED_MODEL' and gate['proof']['declared_model_passes'] == 1
    assert verification['status'] == 'NOT_MET', 'a declared model is not verified proof'


def test_the_gate_names_every_criterion_and_what_closes_it(store, example, delivery):
    members, user, baseline, extra = delivery
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    codes = [c['code'] for c in gate['criteria']]
    assert codes == ['REFERENCE_CLOSURE', 'STRUCTURE', 'CONSTRUCTION_CHAIN', 'EXTERNAL_DEPENDENCIES', 'KNOWLEDGE', 'GAPS', 'VERIFICATION',
                     'PLANNING', 'RUNTIME', 'SECURITY_ZONES', 'COMPLIANCE', 'INDEPENDENT_REVIEW']
    assert gate['result'] == 'NOT_READY' and 'RUNTIME' in gate['blocking'] and 'INDEPENDENT_REVIEW' in gate['blocking']
    assert all(c['to_close'] for c in gate['criteria'] if c['status'] == 'NOT_MET') and not gate['authorization_granted']
    assert next(c for c in gate['criteria'] if c['code'] == 'INDEPENDENT_REVIEW')['owner'] == 'human'


def test_runtime_and_trust_zones_are_checked(store, example, delivery):
    members, user, baseline, extra = delivery
    production = obj(example, 'Environment', 'prod', {'stage': 'PRODUCTION', 'purpose': 'Serve members', 'hosting': 'EU region'})
    public = obj(example, 'NetworkZone', 'public', {'environment': exact(production), 'trust_level': 'PUBLIC', 'purpose': 'Internet'})
    restricted = obj(example, 'NetworkZone', 'restricted', {'environment': exact(production), 'trust_level': 'RESTRICTED', 'purpose': 'Claims data'})
    blocks = [o for o in members if o['meta']['type'] == 'air.ArchitectureBlock']
    web = obj(example, 'RuntimeComponent', 'web', {'kind': 'USER_INTERFACE', 'environment': exact(production), 'zone': exact(public),
                                                   'responsibility': 'Member portal', 'realizes': [exact(blocks[1])]})
    service = obj(example, 'RuntimeComponent', 'service', {'kind': 'SERVICE', 'environment': exact(production), 'zone': exact(restricted),
                                                           'responsibility': 'Claims', 'realizes': [exact(blocks[0])], 'replicas': 3})
    link = obj(example, 'Connection', 'web-service', {'source': exact(web), 'target': exact(service), 'protocol': 'HTTP', 'port': 80,
                                                      'encrypted': False, 'authentication': 'none', 'purpose': 'Submit claims'})
    added = [production, public, restricted, web, service, link]
    store.put_bundle(added, 'fixture')
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': frozen(store, example, members + added, 'urn:delivery:with-runtime')})
    criteria = {c['code']: c for c in gate['criteria']}
    assert criteria['RUNTIME']['status'] == 'MET'
    assert {i['issue'] for i in criteria['SECURITY_ZONES']['detail']['issues']} == {'Unencrypted crossing between trust zones', 'Public zone reaches a restricted zone directly'}


def test_raci_needs_exactly_one_accountable_and_guards_must_parse(example):
    role = obj(example, 'Role', 'lead', {'responsibilities': ['Decide'], 'required_competencies': [], 'authority': {'id': 'urn:x', 'revision': 1}})
    raci = lambda n, letter: obj(example, 'RaciAssignment', n, {'activity': 'Approve the release', 'phase': 'DELIVERY', 'role': exact(role), 'responsibility': letter})
    codes = lambda objects: {d['code'] for d in validate_graph(objects, DELIVERY_PROFILE)['diagnostics']}
    assert 'AIR_RACI_ACCOUNTABLE' in codes([role, raci('a1', 'A'), raci('a2', 'A')])
    assert 'AIR_RACI_ACCOUNTABLE' in codes([role, raci('r1', 'R')]), 'an activity with no Accountable role is reported'
    workflow = obj(example, 'Workflow', 'bad', {'steps': [{'binding': 'air.workflow-step/0.22', 'id': 'a', 'name': 'a', 'function': {'id': 'urn:f', 'revision': 1},
        'participants': [{'id': 'urn:p', 'revision': 1}]}], 'flows': [{'binding': 'air.workflow-flow/0.32', 'id': 'loop', 'source': 'a', 'target': 'a',
        'condition': 'bad', 'guard': {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean', 'ast': {'op': 'le', 'args': []}}}],
        'start_steps': ['a'], 'termination_policy': 'x', 'compensations': []})
    messages = [d['message'] for d in validate(workflow)['diagnostics']]
    assert any('body/flows/loop/guard' in m for m in messages)


def test_a_dossier_moves_to_the_delivery_profile_through_rebase(store, tmp_path, example):
    objects, user, token, request = prepare_architecture(store, tmp_path, example)
    environment = obj(example, 'Environment', 'build', {'stage': 'BUILD_TEST', 'purpose': 'Build and test', 'hosting': 'CI runners'})
    refused = agent.validate_drafts(store, user, POLICY, {'objects': [environment], 'base': request['baseline']})
    assert not refused['candidate']['reference_closure_valid'] or refused['candidate']['closure_diagnostics'], 'architecture profile refuses delivery types'
    moved = agent.rebase_drafts(store, user, POLICY, None, {'base': request['baseline'], 'objects': [environment], 'profile': DELIVERY_PROFILE, 'include_bundle': True})
    assert moved['candidate']['valid'] and moved['baseline_request']['profile'] == DELIVERY_PROFILE


def test_a_step_is_calibrated_only_when_measurements_agree_with_the_model():
    def observation(name, value, unit='Quantity[ms]'):
        return {'meta': {'id': 'urn:obs:' + name, 'revision': 1, 'type': 'air.RuntimeObservation', 'name': name},
                'body': {'metric_or_signal': 'latency p95 of step sense', 'value_or_artifact': {'type': unit, 'value': value}}}
    close, far, seconds = observation('close', '170'), observation('far', '300'), observation('seconds', '0.17', 'Quantity[s]')
    index = {(o['meta']['id'], 1): o for o in (close, far, seconds)}
    model = {'step': 'sense', 'distribution': {'kind': 'TRIANGULAR', 'min': 50, 'mode': 120, 'max': 200}}
    agree = readiness.calibration({'sense': {**model, 'calibrated_from': [{'id': 'urn:obs:close', 'revision': 1}, {'id': 'urn:obs:seconds', 'revision': 1}]}}, index)
    assert agree['sense']['calibrated'] and agree['sense']['observations'][0]['modelled_ms'] == 175.5
    disagree = readiness.calibration({'sense': {**model, 'calibrated_from': [{'id': 'urn:obs:close', 'revision': 1}, {'id': 'urn:obs:far', 'revision': 1}]}}, index)
    assert not disagree['sense']['calibrated'] and disagree['sense']['observations'][1]['status'] == 'DISAGREES'
    assert not readiness.calibration({'sense': model}, index)['sense']['calibrated'], 'a declared step without measurements is not calibrated'
