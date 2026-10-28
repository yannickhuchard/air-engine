from datetime import datetime, timedelta, timezone
import json
import pytest
from air import artifacts, context_export, generation_trace
from air.access import AccessPolicy, Forbidden
from air.core import digest
from air.foundation import exact, InvalidModel
from air.storage import Conflict
from test_build_design import design, model  # noqa: F401


@pytest.fixture
def trace_request(store, design):
    objects, user, token, settings, base = design
    document = {'version': 'trace-1', 'subjects': {user['subject']: {'read': ['*'], 'write': ['*'],
        'export_context': ['*'], 'context_destinations': [{'id': 'approved-model', 'purposes': ['design'],
            'classifications': ['PUBLIC', 'INTERNAL'],
            'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}]}}}
    (settings.home / 'access-policy.json').write_text(json.dumps(document))
    policy = AccessPolicy(document)
    root = next(o for o in objects if o['meta']['type'] == 'air.Scope')
    export = context_export.prepare(store, user, policy, {'baseline': base['baseline'], 'roots': [{**exact(root), 'digest': digest(root)}],
        'destination': 'approved-model', 'purpose': 'design', 'idempotency_key': 'context'}, settings)
    instructions = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
        'media_type': 'application/json', 'idempotency_key': 'instructions'}, b'{"task":"Review the fictional quote design"}')['artifact']
    request = {'before': base['baseline'], 'after': base['baseline'], 'provider': 'fictional-provider', 'model': 'fictional-model',
        'client_version': 'fictional-client-1', 'context_export': export['receipt'], 'instructions': instructions,
        'outputs': [], 'tools': [], 'usage': {'input_tokens': 50, 'output_tokens': 10, 'cost': '0.01', 'currency': 'EUR'},
        'idempotency_key': 'trace'}
    return request, user, policy, settings


def test_declared_trace_retains_exact_context_without_inventing_improvement(store, trace_request):
    request, user, policy, settings = trace_request
    result = generation_trace.create(store, user, policy, request, settings)
    assert result['progress']['closed_criteria'] == [] and result['progress']['regressed_criteria'] == []
    assert not result['provider_attested'] and not result['usage_independently_verified']
    assert not result['private_reasoning_requested'] and not result['design_quality_verified']
    assert result == generation_trace.create(store, user, policy, request, settings)
    assert result == generation_trace.read(store, user, policy, {'trace': result['trace']})
    with pytest.raises(Conflict): generation_trace.create(store, user, policy, {**request, 'model': 'another-model'}, settings)
    with pytest.raises(InvalidModel): generation_trace.create(store, user, policy, {**request, 'private_reasoning': 'not accepted'}, settings)
    unknown = generation_trace.create(store, user, policy, {**request, 'idempotency_key': 'unknown-usage',
        'usage': {'state': 'UNKNOWN', 'reason': 'The native client does not report per-run usage'},
        'settings': {'max_output_tokens': 2000}}, settings)
    assert unknown['request']['usage']['state'] == 'UNKNOWN'
    with pytest.raises(InvalidModel):
        generation_trace.create(store, user, policy, {**request, 'settings': {'api_key': 'forbidden-setting'}}, settings)


def test_forged_context_or_other_identity_cannot_be_attributed(store, trace_request):
    request, user, policy, settings = trace_request
    other = {**user, 'subject': 'different-client'}
    document = json.loads(json.dumps(policy.document))
    document['subjects'][other['subject']] = document['subjects'][user['subject']]
    with pytest.raises(Forbidden): generation_trace.create(store, other, AccessPolicy(document), request)
    wrong = {**request, 'context_export': {**request['context_export'], 'digest': 'sha256:' + '0' * 64}}
    with pytest.raises(InvalidModel): generation_trace.create(store, user, policy, wrong)
