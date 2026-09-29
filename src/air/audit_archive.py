"""Copy immutable audit events to an owner-only archive; never delete authorship evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
from sqlalchemy import select
from air.storage import Store, audits
from air.config import Settings, protect_directory, write_private


def cutoff(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('Audit cutoff requires a timezone')
    return result.astimezone(timezone.utc)


def export(home, destination, before):
    before = cutoff(before)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink(): raise ValueError('A new archive directory is required')
    pending = destination.with_name(destination.name+'.pending-'+uuid.uuid4().hex)
    protect_directory(pending)
    store = Store(Settings.load(home).database_url)
    count = 0; digest = hashlib.sha256()
    try:
        with store.engine.connect() as conn, (pending/'audit.jsonl').open('xb') as output:
            import os
            if os.name != 'nt': os.fchmod(output.fileno(),0o600)
            query = select(audits).order_by(audits.c.at,audits.c.id).execution_options(stream_results=True)
            for row in conn.execute(query).mappings():
                if cutoff(row['at']) >= before: continue
                raw = (json.dumps(dict(row),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
                output.write(raw);digest.update(raw);count += 1
            output.flush();os.fsync(output.fileno())
    finally: store.engine.dispose()
    manifest = {'format':'air.audit-archive/1','events':count,'sha256':digest.hexdigest(),
                'before':before.isoformat(), 'source_events_deleted':False,'contains_business_identifiers':True}
    write_private(pending/'manifest.json',manifest)
    pending.rename(destination)
    return {'status':'PASS','events':count,'sha256':manifest['sha256'],'source_events_deleted':False}


def verify(directory):
    directory = Path(directory)
    for name in ('manifest.json','audit.jsonl'):
        if (directory/name).is_symlink() or not (directory/name).is_file(): raise ValueError('Invalid archive file')
    with (directory/'manifest.json').open('rb') as stream: raw_manifest = stream.read(8193)
    if len(raw_manifest)>8192: raise ValueError('Oversized audit manifest')
    manifest = json.loads(raw_manifest)
    if not isinstance(manifest,dict) or manifest.get('format') != 'air.audit-archive/1': raise ValueError('Unsupported audit archive')
    before = cutoff(manifest['before']);digest = hashlib.sha256();count = 0
    with (directory/'audit.jsonl').open('rb') as source:
        while raw := source.readline(65537):
            if len(raw)>65536 or not raw.endswith(b'\n'): raise ValueError('Invalid audit line')
            row = json.loads(raw)
            if not isinstance(row,dict) or set(row) != {'id','at','subject','action','target'} or not all(isinstance(v,str) for v in row.values()) or cutoff(row['at']) >= before:
                raise ValueError('Invalid audit event')
            digest.update(raw);count += 1
    if type(manifest.get('events')) is not int or count != manifest['events'] or digest.hexdigest() != manifest['sha256']:
        raise ValueError('Audit archive checksum mismatch')
    return {'status':'PASS','events':count,'sha256':digest.hexdigest(),'authenticated_origin':False}
