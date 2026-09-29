"""Rehearse construction traceability for three dossiers in one isolated registry."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from air import __version__
from air.construction import assess_baseline, validate_construction
from air.foundation import exact, resolved
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria"


def read(name):
    path = (FIXTURE / name).resolve()
    if not path.is_relative_to(FIXTURE.resolve()):
        raise ValueError("Fixture escapes its directory")
    return json.loads(path.read_text(encoding="utf-8"))


def rehearse():
    (ROOT / "tmp").mkdir(exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="air-construction-", dir=ROOT / "tmp") as directory:
        store = Store(f"sqlite:///{(Path(directory) / 'company.db').as_posix()}")
        restored = Store(f"sqlite:///{(Path(directory) / 'restored.db').as_posix()}")
        try:
            store.migrate()
            restored.migrate()
            for case in read("manifest.json")["dossiers"]:
                objects = read(case["construction"])
                request = read(case["construction_baseline_request"])
                store.put_bundle(objects, "synthetic-architect")
                base = store.create_baseline(request, "synthetic-architect")
                assessment_request = {"baseline": {**exact(base["baseline"]), "digest": base["digest"]}}
                report = assess_baseline(store, assessment_request)
                assert report["construction_ready"] and len(report["traceability"]) == 1
                assert report["gate_decision"] == "BLOCKED" and not report["authorization_granted"]
                assert len(report["verification_cases"]) == 3
                assert report == assess_baseline(store, assessment_request)
                exported = store.export_baseline(exact(base["baseline"]))
                restored.put_bundle(exported["objects"], "synthetic-restore")
                recovered = restored.create_baseline(request, "synthetic-restore")
                assert recovered["digest"] == base["digest"]
                broken = deepcopy(objects)
                next(o for o in broken if o["meta"]["type"] == "air.SemanticContract")["body"]["error_contract"] = []
                negative = validate_construction(broken)
                assert not negative["valid"] and any(d["code"] == "AIR_CONTRACT_ERRORS" for d in negative["diagnostics"])
                unit = deepcopy(next(o for o in objects if o["meta"]["type"] == "air.ConstructionUnit"))
                estimate = deepcopy(next(o for o in objects if o["meta"]["type"] == "air.Estimate"))
                before = [resolved(unit), resolved(estimate)]
                for obj in (unit, estimate): obj["meta"]["revision"] = 2
                unit["body"]["estimate"] = exact(estimate)
                estimate["body"]["target"] = exact(unit)
                estimate["body"]["value_or_distribution"]["value"] = "15"
                store.put_bundle([unit, estimate], "synthetic-architect")
                meta = deepcopy(request["meta"])
                meta.update(id="urn:asteria:construction-change:" + case["id"], type="air.ChangeSet", name="Revoir une estimation synthétique")
                change = {"meta": meta, "body": {"base": exact(base["baseline"]),
                    "operations": [{"op": "REPLACE", "before": old, "after": resolved(new)} for old, new in zip(before, [unit, estimate])],
                    "rationale": "Réviser l’estimation sans approuver ni réserver de capacité.",
                    "expected_revisions": base["baseline"]["body"]["members"], "approvals": []}}
                proposal = store.propose_change(change, "synthetic-architect")
                assert proposal["target"]["baseline"]["body"]["profiles"] == ["air.construction/0.4"]
                assert not store.propose_change(change, "synthetic-architect")["change"]["created"]
                target = proposal["target"]
                assert assess_baseline(store, {"baseline": {**exact(target["baseline"]), "digest": target["digest"]}})["construction_ready"]
                assert store.export_baseline(exact(base["baseline"]))["digest"] == base["digest"]
                cases.append({"dossier": case["id"], "title": case["title"], "members": len(objects), "status": "PASS",
                    "assessment": report, "restored_digest": recovered["digest"], "negative_test": "AIR_CONTRACT_ERRORS",
                    "proposal_digest": target["digest"], "proposal_replay_identical": True, "original_unchanged": True})
        finally:
            store.engine.dispose()
            restored.engine.dispose()
    return {"version": __version__, "status": "PASS", "dossiers": cases,
            "business_demo_ready": False, "business_scenarios_executed": False, "live_instance_modified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-asteria/construction.json")
    args = parser.parse_args()
    report = rehearse()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "dossiers": 3, "business_demo_ready": False, "report": str(args.output)}))


if __name__ == "__main__":
    main()
