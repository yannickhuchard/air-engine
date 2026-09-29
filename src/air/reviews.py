"""Authenticated, scoped and revocable review receipts; no implicit publication."""
from datetime import datetime, timezone, timedelta
import hashlib
from air.access import ScopedStore, Forbidden
from air.core import REF, TEXT, INSTANT, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict

REQUEST = record({"idempotency_key": {"type": "string", "minLength": 1, "maxLength": 128},
    "baseline": SNAPSHOT, "target": SNAPSHOT, "outcome": {"enum": ["ACCEPTED", "REJECTED"]},
    "rationale": TEXT, "evidence": {"type": "array", "items": SNAPSHOT, "minItems": 1, "maxItems": 64, "uniqueItems": True},
    "expires_at": INSTANT})
from air.proofs import ASSESSMENTS
REQUEST['properties']['proof_assessments'] = ASSESSMENTS


def record_key(kind, actor, idempotency_key):
    return "urn:air:" + kind + ":" + hashlib.sha256((actor + "\0" + idempotency_key).encode()).hexdigest()


def create_review(store, principal, policy, request, settings=None):
    check_schema(request, REQUEST)
    guarded = ScopedStore(store, principal, policy)
    baseline = snapshot(guarded, request["baseline"])
    target = guarded.get(request["target"]["id"], request["target"]["revision"])
    if target is None or target["digest"] != request["target"]["digest"]:
        raise Conflict("Review target digest does not match")
    obj = target["object"]
    if obj["meta"]["type"] not in ("air.Assertion", "air.Baseline", "air.SemanticContract", "air.Requirement"):
        raise InvalidModel("Unsupported review target type")
    scope = obj["meta"]["namespace"]
    policy.require(principal, "review", scope)
    if key(request["target"]) not in {key(exact(o)) for o in baseline["objects"] + [baseline["baseline"]]}:
        raise InvalidModel("Target must belong to the exact review baseline")
    authors = [store.author(request["target"])]
    if obj["meta"]["type"] == "air.Baseline":
        authors.extend(store.author(exact(o)) for o in baseline["objects"])
    if None in authors:
        raise InvalidModel("Authenticated authorship is unavailable for this review scope")
    if principal["subject"] in authors:
        raise Forbidden("The author cannot approve their own content")
    for ref in request["evidence"]:
        row = guarded.get(ref["id"], ref["revision"])
        if row is None or row["digest"] != ref["digest"] or row["object"]["meta"]["type"] not in ("air.Evidence", "air.Source"):
            raise InvalidModel("Review requires readable exact Source/Evidence references")
    receipt_id = record_key("review", principal["subject"], request["idempotency_key"])
    payload = {"request": request, "policy_digest": policy.digest, "reviewer_role": principal["role"],
               "evidence_class": "AUTHENTICATED_REVIEW", "authorization_granted": False}
    if 'proof_assessments' in request:
        from air.proofs import assess
        payload['proof_qualifications'] = assess(store, principal, policy, baseline, request)
    existing = store.get_record(receipt_id)
    if existing is None:
        expiry = datetime.fromisoformat(request["expires_at"])
        now = datetime.now(timezone.utc)
        if not now < expiry <= now + timedelta(days=366):
            raise InvalidModel("Review expiry must be in the next 366 days")
    with store.write() as conn:
        if settings is not None:
            from air.packages import lock_registry
            from air.jobs import check_identity
            from air.access import AccessPolicy
            lock_registry(conn);check_identity(store, conn, principal, settings)
            if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Review policy changed before commit')
        return store._record_once(conn, receipt_id, "review", scope, principal["subject"], payload)


def read_review(store, principal, policy, receipt_id):
    receipt = store.get_record(receipt_id)
    if receipt is None or receipt["kind"] != "review":
        raise InvalidModel("Review receipt is unavailable")
    policy.require(principal, "read", receipt["scope"])
    payload = receipt["payload"]
    guarded = ScopedStore(store, principal, policy)
    guarded.check_read([payload["request"]["baseline"], payload["request"]["target"], *payload["request"]["evidence"]])
    expiry = datetime.fromisoformat(payload["request"]["expires_at"])
    revoked = store.get_record("urn:air:revoked:" + hashlib.sha256(receipt_id.encode()).hexdigest()) is not None
    reasons = []
    if revoked: reasons.append("REVOKED")
    if expiry <= datetime.now(timezone.utc): reasons.append("EXPIRED")
    if payload["policy_digest"] != policy.digest: reasons.append("POLICY_CHANGED")
    reviewer = {"subject": receipt["actor"], "role": payload["reviewer_role"]}
    if not policy.allows(reviewer, "review", receipt["scope"]): reasons.append("MANDATE_MISSING")
    qualifications = []
    if 'proof_assessments' in payload['request'] and not reasons:
        from air.proofs import assess
        try:
            exported = snapshot(guarded, payload['request']['baseline'])
            qualifications = assess(store, principal, policy, exported, payload['request'])
            if qualifications != payload.get('proof_qualifications'):
                reasons.append('PROOF_BINDING_CHANGED');qualifications = []
        except (InvalidModel, Forbidden, Conflict):
            reasons.append('PROOF_UNAVAILABLE');qualifications = []
    return {"record": receipt, "effective": not reasons, "ineffective_reasons": reasons,
            "authorization_granted": False, "outcome": payload["request"]["outcome"], 'proof_qualifications': qualifications}


def revoke_review(store, principal, policy, request, settings=None):
    check_schema(request, record({"review_id": {"type": "string", "maxLength": 128}, "rationale": TEXT}))
    current = read_review(store, principal, policy, request["review_id"])
    policy.require(principal, "review", current["record"]["scope"])
    record_id = "urn:air:revoked:" + hashlib.sha256(request["review_id"].encode()).hexdigest()
    with store.write() as conn:
        if settings is not None:
            from air.packages import lock_registry
            from air.jobs import check_identity
            from air.access import AccessPolicy
            lock_registry(conn);check_identity(store, conn, principal, settings)
            if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Review policy changed before revocation')
        return store._record_once(conn, record_id, "review_revocation", current["record"]["scope"], principal["subject"], request)
