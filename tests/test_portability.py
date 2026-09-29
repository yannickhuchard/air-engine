import json
import pytest
from sqlalchemy import inspect
from air.backup import checksum
from air.config import Settings
from air.foundation import exact
from air.portability import export_registry, import_registry
from air.storage import Store, metadata, SCHEMA_VERSION, RENEWAL_TABLES, AUTHORITY_TABLES, ARTIFACT_TABLES
from test_construction import construction, prepare


def test_registry_transfer_preserves_baseline_authorship_records_and_revokes_tokens(store, construction, tmp_path):
    base, request = prepare(store, construction)
    token = store.create_token("operator", "admin")
    receipt = store.record_once("urn:air:record:test", "note", "asteria.sav", "architect", {"purpose": "synthetic preservation probe"})
    folder = tmp_path / "transfer"
    exported = export_registry(store, folder)
    target_url = "sqlite:///" + (tmp_path / "target.db").as_posix()
    result = import_registry(folder, target_url)
    target = Store(target_url)
    try:
        assert target.export_baseline(request["baseline"])["digest"] == base["digest"]
        assert target.author(exact(base["baseline"])) == "architect"
        assert target.get_record("urn:air:record:test") == receipt["record"]
        assert not target.authenticate(token["access_token"])
        assert result["closed_baselines_verified"] == 1
        assert store.authenticate(token["access_token"])
        assert not exported["plaintext_credentials_included"]
        with pytest.raises(ValueError, match="empty"): import_registry(folder, target_url)
    finally: target.engine.dispose()


def test_semantic_tampering_rolls_back_empty_target(store, example, tmp_path):
    store.put(example, "owner")
    folder = tmp_path / "transfer";export_registry(store, folder)
    file = folder / "object_revision.jsonl"
    row = json.loads(file.read_text(encoding="utf-8"))
    obj = json.loads(row["payload"]);obj["body"]["boundary_description"] += " altered"
    row["payload"] = json.dumps(obj)
    file.write_text(json.dumps(row) + "\n", encoding="utf-8")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    manifest["tables"]["object_revision"].update(bytes=file.stat().st_size, digest=checksum(file))
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    url = "sqlite:///" + (tmp_path / "invalid.db").as_posix()
    with pytest.raises(ValueError, match="digest"): import_registry(folder, url)
    target = Store(url)
    try: assert inspect(target.engine).get_table_names() == []
    finally: target.engine.dispose()


def test_sqlite_export_can_import_into_selected_disposable_backend(store, construction, tmp_path):
    source = Store("sqlite:///" + (tmp_path / "source.db").as_posix())
    try:
        source.migrate();base, request = prepare(source, construction)
        folder = tmp_path / "transfer";export_registry(source, folder)
        # The store fixture is exclusively a new disposable database, explicitly
        # gated by AIR_TEST_ALLOW_RESET when PostgreSQL is selected.
        metadata.drop_all(store.engine)
        result = import_registry(folder, store.engine.url.render_as_string(hide_password=False))
        store.check_version()
        assert store.export_baseline(request["baseline"])["digest"] == base["digest"]
        assert result["backend"] == store.engine.dialect.name
    finally: source.engine.dispose()


def test_schema_two_registry_export_upgrades_into_schema_three(store, example, tmp_path):
    store.put(example, 'owner')
    bundle = tmp_path / 'schema-two';export_registry(store, bundle)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    # Reconstruct the exact earlier transfer shape: the six original tables,
    # schema_version=2 and no job projection. All integrity hashes are explicit.
    manifest['schema'] = 2
    manifest['tables'].pop('job_state')
    for table in (*AUTHORITY_TABLES, *RENEWAL_TABLES, *ARTIFACT_TABLES): manifest['tables'].pop(table.name)
    file = bundle / 'schema_version.jsonl'
    file.write_text(json.dumps({'id': 1, 'version': 2}) + chr(10), encoding='utf-8')
    manifest['tables']['schema_version'].update(bytes=file.stat().st_size, digest=checksum(file))
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    url = 'sqlite:///' + (tmp_path / 'upgraded.db').as_posix()
    result = import_registry(bundle, url)
    target = Store(url)
    try:
        target.check_version()
        assert result['schema'] == SCHEMA_VERSION and result['source_schema'] == 2
        assert target.get(example['meta']['id'], 1)['digest'] == store.get(example['meta']['id'], 1)['digest']
    finally: target.engine.dispose()
