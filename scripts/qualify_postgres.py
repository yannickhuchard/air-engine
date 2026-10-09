"""Run AIR tests against a newly created, isolated local PostgreSQL cluster.
The supplied binaries are used only for this qualification, never the default install.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import re
import socket
import subprocess
import sys
import uuid
from air.config import protect_directory

ROOT = Path(__file__).resolve().parents[1]


def stop_cluster(command, data, timeout):
    """A test PASS is distinct from a verified shutdown; never signal unrelated processes."""
    result = {'status': 'UNKNOWN', 'timeout_seconds': timeout, 'stop_timed_out': False}
    try:
        command('pg_ctl', ['-D', str(data), '-w', '-t', str(timeout), '-m', 'fast', 'stop'], timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        result['stop_timed_out'] = True
    except RuntimeError:
        result['stop_command_failed'] = True
    try:
        status = command('pg_ctl', ['-D', str(data), 'status'], accepted=(0, 3))
        result['status_exit_code'] = status['returncode']
        result['status'] = 'STOPPED_VERIFIED' if status['returncode'] == 3 else 'STILL_RUNNING'
    except (RuntimeError, subprocess.TimeoutExpired):
        result['status'] = 'STATUS_CHECK_FAILED'
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument('--work-root', type=Path, default=ROOT, help='Directory receiving the uniquely named disposable cluster and pytest data')
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/postgresql-qualification.json")
    parser.add_argument("--test-file", type=Path, action="append", help="Optional test file within this repository tests directory")
    parser.add_argument('--stop-timeout', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.stop_timeout <= 3600: parser.error('stop-timeout must be 1..3600 seconds')
    selection = []
    for candidate in args.test_file or []:
        selected = (ROOT / candidate).resolve()
        if not selected.is_relative_to((ROOT / "tests").resolve()) or not selected.is_file() or not selected.name.startswith("test_") or selected.suffix != ".py":
            raise ValueError("Test selection must name a repository test file")
        selection.append(selected.relative_to(ROOT).as_posix())
    binaries = args.bin.resolve()
    suffix = ".exe" if os.name == "nt" else ""
    for tool in ("initdb", "pg_ctl", "postgres"):
        if not (binaries / (tool + suffix)).is_file(): raise ValueError("PostgreSQL binary is missing: " + tool)
    home = args.work_root.resolve() / (".air-pg-qualification-" + uuid.uuid4().hex)
    protect_directory(home)
    password = secrets.token_urlsafe(32)
    password_file = home / "bootstrap-password"
    with password_file.open("x", encoding="utf-8") as stream:
        if os.name != "nt": os.fchmod(stream.fileno(), 0o600)
        stream.write(password + "\n")
    creation = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    def command(tool, argv, timeout=60, accepted=(0,)):
        # Cleanup must remain executable even when the qualification disk cannot accept logs.
        if tool == 'pg_ctl' and argv[-1] in ('stop', 'status'):
            result = subprocess.run([str(binaries / (tool + suffix)), *argv], capture_output=True,
                text=True, timeout=timeout, **creation)
            if result.returncode not in accepted: raise RuntimeError('PostgreSQL control command failed')
            return {'returncode': result.returncode, 'output': result.stdout + result.stderr}
        # A daemon may inherit a pipe even after pg_ctl exits on Windows.
        # File-backed logs allow waiting only for the control process.
        log_file = home / (tool + "-" + uuid.uuid4().hex + ".log")
        (home / "progress.json").write_text(json.dumps({"phase": tool, "state": "STARTED"}), encoding="utf-8")
        with log_file.open("wb") as log:
            result = subprocess.run([str(binaries / (tool + suffix)), *argv],
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout, **creation)
        if result.returncode not in accepted:
            raise RuntimeError(tool + " failed; diagnostic retained privately in " + str(home))
        (home / "progress.json").write_text(json.dumps({"phase": tool, "state": "COMPLETED"}), encoding="utf-8")
        return {"returncode": result.returncode, "output": log_file.read_text(encoding="utf-8", errors="replace")}
    version = command("postgres", ["--version"])["output"].strip()
    data = home / "data"
    command("initdb", ["-D", str(data), "--username=air_test_admin", "--auth=scram-sha-256", "--pwfile=" + str(password_file), "--encoding=UTF8", "--locale=C"])
    password_file.unlink()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0));port = probe.getsockname()[1]
    started = False
    report = {'status': 'FAIL', 'test_status': 'NOT_EXECUTED', 'server': version,
        'isolated_local_cluster': True, 'default_sqlite_unchanged': True, 'test_selection': selection or ['all']}
    safe_log = ''
    try:
        started = True
        command("pg_ctl", ["-D", str(data), "-l", str(home / "server.log"), "-o", "-h 127.0.0.1 -p " + str(port) + " -c max_connections=32 -c shared_buffers=64MB", "-w", "start"])
        started = True
        import psycopg
        from sqlalchemy import URL
        database = "air_test_" + uuid.uuid4().hex
        with psycopg.connect(host="127.0.0.1", port=port, user="air_test_admin", password=password, dbname="postgres", autocommit=True, connect_timeout=10) as conn:
            conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(database)))
        url = URL.create("postgresql+psycopg", username="air_test_admin", password=password, host="127.0.0.1", port=port, database=database).render_as_string(hide_password=False)
        env = dict(os.environ)
        env.pop("AIR_DATABASE_URL", None)
        env["AIR_TEST_DATABASE_URL"] = url
        env["AIR_TEST_ALLOW_RESET"] = "yes"
        scratch = home / "runtime"
        scratch.mkdir(parents=True, exist_ok=True)
        env["TEMP"] = env["TMP"] = str(scratch)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        junit = home / "junit.xml"
        (home / "progress.json").write_text(json.dumps({"phase": "pytest", "state": "STARTED"}), encoding="utf-8")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--basetemp=" + str(home / 'pytest'), "--junitxml=" + str(junit), *selection],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400, **creation)
        safe_log = (result.stdout + result.stderr).replace(url, "[REDACTED_DATABASE_URL]").replace(password, "[REDACTED_PASSWORD]")
        safe_log = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", safe_log)
        safe_log = re.sub(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])", "[REDACTED_TOKEN]", safe_log)
        (home / "pytest.log").write_text(safe_log, encoding="utf-8")
        import xml.etree.ElementTree as ET
        suite = ET.parse(junit).getroot().find("testsuite")
        counts = {k: int(suite.attrib[k]) for k in ("tests", "failures", "errors", "skipped")}
        report.update(test_status='PASS' if result.returncode == 0 else 'FAIL',
            tests=counts, junit_private=str(junit), log_private=str(home / 'pytest.log'),
            junit_sha256=hashlib.sha256(junit.read_bytes()).hexdigest())
    except Exception as exc:
        report['execution_error'] = type(exc).__name__
    finally:
        report['cleanup'] = stop_cluster(command, data, args.stop_timeout) if started else {'status': 'NOT_STARTED'}
        report['status'] = 'PASS' if report['test_status'] == 'PASS' and report['cleanup']['status'] == 'STOPPED_VERIFIED' else 'FAIL'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    if safe_log: print(safe_log)
    return 0 if report['status'] == 'PASS' else 1



if __name__ == "__main__":
    raise SystemExit(main())
