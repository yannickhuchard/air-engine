"""Replayable diagnostic gates on immutable baselines; no approval or admission."""
from air.core import FOUNDATION_PROFILE, REF, record
from air.expr import (ENGINE, Budget, ExprError, Program, artifact_digest, bounded,
                      evaluate, fields, require, typed)
from air.foundation import InvalidModel, check_schema, exact
from air.storage import Conflict

PROFILE = "air.validation/0.3"
GATE = "foundation-review"
GATE_STEPS = 20000


def check_request(request):
    try:
        bounded(request)
        fields(request, ("profile", "gate", "baseline", "rule_set", "inputs"))
        require(request["profile"] == PROFILE and request["gate"] == GATE, "Unsupported validation profile or gate")
        check_schema(request["baseline"], record({**REF["properties"], "digest": {
            "type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}}))
        ruleset = request["rule_set"]
        fields(ruleset, ("id", "version", "rules"))
        for name in ("id", "version"):
            require(isinstance(ruleset[name], str) and 1 <= len(ruleset[name]) <= 128, "Invalid rule set identity")
        rules = ruleset["rules"]
        require(isinstance(rules, list) and 1 <= len(rules) <= 64, "Rule set must contain 1..64 rules")
        seen, declared = set(), {}
        for rule in rules:
            fields(rule, ("id", "version", "mandatory", "method", "applicability"), ("predicate",))
            for name in ("id", "version"):
                require(isinstance(rule[name], str) and 1 <= len(rule[name]) <= 128, "Invalid rule identity")
            require(not rule["id"].startswith(("AIR-", "air.")), "Built-in and normative rule identities are reserved")
            require(rule["id"] not in seen, "Duplicate rule identity")
            seen.add(rule["id"])
            require(type(rule["mandatory"]) is bool, "mandatory must be Boolean")
            require(rule["method"] in ("EXPRESSION", "MANUAL"), "Unsupported check method")
            require(("predicate" in rule) == (rule["method"] == "EXPRESSION"), "Unexpected or missing predicate")
            for expr in [rule["applicability"]] + ([rule["predicate"]] if "predicate" in rule else []):
                program = Program(expr)
                require(expr["result_type"] == "Boolean", "Rules must evaluate to Boolean")
                for name, t in program.inputs.items():
                    require(name not in declared or declared[name] == t, "Conflicting input declarations")
                    declared[name] = t
        require(isinstance(request["inputs"], dict) and len(request["inputs"]) <= 256, "Invalid inputs")
        for name, value in request["inputs"].items():
            require(name.startswith("inputs.") and name in declared, "Unexpected input or attempt to override baseline facts")
            require(typed(value).type == declared[name], "Input declaration mismatch")
        for name in declared:
            require(name.startswith("inputs.") or name in ("baseline.member_count", "baseline.blocking_unknown_count",
                    "baseline.contested_assertion_count", "baseline.closed"), "Property is not authorized")
        return declared
    except ExprError as exc:
        raise InvalidModel(str(exc), {"diagnostics": [{"code": exc.code}]}) from exc


def validate_gate(store, request):
    declared = check_request(request)
    # Export verifies every exact member and its digest before evaluation, with no write transaction.
    exported = store.export_baseline({"id": request["baseline"]["id"], "revision": request["baseline"]["revision"]})
    if exported["digest"] != request["baseline"]["digest"]:
        raise Conflict("Baseline digest differs from the requested immutable snapshot")
    if exported["baseline"]["body"]["profiles"] != [FOUNDATION_PROFILE]:
        raise InvalidModel("foundation-review requires a foundation baseline; use the construction assessment for construction baselines")
    graph = exported["validation"]
    unknowns = [u["reference"] for u in graph["open_unknowns"] if u["blocking_policy"] == "BLOCK"]
    contested = [exact(o) for o in exported["objects"] if o["meta"]["type"] == "air.Assertion"
                 and o["body"]["epistemic_status"] == "CONTESTED"]
    facts = {"baseline.member_count": {"type": "Integer", "value": len(exported["objects"])},
             "baseline.blocking_unknown_count": {"type": "Integer", "value": len(unknowns)},
             "baseline.contested_assertion_count": {"type": "Integer", "value": len(contested)},
             "baseline.closed": {"type": "Boolean", "value": graph["valid"]}}
    if any(name in facts and declared[name] != facts[name]["type"] for name in declared):
        raise InvalidModel("Derived baseline fact type mismatch")
    context = {**request["inputs"], **facts}
    budget = Budget(GATE_STEPS)

    def run(expr):
        names = {x["name"] for x in expr.get("required_inputs", [])}
        return evaluate({"expression": expr, "inputs": {k: v for k, v in context.items() if k in names}}, budget)

    results = []
    blockers = []
    for rule in request["rule_set"]["rules"]:
        applicability = run(rule["applicability"])
        result = {"rule": rule["id"], "version": rule["version"], "mandatory": rule["mandatory"],
                  "applicability": applicability, "execution": "NOT_EXECUTED", "result": "UNKNOWN"}
        if applicability["execution"] != "EXECUTED":
            result["reason"] = "Applicability did not execute successfully"
        elif applicability["result"] == "VIOLATED":
            result.update(result="NOT_APPLICABLE", reason="Applicability evaluated to false")
        elif applicability["result"] != "SATISFIED":
            result.update(result=applicability["result"], reason="Applicability is uncertain")
        elif rule["method"] == "MANUAL":
            result["reason"] = "Authenticated human review is not implemented; supplied approvals are not accepted"
        else:
            evaluation = run(rule["predicate"])
            result.update(execution=evaluation["execution"], result=evaluation["result"], evaluation=evaluation)
        results.append(result)
        if rule["mandatory"] and result["result"] not in ("SATISFIED", "NOT_APPLICABLE"):
            blockers.append({"code": "AIR_GATE_REQUIRED_RULE", "rule": rule["id"], "result": result["result"]})
    if unknowns:
        blockers.append({"code": "AIR_GATE_BLOCKING_UNKNOWNS", "references": unknowns})
    if contested:
        blockers.append({"code": "AIR_GATE_CONTESTED_ASSERTIONS", "references": contested})
    # Even optional calculations cannot conceal malformed or exhausted execution.
    if any(r["applicability"]["execution"] != "EXECUTED" or r["execution"] in ("ERROR", "BUDGET_EXCEEDED") for r in results):
        blockers.append({"code": "AIR_GATE_INCOMPLETE_EXECUTION"})
    report = {"profile": PROFILE, "engine": ENGINE, "gate": GATE,
              "baseline": request["baseline"], "request_digest": artifact_digest(request),
              "rule_set": {"id": request["rule_set"]["id"], "version": request["rule_set"]["version"],
                           "digest": artifact_digest(request["rule_set"])},
              "inputs_digest": artifact_digest(request["inputs"]), "derived_facts": facts,
              "results": results, "blockers": blockers,
              "gate_decision": "BLOCKED" if blockers else "PASSED",
              "decision_ready": False, "authorization_granted": False,
              "policy_authority": "CALLER_SUPPLIED_DIAGNOSTIC_ONLY",
              "coverage": {"scope": "Exact foundation baseline and supplied rule set only",
                           "normative": graph["coverage"],
                           "executed": [r["rule"] for r in results if r["execution"] == "EXECUTED"],
                           "not_executed": [r["rule"] for r in results if r["execution"] == "NOT_EXECUTED"],
                           "failed": [r["rule"] for r in results if r["execution"] in ("ERROR", "BUDGET_EXCEEDED")]},
              "cost": {"steps": budget.used, "limit": budget.limit}}
    report["report_digest"] = artifact_digest(report)
    return report
