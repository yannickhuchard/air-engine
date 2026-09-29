"""Never reflect the active transport credential in diagnostic or MCP payloads."""
import json


def redact(value, authorization):
    if not isinstance(authorization, str): return value
    token = authorization[7:] if authorization.lower().startswith('bearer ') else authorization
    if len(token) < 8: return value
    encoded = json.dumps(value, ensure_ascii=False)
    return json.loads(encoded.replace(token, '[REDACTED]')) if token in encoded else value
