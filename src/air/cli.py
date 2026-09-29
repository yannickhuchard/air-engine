import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from air import __version__
from air.config import Settings, protect_directory, write_private
from air.core import capabilities, validate
from air.parsing import MAX_BYTES, parse
from air.storage import Store, SCHEMA_VERSION
from air.foundation import validate_graph
from air.expr import evaluate
from air.transport import ServerBinding, client_transport
from air.atelier import apply_files, plan_files, previous_generation
from air import artifacts


def bootstrap(home):
    if home.is_symlink():
        raise ValueError("AIR home must not be a symlink")
    home = home.resolve()
    protect_directory(home)
    config = home / "config.json"
    if not config.exists():
        import uuid
        write_private(config, {"config_version": 1, "instance_id": str(uuid.uuid4()), "auth": {"mode": "local"}})
    settings = Settings.load(home)
    ServerBinding.load(home, settings.server).validate_tls()
    if settings.auth_mode == "oidc":
        from air.auth import OIDCVerifier
        OIDCVerifier(settings.oidc)
    store = Store(settings.database_url)
    try:
        store.migrate()
        from air.authority import sync_policy
        from air.access import AccessPolicy
        sync_policy(store, AccessPolicy.load(home), only_if_missing=True)
        credentials = home / "credentials.json"
        if settings.auth_mode == "local":
            if not credentials.exists():
                value = store.create_token("local-admin", "admin")
                try:
                    write_private(credentials, value)
                except Exception:
                    store.revoke_token(value["token_id"])
                    raise
            else:
                value = json.loads(credentials.read_text(encoding="utf-8"))
                if not store.authenticate(value.get("access_token", "")):
                    raise ValueError("Existing bootstrap credential is expired/revoked or belongs to another database; create a new token explicitly")
        return {"status": "ready", "home": str(home), "auth": settings.auth_mode,
                "database": store.engine.dialect.name, "credentials_file": str(credentials) if settings.auth_mode == "local" else None}
    finally:
        store.engine.dispose()


# Server commands that compile or judge whole baselines: they get a long timeout.
LONG_RUNNING = ("deliverables", "presentation", "readiness", "scenarios-walk", "scenario-simulate", "scenario-record", "guide",
                "drafts-validate", "drafts-rebase", "prepared-deposit", "prepared-freeze", "baseline-create", "portfolio-index",
                "portfolio-init", "workspace-init", "ide-setup", "architecture-inspect", "construction-validate", "gate-validate",
                "view", "workbench", "audience-view", "baseline-closure", "impact", "diff")


def resolve_transport(args):
    """An explicit --port or --url wins; otherwise the instance designated by --home tells where it listens."""
    port, url = args.port, args.url
    if port is None or url is None:
        try:
            declared = json.loads((args.home / "server.json").read_text(encoding="utf-8"))
            transport = declared.get("transport") or {}
            if port is None and type(declared.get("port")) is int: port = declared["port"]
            if url is None and isinstance(transport.get("origin"), str) and transport["origin"].startswith("https://"): url = transport["origin"]
        except (OSError, ValueError):
            pass
    return port or 8740, url, args.ca_file


def read_document(file):
    with file.open("rb") as stream:
        return parse(stream.read(MAX_BYTES + 1), "yaml" if file.suffix in (".yml", ".yaml") else "json")


