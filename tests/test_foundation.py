from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import json
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, update
from air.api import create_app
from air.config import Settings
from air.core import FOUNDATION_PROFILE, canonical, digest, validate
from air.foundation import InvalidModel, exact, lock_document, lock_reference, resolved, validate_graph
from air.storage import Conflict, Store, revisions


def obj_like(example, kind, suffix, body):
    result = deepcopy(example)
    result["meta"].update(id="urn:air:test:" + suffix, type="air." + kind, name=kind + " " + suffix)
    result["body"] = body
    return result


@pytest.fixture
def knowledge(example):
    source = obj_like(example, "Source", "source", {"kind": "DOCUMENT", "locator": "urn:synthetic:brief",
        "captured_at": "2026-09-19T00:00:00Z", "access_policy": "test", "retention_policy": "test"})
    scope = deepcopy(example)
    scope["meta"]["provenance"]["source_refs"] = [exact(source)]
    assertion = obj_like(example, "Assertion", "assertion", {"statement": "Synthetic sourced claim",
        "subject_scope": exact(scope), "epistemic_status": "SUPPORTED", "evidence": [{"id": "urn:air:test:evidence", "revision": 1}]})
    evidence = obj_like(example, "Evidence", "evidence", {"source": exact(source), "selector": "section 1",
        "evidence_kind": "DOCUMENT_EXCERPT", "supports_or_refutes": [{**exact(assertion), "direction": "SUPPORTS"}],
        "limitations": ["Synthetic document, not a real observation"]})
    assumption = obj_like(example, "Assumption", "assumption", {"statement": "Availability is estimated",
        "used_by": [exact(scope)], "impact_if_false": "Replan the pilot", "validation_plan": "Ask the owner",
        "review_due": "2026-10-01T00:00:00Z", "state": "OPEN"})
    unknown = obj_like(example, "Unknown", "unknown", {"question": "Is the external API idempotent?",
        "affected_objects": [exact(scope)], "resolution_owner": "urn:identity:responsible",
        "blocking_policy": "BLOCK", "state": "OPEN"})
    return [source, scope, assertion, evidence, assumption, unknown]


def baseline_request(knowledge, revision=1):
    meta = deepcopy(knowledge[1]["meta"])
    meta.update(id="urn:air:test:baseline", type="air.Baseline", revision=revision, name="Knowledge baseline")
    return {"meta": meta, "profile": FOUNDATION_PROFILE,
            "members": [exact(obj) for obj in knowledge], "parent_baselines": []}


def proposed_change(knowledge, baseline, new_object):
    meta = deepcopy(knowledge[1]["meta"])
    meta.update(id="urn:air:test:change", type="air.ChangeSet", name="Clarify an assumption")
    old = next(ref for ref in baseline["body"]["members"] if ref["id"] == new_object["meta"]["id"])
    return {"meta": meta, "body": {"base": exact(baseline), "operations": [
        {"op": "REPLACE", "before": old, "after": resolved(new_object)}], "rationale": "More precise validation plan",
        "expected_revisions": deepcopy(baseline["body"]["members"]), "approvals": []}}


def prepare(store, knowledge):
    store.put_bundle(knowledge, "architect")
    return store.create_baseline(baseline_request(knowledge), "architect")


def test_closed_knowledge_cycles_and_scoped_rule(knowledge):
    result = validate_graph(knowledge)
    assert result["valid"]
    assert result["rule_results"][0]["result"] == "SATISFIED"
    assert result["rule_results"][0]["rule"] == "AIR-V003"
    assert len(result["coverage"]["not_executed"]) == 83
    assert result["open_unknowns"][0]["blocking_policy"] == "BLOCK"
    assert not result["decision_ready"] and not result["conformant_air_0_1"]


