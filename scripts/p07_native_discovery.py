"""Read-only Codex probe using generated project configuration and existing trust.

No MCP or trust override is supplied and no global configuration is modified.
If the native client refuses the project, retain that failure as evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib

from air.config import protect_directory, write_private
from air.native_evidence import calls
from p07_session_bench import bench_home, state
from p07_codex_config import diagnose


def run(root, output):
    bench = state(root)
    bench_home(root, bench)
    if output.exists():
        raise ValueError('Choose a new evidence directory')
    protect_directory(output)
    workspace = Path(bench['clients']['codex']['workspace'])
    user_config = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'config.toml'
    config = tomllib.loads(user_config.read_text(encoding='utf-8')) if user_config.exists() else {}
    if 'air' in config.get('mcp_servers', {}):
        raise ValueError('Global AIR server would make project discovery ambiguous')
    executable = shutil.which('codex')
    if not executable:
        raise ValueError('Codex not installed')
    version = subprocess.check_output([executable, '--version'], text=True).strip()
    diagnostic = diagnose(executable, workspace)
    if diagnostic['status'] != 'PROJECT_CONFIG_LOADED':
        report = {'format': 'air.native-project-discovery/1', 'client': 'codex', 'client_version': version,
                  'status': 'INCOMPLETE', 'config_diagnostic': diagnostic, 'native_session_started': False,
                  'invocation_supplied_mcp': False, 'trust_modified': False, 'p07_received': False}
        write_private(output/'report.json', report)
        return {'status': report['status'], 'config_diagnostic': diagnostic}
    prompt = ('Read-only AIR project discovery acceptance test. Use only tools from the local MCP server named air '
              'discovered from this project. The codex_apps AIR connector is a different remote registry and must not be used. '
              'Discover deferred tools using the native tool search or tool metadata enumeration if needed; '
              'do not conclude that a tool is absent merely because it is not in the initial visible list. '
              'Call air_whoami with {}, then air_capabilities with {}. Do not use shell, files, other connectors or subagents. '
              'Do not edit configuration or trust. If AIR tools are absent, state that; do not simulate calls.')
    stream, errors = output/'native.jsonl', output/'native.stderr'
    env = dict(os.environ, PYTHONUTF8='1')
    env.pop('PYTHONPATH', None)
    env.pop('AIR_DATABASE_URL', None)
    timed_out = False
    exit_code = None
    with stream.open('w', encoding='utf-8') as stdout, errors.open('w', encoding='utf-8') as stderr:
        try:
            process = subprocess.run([executable, 'exec', '--ephemeral', '--json', '--sandbox', 'read-only', '-'],
                                 cwd=workspace, env=env, input=prompt, text=True, encoding='utf-8',
                                 stdout=stdout, stderr=stderr, timeout=240)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    rows = []
    for line in stream.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    observed = calls('codex', rows)
    who = next((c['result'] for c in observed if c['tool'] == 'air_whoami'), {})
    caps = next((c['result'] for c in observed if c['tool'] == 'air_capabilities'), {})
    checks = {'native_exit_zero': exit_code == 0 and not timed_out,
              'project_identity': who.get('subject') == bench['clients']['codex']['subject'],
              'engine_version_matches': caps.get('engine_version') == bench['air_version'],
              'only_expected_calls': [c['tool'] for c in observed] == ['air_whoami', 'air_capabilities']}
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    report = {'format': 'air.native-project-discovery/1', 'client': 'codex', 'client_version': version,
              'config_diagnostic': diagnostic, 'native_session_started': True,
              'status': 'PASS_SCOPED' if all(checks.values()) else 'INCOMPLETE', 'checks': checks,
              'exit_code': exit_code, 'timed_out': timed_out,
              'transcript_sha256': sha(stream), 'stderr_sha256': sha(errors),
              'project_config_sha256': sha(workspace/'.codex/config.toml'),
              'invocation_supplied_mcp': False, 'trust_modified': False, 'p07_received': False}
    write_private(output/'report.json', report)
    return {'status': report['status'], 'checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS_SCOPED' else 2)
