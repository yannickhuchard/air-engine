"""Explain a shared identity change across the three fictional dossiers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from air.core import digest, reference_slots
from air.foundation import exact, key, resolved
from air.projections import diff, impact, view
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def ref(base):
    return {**exact(base["baseline"]), "digest": base["digest"]}


def evolve(objects):
    changed = {"urn:asteria:scope:identity"}
    while True:
        expanded = changed | {o["meta"]["id"] for o in objects
                              if any(r["id"] in changed for _, r, _ in reference_slots(o))}
        if expanded == changed:
            break
        changed = expanded
    result = deepcopy(objects)
    for obj in result:
        if obj["meta"]["id"] in changed:
            obj["meta"]["revision"] += 1
            for _, r, _ in reference_slots(obj):
                if r["id"] in changed:
                    r["revision"] += 1
            if obj["meta"]["id"] == "urn:asteria:scope:identity":
                obj["body"]["boundary_description"] += " Les comptes collecteurs ont une échéance explicite et sont revalidés avant usage."
    return result


def rehearse(output=None):
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="air-projections-", dir=ROOT / "tmp") as folder:
        store = Store(f"sqlite:///{(Path(folder) / 'company.db').as_posix()}")
        try:
            store.migrate()
            bases, dossiers = [], []
            for case in read("manifest.json")["dossiers"]:
                objects = read(case["construction"])
                store.put_bundle(objects, "synthetic-architect")
                base = store.create_baseline(read(case["construction_baseline_request"]), "synthetic-architect")
                bases.append(ref(base))
                evolved = evolve(objects)
                store.put_bundle(evolved, "synthetic-architect")
                before = {o["meta"]["id"]: o for o in objects}
                operations = [{"op": "REPLACE", "before": resolved(before[o["meta"]["id"]]), "after": resolved(o)}
                              for o in evolved if digest(o) != digest(before[o["meta"]["id"]])]
                meta = deepcopy(base["baseline"]["meta"])
                meta.update(id="urn:asteria:identity-change:" + case["id"], type="air.ChangeSet")
                proposal = store.propose_change({"meta": meta, "body": {"base": exact(base["baseline"]), "operations": operations,
                    "rationale": "Proposer une durée explicite des comptes collecteurs ; revue métier encore nécessaire.",
                    "expected_revisions": base["baseline"]["body"]["members"], "approvals": []}}, "synthetic-architect")
                comparison = diff(store, {"before": ref(base), "after": ref(proposal["target"])})
                assert comparison["changes"] and not proposal["approved"]
                artifact = view(store, {"baseline": ref(base)})
                assert artifact == view(store, {"baseline": ref(base)})
                if output:
                    output.mkdir(parents=True, exist_ok=True)
                    (output / (case["id"] + ".html")).write_text(artifact["content"], encoding="utf-8", newline="\n")
                dossiers.append({"dossier": case["id"], "diff": comparison, "view_digest": artifact["digest"],
                                 "view_mapping_count": len(artifact["mapping"])})
            affected = impact(store, {"baselines": bases, "targets": [{"id": "urn:asteria:scope:identity", "revision": 1}]})
            assert all(item["affected"] and item["selected_targets"] for item in affected["baselines"])
            assert len(affected["baselines"]) == 3
            return {"status": "PASS", "dossiers": dossiers, "impact": affected, "business_demo_ready": False}
        finally:
            store.engine.dispose()


if __name__ == "__main__":
    output = ROOT / "tmp/demo-asteria/views"
    result = rehearse(output)
    (output.parent / "projections.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "dossiers": 3, "views": str(output)}))