@pytest.mark.parametrize("mode,code", [("missing", "AIR_REFERENCE_MISSING"), ("wrong_type", "AIR_REFERENCE_TYPE"),
    ("ambiguous", "AIR_BASELINE_VERSION_AMBIGUOUS"), ("reciprocity", "AIR_EVIDENCE_RECIPROCITY"),
    ("unsupported_state", "AIR_EPISTEMIC_BASIS"), ("direction", "AIR_EVIDENCE_DIRECTION")])
def test_invalid_graphs(knowledge, mode, code):
    if mode == "missing":
        knowledge.pop(0)
    elif mode == "wrong_type":
        knowledge[2]["body"]["subject_scope"] = exact(knowledge[0])
    elif mode == "ambiguous":
        other = deepcopy(knowledge[1])
        other["meta"]["revision"] = 2
        knowledge.append(other)
    elif mode == "reciprocity":
        knowledge[2]["body"]["evidence"] = []
    elif mode == "unsupported_state":
        knowledge[2]["body"]["epistemic_status"] = "REFUTED"
    else:
        knowledge[3]["body"]["supports_or_refutes"].append({**exact(knowledge[2]), "direction": "REFUTES"})
    result = validate_graph(knowledge)
    assert not result["valid"]
    assert code in {item["code"] for item in result["diagnostics"]}
    if mode == "missing":
        assert result["rule_results"][0]["result"] == "VIOLATED"


def test_established_cannot_be_self_declared(knowledge):
    knowledge[2]["body"]["epistemic_status"] = "ESTABLISHED"
    result = validate_graph(knowledge)
    assert not result["valid"]
    assert "AIR_REVIEW_REQUIRED" in {d["code"] for d in result["diagnostics"]}
    assert result["rule_results"][0]["execution"] == "NOT_EXECUTED"


def test_unknown_resolution_requires_exact_answer(knowledge):
    knowledge[-1]["body"]["state"] = "RESOLVED"
    assert not validate_graph(knowledge)["valid"]
    knowledge[-1]["body"]["resolution"] = exact(knowledge[2])
    assert validate_graph(knowledge)["valid"]
    knowledge[-1]["body"]["resolution"] = exact(knowledge[1])
    assert not validate_graph(knowledge)["valid"]


def test_baseline_is_exact_immutable_and_replayable(store, knowledge):
    first = prepare(store, knowledge)
    request = baseline_request(knowledge)
    request["members"].reverse()
    repeated = store.create_baseline(request, "architect")
    assert first["digest"] == repeated["digest"] and not repeated["created"]
    exported = store.export_baseline(exact(first["baseline"]))
    assert exported["dependency_lock"] == lock_document(first["baseline"]["body"]["members"])
    assert exported["baseline"]["body"]["dependency_lock"] == lock_reference(first["baseline"]["body"]["members"])
    request["meta"]["name"] = "Tampered name"
    with pytest.raises(Conflict):
        store.create_baseline(request, "architect")
    assert store.export_baseline(exact(first["baseline"]))["digest"] == first["digest"]


def test_baseline_rejects_reference_to_stored_object_outside_members(store, knowledge):
    store.put_bundle(knowledge, "architect")
    request = baseline_request(knowledge)
    request["members"] = request["members"][1:]
    with pytest.raises(InvalidModel):
        store.create_baseline(request, "architect")
    assert store.get(request["meta"]["id"], 1) is None


def test_partial_bundle_write_rolls_back_on_conflict(store, knowledge):
    store.put(knowledge[-1], "architect")
    modified = deepcopy(knowledge)
    modified[-1]["body"]["question"] = "Conflicting content"
    with pytest.raises(Conflict):
        store.put_bundle(modified, "architect")
    assert store.counts()["revisions"] == 1


def test_import_cannot_bypass_baseline_service(store, knowledge):
    snapshot = prepare(store, knowledge)["baseline"]
    with pytest.raises(InvalidModel):
        store.put(snapshot, "architect")
    with pytest.raises(InvalidModel):
        store.put_bundle([snapshot], "architect")


