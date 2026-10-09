"""Bounded connector mapping over an already authorized immutable artifact.

No dynamic Python imports, URLs, shell commands or filesystem paths come from
the artifact. Measurements remain declarations until separately qualified.
"""
import json

from air import artifacts
from air.access import ScopedStore
from air.core import record, canonical, validate, reference_slots
from air.expr import artifact_digest
from air.foundation import check_budget, check_schema, exact, key, InvalidModel
from air.packages import RECORD_REF
from air.parsing import parse
from air.projections import SNAPSHOT

ADAPTER = 'air.observations-json/1'
REQUEST = record({'adapter': {'const': ADAPTER}, 'artifact': RECORD_REF, 'source': SNAPSHOT,
    'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128}})


def mapped_observations(store, principal, policy, artifact):
    metadata = artifacts.describe(store, principal, policy, {'artifact': artifact})
    if metadata['media_type'] != 'application/json' or metadata['size'] > artifacts.JSON_MAX_SIZE:
        raise InvalidModel('The observations connector requires JSON up to 512 KiB')
    metadata, raw = artifacts.download(store, principal, policy, {'artifact': artifact})
    document = parse(raw)
    from air.runtime import INGEST
    check_schema(document, record({'observations': INGEST['properties']['observations']}))
    observations = document['observations']
    checked = validate(observations)
    if not checked['valid']: raise InvalidModel('Invalid observations in connector artifact', checked)
    normalized = sorted([json.loads(canonical(o)) for o in observations], key=lambda o: key(exact(o)))
    if len({key(exact(o)) for o in normalized}) != len(normalized):
        raise InvalidModel('Connector artifact contains duplicate observation revisions')
    return metadata, normalized


def preview(store, principal, policy, request):
    check_schema(request, REQUEST)
    metadata, observations = mapped_observations(store, principal, policy, request['artifact'])
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([request['source']])
    row = guarded.get(request['source']['id'], request['source']['revision'])
    if row is None or row['digest'] != request['source']['digest'] or row['object']['meta']['type'] != 'air.Source':
        raise InvalidModel('Connector requires an exact readable Source')
    refs = [ref for obj in observations for _, ref, _ in reference_slots(obj)]
    guarded.check_read(refs)
    for obj in observations:
        if key(request['source']) not in {key(r) for r in obj['meta']['provenance']['source_refs']}:
            raise InvalidModel('Each observation must cite the declared connector source')
    command = {'idempotency_key': request['idempotency_key'], 'source': request['source'],
               'observations': observations, 'source_artifact': request['artifact'], 'connector': ADAPTER}
    result = {'adapter': ADAPTER, 'artifact': request['artifact'], 'content_digest': metadata['content_digest'],
        'mapping': 'EXACT_RUNTIME_OBSERVATION_JSON', 'qualification': 'STRUCTURAL_MAPPING_ONLY',
        'prepared_ingestion': command, 'registry_written': False, 'external_effects': False,
        'measurement_authenticity_verified': False, 'request_digest': artifact_digest(request)}
    check_budget(result)
    result['report_digest'] = artifact_digest(result)
    return result
