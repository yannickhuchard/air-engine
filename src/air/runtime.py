"""Authenticated observation ingestion and pure comparisons under declared mappings."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from air.access import ScopedStore
from air.core import record, schema, canonical, digest, reference_slots, TEXT, INSTANT, validate
from air.expr import bounded, Program, ExprError, artifact_digest, evaluate, typed
from air.foundation import InvalidModel, check_schema, exact, key
from air.packages import reference, lock_registry
from air.projections import SNAPSHOT
from air.reviews import record_key
from air.storage import Conflict

ENGINE = 'air.runtime-comparison/0.12'
KEY = {'type': 'string', 'minLength': 1, 'maxLength': 128}
INGEST = record({'idempotency_key': KEY, 'source': SNAPSHOT,
    'observations': {'type': 'array', 'items': schema('air.RuntimeObservation'), 'minItems': 1, 'maxItems': 128}})
COMPARE = record({'scope': SNAPSHOT, 'expected': SNAPSHOT, 'as_of': INSTANT,
    'window': record({'start': INSTANT, 'end': INSTANT}), 'max_age_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 31622400},
    'bindings': {'type': 'array', 'minItems': 1, 'maxItems': 128, 'items': record({
        'input': {'type': 'string', 'pattern': '^[a-zA-Z][a-zA-Z0-9_.-]{0,127}$'}, 'observation': SNAPSHOT})},
    'method': record({'basis': {'const': 'DECLARED_MAPPING'}, 'rationale': TEXT, 'expression': {'type': 'object'}})})


def ingest(store, principal, policy, settings, request):
    check_schema(request, INGEST)
    try: bounded(request)
    except ExprError as exc: raise InvalidModel(str(exc)) from exc
    request = deepcopy(request)
    report = validate(request['observations'])
    if not report['valid']: raise InvalidModel('Invalid runtime observations', report)
    request['observations'] = sorted([json.loads(canonical(o)) for o in request['observations']], key=lambda o: key(exact(o)))
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([request['source']])
    refs = [ref for obj in request['observations'] for _, ref, _ in reference_slots(obj)]
    guarded.check_read(refs)
    for obj in request['observations']:
        policy.require(principal, 'write', obj['meta']['namespace'])
        if key(request['source']) not in {key(r) for r in obj['meta']['provenance']['source_refs']}:
            raise InvalidModel('Each observation must reference the exact ingestion source')
    record_id = record_key('runtime-ingestion', principal['subject'], request['idempotency_key'])
    from air.jobs import check_identity
    with store.write() as conn:
        lock_registry(conn);check_identity(store, conn, principal, settings)
        source = store._required(conn, request['source'], 'air.Source')
        prior = store._get_record(conn, record_id)
        if prior:
            if prior['payload']['request'] != request: raise Conflict('Observation ingestion idempotency key was reused')
            return {'ingestion': reference(prior), 'created': False, 'observations': prior['payload']['observations'], 'qualification': 'DRAFT'}
        current = datetime.now(timezone.utc)
        if datetime.fromisoformat(source['body']['captured_at']) > current: raise InvalidModel('Ingestion source capture is in the future')
        stored = []
        for obj in request['observations']:
            if datetime.fromisoformat(obj['body']['window']['end']) > current: raise InvalidModel('An ingested observation window cannot extend into the future')
            for _, ref, kinds in reference_slots(obj):
                target = store._required(conn, ref)
                if target['meta']['type'] not in kinds: raise InvalidModel('Observation reference has an incompatible target type')
            stored.append(store._put(conn, obj, principal['subject']))
        pins = [{k: row[k] for k in ('id', 'revision', 'digest')} for row in stored]
        receipt = store._record_once(conn, record_id, 'runtime_ingestion', request['observations'][0]['meta']['namespace'], principal['subject'],
            {'request': request, 'observations': pins, 'policy_digest': policy.digest, 'qualification': 'DRAFT', 'remote_collection_performed': False})
    return {'ingestion': reference(receipt['record']), 'created': receipt['created'], 'observations': pins, 'qualification': 'DRAFT'}


def compare(store, principal, policy, request):
    return _compare(store, principal, policy, request, {})


def compare_with_constants(store, principal, policy, request, constants):
    """Internal binding for exact stored target values; not exposed in the HTTP request schema."""
    return _compare(store, principal, policy, request, constants)


def _compare(store, principal, policy, request, constants):
    check_schema(request, COMPARE)
    try:
        bounded(request);program = Program(request['method']['expression'])
        if not isinstance(constants, dict) or not all(isinstance(name, str) for name in constants): raise InvalidModel('Invalid constant input context')
        if constants: bounded({'request': request, 'constant_inputs': constants})
        for value in constants.values(): typed(value)
    except ExprError as exc: raise InvalidModel('Comparison expression is invalid', {'code': exc.code, 'message': str(exc)}) from exc
    if program.expression['result_type'] != 'Boolean': raise InvalidModel('Runtime comparisons must evaluate a Boolean predicate')
    request = deepcopy(request);request['bindings'].sort(key=lambda b: b['input'])
    names = [b['input'] for b in request['bindings']]
    if len(set(names)) != len(names) or set(names) & set(constants) or set(names) | set(constants) != set(program.inputs): raise InvalidModel('Each declared input requires exactly one observation or stored constant binding')
    pending, used = [program.expression['ast']], set()
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if 'ref' in node and node['ref'] != '$item': used.add(node['ref'])
            pending.extend(node.values())
        elif isinstance(node, list): pending.extend(node)
    if used != set(names) | set(constants): raise InvalidModel('Comparison must actually reference every bound observation and stored constant')
    start, end = (datetime.fromisoformat(request['window'][f]) for f in ('start', 'end'))
    as_of = datetime.fromisoformat(request['as_of'])
    if not start < end <= as_of: raise InvalidModel('Comparison window must end at or before its declared observation date')
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([request['scope'], request['expected']] + [b['observation'] for b in request['bindings']])
    inputs, observations, diagnostics = deepcopy(constants), [], []
    input_bytes = 0
    with store.engine.connect() as conn:
        scope = store._required(conn, request['scope'], 'air.Scope')
        expected = store._required(conn, request['expected'])
        for binding in request['bindings']:
            obj = store._required(conn, binding['observation'], 'air.RuntimeObservation');body = obj['body']
            input_bytes += len(canonical(obj))
            if input_bytes > 1024 * 1024: raise InvalidModel('Runtime comparison context exceeds 1 MiB')
            reasons = []
            if body['instance_or_scope'] != {k: request['scope'][k] for k in ('id', 'revision')}:
                raise InvalidModel('Observation belongs to a different exact scope')
            observed_start, observed_end = (datetime.fromisoformat(body['window'][f]) for f in ('start', 'end'))
            if observed_end > as_of: reasons.append('OBSERVATION_AFTER_AS_OF')
            if not observed_start <= start or observed_end < end: reasons.append('WINDOW_NOT_COVERED')
            if (as_of - observed_end).total_seconds() > request['max_age_seconds']: reasons.append('OBSERVATION_STALE')
            value = body['value_or_artifact']
            if 'type' not in value: reasons.append('ARTIFACT_NOT_INTERPRETED')
            if reasons:
                inputs[binding['input']] = {'type': program.inputs[binding['input']], 'state': 'UNKNOWN'}
                diagnostics.extend({'input': binding['input'], 'code': reason} for reason in reasons)
            else: inputs[binding['input']] = deepcopy(value)
            observations.append({'input': binding['input'], 'observation': binding['observation'], 'signal': body['metric_or_signal'],
                'window': body['window'], 'coverage': body['coverage'], 'value_or_artifact': value, 'quality_reasons': reasons})
    evaluation = evaluate({'expression': request['method']['expression'], 'inputs': inputs})
    result = evaluation['result']
    if diagnostics and result == 'SATISFIED': result = 'UNKNOWN'
    report = {'engine': ENGINE, 'execution': evaluation['execution'], 'result': result, 'as_of': request['as_of'],
        'scope': request['scope'], 'expected': request['expected'], 'expected_name': expected['meta']['name'],
        'method': request['method'], 'window': request['window'], 'observations': observations, 'evaluation': evaluation, 'diagnostics': diagnostics,
        'mapping_qualification': 'DECLARED_NOT_INDEPENDENTLY_VALIDATED', 'coverage': 'PARTIAL',
        'business_verification_granted': False, 'automatic_model_change': False, 'external_action_executed': False,
        'request_digest': artifact_digest({'request': request, 'constant_inputs': constants} if constants else request), 'limitations': ['Comparison follows an explicit caller-provided mapping',
            'Partial population coverage is not an enterprise completeness claim', 'Source observations remain DRAFT',
            'No artifact download, remote collection, automatic Drift creation or remediation']}
    if constants: report['constant_inputs'] = deepcopy(constants)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Runtime comparison report exceeds its budget') from exc
    report['report_digest'] = artifact_digest(report)
    return report


def verify_ingestions(store, conn):
    from sqlalchemy import select
    from air.storage import service_records
    for record_id in conn.execute(select(service_records.c.id).where(service_records.c.kind == 'runtime_ingestion')).scalars():
        row = store._get_record(conn, record_id);payload = row['payload'];request = payload['request']
        check_schema(request, INGEST)
        if not validate(request['observations'])['valid']: raise InvalidModel('Imported observation ingestion is invalid')
        store._required(conn, request['source'], 'air.Source')
        expected = []
        for obj in request['observations']:
            pin = {**exact(obj), 'digest': digest(obj)}
            stored = store._required(conn, pin, 'air.RuntimeObservation')
            if canonical(stored) != canonical(obj): raise InvalidModel('Imported ingestion differs from its observations')
            if key(request['source']) not in {key(ref) for ref in obj['meta']['provenance']['source_refs']}:
                raise InvalidModel('Imported observation lost its ingestion source')
            for _, ref, kinds in reference_slots(obj):
                if store._required(conn, ref)['meta']['type'] not in kinds:
                    raise InvalidModel('Imported observation reference has an incompatible type')
            expected.append(pin)
        if expected != payload['observations'] or row['scope'] != request['observations'][0]['meta']['namespace']:
            raise InvalidModel('Imported ingestion receipt does not match its pinned observations')
