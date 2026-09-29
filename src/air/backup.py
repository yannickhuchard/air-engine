"""SQLite snapshots and isolated restore, available to the trusted OS owner only."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid
import time
import math
import stat
import re
from sqlalchemy import update
from air.config import Settings, protect_directory, write_private
from air.storage import Store, tokens, SCHEMA_VERSION


def checksum(file):
    result = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return "sha256:" + result.hexdigest()


def snapshot(home, destination, timeout=300):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 3600:
        raise ValueError('Snapshot timeout must be 1..3600 seconds')
    settings = Settings.load(home)
    store = Store(settings.database_url)
    try:
        if not store.sqlite or not store.engine.url.database or store.engine.url.database == ":memory:":
            raise ValueError("This backup command requires a file-based SQLite installation")
        database = Path(store.engine.url.database).resolve()
    finally:
        store.engine.dispose()
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Backup requires a new destination')
    pending = destination.with_name(destination.name + '.pending-' + uuid.uuid4().hex)
    pending.mkdir(parents=True, exist_ok=False)
    protect_directory(pending)
    started = time.monotonic()
    def deadline(*_):
        if time.monotonic() - started >= timeout: raise TimeoutError('SQLite snapshot deadline exceeded')
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(pending / "air.db")) as target:
            source.backup(target, pages=256, progress=deadline, sleep=0.05)
            if target.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite backup integrity check failed")
            schema = target.execute("SELECT version FROM schema_version WHERE id=1").fetchone()[0]
    config = json.loads((home / "config.json").read_text(encoding="utf-8"))
    config.pop("database_url", None)
    write_private(pending / "config.json", config)
    files = ["air.db", "config.json"]
    policy = home / "access-policy.json"
    if policy.exists():
        from air.access import AccessPolicy
        value = AccessPolicy.load(home)
        write_private(pending / "access-policy.json", value.document)
        files.append("access-policy.json")
    manifest = {"format": "air.sqlite-backup/1", "schema": schema,
        "files": {name: checksum(pending / name) for name in files},
        "plaintext_credentials_included": False}
    write_private(pending / "manifest.json", manifest)
    deadline()
    pending.rename(destination)
    return {"status": "PASS", "backup": str(destination.resolve()), "schema": schema,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "plaintext_credentials_included": False}


def validate_backup(backup):
    backup = Path(backup)
    path = backup / 'manifest.json'
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode): raise ValueError('Backup manifest must be a regular file')
    with path.open('rb') as stream: raw = stream.read(65537)
    if len(raw) > 65536: raise ValueError('Backup manifest exceeds its size limit')
    manifest = json.loads(raw)
    expected = {"air.db", "config.json"}
    if not isinstance(manifest, dict) or manifest.get("format") != "air.sqlite-backup/1" or not isinstance(manifest.get('files'), dict) or set(manifest['files']) not in (expected, expected | {"access-policy.json"}):
        raise ValueError("Unsupported backup manifest")
    if type(manifest.get('schema')) is not int or manifest.get("schema") not in (1, 2, 3, 4, 5, SCHEMA_VERSION):
        raise ValueError("Unsupported backup schema")
    for name, digest in manifest["files"].items():
        if not isinstance(digest, str) or not re.fullmatch('sha256:[0-9a-f]{64}', digest) or (backup / name).is_symlink() or not stat.S_ISREG((backup / name).stat().st_mode) or checksum(backup / name) != digest:
            raise ValueError("Backup checksum mismatch")
    return manifest


def restore(backup, destination):
    if os.environ.get("AIR_DATABASE_URL"):
        raise ValueError("Unset AIR_DATABASE_URL before restoring an isolated SQLite installation")
    manifest = validate_backup(backup)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Restore requires a new AIR home; existing installations are never overwritten")
    pending = destination.with_name(destination.name + ".pending-" + uuid.uuid4().hex)
    pending.mkdir(parents=True, exist_ok=False)
    protect_directory(pending)
    shutil.copyfile(backup / "air.db", pending / "air.db")
    with closing(sqlite3.connect(pending / "air.db")) as database:
        if database.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Restored database integrity check failed")
        if database.execute("SELECT version FROM schema_version WHERE id=1").fetchone()[0] != manifest["schema"]:
            raise ValueError("Backup schema disagrees with manifest")
    config = json.loads((backup / "config.json").read_text(encoding="utf-8"))
    config.pop("database_url", None)
    config["instance_id"] = str(uuid.uuid4())
    # Recovery starts locally; TLS keys are deployment secrets, not registry data.
    config.pop("server", None)
    write_private(pending / "config.json", config)
    if "access-policy.json" in manifest["files"]:
        policy = json.loads((backup / "access-policy.json").read_text(encoding="utf-8"))
        policy["version"] = "restore-" + config["instance_id"]
        from air.access import AccessPolicy
        AccessPolicy(policy)
        write_private(pending / "access-policy.json", policy)
    settings = Settings.load(pending)
    store = Store(settings.database_url)
    try:
        store.migrate()
        from air.authority import sync_policy
        from air.access import AccessPolicy
        sync_policy(store, AccessPolicy.load(pending), only_if_missing=True)
        with store.write() as conn:
            from air.artifacts import verify_artifacts
            verify_artifacts(store, conn)
            from air.view_capture import verify_views
            verify_views(store, conn)
            conn.execute(update(tokens).values(revoked=1))
            store.audit(conn, "local-operator", "registry.restored", config["instance_id"])
        if settings.auth_mode == "local":
            write_private(pending / "credentials.json", store.create_token("local-admin", "admin"))
        counts = store.counts()
    finally:
        store.engine.dispose()
    # Rename makes only a completely restored installation visible at the target.
    pending.rename(destination)
    return {"status": "PASS", "home": str(destination.resolve()), "schema": SCHEMA_VERSION,
        "old_tokens_revoked": True, "review_policy_revalidation_required": True, **counts}
