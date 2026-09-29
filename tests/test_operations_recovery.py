import errno
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from air import backup
from air.api import create_app
from air.cli import bootstrap
from air.config import Settings
from air.server_logging import EventLog
from air.storage import Store


def message():
    return logging.LogRecord('uvicorn.error', logging.ERROR, 'PRIVATE_PATH', 1,
                             'Bearer PRIVATE_TOKEN %s', ('PRIVATE_PAYLOAD',), (ValueError, ValueError('PRIVATE_ERROR'), None))


def test_rotating_events_are_bounded_and_never_format_free_text(tmp_path):
    log = EventLog(tmp_path, maximum=1024, backups=2)
    for _ in range(100): log.handle(message())
    log.close()
    files = list(tmp_path.glob('server-events.jsonl*'))
    assert len(files) == 3 and all(p.stat().st_size <= 1024 for p in files)
    for p in files:
        text = p.read_text(encoding='utf-8')
        assert 'PRIVATE' not in text and 'Bearer' not in text and 'Traceback' not in text
        assert all(set(json.loads(line)) == {'time','level','event'} for line in text.splitlines())


def test_logging_failure_degrades_readiness_and_recovers_without_secret_trace(store, tmp_path, monkeypatch, capsys):
    log = EventLog(tmp_path, maximum=1024, backups=1)
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)), run_worker=False)
    app.state.event_log = log
    check = log.validate_paths
    def full(): raise OSError(errno.ENOSPC, 'PRIVATE_DISK_ERROR')
    try:
        with TestClient(app) as client:
            assert client.get('/ready').status_code == 200
            monkeypatch.setattr(log, 'validate_paths', full)
            log.handle(message())
            assert log.snapshot()['write_failures'] == 1
            assert client.get('/ready').status_code == 503
            assert capsys.readouterr().err == ''
            monkeypatch.setattr(log, 'validate_paths', check)
            log.handle(message())
            assert client.get('/ready').status_code == 200
    finally: log.close()


@pytest.mark.parametrize('maximum,backups', [(0,1),(1024,0),(1024,21),(104857601,1)])
def test_invalid_log_retention_is_refused(tmp_path, maximum, backups):
    with pytest.raises(ValueError): EventLog(tmp_path, maximum=maximum, backups=backups)


def test_log_refuses_a_hardlink_without_changing_its_target(tmp_path):
    import os
    target = tmp_path/'target';target.write_text('original')
    try: os.link(target, tmp_path/'server-events.jsonl')
    except OSError: pytest.skip('Hardlinks unavailable on this filesystem')
    with pytest.raises(ValueError): EventLog(tmp_path)
    assert target.read_text() == 'original'


@pytest.mark.parametrize('failure', ['deadline','disk_error'])
def test_failed_backup_never_publishes_destination_or_changes_source(tmp_path, example, monkeypatch, failure):
    home = tmp_path/'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        original = store.put(example, 'operator')
        if failure == 'deadline':
            ticks = iter([0, 999, 999, 999])
            from types import SimpleNamespace
            monkeypatch.setattr(backup, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))
        else:
            def full(_): raise OSError(errno.ENOSPC, 'Private diagnostic')
            monkeypatch.setattr(backup, 'checksum', full)
        destination = tmp_path/'snapshot'
        with pytest.raises((TimeoutError, OSError)): backup.snapshot(home, destination, timeout=1)
        assert not destination.exists()
        assert len(list(tmp_path.glob('snapshot.pending-*'))) == 1
        assert store.get(example['meta']['id'], 1)['digest'] == original['digest']
    finally: store.engine.dispose()
