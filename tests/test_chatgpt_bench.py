import importlib
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('p07_chatgpt_bench')


def test_recorder_redacts_live_rotated_credential_and_stays_bounded(tmp_path, module):
    credential = tmp_path/'identity.json'
    credential.write_text(json.dumps({'access_token': 'first-private-fixture-token'}))
    output = io.BytesIO()
    recorder = module.Recorder(output, credential)
    recorder.record('in', {'text': 'first-private-fixture-token'})
    credential.write_text(json.dumps({'access_token': 'rotated-private-fixture-token'}))
    recorder.record('out', {'text': 'rotated-private-fixture-token'})
    assert b'private-fixture-token' not in output.getvalue()
    assert output.getvalue().count(b'[REDACTED]') == 2
    recorder.size = 64*1024*1024
    with pytest.raises(ValueError, match='budget'):
        recorder.record('out', {})


def test_refuse_recording_ordinary_bench_or_business_database(tmp_path, module, monkeypatch):
    monkeypatch.setattr(module, 'state', lambda root: {'client': 'codex'})
    monkeypatch.setattr(module, 'bench_home', lambda *args: (tmp_path, None))
    with pytest.raises(ValueError, match='dedicated ChatGPT'):
        module.checked(tmp_path)


def test_recording_stream_preserves_protocol_and_rejects_raw_invalid_input(tmp_path, module):
    credential = tmp_path/'identity.json'
    credential.write_text(json.dumps({'access_token': 'never-printed-fixture'}))
    trace = io.BytesIO()
    recorder = module.Recorder(trace, credential)
    incoming = b'{"jsonrpc":"2.0","method":"ping","id":1}\ninvalid-sensitive-data\n'
    reader = module.RecordedInput(io.BytesIO(incoming), recorder)
    assert reader.readline(1024).startswith(b'{')
    assert reader.readline(1024) == b'invalid-sensitive-data\n'
    sink = io.StringIO()
    writer = module.RecordedOutput(sink, recorder)
    reply = '{"jsonrpc":"2.0","id":1,"result":{}}\n'
    writer.write(reply); writer.flush()
    assert sink.getvalue() == reply
    rows = [json.loads(line) for line in trace.getvalue().splitlines()]
    assert rows[-1]['message']['result'] == {}
    assert b'invalid-sensitive-data' not in trace.getvalue()


def test_native_outage_requires_an_actual_completed_air_error(module):
    recovery = importlib.import_module('p07_codex_recovery')
    item = {'type': 'mcpToolCall', 'server': 'air', 'tool': 'air_get', 'arguments': {},
            'status': 'failed', 'error': None, 'result': {'structuredContent': {'error': 'AIR_UNREACHABLE'}}}
    event = {'method': 'item/completed', 'params': {'item': item}}
    assert recovery.observed_calls([event])[0]['result']['error'] == 'AIR_UNREACHABLE'
    for change in ({'error': 'transport interrupted'}, {'server': 'other'}, {'type': 'agentMessage'}):
        assert recovery.observed_calls([{'method': 'item/completed', 'params': {'item': {**item, **change}}}]) == []
    assert recovery.observed_calls([{'method': 'item/started', 'params': {'item': item}}]) == []


@pytest.mark.parametrize('fault', ['missing_call', 'changed_thread', 'wrong_arguments'])
def test_recovery_recheck_rejects_false_receipt(tmp_path, module, monkeypatch, fault):
    recovery = importlib.import_module('p07_codex_recovery')
    ref = {'id': 'urn:test:scope', 'revision': 1}
    monkeypatch.setattr(recovery, 'state', lambda root: {'fixtures': {'scope': {**ref, 'digest': 'exact'}},
                                                       'clients': {'codex': {'subject': 'codex-fixture'}}})
    monkeypatch.setattr(recovery, 'bench_home', lambda *args: None)
    rows = []
    for phase in ('connected', 'restricted', 'expired', 'rotated', 'offline', 'recovered'):
        rows.append({'method': 'turn/started', 'params': {'threadId': 'one' if fault != 'changed_thread' else phase}})
        for tool, arguments in [('air_whoami', {}), ('air_get', ref)]:
            if phase == 'expired': payload = {'error': 'AIR_UNAUTHENTICATED', 'http_status': 401}
            elif phase == 'offline': payload = {'error': 'AIR_UNREACHABLE'}
            elif tool == 'air_get' and phase == 'restricted': payload = {'error': 'AIR_FORBIDDEN', 'http_status': 403}
            else: payload = {'subject': 'codex-fixture', 'digest': 'exact'}
            event = {'method': 'item/completed', 'params': {'item': {'type': 'mcpToolCall', 'server': 'air',
                'tool': tool, 'arguments': arguments, 'status': 'failed' if 'error' in payload else 'completed',
                'error': None, 'result': {'structuredContent': payload}}}}
            if fault == 'wrong_arguments' and tool == 'air_get': event['params']['item']['arguments'] = {'id': 'another', 'revision': 1}
            if fault != 'missing_call' or phase != 'offline': rows.append(event)
        rows.append({'method': 'turn/completed', 'params': {}})
    (tmp_path/'native.jsonl').write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
    assert recovery.evaluate(tmp_path, tmp_path)['status'] == 'INCOMPLETE'
