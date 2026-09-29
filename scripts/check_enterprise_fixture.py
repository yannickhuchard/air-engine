"""Preflight the three fictional dossiers; this is not a business acceptance demo."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from air.core import digest, references, validate
from air.parsing import parse
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/enterprise/asteria"


def read_relative(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Fixture path escapes its directory")
    return parse(path.read_bytes())


def load_fixture(base=FIXTURE):
    manifest = read_relative(base, "manifest.json")
    if manifest["company"]["fictional"] is not True or len(manifest["dossiers"]) != 3:
        raise ValueError("Expected three entirely fictional dossiers")
    shared = read_relative(base, manifest["shared_objects"])
    cases = [(case, read_relative(base, case["bootstrap"])) for case in manifest["dossiers"]]
    objects = shared + [obj for _, group in cases for obj in group]
    report = validate(objects)
    if not report["valid"] or report["unresolved_references"]:
        raise ValueError("Invalid fixture or references missing from the fixture")
    for obj in objects:
        if obj["meta"]["type"] == "air.Source":
            source = (ROOT / obj["body"]["locator"]).resolve()
            if not source.is_relative_to(base.resolve()):
                raise ValueError("Source is outside the fictional fixture")
            expected = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            if obj["body"]["source_revision"] != expected:
                raise ValueError("Source content changed; update its revision explicitly")
    return manifest, shared, cases


def check_fixture():
    manifest, shared, cases = load_fixture()
    temp_root = ROOT / "tmp"
    temp_root.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="air-asteria-", dir=temp_root) as scratch:
        store = Store(f"sqlite:///{(Path(scratch) / 'fixture.db').as_posix()}")
        try:
            store.migrate()
            for obj in shared:
                store.put(obj, "fictional-fixture-runner")
            for case, objects in cases:
                for obj in objects:
                    receipt = store.put(obj, "fictional-fixture-runner")
                    repeat = store.put(obj, "fictional-fixture-runner")
                    if repeat["created"] or receipt["digest"] != repeat["digest"]:
                        raise ValueError("Idempotent replay failed")
                    loaded = store.get(obj["meta"]["id"], obj["meta"]["revision"])
                    if loaded["digest"] != digest(obj):
                        raise ValueError("Stored digest changed")
                    for ref in references(obj):
                        if store.get(ref["id"], ref["revision"]) is None:
                            raise ValueError("Fixture reference not stored")
                results.append({"dossier": case["id"], "title": case["title"],
                                "bootstrap_check": "PASS", "business_acceptance": "NOT_EXECUTED",
                                "objects": len(objects), "shared_objects": len(shared)})
            total = store.counts()["revisions"]
            if total != len(shared) + sum(len(objects) for _, objects in cases):
                raise ValueError("Unexpected duplicate or missing revision")
        finally:
            store.engine.dispose()
    return {
        "company": manifest["company"], "check": "BOOTSTRAP_FIXTURE_ONLY",
        "status": "PASS", "stored_revisions": total, "results": results,
        "business_demo_ready": False,
        "readiness_basis": "Only the bootstrap fixture checks were executed by this command.",
        "business_checks": [{"id": item["id"], "execution": "NOT_EXECUTED", "criterion": item["criterion"]}
                            for item in manifest["milestone"]["requires"]],
        "normative_reference_resolution": "NOT_EXECUTED",
        "portfolio_oracle": "EXPECTED_RESULT_ONLY_NOT_ENGINE_OUTPUT",
        "live_instance_modified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-asteria/preflight.json")
    args = parser.parse_args()
    report = check_fixture()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"fixture_check": report["status"], "business_demo_ready": False,
                      "dossiers": len(report["results"]), "report": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
