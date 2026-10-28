"""Invoke the separately installed AIR CLI on an explicit local project.

No token is read by this helper. AIR consumes its protected credential file.
This is a workflow guard, not a sandbox for executing an untrusted checkout.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

COMMANDS = frozenset('artifact-import ci-ingest context-export effort-calibrate generation-read generation-record baseline-browse baseline-create baseline-export behavior-interfaces behavior-states bundle-put capabilities change-propose checklist-export completeness-assess completion-advance completion-apply completion-authorize completion-create completion-read completion-stop construction-validate deliverables delivery-dashboard diff drafts-rebase drafts-validate evidence-impact gate-validate get guide handoff-assess handoff-compile handoff-create handoff-read handoff-receive handoff-revoke impact interface-suite interface-verify openapi-compile portfolio-index prepared-deposit prepared-freeze presentation project-updates question-resume readiness revisions scenario-record scenario-simulate scenarios-walk scope-gates session-reconcile stakeholders-map traceability-coverage transformation-query type-describe videos-refresh view whoami'.split())


def fail(code, hint):
    print(json.dumps({'error': code, 'hint': hint}), file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--credential', default='credentials.json')
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    engine, home = args.engine.resolve(), args.home.resolve()
    python = engine / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not (engine / 'pyproject.toml').is_file() or not python.is_file():
        return fail('AIR_ENGINE_MISSING', 'Select the authorized AIR Engine checkout; follow its scripts/install.py and installation guide with Python 3.11+. The plugin does not install the engine.')
    if not 1 <= args.port <= 65535:
        return fail('AIR_PORT_INVALID', 'Use the port of this local AIR installation.')
    if Path(args.credential).name != args.credential or '/' in args.credential or '\\' in args.credential or not args.credential.endswith('.json'):
        return fail('AIR_CREDENTIAL_NAME_INVALID', 'Supply only a protected JSON credential filename inside this AIR home, never a token.')
    if not (home / 'config.json').is_file() or not (home / args.credential).is_file():
        return fail('AIR_CONFIGURATION_MISSING', 'Configure this explicit AIR home using the engine installation guide. Do not print or paste credentials.')
    tail = args.arguments
    if tail[:1] == ['--']: tail = tail[1:]
    permitted = {'--output', '--workspace', '--apply', '--replace-generated', '--render'}
    if any(a.startswith('-') and a.split('=', 1)[0] not in permitted for a in tail):
        return fail('AIR_OPTION_REFUSED', 'Use JSON request files and documented output/workspace options. Connection and identity must be supplied before the command.')
    cmd = [str(python), '-m', 'air', '--home', str(home), '--quiet', args.command]
    if args.command != 'capabilities':
        cmd += ['--url', 'http://127.0.0.1:' + str(args.port), '--credential', args.credential]
    try:
        return subprocess.run(cmd + tail, cwd=engine, timeout=600).returncode
    except subprocess.TimeoutExpired:
        return fail('AIR_TIMEOUT', 'Inspect the operation before retrying: a write may already have completed. Keep its idempotency key.')
    except OSError:
        return fail('AIR_EXECUTION_UNAVAILABLE', 'Use a supported local executor with access to the selected engine and project.')


if __name__ == '__main__':
    raise SystemExit(main())
