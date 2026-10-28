"""Permitted client provenance and engine-computed progress, without model reasoning capture."""
import hashlib
from air import artifacts, readiness
from air.access import Forbidden, ScopedStore
from air.builder_handoff import commit_guard
from air.core import record, TEXT
from air.foundation import check_schema, InvalidModel
from air.packages import RECORD_REF, reference
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict

SHORT = {**TEXT, 'maxLength': 128}
COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 1000000000}
CHECKSUM = SNAPSHOT['properties']['digest']
REQUEST = record({'idempotency_key': SHORT, 'before': SNAPSHOT, 'after': SNAPSHOT,
    'provider': SHORT, 'model': SHORT, 'client_version': SHORT,
    'context_export': RECORD_REF, 'instructions': RECORD_REF,
    'outputs': {'type': 'array', 'items': RECORD_REF, 'maxItems': 64, 'uniqueItems': True},
    'tools': {'type': 'array', 'maxItems': 256, 'items': record({'name': SHORT,
        'request_digest': CHECKSUM, 'response_digest': CHECKSUM})},
    'settings': record({'temperature': {'type': 'number', 'minimum': 0, 'maximum': 2},
        'seed': {'type': 'integer', 'minimum': -2147483648, 'maximum': 2147483647},
        'max_output_tokens': {'type': 'integer', 'minimum': 1, 'maximum': 10000000}}, []),
    'usage': {'oneOf': [record({'input_tokens': COUNT, 'output_tokens': COUNT,
        'cost': {'type': 'string', 'pattern': '^(?:0|[1-9][0-9]{0,11})(?:\\.[0-9]{1,6})?$'},
        'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'}}),
        record({'state': {'const': 'UNKNOWN'}, 'reason': SHORT})]}},
    ['idempotency_key', 'before', 'after', 'provider', 'model', 'client_version',
     'context_export', 'instructions', 'outputs', 'tools', 'usage'])
READ = record({'trace': RECORD_REF})
ENGINE = 'air.generation-trace/1'


def create(store, principal, policy, request, settings=None):
    check_schema(request, REQUEST)
    before = snapshot(ScopedStore(store, principal, policy), request['before'])
    after = snapshot(ScopedStore(store, principal, policy), request['after'])
    home = before['baseline']['meta']['namespace']
    policy.require(principal, 'write', home)
    if request['before']['id'] != request['after']['id'] or request['after']['revision'] < request['before']['revision']:
        raise InvalidModel('Generation trace must compare ordered revisions of one baseline')
    if after['baseline']['meta']['namespace'] != home: raise InvalidModel('Generation scope changed')
    export = store.get_record(request['context_export']['id'])
    if not export or export['kind'] != 'context_export' or reference(export) != request['context_export']:
        raise InvalidModel('Generation context needs an exact retained export receipt')
    if export['actor'] != principal['subject'] or export['payload']['request']['baseline'] != request['before']:
        raise Forbidden('Generation trace must bind this caller and original context baseline')
    retained = [artifacts.describe(store, principal, policy, {'artifact': r})
                for r in [request['instructions'], *request['outputs']]]
    identifier = 'urn:air:generation-trace:' + hashlib.sha256((principal['subject'] + '\0' + request['idempotency_key']).encode()).hexdigest()
    prior = store.get_record(identifier)
    if prior:
        if prior['payload']['request'] != request: raise Conflict('Generation trace key reused for another request')
        with store.write() as conn: commit_guard(store, conn, principal, policy, settings)
        return {'trace': reference(prior), **prior['payload']}
    old = readiness.assess_readiness(store, principal, policy, {'baseline': request['before']})
    new = readiness.assess_readiness(store, principal, policy, {'baseline': request['after']})
    met = lambda report: {c['code'] for c in report['criteria'] if c['status'] == 'MET'}
    payload = {'engine': ENGINE, 'request': request, 'actor': principal['subject'],
        'policy_digest': policy.digest, 'artifact_digests': [a['content_digest'] for a in retained],
        'progress': {'before': old['result'], 'after': new['result'],
            'closed_criteria': sorted(met(new) - met(old)), 'regressed_criteria': sorted(met(old) - met(new)),
            'before_report_digest': old['report_digest'], 'after_report_digest': new['report_digest']},
        'qualification': 'DECLARED_CLIENT_TRACE_WITH_ENGINE_COMPUTED_CRITERIA',
        'provider_attested': False, 'tool_execution_attested': False, 'usage_independently_verified': False,
        'design_quality_verified': False, 'private_reasoning_requested': False}
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        row = store._record_once(conn, identifier, 'generation_trace', home, principal['subject'], payload)['record']
    return {'trace': reference(row), **payload}


def read(store, principal, policy, request):
    check_schema(request, READ)
    row = store.get_record(request['trace']['id'])
    if not row or row['kind'] != 'generation_trace': raise Forbidden('Generation trace unavailable')
    policy.require(principal, 'read', row['scope'])
    if reference(row) != request['trace']: raise InvalidModel('Generation trace digest differs')
    payload = row['payload']
    for field in ('before', 'after'): snapshot(ScopedStore(store, principal, policy), payload['request'][field])
    for r in [payload['request']['instructions'], *payload['request']['outputs']]:
        artifacts.describe(store, principal, policy, {'artifact': r})
    return {'trace': reference(row), **payload}
