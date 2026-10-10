"""Admission limits for new immutable data, checked inside serialized registry writes."""
import json
import os
from sqlalchemy import select, func
from air.foundation import InvalidModel

DEFAULTS = {'revisions':100000, 'namespace_revisions':10000, 'records':1000000,
            'namespace_records':100000, 'artifact_bytes':1073741824,
            'namespace_artifact_bytes':268435456, 'pending_jobs':1000, 'subject_pending_jobs':100}
CONTROL = {'job_claim', 'job_result', 'job_cancellation', 'authority_policy', 'review_revocation',
           'proof_key_revocation', 'admission_review_revocation', 'closure_review_revocation',
           'package_revocation', 'builder_revocation', 'admission_release', 'admission_release_marker'}


class QuotaExceeded(InvalidModel):
    def __init__(self, resource):
        self.resource = resource
        super().__init__('AIR quota exceeded: '+resource)


def limits():
    result = {}
    for name, default in DEFAULTS.items():
        value = int(os.environ.get('AIR_QUOTA_'+name.upper(), str(default)))
        if not 1 <= value <= 10**12: raise ValueError('Invalid AIR quota: '+name)
        result[name] = value
    return result


def count(conn, table, *where):
    return conn.execute(select(func.count()).select_from(table).where(*where)).scalar_one()


def require(resource, used, added=1):
    if used + added > limits()[resource]: raise QuotaExceeded(resource)


def revision(conn, namespace):
    from air.storage import identities, revisions
    require('revisions', count(conn, revisions))
    scoped = revisions.join(identities, revisions.c.id == identities.c.id)
    require('namespace_revisions', count(conn, scoped, identities.c.namespace == namespace))


def record(conn, namespace, kind, payload):
    if kind in CONTROL or (kind == 'package_event' and payload.get('event') == 'REVOKED'): return
    from air.storage import service_records
    require('records', count(conn, service_records))
    require('namespace_records', count(conn, service_records, service_records.c.scope == namespace))


def artifact(conn, namespace, size, checksum):
    from air.storage import artifact_blobs, service_records
    exists = conn.execute(select(artifact_blobs.c.digest).where(artifact_blobs.c.digest == checksum)).first()
    total = conn.execute(select(func.coalesce(func.sum(artifact_blobs.c.size),0))).scalar_one()
    require('artifact_bytes', total, 0 if exists else size)
    used = 0
    query = select(service_records.c.payload).where(service_records.c.kind == 'artifact_manifest', service_records.c.scope == namespace)
    for payload in conn.execute(query.execution_options(stream_results=True)).scalars():
        used += json.loads(payload)['request']['size']
    require('namespace_artifact_bytes', used, size)


def job(conn, subject):
    from air.storage import job_heads, service_records
    active = job_heads.c.status.in_(('QUEUED','RUNNING'))
    require('pending_jobs', count(conn, job_heads, active))
    require('subject_pending_jobs', count(conn, job_heads.join(service_records, job_heads.c.id == service_records.c.id), active, service_records.c.actor == subject))


def status(conn):
    from air.storage import revisions, service_records, artifact_blobs, job_heads
    return {'limits':limits(), 'usage':{'revisions':count(conn,revisions), 'records':count(conn,service_records),
        'artifact_bytes':conn.execute(select(func.coalesce(func.sum(artifact_blobs.c.size),0))).scalar_one(),
        'pending_jobs':count(conn,job_heads,job_heads.c.status.in_(('QUEUED','RUNNING')))},
        'scope':'REGISTRY_ADMISSION', 'physical_disk_limit':False, 'control_records_exempt':True}
