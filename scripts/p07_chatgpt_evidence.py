"""Read isolated tunnel receipts; a protocol log alone never proves native authorship."""
import argparse
import hashlib
import json
from pathlib import Path


def completed_calls(path):
    """Pair each response with its request, including IDs reused after initialize."""
    pending, calls = {}, []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        row = json.loads(line)
        message = row['message']
        identifier = message.get('id')
        if row['direction'] == 'in' and identifier is not None:
            if identifier in pending:
                raise ValueError('Ambiguous outstanding request ID')
            pending[identifier] = (row, number)
        elif row['direction'] == 'out' and identifier is not None:
            request = pending.pop(identifier, None)
            if request is None:
                raise ValueError('Unmatched protocol response')
            incoming, start_line = request
            if incoming['message'].get('method') != 'tools/call':
                continue
            parameters = incoming['message']['params']
            result = message.get('result', {}).get('structuredContent')
            calls.append({'at': incoming['at'], 'completed_at': row['at'],
                'lines': [start_line, number], 'tool': parameters['name'],
                'arguments': parameters.get('arguments', {}), 'result': result,
                'rpc_error': message.get('error')})
    if pending:
        raise ValueError('Incomplete protocol requests')
    return calls


def native_window(calls, turn):
    """Bind actual payloads to a completed native app turn; prose is never a result."""
    if turn.get('status') != 'completed' or turn.get('error'):
        raise ValueError('Native turn did not complete')
    start, end = turn['startedAt'], turn['completedAt']
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
        raise ValueError('Invalid native time window')
    return [c for c in calls if start <= c['at'] <= c['completed_at'] <= end]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('transcript', type=Path)
    args = parser.parse_args()
    data = args.transcript.read_bytes()
    calls = completed_calls(args.transcript)
    # No client metadata, locations, subjects, credential material or object bodies.
    print(json.dumps({'transcript_sha256': hashlib.sha256(data).hexdigest(),
        'calls': [{'at': c['at'], 'tool': c['tool'], 'rpc_error': bool(c['rpc_error']),
                   'error': (c['result'] or {}).get('error'),
                   'http_status': (c['result'] or {}).get('http_status')}
                  for c in calls]}, indent=2))
