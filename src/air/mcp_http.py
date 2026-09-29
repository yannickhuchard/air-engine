from air import admission, renewal, closure, runtime, collaboration
"""Stateless Streamable HTTP binding for AIR's local authenticated endpoint."""
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import OperationalError
from air.access import ScopedStore, Forbidden, NotFound
from air import acceptance, agent, deliverables, presentation, readiness
from air.core import capabilities
from air.construction import assess_baseline
from air.foundation import InvalidModel
from air.mcp import PROTOCOL, Session
from air.projections import diff, impact, view
from air.planning import plan
from air.experiments import simulate
from air.contexts import create_context, read_context, reconcile
from air.discovery import discover
from air import jobs
from air.authority import publish_offer, get_offer
from air.workbench import compile_workbench
from air.business import assess as assess_goal
from air.knowledge import inspect_knowledge
from air.organization import inspect_organization
from air.workflow import inspect_workflow
from air.data_validation import validate_payload
from air.state_replay import replay as replay_state
from air.policy_check import check_policy
from air.architecture import inspect_architecture
from air.openapi_compiler import compile_openapi
from air.workspace import compile_workspace
from air.ide_adapter import compile_adapter
from air.portfolio import compile_portfolio, index_portfolio
from air.baseline_closure import compute_closure
from air import artifacts, view_capture
from air.audience import compile_view as compile_audience_view
from air.packages import prepare_package, publish_package, read_package, revoke_package
from air.storage import Conflict


def invoke(store, principal, name, args, settings=None):
    from air.tool_access import allowed_tools, actions
    if name not in allowed_tools(actions(principal, principal['policy'])):
        return {'error': 'AIR_FORBIDDEN', 'http_status': 403}
    guarded = ScopedStore(store, principal, principal["policy"])
    actor = principal["subject"]
    try:
        if name == "air_guide": return agent.guide(store, principal, principal["policy"], args)
        if name == "air_list_revisions": return agent.list_revisions(store, principal, principal["policy"], args)
        if name == "air_browse_baseline": return agent.browse_baseline(store, principal, principal["policy"], args)
        if name == "air_describe_type": return agent.describe_type(store, principal, principal["policy"], args)
        if name == "air_validate_drafts": return agent.validate_drafts(store, principal, principal["policy"], args)
        if name == "air_rebase_drafts": return agent.rebase_drafts(store, principal, principal["policy"], settings, args)
        if name == "air_deposit_prepared": return agent.deposit_prepared(store, principal, principal["policy"], args)
        if name == "air_walk_scenarios": return acceptance.walk_baseline(store, principal, principal["policy"], args)
        if name == "air_compile_presentation": return presentation.compile_presentation(store, principal, principal["policy"], {**args, "content": args.get("content", "OUTLINE")})
        if name == "air_compile_deliverables": return deliverables.compile_deliverables(store, principal, principal["policy"], args)
        if name == "air_assess_readiness": return readiness.assess_readiness(store, principal, principal["policy"], args)
        if name == "air_simulate_scenario": return readiness.simulate_scenario(store, principal, principal["policy"], args)
        if name == "air_record_simulation": return readiness.record_simulation(store, principal, principal["policy"], settings, args)
        if name == "air_freeze_prepared": return agent.freeze_prepared(store, principal, principal["policy"], args)
        if name == "air_capture_view": return view_capture.capture(store, principal, principal["policy"], settings, args)
        if name == "air_read_captured_view": return view_capture.read(store, principal, principal["policy"], args)
        if name == "air_compile_audience_view": return compile_audience_view(store, principal, principal["policy"], args)
        if name == "air_import_artifact": return artifacts.import_base64(store, principal, principal["policy"], settings, args)
        if name == "air_describe_artifact": return artifacts.describe(store, principal, principal["policy"], args)
        if name == "air_read_artifact": return artifacts.read_base64(store, principal, principal["policy"], args)
        if name == "air_compile_openapi": return compile_openapi(store, principal, principal["policy"], args)
        if name == "air_compile_workspace": return compile_workspace(store, principal, principal["policy"], args)
        if name == "air_compile_ide_adapter": return compile_adapter(store, principal, principal["policy"], args)
        if name == "air_compute_baseline_closure": return compute_closure(store, principal, principal["policy"], args)
        if name == "air_compile_portfolio": return compile_portfolio(store, principal, principal["policy"], args)
        if name == "air_index_portfolio": return index_portfolio(store, principal, principal["policy"], args)
        if name == "air_inspect_architecture": return inspect_architecture(store, principal, principal["policy"], args)
        if name == "air_check_policy": return check_policy(store, principal, principal["policy"], args)
        if name == "air_replay_state_machine": return replay_state(store, principal, principal["policy"], args)
        if name == "air_validate_data": return validate_payload(store, principal, principal["policy"], args)
        if name == "air_inspect_workflow": return inspect_workflow(store, principal, principal["policy"], args)
        if name == "air_inspect_organization": return inspect_organization(store, principal, principal["policy"], args)
        if name == "air_inspect_knowledge": return inspect_knowledge(store, principal, principal["policy"], args)
        if name == "air_assess_goal_targets": return assess_goal(store, principal, principal["policy"], args)
        if name == "air_compile_workbench": return compile_workbench(store, principal, principal["policy"], settings, args)
        if name == "air_whoami": return collaboration.whoami(principal, settings)
        if name == "air_collaboration_submit": return collaboration.submit(store, principal, principal["policy"], settings, args)
        if name == "air_collaboration_read": return collaboration.read(store, principal, principal["policy"], args)
        if name == "air_runtime_ingest": return runtime.ingest(store, principal, principal["policy"], settings, args)
        if name == "air_runtime_compare": return runtime.compare(store, principal, principal["policy"], args)
        if name == "air_renewal_propose": return renewal.propose(store, principal, principal["policy"], settings, args)
        if name == "air_renewal_renew": return renewal.renew(store, principal, principal["policy"], settings, args)
        if name == "air_closure_propose": return closure.propose(store, principal, principal["policy"], settings, args)
        if name == "air_closure_review": return closure.review(store, principal, principal["policy"], settings, args)
        if name == "air_closure_revoke_review": return closure.revoke_review(store, principal, principal["policy"], settings, args)
        if name == "air_closure_close": return closure.close(store, principal, principal["policy"], settings, args)
        if name == "air_admission_propose": return admission.propose(store, principal, principal["policy"], settings, args)
        if name == "air_admission_review": return admission.review(store, principal, principal["policy"], settings, args)
        if name == "air_admission_revoke_review": return admission.revoke_review(store, principal, principal["policy"], settings, args)
        if name == "air_admission_admit": return admission.admit(store, principal, principal["policy"], settings, args)
        if name == "air_admission_read": return admission.read(store, principal, principal["policy"], args)
        if name == "air_admission_release": return admission.release(store, principal, principal["policy"], settings, args)
        if name == "air_admission_activate": return admission.activate(store, principal, principal["policy"], settings, args)
        if name == "air_capacity_publish": return publish_offer(store, principal, principal["policy"], settings, args)
        if name == "air_capacity_get": return get_offer(store, principal, principal["policy"], args)
        if name == "air_submit_job": return jobs.submit(store, principal, principal["policy"], settings, args)
        if name == "air_get_job": return jobs.get_job(store, principal, principal["policy"], args)
        if name == "air_cancel_job": return jobs.cancel(store, principal, principal["policy"], args)
        package_tools = {"air_discover": discover, "air_get_context": create_context, "air_read_context": read_context, "air_reconcile": reconcile, "air_package_prepare": prepare_package, "air_package_publish": publish_package,
                         "air_package_read": read_package, "air_package_revoke": revoke_package}
        if name in package_tools: return package_tools[name](store, principal, principal["policy"], args)
        if name == "air_capabilities": return capabilities()
        if name == "air_get":
            found = guarded.get(args["id"], args["revision"])
            if found is None: raise guarded.missing(args["id"], args["revision"])
            return found
        if name == "air_export_baseline": return guarded.export_baseline(args)
        if name == "air_import_drafts": return guarded.put_bundle(args["objects"], actor)
        if name == "air_freeze_baseline": return guarded.create_baseline(args, actor)
        if name == "air_propose_change": return guarded.propose_change(args, actor)
        return {"air_simulate": simulate, "air_plan": plan, "air_validate_construction": assess_baseline, "air_diff": diff,
                "air_impact": impact, "air_compile_view": view}[name](guarded, args)
    except (Forbidden, NotFound, Conflict, InvalidModel) as exc:
        return agent.error_from_exception(exc)
    except OperationalError:
        return {"error": "AIR_STORAGE_UNAVAILABLE", "http_status": 503}


