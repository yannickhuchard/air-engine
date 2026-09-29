from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air.api import create_app
from air.config import Settings
from air.construction import assess_baseline, validate_construction
from air.core import CONSTRUCTION_PROFILE, FOUNDATION_PROFILE, canonical, digest, validate
from air.foundation import InvalidModel, exact, validate_graph
from air.storage import Conflict

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria/dossiers/sav"


@pytest.fixture
def construction():
    return json.loads((FIXTURE / "construction.json").read_text(encoding="utf-8"))


def get(objects, kind):
    return next(o for o in objects if o["meta"]["type"] == "air." + kind)


def request():
    return json.loads((FIXTURE / "construction-baseline-request.json").read_text(encoding="utf-8"))


def prepare(store, objects):
    store.put_bundle(objects, "architect")
    base = store.create_baseline(request(), "architect")
    return base, {"baseline": {**exact(base["baseline"]), "digest": base["digest"]}}


def test_complete_chain_and_verification_is_not_execution(construction, store):
    assert validate(construction)["profile"] == CONSTRUCTION_PROFILE
    base, req = prepare(store, construction)
    counts, audit = store.counts(), store.audit_log()
    report = assess_baseline(store, req)
    assert report["valid"] and report["construction_ready"]
    assert len(report["traceability"]) == 1 and len(report["traceability"][0]["acceptance"]) == 3
    assert len(report["verification_cases"]) == 3
    assert all(v["execution"] == "NOT_EXECUTED" for v in report["verification_cases"])
    assert report["gate_decision"] == "BLOCKED" and not report["decision_ready"]
    assert report == assess_baseline(store, req)
    assert store.counts() == counts and store.audit_log() == audit
    assert base["baseline"]["body"]["profiles"] == [CONSTRUCTION_PROFILE]
    assert store.export_baseline(exact(base["baseline"]))["dependency_lock"]["profile"] == CONSTRUCTION_PROFILE


@pytest.mark.parametrize("mutation,code", [
    ("uncovered", "AIR_REQUIRED_REALIZATION"), ("no_cases", "AIR_ACCEPTANCE_CASES"),
    ("wrong_target", "AIR_REQUIREMENT_VERIFICATION"), ("method", "AIR_ACCEPTANCE_METHOD"),
    ("errors", "AIR_CONTRACT_ERRORS"), ("effects", "AIR_CONTRACT_EFFECTS"),
    ("realizes", "AIR_UNIT_OPERATIONS"), ("acceptance", "AIR_UNIT_ACCEPTANCE"),
])
def test_structural_gaps_are_rejected(construction, mutation, code):
    if mutation == "uncovered":
        extra = deepcopy(get(construction, "Requirement"));extra["meta"]["id"] += ":uncovered";construction.append(extra)
    elif mutation == "no_cases": get(construction, "AcceptanceCriterion")["body"]["cases"] = []
    elif mutation == "wrong_target":
        extra = deepcopy(get(construction, "Requirement"));extra["meta"]["id"] += ":unrelated";extra["body"]["priority"] = "COULD";construction.append(extra)
        get(construction, "VerificationCase")["body"]["target"] = exact(extra)
    elif mutation == "method": get(construction, "VerificationCase")["body"]["method"] = "REVIEW"
    elif mutation == "errors": get(construction, "SemanticContract")["body"]["error_contract"] = []
    elif mutation == "effects": get(construction, "SemanticContract")["body"]["state_effects"] = []
    elif mutation == "realizes": get(construction, "ConstructionUnit")["body"]["realizes"] = [exact(get(construction, "SemanticContract"))]
    else: get(construction, "ConstructionUnit")["body"]["acceptance"].pop()
    report = validate_construction(construction)
    assert not report["valid"] and any(d["code"] == code for d in report["diagnostics"])


