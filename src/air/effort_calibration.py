"""Compare retained effort observations to exact estimates; no causal AI-gain claim."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from collections import defaultdict
from air import artifacts
from air.access import ScopedStore
from air.core import record, TEXT, INSTANT
from air.delivery_schema import ACTIVITIES, DECIMAL
from air.expr import artifact_digest
from air.foundation import check_schema, InvalidModel, key
from air.packages import RECORD_REF
from air.parsing import parse
from air.projections import SNAPSHOT, snapshot

OBSERVATIONS = record({'format': {'const': 'air.effort-observations/1'},
    'observations': {'type': 'array', 'minItems': 1, 'maxItems': 256, 'items': record({
        'id': {**TEXT, 'maxLength': 128}, 'unit': SNAPSHOT, 'estimate': SNAPSHOT,
        'activity': {'enum': ACTIVITIES}, 'person_days': DECIMAL, 'review_person_days': DECIMAL,
        'rework_person_days': DECIMAL, 'ai_used': {'type': 'boolean'},
        'started_at': INSTANT, 'finished_at': INSTANT, 'source_record': {**TEXT, 'maxLength': 512}})}})
REQUEST = record({'baseline': SNAPSHOT, 'observations': RECORD_REF, 'as_of': INSTANT})


def project(exported, observations, as_of):
    check_schema(observations, OBSERVATIONS)
    by = {key(o['meta']): o for o in exported['objects']}; grouped = defaultdict(list); ids = set()
    for row in observations['observations']:
        if row['id'] in ids: raise InvalidModel('Duplicate effort observation')
        ids.add(row['id'])
        for field, kind in [('unit', 'air.ConstructionUnit'), ('estimate', 'air.DeliveryEstimate')]:
            from air.core import digest
            obj = by.get(key(row[field]))
            if not obj or obj['meta']['type'] != kind or digest(obj) != row[field]['digest']:
                raise InvalidModel('Effort observations must pin baseline units and estimates')
        estimate = by[key(row['estimate'])]
        if key(estimate['body']['unit']) != key(row['unit']): raise InvalidModel('Estimate targets another construction unit')
        if not datetime.fromisoformat(row['started_at']) <= datetime.fromisoformat(row['finished_at']) <= datetime.fromisoformat(as_of):
            raise InvalidModel('Effort observation lies outside its declared assessment window')
        if Decimal(row['review_person_days']) + Decimal(row['rework_person_days']) > Decimal(row['person_days']):
            raise InvalidModel('Review and rework are included in total person-days')
        if row['activity'] not in {a['activity'] for a in estimate['body']['activities']}:
            raise InvalidModel('Observed activity is outside the pinned estimate')
        grouped[key(row['estimate'])].append(row)
    results = []
    fmt = lambda n: format(n, 'f')
    for estimate_key, rows in sorted(grouped.items()):
        estimate = by[estimate_key]; activities = estimate['body']['activities']
        actual = sum((Decimal(r['person_days']) for r in rows), Decimal(0))
        planned = sum((Decimal(a['effort_pd']) for a in activities), Decimal(0))
        ai_planned = sum((Decimal(a.get('ai_effort_pd', a['effort_pd'])) for a in activities), Decimal(0))
        observed = {r['activity'] for r in rows}; missing = sorted({a['activity'] for a in activities} - observed)
        mixed = len({r['ai_used'] for r in rows}) > 1
        selected_plan = None if mixed else ai_planned if rows[0]['ai_used'] else planned
        with localcontext() as precision:
            precision.prec = 48
            ratio = fmt(actual / selected_plan) if selected_plan and not missing else None
        results.append({'estimate': rows[0]['estimate'], 'unit': rows[0]['unit'], 'observations': len(rows),
            'actual_person_days': fmt(actual), 'planned_person_days': fmt(planned), 'planned_ai_person_days': fmt(ai_planned),
            'review_person_days': fmt(sum((Decimal(r['review_person_days']) for r in rows), Decimal(0))),
            'rework_person_days': fmt(sum((Decimal(r['rework_person_days']) for r in rows), Decimal(0))),
            'missing_activities': missing, 'mixed_ai_usage': mixed,
            'forecast_ratio': ratio,
            'comparison_state': 'PARTIAL' if missing else 'MIXED_USAGE' if mixed else 'ZERO_FORECAST' if not selected_plan else 'COMPARABLE_RECORDED_EFFORT'})
    return {'engine': 'air.effort-calibration/1', 'results': results, 'units': len({key(r['unit']) for r in results}),
        'basis': 'RETAINED_RECORDED_OBSERVATIONS', 'source_authenticity_verified': False,
        'ai_productivity_gain_causally_established': False,
        'limitations': ['Recorded effort and completeness of source records need independent validation',
                       'Forecast agreement does not establish AI causality, quality or financial benefit']}


def assess(store, principal, policy, request):
    check_schema(request, REQUEST)
    if datetime.fromisoformat(request['as_of']) > datetime.now(timezone.utc):
        raise InvalidModel('Recorded effort cannot be assessed in the future')
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    metadata, raw = artifacts.download(store, principal, policy, {'artifact': request['observations']})
    if metadata['media_type'] != 'application/json' or len(raw) > 524288:
        raise InvalidModel('Effort observations must be JSON up to 512 KiB')
    result = {**project(exported, parse(raw), request['as_of']), 'baseline': request['baseline'],
        'observations_digest': metadata['content_digest'], 'as_of': request['as_of'], 'registry_written': False}
    return {**result, 'report_digest': artifact_digest(result)}
