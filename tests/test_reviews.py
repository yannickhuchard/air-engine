from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import pytest
from sqlalchemy import select, update
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.foundation import exact, InvalidModel
from air.reviews import create_review, read_review, revoke_review
from air.storage import Conflict, Store, service_records, versions, job_heads, AUTHORITY_TABLES, RENEWAL_TABLES
from test_construction import construction, prepare


def context(store, objects):
    base, request = prepare(store, objects)
    target = next(o for o in objects if o["meta"]["type"] == "air.SemanticContract")
    evidence = next(o for o in objects if o["meta"]["type"] == "air.Evidence")
    def ref(o): return {**exact(o), "digest": store.get(o["meta"]["id"], o["meta"]["revision"])["digest"]}
    principal = {"subject": "reviewer", "role": "editor"}
    policy = AccessPolicy({"version": "1", "subjects": {"reviewer": {"read": ["*"], "review": ["asteria.sav"]},
                                                         "architect": {"read": ["*"], "review": ["*"]}}})
    return principal, policy, {"idempotency_key": "review-1", "baseline": request["baseline"], "target": ref(target),
        "outcome": "ACCEPTED", "rationale": "Synthetic independent review of the contract specification, not execution evidence.",
        "evidence": [ref(evidence)], "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")}


def test_review_is_authenticated_scoped_and_idempotent(store, construction):
    principal, policy, request = context(store, construction)
    result = create_review(store, principal, policy, request)
    assert result["created"] and result["record"]["actor"] == "reviewer"
    assert not result["record"]["payload"]["authorization_granted"]
    assert not create_review(store, principal, policy, request)["created"]
    assert read_review(store, principal, policy, result["record"]["id"])["effective"]
    changed = deepcopy(request);changed["rationale"] += " changed"
    with pytest.raises(Conflict): create_review(store, principal, policy, changed)
    with pytest.raises(Forbidden): create_review(store, {"subject": "architect", "role": "admin"}, policy, request)
    with pytest.raises(Forbidden): create_review(store, principal, AccessPolicy(), request)
    bad = deepcopy(request);bad["approved"] = True
    with pytest.raises(InvalidModel): create_review(store, principal, policy, bad)


def test_policy_expiry_revocation_and_target_versions(store, construction):
    principal, policy, request = context(store, construction)
    result = create_review(store, principal, policy, request)
    receipt_id = result["record"]["id"]
    changed = deepcopy(policy.document);changed["version"] = "2"
    assert "POLICY_CHANGED" in read_review(store, principal, AccessPolicy(changed), receipt_id)["ineffective_reasons"]
    revoke_review(store, principal, policy, {"review_id": receipt_id, "rationale": "Synthetic revocation"})
    assert "REVOKED" in read_review(store, principal, policy, receipt_id)["ineffective_reasons"]
    stale = deepcopy(request);stale["idempotency_key"] = "expired"
    stale["expires_at"] = "2000-01-01T00:00:00Z"
    with pytest.raises(InvalidModel): create_review(store, principal, policy, stale)
    wrong = deepcopy(request);wrong["target"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(Conflict): create_review(store, principal, policy, wrong)


def test_concurrent_review_has_one_receipt_and_audit(store, construction):
    principal, policy, request = context(store, construction)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create_review(store, principal, policy, request), range(2)))
    assert sum(r["created"] for r in results) == 1
    assert results[0]["record"] == results[1]["record"]
    assert len([a for a in store.audit_log() if a["action"] == "review.recorded"]) == 1


def test_additive_migration_preserves_old_revisions(store, example):
    before = store.put(example, "owner")
    with store.write() as conn:
        for table in reversed((*AUTHORITY_TABLES, *RENEWAL_TABLES)): table.drop(conn)
        job_heads.drop(conn)
        service_records.drop(conn)
        conn.execute(update(versions).values(version=1))
    with pytest.raises(ValueError): store.check_version()
    store.migrate();store.migrate()
    store.check_version()
    assert store.get(example["meta"]["id"], 1)["digest"] == before["digest"]
    assert store.author(exact(example)) == "owner"


def test_review_api_has_no_self_declared_actor(store, construction, tmp_path):
    principal, policy, request = context(store, construction)
    (tmp_path / "access-policy.json").write_text(json.dumps(policy.document), encoding="utf-8")
    token = store.create_token("reviewer", "editor")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post("/v1/reviews", json=request).status_code == 401
        receipt = client.post("/v1/reviews", json=request, headers=headers)
        assert receipt.status_code == 200
        assert receipt.json()["record"]["actor"] == "reviewer"
        request["actor"] = "someone-else"
        assert client.post("/v1/reviews", json=request, headers=headers).status_code == 422
