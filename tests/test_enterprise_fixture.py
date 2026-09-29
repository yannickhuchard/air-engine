from decimal import Decimal
from pathlib import Path
import importlib.util
import json
from fastapi.testclient import TestClient
import pytest
from air.api import create_app
from air.config import Settings
from air.core import digest, references, validate

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fixture_preflight", ROOT / "scripts/check_enterprise_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_sources_are_pinned_and_all_fixture_references_present():
    manifest, shared, cases = fixture.load_fixture()
    assert {case["id"] for case, _ in cases} == {"D01", "D02", "D03"}
    all_objects = shared + [obj for _, group in cases for obj in group]
    assert len(all_objects) == 9
    assert len({(obj["meta"]["id"], obj["meta"]["revision"]) for obj in all_objects}) == 9
    shared_refs = {(obj["meta"]["id"], obj["meta"]["revision"]) for obj in shared}
    for case, group in cases:
        report = validate(shared + group)
        assert report["valid"] and not report["unresolved_references"]
        assert not report["conformant_air_0_1"]
        assert report["coverage"]["reference_resolution"] == "NOT_EXECUTED"
        used_refs = {(ref["id"], ref["revision"]) for obj in group for ref in references(obj)}
        assert shared_refs <= used_refs


def test_three_dossiers_coexist_in_one_authenticated_registry(store, tmp_path):
    _, shared, cases = fixture.load_fixture()
    token = store.create_token("fictional-architect", "editor")
    reader = store.create_token("fictional-reader", "reader")
    headers = {"Authorization": "Bearer " + token["access_token"]}
    reader_headers = {"Authorization": "Bearer " + reader["access_token"]}
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))
    with TestClient(app) as client:
        for obj in shared:
            assert client.post("/v1/drafts", json=obj, headers=headers).status_code == 201
        for case, group in cases:
            for obj in group:
                assert client.post("/v1/drafts", json=obj, headers=reader_headers).status_code == 403
                created = client.post("/v1/drafts", json=obj, headers=headers)
                assert created.status_code == 201
                assert created.json()["digest"] == digest(obj)
                assert client.post("/v1/drafts", json=obj, headers=headers).status_code == 200
                response = client.get(f"/v1/objects/{obj['meta']['id']}/revisions/1", headers=reader_headers)
                assert response.status_code == 200
                assert digest(response.json()["object"]) == digest(obj)
        assert store.counts()["revisions"] == 9
        assert len([e for e in store.audit_log() if e["action"] == "draft.stored"]) == 9


def test_portfolio_oracle_is_consistent_not_a_planner_result():
    manifest, _, _ = fixture.load_fixture()
    portfolio = manifest["portfolio"]
    supply = list(map(Decimal, portfolio["resource"]["net_supply_per_week"]))
    demands = portfolio["demands"]
    total = [sum(Decimal(d["per_week"][week]) for d in demands) for week in range(8)]
    shortfall = [max(Decimal(0), demand - capacity) for demand, capacity in zip(total, supply)]
    oracle = portfolio["oracle"]
    assert oracle["kind"] == "EXPECTED_RESULT_NOT_ENGINE_OUTPUT"
    assert total == list(map(Decimal, oracle["initial_total_per_week"]))
    assert shortfall == list(map(Decimal, oracle["initial_shortfall_per_week"]))
    assert sum(shortfall) == Decimal(oracle["initial_shortfall_FTE_weeks"]) == 4
    for demand in demands:
        assert sum(map(Decimal, demand["per_week"])) == Decimal(demand["total_FTE_weeks"])
    variant = oracle["proposed_variant"]
    changed = [sum(Decimal(variant["per_week"][week]) if d["dossier"] == variant["shifted_dossier"]
                   else Decimal(d["per_week"][week]) for d in demands) for week in range(8)]
    assert changed == list(map(Decimal, variant["total_per_week"]))
    assert all(demand <= capacity for demand, capacity in zip(changed, supply))
    assert not variant["approved"] and not variant["admitted"] and not variant["launch_authorized"]


def test_preflight_does_not_claim_business_demo_or_normative_rules():
    report = fixture.check_fixture()
    assert report["status"] == "PASS"
    assert len(report["results"]) == 3
    assert report["stored_revisions"] == 9
    assert report["business_demo_ready"] is False
    assert {r["business_acceptance"] for r in report["results"]} == {"NOT_EXECUTED"}
    assert all(item["execution"] == "NOT_EXECUTED" for item in report["business_checks"])
    assert report["live_instance_modified"] is False
