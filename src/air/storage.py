"""Portable SQL registry. SQLite and PostgreSQL share the same write invariants."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
import uuid
from sqlalchemy import (Column, Integer, BigInteger, String, Text, LargeBinary, Table, MetaData, ForeignKey, Index, CheckConstraint,
                        create_engine, event, select, update, func)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from air.core import canonical, digest, validate
from air.foundation import (BASELINE_REQUEST, InvalidModel, apply_change, build_baseline,
                            check_schema, exact, key, lock_document, lock_reference, resolved, validate_graph)

metadata = MetaData()
versions = Table("schema_version", metadata, Column("id", Integer, primary_key=True), Column("version", Integer, nullable=False))
identities = Table("object_identity", metadata, Column("id", String(512), primary_key=True),
                   Column("namespace", String(128), nullable=False), Column("type", String(100), nullable=False))
revisions = Table("object_revision", metadata,
                  Column("id", String(512), ForeignKey("object_identity.id"), primary_key=True),
                  Column("revision", Integer, primary_key=True), Column("digest", String(71), nullable=False),
                  Column("payload", Text, nullable=False), Column("stored_at", String(40), nullable=False))
tokens = Table("access_token", metadata, Column("id", String(36), primary_key=True),
               Column("token_hash", String(64), nullable=False, unique=True),
               Column("subject", String(256), nullable=False), Column("role", String(16), nullable=False),
               Column("expires_at", Integer, nullable=False), Column("revoked", Integer, nullable=False))
audits = Table("audit_event", metadata, Column("id", String(36), primary_key=True),
               Column("at", String(40), nullable=False), Column("subject", String(256), nullable=False),
               Column("action", String(64), nullable=False), Column("target", String(550), nullable=False))
service_records = Table("service_record", metadata,
    Column("id", String(128), primary_key=True), Column("kind", String(32), nullable=False, index=True),
    Column("scope", String(128), nullable=False), Column("actor", String(256), nullable=False),
    Column("request_digest", String(71), nullable=False), Column("payload", Text, nullable=False),
    Column("created_at", String(40), nullable=False))
job_heads = Table("job_state", metadata,
    Column("id", String(128), ForeignKey("service_record.id"), primary_key=True),
    Column("status", String(16), nullable=False), Column("attempt", Integer, nullable=False),
    Column("lease_until", BigInteger), Column("claim_id", String(128)),
    Column("result_id", String(128), ForeignKey("service_record.id")),
    Column("created_epoch", BigInteger, nullable=False),
    CheckConstraint("status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')", name="job_status_allowed"),
    CheckConstraint("attempt >= 0 AND attempt <= 3", name="job_attempt_bound"))
Index("ix_job_ready", job_heads.c.status, job_heads.c.lease_until, job_heads.c.created_epoch)
authority_policies = Table("authority_policy", metadata,
    Column("id", Integer, primary_key=True), Column("generation", Integer, nullable=False),
    Column("digest", String(71), nullable=False), Column("payload", Text, nullable=False),
    Column("actor", String(256), nullable=False), Column("updated_at", String(40), nullable=False),
    CheckConstraint("id = 1", name="authority_singleton"))
capacity_heads = Table("capacity_pool", metadata,
    Column("id", String(512), primary_key=True), Column("namespace", String(128), nullable=False),
    Column("offer_id", String(128), ForeignKey("service_record.id"), nullable=False),
    Column("generation", Integer, nullable=False), Column("week_anchor", Integer, nullable=False))
resource_bindings = Table("capacity_resource", metadata,
    Column("id", String(512), primary_key=True),
    Column("pool_id", String(512), ForeignKey("capacity_pool.id"), nullable=False, index=True))
reservations = Table("capacity_reservation", metadata,
    Column("id", String(128), primary_key=True),
    Column("admission_id", String(128), ForeignKey("service_record.id"), nullable=False, index=True),
    Column("pool_id", String(512), ForeignKey("capacity_pool.id"), nullable=False),
    Column("unit_id", String(512), nullable=False), Column("unit_revision", Integer, nullable=False),
    Column("period_start", BigInteger, nullable=False), Column("period_end", BigInteger, nullable=False),
    Column("micro_fte", BigInteger, nullable=False), Column("released", Integer, nullable=False),
    CheckConstraint("micro_fte >= 0 AND period_end > period_start AND released IN (0,1)", name="reservation_values"))
Index("ix_capacity_reserved_period", reservations.c.pool_id, reservations.c.released, reservations.c.period_start, reservations.c.period_end)
activation_heads = Table("activation_episode", metadata,
    Column("id", String(128), ForeignKey("service_record.id"), primary_key=True),
    Column("admission_id", String(128), ForeignKey("service_record.id"), nullable=False, index=True),
    Column("unit_id", String(512), nullable=False), Column("unit_revision", Integer, nullable=False))
AUTHORITY_TABLES = (authority_policies, capacity_heads, resource_bindings, reservations, activation_heads)
authorization_heads = Table("admission_authorization", metadata,
    Column("admission_id", String(128), ForeignKey("service_record.id"), primary_key=True),
    Column("generation", Integer, nullable=False),
    Column("receipt_id", String(128), ForeignKey("service_record.id"), nullable=False),
    CheckConstraint("generation > 0", name="authorization_generation_positive"))
RENEWAL_TABLES = (authorization_heads,)
artifact_blobs = Table("artifact_blob", metadata,
    Column("digest", String(64), primary_key=True),
    Column("size", Integer, nullable=False), Column("chunks", Integer, nullable=False),
    CheckConstraint("length(digest) = 64 AND size > 0 AND size <= 16777216 AND chunks > 0 AND chunks <= 64", name="artifact_blob_bounds"))
artifact_chunks = Table("artifact_chunk", metadata,
    Column("digest", String(64), ForeignKey("artifact_blob.digest"), primary_key=True),
    Column("ordinal", Integer, primary_key=True), Column("payload", LargeBinary, nullable=False),
    CheckConstraint("ordinal >= 0 AND ordinal < 64 AND length(payload) > 0 AND length(payload) <= 262144", name="artifact_chunk_bounds"))
ARTIFACT_TABLES = (artifact_blobs, artifact_chunks)
SCHEMA_VERSION = 6


class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, url):
        from air.quotas import limits
        limits()
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        self.sqlite = self.engine.dialect.name == "sqlite"
        if self.sqlite:
            @event.listens_for(self.engine, "connect")
            def setup(connection, _):
                connection.isolation_level = None
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")

            @event.listens_for(self.engine, "begin")
            def begin(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE" if connection.get_execution_options().get("air_write") else "BEGIN")

    @contextmanager
    def write(self):
        with self.engine.connect().execution_options(air_write=True) as conn:
            with conn.begin():
                # Acquire before any row lock, including before initial migration.
                if not self.sqlite:
                    conn.execute(select(func.set_config('lock_timeout','10000',True)))
                    conn.execute(select(func.pg_advisory_xact_lock(1095324241)))
                from air.request_authority import guard_write
                guard_write(self, conn)
                yield conn
                guard_write(self, conn)

    def insert_once(self, conn, table, values, keys):
        if table is revisions:
            prior = conn.execute(select(revisions.c.id).where(revisions.c.id == values['id'], revisions.c.revision == values['revision'])).first()
            if prior is None:
                from air.quotas import revision
                namespace = conn.execute(select(identities.c.namespace).where(identities.c.id == values['id'])).scalar_one()
                revision(conn, namespace)
        stmt = (sqlite_insert if self.sqlite else pg_insert)(table).values(**values)
        statement = stmt.on_conflict_do_nothing(index_elements=keys)
        if self.sqlite:
            return conn.execute(statement).rowcount == 1
        # psycopg may expose rowcount=-1; RETURNING is the insertion witness.
        return conn.execute(statement.returning(table.c[keys[0]])).first() is not None

    def migrate(self):
        from sqlalchemy import inspect
        if inspect(self.engine).has_table("schema_version"):
            with self.write() as conn:
                version = conn.execute(select(versions.c.version).where(versions.c.id == 1).with_for_update()).scalar_one()
                if version not in (1, 2, 3, 4, 5, SCHEMA_VERSION):
                    raise ValueError("Unsupported database schema; migrate with a compatible AIR version")
                if version == 1:
                    service_records.create(conn, checkfirst=True)
                if version in (1, 2):
                    job_heads.create(conn, checkfirst=True)
                if version in (1, 2, 3):
                    for table in AUTHORITY_TABLES:
                        table.create(conn, checkfirst=True)
                if version in (1, 2, 3, 4):
                    authorization_heads.create(conn, checkfirst=True)
                if version in (1, 2, 3, 4, 5):
                    for table in ARTIFACT_TABLES:
                        table.create(conn, checkfirst=True)
                    conn.execute(update(versions).where(versions.c.id == 1).values(version=SCHEMA_VERSION))
            return
        with self.write() as conn:
            metadata.create_all(conn)
            self.insert_once(conn, versions, dict(id=1, version=SCHEMA_VERSION), ["id"])

    def check_version(self):
        with self.engine.connect() as conn:
            value = conn.execute(select(versions.c.version).where(versions.c.id == 1)).scalar_one()
            if value != SCHEMA_VERSION:
                raise ValueError("Unsupported database schema; migrate with a compatible AIR version")

    def _record_once(self, conn, record_id, kind, scope, actor, payload):
        from air.expr import artifact_digest
        checksum = artifact_digest({"kind": kind, "scope": scope, "actor": actor, "payload": payload})
        if self._get_record(conn, record_id) is None:
            from air.quotas import record
            record(conn, scope, kind, payload)
        created = self.insert_once(conn, service_records, dict(id=record_id, kind=kind, scope=scope,
            actor=actor, request_digest=checksum, payload=json.dumps(payload, ensure_ascii=False, sort_keys=True), created_at=now()), ["id"])
        row = self._get_record(conn, record_id)
        if row["request_digest"] != checksum:
            raise Conflict("Idempotency key already used for different content")
        if created:
            self.audit(conn, actor, kind + ".recorded", record_id)
        return {"record": row, "created": created}

    def record_once(self, record_id, kind, scope, actor, payload):
        with self.write() as conn:
            return self._record_once(conn, record_id, kind, scope, actor, payload)

    def _get_record(self, conn, record_id):
        row = conn.execute(select(service_records).where(service_records.c.id == record_id)).mappings().first()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        from air.expr import artifact_digest
        if artifact_digest({k: result[k] for k in ("kind", "scope", "actor", "payload")}) != result["request_digest"]:
            raise InvalidModel("Service record integrity check failed")
        return result

    def get_record(self, record_id):
        with self.engine.connect() as conn:
            return self._get_record(conn, record_id)

    def author(self, ref):
        with self.engine.connect() as conn:
            return conn.execute(select(audits.c.subject).where(
                audits.c.target == f"{ref['id']}@{ref['revision']}",
                audits.c.action.in_(["draft.stored", "baseline.frozen", "change.proposed"]))).scalar_one_or_none()

    def audit(self, conn, subject, action, target):
        conn.execute(audits.insert().values(id=str(uuid.uuid4()), at=now(), subject=subject, action=action, target=target))

    def put(self, obj, subject):
        report = validate(obj)
        if not report["valid"] or not isinstance(obj, dict):
            raise ValueError("Invalid bootstrap object")
        if obj["meta"]["type"] in ("air.Baseline", "air.ChangeSet", "air.View"):
            raise InvalidModel("Use the baseline, ChangeSet or View capture service; direct writes are forbidden")
        with self.write() as conn:
            return self._put(conn, obj, subject)

    def _put(self, conn, obj, subject):
        meta = obj["meta"]
        content_digest = digest(obj)
        self.insert_once(conn, identities, {k: meta[k] for k in ("id", "namespace", "type")}, ["id"])
        identity = conn.execute(select(identities).where(identities.c.id == meta["id"])).mappings().one()
        if identity["namespace"] != meta["namespace"] or identity["type"] != meta["type"]:
            raise Conflict("Identity cannot change namespace or type")
        created = self.insert_once(conn, revisions, dict(id=meta["id"], revision=meta["revision"],
                                   digest=content_digest, payload=canonical(obj).decode(), stored_at=now()), ["id", "revision"])
        stored_digest = conn.execute(select(revisions.c.digest).where(revisions.c.id == meta["id"], revisions.c.revision == meta["revision"])).scalar_one()
        if stored_digest != content_digest:
            raise Conflict("Revision already exists with different content")
        if created:
            action = {"air.Baseline": "baseline.frozen", "air.ChangeSet": "change.proposed"}.get(meta["type"], "draft.stored")
            self.audit(conn, subject, action, f"{meta['id']}@{meta['revision']}")
        return {"id": meta["id"], "revision": meta["revision"], "digest": content_digest, "created": created}

    def put_bundle(self, objects, subject):
        report = validate(objects)
        if not isinstance(objects, list) or not report["valid"]:
            raise InvalidModel("Invalid draft bundle", report)
        if any(obj["meta"]["type"] in ("air.Baseline", "air.ChangeSet", "air.View") for obj in objects):
            raise InvalidModel("Draft bundles cannot bypass snapshot/change services")
        with self.write() as conn:
            return {"objects": [self._put(conn, obj, subject) for obj in sorted(objects, key=lambda o: key(exact(o)))],
                    "closed": False, "note": "Draft import; freeze a baseline (air_freeze_baseline, CLI baseline-create) to enforce closure"}

    def _required(self, conn, ref, kind=None):
        row = conn.execute(select(revisions).where(revisions.c.id == ref["id"], revisions.c.revision == ref["revision"])).mappings().first()
        if row is None:
            raise InvalidModel("Required revision does not exist", {"diagnostics": [
                {"code": "AIR_REFERENCE_MISSING", "target": {"id": ref["id"], "revision": ref["revision"]}}]})
        obj = json.loads(row["payload"])
        if digest(obj) != row["digest"] or (ref.get("digest") and ref["digest"] != row["digest"]):
            raise InvalidModel("Stored or requested content digest does not match")
        if (kind and obj["meta"]["type"] != kind) or (ref.get("type") and ref["type"] != obj["meta"]["type"]):
            raise InvalidModel("Reference target type mismatch")
        return obj

    def _baseline(self, conn, request, subject):
        check_schema(request, BASELINE_REQUEST)
        objects = [self._required(conn, ref) for ref in request["members"]]
        for parent in request["parent_baselines"]:
            self._required(conn, parent, "air.Baseline")
            if parent["id"] == request["meta"]["id"] and parent["revision"] >= request["meta"]["revision"]:
                raise InvalidModel("Parent revision must precede its successor")
        baseline, report = build_baseline(request, objects)
        receipt = self._put(conn, baseline, subject)
        return {**receipt, "baseline": baseline, "validation": report, "published": False}

    def create_baseline(self, request, subject):
        with self.write() as conn:
            return self._baseline(conn, request, subject)

    def _export(self, conn, ref):
        baseline = self._required(conn, ref, "air.Baseline")
        report = validate(baseline)
        if not report["valid"]:
            raise InvalidModel("Invalid stored baseline", report)
        objects = [self._required(conn, member) for member in baseline["body"]["members"]]
        profile = baseline["body"]["profiles"][0]
        if baseline["body"]["dependency_lock"] != lock_reference(baseline["body"]["members"], profile):
            raise InvalidModel("Dependency lock does not match manifest")
        validation = validate_graph(objects, profile)
        if not validation["valid"]:
            raise InvalidModel("Stored baseline fails closure", validation)
        return {"baseline": baseline, "digest": digest(baseline), "objects": objects,
                "dependency_lock": lock_document(baseline["body"]["members"], profile), "validation": validation,
                "validation_scope": {"checked": "Schema of each member and exact reference closure (AIR-V003) under " + profile,
                                     "not_checked": ["Construction traceability: air_validate_construction",
                                                     "Structural architecture checks: air_inspect_architecture"]}}

    def export_baseline(self, ref):
        with self.engine.connect() as conn:
            return self._export(conn, ref)

    def propose_change(self, request, subject):
        change = request
        report = validate(change)
        if not report["valid"] or not isinstance(change, dict) or change["meta"]["type"] != "air.ChangeSet":
            raise InvalidModel("Invalid ChangeSet", report)
        # A proposal has one deterministic target, so retries cannot create extra snapshots.
        from copy import deepcopy
        target_meta = deepcopy(change["meta"])
        target_meta.update(id="urn:air:baseline:proposal:" + digest(change).split(":", 1)[1],
                           revision=1, type="air.Baseline", name="Proposal: " + change["meta"]["name"])
        with self.write() as conn:
            exported = self._export(conn, change["body"]["base"])
            base = exported["baseline"]
            if key(exact(base)) == key(target_meta):
                raise InvalidModel("A proposal must create a distinct baseline revision")
            members, diff = apply_change(base, change)
            objects = [self._required(conn, ref) for ref in members]
            if any(resolved(obj) != ref for obj, ref in zip(objects, members)):
                raise InvalidModel("Proposed member digest or type differs from storage")
            source_refs = {key(ref) for ref in change["meta"]["provenance"]["source_refs"]}
            sources = {key(exact(obj)) for obj in exported["objects"] + objects if obj["meta"]["type"] == "air.Source"}
            if not source_refs <= sources:
                raise InvalidModel("Change provenance must resolve to a Source in its base or target")
            target = self._baseline(conn, {"meta": target_meta, "profile": base["body"]["profiles"][0],
                "members": [exact(obj) for obj in objects], "parent_baselines": [exact(base)]}, subject)
            receipt = self._put(conn, change, subject)
            return {"change": receipt, "target": target, "diff": diff, "approved": False, "published": False}

    def head(self, object_id):
        """Identity, namespace, type and latest stored revision; None for an unknown identifier."""
        with self.engine.connect() as conn:
            identity = conn.execute(select(identities).where(identities.c.id == object_id)).mappings().first()
            if identity is None:
                return None
            latest = conn.execute(select(func.max(revisions.c.revision)).where(revisions.c.id == object_id)).scalar_one()
            return {"id": object_id, "namespace": identity["namespace"], "type": identity["type"], "latest_revision": latest}

    def revisions(self, object_id, limit=200):
        with self.engine.connect() as conn:
            rows = conn.execute(select(revisions.c.revision, revisions.c.digest, revisions.c.stored_at).where(revisions.c.id == object_id)
                                .order_by(revisions.c.revision.desc()).limit(limit)).mappings().all()
            total = conn.execute(select(func.count()).select_from(revisions).where(revisions.c.id == object_id)).scalar_one()
            return [dict(r) for r in rows], total

    def reviews_of(self, object_id, scope, limit=2000):
        """Authenticated review receipts whose exact target is a revision of this identifier, with their revocation state."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(service_records.c.id).where(service_records.c.kind == "review", service_records.c.scope == scope)
                                .order_by(service_records.c.id).limit(limit + 1)).scalars().all()
            if len(rows) > limit:
                from air.foundation import InvalidModel
                raise InvalidModel('Review receipt budget exceeded; acceptance cannot be determined from a partial catalogue')
            revoked = set(conn.execute(select(service_records.c.id).where(service_records.c.kind == "review_revocation",
                                                                       service_records.c.scope == scope).limit(limit)).scalars().all())
            found = []
            for record_id in rows:
                row = self._get_record(conn, record_id)
                target = row["payload"]["request"].get("target", {})
                if target.get("id") != object_id: continue
                import hashlib
                found.append({"receipt": record_id, "reviewer": row["actor"], "revision": target.get("revision"), "digest": target.get("digest"),
                              "recorded_at": row["created_at"], "expires_at": row["payload"]["request"].get("expires_at"),
                              "revoked": "urn:air:revoked:" + hashlib.sha256(record_id.encode()).hexdigest() in revoked})
            return found

    def identities_of(self, namespace, kind, limit=50):
        with self.engine.connect() as conn:
            return list(conn.execute(select(identities.c.id).where(identities.c.namespace == namespace, identities.c.type == kind)
                                     .order_by(identities.c.id).limit(limit)).scalars().all())

    def latest_revisions(self, object_ids):
        """Latest stored revision for many identifiers at once."""
        result = {}
        ids = sorted(set(object_ids))
        with self.engine.connect() as conn:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                for row in conn.execute(select(revisions.c.id, func.max(revisions.c.revision)).where(revisions.c.id.in_(chunk)).group_by(revisions.c.id)):
                    result[row[0]] = row[1]
        return result

    def get(self, object_id, revision):
        with self.engine.connect() as conn:
            row = conn.execute(select(revisions).where(revisions.c.id == object_id, revisions.c.revision == revision)).mappings().first()
            return {"object": json.loads(row["payload"]), "digest": row["digest"]} if row else None

    def create_token(self, subject, role, days=30):
        if role not in ("admin", "editor", "reader") or not subject or len(subject) > 256 or not 1 <= days <= 365:
            raise ValueError("Invalid token subject, role or lifetime (1..365 days)")
        raw = secrets.token_urlsafe(32)
        token_id = str(uuid.uuid4())
        expiry = int(time.time()) + days * 86400
        with self.write() as conn:
            conn.execute(tokens.insert().values(id=token_id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                        subject=subject, role=role, expires_at=expiry, revoked=0))
            self.audit(conn, "local-administrator", "token.created", token_id)
        return {"token_id": token_id, "access_token": raw, "subject": subject, "role": role, "expires_at": expiry}

    def authenticate(self, raw, include_binding=False):
        if len(raw) > 4096:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(select(tokens.c.subject, tokens.c.role, tokens.c.id, tokens.c.expires_at).where(
                tokens.c.token_hash == hashlib.sha256(raw.encode()).hexdigest(),
                tokens.c.revoked == 0, tokens.c.expires_at > int(time.time()))).mappings().first()
            if row is None: return None
            principal = {"subject": row["subject"], "role": row["role"]}
            if include_binding:
                principal["authorization"] = {"mode": "local", "token_id": row["id"], "expires_at": row["expires_at"]}
            return principal

    def revoke_token(self, token_id):
        with self.write() as conn:
            statement = update(tokens).where(tokens.c.id == token_id, tokens.c.revoked == 0).values(revoked=1)
            found = (conn.execute(statement).rowcount == 1 if self.sqlite
                     else conn.execute(statement.returning(tokens.c.id)).first() is not None)
            if found:
                self.audit(conn, "local-administrator", "token.revoked", token_id)
            return bool(found)

    def audit_log(self):
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(audits).order_by(audits.c.at.desc(), audits.c.id).limit(100)).mappings()]

    def counts(self):
        with self.engine.connect() as conn:
            return {"revisions": conn.execute(select(func.count()).select_from(revisions)).scalar_one()}
