"""Compute, rather than copy, the Asteria capacity oracle and an alternative schedule."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from air.core import digest
from air.foundation import exact
from air.planning import plan
from air.storage import Store
from demo_projections import read, ref
ROOT = Path(__file__).resolve().parents[1]


def prepare(store):
    manifest = read("manifest.json")
    demands, units = [], []
    for case, workload in zip(manifest["dossiers"], manifest["portfolio"]["demands"]):
        objects = read(case["construction"])
        store.put_bundle(objects, "synthetic-architect")
        base = store.create_baseline(read(case["construction_baseline_request"]), "synthetic-architect")
        unit = next(o for o in objects if o["meta"]["type"] == "air.ConstructionUnit")
        units.append(exact(unit))
        demands.append({"baseline": ref(base), "unit": {**exact(unit), "digest": digest(unit)},
            "pool": {"id": "urn:asteria:scope:integration", "revision": 1}, "per_week": workload["per_week"]})
    def pin(object_id):
        row = store.get(object_id, 1)
        return {"id": object_id, "revision": 1, "digest": row["digest"]}
    shared = read("shared.bootstrap.json")
    source = next(o for o in shared if o["meta"]["type"] == "air.Source")
    start = datetime(2026, 10, 5, tzinfo=timezone.utc)
    def instant(d): return d.isoformat().replace("+00:00", "Z")
    return {"basis": "SCENARIO_INPUT", "as_of": "2026-09-19T12:00:00Z", "unit": "FTE",
        "periods": [{"start": instant(start + timedelta(weeks=i)), "end": instant(start + timedelta(weeks=i+1))} for i in range(8)],
        "pools": [{"scope": pin("urn:asteria:scope:integration"), "source": {**exact(source), "digest": digest(source)},
            "resource_ids": ["urn:asteria:resource:integration-" + str(i) for i in range(6)],
            "availability": "AVAILABLE", "observed_at": "2026-09-19T10:00:00Z", "expires_at": "2026-10-01T00:00:00Z",
            "gross": ["6"] * 8, "baseline_obligations": ["2"] * 8, "existing_reservations": ["0"] * 8}],
        "demands": demands, "dependencies": [], "priority_order": [units[0], units[2], units[1]], "strategy": "AS_PROPOSED"}


def rehearse():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="air-planning-", dir=ROOT / "tmp") as folder:
        store = Store("sqlite:///" + (Path(folder) / "air.db").as_posix())
        try:
            store.migrate();request = prepare(store)
            counts, audit = store.counts(), store.audit_log()
            initial = plan(store, request)
            variant_request = deepcopy(request);variant_request["strategy"] = "SERIAL_EARLIEST_FEASIBLE"
            variant = plan(store, variant_request)
            missing_request = deepcopy(request);missing_request["pools"][0]["availability"] = "UNAVAILABLE"
            missing = plan(store, missing_request)
            oracle = read("manifest.json")["portfolio"]["oracle"]
            assert initial["proposed"]["total_shortfall_FTE_weeks"] == oracle["initial_shortfall_FTE_weeks"]
            assert [p["demand"] for p in initial["proposed"]["pools"][0]["periods"]] == oracle["initial_total_per_week"]
            assert [p["demand"] for p in variant["candidate"]["pools"][0]["periods"]] == oracle["proposed_variant"]["total_per_week"]
            assert variant["candidate"]["capacity_feasible"] and not variant["solver"]["optimality_proven"]
            assert missing["result"] == "UNKNOWN" and missing["proposed"]["total_shortfall_FTE_weeks"] is None
            assert initial == plan(store, request) and variant == plan(store, variant_request)
            assert store.counts() == counts and store.audit_log() == audit
            return {"status": "PASS_SCOPED", "request": request, "initial": initial, "variant": variant, "source_unavailable": missing,
                    "replay_identical": True, "storage_unchanged": True, "portfolio_milestone_ready": False}
        finally: store.engine.dispose()


if __name__ == "__main__":
    report = rehearse()
    output = ROOT / "tmp/demo-asteria/planning.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from air.report_views import planning_html
    labels = {o["meta"]["id"]: o["meta"]["name"] for case in read("manifest.json")["dossiers"] for o in read(case["construction"])}
    output.with_suffix(".html").write_text(planning_html(report["initial"], report["variant"], labels), encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "initial_shortfall_FTE_weeks": report["initial"]["proposed"]["total_shortfall_FTE_weeks"],
        "variant_feasible": report["variant"]["candidate"]["capacity_feasible"], "reservations_created": False, "report": str(output)}))
