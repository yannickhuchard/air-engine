from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from air.api import create_app
from air.config import Settings
from air.core import FOUNDATION_PROFILE
from air.expr import artifact_digest
from air.foundation import InvalidModel, exact
from air.gates import PROFILE, validate_gate
from air.storage import Conflict
from test_expr import call, expression, lit
from test_foundation import knowledge, baseline_request


def rule(name="check", predicate=None, mandatory=True, method="EXPRESSION", applicability=None):
    result = {"id": name, "version": "1", "mandatory": mandatory, "method": method,
              "applicability": applicability or expression(lit("Boolean", True))}
    if method == "EXPRESSION":
        result["predicate"] = predicate or expression(lit("Boolean", True))
    return result


@pytest.fixture
def gate_request(store, example):
    store.put(example, "test")
    meta = deepcopy(example["meta"])
    meta.update(id="urn:test:gate-baseline", type="air.Baseline")
    base = store.create_baseline({"meta": meta, "profile": FOUNDATION_PROFILE,
                                  "members": [exact(example)], "parent_baselines": []}, "test")
    return {"profile": PROFILE, "gate": "foundation-review", "baseline": {**exact(base["baseline"]), "digest": base["digest"]},
            "rule_set": {"id": "test:rules", "version": "1", "rules": [rule()]}, "inputs": {}}


def test_pass_is_diagnostic_replayable_and_read_only(store, gate_request):
    counts, audit = store.counts(), store.audit_log()
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "PASSED"
    assert not report["authorization_granted"] and not report["decision_ready"]
    assert report == validate_gate(store, deepcopy(gate_request))
    digest = report.pop("report_digest")
    assert artifact_digest(report) == digest
    assert store.counts() == counts and store.audit_log() == audit
    gate_request["baseline"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(Conflict):
        validate_gate(store, gate_request)


@pytest.mark.parametrize("state,result", [("UNKNOWN", "UNKNOWN"), ("CONFLICTING", "CONFLICTING"), ("KNOWN", "VIOLATED")])
def test_required_rule_does_not_pass_uncertain_or_false(store, gate_request, state, result):
    gate_request["rule_set"]["rules"] = [rule(predicate=expression({"ref": "inputs.check"}, **{"inputs.check": "Boolean"}))]
    gate_request["inputs"] = {"inputs.check": {"type": "Boolean", **({"value": False} if state == "KNOWN" else {"state": state})}}
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "BLOCKED" and report["results"][0]["result"] == result


def test_manual_and_applicability_are_separate(store, gate_request):
    gate_request["rule_set"]["rules"] = [rule(method="MANUAL")]
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "BLOCKED" and report["results"][0]["execution"] == "NOT_EXECUTED"
    gate_request["rule_set"]["rules"][0]["applicability"] = expression(lit("Boolean", False))
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "PASSED" and report["results"][0]["result"] == "NOT_APPLICABLE"
    gate_request["rule_set"]["rules"][0]["applicability"] = expression({"ref": "inputs.scope"}, **{"inputs.scope": "Boolean"})
    assert validate_gate(store, gate_request)["gate_decision"] == "BLOCKED"


def test_optional_violation_is_visible_but_execution_error_blocks(store, gate_request):
    gate_request["rule_set"]["rules"] = [rule(mandatory=False, predicate=expression(lit("Boolean", False)))]
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "PASSED" and report["results"][0]["result"] == "VIOLATED"
    gate_request["rule_set"]["rules"][0]["predicate"] = expression(call("eq", call("div", lit("Integer", 1), lit("Integer", 0)), lit("Decimal", "1")))
    assert validate_gate(store, gate_request)["gate_decision"] == "BLOCKED"


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "approval", "override", "forged_normative", "unknown_property", "malformed_inapplicable"])
def test_gate_rejects_incomplete_or_forged_policy(store, gate_request, mutation):
    if mutation == "empty": gate_request["rule_set"]["rules"] = []
    elif mutation == "duplicate": gate_request["rule_set"]["rules"] *= 2
    elif mutation == "approval": gate_request["approved"] = True
    elif mutation == "override": gate_request["inputs"]["baseline.closed"] = {"type": "Boolean", "value": True}
    elif mutation == "forged_normative": gate_request["rule_set"]["rules"][0]["id"] = "AIR-V037"
    elif mutation == "unknown_property": gate_request["rule_set"]["rules"][0]["predicate"] = expression({"ref": "baseline.secret"}, **{"baseline.secret": "Boolean"})
    else:
        gate_request["rule_set"]["rules"][0]["applicability"] = expression(lit("Boolean", False))
        gate_request["rule_set"]["rules"][0]["predicate"] = expression({"op": "exec", "args": []})
    with pytest.raises(InvalidModel):
        validate_gate(store, gate_request)


