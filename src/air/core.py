"""The explicit bootstrap profile; full AIR 0.1 conformance remains out of scope."""
from copy import deepcopy
from datetime import datetime
import hashlib
from jsonschema import Draft202012Validator, FormatChecker
import rfc8785
from air import __version__
from air.parsing import check_tree
from air import construction_schema as construction
from air import runtime_schema as runtime
from air import collaboration_schema as collaboration
from air import business_schema as business
from air import knowledge_schema as knowledge
from air import audience_schema as audience
from air import view_schema as captured_view
from air import organization_schema as organization
from air import workflow_schema as workflow
from air import data_schema as data_model
from air import state_schema as state_machine
from air import governance_schema as governance
from air import architecture_schema as architecture_model
from air import delivery_schema as delivery

PROFILE = "air.bootstrap/0.1"
FOUNDATION_PROFILE = "air.foundation/0.2"
FOUNDATION_TYPES = ["air.Scope", "air.Source", "air.Assertion", "air.Evidence", "air.Assumption", "air.Unknown"]
CONSTRUCTION_PROFILE = construction.PROFILE
CONSTRUCTION_TYPES = FOUNDATION_TYPES + ["air." + name for name in construction.NAMES]
RUNTIME_PROFILE = runtime.PROFILE
RUNTIME_TYPES = CONSTRUCTION_TYPES + ["air." + name for name in runtime.NAMES]
COLLABORATION_PROFILE = collaboration.PROFILE
COLLABORATION_TYPES = RUNTIME_TYPES + ["air." + name for name in collaboration.NAMES]
BUSINESS_PROFILE = business.PROFILE
BUSINESS_TYPES = COLLABORATION_TYPES + ["air." + name for name in business.NAMES]
KNOWLEDGE_PROFILE = knowledge.PROFILE
KNOWLEDGE_TYPES = BUSINESS_TYPES + ["air." + name for name in knowledge.NAMES]
AUDIENCE_PROFILE = audience.PROFILE
VIEW_PROFILE = captured_view.PROFILE
AUDIENCE_TYPES = KNOWLEDGE_TYPES + ["air." + name for name in audience.NAMES]
ORGANIZATION_PROFILE = organization.PROFILE
ORGANIZATION_TYPES = AUDIENCE_TYPES + ["air." + name for name in organization.NAMES]
WORKFLOW_PROFILE = workflow.PROFILE
WORKFLOW_TYPES = ORGANIZATION_TYPES + ["air." + name for name in workflow.NAMES]
DATA_PROFILE = data_model.PROFILE
DATA_MODEL_TYPES = WORKFLOW_TYPES + ["air." + name for name in data_model.NAMES]
STATE_PROFILE = state_machine.PROFILE
STATE_TYPES = DATA_MODEL_TYPES + ["air." + name for name in state_machine.NAMES]
GOVERNANCE_PROFILE = governance.PROFILE
GOVERNANCE_TYPES = STATE_TYPES + ["air." + name for name in governance.NAMES]
ARCHITECTURE_PROFILE = architecture_model.PROFILE
ARCHITECTURE_TYPES = GOVERNANCE_TYPES + ["air." + name for name in architecture_model.NAMES]
DELIVERY_PROFILE = delivery.PROFILE
DELIVERY_TYPES = ARCHITECTURE_TYPES + ["air." + name for name in delivery.NAMES]
DATA_TYPES = DELIVERY_TYPES
PROFILE_TYPES = {FOUNDATION_PROFILE: FOUNDATION_TYPES, CONSTRUCTION_PROFILE: CONSTRUCTION_TYPES, RUNTIME_PROFILE: RUNTIME_TYPES, COLLABORATION_PROFILE: COLLABORATION_TYPES, BUSINESS_PROFILE: BUSINESS_TYPES, KNOWLEDGE_PROFILE: KNOWLEDGE_TYPES, AUDIENCE_PROFILE: AUDIENCE_TYPES, ORGANIZATION_PROFILE: ORGANIZATION_TYPES, WORKFLOW_PROFILE: WORKFLOW_TYPES, DATA_PROFILE: DATA_MODEL_TYPES, STATE_PROFILE: STATE_TYPES, GOVERNANCE_PROFILE: GOVERNANCE_TYPES, ARCHITECTURE_PROFILE: ARCHITECTURE_TYPES, DELIVERY_PROFILE: DELIVERY_TYPES}
TYPES = DATA_TYPES + ["air.Baseline", "air.ChangeSet", "air.View"]
TEXT = {"type": "string", "minLength": 1, "maxLength": 10000}
URI = {"type": "string", "format": "uri", "maxLength": 512}
INSTANT = {"type": "string", "format": "date-time", "pattern": "Z$"}


