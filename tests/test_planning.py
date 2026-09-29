from copy import deepcopy
from decimal import getcontext
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from air.api import create_app
from air.config import Settings
from air.foundation import InvalidModel
from air.planning import plan

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_planning import prepare, rehearse


def test_asteria_capacity_oracle_is_computed_without_writes(store):
    request = prepare(store)
    before, audit = store.counts(), store.audit_log()
    initial = plan(store, request)
    assert initial["result"] == "VIOLATED"
    assert initial["proposed"]["total_shortfall_FTE_weeks"] == "4"
    assert [c["demand"] for c in initial["proposed"]["pools"][0]["periods"]] == ["5"] * 4 + ["0"] * 4
    request["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
    result = plan(store, request)
    assert result["result"] == "SATISFIED" and result["candidate"]["capacity_feasible"]
    assert [c["demand"] for c in result["candidate"]["pools"][0]["periods"]] == ["3"] * 4 + ["2"] * 4
    assert not result["authorization_granted"] and not result["reservations_created"]
    assert not result["solver"]["optimality_proven"] and result["solver"]["optimality_gap"] is None
    assert result == plan(store, deepcopy(request))
    assert store.counts() == before and store.audit_log() == audit


def test_unknown_capacity_expiry_and_existing_reservations(store):
    request = prepare(store)
    for cause in ("unavailable", "expired", "missing"):
        case = deepcopy(request)
        if cause == "unavailable": case["pools"][0]["availability"] = "UNAVAILABLE"
        if cause == "expired": case["as_of"] = "2026-10-01T00:00:00Z"
        if cause == "missing": case["pools"][0]["gross"][0] = None
        result = plan(store, case)
        assert result["proposed"]["total_shortfall_FTE_weeks"] is None
        assert not result["proposed"]["capacity_feasible"]
        case["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
        assert plan(store, case)["solver"]["status"] == "UNKNOWN_CAPACITY"
    request["pools"][0]["existing_reservations"] = ["1"] * 8
    assert plan(store, request)["proposed"]["total_shortfall_FTE_weeks"] == "8"


def test_duplicate_resources_bad_pin_and_invalid_periods_are_rejected(store):
    request = prepare(store)
    duplicate = deepcopy(request["pools"][0]);duplicate["scope"]["id"] = "urn:asteria:scope:identity"
    duplicate["scope"]["digest"] = store.get(duplicate["scope"]["id"], 1)["digest"]
    request["pools"].append(duplicate)
    with pytest.raises(InvalidModel, match="same resource"): plan(store, request)
    request["pools"].pop();request["demands"][0]["unit"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(InvalidModel): plan(store, request)
    request = prepare(store);request["periods"][1]["start"] = request["periods"][0]["start"]
    with pytest.raises(InvalidModel, match="periods"): plan(store, request)
    request = prepare(store);request["pools"][0]["gross"] = ["4"]
    with pytest.raises(InvalidModel, match="vector"): plan(store, request)


def test_precedence_cycles_and_failed_greedy_are_not_false_success(store):
    request = prepare(store)
    a, b = [d["unit"] for d in request["demands"][:2]]
    ref = lambda r: {"id": r["id"], "revision": r["revision"]}
    request["dependencies"] = [{"before": ref(a), "after": ref(b)}]
    assert plan(store, request)["proposed"]["precedence_diagnostics"]
    request["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
    assert plan(store, request)["candidate"]["precedence_satisfied"]
    request["dependencies"].append({"before": ref(b), "after": ref(a)})
    with pytest.raises(InvalidModel, match="acyclic"): plan(store, request)
    request = prepare(store);request["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
    request["pools"][0]["gross"] = ["2"] * 8
    result = plan(store, request)
    assert result["candidate"] is None and result["result"] == "UNKNOWN"
    assert result["solver"]["status"] == "NO_FEASIBLE_SCHEDULE_FOUND"


def test_exact_decimals_independent_of_ambient_context_and_set_order(store):
    request = prepare(store)
    request["pools"][0]["gross"] = ["4.100001"] * 8
    expected = plan(store, request)
    previous = getcontext().copy()
    try:
        getcontext().prec = 2
        changed = deepcopy(request);changed["demands"].reverse();changed["pools"][0]["resource_ids"].reverse()
        assert plan(store, changed) == expected
    finally:
        from decimal import setcontext
        setcontext(previous)
    assert expected["proposed"]["total_shortfall_FTE_weeks"] == "11.599996"


def test_annex_f7_separates_profiles_and_late_supply(store):
    request = prepare(store)
    request["demands"] = [request["demands"][0]]
    request["priority_order"] = [{k: request["demands"][0]["unit"][k] for k in ("id", "revision")}]
    engineer = request["pools"][0]
    engineer["baseline_obligations"] = ["0"] * 8
    engineer["gross"] = ["2"] * 4 + ["4"] * 4
    request["demands"][0]["per_week"] = ["4"] * 4 + ["0"] * 4
    analyst = deepcopy(engineer)
    analyst["scope"] = {"id": "urn:asteria:scope:identity", "revision": 1, "digest": store.get("urn:asteria:scope:identity", 1)["digest"]}
    analyst["resource_ids"] = ["urn:asteria:resource:analyst1", "urn:asteria:resource:analyst2"]
    analyst["gross"] = ["1"] * 4 + ["2"] * 4
    request["pools"].append(analyst)
    demand = deepcopy(request["demands"][0]);demand["pool"] = {k: analyst["scope"][k] for k in ("id", "revision")}
    demand["per_week"] = ["2"] * 4 + ["0"] * 4;request["demands"].append(demand)
    initial = plan(store, request)
    assert [sum(int(p["shortfall"]) for p in row["periods"]) for row in initial["proposed"]["pools"]] == [4, 8]
    engineer["gross"] = ["2", "2"] + ["4"] * 6
    improved = plan(store, request)
    assert [sum(int(p["shortfall"]) for p in row["periods"]) for row in improved["proposed"]["pools"]] == [4, 4]
    assert improved["result"] == "VIOLATED"


def test_planning_http_and_mcp_refuse_inaccessible_dossier(store, tmp_path):
    from air.mcp import PROTOCOL
    request = prepare(store)
    token = store.create_token("planner", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    policy = {"version": "1", "subjects": {"planner": {"read": ["asteria.shared", "asteria.sav"]}}}
    (tmp_path / "access-policy.json").write_text(json.dumps(policy), encoding="utf-8")
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))), base_url="http://127.0.0.1:8740") as client:
        assert client.post("/v1/plans", json=request).status_code == 401
        assert client.post("/v1/plans", json=request, headers=headers).status_code == 403
        mcp_headers = {**headers, "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "air_plan", "arguments": request}}
        denied = client.post("/mcp", json=message, headers=mcp_headers).json()["result"]
        assert denied["isError"] and denied["structuredContent"]["http_status"] == 403
        policy["subjects"]["planner"]["read"] = ["*"]
        (tmp_path / "access-policy.json").write_text(json.dumps(policy), encoding="utf-8")
        result = client.post("/v1/plans", json=request, headers=headers).json()
        via_mcp = client.post("/mcp", json=message, headers=mcp_headers).json()["result"]
        assert via_mcp["structuredContent"] == result and not via_mcp["isError"]
        assert result["proposed"]["total_shortfall_FTE_weeks"] == "4"
