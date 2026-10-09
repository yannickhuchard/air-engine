"""Explicit, sourced conversion of pinned design costs; never an implicit FX rate."""
from datetime import datetime
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext

from air.access import ScopedStore
from air.core import INSTANT, TEXT, URI, record, digest
from air.expr import artifact_digest
from air.foundation import check_budget, InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.currency-conversion/1'
CURRENCY = {'type': 'string', 'pattern': '^[A-Z]{3}$'}
RATE = record({'id': URI, 'revision': {'type': 'integer', 'minimum': 1}, 'source': SNAPSHOT,
    'from_currency': CURRENCY, 'to_currency': CURRENCY,
    'value': {'type': 'string', 'pattern': '^(0|[1-9][0-9]{0,17})(\\.[0-9]{1,18})?$'},
    'observed_at': INSTANT, 'validity': record({'start': INSTANT, 'end': INSTANT}), 'basis': TEXT})
REQUEST = record({'baseline': SNAPSHOT, 'as_of': INSTANT, 'target_currency': CURRENCY,
    'fraction_digits': {'type': 'integer', 'minimum': 0, 'maximum': 6},
    'items': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
    'rates': {'type': 'array', 'items': RATE, 'maxItems': 256}})


def convert(store, principal, policy, request):
    check_schema(request, REQUEST)
    check_budget(request)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    index = {key(exact(obj)): obj for obj in exported['objects']}
    def resolve(pin, kind):
        obj = index.get(key(pin))
        if obj is None or obj['meta']['type'] != kind or digest(obj) != pin['digest']:
            raise InvalidModel('Conversion inputs must be exact members of the readable baseline')
        return obj
    as_of = datetime.fromisoformat(request['as_of'])
    target = request['target_currency']
    rates, identities = {}, set()
    for rate in request['rates']:
        identity = (rate['id'], rate['revision'])
        source = resolve(rate['source'], 'air.Source')
        start, end = (datetime.fromisoformat(rate['validity'][k]) for k in ('start', 'end'))
        if not start <= as_of < end or datetime.fromisoformat(rate['observed_at']) > as_of:
            raise InvalidModel('Exchange rate is not valid and observed at the conversion instant')
        if datetime.fromisoformat(source['body']['captured_at']) > as_of:
            raise InvalidModel('Exchange rate source was captured after the conversion instant')
        currency = rate['from_currency']
        if identity in identities or currency in rates or currency == target or rate['to_currency'] != target:
            raise InvalidModel('Duplicate, identity or indirect exchange rate')
        if Decimal(rate['value']) <= 0:
            raise InvalidModel('Exchange rates must be positive')
        identities.add(identity)
        rates[currency] = rate
    rows, groups, used, seen = [], {}, set(), set()
    try:
        # Do not inherit a caller's Decimal precision or rounding policy.
        with localcontext(Context(prec=80, rounding=ROUND_HALF_EVEN)):
            quantum = Decimal(1).scaleb(-request['fraction_digits'])
            for pin in sorted(request['items'], key=key):
                if key(pin) in seen: raise InvalidModel('A cost item must not be counted twice')
                seen.add(key(pin))
                item = resolve(pin, 'air.CostItem')
                body = item['body']; original = body['amount']
                source_currency = original['currency']
                rate = rates.get(source_currency)
                if source_currency != target and rate is None:
                    raise InvalidModel('No explicit direct rate for ' + source_currency + ' -> ' + target)
                if rate: used.add(source_currency)
                factor = Decimal(rate['value']) if rate else Decimal(1)
                raw = Decimal(original['value']) * factor
                rounded = raw.quantize(quantum)
                bucket = (body['nature'], body['recurrence'], body['start'], body.get('end'))
                groups[bucket] = groups.get(bucket, Decimal(0)) + raw
                rows.append({'item': pin, 'original': original, 'exact_value': format(raw, 'f'),
                    'rounded_value': format(rounded, 'f'), 'currency': target,
                    'rate_digest': artifact_digest(rate) if rate else None,
                    'rate': rate, 'rounding_delta': format(rounded - raw, 'f')})
            if set(rates) != used: raise InvalidModel('Unused exchange rates are not part of this conversion')
            totals = [{'nature': group[0], 'recurrence': group[1], 'start': group[2], 'end': group[3],
                       'exact_value': format(amount, 'f'), 'rounded_value': format(amount.quantize(quantum), 'f'),
                       'currency': target} for group, amount in sorted(groups.items(), key=lambda x: str(x[0]))]
    except DecimalException as exc:
        raise InvalidModel('Conversion exceeds the decimal arithmetic bounds') from exc
    result = {'engine': ENGINE, 'baseline': request['baseline'], 'as_of': request['as_of'],
        'basis': 'DECLARED_SOURCED_EXCHANGE_RATES', 'rate_authenticity_verified': False,
        'rounding': {'mode': 'HALF_EVEN', 'fraction_digits': request['fraction_digits'],
                     'totals': 'ROUND_ONCE_PER_EQUAL_NATURE_RECURRENCE_AND_PERIOD'},
        'items': rows, 'totals': totals, 'request_digest': artifact_digest(request),
        'model_updated': False, 'external_effects': False}
    check_budget(result)
    result['report_digest'] = artifact_digest(result)
    return result