def record(properties, required=None):
    return {"type": "object", "properties": properties, "additionalProperties": False,
            "required": list(properties) if required is None else required}


REF = record({"id": URI, "revision": {"type": "integer", "minimum": 1, "maximum": 2147483647}})
REFS = {"type": "array", "items": REF, "uniqueItems": True, "maxItems": 1000}
META = record({
    "id": URI, "type": {"enum": TYPES},
    "revision": {"type": "integer", "minimum": 1, "maximum": 2147483647},
    "name": TEXT, "description": TEXT, "namespace": {"type": "string", "pattern": "^[a-z][a-z0-9_.-]{0,127}$"},
    "owner": URI,
    "classification": record({"level": {"enum": ["PUBLIC", "INTERNAL"]}}),
    "lifecycle": {"const": "DRAFT"}, "recorded_at": INSTANT,
    "validity": record({"start": INSTANT, "end": {"anyOf": [INSTANT, {"type": "null"}]}}),
    "provenance": record({"recorded_by": URI, "method": TEXT, "source_refs": REFS}),
})
BODIES = {
    "air.Scope": record({"includes": REFS, "excludes": REFS, "boundary_description": TEXT,
                         "context_dimensions": {"type": "object", "additionalProperties": TEXT}},
                        ["includes", "excludes", "boundary_description"]),
    "air.Source": record({
        "kind": {"enum": ["DOCUMENT", "CODE", "INTERVIEW", "DATABASE", "TELEMETRY", "EXTERNAL"]},
        "locator": TEXT, "source_revision": TEXT, "captured_at": INSTANT,
        "access_policy": TEXT, "retention_policy": TEXT,
    }, ["kind", "locator", "captured_at", "access_policy", "retention_policy"]),
}
NONEMPTY_REFS = {**REFS, "minItems": 1}
RESOLVED_REF = record({**REF["properties"], "type": {"enum": DATA_TYPES},
                       "digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}})
RESOLVED_REFS = {"type": "array", "items": RESOLVED_REF, "minItems": 1, "maxItems": 1000, "uniqueItems": True}
ARTIFACT_REF = record({"locator": URI, "media_type": {"const": "application/json"},
    "size": {"type": "integer", "minimum": 1},
    "digest": record({"algorithm": {"const": "sha256"}, "value": {"type": "string", "pattern": "^[a-f0-9]{64}$"}}),
    "access_policy": TEXT, "retention_policy": TEXT})
EVIDENCE_LINK = record({**REF["properties"], "direction": {"enum": ["SUPPORTS", "REFUTES"]}})
BODIES.update({
    "air.Assertion": record({"statement": TEXT, "subject_scope": REF,
        "epistemic_status": {"enum": ["UNASSESSED", "SUPPORTED", "ESTABLISHED", "CONTESTED", "REFUTED", "EXPIRED"]},
        "evidence": REFS, "review_due": INSTANT}, ["statement", "subject_scope", "epistemic_status", "evidence"]),
    "air.Evidence": record({"source": REF, "selector": TEXT,
        "evidence_kind": {"enum": ["DOCUMENT_EXCERPT", "RECORD", "MEASUREMENT", "TEST_RESULT", "INTERVIEW"]},
        "supports_or_refutes": {"type": "array", "items": EVIDENCE_LINK, "minItems": 1, "maxItems": 1000, "uniqueItems": True},
        "limitations": {"type": "array", "items": TEXT, "maxItems": 1000}},
        ["source", "selector", "evidence_kind", "supports_or_refutes", "limitations"]),
    "air.Assumption": record({"statement": TEXT, "used_by": NONEMPTY_REFS, "impact_if_false": TEXT,
        "validation_plan": TEXT, "review_due": INSTANT, "state": {"enum": ["OPEN", "UNDER_TEST"]}}),
    "air.Unknown": record({"question": TEXT, "affected_objects": NONEMPTY_REFS, "resolution_owner": URI,
        "blocking_policy": {"enum": ["BLOCK", "INFORMATIONAL"]},
        "state": {"enum": ["OPEN", "INVESTIGATING", "RESOLVED"]}, "resolution": REF},
        ["question", "affected_objects", "resolution_owner", "blocking_policy", "state"]),
    "air.Baseline": record({"members": RESOLVED_REFS, "dependency_lock": ARTIFACT_REF,
        "profiles": {"enum": [[FOUNDATION_PROFILE], [CONSTRUCTION_PROFILE], [RUNTIME_PROFILE], [COLLABORATION_PROFILE], [BUSINESS_PROFILE], [KNOWLEDGE_PROFILE], [AUDIENCE_PROFILE], [ORGANIZATION_PROFILE], [WORKFLOW_PROFILE], [DATA_PROFILE], [STATE_PROFILE], [GOVERNANCE_PROFILE], [ARCHITECTURE_PROFILE], [DELIVERY_PROFILE]]}, "parent_baselines": REFS}),
    "air.ChangeSet": record({"base": REF,
        "operations": {"type": "array", "minItems": 1, "maxItems": 1000, "items": {"oneOf": [
            record({"op": {"const": "ADD"}, "after": RESOLVED_REF}),
            record({"op": {"const": "REPLACE"}, "before": RESOLVED_REF, "after": RESOLVED_REF}),
            record({"op": {"const": "REMOVE"}, "before": RESOLVED_REF}),
        ]}}, "rationale": TEXT, "expected_revisions": RESOLVED_REFS,
        "approvals": {"type": "array", "maxItems": 0}}),
})


BODIES.update(construction.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS))
BODIES.update(runtime.bodies(record, TEXT, REF, REFS, NONEMPTY_REFS, INSTANT, ARTIFACT_REF))
BODIES.update(collaboration.bodies(record, TEXT, URI, REF, NONEMPTY_REFS))
BODIES.update(business.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS, INSTANT))
BODIES.update(knowledge.bodies(record, TEXT, REF, REFS, NONEMPTY_REFS))
BODIES.update(audience.bodies(record, TEXT, REF, REFS, NONEMPTY_REFS, DATA_TYPES))
BODIES.update(captured_view.bodies(record, TEXT, URI, REF))
BODIES.update(organization.bodies(record, TEXT, URI, REF, REFS))
BODIES.update(workflow.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS))
BODIES.update(data_model.bodies(record, TEXT, URI, REF, REFS, ARTIFACT_REF))
BODIES.update(state_machine.bodies(record, TEXT))
BODIES.update(governance.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS, INSTANT))
BODIES.update(architecture_model.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS))
BODIES.update(delivery.bodies(record, TEXT, URI, REF, REFS, NONEMPTY_REFS, INSTANT, ARTIFACT_REF))


