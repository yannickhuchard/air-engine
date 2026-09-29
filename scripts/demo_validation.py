"""Execute diagnostic gates for the three fictional Asteria dossiers."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from air import __version__
from air.foundation import exact
from air.gates import PROFILE, validate_gate
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria"


def read(name):
    path = (FIXTURE / name).resolve()
    if not path.is_relative_to(FIXTURE.resolve()):
        raise ValueError("Fixture path escapes its directory")
    return json.loads(path.read_text(encoding="utf-8"))


def request_for(case, base, corrected=False):
    scenario = read(case["validation"])
    return {"profile": PROFILE, "gate": "foundation-review",
            "baseline": {**exact(base["baseline"]), "digest": base["digest"]},
            "rule_set": scenario["rule_set"],
            "inputs": scenario["corrected_inputs" if corrected else "initial_inputs"]}


def rehearse():
    temp_root = ROOT / "tmp"
    temp_root.mkdir(exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="air-validation-", dir=temp_root) as directory:
        store = Store(f"sqlite:///{(Path(directory) / 'enterprise.db').as_posix()}")
        try:
            store.migrate()
            for case in read("manifest.json")["dossiers"]:
                store.put_bundle(read(case["foundation"]), "synthetic-architect")
                base = store.create_baseline(read(case["baseline_request"]), "synthetic-architect")
                counts, audit = store.counts(), store.audit_log()
                request = request_for(case, base)
                initial = validate_gate(store, request)
                repeated = validate_gate(store, deepcopy(request))
                corrected = validate_gate(store, request_for(case, base, corrected=True))
                scenario = read(case["validation"])
                assert initial == repeated
                assert initial["results"][0]["result"] == scenario["expected_initial_result"]
                assert corrected["results"][0]["result"] == "SATISFIED"
                for report in (initial, corrected):
                    assert report["gate_decision"] == "BLOCKED" and not report["authorization_granted"]
                    assert any(b["code"] == "AIR_GATE_BLOCKING_UNKNOWNS" for b in report["blockers"])
                    assert report["results"][1]["execution"] == "NOT_EXECUTED"
                assert store.counts() == counts and store.audit_log() == audit
                cases.append({"dossier": case["id"], "title": case["title"], "status": "PASS",
                              "initial": initial, "corrected_inputs_only": corrected, "replay_identical": True})
        finally:
            store.engine.dispose()
    return {"version": __version__, "profile": PROFILE, "status": "PASS", "dossiers": cases,
            "business_demo_ready": False, "live_instance_modified": False,
            "scope": "Synthetic diagnostic checks, not authenticated business evidence or approval"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-asteria/validation.json")
    args = parser.parse_args()
    report = rehearse()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "dossiers": len(report["dossiers"]),
                      "business_demo_ready": False, "report": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
