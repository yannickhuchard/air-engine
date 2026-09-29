"""Receive the pinned public rc9 in a NEW workspace; never attest a second device."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from urllib.request import urlopen

from qualify_release import qualify

BASE = 'https://github.com/yannickhuchard/air-engine/releases/download/v0.34.0rc9/'
PINS = {
    'release-set.json': '5bb8a9f1ff8afc4f6269fc1ab67fe3ae4d3bd1c28de076dc55250082e17a3c63',
    'air-0.34.0rc9-source.zip': '5fb7dfbb3dc5b10c021440c038c44155da6ad7c93f03dcd93f4fdfd731f34d03',
    'air_engine-0.34.0rc9-py3-none-any.whl': '37f423799d0f019d6167efc1f386a72cec284a294c88539376e9571f59fa1ab0',
    'constraints.cdx.json': 'fc7e7a4ce22b21d9e73477466bb8a575da4779fcaa29b7d8051883d14edae735',
}
EXPECTED = {'D01': 'UNKNOWN', 'D02': 'VIOLATED', 'D03': 'CONFLICTING'}


def download(folder):
    for name, expected in PINS.items():
        with urlopen(BASE + name, timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Public artifact checksum mismatch: ' + name)
        with (folder / name).open('xb') as stream:
            stream.write(data)


def summarize(installation, demo):
    required = ('fresh_environment', 'installed_from_wheel', 'offline_installation',
                'reinstallation_preserves_identity_and_revision',
                'recovery_preserves_digest_and_revokes_old_identity', 'server_stopped')
    if installation.get('status') != 'PASS_SCOPED' or any(installation.get(k) is not True for k in required):
        raise ValueError('Incomplete installation evidence')
    if installation.get('archive_sha256') != PINS['air-0.34.0rc9-source.zip'] or installation.get('wheel_sha256') != PINS['air_engine-0.34.0rc9-py3-none-any.whl']:
        raise ValueError('Wrong release evidence')
    if demo.get('version') != '0.34.0rc9' or demo.get('status') != 'PASS_SCOPED':
        raise ValueError('Wrong demonstration evidence')
    if any(demo.get(k) is not True for k in ('http_executed', 'mcp_executed', 'cross_dossier_read_refused')) or demo.get('business_scenarios_executed') is not False:
        raise ValueError('Incomplete demonstration evidence')
    dossiers = demo['dossiers']
    if len(dossiers) != 3 or {d['dossier'] for d in dossiers} != set(EXPECTED):
        raise ValueError('Three distinct dossiers required')
    rows = []
    for dossier in dossiers:
        gate = dossier['exception_gate']
        executed = [r['result'] for r in gate['results'] if r['execution'] == 'EXECUTED']
        cases = dossier['assessment']['verification_cases']
        if dossier['status'] != 'PASS' or gate['gate_decision'] != 'BLOCKED' or EXPECTED[dossier['dossier']] not in executed:
            raise ValueError('Unexpected dossier outcome')
        if len(cases) != 3 or any(c['execution'] != 'NOT_EXECUTED' for c in cases):
            raise ValueError('Future business tests must stay unexecuted')
        rows.append({'dossier': dossier['dossier'], 'computed_results': executed,
                     'gate': gate['gate_decision'], 'business_tests_not_executed': len(cases)})
    return {'schema': 'air.public-reception/1', 'status': 'PASS_SCOPED',
            'date': datetime.now(timezone.utc).isoformat(), 'version': '0.34.0rc9',
            'platform': platform.system(), 'python': platform.python_version(),
            'artifacts': PINS, 'installation': {k: installation[k] for k in required},
            'dossiers': rows, 'http_executed': True, 'mcp_executed': True,
            'second_physical_device': 'NOT_ATTESTED', 'native_agent_acceptance': 'NOT_EXECUTED',
            'public_chatgpt_acceptance': 'NOT_EXECUTED', 'full_air_conformance': False,
            'ci_executed': False}


def receive(output):
    if sys.flags.optimize:
        raise ValueError('Run without -O; acceptance assertions must remain enabled')
    if any(os.environ.get(k) for k in ('AIR_DATABASE_URL', 'AIR_HOME', 'AIR_WORK_ROOT', 'PYTHONPATH', 'PYTHONOPTIMIZE')):
        raise ValueError('Use a clean shell without AIR or Python path/optimization overrides')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    release = output / 'release'; release.mkdir()
    print('Downloading and verifying public rc9 artifacts', flush=True)
    download(release)
    print('Checking fresh/offline installation, reinstall and recovery', flush=True)
    installation = qualify(release, output / 'private')
    workspace = Path(installation['installed_sbom']).parent
    (workspace / 'installation.json').write_text(json.dumps(installation, indent=2) + '\n', encoding='utf-8')
    python = workspace / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    demo_output = workspace / 'asteria'
    print('Running the three synthetic Asteria dossiers through HTTP and MCP', flush=True)
    with (workspace / 'demonstration.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([str(python), str(workspace / 'source/scripts/demo_metier.py'),
                                 '--output', str(demo_output)], cwd=workspace,
                                stdout=log, stderr=subprocess.STDOUT, timeout=600,
                                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONOPTIMIZE': '0'})
    if result.returncode:
        raise RuntimeError('Asteria failed; diagnostics retained in private workspace')
    demo = json.loads((demo_output / 'report.json').read_text(encoding='utf-8'))
    receipt = summarize(installation, demo)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    (output / 'owner-review.json').write_text(json.dumps({
        'status': 'NOT_COMPLETED', 'second_physical_device': 'NOT_ATTESTED',
        'receipt_sha256': hashlib.sha256((output / 'receipt.json').read_bytes()).hexdigest(),
        'operator_alias': None, 'device_alias': None, 'agent_client_and_version': None,
        'installation_without_developer_assistance': None, 'three_views_reviewed': None,
        'limitations_understood': None, 'observations': []}, indent=2) + '\n', encoding='utf-8')
    print('PASS_SCOPED: receipt.json saved; second-device and native-agent reception NOT attested', flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never an existing AIR home')
    args = parser.parse_args()
    try:
        receive(args.output)
    except Exception as error:
        print('Reception FAILED (' + type(error).__name__ + '); no acceptance claimed. Keep local diagnostics private.', file=sys.stderr)
        sys.exit(1)
