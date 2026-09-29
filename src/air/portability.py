"""Private, checksummed registry transfer to an empty SQLite/PostgreSQL database."""
import os
import base64
import binascii
import uuid
import json
import hashlib
from pathlib import Path
from sqlalchemy import inspect, select, update
from air.backup import checksum
from air.config import protect_directory, write_private
from air.access import AccessPolicy
from air.core import digest, validate
from air.expr import artifact_digest
from air.foundation import InvalidModel
from air.parsing import check_tree, pairs
from air.storage import Store, SCHEMA_VERSION, AUTHORITY_TABLES, RENEWAL_TABLES, ARTIFACT_TABLES, metadata, versions, identities, revisions, service_records, tokens, now

FORMAT = "air.registry-transfer/1"
MAX_LINE = 4 * 1024 * 1024
TABLES = {table.name: table for table in metadata.sorted_tables}


def export_registry(store, destination, access_policy=None):
    destination = destination.absolute()
    destination.mkdir(parents=True, exist_ok=False)
    protect_directory(destination)
    connection = store.engine.connect()
    if not store.sqlite:
        connection = connection.execution_options(isolation_level="REPEATABLE READ")
    files = {}
    with connection as conn, conn.begin():
        version = conn.execute(select(versions.c.version).where(versions.c.id == 1)).scalar_one()
        if version != SCHEMA_VERSION: raise ValueError("Migrate the source before exporting its registry")
        for name, table in TABLES.items():
            path = destination / (name + ".jsonl")
            count = 0
            with path.open("x", encoding="utf-8", newline="\n") as output:
                cursor = conn.execute(select(table).order_by(*table.primary_key.columns)).mappings()
                for row in cursor:
                    line = json.dumps({k: {"base64": base64.b64encode(v).decode("ascii")} if isinstance(v, bytes) else v for k, v in row.items()}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if len(line.encode("utf-8")) > MAX_LINE - 1:
                        raise ValueError("A registry row exceeds the transfer budget")
                    output.write(line + "\n");count += 1
            files[name] = {"file": path.name, "rows": count, "bytes": path.stat().st_size, "digest": checksum(path)}
    manifest = {"format": FORMAT, "schema": SCHEMA_VERSION, "created_at": now(), "source_backend": store.engine.dialect.name,
                "tables": files, "plaintext_credentials_included": False}
    if access_policy is not None:
        AccessPolicy(access_policy)
        policy_file = destination / "access-policy.json"
        write_private(policy_file, access_policy)
        if policy_file.stat().st_size > 65536: raise ValueError("Access policy exceeds 64 KiB")
        manifest["access_policy"] = {"file": policy_file.name, "digest": checksum(policy_file), "bytes": policy_file.stat().st_size}
    write_private(destination / "manifest.json", manifest)
    return {"status": "PASS", "directory": str(destination.resolve()), "manifest_digest": artifact_digest(manifest),
            "tables": {name: item["rows"] for name, item in files.items()}, "plaintext_credentials_included": False}


def rows(file, table, expected):
    checksum_state, byte_count = hashlib.sha256(), 0
    columns = {c.name: c for c in table.columns}
    with file.open("rb") as stream:
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line: break
            checksum_state.update(line);byte_count += len(line)
            if len(line) > MAX_LINE: raise ValueError("Transfer row exceeds 4 MiB")
            value = json.loads(line.decode("utf-8"), object_pairs_hook=pairs)
            check_tree(value)
            if not isinstance(value, dict) or set(value) != set(columns): raise ValueError("Unexpected registry columns")
            for name, column in columns.items():
                item = value[name]
                if item is None and column.nullable: continue
                if column.type.python_type is bytes:
                    if not isinstance(item, dict) or set(item) != {"base64"} or not isinstance(item["base64"], str):
                        raise ValueError("Invalid binary registry column")
                    try: decoded = base64.b64decode(item["base64"], validate=True)
                    except (ValueError, binascii.Error): raise ValueError("Invalid binary registry encoding") from None
                    if base64.b64encode(decoded).decode("ascii") != item["base64"]:
                        raise ValueError("Noncanonical binary registry encoding")
                    value[name] = item = decoded
                if type(item) is not column.type.python_type: raise ValueError("Invalid registry column type")
                if isinstance(item, str) and getattr(column.type, "length", None) and len(item) > column.type.length:
                    raise ValueError("Registry column exceeds its declared bound")
            yield value
    if byte_count != expected["bytes"] or "sha256:" + checksum_state.hexdigest() != expected["digest"]:
        raise ValueError("Registry transfer changed while being imported")


def verify_import(store, conn, source_schema=SCHEMA_VERSION):
    version_rows = conn.execute(select(versions)).mappings().all()
    if len(version_rows) != 1 or dict(version_rows[0]) != {"id": 1, "version": source_schema}:
        raise ValueError("Imported schema metadata is invalid")
    baseline_refs = []
    query = select(revisions, identities.c.namespace, identities.c.type).join(identities, identities.c.id == revisions.c.id)
    for row in conn.execute(query).mappings():
        obj = json.loads(row["payload"], object_pairs_hook=pairs)
        report = validate(obj)
        if not report["valid"] or not isinstance(obj, dict): raise InvalidModel("Invalid imported object", report)
        meta = obj["meta"]
        if (meta["id"], meta["revision"], meta["namespace"], meta["type"]) != (row["id"], row["revision"], row["namespace"], row["type"]):
            raise ValueError("Imported identity metadata disagrees with its revision")
        if row["digest"] != digest(obj): raise ValueError("Imported revision digest mismatch")
        if meta["type"] == "air.Baseline": baseline_refs.append({"id": meta["id"], "revision": meta["revision"]})
    for ref in baseline_refs:
        exported = store._export(conn, ref)
        for parent in exported["baseline"]["body"]["parent_baselines"]:
            store._required(conn, parent, "air.Baseline")
    for row in conn.execute(select(service_records)).mappings():
        payload = json.loads(row["payload"], object_pairs_hook=pairs)
        check_tree(payload)
        if artifact_digest({"kind": row["kind"], "scope": row["scope"], "actor": row["actor"], "payload": payload}) != row["request_digest"]:
            raise ValueError("Imported service record digest mismatch")
    from air.jobs import verify_heads
    verify_heads(store, conn)
    from air.authority import verify_projection
    verify_projection(store, conn)
    from air.runtime import verify_ingestions
    verify_ingestions(store, conn)
    from air.collaboration import verify_submissions
    verify_submissions(store, conn)
    from air.artifacts import verify_artifacts
    verify_artifacts(store, conn)
    from air.view_capture import verify_views
    verify_views(store, conn)
    return len(baseline_refs)


def import_registry(bundle, target_url):
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"), object_pairs_hook=pairs)
    source_schema = manifest.get("schema")
    schema_five_tables = set(TABLES) - {table.name for table in ARTIFACT_TABLES}
    schema_four_tables = schema_five_tables - {table.name for table in RENEWAL_TABLES}
    legacy_tables = schema_four_tables - {table.name for table in AUTHORITY_TABLES}
    source_tables = set(TABLES) if source_schema == SCHEMA_VERSION else schema_five_tables if source_schema == 5 else schema_four_tables if source_schema == 4 else legacy_tables if source_schema == 3 else legacy_tables - {"job_state"} if source_schema == 2 else set()
    if manifest.get("format") != FORMAT or not source_tables or set(manifest.get("tables", {})) != source_tables:
        raise ValueError("Unsupported registry transfer manifest")
    for name in sorted(source_tables):
        item = manifest["tables"][name]
        if item.get("file") != name + ".jsonl": raise ValueError("Unexpected transfer filename")
        path = bundle / item["file"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item.get("bytes") or checksum(path) != item.get("digest"):
            raise ValueError("Registry transfer checksum mismatch")
        if type(item.get("rows")) is not int or item["rows"] < 0: raise ValueError("Invalid row count")
    if not target_url.startswith(("sqlite:///", "postgresql+psycopg://")):
        raise ValueError("Registry target must use SQLite or PostgreSQL/psycopg")
    store = Store(target_url)
    try:
        if inspect(store.engine).get_table_names():
            raise ValueError("Registry import requires an empty target database; no existing table is overwritten")
        counts = {}
        with store.write() as conn:
            metadata.create_all(conn, checkfirst=False)
            for name, table in TABLES.items():
                if name not in source_tables:
                    counts[name] = 0
                    continue
                count, batch = 0, []
                for row in rows(bundle / manifest["tables"][name]["file"], table, manifest["tables"][name]):
                    batch.append(row);count += 1
                    if len(batch) == 256:
                        conn.execute(table.insert(), batch);batch.clear()
                if batch: conn.execute(table.insert(), batch)
                if count != manifest["tables"][name]["rows"]: raise ValueError("Registry transfer row count mismatch")
                counts[name] = count
            baselines = verify_import(store, conn, source_schema)
            if source_schema != SCHEMA_VERSION:
                conn.execute(update(versions).where(versions.c.id == 1).values(version=SCHEMA_VERSION))
            conn.execute(update(tokens).values(revoked=1))
            store.audit(conn, "local-operator", "registry.imported", artifact_digest(manifest))
        return {"status": "PASS", "backend": store.engine.dialect.name, "schema": SCHEMA_VERSION, "source_schema": source_schema,
            "tables_preserved": counts, "closed_baselines_verified": baselines, "old_tokens_revoked": True,
            "authority_revalidation_required": True, "manifest_digest": artifact_digest(manifest)}
    finally: store.engine.dispose()


def import_home(bundle, home, target_url=None):
    """Prepare a new home; the target PostgreSQL database must already be empty."""
    if os.environ.get("AIR_DATABASE_URL"):
        raise ValueError("Unset AIR_DATABASE_URL for import; supply a separate target environment variable")
    home = home.absolute()
    if home.exists() or home.is_symlink(): raise ValueError("Registry import requires a new AIR home")
    if target_url is not None and not target_url.startswith("postgresql+psycopg://"):
        raise ValueError("An external import target must use PostgreSQL/psycopg")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"), object_pairs_hook=pairs)
    policy = None
    if "access_policy" in manifest:
        item = manifest["access_policy"]
        file = bundle / "access-policy.json"
        if item.get("file") != file.name or file.is_symlink() or file.stat().st_size != item.get("bytes") or file.stat().st_size > 65536 or checksum(file) != item.get("digest"):
            raise ValueError("Registry policy checksum mismatch")
        policy = AccessPolicy.load(bundle).document
    pending = home.with_name(home.name + ".pending-" + uuid.uuid4().hex)
    pending.mkdir(parents=True, exist_ok=False)
    protect_directory(pending)
    url = target_url or "sqlite:///" + (pending / "air.db").as_posix()
    result = import_registry(bundle, url)
    instance_id = str(uuid.uuid4())
    config = {"config_version": 1, "instance_id": instance_id, "auth": {"mode": "local"},
              "database_backend": "postgresql" if target_url else "sqlite"}
    write_private(pending / "config.json", config)
    if policy is not None:
        policy["version"] = "import-" + instance_id
        write_private(pending / "access-policy.json", policy)
    store = Store(url)
    try:
        from air.authority import sync_policy
        sync_policy(store, AccessPolicy.load(pending), only_if_missing=True)
        write_private(pending / "credentials.json", store.create_token("local-admin", "admin"))
    finally: store.engine.dispose()
    pending.rename(home)
    return {**result, "home": str(home.resolve()), "credentials_file": str(home.resolve() / "credentials.json"),
            "runtime_database_environment": "AIR_DATABASE_URL" if target_url else None}
