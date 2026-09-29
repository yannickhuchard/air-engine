"""Tranche 32, ChatGPT pass: what an agent with a cached tool catalogue and a context budget got wrong, and why."""
import json
from air import agent, deliverables, readiness
from air.core import digest
from air.mcp import Session, TOOLS, MCP_OUTPUT_MAX
from test_delivery_032 import POLICY, delivery, frozen, obj  # noqa: F401  (fixture re-export)


def test_the_guide_carries_the_ready_to_build_verdict_and_counts_cases_like_the_gate(store, delivery):
    members, user, baseline, extra = delivery
    guide = agent.guide(store, user, POLICY, {'baseline': baseline, 'intent': 'ORIENT'})
    gate = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    assert guide['readiness']['result'] == gate['result'] == 'NOT_READY' and guide['readiness']['blocking'] == gate['blocking']
    assert 'verification_cases_not_executed' not in guide['health']['construction'], 'the count that mixed borrowed cases is gone'
    assert 'readiness.result' in guide['health']['construction']['meaning']
    assert guide['next_steps'][0]['tool'] == 'air_assess_readiness'
    deliver = agent.guide(store, user, POLICY, {'baseline': baseline, 'intent': 'DELIVER'})
    assert 'air_compile_view' not in [s['tool'] for s in deliver['next_steps']] and 'air_compile_deliverables' in [s['tool'] for s in deliver['next_steps']]


def test_construction_validation_reads_recorded_runs_and_does_not_claim_readiness(store, tmp_path, example, delivery):
    from air.config import Settings
    from air.construction import validate_construction
    from air.foundation import exact
    members, user, baseline, extra = delivery
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='artifact-test')
    user['authorization']['instance_id'] = settings.instance_id
    recorded = readiness.record_simulation(store, user, POLICY, settings, {'baseline': baseline, 'scenario': {**exact(extra[3]), 'digest': digest(extra[3])},
                                                                           'run_id': 'urn:delivery:run-chatgpt', 'idempotency_key': 'run-chatgpt'})
    run = recorded['verification_run']
    rebased = agent.rebase_drafts(store, user, POLICY, None, {'base': baseline, 'objects': [run], 'include_bundle': True})
    store.put_bundle(rebased['objects'], 'architect');after = store.create_baseline(rebased['baseline_request'], 'architect')
    objects = store.export_baseline(exact(after['baseline']))['objects']
    report = validate_construction(objects, 'air.delivery/0.32')
    case = next(c for c in report['verification_cases'] if c['case']['id'] == extra[2]['meta']['id'])
    assert case['execution'] == 'RECORDED_RUN' and case['proof_level'] == 'DECLARED_MODEL_SIMULATION'
    assert report['ready_to_build']['decided_by'] == 'air_assess_readiness'


def test_an_oversized_tool_answer_becomes_a_hint(monkeypatch):
    session = Session(lambda name, args: {'html': 'x' * (MCP_OUTPUT_MAX + 10)})
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 't'}}})
    init = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 't'}}})
    assert str(len(TOOLS)) + ' tools' in init['result']['instructions'] and 'Refresh' in init['result']['instructions']
    answer = session.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'air_capabilities', 'arguments': {}}})
    value = answer['result']['structuredContent']
    assert answer['result']['isError'] and value['error'] == 'AIR_OUTPUT_TOO_LARGE' and value['bytes'] > MCP_OUTPUT_MAX and value['hint']


def test_one_deliverable_can_be_read_alone(store, example, delivery):
    members, user, baseline, extra = delivery
    one = deliverables.compile_deliverables(store, user, POLICY, {'title': 'T', 'baselines': [baseline], 'only': ['28-preparation-construction']})
    assert [f['path'] for f in one['files']] == ['livrables/28-preparation-construction.md']
    import pytest
    from air.foundation import InvalidModel
    with pytest.raises(InvalidModel):
        deliverables.compile_deliverables(store, user, POLICY, {'title': 'T', 'baselines': [baseline], 'only': ['99-inconnu']})


def test_a_chat_assistant_profile_publishes_no_commitment_tool():
    from air.ide_adapter import COMMITTING
    from air.mcp import published_tools
    session = Session(lambda name, args: {'ok': True}, 'contribute')
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 't'}}})
    names = {t['name'] for t in session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})['result']['tools']}
    assert not names & set(COMMITTING) and 'air_assess_readiness' in names and 'air_deposit_prepared' in names
    refused = session.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'air_admission_activate', 'arguments': {}}})
    assert refused['error']['code'] == -32602 and 'humans' in refused['error']['message']
    assert set(published_tools('read')) < set(published_tools('contribute')) < set(TOOLS)


def test_the_credential_role_chooses_the_catalogue_when_no_profile_is_given():
    from air.ide_adapter import COMMITTING
    calls = []
    def invoke(name, args):
        calls.append(name);return {'role': 'editor'} if name == 'air_whoami' else {'ok': True}
    session = Session(invoke, 'auto')
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 't'}}})
    names = {t['name'] for t in session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})['result']['tools']}
    assert 'air_deposit_prepared' in names and not names & set(COMMITTING) and calls.count('air_whoami') == 2


def test_the_gate_judges_a_prepared_change_before_anything_is_deposited(store, example, delivery):
    members, user, baseline, extra = delivery
    production = obj(example, 'Environment', 'prod', {'stage': 'PRODUCTION', 'purpose': 'Serve members', 'hosting': 'EU region'})
    prepared = agent.rebase_drafts(store, user, POLICY, None, {'base': baseline, 'objects': [production]})
    before = readiness.assess_readiness(store, user, POLICY, {'baseline': baseline})
    candidate = readiness.assess_readiness(store, user, POLICY, {'prepared_change': prepared['prepared_change']['id']})
    assert candidate['baseline']['candidate'] and candidate['baseline']['would_freeze']['revision'] == baseline['revision'] + 1
    assert [c['code'] for c in candidate['criteria']] == [c['code'] for c in before['criteria']]
    assert store.get(production['meta']['id'], 1) is None, 'judging a candidate writes nothing'
