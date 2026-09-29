"""Closed snapshots and proposed changes, without publication or approval effects."""
from copy import deepcopy
import hashlib
from jsonschema import Draft202012Validator, FormatChecker
import rfc8785
from air.core import (DATA_TYPES, FOUNDATION_TYPES, CONSTRUCTION_PROFILE, FOUNDATION_PROFILE, RUNTIME_PROFILE, COLLABORATION_PROFILE, BUSINESS_PROFILE, KNOWLEDGE_PROFILE, AUDIENCE_PROFILE, ORGANIZATION_PROFILE, WORKFLOW_PROFILE, DATA_PROFILE, STATE_PROFILE, GOVERNANCE_PROFILE, ARCHITECTURE_PROFILE, DELIVERY_PROFILE, PROFILE_TYPES, infer_profile, META, NONEMPTY_REFS, REFS,
                      canonical, digest, record, reference_slots, validate)


class InvalidModel(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


class TooLarge(InvalidModel):
    """A bounded output or generated file would exceed its budget; the request is valid, the answer is too big."""


def key(ref):
    return ref["id"], ref["revision"]


def exact(obj):
    return {"id": obj["meta"]["id"], "revision": obj["meta"]["revision"]}


def resolved(obj):
    return {**exact(obj), "type": obj["meta"]["type"], "digest": digest(obj)}


def metadata_schema(kind):
    result = deepcopy(META)
    result["properties"]["type"] = {"const": kind}
    return result


BASELINE_REQUEST = record({"meta": metadata_schema("air.Baseline"),
    "profile": {"enum": [FOUNDATION_PROFILE, CONSTRUCTION_PROFILE, RUNTIME_PROFILE, COLLABORATION_PROFILE, BUSINESS_PROFILE, KNOWLEDGE_PROFILE, AUDIENCE_PROFILE, ORGANIZATION_PROFILE, WORKFLOW_PROFILE, DATA_PROFILE, STATE_PROFILE, GOVERNANCE_PROFILE, ARCHITECTURE_PROFILE, DELIVERY_PROFILE]}, "members": NONEMPTY_REFS, "parent_baselines": REFS})


def check_schema(value, definition):
    errors = list(Draft202012Validator(definition, format_checker=FormatChecker()).iter_errors(value))
    if errors:
        raise InvalidModel("Invalid request", {"diagnostics": [
            {"code": "AIR_SCHEMA", "path": "/".join(map(str, e.absolute_path)), "message": e.message}
            for e in errors]})


def validate_graph(objects, profile=None):
    objects = objects if isinstance(objects, list) else [objects]
    profile = profile or infer_profile(objects)
    report = validate(objects)
    report["profile"] = profile
    report["coverage"]["executed"].append("foundation-reference-types")
    report["coverage"]["reference_resolution"] = "EXECUTED" if report["valid"] else "NOT_EXECUTED"
    report["rule_results"] = []
    report["decision_ready"] = False
    report["decision_note"] = "Closed snapshot only; diagnostic gates are a separate operation; review receipts are separate and do not grant execution authority"
    if not report["valid"]:
        report["rule_results"].append({"rule": "AIR-V003", "execution": "NOT_EXECUTED", "result": "UNKNOWN",
                                       "profile": profile, "reason": "Invalid input schemas"})
        return report
    by_ref = {key(exact(obj)): obj for obj in objects}
    by_id = {}
    missing = []

    def issue(code, location, message, **detail):
        report["diagnostics"].append({"code": code, "path": location, "message": message, **detail})

    from air.business_schema import graph_issues
    for obj in objects:
        meta, body = obj["meta"], obj["body"]
        allowed = PROFILE_TYPES.get(profile, [])
        if meta["type"] not in allowed:
            issue("AIR_BASELINE_MEMBER_TYPE", meta["id"], "Baseline profile does not support this member type")
        if meta["id"] in by_id:
            issue("AIR_BASELINE_VERSION_AMBIGUOUS", meta["id"], "A baseline selects one exact revision per identity")
        by_id[meta["id"]] = obj
        for field, ref, targets in reference_slots(obj):
            target = by_ref.get(key(ref))
            if target is None:
                missing.append({"from": exact(obj), "field": field, "target": {"id": ref["id"], "revision": ref["revision"]}})
                issue("AIR_REFERENCE_MISSING", meta["id"] + "/" + field, "Exact target is absent from this baseline",
                      missing={"id": ref["id"], "revision": ref["revision"]})
            elif target["meta"]["type"] not in targets:
                issue("AIR_REFERENCE_TYPE", meta["id"] + "/" + field, "Expected " + ", ".join(targets))
        for code, message in graph_issues(obj, by_ref): issue(code, meta["id"], message)
        if meta["type"] == "air.Evidence":
            targets_seen = set()
            for link in body["supports_or_refutes"]:
                if key(link) in targets_seen:
                    issue("AIR_EVIDENCE_DIRECTION", meta["id"], "One evidence-to-assertion link must have one explicit direction")
                targets_seen.add(key(link))
                assertion = by_ref.get(key(link))
                if assertion and assertion["meta"]["type"] == "air.Assertion":
                    if exact(obj) not in assertion["body"]["evidence"]:
                        issue("AIR_EVIDENCE_RECIPROCITY", meta["id"], "Assertion must reference this evidence revision")
        if meta["type"] == "air.Assertion":
            directions = set()
            for ref in body["evidence"]:
                evidence = by_ref.get(key(ref))
                if evidence and evidence["meta"]["type"] == "air.Evidence":
                    links = [link for link in evidence["body"]["supports_or_refutes"] if key(link) == key(exact(obj))]
                    if not links:
                        issue("AIR_EVIDENCE_RECIPROCITY", meta["id"], "Evidence must explicitly support or refute this assertion revision")
                    directions.update(link["direction"] for link in links)
            required = {"SUPPORTED": {"SUPPORTS"}, "REFUTED": {"REFUTES"}, "CONTESTED": {"SUPPORTS", "REFUTES"}}.get(body["epistemic_status"], set())
            if not required <= directions:
                issue("AIR_EPISTEMIC_BASIS", meta["id"], "Claimed epistemic state lacks the required evidence links")
            if directions == {"SUPPORTS", "REFUTES"} and body["epistemic_status"] != "CONTESTED":
                issue("AIR_KNOWLEDGE_CONFLICT", meta["id"], "Conflicting evidence must remain explicitly CONTESTED")
    from air.knowledge_schema import graph_issues as knowledge_graph_issues
    for code, location, message in knowledge_graph_issues(objects, by_ref): issue(code, location, message)
    from air.audience_schema import graph_issues as audience_graph_issues
    for code, location, message in audience_graph_issues(objects, by_ref): issue(code, location, message)
    from air.organization_schema import graph_issues as organization_graph_issues
    for code, location, message in organization_graph_issues(objects, by_ref): issue(code, location, message)
    from air.architecture_schema import graph_issues as architecture_graph_issues
    for code, location, message in architecture_graph_issues(objects, by_ref): issue(code, location, message)
    from air.delivery_schema import graph_issues as delivery_graph_issues
    for code, location, message in delivery_graph_issues(objects, by_ref): issue(code, location, message)
    report["rule_results"].append({"rule": "AIR-V003", "execution": "EXECUTED",
        "result": "VIOLATED" if missing else "SATISFIED", "profile": profile,
        "scope": "All declared reference fields of the selected profile; identity URIs are external"})
    report["coverage"]["executed"].append("AIR-V003")
    report["coverage"]["not_executed"].remove("AIR-V003")
    report["unresolved_references"] = missing
    report["open_unknowns"] = [{"reference": exact(obj), "blocking_policy": obj["body"]["blocking_policy"]}
        for obj in objects if obj["meta"]["type"] == "air.Unknown" and obj["body"]["state"] != "RESOLVED"]
    report["valid"] = not report["diagnostics"]
    return report


def lock_document(members, profile=FOUNDATION_PROFILE):
    return {"profile": profile, "members": sorted(members, key=key)}


def lock_reference(members, profile=FOUNDATION_PROFILE):
    content = rfc8785.dumps(lock_document(members, profile))
    checksum = hashlib.sha256(content).hexdigest()
    return {"locator": "urn:sha256:" + checksum, "media_type": "application/json", "size": len(content),
            "digest": {"algorithm": "sha256", "value": checksum},
            "access_policy": "Same authenticated access as the baseline", "retention_policy": "Retain with baseline"}


def build_baseline(request, objects):
    check_schema(request, BASELINE_REQUEST)
    profile = request["profile"]
    report = validate_graph(objects, profile)
    if not report["valid"]:
        raise InvalidModel("Baseline is not closed and valid", report)
    members = sorted([resolved(obj) for obj in objects], key=key)
    if sorted(map(key, request["members"])) != sorted(map(key, members)):
        raise InvalidModel("Requested members differ from resolved members")
    member_types = {key(member): member["type"] for member in members}
    for ref in request["meta"]["provenance"]["source_refs"]:
        if member_types.get(key(ref)) != "air.Source":
            raise InvalidModel("Baseline provenance must resolve to a member Source")
    obj = {"meta": deepcopy(request["meta"]), "body": {"members": members,
           "dependency_lock": lock_reference(members, profile), "profiles": [profile],
           "parent_baselines": request["parent_baselines"]}}
    checked = validate(obj)
    if not checked["valid"]:
        raise InvalidModel("Invalid baseline envelope", checked)
    if any(key(parent) == key(exact(obj)) for parent in obj["body"]["parent_baselines"]):
        raise InvalidModel("Baseline cannot be its own parent")
    return obj, report


def apply_change(base, change):
    checked = validate(change)
    if not checked["valid"] or change["meta"]["type"] != "air.ChangeSet":
        raise InvalidModel("Invalid ChangeSet", checked)
    if change["body"]["base"] != exact(base):
        raise InvalidModel("ChangeSet targets another baseline")
    expected = sorted(change["body"]["expected_revisions"], key=key)
    if expected != sorted(base["body"]["members"], key=key):
        raise InvalidModel("Expected revision vector differs from the baseline")
    members = {ref["id"]: deepcopy(ref) for ref in expected}
    touched, diff = set(), []
    for operation in change["body"]["operations"]:
        before, after = operation.get("before"), operation.get("after")
        object_id = (before or after)["id"]
        if object_id in touched:
            raise InvalidModel("One operation per identity is required")
        touched.add(object_id)
        if before and members.get(object_id) != before:
            raise InvalidModel("Expected object revision does not match")
        if operation["op"] == "ADD" and object_id in members:
            raise InvalidModel("ADD cannot replace an existing identity")
        if before and after and (before["id"] != after["id"] or before["type"] != after["type"] or after["revision"] <= before["revision"]):
            raise InvalidModel("REPLACE must preserve identity and type and advance the revision")
        if after:
            members[object_id] = deepcopy(after)
        else:
            del members[object_id]
        diff.append(deepcopy(operation))
    if not members:
        raise InvalidModel("A baseline must contain at least one member")
    return sorted(members.values(), key=key), diff
