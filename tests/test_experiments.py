from copy import deepcopy
import sys
from pathlib import Path
import pytest
from air.expr import artifact_digest
from air.experiments import simulate
from air.foundation import InvalidModel
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from demo_experiments import expression, read, request_for, rehearse


def fixture_request(store): return request_for(store, read("manifest.json")["dossiers"][0])


def test_three_experiments_are_illustrative_and_preserve_conflicts():
    result = rehearse()
    assert result["status"] == "PASS_SCOPED"
    assert [r["result"]["result"] for r in result["dossiers"]] == ["SATISFIED", "SATISFIED", "CONFLICTING"]
    assert sum(len(r["result"]["outcomes"]) for r in result["dossiers"]) == 11
    assert all(not r["result"]["authorization_granted"] for r in result["dossiers"])


def test_missing_input_oracle_mismatch_and_model_tampering(store):
    request = fixture_request(store)
    changed = deepcopy(request);changed["model"]["description"] += " tampered"
    with pytest.raises(InvalidModel, match="digest"): simulate(store, changed)
    changed = deepcopy(request);changed["scenarios"][0]["expected"]["new_registration"]["value"] = False
    assert simulate(store, changed)["result"] == "VIOLATED"
    changed = deepcopy(request);del changed["scenarios"][0]["inputs"]["authorized"]
    assert simulate(store, changed)["result"] == "UNKNOWN"
    changed = deepcopy(request);changed["scenarios"][0]["expected"] = {}
    with pytest.raises(InvalidModel, match="expected"): simulate(store, changed)
    changed = deepcopy(request);changed["evidence_class"] = "OBSERVED"
    with pytest.raises(InvalidModel): simulate(store, changed)


def test_division_error_and_total_budget_cannot_pass(store):
    request = fixture_request(store)
    request["model"]["measures"] = {"ratio": expression({"op": "div", "args": [{"literal": {"type": "Integer", "value": 1}}, {"literal": {"type": "Integer", "value": 0}}]}, {}, "Decimal")}
    request["model_digest"] = artifact_digest(request["model"])
    request["scenarios"] = [{**request["scenarios"][0], "inputs": {}, "expected": {"ratio": {"type": "Decimal", "value": "0"}}}]
    result = simulate(store, request)
    assert result["result"] == "UNKNOWN"
    assert result["outcomes"][0]["measures"][0]["observation"]["execution"] == "ERROR"
    request["model"]["measures"] = {"all_positive": expression({"op": "every", "over": {"ref": "items"}, "predicate": {"op": "gte", "args": [{"ref": "$item"}, {"literal": {"type": "Integer", "value": 0}}]}}, {"items": "Collection[Integer]"})}
    request["model_digest"] = artifact_digest(request["model"])
    case = request["scenarios"][0]["verification_case"]
    request["scenarios"] = [{"id": "case" + str(i), "verification_case": case,
        "inputs": {"items": {"type": "Collection[Integer]", "value": [{"type": "Integer", "value": 1}] * 256}},
        "expected": {"all_positive": {"type": "Boolean", "value": True}}} for i in range(32)]
    result = simulate(store, request)
    assert result["result"] == "UNKNOWN" and result["cost"]["steps"] == 20000
    assert any(m["observation"]["execution"] == "BUDGET_EXCEEDED" for o in result["outcomes"] for m in o["measures"])


def test_experiment_order_is_replay_stable_and_foreign_case_rejected(store):
    request = fixture_request(store)
    result = simulate(store, request)
    request["scenarios"].reverse()
    assert simulate(store, request) == result
    other = request_for(store, read("manifest.json")["dossiers"][1])
    request["scenarios"][0]["verification_case"] = other["scenarios"][0]["verification_case"]
    with pytest.raises(InvalidModel): simulate(store, request)