def test_derived_properties_and_shared_gate_budget(store, gate_request, monkeypatch):
    gate_request["rule_set"]["rules"] = [rule(predicate=expression(call("eq", {"ref": "baseline.member_count"}, lit("Integer", 1)), **{"baseline.member_count": "Integer"}))]
    assert validate_gate(store, gate_request)["results"][0]["result"] == "SATISFIED"
    monkeypatch.setattr("air.gates.GATE_STEPS", 2)
    report = validate_gate(store, gate_request)
    assert report["gate_decision"] == "BLOCKED" and report["results"][0]["execution"] == "BUDGET_EXCEEDED"


def test_authenticated_api_uses_same_engine(store, gate_request, tmp_path):
    token = store.create_token("reader", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post("/v1/validations", json=gate_request).status_code == 401
        assert client.post("/v1/expressions/evaluate", json={}).status_code == 401
        result = client.post("/v1/validations", json=gate_request, headers=headers)
        assert result.status_code == 200 and result.json() == validate_gate(store, gate_request)
        result = client.post("/v1/expressions/evaluate", json={"expression": expression(lit("Boolean", True)), "inputs": {}}, headers=headers)
        assert result.status_code == 200 and result.json()["result"] == "SATISFIED"
        gate_request["baseline"]["digest"] = "sha256:" + "0" * 64
        assert client.post("/v1/validations", json=gate_request, headers=headers).status_code == 409
        gate_request["approved"] = True
        assert client.post("/v1/validations", json=gate_request, headers=headers).status_code == 422


def test_contested_baseline_blocks_even_when_caller_omits_checks(store, knowledge):
    refutation = deepcopy(knowledge[3])
    refutation["meta"]["id"] += ":refutation"
    refutation["body"]["supports_or_refutes"][0]["direction"] = "REFUTES"
    knowledge[2]["body"]["epistemic_status"] = "CONTESTED"
    knowledge[2]["body"]["evidence"].append(exact(refutation))
    knowledge.append(refutation)
    store.put_bundle(knowledge, "test")
    base = store.create_baseline(baseline_request(knowledge), "test")
    request = {"profile": PROFILE, "gate": "foundation-review", "baseline": {**exact(base["baseline"]), "digest": base["digest"]},
               "rule_set": {"id": "test", "version": "1", "rules": [rule(mandatory=False)]}, "inputs": {}}
    report = validate_gate(store, request)
    assert report["gate_decision"] == "BLOCKED"
    assert {x["code"] for x in report["blockers"]} >= {"AIR_GATE_BLOCKING_UNKNOWNS", "AIR_GATE_CONTESTED_ASSERTIONS"}


def test_asteria_validation_rehearsal():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts/demo_validation.py"
    spec = importlib.util.spec_from_file_location("demo_validation", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.rehearse()
    assert report["status"] == "PASS" and len(report["dossiers"]) == 3
    assert [c["initial"]["results"][0]["result"] for c in report["dossiers"]] == ["UNKNOWN", "VIOLATED", "CONFLICTING"]
    assert all(c["corrected_inputs_only"]["gate_decision"] == "BLOCKED" for c in report["dossiers"])
    assert not report["business_demo_ready"]
