"""Fictional independent provider prototype, JSON lines, no AIR dependency.

Not a production service. No transport security, persistence, time window or
concurrent access. The demo does not infer those properties from this cache.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

cache = {}


def quote(envelope):
    body = envelope.get('body', {})
    quantity = body.get('quantity')
    token = envelope.get('headers', {}).get('Idempotency-Key')
    if not isinstance(token, str) or not token or isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 100 or set(body) != {'quantity'}:
        return {'status': 422, 'body': {'error': 'INVALID_REQUEST'}}
    if token in cache:
        previous, response = cache[token]
        return response if previous == body else {'status': 409, 'body': {'error': 'KEY_REUSED'}}
    response = {'status': 200, 'body': {'quantity': quantity, 'total_minor': quantity * 125, 'currency': 'EUR'}}
    cache[token] = (body.copy(), response)
    return response


if __name__ == '__main__':
    if '--http' in sys.argv:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                if self.path != '/quotes' or not 1 <= length <= 4096:
                    self.send_error(400); return
                response = quote({'body': json.loads(self.rfile.read(length)), 'headers': {'Idempotency-Key': self.headers.get('Idempotency-Key')}})
                raw = json.dumps(response['body']).encode()
                self.send_response(response['status']); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        server = HTTPServer(('127.0.0.1', 0), Handler)
        print(json.dumps({'port': server.server_port}), flush=True)
        server.serve_forever()
    else:
        for line in sys.stdin:
            print(json.dumps(quote(json.loads(line))), flush=True)