@pytest.mark.parametrize("mutation", ["missing", "wrong_type", "duplicate_parameter", "estimate_unit", "unknown_field"])
def test_strict_schemas_and_reference_closure(construction, mutation):
    if mutation == "missing": construction.remove(get(construction, "Actor"))
    elif mutation == "wrong_type": get(construction, "Requirement")["body"]["acceptance"] = [exact(get(construction, "Source"))]
    elif mutation == "duplicate_parameter": get(construction, "Function")["body"]["inputs"] *= 2
    elif mutation == "estimate_unit": get(construction, "Estimate")["body"]["value_or_distribution"]["unit"] = "second"
    else: get(construction, "VerificationCase")["body"]["approved"] = True
    assert not validate_construction(construction)["valid"]


def test_old_profile_cannot_contain_new_types(construction, store):
    assert not validate_graph(construction, FOUNDATION_PROFILE)["valid"]
    store.put_bundle(construction, "architect")
    req = request();req["profile"] = FOUNDATION_PROFILE
    before = store.counts()
    with pytest.raises(InvalidModel): store.create_baseline(req, "architect")
    assert store.counts() == before


def test_old_baseline_digests_match_recorded_release(store):
    evidence = json.loads((ROOT / "docs/traceability/verification-foundation.json").read_text(encoding="utf-8"))
    # Historical fixture digests are checked separately from the current implementation.
    manifest = json.loads((ROOT / "fixtures/enterprise/asteria/manifest.json").read_text(encoding="utf-8"))
    def find(value, object_id):
        if isinstance(value, dict):
            if value.get("baseline", {}).get("id") == object_id and "digest" in value: return value["digest"]
            for v in value.values():
                found = find(v, object_id)
                if found: return found
        if isinstance(value, list):
            for v in value:
                found = find(v, object_id)
                if found: return found
    for case in manifest["dossiers"]:
        folder = ROOT / "fixtures/enterprise/asteria"
        objects = json.loads((folder / case["foundation"]).read_text(encoding="utf-8"))
        req = json.loads((folder / case["baseline_request"]).read_text(encoding="utf-8"))
        store.put_bundle(objects, "architect")
        base = store.create_baseline(req, "architect")
        expected = find(evidence, req["meta"]["id"])
        assert expected is not None and base["digest"] == expected


def test_reference_set_normalization_and_immutable_revisions(construction, store):
    obj = get(construction, "Requirement")
    changed = deepcopy(obj);changed["body"]["acceptance"].reverse()
    assert canonical(obj) == canonical(changed)
    store.put(obj, "architect")
    assert not store.put(changed, "architect")["created"]
    changed["body"]["statement"] += " Change"
    with pytest.raises(Conflict): store.put(changed, "architect")


def test_authenticated_route_and_exact_digest(construction, store, tmp_path):
    base, req = prepare(store, construction)
    token = store.create_token("reader", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post("/v1/construction/validations", json=req).status_code == 401
        response = client.post("/v1/construction/validations", json=req, headers=headers)
        assert response.status_code == 200 and response.json() == assess_baseline(store, req)
        req["baseline"]["digest"] = "sha256:" + "0" * 64
        assert client.post("/v1/construction/validations", json=req, headers=headers).status_code == 409
        req["approved"] = True
        assert client.post("/v1/construction/validations", json=req, headers=headers).status_code == 422


def test_foundation_gate_cannot_claim_coverage_of_construction(construction, store):
    from air.gates import validate_gate
    from test_gates import rule
    base, req = prepare(store, construction)
    req.update(profile="air.validation/0.3", gate="foundation-review", inputs={},
               rule_set={"id": "test", "version": "1", "rules": [rule()]})
    with pytest.raises(InvalidModel): validate_gate(store, req)


def test_three_dossier_construction_rehearsal():
    spec = importlib.util.spec_from_file_location("demo_construction", ROOT / "scripts/demo_construction.py")
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report = module.rehearse()
    assert report["status"] == "PASS" and len(report["dossiers"]) == 3
    assert not report["business_scenarios_executed"] and not report["business_demo_ready"]
