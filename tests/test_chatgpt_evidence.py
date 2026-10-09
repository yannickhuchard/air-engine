import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('p07_chatgpt_evidence')


def row(direction, at, message):
    return {'direction': direction, 'at': at, 'message': message}


def test_reused_ids_and_rpc_failures_do_not_become_success(tmp_path, evidence):
    rows = [row('in', 1, {'id': 1, 'method': 'tools/call', 'params': {'name': 'air_get'}}),
            row('out', 2, {'id': 1, 'error': {'code': -32000}}),
            row('in', 3, {'id': 1, 'method': 'initialize'}),
            row('out', 4, {'id': 1, 'result': {}}),
            row('in', 5, {'id': 1, 'method': 'tools/call', 'params': {'name': 'air_get'}}),
            row('out', 6, {'id': 1, 'result': {'structuredContent': {'http_status': 403}}})]
    path = tmp_path / 'trace.jsonl'
    path.write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
    calls = evidence.completed_calls(path)
    assert len(calls) == 2
    assert calls[0]['result'] is None and calls[0]['rpc_error']
    assert calls[1]['result'] == {'http_status': 403}
    assert evidence.native_window(calls, {'status': 'completed', 'startedAt': 4, 'completedAt': 7}) == calls[1:]


@pytest.mark.parametrize('fault', ['overlap', 'unfinished', 'orphan'])
def test_ambiguous_or_incomplete_protocol_is_rejected(tmp_path, evidence, fault):
    request = row('in', 1, {'id': 1, 'method': 'tools/call', 'params': {'name': 'air_get'}})
    rows = {'overlap': [request, request], 'unfinished': [request],
            'orphan': [row('out', 2, {'id': 1, 'result': {}})]}[fault]
    path = tmp_path / 'trace.jsonl'
    path.write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
    with pytest.raises(ValueError):
        evidence.completed_calls(path)


def test_unfinished_native_turn_cannot_attribute_protocol(evidence):
    with pytest.raises(ValueError):
        evidence.native_window([], {'status': 'completed', 'startedAt': 1, 'completedAt': 1})
