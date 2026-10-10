"""Explicit namespace grants, reloaded for each authenticated request."""
from pathlib import Path
from air.core import record, reference_slots
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, key
from air.parsing import parse

ACTIONS = ("read", "write", "review", "publish", "admit", "activate", "capacity", "attest", "operate", "receive")
NAMESPACES = {"type": "array", "items": {"type": "string", "pattern": "^(?:\\*|[a-z][a-z0-9_.-]{0,127})$"},
              "maxItems": 256, "uniqueItems": True}
POLICY = record({"version": {"type": "string", "minLength": 1, "maxLength": 128},
                 "subjects": {"type": "object", "maxProperties": 1000,
                              "additionalProperties": record({**{action: NAMESPACES for action in ACTIONS},
                                  'builder_roles': {'type': 'array', 'maxItems': 128, 'uniqueItems': True,
                                      'items': record({'id': {'type': 'string', 'format': 'uri'},
                                          'revision': {'type': 'integer', 'minimum': 1},
                                          'digest': {'type': 'string', 'pattern': '^sha256:[a-f0-9]{64}$'}})}}, [])}})


class Forbidden(ValueError):
    def __init__(self, message, unavailable=None):
        super().__init__(message)
        # Echo of references the caller supplied: no existence is disclosed beyond their own request.
        self.unavailable = unavailable or []


class NotFound(ValueError):
    """An exact revision that does not exist. Carries the latest revision only when the caller may read its namespace."""
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail or {}


class PolicyUnavailable(ValueError):
    pass


class AccessPolicy:
    def __init__(self, document=None):
        self.document = document
        self.digest = artifact_digest(document if document is not None else {"policy": "local-role-default/1"})
        if document is not None:
            check_schema(document, POLICY)

    @classmethod
    def load(cls, home):
        path = Path(home) / "access-policy.json"
        try:
            with path.open("rb") as stream:
                raw = stream.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Policy exceeds 64 KiB")
                return cls(parse(raw))
        except FileNotFoundError:
            return cls()
        except (ValueError, OSError) as exc:
            raise PolicyUnavailable("Access policy is invalid or unavailable") from exc

    def allows(self, principal, action, namespace):
        role = principal["role"]
        if action != "read" and role not in ("editor", "admin"):
            return False
        if self.document is None:
            # Explicit business authority is always needed for approval and commitment.
            return action in ("read", "write") or action == 'operate' and role == 'admin'
        grants = self.document["subjects"].get(principal["subject"], {}).get(action, [])
        return "*" in grants or namespace in grants

    def require(self, principal, action, namespace):
        if not self.allows(principal, action, namespace):
            raise Forbidden("Operation is outside the authenticated subject's permitted scope")


class ScopedStore:
    """No fallback delegation: every exposed read/write must pass the same policy."""
    def __init__(self, store, principal, policy):
        self.store, self.principal, self.policy = store, principal, policy

    def allow(self, obj, action):
        self.policy.require(self.principal, action, obj["meta"]["namespace"])

    def check_read(self, refs):
        pending = list(refs)
        roots = {key(r) for r in refs}
        visited = set()
        unavailable = []
        while pending:
            ref = pending.pop()
            identity = key(ref)
            if identity in visited:
                continue
            visited.add(identity)
            if len(visited) > 4096:
                raise InvalidModel("Authorization closure exceeds 4096 references")
            row = self.store.get(*identity)
            if row is None:
                if identity in roots:
                    unavailable.append({"id": identity[0], "revision": identity[1]})
                continue  # Drafts may contain unresolved links; closure is a separate check.
            obj = row["object"]
            self.allow(obj, "read")
            pending.extend(r for _, r, _ in reference_slots(obj))
        if unavailable:
            raise Forbidden("Requested context is unavailable in the permitted scope", sorted(unavailable, key=lambda r: (r["id"], r["revision"])))

    def get(self, object_id, revision):
        row = self.store.get(object_id, revision)
        if row is None:
            return None
        self.check_read([{"id": object_id, "revision": revision}])
        return row

    def missing(self, object_id, revision):
        """The same answer for every tool: 404, plus the latest revision when the namespace is readable."""
        head = self.store.head(object_id)
        detail = {"id": object_id, "revision": revision}
        if head and self.policy.allows(self.principal, "read", head["namespace"]):
            detail.update(type=head["type"], latest_revision=head["latest_revision"])
        return NotFound("Exact revision does not exist", detail)

    def export_baseline(self, ref):
        if self.store.get(ref["id"], ref["revision"]) is None:
            raise self.missing(ref["id"], ref["revision"])
        self.check_read([ref])
        return self.store.export_baseline(ref)

    def put(self, obj, subject):
        self.allow(obj, "write")
        return self.store.put(obj, subject)

    def put_bundle(self, objects, subject):
        from air.core import validate
        report = validate(objects)
        if not isinstance(objects, list) or not report["valid"]:
            raise InvalidModel("Invalid draft bundle", report)
        from air.core import digest
        for obj in objects:
            stored = self.store.get(obj["meta"]["id"], obj["meta"]["revision"])
            # Carrying another project's exact revision, already stored identical, writes nothing: reading it is enough.
            self.allow(obj, "read" if stored is not None and stored["digest"] == digest(obj) else "write")
        return self.store.put_bundle(objects, subject)

    def create_baseline(self, request, subject):
        from air.foundation import BASELINE_REQUEST
        check_schema(request, BASELINE_REQUEST)
        self.policy.require(self.principal, "write", request["meta"]["namespace"])
        self.check_read(request["members"] + request["parent_baselines"])
        return self.store.create_baseline(request, subject)

    def propose_change(self, request, subject):
        from air.core import validate
        report = validate(request)
        if not isinstance(request, dict) or not report["valid"] or request["meta"]["type"] != "air.ChangeSet":
            raise InvalidModel("Invalid ChangeSet", report)
        self.allow(request, "write")
        self.check_read([r for _, r, _ in reference_slots(request)])
        return self.store.propose_change(request, subject)

    def audit_log(self):
        if self.principal["role"] != "admin" or not self.policy.allows(self.principal, "read", "*"):
            raise Forbidden("Global audit requires an administrator with global read scope")
        return self.store.audit_log()
