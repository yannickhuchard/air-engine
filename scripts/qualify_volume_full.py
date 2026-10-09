"""Linux only: fill a newly mounted 16 MiB tmpfs, never the host or a business volume."""
import argparse
import errno
import json
import logging
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import uuid

from sqlalchemy.exc import OperationalError
from air import __version__
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings
from air.server_logging import EventLog
from air.storage import Store


def mount_info(path):
    result = subprocess.run(['findmnt', '--json', '--mountpoint', str(path), '--output', 'TARGET,FSTYPE,SIZE', '--bytes'],
                            capture_output=True, text=True, timeout=10, check=True)
    mounts = json.loads(result.stdout)['filesystems']
    if len(mounts) != 1 or Path(mounts[0]['target']).resolve() != path.resolve() or mounts[0]['fstype'] != 'tmpfs' or int(mounts[0]['size']) != 16*1024**2:
        raise ValueError('Only the newly mounted 16 MiB tmpfs is allowed')


def exercise(volume):
    mount_info(volume)
    home = volume/'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try: original = store.record_once('before-full', 'ops.fixture', 'ops', 'fixture', {'value':1})['record']
    finally: store.engine.dispose()
    log = EventLog(home, maximum=1024, backups=1)
    filler = volume/'filler.bin'
    try:
        with filler.open('xb', buffering=0) as output:
            try:
                while True: output.write(b'x'*65536)
            except OSError as exc:
                if exc.errno != errno.ENOSPC: raise
        assert os.statvfs(volume).f_bavail == 0
        store = Store(Settings.load(home).database_url)
        try:
            try: store.record_once('failed-full', 'ops.fixture', 'ops', 'fixture', {'synthetic':'x'*1048576})
            except OperationalError as exc:
                if exc.orig.sqlite_errorcode & 255 not in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_IOERR): raise
            else: raise AssertionError('Write succeeded on the full tmpfs')
        finally: store.engine.dispose()
        log.handle(logging.LogRecord('uvicorn.error', logging.ERROR, '', 0, 'PRIVATE', (), None))
        assert not log.snapshot()['last_write_ok'] and log.snapshot()['write_failures'] > 0
        try: snapshot(home, volume/'failed-backup', timeout=1)
        except (OSError, sqlite3.Error): pass
        else: raise AssertionError('Backup unexpectedly succeeded on full tmpfs')
        assert not (volume/'failed-backup').exists()
    finally:
        # This exact file was created exclusively on the freshly verified private mount.
        if filler.exists(): filler.unlink()
        log.close()
    store = Store(Settings.load(home).database_url)
    try:
        assert store.get_record('before-full') == original
        assert store.get_record('failed-full') is None
        store.record_once('after-full', 'ops.fixture', 'ops', 'fixture', {'value':2})
        with store.engine.connect() as conn: assert conn.exec_driver_sql('PRAGMA quick_check').all() == [('ok',)]
    finally: store.engine.dispose()
    snapshot(home, volume/'backup');restore(volume/'backup', volume/'restored')
    store = Store(Settings.load(volume/'restored').database_url)
    try:
        assert store.get_record('before-full') == original
        assert store.get_record('after-full') is not None
    finally: store.engine.dispose()
    return {'physical_volume_enospc':'PASS', 'medium':'16_MiB_TMPFS', 'committed_data_preserved':True,
            'failed_write_absent':True, 'subsequent_write':'PASS', 'logging_failure_detected':True,
            'failed_backup_unpublished':True, 'backup_restore_after_recovery':'PASS'}


def qualify(work_root, allow_mount):
    if sys.platform != 'linux' or not allow_mount or os.environ.get('AIR_DATABASE_URL'):
        raise ValueError('Requires Linux, explicit --allow-mount and no AIR_DATABASE_URL')
    root = work_root.resolve();root.mkdir(parents=True, exist_ok=True)
    volume = root/('air-full-volume-'+uuid.uuid4().hex)
    volume.mkdir(mode=0o700)
    report = {'version':__version__, 'status':'FAIL', 'production_ready':False,
              'environment':{'os':platform.platform(),'python':platform.python_version()},
              'cleanup':'NOT_MOUNTED', 'not_executed':['Windows physical ENOSPC','Host power loss','Persistent disk hardware failure']}
    mounted = False
    try:
        subprocess.run(['sudo','-n','mount','-t','tmpfs','-o',f'size=16m,uid={os.getuid()},gid={os.getgid()},mode=0700',
                        'air-qualification',str(volume)], check=True, capture_output=True, timeout=20)
        mounted = True
        report['checks'] = exercise(volume)
        report['status'] = 'PASS_SCOPED'
    except Exception as exc: report['error_type'] = type(exc).__name__
    finally:
        if mounted:
            try:
                subprocess.run(['sudo','-n','umount',str(volume)], check=True,capture_output=True,timeout=20)
                assert not os.path.ismount(volume)
                report['cleanup'] = 'UNMOUNTED_VERIFIED'
            except Exception as exc:
                report.update(status='FAIL', cleanup='FAILED', cleanup_error_type=type(exc).__name__)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-mount', action='store_true')
    args = parser.parse_args()
    report = qualify(args.work_root, args.allow_mount)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps({'status':report['status'],'cleanup':report['cleanup'],'report':str(args.output)}))
    raise SystemExit(0 if report['status']=='PASS_SCOPED' else 1)