def main(argv=None):
    # Machine-readable JSON must keep the same encoding on Windows and Unix,
    # including when an IDE redirects stdout into an artifact.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline='\n')
    parser = argparse.ArgumentParser(prog="air")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--home", type=Path, default=Path(os.environ.get("AIR_HOME", ".air")))
    parser.add_argument("--quiet", action="store_true", help="No progress animation on stderr (it never shows when stderr is not a terminal)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    commands.add_parser("doctor")
    commands.add_parser('workstation-check')
    monitor = commands.add_parser('monitor')
    monitor.add_argument('--warning-days',type=int,default=30)
    monitor.add_argument('--credential',default='credentials.json')
    archive = commands.add_parser('audit-export')
    archive.add_argument('destination',type=Path)
    archive.add_argument('--before',required=True)
    acceptance = commands.add_parser('operations-compare')
    acceptance.add_argument('targets',type=Path)
    acceptance.add_argument('capacity',type=Path)
    acceptance.add_argument('recovery',type=Path)
    reception = commands.add_parser('operations-reception-check')
    reception.add_argument('dossier',type=Path)
    commands.add_parser('client-reception-check').add_argument('dossier',type=Path)
    commands.add_parser('audit-verify').add_argument('directory',type=Path)
    server_config = commands.add_parser("server-configure")
    server_config.add_argument("file", type=Path)
    commands.add_parser("capabilities")
    commands.add_parser("worker-once")
    export = commands.add_parser("registry-export")
    export.add_argument("destination", type=Path)
    transfer = commands.add_parser("registry-import")
    transfer.add_argument("bundle", type=Path)
    transfer.add_argument("--target-database-env", help="Name of an environment variable containing the empty PostgreSQL target URL")
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    backup.add_argument("--timeout", type=float, default=300, help="SQLite snapshot deadline in seconds (1..3600)")
    restore = commands.add_parser("restore")
    restore.add_argument("backup", type=Path)
    commands.add_parser('backup-keygen').add_argument('directory', type=Path)
    for command in ('backup-encrypt', 'backup-decrypt'):
        sub = commands.add_parser(command)
        sub.add_argument('source', type=Path)
        sub.add_argument('destination', type=Path)
        sub.add_argument('--key-file', type=Path, required=True)
    policy = commands.add_parser("policy-set")
    policy.add_argument("file", type=Path)
    for command in ('proof-key-register', 'proof-key-revoke'):
        commands.add_parser(command).add_argument('file', type=Path)
    for command in ('proof-challenge', 'proof-import'):
        sub = commands.add_parser(command)
        sub.add_argument('file', type=Path)
        sub.add_argument('--credential', default='credentials.json')
        sub.add_argument('--port', type=int)
        sub.add_argument('--url')
        sub.add_argument('--ca-file', type=Path)
    expression = commands.add_parser("expr-evaluate")
    expression.add_argument("file", type=Path)
    skills_cmd = commands.add_parser("skills-export", help="Write AIR's portable Agent Skills for an agent (local, no server)")
    skills_cmd.add_argument("--target", type=Path, required=True, help="Repository root, or the directory receiving the zips")
    skills_cmd.add_argument("--layout", choices=["agents", "claude", "chatgpt"], default="agents",
                            help="agents: .agents/skills (Codex, Cursor, Antigravity, OpenCode, Gemini CLI); claude: .claude/skills; chatgpt: one zip per skill")
    skills_cmd.add_argument("--skill", action="append", help="Export only this skill (repeatable)")
    skills_cmd.add_argument("--apply", action="store_true", help="Write the files; without it, print the plan only")
    cmd = commands.add_parser("validate")
    cmd.add_argument("file", type=Path)
    cmd.add_argument("--closed", action="store_true", help="Check typed references and AIR-V003 in the supplied bundle")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int)
    serve.add_argument("--no-worker", action="store_true", help="Use a separate worker-once process instead of the embedded worker")
    tok = commands.add_parser("token-create")
    tok.add_argument("--subject", required=True)
    tok.add_argument("--role", choices=["reader", "editor", "admin"], default="reader")
    tok.add_argument("--days", type=int, default=30)
    tok.add_argument("--name", required=True, help="New credential filename within AIR home")
    revoke = commands.add_parser("token-revoke")
    revoke.add_argument("token_id")
    for name in ("put", "get", "bundle-put", "baseline-create", "baseline-export", "change-propose", "gate-validate", "construction-validate", "diff", "impact", "view", "review", "review-revoke", "plan", "simulate", "package-prepare", "package-publish", "package-read", "package-revoke", "context-create", "context-read", "reconcile", "discover", "job-submit", "job-read", "job-cancel", "capacity-publish", "capacity-get", "admission-propose", "admission-review", "admission-review-revoke", "admit", "admission-read", "admission-release", "activate", "renewal-propose", "renew", "closure-propose", "closure-review", "closure-review-revoke", "episode-close", "observation-ingest", "runtime-compare", "whoami", "collaboration-submit", "collaboration-read", "workbench", "goal-assess", "knowledge-inspect", "artifact-import", "artifact-describe", "artifact-read", "artifact-upload", "artifact-download", "audience-view", "view-capture", "view-read", "organization-inspect", "workflow-inspect", "data-validate", "state-replay", "policy-check", "architecture-inspect", "openapi-compile", "workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "baseline-closure", "guide", "revisions", "baseline-browse", "type-describe", "drafts-validate", "drafts-rebase", "prepared-deposit", "prepared-freeze", "readiness", "scenario-simulate", "scenario-record", "deliverables", "scenarios-walk", "presentation"):
        sub = commands.add_parser(name)
        sub.add_argument("--port", type=int)
        sub.add_argument("--url", help="Explicit AIR origin; HTTPS required outside loopback")
        sub.add_argument("--ca-file", type=Path, help="Trusted enterprise CA PEM for HTTPS")
        sub.add_argument("--credential", default="credentials.json")
        if name == "whoami": continue
        if name == "artifact-upload":
            sub.add_argument("--namespace", required=True)
            sub.add_argument("--media-type", default="application/octet-stream")
            sub.add_argument("--idempotency-key", required=True)
        if name in ("view", "workbench", "artifact-download", "audience-view", "openapi-compile", "presentation"):
            sub.add_argument("--output", type=Path, required=True)
        if name in ("workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "deliverables"):
            sub.add_argument("--workspace", type=Path, required=True, help="Repository directory receiving the generated files")
            sub.add_argument("--apply", action="store_true", help="Create missing files and refresh AIR-owned sections")
            sub.add_argument("--replace-generated", action="store_true", help="Also rewrite generated files that differ; seeded files stay untouched")
        if name in ("put", "bundle-put", "baseline-create", "change-propose", "gate-validate", "construction-validate", "diff", "impact", "view", "review", "review-revoke", "plan", "simulate", "package-prepare", "package-publish", "package-read", "package-revoke", "context-create", "context-read", "reconcile", "discover", "job-submit", "job-read", "job-cancel", "capacity-publish", "capacity-get", "admission-propose", "admission-review", "admission-review-revoke", "admit", "admission-read", "admission-release", "activate", "renewal-propose", "renew", "closure-propose", "closure-review", "closure-review-revoke", "episode-close", "observation-ingest", "runtime-compare", "whoami", "collaboration-submit", "collaboration-read", "workbench", "goal-assess", "knowledge-inspect", "artifact-import", "artifact-describe", "artifact-read", "artifact-upload", "artifact-download", "audience-view", "view-capture", "view-read", "organization-inspect", "workflow-inspect", "data-validate", "state-replay", "policy-check", "architecture-inspect", "openapi-compile", "workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "baseline-closure", "guide", "revisions", "baseline-browse", "type-describe", "drafts-validate", "drafts-rebase", "prepared-deposit", "prepared-freeze", "readiness", "scenario-simulate", "scenario-record", "deliverables", "scenarios-walk", "presentation"):
            sub.add_argument("file", type=Path)
        else:
            sub.add_argument("id")
            sub.add_argument("revision", type=int)
    args = parser.parse_args(argv)
    store = None
    # The progress animation writes to an interactive stderr only; stdout keeps the JSON result.
    from air import tui
    activity = tui.for_command(args.command, args.quiet)
    activity.enter(0)
    try:
        if args.command == "bootstrap":
            result = bootstrap(args.home)
        elif args.command == "server-configure":
            if (args.home / "server.json").exists():
                raise ValueError("Stop the verified AIR server before changing its transport")
            config = read_document(args.file)
            binding = ServerBinding.load(args.home, config)
            binding.validate_tls()
            configuration = json.loads((args.home / "config.json").read_text(encoding="utf-8"))
            configuration["server"] = config
            import uuid
            pending = args.home / ("config-" + uuid.uuid4().hex + ".tmp")
            try:
                write_private(pending, configuration)
                os.replace(pending, args.home / "config.json")
            finally:
                pending.unlink(missing_ok=True)
            result = {"status": "configured", "origin": binding.origin, "host": binding.host,
                      "tls": bool(binding.cert_file), "restart_required": True}
        elif args.command in ('proof-key-register', 'proof-key-revoke'):
            from air.external_proofs import register_key, revoke_key
            settings = Settings.load(args.home);store = Store(settings.database_url)
            request = read_document(args.file)
            result = register_key(store, settings, request) if args.command == 'proof-key-register' else revoke_key(store, request)
        elif args.command == "registry-export":
            from air.portability import export_registry
            from air.access import AccessPolicy
            store = Store(Settings.load(args.home).database_url)
            result = export_registry(store, args.destination, AccessPolicy.load(args.home).document)
        elif args.command == "registry-import":
            from air.portability import import_home
            import re
            target = None
            if args.target_database_env:
                if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", args.target_database_env):
                    raise ValueError("Invalid environment variable name")
                target = os.environ.get(args.target_database_env)
                if not target:
                    raise ValueError("Target database environment variable is unset")
            result = import_home(args.bundle, args.home, target)
        elif args.command == "backup":
            from air.backup import snapshot
            result = snapshot(args.home, args.destination, timeout=args.timeout)
        elif args.command == "restore":
            from air.backup import restore
            result = restore(args.backup, args.home)
        elif args.command == 'backup-keygen':
            from air.backup_crypto import create_key
            result = create_key(args.directory)
        elif args.command in ('backup-encrypt', 'backup-decrypt'):
            from air.backup_crypto import encrypt, decrypt
            operation = encrypt if args.command == 'backup-encrypt' else decrypt
            result = operation(args.source, args.destination, args.key_file)
        elif args.command == "policy-set":
            from air.access import AccessPolicy
            import uuid
            document = read_document(args.file)
            policy = AccessPolicy(document)
            protect_directory(args.home)
            pending = args.home / ("policy-" + uuid.uuid4().hex + ".json")
            try:
                write_private(pending, document)
                if pending.stat().st_size > 65536:
                    raise ValueError("Access policy exceeds 64 KiB")
                os.replace(pending, args.home / "access-policy.json")
            finally:
                if pending.exists():
                    pending.unlink()
            result = {"policy_digest": policy.digest, "version": document["version"]}
            if (args.home / "config.json").exists():
                from air.authority import sync_policy
                store = Store(Settings.load(args.home).database_url)
                store.check_version()
                result["authority_policy"] = sync_policy(store, policy)
            else:
                result["authority_policy"] = {"committed": False, "reason": "BOOTSTRAP_REQUIRED"}
        elif args.command == "capabilities":
            result = capabilities()
        elif args.command == "expr-evaluate":
            result = evaluate(read_document(args.file))
            activity.finish()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["execution"] == "EXECUTED" and result["result"] in ("KNOWN", "SATISFIED") else 1
        elif args.command == "skills-export":
            from air.skills import export
            result = export(args.target, args.layout, args.apply, args.skill)
            activity.finish()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        elif args.command == "validate":
            result = (validate_graph if args.closed else validate)(read_document(args.file))
            activity.finish()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["valid"] else 1
        elif args.command == 'monitor':
            from air.monitor import probe
            result = probe(args.home,args.warning_days,args.credential)
        elif args.command == 'operations-compare':
            from air.operations_acceptance import compare,read_report
            result = compare(read_report(args.targets),read_report(args.capacity),read_report(args.recovery))
        elif args.command == 'operations-reception-check':
            from air.operations_reception import check
            result = check(args.dossier)
        elif args.command == 'workstation-check':
            from air.workstation import inspect
            result = inspect(args.home)
        elif args.command == 'client-reception-check':
            from air.client_reception import check
            result = check(args.dossier)
        elif args.command == 'audit-export':
            from air.audit_archive import export
            result = export(args.home,args.destination,args.before)
        elif args.command == 'audit-verify':
            from air.audit_archive import verify
            result = verify(args.directory)
        elif args.command == "serve":
            from air.service_budget import install as install_service_budget
            install_service_budget()
            import uvicorn
            from air.api import create_app
            settings = Settings.load(args.home)
            binding = ServerBinding.load(args.home, settings.server, args.port)
            binding.validate_tls()
            from air.server_logging import EventLog, configuration
            event_log = EventLog(settings.home)
            app = create_app(settings, run_worker=not args.no_worker)
            app.state.event_log = event_log
            config = uvicorn.Config(app, host=binding.host, port=binding.port,
                        workers=1, proxy_headers=False, access_log=False,
                        log_config=configuration(event_log),
                        ssl_certfile=binding.cert_file, ssl_keyfile=binding.key_file)
            config.load()
            if config.ssl:
                import ssl
                config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
                config.ssl.keylog_filename = None
            activity.finish()
            try: uvicorn.Server(config).run()
            finally: event_log.close()
            return 0
        elif args.command in ("proof-challenge", "proof-import", "put", "get", "bundle-put", "baseline-create", "baseline-export", "change-propose", "gate-validate", "construction-validate", "diff", "impact", "view", "review", "review-revoke", "plan", "simulate", "package-prepare", "package-publish", "package-read", "package-revoke", "context-create", "context-read", "reconcile", "discover", "job-submit", "job-read", "job-cancel", "capacity-publish", "capacity-get", "admission-propose", "admission-review", "admission-review-revoke", "admit", "admission-read", "admission-release", "activate", "renewal-propose", "renew", "closure-propose", "closure-review", "closure-review-revoke", "episode-close", "observation-ingest", "runtime-compare", "whoami", "collaboration-submit", "collaboration-read", "workbench", "goal-assess", "knowledge-inspect", "artifact-import", "artifact-describe", "artifact-read", "artifact-upload", "artifact-download", "audience-view", "view-capture", "view-read", "organization-inspect", "workflow-inspect", "data-validate", "state-replay", "policy-check", "architecture-inspect", "openapi-compile", "workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "baseline-closure", "guide", "revisions", "baseline-browse", "type-describe", "drafts-validate", "drafts-rebase", "prepared-deposit", "prepared-freeze", "readiness", "scenario-simulate", "scenario-record", "deliverables", "scenarios-walk", "presentation"):
            filename = Path(args.credential)
            if filename.name != args.credential or filename.suffix != ".json":
                raise ValueError("Credential must be a JSON filename within AIR home")
            cred = json.loads((args.home / filename).read_text(encoding="utf-8"))
            writes = {"put": "/v1/drafts", "bundle-put": "/v1/draft-bundles",
                      "baseline-create": "/v1/baselines", "change-propose": "/v1/changes", "gate-validate": "/v1/validations", "construction-validate": "/v1/construction/validations", "diff": "/v1/diffs", "impact": "/v1/impacts", "view": "/v1/views", "review": "/v1/reviews", "review-revoke": "/v1/review-revocations", "plan": "/v1/plans", "simulate": "/v1/experiments", "package-prepare": "/v1/packages/prepare", "package-publish": "/v1/packages/publish", "package-read": "/v1/packages/read", "package-revoke": "/v1/packages/revoke", "context-create": "/v1/contexts", "context-read": "/v1/contexts/read", "reconcile": "/v1/reconciliations", "discover": "/v1/packages/discover", "job-submit": "/v1/jobs", "job-read": "/v1/jobs/read", "job-cancel": "/v1/jobs/cancel", "capacity-publish": "/v1/capacity/offers", "capacity-get": "/v1/capacity/read", "admission-propose": "/v1/admission/propose", "admission-review": "/v1/admission/review", "admission-review-revoke": "/v1/admission/revoke_review", "admit": "/v1/admission/admit", "admission-read": "/v1/admission/read", "admission-release": "/v1/admission/release", "activate": "/v1/admission/activate", "renewal-propose": "/v1/renewal/propose", "renew": "/v1/renewal/renew", "closure-propose": "/v1/closure/propose", "closure-review": "/v1/closure/review", "closure-review-revoke": "/v1/closure/revoke_review", "episode-close": "/v1/closure/close", "observation-ingest": "/v1/runtime/observations", "runtime-compare": "/v1/runtime/comparisons", "collaboration-submit": "/v1/collaboration/submissions", "collaboration-read": "/v1/collaboration/read", "workbench": "/v1/workbench", "goal-assess": "/v1/goals/assess", "knowledge-inspect": "/v1/knowledge/inspect", "artifact-import": "/v1/artifacts/import", "artifact-describe": "/v1/artifacts/describe", "artifact-read": "/v1/artifacts/read", "artifact-upload": "/v1/artifacts/upload", "artifact-download": "/v1/artifacts/download", "audience-view": "/v1/audience-views", "view-capture": "/v1/views/capture", "view-read": "/v1/views/read", "organization-inspect": "/v1/organization/inspect", "workflow-inspect": "/v1/workflow/inspect", "data-validate": "/v1/data/validate", "state-replay": "/v1/states/replay", "policy-check": "/v1/policies/check", "architecture-inspect": "/v1/architecture/inspect", "openapi-compile": "/v1/compilations/openapi", "workspace-init": "/v1/workspaces/compile", "ide-setup": "/v1/ide/adapters", "portfolio-init": "/v1/portfolios/compile", "portfolio-index": "/v1/portfolios/index", "baseline-closure": "/v1/baselines/closure", "guide": "/v1/agent/guide", "revisions": "/v1/agent/revisions", "baseline-browse": "/v1/agent/baselines/browse", "type-describe": "/v1/agent/types/describe", "drafts-validate": "/v1/agent/drafts/validate", "drafts-rebase": "/v1/agent/drafts/rebase", "prepared-deposit": "/v1/agent/prepared/deposit", "prepared-freeze": "/v1/agent/prepared/freeze", "readiness": "/v1/readiness/assess", "scenario-simulate": "/v1/simulations/scenario", "scenario-record": "/v1/simulations/record", "deliverables": "/v1/deliverables/compile", "scenarios-walk": "/v1/acceptance/walk", "presentation": "/v1/presentations/compile"}
            writes.update({"proof-challenge": "/v1/proofs/challenges", "proof-import": "/v1/proofs/import"})
            if args.command in writes:
                endpoint = writes[args.command]
                if args.command == "artifact-upload":
                    with args.file.open("rb") as stream: body = stream.read(artifacts.MAX_SIZE + 1)
                    if not 1 <= len(body) <= artifacts.MAX_SIZE: raise ValueError("Artifact must contain 1 byte to 16 MiB")
                else:
                    payload = read_document(args.file)
                    if args.command == "portfolio-index" and isinstance(payload, dict) and "portfolio" not in payload:
                        # The pins file stays small and never stale: the declaration comes from the central repository itself.
                        declaration = args.workspace / "air-portfolio.request.json"
                        if not declaration.is_file():
                            raise ValueError("portfolio-index needs 'portfolio' in the request or air-portfolio.request.json in the workspace")
                        payload = {**payload, "portfolio": read_document(declaration)}
                    if args.command == "presentation" and isinstance(payload, dict):
                        # The deck is for people: the CLI always asks for the page and writes it to --output.
                        payload = {**payload, "content": "HTML"}
                    body = json.dumps(payload).encode()
            elif args.command == "whoami":
                endpoint, body = "/v1/identity", None
            else:
                endpoint = (f"/v1/baselines/{quote(args.id, safe='')}/revisions/{args.revision}/export"
                            if args.command == "baseline-export" else f"/v1/objects/{quote(args.id, safe='')}/revisions/{args.revision}")
                body = None
            activity.enter(1)
            base_url, opener = client_transport(*resolve_transport(args))
            headers = {"Authorization": "Bearer " + cred["access_token"], "Content-Type": "application/json"}
            if args.command == "artifact-upload":
                headers.update({"Content-Type": "application/octet-stream", "X-AIR-Namespace": args.namespace,
                    "X-AIR-Media-Type": args.media_type, "Idempotency-Key": args.idempotency_key})
            req = Request(base_url + endpoint, data=body, headers=headers)
            if args.command == "artifact-download":
                import hashlib
                lookup = json.loads(body)
                metadata_request = Request(base_url + "/v1/artifacts/describe", data=body, headers=headers)
                with opener.open(metadata_request, timeout=30) as response:
                    metadata_bytes = response.read(MAX_BYTES + 1)
                    if len(metadata_bytes) > MAX_BYTES: raise ValueError("Artifact metadata exceeds budget")
                    result = json.loads(metadata_bytes)
                if result.get("artifact") != lookup["artifact"] or type(result.get("size")) is not int or not 1 <= result["size"] <= artifacts.MAX_SIZE:
                    raise ValueError("Artifact response differs from the requested manifest")
                with opener.open(req, timeout=30) as response:
                    artifact_content = response.read(artifacts.MAX_SIZE + 1)
                if len(artifact_content) != result["size"] or "sha256:" + hashlib.sha256(artifact_content).hexdigest() != result["content_digest"]:
                    raise ValueError("Downloaded artifact checksum or size differs")
            else:
                # compilations over several baselines can take minutes; a plain read stays short
                timeout = 600 if args.command in LONG_RUNNING else 30 if args.command == "artifact-upload" else 15
                with opener.open(req, timeout=timeout) as response:
                    payload = response.read(8 * MAX_BYTES + 1)
                    if len(payload) > 8 * MAX_BYTES: raise ValueError("AIR result exceeds adapter output budget")
                    result = json.loads(payload)
            activity.enter(2)
        else:
            if args.command == 'worker-once':
                from air.service_budget import install as install_service_budget
                install_service_budget()
            settings = Settings.load(args.home)
            store = Store(settings.database_url)
            store.check_version()
            if args.command == "worker-once":
                from air.jobs import run_next
                result = run_next(store, settings)
            elif args.command == "doctor":
                binding = ServerBinding.load(args.home, settings.server)
                binding.validate_tls()
                if settings.auth_mode == "oidc":
                    from air.auth import OIDCVerifier
                    OIDCVerifier(settings.oidc)
                result = {"status": "ok", "version": __version__, "schema": SCHEMA_VERSION,
                          "database": store.engine.dialect.name, "auth": settings.auth_mode,
                          "oidc_live_verified": False, "transport": {"origin": binding.origin, "host": binding.host, "tls": bool(binding.cert_file)}, **store.counts(), "capabilities": capabilities()}
            elif settings.auth_mode != "local":
                raise ValueError("Local tokens are disabled in OIDC mode")
            elif args.command == "token-create":
                filename = Path(args.name)
                if filename.name != args.name or filename.suffix != ".json" or filename.name == "config.json":
                    raise ValueError("Use a new JSON filename within AIR home")
                destination = args.home / filename
                if destination.exists():
                    raise ValueError("Credential file already exists; use a new name")
                value = store.create_token(args.subject, args.role, args.days)
                try:
                    write_private(destination, value)
                except Exception:
                    store.revoke_token(value["token_id"])
                    raise
                result = {"token_id": value["token_id"], "credentials_file": str(destination)}
            else:
                result = {"revoked": store.revoke_token(args.token_id)}
        if args.command == "artifact-download":
            with args.output.open("xb") as stream: stream.write(artifact_content)
            result["output"] = str(args.output.resolve())
        if args.command == "openapi-compile":
            import hashlib
            compiled = result.pop("content").encode("utf-8")
            if len(compiled) != result["size"] or "sha256:" + hashlib.sha256(compiled).hexdigest() != result["content_digest"]:
                raise ValueError("Compiled output checksum or size differs")
            with args.output.open("xb") as stream: stream.write(compiled)
            result["output"] = str(args.output.resolve())
        if args.command in ("workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "deliverables"):
            root = args.workspace
            # A plan writes nothing, not even its own directory.
            if args.apply: root.mkdir(parents=True, exist_ok=True)
            previous = previous_generation(root, result["files"])
            steps = plan_files(root, result["files"], previous)
            blocked = [s["path"] for s in steps if s["action"] in ("CONFLICT", "SECTION_MISSING")]
            if args.apply and blocked and not args.replace_generated:
                # All or nothing: a partial refresh would leave instructions and permissions out of step.
                result["written"] = []
                result["hint"] = ("Nothing was written: these files differ from what AIR generated and were edited locally: " + ", ".join(blocked)
                                  + ". Review the diffs, then rerun with --replace-generated to overwrite them (seeded files are never overwritten).")
            elif args.apply:
                result["written"] = apply_files(root, result["files"], steps, args.replace_generated)
                steps = plan_files(root, result["files"], previous_generation(root, result["files"]))
            elif blocked:
                result["hint"] = "Files edited locally would conflict: " + ", ".join(blocked) + ". --apply --replace-generated overwrites them."
            result.pop("files")
            result["workspace_directory"] = str(root.resolve());result["applied"] = bool(args.apply);result["plan"] = steps
        if args.command == "presentation":
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(result.pop("html"))
            result["output"] = str(args.output.resolve())
        if args.command in ("view", "workbench", "audience-view"):
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(result.pop("content"))
            result["output"] = str(args.output.resolve())
        activity.finish(tui.summary(args.command, result))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == 'monitor': return 0 if result['status']=='PASS' else 2
        if args.command == 'operations-compare': return 0 if result['status']=='PASS_MEASURED_THRESHOLDS' else 2
        if args.command == 'operations-reception-check': return 0 if result['status']=='READY_FOR_INDEPENDENT_REVIEW' else 2
        if args.command == 'workstation-check': return 0 if result['status']=='PASS' else 2
        if args.command == 'client-reception-check': return 0 if result['evidence_complete'] else 2
        if args.command in ("plan", "simulate"):
            return 0 if result["result"] == "SATISFIED" else 1
        if args.command in ("gate-validate", "construction-validate"):
            return 0 if result["gate_decision"] == "PASSED" else 1
        if args.command in ("workspace-init", "ide-setup", "portfolio-init", "portfolio-index", "deliverables"):
            return 1 if any(step["action"] in ("CONFLICT", "SECTION_MISSING") for step in result["plan"]) else 0
        return 0
    except HTTPError as exc:
        try:
            response = json.loads(exc.read(MAX_BYTES + 1))
        except (ValueError, UnicodeError):
            response = None
        activity.fail("HTTP %s" % exc.code)
        print(json.dumps({"error": "AIR_HTTP", "status": exc.code, "response": response}), file=sys.stderr)
        return 1
    except URLError as exc:
        origin = locals().get("base_url", "unknown origin")
        activity.fail(str(origin))
        print(json.dumps({"error": "AIR_UNREACHABLE", "origin": origin, "reason": str(getattr(exc, "reason", exc))[:200],
                          "hint": "Is the AIR server started for this home, and does --port or --url match it?"}), file=sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as exc:
        activity.fail(str(exc)[:160])
        print(json.dumps({"error": "AIR_CONFIGURATION_OR_INPUT", "message": str(exc)}), file=sys.stderr)
        return 1
    except Exception as exc:
        # Do not print connection strings, driver exceptions or secrets in unattended logs.
        activity.fail(type(exc).__name__)
        print(json.dumps({"error": "AIR_RUNTIME", "exception": type(exc).__name__}), file=sys.stderr)
        return 1
    finally:
        activity.fail()
        if store:
            store.engine.dispose()
