"""Fictional independent consumer prototype. No provider or AIR import."""
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(quantity, key):
    return {'method': 'POST', 'path': '/quotes', 'headers': {'Idempotency-Key': key}, 'body': {'quantity': quantity}}


def interpret(response, quantity):
    if response['status'] != 200: return {'accepted': False, 'reason': response['body']['error']}
    result = response['body']
    if result['quantity'] != quantity or result['currency'] != 'EUR' or result['total_minor'] != quantity * 125:
        raise ValueError('Provider violated the declared quote')
    return {'accepted': True, 'total_minor': result['total_minor']}


if __name__ == '__main__':
    url = sys.argv[sys.argv.index('--http-url') + 1] if '--http-url' in sys.argv else None
    for line in sys.stdin:
        value = json.loads(line)
        envelope = request(value['quantity'], value['key'])
        if url:
            req = Request(url + envelope['path'], data=json.dumps(envelope['body']).encode(), method=envelope['method'],
                headers={**envelope['headers'], 'Content-Type': 'application/json'})
            try:
                with urlopen(req, timeout=5) as result: response = {'status': result.status, 'body': json.load(result)}
            except HTTPError as exc: response = {'status': exc.code, 'body': json.load(exc)}
            output = {'request': envelope, 'response': response, 'interpretation': interpret(response, value['quantity'])}
        else: output = envelope
        print(json.dumps(output), flush=True)