def test_concurrent_baseline_retries_create_one_snapshot(store, knowledge):
    store.put_bundle(knowledge, "architect")
    request = baseline_request(knowledge)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.create_baseline(request, "architect"), range(4)))
    assert sum(item["created"] for item in results) == 1
    assert len({item["digest"] for item in results}) == 1


def test_changeset_creates_new_snapshot_and_preserves_base(store, knowledge):
    base = prepare(store, knowledge)
    new_object = deepcopy(knowledge[4])
    new_object["meta"]["revision"] = 2
    new_object["body"]["validation_plan"] = "Confirm with the named resource owner before October 1"
    store.put(new_object, "architect")
    change = proposed_change(knowledge, base["baseline"], new_object)
    result = store.propose_change(change, "architect")
    replay = store.propose_change(change, "architect")
    assert not result["approved"] and not result["published"]
    assert result["target"]["digest"] == replay["target"]["digest"]
    assert not replay["change"]["created"] and not replay["target"]["created"]
    assert result["target"]["baseline"]["body"]["parent_baselines"] == [exact(base["baseline"])]
    assert store.export_baseline(exact(base["baseline"]))["digest"] == base["digest"]
    assert resolved(new_object) in result["target"]["baseline"]["body"]["members"]


@pytest.mark.parametrize("mode", ["wrong_expected", "wrong_digest", "remove_referenced", "fake_approval", "old_revision", "duplicate_operation"])
def test_changeset_invalid_or_stale_input_leaves_no_artifacts(store, knowledge, mode):
    base = prepare(store, knowledge)["baseline"]
    new_object = deepcopy(knowledge[4])
    new_object["meta"]["revision"] = 2
    store.put(new_object, "architect")
    change = proposed_change(knowledge, base, new_object)
    if mode == "wrong_expected":
        change["body"]["expected_revisions"].pop()
    elif mode == "wrong_digest":
        change["body"]["operations"][0]["after"]["digest"] = "sha256:" + "0" * 64
    elif mode == "remove_referenced":
        source_ref = next(ref for ref in base["body"]["members"] if ref["type"] == "air.Source")
        change["body"]["operations"] = [{"op": "REMOVE", "before": source_ref}]
    elif mode == "fake_approval":
        change["body"]["approvals"] = [{"approved": True}]
    elif mode == "old_revision":
        change["body"]["operations"][0]["after"] = change["body"]["operations"][0]["before"]
    else:
        change["body"]["operations"] *= 2
    count = store.counts()
    with pytest.raises(InvalidModel):
        store.propose_change(change, "architect")
    assert store.counts() == count
    assert store.get(change["meta"]["id"], 1) is None


def test_restore_root_baseline_in_new_sqlite_store(store, knowledge, tmp_path):
    base = prepare(store, knowledge)["baseline"]
    exported = store.export_baseline(exact(base))
    restored = Store(f"sqlite:///{(tmp_path / 'restored.db').as_posix()}")
    try:
        restored.migrate()
        restored.put_bundle(exported["objects"], "restore-test")
        receipt = restored.create_baseline({"meta": base["meta"], "profile": FOUNDATION_PROFILE,
            "members": [exact(obj) for obj in exported["objects"]], "parent_baselines": []}, "restore-test")
        assert receipt["digest"] == exported["digest"]
        assert restored.export_baseline(exact(base))["dependency_lock"] == exported["dependency_lock"]
    finally:
        restored.engine.dispose()


def test_tampered_stored_member_is_detected(store, knowledge):
    base = prepare(store, knowledge)["baseline"]
    damaged = deepcopy(knowledge[0])
    damaged["body"]["locator"] = "urn:tampered"
    with store.write() as conn:
        conn.execute(update(revisions).where(revisions.c.id == damaged["meta"]["id"]).values(payload=canonical(damaged).decode()))
    with pytest.raises(InvalidModel):
        store.export_baseline(exact(base))


