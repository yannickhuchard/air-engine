from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool
from air import __version__
from air import question_capsule
from air import transformation_view, project_updates, video_refresh
from air import completeness, interface_contracts
from air.auth import OIDCVerifier
from air.core import capabilities, schema, TYPES, validate
from air.parsing import parse
from air.storage import Conflict, Store
from air.foundation import InvalidModel, validate_graph
from air.expr import evaluate
from air.gates import validate_gate
from air.construction import assess_baseline
from air.projections import diff, impact, view
from air.planning import plan
from air.experiments import simulate
from air.contexts import create_context, read_context, reconcile
from air.discovery import discover
from air import jobs, admission, renewal, closure, runtime, collaboration
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
from air.access import AccessPolicy, ScopedStore, Forbidden, NotFound, PolicyUnavailable
from air import acceptance, agent, business_paths, branding, deliverables, presentation, readiness
from air.reviews import create_review, read_review, revoke_review


from air.transport import ServerBinding, request_origin_allowed


def create_app(settings, run_worker=True):
    from air.job_budget import limits as job_limits
    job_limits()
    binding = ServerBinding.load(settings.home, settings.server)
    store = Store(settings.database_url)
    store.check_version()
    oidc = OIDCVerifier(settings.oidc) if settings.auth_mode == "oidc" else None

    @asynccontextmanager
    async def lifespan(app):
        import asyncio
        stopping = asyncio.Event()
        async def worker_loop():
            while not stopping.is_set():
                try:
                    app.state.worker_status = "PROCESSING"
                    result = await run_in_threadpool(jobs.run_next, store, settings)
                    app.state.worker_status = "IDLE"
                    if result['processed']: continue
                except Exception:
                    # No arbitrary driver text or credentials in logs. The lease
                    # stays recoverable after a transient database failure.
                    app.state.worker_status = "RETRYING"
                try: await asyncio.wait_for(stopping.wait(), timeout=1)
                except TimeoutError: pass
        task = asyncio.create_task(worker_loop()) if run_worker else None
        try:
            yield
        finally:
            stopping.set()
            if task: await task
            app.state.worker_status = "STOPPED"
            store.engine.dispose()

    app = FastAPI(title="AIR bootstrap", version=__version__, docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    if binding.cert_file:
        @app.middleware("http")
        async def tls_origin(request, call_next):
            if request.url.scheme != "https" or not request_origin_allowed(request.headers, binding.origin):
                return JSONResponse({"detail": {"code": "AIR_TRANSPORT_ORIGIN_FORBIDDEN"}}, status_code=403)
            return await call_next(request)
    app.state.store = store
    from air.request_authority import ResponseAuthority, current as request_authority
    app.add_middleware(ResponseAuthority, store=store)
    from air.operations import State, AdmissionGuard, read_document_bytes
    app.state.operations = State()
    app.add_middleware(AdmissionGuard, state=app.state.operations)
    app.state.worker_status = "STARTING" if run_worker else "DISABLED"
    bearer = HTTPBearer(auto_error=False)

    async def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        principal = None
        if credentials and credentials.scheme.lower() == "bearer":
            principal = await run_in_threadpool(oidc.authenticate, credentials.credentials, True) if oidc else await run_in_threadpool(store.authenticate, credentials.credentials, include_binding=True)
        if principal is None:
            raise HTTPException(401, detail={"code": "AIR_UNAUTHENTICATED"}, headers={"WWW-Authenticate": "Bearer"})
        principal["authorization"]["instance_id"] = settings.instance_id
        principal["policy"] = await run_in_threadpool(AccessPolicy.load, settings.home)
        if not app.state.operations.enter_subject(principal['subject']):
            raise HTTPException(429, detail={'code': 'AIR_SUBJECT_BUSY'}, headers={'Retry-After': '1'})
        try:
            authority = (store, principal, principal['policy'], settings)
            request.state.air_authority = authority
            context = request_authority.set(authority)
            try: yield principal
            finally: request_authority.reset(context)
        finally: app.state.operations.leave_subject(principal['subject'])

    def scoped(principal):
        return ScopedStore(store, principal, principal["policy"])

    def writer(principal=Depends(identity)):
        if principal["role"] not in ("editor", "admin"):
            raise HTTPException(403, detail={"code": "AIR_FORBIDDEN"})
        return principal

    async def document(request):
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise HTTPException(415, detail={"code": "AIR_JSON_REQUIRED"})
        data = await read_document_bytes(request, app.state.operations)
        try:
            return await run_in_threadpool(parse, data)
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "AIR_PARSE", "message": str(exc)}) from exc

    def error_response(request, payload, status, headers=None):
        from air.redaction import redact
        return JSONResponse(redact(payload, request.headers.get('authorization')), status_code=status, headers=headers)

    @app.exception_handler(HTTPException)
    async def http_exception(request, exc):
        return error_response(request, {'detail': exc.detail}, exc.status_code, exc.headers)

    @app.exception_handler(Forbidden)
    async def forbidden(request, exc):
        return error_response(request, {"detail": {"code": "AIR_FORBIDDEN", "unavailable_references": getattr(exc, "unavailable", [])}}, 403)

    @app.exception_handler(NotFound)
    async def not_found(request, exc):
        return error_response(request, {"detail": {"code": "AIR_NOT_FOUND", "message": str(exc), **exc.detail}}, 404)

    @app.exception_handler(PolicyUnavailable)
    async def invalid_policy(request, exc):
        return JSONResponse({"detail": {"code": "AIR_POLICY_UNAVAILABLE"}}, status_code=503)

    @app.exception_handler(OperationalError)
    async def unavailable(request, exc):
        return JSONResponse({"detail": {"code": "AIR_STORAGE_UNAVAILABLE"}}, status_code=503)

    @app.exception_handler(InvalidModel)
    async def invalid_model(request, exc):
        from air.foundation import TooLarge
        code = "AIR_OUTPUT_TOO_LARGE" if isinstance(exc, TooLarge) else "AIR_INVALID_MODEL"
        return error_response(request, {"detail": {"code": code, "message": str(exc), "report": exc.report}}, 422)

    from air.quotas import QuotaExceeded
    @app.exception_handler(QuotaExceeded)
    async def quota_exceeded(request, exc):
        return JSONResponse({'detail':{'code':'AIR_QUOTA_EXCEEDED','resource':exc.resource}}, status_code=429)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return error_response(request, {"detail": {"code": "AIR_REVISION_CONFLICT", "message": str(exc)}}, 409)

    @app.get("/health")
    def health():
        store.check_version()
        import os
        return {"status": "ok", "service": "air", "version": __version__,
                "instance_id": settings.instance_id, "pid": os.getpid(), "worker": app.state.worker_status}

    @app.get("/v1/capabilities")
    def get_capabilities(principal=Depends(identity)):
        return capabilities()

    @app.get('/ready')
    def ready():
        try:
            store.check_version()
            AccessPolicy.load(settings.home)
            available = app.state.worker_status in ('IDLE', 'PROCESSING', 'DISABLED')
            event_log = getattr(app.state, 'event_log', None)
            if event_log is not None and not event_log.snapshot()['last_write_ok']: available = False
        except Exception:
            available = False
        return JSONResponse({'status': 'ready' if available else 'not_ready'}, status_code=200 if available else 503)

    @app.get('/v1/operations')
    def operational_status(principal=Depends(identity)):
        if principal['role'] != 'admin': raise Forbidden('Operational metrics require an administrator')
        principal['policy'].require(principal, 'operate', 'air.system')
        event_log = getattr(app.state, 'event_log', None)
        log_state = event_log.snapshot() if event_log is not None else None
        from air.quotas import status as quota_status
        from air.resource_usage import status as resource_status
        with store.engine.connect() as conn: quotas = quota_status(conn)
        resources = resource_status(settings.home)
        return {**app.state.operations.snapshot(), 'worker': app.state.worker_status,
                'quotas': quotas,
                'resources': resources,
                'event_log': log_state,
                'alerts': {'home_volume_low': resources['home_volume_low'],
                           'worker_retrying': app.state.worker_status == 'RETRYING',
                           'event_log_unavailable': log_state is not None and not log_state['last_write_ok']}}

    @app.get("/v1/schemas/{type_name}")
    def get_schema(type_name: str, principal=Depends(identity)):
        if type_name not in TYPES:
            raise HTTPException(404, detail={"code": "AIR_TYPE_UNSUPPORTED"})
        return schema(type_name)

    @app.get("/openapi.json")
    def openapi(principal=Depends(identity)):
        return app.openapi()

    @app.post("/v1/bootstrap/validations")
    async def validation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(validate, await document(request))

    @app.post("/v1/foundation/validations")
    async def graph_validation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(validate_graph, await document(request))

    @app.post("/v1/expressions/evaluate")
    async def expression_evaluation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(evaluate, await document(request))

    @app.post("/v1/validations")
    async def gate_validation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(validate_gate, scoped(principal), await document(request))

    @app.post("/v1/construction/validations")
    async def construction_validation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(assess_baseline, scoped(principal), await document(request))

    @app.post("/v1/artifacts/import")
    async def artifact_import(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(artifacts.import_base64, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/artifacts/upload")
    async def artifact_upload(request: Request, principal=Depends(writer)):
        if request.headers.get("content-type") != "application/octet-stream":
            raise HTTPException(415, detail={"code": "AIR_BINARY_REQUIRED"})
        descriptor = {"namespace": request.headers.get("x-air-namespace", ""),
            "media_type": request.headers.get("x-air-media-type", "application/octet-stream"),
            "idempotency_key": request.headers.get("idempotency-key", "")}
        from air.foundation import check_schema
        check_schema(descriptor, artifacts.UPLOAD)
        principal["policy"].require(principal, "write", descriptor["namespace"])
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > artifacts.MAX_SIZE: raise HTTPException(413, detail={"code": "AIR_ARTIFACT_TOO_LARGE"})
            data.extend(chunk)
        return await run_in_threadpool(artifacts.put, store, principal, principal["policy"], settings, descriptor, bytes(data))

    @app.post("/v1/artifacts/describe")
    async def artifact_describe(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(artifacts.describe, store, principal, principal["policy"], await document(request))

    @app.post("/v1/artifacts/read")
    async def artifact_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(artifacts.read_base64, store, principal, principal["policy"], await document(request))

    @app.post("/v1/artifacts/download")
    async def artifact_download(request: Request, principal=Depends(identity)):
        result, data = await run_in_threadpool(artifacts.download, store, principal, principal["policy"], await document(request))
        return Response(data, media_type=result["media_type"], headers={"Content-Disposition": 'attachment; filename="air-artifact.bin"',
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store", "X-AIR-Content-SHA256": result["content_digest"].split(":")[1]})

    @app.post("/v1/views/capture")
    async def captured_view_create(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(view_capture.capture, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/views/read")
    async def captured_view_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(view_capture.read, store, principal, principal["policy"], await document(request))

    @app.post("/v1/audience-views")
    async def audience_view(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_audience_view, store, principal, principal["policy"], await document(request))

    @app.post("/v1/compilations/openapi")
    async def openapi_compilation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_openapi, store, principal, principal["policy"], await document(request))

    @app.post('/v1/completeness/assess')
    async def contextual_completeness(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(completeness.assess, store, principal, principal['policy'], await document(request))

    @app.post('/v1/interfaces/compile')
    async def interface_suite(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(interface_contracts.compile_suite, store, principal, principal['policy'], await document(request))

    @app.post('/v1/interfaces/verify')
    async def interface_exchange(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(interface_contracts.verify, store, principal, principal['policy'], await document(request))

    @app.post("/v1/workspaces/compile")
    async def workspace_compilation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_workspace, store, principal, principal["policy"], await document(request))

    @app.post("/v1/ide/adapters")
    async def ide_adapter(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_adapter, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/guide")
    async def agent_guide(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.guide, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/questions/resume")
    async def question_resume(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(question_capsule.resume, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/agent/revisions")
    async def agent_revisions(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.list_revisions, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/baselines/browse")
    async def agent_browse(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.browse_baseline, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/types/describe")
    async def agent_describe_type(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.describe_type, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/drafts/validate")
    async def agent_validate(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.validate_drafts, store, principal, principal["policy"], await document(request))

    @app.post("/v1/acceptance/walk")
    async def acceptance_walk(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(acceptance.walk_baseline, store, principal, principal["policy"], await document(request))

    @app.post("/v1/presentations/compile")
    async def presentation_compile(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(presentation.compile_presentation, store, principal, principal["policy"], await document(request))

    @app.post("/v1/deliverables/compile")
    async def deliverables_pack(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(deliverables.compile_deliverables, store, principal, principal["policy"], await document(request))

    @app.post("/v1/branding/compile")
    async def branding_profile(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(branding.compile_branding, store, principal, principal["policy"], await document(request))

    @app.post("/v1/readiness/assess")
    async def readiness_gate(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(readiness.assess_readiness, store, principal, principal["policy"], await document(request))

    @app.post("/v1/simulations/scenario")
    async def scenario_simulation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(readiness.simulate_scenario, store, principal, principal["policy"], await document(request))

    @app.post("/v1/simulations/record")
    async def scenario_record(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(readiness.record_simulation, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/agent/prepared/deposit")
    async def agent_deposit(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(agent.deposit_prepared, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/prepared/freeze")
    async def agent_freeze(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(agent.freeze_prepared, store, principal, principal["policy"], await document(request))

    @app.post("/v1/agent/drafts/rebase")
    async def agent_rebase(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(agent.rebase_drafts, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/baselines/closure")
    async def baseline_closure(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compute_closure, store, principal, principal["policy"], await document(request))

    @app.post("/v1/portfolios/compile")
    async def portfolio_compilation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_portfolio, store, principal, principal["policy"], await document(request))

    @app.post("/v1/portfolios/index")
    async def portfolio_index(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(index_portfolio, store, principal, principal["policy"], await document(request))

    @app.post("/v1/project-updates/query")
    async def project_news(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(project_updates.query, store, principal, principal["policy"], await document(request))

    @app.post("/v1/videos/refresh")
    async def video_companions(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(video_refresh.prepare, store, principal, principal["policy"], await document(request))

    @app.post("/v1/transformations/query")
    async def transformation_query(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(transformation_view.query, store, principal, principal["policy"], await document(request))

    @app.post("/v1/architecture/inspect")
    async def architecture_dossier(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(inspect_architecture, store, principal, principal["policy"], await document(request))

    @app.post("/v1/policies/check")
    async def policy_check(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(check_policy, store, principal, principal["policy"], await document(request))

    @app.post("/v1/states/replay")
    async def state_replay(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(replay_state, store, principal, principal["policy"], await document(request))

    @app.post("/v1/data/validate")
    async def data_validation(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(validate_payload, store, principal, principal["policy"], await document(request))

    @app.post("/v1/workflow/inspect")
    async def workflow_dossier(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(inspect_workflow, store, principal, principal["policy"], await document(request))

    @app.post("/v1/business-paths/query")
    async def business_path_query(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(business_paths.query_paths, store, principal, principal["policy"], await document(request))

    @app.post("/v1/organization/inspect")
    async def organization_dossier(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(inspect_organization, store, principal, principal["policy"], await document(request))

    @app.post("/v1/knowledge/inspect")
    async def knowledge_dossier(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(inspect_knowledge, store, principal, principal["policy"], await document(request))

    @app.post("/v1/temporal/reconstruct")
    async def temporal_reconstruct(request: Request, principal=Depends(identity)):
        from air.temporal import reconstruct
        return await run_in_threadpool(reconstruct, store, principal, principal["policy"], await document(request))

    @app.post("/v1/currency/convert")
    async def currency_convert(request: Request, principal=Depends(identity)):
        from air.currency import convert
        return await run_in_threadpool(convert, store, principal, principal["policy"], await document(request))

    @app.post("/v1/federation/checkpoints")
    async def federation_import(request: Request, principal=Depends(identity)):
        from air.federation import ingest
        return await run_in_threadpool(ingest, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/federation/read")
    async def federation_read(request: Request, principal=Depends(identity)):
        from air.federation import read
        return await run_in_threadpool(read, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/connectors/preview")
    async def connector_preview(request: Request, principal=Depends(identity)):
        from air.connectors import preview
        return await run_in_threadpool(preview, store, principal, principal["policy"], await document(request))

    @app.post("/v1/goals/assess")
    async def goal_assessment(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(assess_goal, store, principal, principal["policy"], await document(request))

    @app.post("/v1/workbench")
    async def workbench(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(compile_workbench, store, principal, principal["policy"], settings, await document(request))

    @app.get("/v1/identity")
    def current_identity(principal=Depends(identity)):
        return collaboration.whoami(principal, settings)

    @app.post("/v1/collaboration/submissions")
    async def collaboration_submit(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(collaboration.submit, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/collaboration/read")
    async def collaboration_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(collaboration.read, store, principal, principal["policy"], await document(request))

    @app.post("/v1/runtime/observations")
    async def runtime_ingest(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(runtime.ingest, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/runtime/comparisons")
    async def runtime_compare(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(runtime.compare, store, principal, principal["policy"], await document(request))

    @app.post("/v1/renewal/propose")
    async def renewal_propose(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(renewal.propose, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/renewal/renew")
    async def renewal_renew(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(renewal.renew, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/closure/propose")
    async def closure_propose(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(closure.propose, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/closure/review")
    async def closure_review(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(closure.review, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/closure/revoke_review")
    async def closure_revoke_review(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(closure.revoke_review, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/closure/close")
    async def closure_close(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(closure.close, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/propose")
    async def admission_propose(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.propose, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/review")
    async def admission_review(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.review, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/revoke_review")
    async def admission_revoke_review(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.revoke_review, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/admit")
    async def admission_admit(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.admit, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/read")
    async def admission_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(admission.read, store, principal, principal["policy"], await document(request))

    @app.post("/v1/admission/release")
    async def admission_release(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.release, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/admission/activate")
    async def admission_activate(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(admission.activate, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/capacity/offers")
    async def capacity_offer(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(publish_offer, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/capacity/read")
    async def capacity_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(get_offer, store, principal, principal["policy"], await document(request))

    @app.post("/v1/jobs")
    async def submit_job(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(jobs.submit, store, principal, principal["policy"], settings, await document(request))

    @app.post("/v1/jobs/read")
    async def read_job(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(jobs.get_job, store, principal, principal["policy"], await document(request))

    @app.post("/v1/jobs/cancel")
    async def cancel_job(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(jobs.cancel, store, principal, principal["policy"], await document(request))

    @app.post("/v1/packages/discover")
    async def package_discover(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(discover, store, principal, principal["policy"], await document(request))

    @app.post("/v1/contexts")
    async def context_snapshot(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(create_context, store, principal, principal["policy"], await document(request))

    @app.post("/v1/contexts/read")
    async def context_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(read_context, store, principal, principal["policy"], await document(request))

    @app.post("/v1/reconciliations")
    async def context_reconcile(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(reconcile, store, principal, principal["policy"], await document(request))

    @app.post("/v1/packages/prepare")
    async def package_prepare(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(prepare_package, store, principal, principal["policy"], await document(request))

    @app.post("/v1/packages/publish")
    async def package_publish(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(publish_package, store, principal, principal["policy"], await document(request))

    @app.post("/v1/packages/read")
    async def package_read(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(read_package, store, principal, principal["policy"], await document(request))

    @app.post("/v1/packages/revoke")
    async def package_revoke(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(revoke_package, store, principal, principal["policy"], await document(request))

    @app.post("/v1/experiments")
    async def experiment(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(simulate, scoped(principal), await document(request))

    @app.post("/v1/plans")
    async def capacity_plan(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(plan, scoped(principal), await document(request))

    @app.post("/v1/diffs")
    async def diff_baselines(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(diff, scoped(principal), await document(request))

    @app.post("/v1/impacts")
    async def impact_baselines(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(impact, scoped(principal), await document(request))

    @app.post("/v1/views")
    async def compile_view(request: Request, principal=Depends(identity)):
        return await run_in_threadpool(view, scoped(principal), await document(request))

    @app.post("/v1/proofs/challenges")
    async def proof_challenge(request: Request, principal=Depends(writer)):
        from air.external_proofs import challenge
        return await run_in_threadpool(challenge, store, principal, principal['policy'], settings, await document(request))

    @app.post("/v1/proofs/import")
    async def proof_import(request: Request, principal=Depends(writer)):
        from air.external_proofs import import_report
        return await run_in_threadpool(import_report, store, principal, principal['policy'], settings, await document(request))

    @app.post("/v1/reviews")
    async def review(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(create_review, store, principal, principal["policy"], await document(request), settings)

    @app.get("/v1/reviews/{review_id:path}")
    def get_review(review_id: str, principal=Depends(identity)):
        return read_review(store, principal, principal["policy"], review_id)

    @app.post("/v1/review-revocations")
    async def revoke(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(revoke_review, store, principal, principal["policy"], await document(request), settings)

    @app.post("/v1/draft-bundles")
    async def put_bundle(request: Request, principal=Depends(writer)):
        return await run_in_threadpool(scoped(principal).put_bundle, await document(request), principal["subject"])

    @app.post("/v1/baselines")
    async def create_baseline(request: Request, principal=Depends(writer)):
        result = await run_in_threadpool(scoped(principal).create_baseline, await document(request), principal["subject"])
        return JSONResponse(result, status_code=201 if result["created"] else 200)

    @app.get("/v1/baselines/{object_id:path}/revisions/{revision}/export")
    def export_baseline(object_id: str, revision: int, principal=Depends(identity)):
        return scoped(principal).export_baseline({"id": object_id, "revision": revision})

    @app.post("/v1/changes")
    async def propose_change(request: Request, principal=Depends(writer)):
        result = await run_in_threadpool(scoped(principal).propose_change, await document(request), principal["subject"])
        return JSONResponse(result, status_code=201 if result["change"]["created"] else 200)

    @app.post("/v1/drafts")
    async def put_draft(request: Request, principal=Depends(writer)):
        obj = await document(request)
        report = await run_in_threadpool(validate, obj)
        if not report["valid"] or not isinstance(obj, dict):
            raise HTTPException(422, detail={"code": "AIR_INVALID", "report": report})
        try:
            result = await run_in_threadpool(scoped(principal).put, obj, principal["subject"])
            return JSONResponse(result, status_code=201 if result["created"] else 200)
        except Conflict as exc:
            raise HTTPException(409, detail={"code": "AIR_REVISION_CONFLICT", "message": str(exc)}) from exc

    @app.get("/v1/objects/{object_id:path}/revisions/{revision}")
    def get_object(object_id: str, revision: int, principal=Depends(identity)):
        guarded = scoped(principal)
        obj = guarded.get(object_id, revision)
        if obj is None:
            raise guarded.missing(object_id, revision)
        return obj

    @app.get("/v1/audit")
    def audit(principal=Depends(identity)):
        if principal["role"] != "admin":
            raise HTTPException(403, detail={"code": "AIR_FORBIDDEN"})
        return {"events": scoped(principal).audit_log(), "limit": 100}

    from air.mcp_http import install as install_mcp
    install_mcp(app, store, identity, document, settings)
    return app
