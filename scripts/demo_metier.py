"""Execute DEMO-METIER-1 on a fresh local AIR instance, through HTTP and MCP."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler
from air import __version__
from air.backup import snapshot, restore
from air.config import Settings, write_private
from air.core import digest
from air.foundation import exact, resolved
from air.mcp import APIClient, PROTOCOL, Session
from air.storage import Store
from demo_projections import evolve, read, ref
from demo_validation import request_for

ROOT = Path(__file__).resolve().parents[1]


def rehearse(output, fresh_environment=False, qualify_design_proofs=False, qualify_external_proofs=False):
    if os.environ.get("AIR_DATABASE_URL"):
        raise ValueError("Unset AIR_DATABASE_URL for the isolated SQLite demonstration")
    output.mkdir(parents=True, exist_ok=True)
    workspace = output / ("run-" + uuid.uuid4().hex)
    home = workspace / "home"
    environment = workspace / "venv" if fresh_environment else Path(sys.prefix)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    install = [sys.executable, str(ROOT / "scripts/install.py"), "--home", str(home), "--venv", str(environment), "--port", str(port)]
    command = install + ["--start"] + ([] if fresh_environment else ["--skip-install"])
    installed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=300)
    if installed.returncode:
        raise RuntimeError("Isolated installation failed; no acceptance report emitted")
    cases = read("manifest.json")["dossiers"]
    bases, dossiers, receipt_ids = [], [], []
    opener = build_opener(ProxyHandler({}))
    def call(endpoint, body=None, credential="credentials.json", expected=(200, 201)):
        secret = json.loads((home / credential).read_text(encoding="utf-8"))["access_token"]
        request = Request("http://127.0.0.1:" + str(port) + endpoint,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"})
        try:
            with opener.open(request, timeout=30) as response:
                status, result = response.status, json.load(response)
        except HTTPError as exc:
            status, result = exc.code, json.load(exc)
        assert status in expected, "Unexpected HTTP status " + str(status) + " at " + endpoint
        return result
    try:
        policy = {"version": "asteria-demo-1", "subjects": {"local-admin": {"read": ["*"], "write": ["*"]},
                  "independent-reviewer": {"read": ["*"], "review": ["asteria.sav", "asteria.atelier", "asteria.identites"]}}}
        store = Store(Settings.load(home).database_url)
        try:
            for case in cases:
                namespace = read(case["construction_baseline_request"])["meta"]["namespace"]
                actor = "architect-" + case["id"]
                policy["subjects"][actor] = {"read": [namespace, "asteria.shared"], "write": [namespace], "review": [namespace]}
                if qualify_external_proofs:
                    policy['subjects']['urn:asteria:runner:' + case['id']] = {'attest': [namespace]}
                write_private(home / (actor + ".json"), store.create_token(actor, "editor"))
            write_private(home / "reviewer.json", store.create_token("independent-reviewer", "editor"))
            write_private(home / "access-policy.json", policy)
        finally: store.engine.dispose()
        call("/v1/draft-bundles", read("shared.bootstrap.json"))
        for case in cases:
            objects = read(case["construction"])
            credential = "architect-" + case["id"] + ".json"
            own = [o for o in objects if o["meta"]["namespace"] != "asteria.shared"]
            call("/v1/draft-bundles", own, credential)
            base = call("/v1/baselines", read(case["construction_baseline_request"]), credential)
            bases.append(ref(base))
            request = {"baseline": ref(base)}
            assessment = call("/v1/construction/validations", request, credential)
            assert assessment["construction_ready"] and assessment["gate_decision"] == "BLOCKED"
            assert not assessment["authorization_granted"] and len(assessment["traceability"]) == 1
            assert all(c["execution"] == "NOT_EXECUTED" for c in assessment["verification_cases"])
            foundation = call("/v1/baselines", read(case["baseline_request"]), credential)
            gate = call("/v1/validations", request_for(case, foundation), credential)
            assert gate["gate_decision"] == "BLOCKED"
            assert gate["results"][0]["result"] == read(case["validation"])["expected_initial_result"]
            missing = deepcopy(read(case["construction_baseline_request"]))
            missing["meta"]["id"] += ":missing"
            missing["members"].append({"id": "urn:asteria:missing", "revision": 1})
            call("/v1/baselines", missing, credential, expected=(403, 422))
            target = next(o for o in objects if o["meta"]["type"] == "air.SemanticContract")
            evidence = next(o for o in objects if o["meta"]["type"] == "air.Evidence")
            def pin(obj): return {**exact(obj), "digest": digest(obj)}
            review = {"idempotency_key": case["id"], "baseline": ref(base), "target": pin(target), "outcome": "ACCEPTED",
                "rationale": "Revue fictive de la description du contrat ; ne prouve aucune exécution métier.",
                "evidence": [pin(evidence)], "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")}
            call("/v1/reviews", review, credential, expected=(403,))
            forged = deepcopy(review);forged["approved"] = True
            call("/v1/reviews", forged, "reviewer.json", expected=(422,))
            receipt = call("/v1/reviews", review, "reviewer.json")
            receipt_ids.append(receipt["record"]["id"])
            assert not call("/v1/reviews", review, "reviewer.json")["created"]
            assert call("/v1/reviews/" + quote(receipt["record"]["id"], safe=""), credential="reviewer.json")["effective"]
            assert call("/v1/construction/validations", request, credential)["gate_decision"] == "BLOCKED"
            artifact = call("/v1/views", request, credential)
            assert len(artifact["mapping"]) == 24
            (output / (case["id"] + ".html")).write_text(artifact["content"], encoding="utf-8", newline="\n")
            evolved = evolve(objects)
            call("/v1/draft-bundles", [o for o in evolved if o["meta"]["namespace"] == "asteria.shared"])
            call("/v1/draft-bundles", [o for o in evolved if o["meta"]["namespace"] != "asteria.shared"], credential)
            before = {o["meta"]["id"]: o for o in objects}
            meta = deepcopy(base["baseline"]["meta"]);meta.update(id="urn:asteria:identity-change:" + case["id"], type="air.ChangeSet")
            change = {"meta": meta, "body": {"base": exact(base["baseline"]),
                "operations": [{"op": "REPLACE", "before": resolved(before[o["meta"]["id"]]), "after": resolved(o)} for o in evolved if digest(o) != digest(before[o["meta"]["id"]])],
                "rationale": "Proposition de validité temporelle des comptes collecteurs.", "expected_revisions": base["baseline"]["body"]["members"], "approvals": []}}
            proposal = call("/v1/changes", change, credential)
            assert not proposal["approved"]
            assert not call("/v1/changes", change, credential)["change"]["created"]
            comparison = call("/v1/diffs", {"before": ref(base), "after": ref(proposal["target"])}, credential)
            assert comparison["changes"]
            session = Session(APIClient(home, credential, port))
            session.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "fresh-context", "version": "1"}}})
            session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
            resumed = session.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "air_export_baseline", "arguments": exact(base["baseline"])}})
            assert resumed["result"]["structuredContent"]["digest"] == base["digest"]
            proof = None
            external_proof = None
            if qualify_design_proofs:
                from demo_proofs import qualify
                proof = qualify(call, case, objects, base, credential, home, port, session, output)
                bases.append(proof['baseline'])
                receipt_ids.extend(proof['review_ids'])
            if qualify_external_proofs:
                from demo_external_proofs import qualify as qualify_external
                external_proof = qualify_external(call, case, objects, base, credential, home, port, session, output)
                bases.append(external_proof['baseline']);receipt_ids.append(external_proof['review_id'])
            dossiers.append({"dossier": case["id"], "title": case["title"], "status": "PASS", "baseline": ref(base),
                "assessment": assessment, "exception_gate": gate, "diff": comparison, "view_digest": artifact["digest"],
                "review_id": receipt["record"]["id"], "self_review_refused": True, "self_declared_approval_refused": True,
                "mcp_new_context_replay": True, "view": case["id"] + ".html",
                **({'design_proof_qualification': proof} if proof else {}),
                **({'external_proof_qualification': external_proof} if external_proof else {})})
        original_bases = [d['baseline'] for d in dossiers]
        call("/v1/views", {"baseline": original_bases[1]}, "architect-D01.json", expected=(403,))
        affected = call("/v1/impacts", {"baselines": original_bases, "targets": [{"id": "urn:asteria:scope:identity", "revision": 1}]})
        assert len(affected["baselines"]) == 3 and all(b["selected_targets"] and b["affected"] for b in affected["baselines"])
        backup = workspace / "backup"
        snapshot(home, backup)
        restored_home = workspace / "restored"
        restored_result = restore(backup, restored_home)
        restored = Store(Settings.load(restored_home).database_url)
        try:
            for baseline in bases:
                assert restored.export_baseline(baseline)["digest"] == baseline["digest"]
            assert all(restored.get_record(r) for r in receipt_ids)
            if qualify_design_proofs:
                from air.access import AccessPolicy
                from air.readiness import assess_readiness
                for dossier in dossiers:
                    proof = dossier['design_proof_qualification']
                    result = assess_readiness(restored, {'subject': 'independent-reviewer', 'role': 'editor'},
                                              AccessPolicy.load(restored_home), {'baseline': proof['baseline']})
                    # Recovery intentionally rotates policy/identity. Historical receipts survive,
                    # but the restored service must require renewed authority, not reuse our old test policy.
                    assert result['proof']['qualified_design_cases'] == 0
                    proof['restored_policy_invalidates_qualification'] = True
        finally: restored.engine.dispose()
        criteria = [{"id": c["id"], "status": "PASS_SCOPED"} for c in read("manifest.json")["milestone"]["requires"]]
        report = {"version": __version__, "milestone": "DEMO-METIER-1", "status": "PASS_SCOPED", "criteria": criteria,
            "scope": "Conception traçable dans le sous-profil construction/0.4 ; entreprise et revues entièrement fictives.",
            "fresh_sqlite_installation": True, "fresh_python_environment": fresh_environment, "http_executed": True, "mcp_executed": True,
            "dossiers": dossiers, "impact": affected, "restoration": restored_result, "cross_dossier_read_refused": True,
            "business_scenarios_executed": False, "execution_authorized": False, "live_instance_modified": False,
            "limitations": ["No native IDE client qualification", "No business runtime or machine/IAM action", "Not full AIR conformance"]}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        stopped = subprocess.run(install + ["--stop"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        if stopped.returncode:
            raise RuntimeError("Demonstration cleanup could not verify its server process")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-asteria/metier")
    parser.add_argument("--fresh-environment", action="store_true")
    parser.add_argument("--qualify-design-proofs", action="store_true", help="Also exercise the scoped P03 design review binding")
    parser.add_argument('--qualify-external-proofs', action='store_true', help='Run and attest three explicit synthetic Python test suites')
    args = parser.parse_args()
    result = rehearse(args.output.resolve(), args.fresh_environment, args.qualify_design_proofs or args.qualify_external_proofs, args.qualify_external_proofs)
    print(json.dumps({"status": result["status"], "milestone": result["milestone"], "dossiers": 3, "report": str(args.output / "report.json")}))


if __name__ == "__main__":
    main()
