from copy import deepcopy
from decimal import localcontext

import pytest

from air.access import AccessPolicy, Forbidden
from air.core import digest
from air.currency import convert
from air.foundation import exact, InvalidModel
from test_architecture import find
from test_delivery_032 import delivery, frozen, obj, POLICY


def conversion(store, example, delivery):
    members, user, _, _ = delivery
    source = find(members, 'Source')
    costs = [obj(example, 'CostItem', 'currency-' + suffix, {
        'nature': 'CAPEX', 'category': 'SERVICE', 'amount': {'value': '0.05', 'currency': 'USD'},
        'recurrence': 'ONCE', 'start': '2026-09', 'basis': 'Synthetic oracle', 'confidence': 'LOW'})
        for suffix in ('a', 'b')]
    store.put_bundle(costs, 'fixture')
    base = frozen(store, example, members + costs, 'urn:currency:baseline')
    req = {'baseline': base, 'as_of': '2026-09-28T00:00:00Z', 'target_currency': 'EUR', 'fraction_digits': 2,
        'items': [{**exact(c), 'digest': digest(c)} for c in costs],
        'rates': [{'id': 'urn:synthetic:usd-eur', 'revision': 1,
                   'source': {**exact(source), 'digest': digest(source)},
                   'from_currency': 'USD', 'to_currency': 'EUR', 'value': '0.9',
                   'observed_at': '2026-09-27T00:00:00Z',
                   'validity': {'start': '2026-09-27T00:00:00Z', 'end': '2026-09-29T00:00:00Z'},
                   'basis': 'Fictitious rate for arithmetic testing'}]}
    return user, req


def test_explicit_rates_and_round_once_not_sum_rounded_items(store, example, delivery):
    user, req = conversion(store, example, delivery)
    report = convert(store, user, POLICY, req)
    assert [x['rounded_value'] for x in report['items']] == ['0.04', '0.04']
    assert report['totals'][0]['rounded_value'] == '0.09'
    assert report['items'][0]['rate']['source'] == req['rates'][0]['source']
    assert report['items'][0]['rate_digest']
    assert not report['external_effects'] and not report['rate_authenticity_verified']
    with localcontext() as context:
        context.prec = 2
        assert convert(store, user, POLICY, req) == report


@pytest.mark.parametrize('fault', ['missing', 'stale', 'future', 'zero', 'negative', 'duplicate', 'wrong_digest', 'wrong_direction', 'same_item'])
def test_unsafe_conversion_is_rejected(store, example, delivery, fault):
    user, req = conversion(store, example, delivery)
    if fault == 'missing': req['rates'] = []
    elif fault == 'stale': req['as_of'] = req['rates'][0]['validity']['end']
    elif fault == 'future': req['rates'][0]['observed_at'] = '2026-10-01T00:00:00Z'
    elif fault == 'zero': req['rates'][0]['value'] = '0'
    elif fault == 'negative': req['rates'][0]['value'] = '-1'
    elif fault == 'duplicate': req['rates'].append(deepcopy(req['rates'][0]))
    elif fault == 'wrong_digest': req['rates'][0]['source']['digest'] = 'sha256:' + '0' * 64
    elif fault == 'wrong_direction': req['rates'][0]['to_currency'] = 'GBP'
    else: req['items'].append(deepcopy(req['items'][0]))
    with pytest.raises(InvalidModel): convert(store, user, POLICY, req)


def test_conversion_requires_readable_closed_inputs(store, example, delivery):
    user, req = conversion(store, example, delivery)
    with pytest.raises(Forbidden):
        convert(store, user, AccessPolicy({'version': 'removed', 'subjects': {}}), req)


def test_http_and_mcp_use_same_conversion(store, example, delivery, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.config import Settings
    from air.mcp import PROTOCOL
    user, req = conversion(store, example, delivery)
    headers = {'Authorization': 'Bearer ' + store.create_token('reader', 'reader')['access_token']}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False),
                    base_url='http://127.0.0.1:8740') as client:
        http = client.post('/v1/currency/convert', json=req, headers=headers)
        assert http.status_code == 200
        rpc = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'air_convert_currency', 'arguments': req}}, headers={**headers,
            'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()
        assert rpc['result']['structuredContent'] == http.json()
