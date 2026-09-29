"""Illustrative finite experiments for the three fictional Asteria contracts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from air.core import digest
from air.expr import artifact_digest
from air.experiments import simulate
from air.foundation import exact
from air.storage import Store
from demo_projections import read, ref
ROOT = Path(__file__).resolve().parents[1]


def boolean(value): return {"type": "Boolean", "value": value}


def expression(ast, inputs, result_type="Boolean"):
    return {"language": "AIR-Expr", "language_version": "0.1", "result_type": result_type,
        "required_inputs": [{"name": n, "type": t} for n, t in inputs.items()], "ast": ast}


def request_for(store, case):
    objects = read(case["construction"])
    store.put_bundle(objects, "synthetic-architect")
    base = store.create_baseline(read(case["construction_baseline_request"]), "synthetic-architect")
    function = next(o for o in objects if o["meta"]["type"] == "air.Function")
    cases = sorted([o for o in objects if o["meta"]["type"] == "air.VerificationCase"], key=lambda o: o["meta"]["id"])
    pin = lambda o: {**exact(o), "digest": digest(o)}
    var = lambda name: {"ref": name}
    conjunction = lambda a, b: {"op": "and", "args": [a, b]}
    constant_false = expression({"literal": boolean(False)}, {})
    if case["id"] == "D01":
        accepted = conjunction(conjunction(var("authorized"), var("storage_available")), {"op": "not", "args": [var("duplicate")]})
        measures = {"new_registration": expression(accepted, {"authorized": "Boolean", "storage_available": "Boolean", "duplicate": "Boolean"}),
                    "guarantee_decided": constant_false}
        rows = [("nominal", 0, True, True, False, True), ("duplicate", 0, True, True, True, False),
                ("foreign_customer", 1, False, True, False, False), ("storage_down", 2, True, False, False, False)]
        scenarios = [{"id": name, "verification_case": pin(cases[index]),
            "inputs": {"authorized": boolean(auth), "storage_available": boolean(storage), "duplicate": boolean(duplicate)},
            "expected": {"new_registration": boolean(expected), "guarantee_decided": boolean(False)}}
            for name, index, auth, storage, duplicate, expected in rows]
    elif case["id"] == "D02":
        fresh = {"op": "lte", "args": [var("age"), {"literal": {"type": "Duration", "value": "300"}}]}
        measures = {"inspection_proposed": expression(conjunction(fresh, conjunction(var("collector_valid"), var("unit_valid"))),
            {"age": "Duration", "collector_valid": "Boolean", "unit_valid": "Boolean"}), "machine_command": constant_false}
        rows = [("nominal", 0, "60", True, True, True), ("stale_measure", 1, "600", True, True, False),
                ("invalid_collector", 2, "60", False, True, False), ("wrong_unit", 2, "60", True, False, False)]
        scenarios = [{"id": name, "verification_case": pin(cases[index]),
            "inputs": {"age": {"type": "Duration", "value": age}, "collector_valid": boolean(collector), "unit_valid": boolean(unit)},
            "expected": {"inspection_proposed": boolean(expected), "machine_command": boolean(False)}}
            for name, index, age, collector, unit, expected in rows]
    else:
        measures = {"revocation_proposed": expression(conjunction(var("dates_consistent"), var("account_mapped")),
            {"dates_consistent": "Boolean", "account_mapped": "Boolean"}), "iam_command": constant_false}
        rows = [("nominal", 0, boolean(True), True, True), ("contradictory_dates", 1, {"type": "Boolean", "state": "CONFLICTING"}, True, False),
                ("unmapped_account", 2, boolean(True), False, False)]
        scenarios = [{"id": name, "verification_case": pin(cases[index]),
            "inputs": {"dates_consistent": dates, "account_mapped": boolean(mapped)},
            "expected": {"revocation_proposed": boolean(expected), "iam_command": boolean(False)}}
            for name, index, dates, mapped, expected in rows]
    model = {"function": pin(function), "description": "Modèle illustratif simplifié de " + function["meta"]["name"],
        "limitations": ["Données et logique synthétiques non calibrées", "Aucun système réel ni état persistant métier", "Les mesures couvrent quelques décisions, pas tout le contrat"], "measures": measures}
    return {"baseline": ref(base), "question": "Les décisions simulées restent-elles cohérentes avec les cas nominaux et interdits déclarés ?",
        "model": model, "model_digest": artifact_digest(model), "scenarios": scenarios}


def rehearse():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="air-experiments-", dir=ROOT / "tmp") as folder:
        store = Store("sqlite:///" + (Path(folder) / "air.db").as_posix())
        try:
            store.migrate();reports = []
            for case in read("manifest.json")["dossiers"]:
                request = request_for(store, case)
                before, audit = store.counts(), store.audit_log()
                result = simulate(store, request)
                assert result == simulate(store, deepcopy(request))
                assert result["result"] == ("CONFLICTING" if case["id"] == "D03" else "SATISFIED")
                assert result["evidence_class"] == "ILLUSTRATIVE" and not result["business_verification_granted"]
                assert store.counts() == before and store.audit_log() == audit
                reports.append({"dossier": case["id"], "request": request, "result": result})
            return {"status": "PASS_SCOPED", "dossiers": reports, "external_effects": False, "business_runtime_verified": False}
        finally: store.engine.dispose()


if __name__ == "__main__":
    result = rehearse()
    output = ROOT / "tmp/demo-asteria/experiments.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "dossiers": 3, "report": str(output)}))
