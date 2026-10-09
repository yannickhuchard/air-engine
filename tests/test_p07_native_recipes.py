"""A failed native qualification must not leave a temporary business mandate behind."""
import importlib
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def recipe(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('p07_native_stale_catalog')


@pytest.mark.parametrize('failure', ['native_exception', 'no_calls'])
def test_stale_recipe_restores_original_policy_on_incomplete_native_run(tmp_path, monkeypatch, recipe, failure):
    root = tmp_path/'bench'; home = root/'.air-p07'; home.mkdir(parents=True)
    workspace = root/'workspace-codex'; (workspace/'.codex').mkdir(parents=True)
    (workspace/'.codex/config.toml').write_text('[mcp_servers.air]\ncommand="fixture"\nargs=[]\n', encoding='utf-8')
    original = {'version': 'fixture', 'subjects': {'codex': {'read': ['example.claims'], 'write': ['example.claims']}}}
    (home/'access-policy.json').write_text(json.dumps(original), encoding='utf-8')
    settings = SimpleNamespace(database_url='sqlite://')
    bench = {'clients': {'codex': {'subject': 'codex', 'workspace': str(workspace)}}}
    disposed = []
    store = SimpleNamespace(engine=SimpleNamespace(dispose=lambda: disposed.append(True)))
    applied = []
    monkeypatch.setattr(recipe, 'state', lambda r: bench)
    monkeypatch.setattr(recipe, 'bench_home', lambda r, b: (home, settings))
    monkeypatch.setattr(recipe, 'Store', lambda _: store)
    monkeypatch.setattr(recipe, 'inspect', lambda s, b: {'counts': {'reservations': 0, 'activations': 0}})
    monkeypatch.setattr(recipe, 'policy', lambda r, value, label: applied.append((value, label)))
    def invoke(*args):
        if failure == 'native_exception':
            raise RuntimeError('native startup failed')
        return {'status': 'INCOMPLETE', 'calls': []}
    monkeypatch.setattr(recipe, 'invoke', invoke)
    if failure == 'native_exception':
        with pytest.raises(RuntimeError, match='startup failed'):
            recipe.run(root, root/'evidence')
    else:
        result = recipe.run(root, root/'evidence')
        assert result['status'] == 'INCOMPLETE'
        assert not result['checks']['native_admission_refused']
        assert not result['checks']['native_activation_refused']
    assert applied[0][0]['subjects']['codex']['admit'] == ['example.claims']
    assert applied[-1] == (original, 'codex-original-restored')
    assert 'admit' not in original['subjects']['codex']
    assert disposed == [True]


def test_unfinished_native_json_line_is_not_a_completed_call(tmp_path, recipe):
    stream = tmp_path/'native.jsonl'
    stream.write_text('{"type":"item.completed","item":{"type":"agent_message","text":"PASS"}}\n{"type":', encoding='utf-8')
    rows = recipe.rows_in(tmp_path)
    assert len(rows) == 1
    assert recipe.calls('codex', rows) == []


def test_followup_rejects_tampered_transcript_and_does_not_accept_prose(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    evidence = importlib.import_module('p07_followup_evidence')
    raw = b'{"type":"item.completed","item":{"type":"agent_message","text":"All tests PASS"}}\n'
    (tmp_path/'native.jsonl').write_bytes(raw)
    (tmp_path/'report.json').write_text(json.dumps({'transcript_sha256': hashlib.sha256(raw).hexdigest()}), encoding='utf-8')
    assert evidence.read_native(tmp_path, 'codex')[1] == []
    (tmp_path/'native.jsonl').write_bytes(raw+b'{}\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        evidence.read_native(tmp_path, 'codex')


def test_native_job_receipt_requires_actual_completion_and_idempotence(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    evidence = importlib.import_module('p07_claude_job_evidence')
    request = {'operation': 'plan', 'idempotency_key': 'original', 'arguments': {}}
    assert not any(evidence.job_checks([], request, 'following').values())
    old, new = {'id': 'old', 'digest': 'old-digest'}, {'id': 'new', 'digest': 'new-digest'}
    def call(tool, args, result): return {'tool': tool, 'arguments': args, 'result': result}
    observed = [call('air_submit_job', request, {'job': old, 'created': True}),
                call('air_cancel_job', {'job': old}, {'job': old, 'changed': True, 'status': 'CANCELLED'}),
                call('air_cancel_job', {'job': old}, {'job': old, 'changed': False, 'status': 'CANCELLED'}),
                call('air_submit_job', request, {'job': old, 'created': False}),
                call('air_submit_job', {**request, 'idempotency_key': 'following'}, {'job': new, 'created': True}),
                call('air_get_job', {'job': old}, {'status': 'CANCELLED', 'attempt': 0}),
                call('air_get_job', {'job': new}, {'status': 'QUEUED', 'result': None})]
    assert not evidence.job_checks(observed, request, 'following')['new_job_completed_without_commitment']
    observed[-1]['result'] = {'status': 'SUCCEEDED', 'result': {'outcome': {'reservations_created': False}}}
    assert all(evidence.job_checks(observed, request, 'following').values())
    observed[2]['result']['changed'] = True
    assert not evidence.job_checks(observed, request, 'following')['cancel_idempotent']
