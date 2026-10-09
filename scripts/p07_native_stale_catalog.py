"""Native Codex calls after its discovered admission/activation mandate is revoked.

The temporary mandate exists only on the synthetic bench and is restored in finally.
No blanket client approval override is used. A race or missing call fails the recipe.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import tomllib

from air.config import protect_directory, write_private
from air.native_evidence import calls
from air.storage import Store
from p07_session_bench import bench_home, inspect, policy, state
from qualify_native_clients import invoke


def rows_in(folder):
    rows = []
    for path in folder.glob('*.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass  # A currently written line is not evidence yet.
    return rows


def run(root, output):
    root = root.resolve()
    bench = state(root)
    home, settings = bench_home(root, bench)
    if output.exists():
        raise ValueError('Choose a new evidence directory')
    protect_directory(output)
    original = json.loads((home/'access-policy.json').read_text(encoding='utf-8'))
    temporary = deepcopy(original)
    temporary['version'] += '-stale-catalog-discovery'
    subject = bench['clients']['codex']['subject']
    temporary['subjects'][subject].update(admit=['example.claims'], activate=['example.claims'])
    cfg = tomllib.loads((Path(bench['clients']['codex']['workspace'])/'.codex/config.toml').read_text(encoding='utf-8'))['mcp_servers']['air']
    missing = {'id': 'urn:p07:nonexistent:receipt', 'digest': 'sha256:'+'0'*64}
    steps = [{'tool': 'air_whoami', 'arguments': {}},
             {'tool': 'air_admission_admit', 'arguments': {'idempotency_key': 'native-stale-admit', 'proposal': missing, 'approvals': [missing]}},
             {'tool': 'air_admission_activate', 'arguments': {'idempotency_key': 'native-stale-activate', 'admission': missing,
              'unit': {**missing, 'revision': 1}}},
             {'tool': 'air_whoami', 'arguments': {}}]
    store = Store(settings.database_url)
    events = []
    try:
        before = inspect(store, bench)['counts']
        policy(root, temporary, 'codex-discovery-mandate')
        events.append({'event': 'temporary_mandate_for_discovery', 'at': time.time()})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(invoke, 'codex', output, {'command': cfg['command'], 'args': cfg['args']}, steps, 240)
            deadline = time.monotonic()+240
            while time.monotonic() < deadline and not future.done():
                observed = calls('codex', rows_in(output))
                if any(c['tool'] == 'air_whoami' for c in observed):
                    policy(root, original, 'codex-mandate-revoked')
                    events.append({'event': 'mandate_revoked_after_native_identity_call', 'at': time.time()})
                    break
                time.sleep(0.1)
            stage = future.result()
        observed = stage['calls']
        identities = [c['result'] for c in observed if c['tool'] == 'air_whoami']
        refused = {c['tool']: c['result'] for c in observed if c['tool'] in ('air_admission_admit', 'air_admission_activate')}
        after = inspect(store, bench)['counts']
        checks = {'all_native_calls_completed': stage['status'] == 'CALLS_COMPLETED',
                  'initial_mandate_observed': bool(identities and all(a in identities[0].get('actions', []) for a in ('admit', 'activate'))),
                  'operator_revocation_performed': len(events) == 2,
                  'native_admission_refused': refused.get('air_admission_admit', {}).get('http_status') == 403,
                  'native_activation_refused': refused.get('air_admission_activate', {}).get('http_status') == 403,
                  'final_mandate_absent': bool(len(identities) == 2 and not set(identities[-1].get('actions', [])).intersection({'admit', 'activate'})),
                  'no_commitments_created': before == after and not any(after.values())}
        report = {'format': 'air.native-stale-catalog/1', 'status': 'PASS_SCOPED' if all(checks.values()) else 'INCOMPLETE',
                  'client': 'codex', 'checks': checks, 'events': events, 'before': before, 'after': after,
                  'stage': {k: v for k, v in stage.items() if k != 'calls'},
                  'scope': 'Discovered tools remain in the native client catalogue after operator revocation; real server refusals, no old client binary compatibility claim.',
                  'mcp_sha256': hashlib.sha256((Path(__file__).resolve().parents[1]/'src/air/mcp.py').read_bytes()).hexdigest(),
                  'p07_received': False}
        write_private(output/'report.json', report)
        return {'status': report['status'], 'checks': checks}
    finally:
        try:
            policy(root, original, 'codex-original-restored')
        finally:
            store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.output.resolve())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS_SCOPED' else 2)
