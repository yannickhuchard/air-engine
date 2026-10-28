"""Bounded synthetic portfolio storage/recovery exercise with targets fixed before measurement."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from air import __version__
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings
from air.core import FOUNDATION_PROFILE, record
from air.foundation import check_schema, exact
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
TARGETS = record({'format': {'const': 'air.portfolio-scale-targets/1'}, 'synthetic': {'const': True},
    'projects': {'type': 'integer', 'minimum': 1, 'maximum': 64},
    'revisions_per_project': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
    'concurrency': {'type': 'integer', 'minimum': 1, 'maximum': 8},
    'description_bytes': {'type': 'integer', 'minimum': 1, 'maximum': 9000},
    'put_p95_seconds': {'type': 'number', 'exclusiveMinimum': 0},
    'read_p95_seconds': {'type': 'number', 'exclusiveMinimum': 0},
    'restore_seconds': {'type': 'number', 'exclusiveMinimum': 0}})


def p95(values): return sorted(values)[max(0, math.ceil(len(values) * .95) - 1)]


def qualify(target_path, output):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Use an isolated SQLite environment')
    raw = Path(target_path).read_bytes(); targets = json.loads(raw); check_schema(targets, TARGETS)
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    # Persist the exact targets before starting the timed workload.
    (output / 'targets.json').write_bytes(raw)
    home = output / '.air'; bootstrap(home); store = Store(Settings.load(home).database_url)
    example = json.loads((ROOT / 'examples/scope.json').read_text(encoding='utf-8'))
    shared = deepcopy(example); shared['meta'].update(id='urn:scale:shared', namespace='scale.shared')
    store.put(shared, 'synthetic-scale-operator')
    def project(number):
        durations = []
        for revision in range(1, targets['revisions_per_project'] + 1):
            obj = deepcopy(example); obj['meta'].update(id='urn:scale:project:' + str(number),
                namespace='scale.p' + str(number), revision=revision, description='x' * targets['description_bytes'])
            obj['body']['includes'] = [exact(shared)]
            begin = time.perf_counter(); store.put(obj, 'synthetic-scale-operator'); durations.append(time.perf_counter() - begin)
        meta = deepcopy(obj['meta']); meta.update(id=obj['meta']['id'] + ':baseline', revision=1, type='air.Baseline')
        result = store.create_baseline({'meta': meta, 'profile': FOUNDATION_PROFILE,
            'members': [exact(shared), exact(obj)], 'parent_baselines': []}, 'synthetic-scale-operator')
        begin = time.perf_counter(); exported = store.export_baseline(exact(result['baseline'])); read_seconds = time.perf_counter() - begin
        if exported['digest'] != result['digest']: raise ValueError('Baseline integrity mismatch')
        return durations, read_seconds, exact(result['baseline']), result['digest']
    try:
        begin = time.perf_counter()
        with ThreadPoolExecutor(max_workers=targets['concurrency']) as pool:
            results = list(pool.map(project, range(targets['projects'])))
        elapsed = time.perf_counter() - begin
        counts = store.counts(); store.engine.dispose()
        snapshot(home, output / 'backup')
        begin = time.perf_counter(); restore(output / 'backup', output / 'restored'); recovery_seconds = time.perf_counter() - begin
        restored = Store(Settings.load(output / 'restored').database_url)
        try: equal = all(restored.export_baseline(ref)['digest'] == checksum for _, _, ref, checksum in results)
        finally: restored.engine.dispose()
        put = p95([d for row in results for d in row[0]]); read = p95([r[1] for r in results])
        checks = {'put_p95_within_target': put <= targets['put_p95_seconds'],
            'read_p95_within_target': read <= targets['read_p95_seconds'],
            'restore_within_target': recovery_seconds <= targets['restore_seconds'], 'restored_digests_equal': equal}
        report = {'format': 'air.portfolio-scale-reception/1', 'status': 'PASS_SCOPED' if all(checks.values()) else 'FAIL',
            'engine_version': __version__, 'python': platform.python_version(), 'platform': platform.platform(),
            'targets_sha256': hashlib.sha256(raw).hexdigest(), 'targets': targets, 'checks': checks,
            'stored_counts': counts, 'projects': targets['projects'], 'requested_scope_revisions': targets['projects'] * targets['revisions_per_project'],
            'put_p95_seconds': put, 'read_p95_seconds': read, 'restore_seconds': recovery_seconds, 'workload_seconds': elapsed,
            'storage_kernel_measured': True, 'http_latency_measured': False, 'synthetic': True,
            'enterprise_workload_representativeness_verified': False, 'enterprise_capacity_received': False,
            'independent_restore_received': False, 'ci_executed': False,
            'limitations': ['Foundation scopes and shared dependencies; no full construction workload or distributed writes',
                'Results apply to this machine and current background load only', 'Synthetic thresholds are not enterprise service objectives']}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    finally: store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('targets', type=Path); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); report = qualify(args.targets, args.output)
    print(json.dumps({k: report[k] for k in ('status', 'projects', 'requested_scope_revisions', 'put_p95_seconds', 'read_p95_seconds', 'restore_seconds')}))
    raise SystemExit(0 if report['status'] == 'PASS_SCOPED' else 1)
