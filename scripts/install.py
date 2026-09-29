#!/usr/bin/env python3
"""Install AIR using only Python's standard library. No Docker or Node required."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import tempfile
from urllib.request import build_opener, ProxyHandler
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from air.transport import ServerBinding


def health(port, binding=None):
    try:
        return (binding or ServerBinding.load(ROOT, {}, port)).health()
    except Exception:
        return None


def start(python, home, port, no_worker=False):
    config = json.loads((home / "config.json").read_text(encoding="utf-8"))
    instance = config["instance_id"]
    binding = ServerBinding.load(home, config.get("server", {}), port)
    binding.validate_tls()
    port = binding.port
    existing = health(port, binding)
    if existing:
        if existing.get("service") == "air" and existing.get("instance_id") == instance:
            (home / "server.json").write_text(json.dumps({"pid": existing["pid"], "port": port, "instance_id": instance, "transport": binding.probe_state()}), encoding="utf-8")
            print(f"AIR already running: {binding.origin}")
            return
        raise RuntimeError("Port belongs to another service; choose --port")
    with socket.socket(socket.AF_INET6 if ":" in binding.host else socket.AF_INET) as probe:
        probe.bind((binding.host, port))
    kwargs = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # AIR owns bounded, content-free event logs. Never capture raw library stderr indefinitely.
    proc = subprocess.Popen([str(python), "-m", "air", "--home", str(home), "serve", "--port", str(port)] + (["--no-worker"] if no_worker else []),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError("Server exited; run doctor and inspect the private server-events.jsonl")
        value = health(port, binding)
        if value and value.get("instance_id") == instance and isinstance(value.get("pid"), int):
            # Windows venv launchers can have a different PID from the Python server.
            (home / "server.json").write_text(json.dumps({"pid": value["pid"], "port": port, "instance_id": instance, "transport": binding.probe_state()}), encoding="utf-8")
            print(f"AIR ready: {binding.origin} (PID {value['pid']})")
            return
        time.sleep(0.1)
    # Only the process tree created by this start attempt. On Windows the venv
    # launcher and Python server can have distinct PIDs.
    if os.name == "nt" and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=True, capture_output=True)
    elif proc.poll() is None:
        proc.terminate()
    proc.wait(timeout=10)
    raise RuntimeError("AIR did not become healthy")


def stop(home):
    state = json.loads((home / "server.json").read_text(encoding="utf-8"))
    binding = ServerBinding.from_probe_state(state["transport"]) if "transport" in state else ServerBinding.load(home, {}, state["port"])
    current = health(state["port"], binding)
    if not current or current.get("pid") != state["pid"] or current.get("instance_id") != state["instance_id"]:
        raise RuntimeError("Cannot verify the process identity; no process was stopped")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(state["pid"]), "/F"], check=True, capture_output=True)
    else:
        os.kill(state["pid"], signal.SIGTERM)
    for _ in range(50):
        if health(state["port"], binding) is None:
            (home / "server.json").unlink(missing_ok=True)
            print("AIR stopped")
            return
        time.sleep(0.1)
    raise RuntimeError("Stop requested; process shutdown not confirmed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=ROOT / ".air")
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    parser.add_argument("--port", type=int, help="Local port, or the port declared in the HTTPS origin")
    parser.add_argument("--extras", help="Comma-separated optional extras: postgres, oidc, proofs, backup, dev")
    parser.add_argument("--work-root", type=Path, default=Path(os.environ.get('AIR_WORK_ROOT', ROOT / 'tmp')))
    parser.add_argument("--wheel", type=Path, help="Install a verified AIR wheel instead of the editable source")
    parser.add_argument("--wheelhouse", type=Path, help="Install offline, exclusively from this local directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--start", action="store_true")
    mode.add_argument("--stop", action="store_true")
    parser.add_argument("--no-worker", action="store_true", help="Start without the embedded calculation worker")
    parser.add_argument("--skip-install", action="store_true", help="Use an already installed environment")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required")
    if args.port is not None and not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    if args.extras and (not set(args.extras.split(',')) <= {'postgres', 'oidc', 'proofs', 'backup', 'dev'}):
        parser.error('Unknown optional extra')
    home = args.home.absolute()
    if args.stop:
        stop(home)
        return
    environment = args.venv.resolve()
    scratch = args.work_root.resolve() / "install"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(scratch)
    tempfile.tempdir = str(scratch)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        if args.skip_install:
            raise RuntimeError("No installed environment")
        venv.EnvBuilder(with_pip=True).create(environment)
    if not args.skip_install:
        package = str(args.wheel.resolve() if args.wheel else ROOT) + (f"[{args.extras}]" if args.extras else "")
        command = [str(python), "-m", "pip", "install", "--no-cache-dir", "--disable-pip-version-check", "-c", str(ROOT / "constraints.txt")]
        if args.wheelhouse:
            if not args.wheel: raise ValueError('Offline installation requires a prebuilt AIR wheel')
            command += ['--no-index', '--find-links', str(args.wheelhouse.resolve())]
        command += ([] if args.wheel else ['-e']) + [package]
        # Standard PIP_INDEX_URL / PIP_NO_INDEX / PIP_FIND_LINKS work with company mirrors.
        # Avoid echoing package-manager output which may include a credentialed mirror URL.
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Dependency installation failed; verify network/mirror, Python version and constraints")
    installed_version = subprocess.check_output([str(python), '-c', 'import air; print(air.__version__)'], cwd=environment, text=True).strip()
    import tomllib
    if installed_version != tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']:
        raise RuntimeError('Installed AIR version differs from the installation source')
    base = [str(python), "-m", "air", "--home", str(home)]
    subprocess.run(base + ["bootstrap"], check=True, cwd=ROOT)
    subprocess.run(base + ["doctor"], check=True, cwd=ROOT)
    subprocess.run([str(python), "-m", "air", "validate", str(ROOT / "examples/scope.json")], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    if args.start:
        start(python, home, args.port, args.no_worker)
    else:
        print("Installation verified. Add --start to launch AIR.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"AIR installation failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