def schema(type_name):
    result = record({"meta": deepcopy(META), "body": BODIES[type_name]})
    result["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    result["properties"]["meta"]["properties"]["type"] = {"const": type_name}
    return result


def capabilities():
    return {"engine_version": __version__, "profile": ARCHITECTURE_PROFILE, "supported_profiles": [PROFILE, FOUNDATION_PROFILE, CONSTRUCTION_PROFILE, RUNTIME_PROFILE, COLLABORATION_PROFILE, BUSINESS_PROFILE, KNOWLEDGE_PROFILE, AUDIENCE_PROFILE, VIEW_PROFILE, ORGANIZATION_PROFILE, WORKFLOW_PROFILE, DATA_PROFILE, STATE_PROFILE, GOVERNANCE_PROFILE, ARCHITECTURE_PROFILE, DELIVERY_PROFILE],
            "types": TYPES, "lifecycle": ["DRAFT"],
            "air_conformant_profiles": [], "normative_rules_implemented": [],
            "scoped_normative_rules": [{"id": "AIR-V003", "profile": FOUNDATION_PROFILE,
                "scope": "Exact reference closure of six foundation data types"},
                {"id": "AIR-V003", "profile": CONSTRUCTION_PROFILE,
                 "scope": "Exact reference closure of fifteen construction and knowledge data types"},
                {"id": "AIR-V003", "profile": RUNTIME_PROFILE, "scope": "Exact declared references of eighteen runtime, construction and knowledge data types"},
                {"id": "AIR-V003", "profile": COLLABORATION_PROFILE, "scope": "Exact declared references of twenty collaboration, runtime, construction and knowledge data types"},
                {"id": "AIR-V003", "profile": BUSINESS_PROFILE, "scope": "Exact declared references of twenty-eight business, collaboration, runtime, construction and knowledge data types"},
                {"id": "AIR-V003", "profile": KNOWLEDGE_PROFILE, "scope": "Exact declared references of thirty knowledge, business, collaboration, runtime and construction data types"},
                {"id": "AIR-V003", "profile": AUDIENCE_PROFILE, "scope": "Exact references of thirty-one audience and prior data types"},
                {"id": "AIR-V003", "profile": ORGANIZATION_PROFILE, "scope": "Exact references of thirty-five organization and prior data types"},
                {"id": "AIR-V003", "profile": WORKFLOW_PROFILE, "scope": "Exact references of thirty-eight workflow and prior data types"},
                {"id": "AIR-V003", "profile": DATA_PROFILE, "scope": "Exact model-object references of forty-four data and prior types; schema artifact field paths require explicit data validation"},
                {"id": "AIR-V003", "profile": STATE_PROFILE, "scope": "Exact model-object references of forty-five state and prior types, including expression literals"},
                {"id": "AIR-V003", "profile": GOVERNANCE_PROFILE, "scope": "Exact model-object references of fifty-one governance and prior types, including condition literals"},
                {"id": "AIR-V003", "profile": ARCHITECTURE_PROFILE, "scope": "Exact model-object references of fifty-seven architecture and prior types"},
                {"id": "AIR-V003", "profile": DELIVERY_PROFILE, "scope": "Exact model-object references of seventy-five delivery and prior types"}],
            "features": ["typed-exact-references", "closed-baselines", "knowledge-drafts", "changeset-proposals", "baseline-export",
                         "bounded-expressions", "diagnostic-validation-gates", "construction-traceability", "baseline-diff", "reference-impact", "offline-dossier-views",
                         "namespace-access-policy", "authenticated-review-receipts", "mcp-stdio", "mcp-streamable-http-local", "sqlite-backup-restore", "weekly-capacity-scenarios", "illustrative-experiments", "registry-transfer-sqlite-postgresql", "atomic-local-design-packages", "historical-contribution-contexts", "shared-revision-reconciliation", "authorized-package-discovery", "durable-pure-calculation-jobs", "committed-local-authority", "versioned-human-capacity-offers", "atomic-local-resource-admission", "guarded-local-activation-episodes", "reviewed-admission-renewal", "reviewed-local-episode-closure", "runtime-observation-drafts", "authenticated-runtime-ingestion", "explicit-runtime-comparison", "draft-contributions-decisions", "authenticated-design-submissions", "portable-interactive-workbench", "draft-business-goals-services", "explicit-goal-target-assessment", "declared-inferences-conflicts", "exact-knowledge-dossier", "immutable-artifact-bytes", "authorized-artifact-manifests", "declared-audience-viewpoints", "deterministic-audience-views", "bounded-illustrative-state-replay", "declared-governance-models", "bounded-policy-diagnostics", "declared-architecture-structure", "exact-architecture-dossier", "deterministic-openapi-design-compilation", "structural-architecture-checks", "declared-message-channels", "baseline-closure-computation", "guided-agent-path", "draft-dry-run-validation", "reference-rebase-projection", "paged-baseline-browsing", "structured-agent-errors", "codex-adapter", "declared-architecture-repository-scaffold", "deterministic-ide-adapter-generation", "declared-portfolio-index", "declared-data-models", "authorized-local-json-validation", "declared-workflows-operating-models", "declared-organizational-responsibilities", "atomic-captured-view-products", "artifact-source-context-guards"],
            "compilation": {"engine": "air.openapi-compiler/0.31", "operation_roles": True, "target_formats": ["OpenAPI 3.1.1"],
                "source_bindings": ["air.http-json-mapping/0.26", "air.http-json-mapping/0.30"], "schema_subset": "air.structured-json/0.30",
                "path_parameters": True, "error_responses": True, "declared_security_scheme": True,
                "external_execution": False, "security_verified": False, "asyncapi_generated": False},
            "architecture_checks": {"binding": "air.architecture-checks/0.31", "structural_only": True,
                "families": ["EXCLUSIVITY (MECE)", "EXHAUSTIVENESS (MECE)", "CONTEXT_COHERENCE (DDD)", "COMPILABILITY"],
                "checks": ["function exposed once", "operation names unique", "one owning block per aggregate", "one provider per contract",
                           "mandatory functional requirements satisfied", "functions realised by a block", "required contracts provided",
                           "a block within one data authority", "an event published by the owner of its aggregate", "declared schemas inside the compilation subset"],
                "semantics_verified": False},
            "message_channels": {"binding": "air.message-channel-mapping/0.30", "protocols": ["KAFKA", "AMQP", "MQTT", "NATS"],
                "declared_only": True, "broker_contacted": False, "ordering_and_delivery": "DECLARED_NOT_VERIFIED"},
            "baseline_closure": {"engine": "air.baseline-closure/0.30", "registry_written": False, "baseline_created": False},
            "workspace": {"engine": "air.workspace/0.28", "registry_written": False, "resolve_implemented": False, "lockfile_implemented": False},
            "ide_adapters": {"engine": "air.ide-adapter/0.31", "clients": ["claude-code", "codex"], "support_state": "ADAPTER_DELIVERED", "client_qualified": False, "secrets_generated": False,
                "journeys": ["air-dossier", "air-proposer", "air-relire", "air-impact", "air-livrer"]},
            "delivery": {"profile": DELIVERY_PROFILE, "types": ["air." + n for n in delivery.NAMES],
                "readiness_gate": "air.readiness-gate/0.32", "scenario_simulation": "air.scenario-simulation/0.32",
                "simulation_regime": "MODEL_BASED_SEEDED", "calibration": "CALIBRATED only when every step cites runtime observations of the baseline",
                "workflow_guards": "air.workflow-flow/0.32"},
            "agent_path": {"engine": "air.agent-path/0.31", "tools": ["air_guide", "air_list_revisions", "air_browse_baseline", "air_describe_type", "air_validate_drafts", "air_rebase_drafts"],
                "registry_written": False, "errors": "AIR code, message, bounded diagnostics and a hint relayed by both MCP transports"},
            "portfolio": {"engine": "air.portfolio/0.29", "single_instance": True, "federation_implemented": False, "registry_written": False, "semantic_compatibility_executed": False},
            "artifact_storage": {"binding": "air.artifact/0.18", "max_bytes": 16777216, "json_max_bytes": 524288, "chunk_bytes": 262144, "evidence_qualified": False, "retention": "No automatic deletion"},
            "expression_engine": {"implementation": "air.expr/0.3", "language": "AIR-Expr", "language_version": "0.1",
                "subset": True, "validation_profile": "air.validation/0.3", "gate": "foundation-review",
                "limits": {"nodes": 2048, "depth": 24, "steps": 10000, "gate_steps": 20000, "collection": 256},
                "authority": "Diagnostic only; no approval, admission or activation"},
            "not_implemented": ["remote-signed-publication", "live-Workbench-synchronization", "established-assertion-promotion",
                                "calibrated-simulation", "full-resource-planning", "federation", "distributed-admission", "external-activation", "runtime-instance-binding", "automatic-remediation"],
            "runtime_comparison": {"binding": "air.runtime-comparison/0.12", "coverage": "PARTIAL", "observation_qualification": "DRAFT", "mapping_qualification": "DECLARED_NOT_INDEPENDENTLY_VALIDATED", "remote_collection": False},
            "resource_authority": {"binding": "air.local-resource-admission/0.11", "capacity": "disjoint weekly HUMAN_FTE pools", "external_execution": False, "design_acceptance": "NOT_EXECUTED"},
            "scope": "Single organization; optional explicit namespace policy, shared reads by default"}


def reference_slots(obj):
    """(field path, exact ref, permitted target types); identity URIs are external."""
    slots = [("meta/provenance/source_refs", ref, ["air.Source"])
             for ref in obj["meta"]["provenance"]["source_refs"]]
    body, kind = obj["body"], obj["meta"]["type"]
    many = {"air.Scope": {"includes": DATA_TYPES, "excludes": DATA_TYPES},
            "air.Assertion": {"evidence": ["air.Evidence"]},
            "air.Evidence": {"supports_or_refutes": ["air.Assertion"]},
            "air.Assumption": {"used_by": DATA_TYPES},
            "air.Unknown": {"affected_objects": DATA_TYPES},
            "air.Baseline": {"members": DATA_TYPES, "parent_baselines": ["air.Baseline"]},
            "air.ChangeSet": {"expected_revisions": DATA_TYPES}}
    one = {"air.Assertion": {"subject_scope": ["air.Scope"]},
           "air.Evidence": {"source": ["air.Source"]},
           "air.Unknown": {"resolution": ["air.Assertion", "air.Evidence"]},
           "air.ChangeSet": {"base": ["air.Baseline"]}}
    for field, targets in many.get(kind, {}).items():
        slots.extend(("body/" + field, ref, targets) for ref in body[field])
    for field, targets in one.get(kind, {}).items():
        if field in body:
            slots.append(("body/" + field, body[field], targets))
    if kind == "air.ChangeSet":
        for operation in body["operations"]:
            slots.extend(("body/operations/" + field, operation[field], DATA_TYPES)
                         for field in ("before", "after") if field in operation)
    slots.extend(construction.slots(obj))
    slots.extend(runtime.slots(obj, DATA_TYPES))
    slots.extend(collaboration.slots(obj, DATA_TYPES))
    slots.extend(business.slots(obj, DATA_TYPES))
    slots.extend(knowledge.slots(obj, DATA_TYPES))
    slots.extend(audience.slots(obj, DATA_TYPES))
    slots.extend(captured_view.slots(obj))
    slots.extend(organization.slots(obj))
    slots.extend(workflow.slots(obj, DATA_TYPES))
    slots.extend(data_model.slots(obj))
    slots.extend(state_machine.slots(obj, DATA_TYPES))
    slots.extend(governance.slots(obj, DATA_TYPES))
    slots.extend(architecture_model.slots(obj))
    slots.extend(delivery.slots(obj, DATA_TYPES))
    return slots


def references(obj):
    return [{"id": ref["id"], "revision": ref["revision"]} for _, ref, _ in reference_slots(obj)]


def infer_profile(objects):
    types = {o['meta']['type'] for o in objects if isinstance(o, dict) and isinstance(o.get('meta'), dict) and isinstance(o['meta'].get('type'), str)}
    declared = {p for o in objects if isinstance(o, dict) and isinstance(o.get('body'), dict) and isinstance(o['body'].get('profiles'), list) for p in o['body']['profiles'] if isinstance(p, str)}
    if 'air.View' in types: return VIEW_PROFILE
    if types & {'air.' + name for name in delivery.NAMES} or DELIVERY_PROFILE in declared: return DELIVERY_PROFILE
    if types & {'air.' + name for name in architecture_model.NAMES} or ARCHITECTURE_PROFILE in declared: return ARCHITECTURE_PROFILE
    if types & {'air.' + name for name in governance.NAMES} or GOVERNANCE_PROFILE in declared: return GOVERNANCE_PROFILE
    if types & {'air.' + name for name in state_machine.NAMES} or STATE_PROFILE in declared: return STATE_PROFILE
    if types & {'air.' + name for name in data_model.NAMES} or DATA_PROFILE in declared: return DATA_PROFILE
    if types & {'air.' + name for name in workflow.NAMES} or WORKFLOW_PROFILE in declared: return WORKFLOW_PROFILE
    if any(isinstance(o, dict) and isinstance(o.get('meta'), dict) and o['meta'].get('type') == 'air.OrganizationUnit' and isinstance(o.get('body'), dict) and o['body'].get('operating_model') for o in objects): return WORKFLOW_PROFILE
    if types & {'air.' + name for name in organization.NAMES} or ORGANIZATION_PROFILE in declared: return ORGANIZATION_PROFILE
    if any(isinstance(o, dict) and isinstance(o.get('meta'), dict) and o['meta'].get('type') == 'air.Actor' and isinstance(o.get('body'), dict) and o['body'].get('roles') for o in objects): return ORGANIZATION_PROFILE
    if types & {'air.' + name for name in audience.NAMES} or AUDIENCE_PROFILE in declared: return AUDIENCE_PROFILE
    if any(isinstance(o, dict) and isinstance(o.get('meta'), dict) and o['meta'].get('type') == 'air.Concern' and isinstance(o.get('body'), dict) and o['body'].get('addressed_by') for o in objects): return AUDIENCE_PROFILE
    if types & {'air.' + name for name in knowledge.NAMES} or KNOWLEDGE_PROFILE in declared: return KNOWLEDGE_PROFILE
    if types & {'air.' + name for name in business.NAMES} or BUSINESS_PROFILE in declared: return BUSINESS_PROFILE
    if any(isinstance(o, dict) and isinstance(o.get('body'), dict) and isinstance(o['body'].get('metric_or_signal'), dict) for o in objects): return BUSINESS_PROFILE
    if types & {'air.' + name for name in collaboration.NAMES} or COLLABORATION_PROFILE in declared: return COLLABORATION_PROFILE
    if types & {'air.' + name for name in runtime.NAMES} or RUNTIME_PROFILE in declared: return RUNTIME_PROFILE
    if types & (set(CONSTRUCTION_TYPES) - set(FOUNDATION_TYPES)) or CONSTRUCTION_PROFILE in declared: return CONSTRUCTION_PROFILE
    return FOUNDATION_PROFILE


def identify(diagnostics, objects):
    """A diagnostic names the object it concerns, not only its position in the bundle."""
    for row in diagnostics:
        head = str(row.get("path", "")).split("/")[0]
        if not head.isdigit() or "object" in row: continue
        obj = objects[int(head)] if int(head) < len(objects) else None
        meta = obj.get("meta") if isinstance(obj, dict) else None
        if isinstance(meta, dict) and isinstance(meta.get("id"), str):
            row["object"] = {"id": meta["id"], "revision": meta.get("revision"), "type": meta.get("type")}
    return diagnostics


def validate(document):
    diagnostics = []
    objects = document if isinstance(document, list) else [document]
    def issue(code, location, message):
        diagnostics.append({"code": code, "path": location, "message": message})
    try:
        check_tree(document)
    except ValueError as exc:
        issue("AIR_INPUT", "", str(exc))
    if not objects or len(objects) > 1000:
        issue("AIR_COUNT", "", "Expected 1 to 1000 objects")
    valid_objects = []
    for index, obj in enumerate(objects[:1000]):
        typename = obj.get("meta", {}).get("type") if isinstance(obj, dict) and isinstance(obj.get("meta"), dict) else None
        if typename not in TYPES:
            issue("AIR_TYPE_UNSUPPORTED", str(index), "Type not implemented in bootstrap profile")
            continue
        errors = list(Draft202012Validator(schema(typename), format_checker=FormatChecker()).iter_errors(obj))
        for err in errors:
            issue("AIR_SCHEMA", f"{index}/" + "/".join(map(str, err.absolute_path)), err.message)
        if errors:
            continue
        if typename == "air.Assertion" and obj["body"]["epistemic_status"] == "ESTABLISHED":
            issue("AIR_REVIEW_REQUIRED", str(index), "ESTABLISHED promotion is not implemented; a review receipt alone does not establish an assertion")
        if typename == "air.Unknown":
            resolved = obj["body"]["state"] == "RESOLVED"
            if resolved != ("resolution" in obj["body"]):
                issue("AIR_UNKNOWN_RESOLUTION", str(index), "RESOLVED requires an exact resolution; open unknowns cannot declare a resolution")
        for code, message in [*construction.local_issues(obj), *runtime.local_issues(obj), *collaboration.local_issues(obj), *business.local_issues(obj), *knowledge.local_issues(obj), *audience.local_issues(obj), *captured_view.local_issues(obj), *workflow.local_issues(obj), *data_model.local_issues(obj), *state_machine.local_issues(obj), *governance.local_issues(obj), *architecture_model.local_issues(obj), *delivery.local_issues(obj)]:
            issue(code, str(index), message)
        if typename == "air.Baseline":
            if any(r["type"] not in PROFILE_TYPES[obj["body"]["profiles"][0]] for r in obj["body"]["members"]):
                issue("AIR_PROFILE_TYPE", str(index), "Members require a profile that supports their types")
        period = obj["meta"]["validity"]
        if period["end"] and datetime.fromisoformat(period["end"]) <= datetime.fromisoformat(period["start"]):
            issue("AIR_INTERVAL", f"{index}/meta/validity", "Expected nonempty [start, end) interval")
        if typename == "air.Scope":
            include = {(r["id"], r["revision"]) for r in obj["body"]["includes"]}
            exclude = {(r["id"], r["revision"]) for r in obj["body"]["excludes"]}
            if include & exclude:
                issue("AIR_SCOPE_CONFLICT", str(index), "Same exact reference included and excluded")
        valid_objects.append(obj)
    seen = set()
    for obj in valid_objects:
        key = (obj["meta"]["id"], obj["meta"]["revision"])
        if key in seen:
            issue("AIR_DUPLICATE_REVISION", "", "Duplicate identity/revision in document")
        seen.add(key)
    # Closure is deliberately not inferred: external references need a future resolver.
    unresolved = sorted({(r["id"], r["revision"]) for obj in valid_objects for r in references(obj)} - seen)
    active_profile = infer_profile(valid_objects)
    return {"profile": active_profile, "valid": not diagnostics,
            "conformant_air_0_1": False, "diagnostics": identify(diagnostics, objects),
            "coverage": {"executed": ["bootstrap-schema", "bootstrap-temporal", "bootstrap-scope", "bootstrap-identity"],
                         "not_executed": [f"AIR-V{i:03}" for i in range(1, 85)],
                         "reference_resolution": "NOT_EXECUTED"},
            "unresolved_references": [{"id": i, "revision": r} for i, r in unresolved]}


def canonical(obj):
    result = deepcopy(obj)
    key = lambda ref: (ref["id"], ref["revision"])
    result["meta"]["provenance"]["source_refs"].sort(key=key)
    if result["meta"]["type"] == "air.Scope":
        for field in ("includes", "excludes"):
            result["body"][field].sort(key=key)
    for field in {"air.Assertion": ["evidence"], "air.Assumption": ["used_by"],
                  "air.Unknown": ["affected_objects"], "air.Baseline": ["members", "parent_baselines"],
                  "air.ChangeSet": ["expected_revisions"]}.get(result["meta"]["type"], []):
        result["body"][field].sort(key=key)
    for field in construction.MANY.get(result["meta"]["type"], {}):
        result["body"][field].sort(key=key)
    if result["meta"]["type"] == "air.Evidence":
        result["body"]["supports_or_refutes"].sort(key=lambda ref: (*key(ref), ref["direction"]))
    runtime.canonicalize(result)
    collaboration.canonicalize(result)
    business.canonicalize(result)
    knowledge.canonicalize(result)
    audience.canonicalize(result)
    captured_view.canonicalize(result)
    organization.canonicalize(result)
    workflow.canonicalize(result)
    data_model.canonicalize(result)
    state_machine.canonicalize(result)
    governance.canonicalize(result)
    architecture_model.canonicalize(result)
    delivery.canonicalize(result)
    return rfc8785.dumps(result)


def digest(obj):
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()
