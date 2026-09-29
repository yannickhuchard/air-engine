"""Structural construction traceability, without executing acceptance cases."""
import json
from air.core import CONSTRUCTION_PROFILE, PROFILE_TYPES, REF, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key, validate_graph


def validate_construction(objects, profile=CONSTRUCTION_PROFILE):
    report = validate_graph(objects, profile)
    report.update(construction_ready=False, authorization_granted=False, traceability=[], verification_cases=[])
    if not report["valid"]:
        report["construction_execution"] = "NOT_EXECUTED"
        return report
    by_ref = {key(exact(o)): o for o in objects}
    groups = {}
    for obj in objects:
        groups.setdefault(obj["meta"]["type"], []).append(obj)

    def issue(code, obj, message, suffix="", **detail):
        report["diagnostics"].append({"code": code, "path": (obj["meta"]["id"] if obj else "") + suffix, "message": message,
                                      **({"object": {**exact(obj), "type": obj["meta"]["type"]}} if obj else {}), **detail})

    def target(ref):
        return by_ref[key(ref)]

    def keys(refs):
        return {key(r) for r in refs}

    contracts_by_function, units_by_realization = {}, {}
    for criterion in groups.get("air.AcceptanceCriterion", []):
        if not criterion["body"]["cases"]:
            issue("AIR_ACCEPTANCE_CASES", criterion, "Construction acceptance needs at least one verification case")
        for ref in criterion["body"]["cases"]:
            if target(ref)["body"]["method"] != criterion["body"]["verification_method"]:
                issue("AIR_ACCEPTANCE_METHOD", criterion, "Criterion and verification case methods differ")
    for contract in groups.get("air.SemanticContract", []):
        errors = keys([e["failure_mode"] for e in contract["body"]["error_contract"]])
        promised_effects = {json.dumps(e, sort_keys=True) for e in contract["body"]["state_effects"]}
        for op in contract["body"]["operations"]:
            fn = target(op["function"])
            contracts_by_function.setdefault(key(op["function"]), []).append(contract)
            if not keys(fn["body"]["exceptions"]) <= errors:
                issue("AIR_CONTRACT_ERRORS", contract, "Contract omits a failure mode of operation " + op["name"], "#operations/" + op["name"],
                      operation=op["name"], function=exact(fn), missing_failure_modes=sorted([{"id": i, "revision": r} for i, r in keys(fn["body"]["exceptions"]) - errors], key=lambda r: (r["id"], r["revision"])),
                      fix="Add an error_contract entry for each missing failure mode, or remove it from the function exceptions")
            missing = [e for e in fn["body"]["effects"] if json.dumps(e, sort_keys=True) not in promised_effects]
            if missing:
                issue("AIR_CONTRACT_EFFECTS", contract, "Contract omits a state effect of operation " + op["name"], "#operations/" + op["name"],
                      operation=op["name"], function=exact(fn), missing_state_effects=missing,
                      fix="Copy these function effects into the contract state_effects, exactly as declared on the function")
    for unit in groups.get("air.ConstructionUnit", []):
        body = unit["body"]
        realized = keys(body["realizes"])
        for ref in body["realizes"]:
            units_by_realization.setdefault(key(ref), []).append(unit)
            obj = target(ref)
            if obj["meta"]["type"] == "air.SemanticContract":
                if not keys([op["function"] for op in obj["body"]["operations"]]) <= realized:
                    issue("AIR_UNIT_OPERATIONS", unit, "Unit must explicitly realize the operations of its contracts")
        estimate = target(body["estimate"])
        if estimate["body"]["target"] != exact(unit):
            issue("AIR_ESTIMATE_TARGET", unit, "Estimate must target this exact unit revision")
        satisfied = {key(r) for ref in body["realizes"] if target(ref)["meta"]["type"] == "air.Function"
                     for r in target(ref)["body"]["satisfies"]}
        if not keys(body["justified_by"]) <= satisfied:
            issue("AIR_UNIT_JUSTIFICATION", unit, "Unit justification must be satisfied by a realized function")
    functions_by_requirement = {}
    for fn in groups.get("air.Function", []):
        for ref in fn["body"]["satisfies"]:
            functions_by_requirement.setdefault(key(ref), []).append(fn)
        if not contracts_by_function.get(key(exact(fn))):
            issue("AIR_FUNCTION_CONTRACT", fn, "Function has no semantic contract in the baseline")
        if not units_by_realization.get(key(exact(fn))):
            issue("AIR_FUNCTION_REALIZATION", fn, "Function has no construction unit in the baseline")
    for kind in ("air.Requirement", "air.Function", "air.SemanticContract", "air.ConstructionUnit"):
        if not groups.get(kind):
            issue("AIR_CONSTRUCTION_EMPTY", None, "Construction profile needs at least one " + kind)
    for req in groups.get("air.Requirement", []):
        linked = False
        for fn in functions_by_requirement.get(key(exact(req)), []):
            for contract in contracts_by_function.get(key(exact(fn)), []):
                for unit in units_by_realization.get(key(exact(fn)), []):
                    if key(exact(contract)) not in keys(unit["body"]["realizes"]) or key(exact(req)) not in keys(unit["body"]["justified_by"]):
                        continue
                    linked = True
                    acceptance = req["body"]["acceptance"]
                    if not keys(acceptance) <= keys(unit["body"]["acceptance"]):
                        issue("AIR_UNIT_ACCEPTANCE", unit, "Unit omits a realized requirement acceptance criterion")
                    case_refs = []
                    permitted = {key(exact(o)) for o in (req, fn, contract, unit)}
                    for criterion_ref in acceptance:
                        criterion = target(criterion_ref)
                        matching = [ref for ref in criterion["body"]["cases"] if key(target(ref)["body"]["target"]) in permitted]
                        if not matching:
                            issue("AIR_REQUIREMENT_VERIFICATION", req, "Acceptance criterion lacks a case targeting this realization chain")
                        case_refs.extend(matching)
                    report["traceability"].append({"requirement": exact(req), "function": exact(fn),
                        "contract": exact(contract), "unit": exact(unit), "acceptance": acceptance,
                        "verification_cases": sorted({key(r): r for r in case_refs}.values(), key=key),
                        "estimate": unit["body"]["estimate"]})
                    if len(report["traceability"]) > 4096:
                        raise InvalidModel("Construction traceability exceeds 4096 paths; narrow the baseline")
        if req["body"]["priority"] == "MUST" and not linked:
            issue("AIR_REQUIRED_REALIZATION", req, "Mandatory requirement lacks a complete function/contract/unit chain")
    report["traceability"].sort(key=lambda r: tuple(key(r[f]) for f in ("requirement", "function", "contract", "unit")))
    runs = {}
    for run in sorted(groups.get("air.VerificationRun", []), key=lambda r: r["body"]["executed_at"]):
        runs[key(run["body"]["case"])] = run
    def status(case):
        run = runs.get(key(exact(case)))
        if run is None:
            return {"execution": "NOT_EXECUTED", "result": "UNKNOWN", "reason": "No recorded VerificationRun for this case in the baseline"}
        return {"execution": "RECORDED_RUN", "result": run["body"]["result"], "proof_level": run["body"]["proof_level"], "run": exact(run)}
    report["verification_cases"] = [{"case": exact(case), "target": case["body"]["target"], "method": case["body"]["method"], **status(case)}
        for case in sorted(groups.get("air.VerificationCase", []), key=lambda o: key(exact(o)))]
    report["valid"] = not report["diagnostics"]
    report["construction_ready"] = report["valid"]
    report["construction_execution"] = "EXECUTED"
    report["coverage"]["executed"].append("construction-structure/0.4")
    report["decision_note"] = "Structural design checks only; verification cases, human authority and business execution remain unverified"
    report["ready_to_build"] = {"decided_by": "air_assess_readiness",
        "note": "construction_ready means the construction chain is structurally complete, not that the dossier is ready to build"}
    return report


