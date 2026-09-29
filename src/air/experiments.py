"""Finite deterministic experiments using AIR-Expr, with explicit illustrative evidence."""
from air.core import TEXT, record, digest
from air.expr import Budget, ENGINE as EXPR_ENGINE, ExprError, Program, artifact_digest, bounded, evaluate, typed, wire
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot

ENGINE = "air.experiments/0.6"
NAME = {"pattern": "^[a-zA-Z][a-zA-Z0-9_.-]{0,127}$"}
MAP = {"type": "object", "maxProperties": 256, "propertyNames": NAME, "additionalProperties": {"type": "object"}}
MODEL = record({"function": SNAPSHOT, "description": TEXT, "limitations": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 32},
    "measures": {**MAP, "minProperties": 1, "maxProperties": 16}})
REQUEST = record({"baseline": SNAPSHOT, "question": TEXT, "model": MODEL,
    "model_digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
    "scenarios": {"type": "array", "minItems": 1, "maxItems": 32, "items": record({
        "id": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_.-]{0,127}$"},
        "verification_case": SNAPSHOT, "inputs": MAP, "expected": MAP})}})


def simulate(store, request):
    try:
        bounded(request)
        check_schema(request, REQUEST)
        if artifact_digest(request["model"]) != request["model_digest"]:
            raise InvalidModel("Model digest does not match the replay artifact")
        baseline = snapshot(store, request["baseline"])
        objects = {key(exact(o)): o for o in baseline["objects"]}
        def target(pin, kind):
            obj = objects.get(key(pin))
            if obj is None or obj["meta"]["type"] != kind or digest(obj) != pin["digest"]:
                raise InvalidModel("Experiment target must be exactly pinned in the supplied baseline")
            return obj
        function = target(request["model"]["function"], "air.Function")
        programs = {name: Program(expr) for name, expr in request["model"]["measures"].items()}
        if sum(p.nodes for p in programs.values()) > 4096:
            raise InvalidModel("Combined experiment expressions exceed 4096 nodes")
        inputs = {}
        for program in programs.values():
            for name, type_name in program.inputs.items():
                if name in inputs and inputs[name] != type_name: raise InvalidModel("Conflicting model input types")
                inputs[name] = type_name
        seen = set()
        for scenario in request["scenarios"]:
            if scenario["id"] in seen: raise InvalidModel("Duplicate scenario id")
            seen.add(scenario["id"])
            case = target(scenario["verification_case"], "air.VerificationCase")
            if key(case["body"]["target"]) != key(exact(function)):
                raise InvalidModel("Verification case targets a different function")
            if set(scenario["inputs"]) - set(inputs): raise InvalidModel("Scenario contains undeclared input")
            for name, value in scenario["inputs"].items():
                if typed(value).type != inputs[name]: raise InvalidModel("Scenario input type mismatch")
            if set(scenario["expected"]) != set(programs): raise InvalidModel("Independent expected values are required for every measure")
            for name, value in scenario["expected"].items():
                oracle = typed(value)
                if oracle.state != "KNOWN" or oracle.type != programs[name].expression["result_type"]:
                    raise InvalidModel("Oracle values must be known and match measure types")
    except ExprError as exc:
        raise InvalidModel("Invalid experiment expression or input: " + exc.code) from exc
    budget = Budget(limit=20000)
    outcomes, comparisons = [], []
    for scenario in sorted(request["scenarios"], key=lambda s: s["id"]):
        measures = []
        for name, program in sorted(programs.items()):
            context = {n: v for n, v in scenario["inputs"].items() if n in program.inputs}
            observation = evaluate({"expression": program.expression, "inputs": context}, budget)
            expected = wire(typed(scenario["expected"][name]))
            if observation["execution"] != "EXECUTED": result = "UNKNOWN"
            elif observation["value"].get("state") in ("UNKNOWN", "CONFLICTING"): result = observation["value"]["state"]
            else: result = "SATISFIED" if observation["value"] == expected else "VIOLATED"
            comparisons.append(result)
            measures.append({"name": name, "observation": observation, "expected": expected, "comparison": result})
        outcomes.append({"scenario": scenario["id"], "verification_case": scenario["verification_case"], "measures": measures})
    result = next((s for s in ("CONFLICTING", "VIOLATED", "UNKNOWN") if s in comparisons), "SATISFIED")
    normalized = {**request, "scenarios": sorted(request["scenarios"], key=lambda s: s["id"])}
    report = {"engine": ENGINE, "expression_engine": EXPR_ENGINE, "baseline": request["baseline"], "question": request["question"],
        "model_digest": request["model_digest"], "request_digest": artifact_digest(normalized), "evidence_class": "ILLUSTRATIVE",
        "reproducibility": "DETERMINISTIC_RECALCULATION", "repetitions": 1, "random_seeds": None,
        "result": result, "outcomes": outcomes, "cost": {"steps": budget.used, "limit": budget.limit},
        "external_effects": False, "authorization_granted": False, "business_verification_granted": False,
        "limitations": request["model"]["limitations"] + ["Finite declared scenarios and simplified expressions only",
            "The model and its oracle require independent review; no independence is inferred from their separation",
            "No observed runtime, calibrated model, statistical inference or automatic promotion of VerificationCase"]}
    report["report_digest"] = artifact_digest(report)
    return report
