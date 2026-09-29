import json
from pathlib import Path
import pytest
from air.audit_archive import export,verify
from air.cli import bootstrap
from air.config import Settings
from air.storage import Store


def test_export_verification_keeps_authorship_and_detects_tampering(tmp_path,example):
    home = tmp_path/'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        stored = store.put(example,'original-author')
        destination = tmp_path/'archive'
        result = export(home,destination,'2099-01-01T00:00:00Z')
        assert result['events'] >= 1 and not result['source_events_deleted']
        assert verify(destination)['sha256'] == result['sha256']
        assert store.author(stored) == 'original-author'
        with pytest.raises(ValueError): export(home,destination,'2099-01-01T00:00:00Z')
        text = (destination/'audit.jsonl').read_text(encoding='utf-8')
        (destination/'audit.jsonl').write_text(text.replace('original-author','changed-author'),encoding='utf-8')
        with pytest.raises(ValueError,match='checksum'): verify(destination)
        assert store.author(stored) == 'original-author'
    finally: store.engine.dispose()


def test_audit_cutoff_requires_timezone_and_can_export_empty(tmp_path):
    home = tmp_path/'home';bootstrap(home)
    with pytest.raises(ValueError,match='timezone'): export(home,tmp_path/'bad','2020-01-01')
    result = export(home,tmp_path/'old','1900-01-01T01:00:00+01:00')
    assert result['events'] == 0 and verify(tmp_path/'old')['status'] == 'PASS'
    (tmp_path/'old'/'audit.jsonl').write_bytes(b'x'*65537)
    with pytest.raises(ValueError,match='line'): verify(tmp_path/'old')