def assess_baseline(store, request):
    from air.storage import Conflict
    check_schema(request, record({"baseline": record({**REF["properties"],
        "digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}})}))
    ref = request["baseline"]
    exported = store.export_baseline({"id": ref["id"], "revision": ref["revision"]})
    if exported["digest"] != ref["digest"]:
        raise Conflict("Construction assessment targets another baseline digest")
    profile = exported["baseline"]["body"]["profiles"][0]
    # Any profile that carries the construction types can be assessed; richer dossiers need no second baseline.
    if not set(PROFILE_TYPES[CONSTRUCTION_PROFILE]) <= set(PROFILE_TYPES.get(profile, [])):
        raise InvalidModel("Construction assessment requires a profile that includes the construction types")
    report = validate_construction(exported["objects"], profile)
    blockers = []
    if not report["valid"]:
        blockers.append("AIR_CONSTRUCTION_INVALID")
    if report["verification_cases"]:
        blockers.append("AIR_CONSTRUCTION_VERIFICATION_PENDING")
    if any(u["blocking_policy"] == "BLOCK" for u in report.get("open_unknowns", [])):
        blockers.append("AIR_GATE_BLOCKING_UNKNOWNS")
    if any(o["meta"]["type"] == "air.Assertion" and o["body"]["epistemic_status"] == "CONTESTED" for o in exported["objects"]):
        blockers.append("AIR_GATE_CONTESTED_ASSERTIONS")
    blockers.append("AIR_CONSTRUCTION_AUTHORITY_PENDING")
    report.update(baseline=ref, engine="air.construction/0.4", blockers=blockers, gate_decision="BLOCKED",
                  validation_scope={"checked": "Construction traceability under " + profile + ": requirement, function, contract, unit and verification chain",
                                    "not_checked": ["Structural architecture checks: air_inspect_architecture", "Execution of verification cases"]},
                  request_digest=artifact_digest(request))
    report["report_digest"] = artifact_digest(report)
    return report