def install(app, store, identity, document, settings=None):
    @app.post("/mcp")
    async def mcp(request: Request, principal=Depends(identity)):
        if not (settings and settings.server):
            # The built-in listener is loopback only. Reject browser origins and Host
            # values outside that listener, including DNS rebinding through a proxy.
            try:
                host = urlsplit("http://" + request.headers.get("host", ""))
                port = host.port or 80
            except ValueError:
                raise HTTPException(403, detail={"code": "AIR_MCP_HOST_FORBIDDEN"})
            if host.hostname not in ("127.0.0.1", "localhost", "[::1]", "::1"):
                raise HTTPException(403, detail={"code": "AIR_MCP_HOST_FORBIDDEN"})
            origin = request.headers.get("origin")
            allowed = {"http://127.0.0.1:" + str(port), "http://localhost:" + str(port)}
            if origin is not None and origin not in allowed:
                raise HTTPException(403, detail={"code": "AIR_MCP_ORIGIN_FORBIDDEN"})
        accept = {part.split(";")[0].strip() for part in request.headers.get("accept", "").split(",")}
        if not {"application/json", "text/event-stream"} <= accept:
            raise HTTPException(406, detail={"code": "AIR_MCP_ACCEPT_REQUIRED"})
        body = await document(request)
        method = body.get("method") if isinstance(body, dict) else None
        protocol = request.headers.get("mcp-protocol-version")
        if protocol is not None and protocol != PROTOCOL or method != "initialize" and protocol != PROTOCOL:
            raise HTTPException(400, detail={"code": "AIR_MCP_PROTOCOL_UNSUPPORTED"})
        session = Session(lambda name, args: invoke(store, principal, name, args, settings), access='auto')
        # No server sessions: each request carries its identity and protocol.
        session.ready = method != "initialize"
        session.initialized = session.ready
        result = await run_in_threadpool(session.handle, body)
        from air.redaction import redact
        result = redact(result, request.headers.get('authorization'))
        return Response(status_code=202) if result is None else JSONResponse(result)
