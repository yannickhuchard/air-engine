"""Technical rehearsal of knowledge/baseline/change flows for all three dossiers."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from air import __version__
from air.core import FOUNDATION_PROFILE, digest
from air.foundation import InvalidModel, exact, resolved, validate_graph
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria"


def read(name):
    path = (FIXTURE / name).resolve()
    if not path.is_relative_to(FIXTURE.resolve()):
        raise ValueError("Fixture path escapes its directory")
    return json.loads(path.read_text(encoding="utf-8"))


def rehearse():
    manifest = read("manifest.json")
    temp_root = ROOT / "tmp"
    temp_root.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="air-foundation-", dir=temp_root) as directory:
        store = Store(f"sqlite:///{(Path(directory) / 'enterprise.db').as_posix()}")
        restored = Store(f"sqlite:///{(Path(directory) / 'restored.db').as_posix()}")
        try:
            store.migrate()
            restored.migrate()
            for case in manifest["dossiers"]:
                objects = read(case["foundation"])
                request = read(case["baseline_request"])
                original_report = validate_graph(objects)
                if not original_report["valid"]:
                    raise InvalidModel("Fixture graph failed", original_report)
                store.put_bundle(objects, "synthetic-architect")
                base = store.create_baseline(request, "synthetic-architect")
                exported = store.export_baseline(exact(base["baseline"]))
                restored.put_bundle(exported["objects"], "synthetic-restore")
                recovered = restored.create_baseline(request, "synthetic-restore")
                if recovered["digest"] != base["digest"]:
                    raise AssertionError("Restore changed the baseline")
                assumption = deepcopy(next(obj for obj in objects if obj["meta"]["type"] == "air.Assumption"))
                before = resolved(assumption)
                assumption["meta"]["revision"] = 2
                assumption["body"]["validation_plan"] += " Conserver le compte rendu et les écarts identifiés."
                store.put(assumption, "synthetic-architect")
                meta = deepcopy(request["meta"])
                meta.update(id="urn:asteria:change:" + case["id"].lower(), type="air.ChangeSet", name="Préciser la vérification — " + case["id"])
                change = {"meta": meta, "body": {"base": exact(base["baseline"]),
                    "operations": [{"op": "REPLACE", "before": before, "after": resolved(assumption)}],
                    "rationale": "Rendre la vérification de l’hypothèse plus traçable, sans la déclarer confirmée.",
                    "expected_revisions": base["baseline"]["body"]["members"], "approvals": []}}
                proposal = store.propose_change(change, "synthetic-architect")
                repeated = store.propose_change(change, "synthetic-architect")
                if repeated["change"]["created"] or repeated["target"]["created"]:
                    raise AssertionError("Proposal replay was not idempotent")
                if store.export_baseline(exact(base["baseline"]))["digest"] != base["digest"]:
                    raise AssertionError("Original baseline was modified")
                source_id = next(obj["meta"]["id"] for obj in objects
                                 if obj["meta"]["type"] == "air.Source" and obj["meta"]["namespace"] != "asteria.shared")
                incomplete = validate_graph([obj for obj in objects if obj["meta"]["id"] != source_id])
                if incomplete["valid"] or incomplete["rule_results"][0]["result"] != "VIOLATED":
                    raise AssertionError("Missing reference was accepted")
                results.append({"dossier": case["id"], "title": case["title"], "technical_flow": "PASS",
                    "members": len(objects), "baseline": exact(base["baseline"]), "digest": base["digest"],
                    "restored_digest": recovered["digest"], "proposal": proposal,
                    "missing_reference": incomplete["rule_results"], "open_unknowns": original_report["open_unknowns"],
                    "business_acceptance": "NOT_READY"})
            return {"version": __version__, "profile": FOUNDATION_PROFILE, "company": manifest["company"]["name"],
                    "status": "PASS", "scope": "Knowledge, closure, immutable baselines, change proposals and content restore",
                    "dossiers": results, "business_demo_ready": False,
                    "remaining": ["requirements/functions/contracts/construction units", "fine-grained authorization",
                                  "evidence qualification and approval", "cross-project impact", "generated business views"],
                    "live_instance_modified": False, "full_registry_restore": "NOT_EXECUTED"}
        finally:
            store.engine.dispose()
            restored.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-asteria/foundation.json")
    args = parser.parse_args()
    report = rehearse()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "dossiers": len(report["dossiers"]),
                      "business_demo_ready": False, "report": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
