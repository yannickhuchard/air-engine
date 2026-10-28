"""Import a retained CI ledger with exact source/build bindings. No remote job execution."""
from copy import deepcopy
from datetime import datetime, timezone
from air import artifacts
from air.access import ScopedStore
from air.builder_handoff import commit_guard
from air.collaboration import identity_context, identity_uri
from air.core import record, TEXT, URI, INSTANT, validate, digest
from air.foundation import check_schema, InvalidModel, key, exact
from air.packages import RECORD_REF, reference
from air.parsing import parse
from air.projections import SNAPSHOT, snapshot

SHORT = {**TEXT, 'maxLength': 256}
REPORT = record({'format': {'const': 'air.ci-ledger/1'}, 'repository': URI, 'executor': URI,
    'source_revision': {'type': 'string', 'pattern': '^(?:[a-f0-9]{40}|[a-f0-9]{64})$'},
    'build_artifact': RECORD_REF, 'build_digest': SNAPSHOT['properties']['digest'],
    'started_at': INSTANT, 'finished_at': INSTANT,
    'run_url': {**URI, 'pattern': '^https://[^\\s]+$'},
    'tests': {'type': 'array', 'minItems': 1, 'maxItems': 4096,
        'items': record({'id': SHORT, 'status': {'enum': ['PASS', 'FAIL', 'ERROR', 'SKIP']}})}})
REQUEST = record({'baseline': SNAPSHOT, 'source': SNAPSHOT, 'case': SNAPSHOT, 'environment': SNAPSHOT,
    'report': RECORD_REF, 'object_id': URI, 'idempotency_key': SHORT})
ENGINE = 'air.ci-ledger-ingestion/1'


def ingest(store, principal, policy, request, settings):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    by = {key(o['meta']): o for o in exported['objects']}
    home = exported['baseline']['meta']['namespace']; policy.require(principal, 'write', home)
    selected = {}
    for field, kind in [('source', 'air.Source'), ('case', 'air.VerificationCase'), ('environment', 'air.Environment')]:
        obj = by.get(key(request[field]))
        if not obj or obj['meta']['type'] != kind or digest(obj) != request[field]['digest']:
            raise InvalidModel('CI evidence requires exact baseline source, case and environment')
        selected[field] = obj
    if selected['case']['body']['method'] != 'TEST': raise InvalidModel('CI ledger requires a TEST case')
    metadata, raw = artifacts.download(store, principal, policy, {'artifact': request['report']})
    if metadata['namespace'] != home: raise InvalidModel('CI report belongs to another namespace')
    if metadata['media_type'] != 'application/json' or len(raw) > 524288:
        raise InvalidModel('CI ledger must be JSON up to 512 KiB')
    report = parse(raw); check_schema(report, REPORT)
    if selected['source']['body'].get('source_revision') != report['source_revision']:
        raise InvalidModel('CI source revision differs from the pinned Source')
    source = selected['source']['body']
    if source['kind'] != 'CODE' or source['locator'] != report['repository']:
        raise InvalidModel('CI repository differs from the pinned Source')
    build, _ = artifacts.download(store, principal, policy, {'artifact': report['build_artifact']})
    if build['content_digest'] != report['build_digest']: raise InvalidModel('CI build digest differs from retained artifact')
    started, finished = [datetime.fromisoformat(report[f]) for f in ('started_at', 'finished_at')]
    if started > finished or finished > datetime.now(timezone.utc): raise InvalidModel('CI execution window is invalid')
    if len({t['id'] for t in report['tests']}) != len(report['tests']): raise InvalidModel('Duplicate CI test identifiers')
    states = {t['status'] for t in report['tests']}
    result = 'FAIL' if states & {'FAIL', 'ERROR'} else 'INCONCLUSIVE' if 'SKIP' in states else 'PASS'
    meta = deepcopy(selected['case']['meta'])
    meta.update(id=request['object_id'], revision=1, type='air.OperationalEvidence', namespace=home,
        name='CI evidence ' + report['source_revision'][:12], recorded_at=report['finished_at'],
        provenance={'recorded_by': identity_uri(identity_context(principal, settings)),
                    'method': 'air.ci-ledger/1 retained import; execution declared by the source ledger', 'source_refs': [exact(selected['source'])]})
    obj = {'meta': meta, 'body': {'case': exact(selected['case']), 'kind': 'CI_CD', 'result': result,
        'executed_at': report['finished_at'], 'executor': report['executor'],
        'environment': exact(selected['environment']), 'report': metadata['artifact_reference'],
        'run_url': report['run_url'], 'source_revision': report['source_revision'],
        'summary': 'Retained CI ledger; ' + str(len(report['tests'])) + ' results; no independent execution qualification', 'metrics': []}}
    if not validate(obj)['valid']: raise InvalidModel('Mapped CI evidence is invalid')
    payload = {'request': request, 'report_digest': metadata['content_digest'], 'build_digest': build['content_digest'],
               'object': obj, 'execution_authenticity_verified': False}
    import hashlib
    identifier = 'urn:air:ci-ingestion:' + hashlib.sha256((principal['subject'] + '\0' + request['idempotency_key']).encode()).hexdigest()
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        row = store._record_once(conn, identifier, 'ci_ingestion', home, principal['subject'], payload)['record']
        store._put(conn, obj, principal['subject'])
    return {'engine': ENGINE, 'receipt': reference(row), 'object': obj,
        'object_reference': {**exact(obj), 'digest': digest(obj)},
        'qualification': 'RECORDED_TEST_LEDGER_NOT_INDEPENDENTLY_QUALIFIED',
        'execution_authenticity_verified': False, 'external_job_executed': False}