def test_foundation_http_services_and_permissions(store, knowledge, tmp_path):
    token = store.create_token("writer", "editor")
    reader = store.create_token("reader", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    read_headers = {"Authorization": "Bearer " + reader["access_token"]}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post("/v1/draft-bundles", json=knowledge).status_code == 401
        assert client.post("/v1/draft-bundles", json=knowledge, headers=read_headers).status_code == 403
        assert client.post("/v1/draft-bundles", json=knowledge, headers=headers).status_code == 200
        graph = client.post("/v1/foundation/validations", json=knowledge, headers=read_headers)
        assert graph.status_code == 200 and graph.json()["valid"]
        assert client.post("/v1/baselines", json=baseline_request(knowledge), headers=read_headers).status_code == 403
        result = client.post("/v1/baselines", json=baseline_request(knowledge), headers=headers)
        assert result.status_code == 201
        assert client.post("/v1/drafts", json=result.json()["baseline"], headers=headers).status_code == 422
        assert client.get("/v1/baselines/urn:air:test:baseline/revisions/1/export", headers=read_headers).status_code == 200
        new = deepcopy(knowledge[4])
        new["meta"]["revision"] = 2
        assert client.post("/v1/drafts", json=new, headers=headers).status_code == 201
        change = proposed_change(knowledge, result.json()["baseline"], new)
        assert client.post("/v1/changes", json=change, headers=read_headers).status_code == 403
        assert client.post("/v1/changes", json=change, headers=headers).status_code == 201
        assert client.post("/v1/changes", json=change, headers=headers).status_code == 200
        bad_request = baseline_request(knowledge, 2)
        bad_request["profile"] = "AIR 0.1"
        assert client.post("/v1/baselines", json=bad_request, headers=headers).status_code == 422


def test_add_remove_unreferenced_member(store, knowledge):
    base = prepare(store, knowledge)["baseline"]
    extra = deepcopy(knowledge[0])
    extra["meta"]["id"] = "urn:air:test:extra-source"
    store.put(extra, "architect")
    change = proposed_change(knowledge, base, knowledge[4])
    change["body"]["operations"] = [{"op": "ADD", "after": resolved(extra)}]
    added = store.propose_change(change, "architect")["target"]["baseline"]
    assert resolved(extra) in added["body"]["members"]
    change["meta"]["revision"] = 2
    change["body"].update(base=exact(added), expected_revisions=added["body"]["members"],
                          operations=[{"op": "REMOVE", "before": resolved(extra)}])
    removed = store.propose_change(change, "architect")["target"]["baseline"]
    assert removed["body"]["members"] == base["body"]["members"]


def test_change_identity_collision_rolls_back_target(store, knowledge):
    base = prepare(store, knowledge)["baseline"]
    updated = deepcopy(knowledge[4])
    updated["meta"]["revision"] = 2
    store.put(updated, "architect")
    change = proposed_change(knowledge, base, updated)
    store.propose_change(change, "architect")
    count = store.counts()
    change["body"]["rationale"] += " conflicting retry"
    with pytest.raises(Conflict):
        store.propose_change(change, "architect")
    assert store.counts() == count
    orphan = "urn:air:baseline:proposal:" + digest(change).split(":", 1)[1]
    assert store.get(orphan, 1) is None


def test_invalid_input_does_not_claim_executed_closure():
    report = validate_graph({"meta": None})
    assert not report["valid"]
    assert report["rule_results"][0]["execution"] == "NOT_EXECUTED"


def test_asteria_three_dossier_rehearsal():
    import importlib.util
    script = Path(__file__).resolve().parents[1] / "scripts/demo_foundation.py"
    spec = importlib.util.spec_from_file_location("demo_foundation", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.rehearse()
    assert report["status"] == "PASS" and len(report["dossiers"]) == 3
    assert all(case["digest"] == case["restored_digest"] for case in report["dossiers"])
    assert all(case["members"] == 9 for case in report["dossiers"])
    assert not report["business_demo_ready"] and not report["live_instance_modified"]
