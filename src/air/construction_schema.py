"""Versioned construction subset. Imported after core schema primitives exist."""

NAMES = ["Requirement", "AcceptanceCriterion", "Function", "Actor", "FailureMode",
         "SemanticContract", "ConstructionUnit", "VerificationCase", "Estimate"]
PROFILE = "air.construction/0.4"


def bodies(record, text, uri, ref, refs, nonempty):
    def array(items, minimum=0):
        return {"type": "array", "items": items, "minItems": minimum, "maxItems": 1000}
    texts = array(text)
    method = {"enum": ["TEST", "ANALYSIS", "INSPECTION", "SIMULATION", "REVIEW"]}
    parameter = record({"name": text, "data_type": text, "description": text})
    effect = record({"kind": {"enum": ["STATE_CHANGE", "EVENT", "HUMAN_ACTION", "PHYSICAL_ACTION"]}, "description": text})
    return {
        "air.Requirement": record({"statement": text, "kind": {"enum": ["FUNCTIONAL", "QUALITY", "CONSTRAINT"]},
            "priority": {"enum": ["MUST", "SHOULD", "COULD"]}, "applicability": text, "acceptance": nonempty, "source": nonempty}),
        "air.AcceptanceCriterion": record({"condition": text, "verification_method": method,
            "acceptance_authority": uri, "cases": refs}),
        "air.Function": record({"kind": {"enum": ["BUSINESS", "SOFTWARE", "HUMAN", "PHYSICAL"]},
            "inputs": array(parameter), "outputs": array(parameter), "preconditions": texts,
            "postconditions": array(text, 1), "effects": array(effect), "exceptions": refs,
            "atomic": {"type": "boolean"}, "satisfies": nonempty}),
        "air.Actor": record({"kind": {"enum": ["HUMAN", "ORGANIZATION", "SOFTWARE", "AGENT", "DEVICE", "MACHINE", "ROBOT"]},
            "roles": {**refs, "maxItems": 128}, "boundary": ref}),
        "air.FailureMode": record({"trigger": text, "effect": text, "detection": text,
            "response": text, "recovery_condition": text}),
        "air.SemanticContract": record({"operations": array(record({"name": text, "function": ref}), 1),
            "participants": array(record({"actor": ref, "role": text}), 1), "authorization": text,
            "state_effects": array(effect), "error_contract": array(record({"code": text, "failure_mode": ref, "response": text})),
            "quality": {"type": "array", "maxItems": 0}, "compatibility_policy": text}),
        "air.ConstructionUnit": record({"realizes": nonempty,
            "work_kind": {"enum": ["SOFTWARE", "CONFIGURATION", "PROCESS", "TRAINING", "PHYSICAL"]},
            "outputs": array(record({"name": text, "kind": text, "description": text}), 1),
            "acceptance": nonempty, "justified_by": nonempty,
            "resource_demand": {"type": "array", "maxItems": 0}, "estimate": ref}),
        "air.VerificationCase": record({"target": ref, "method": method, "inputs": array(parameter),
            "oracle": text, "acceptance": text, "independence_basis": text}),
        "air.Estimate": record({"target": ref, "measure": {"enum": ["effort", "duration"]},
            "value_or_distribution": record({"value": {"type": "string", "pattern": "^(?:0|[1-9][0-9]{0,17})(?:\\.[0-9]{1,6})?$"},
                                             "unit": {"enum": ["person_day", "second"]}}),
            "basis": array(text, 1), "scope_assumptions": refs, "calibration_class": text}),
    }


MANY = {
    "air.Requirement": {"acceptance": ["air.AcceptanceCriterion"], "source": ["air.Source", "air.Assertion"]},
    "air.AcceptanceCriterion": {"cases": ["air.VerificationCase"]},
    "air.Function": {"exceptions": ["air.FailureMode"], "satisfies": ["air.Requirement"]},
    "air.ConstructionUnit": {"realizes": ["air.Function", "air.SemanticContract"],
                             "acceptance": ["air.AcceptanceCriterion"], "justified_by": ["air.Requirement"]},
    "air.Estimate": {"scope_assumptions": ["air.Assumption"]},
}
ONE = {
    "air.Actor": {"boundary": ["air.Scope"]},
    "air.ConstructionUnit": {"estimate": ["air.Estimate"]},
    "air.Estimate": {"target": ["air.ConstructionUnit"]},
    "air.VerificationCase": {"target": ["air.Requirement", "air.Function", "air.SemanticContract", "air.ConstructionUnit", "air.BusinessRule", "air.Constraint", "air.Control"]},
}


def slots(obj):
    body, kind = obj["body"], obj["meta"]["type"]
    for field, kinds in MANY.get(kind, {}).items():
        for ref in body[field]:
            yield "body/" + field, ref, kinds
    for field, kinds in ONE.get(kind, {}).items():
        yield "body/" + field, body[field], kinds
    if kind == "air.SemanticContract":
        for field, link, target in [("operations", "function", "air.Function"),
                                    ("participants", "actor", "air.Actor"),
                                    ("error_contract", "failure_mode", "air.FailureMode")]:
            for i, item in enumerate(body[field]):
                yield f"body/{field}/{i}/{link}", item[link], [target]


def local_issues(obj):
    body, kind = obj["body"], obj["meta"]["type"]
    named = {"air.Function": ["inputs", "outputs"], "air.VerificationCase": ["inputs"],
             "air.ConstructionUnit": ["outputs"], "air.SemanticContract": ["operations", "error_contract"]}
    for field in named.get(kind, []):
        key = "code" if field == "error_contract" else "name"
        names = [item[key] for item in body[field]]
        if len(names) != len(set(names)):
            yield "AIR_CONSTRUCTION_DUPLICATE", "Duplicate name in " + field
    if kind == "air.Estimate":
        expected = {"effort": "person_day", "duration": "second"}[body["measure"]]
        if body["value_or_distribution"]["unit"] != expected:
            yield "AIR_ESTIMATE_UNIT", "Estimate measure and unit are incompatible"
