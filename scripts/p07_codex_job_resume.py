"""Submit a fresh job natively after cancellation, run the isolated worker, reread both."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import uuid

from air.config import protect_directory, write_private
from air.mcp import APIClient
from p07_session_bench import bench_home, state
from qualify_native_clients import invoke


def run(root, output, cancelled_file):
    bench = state(root); home, _ = bench_home(root, bench)
    if Path(cancelled_file).name != cancelled_file or (root/cancelled_file).is_symlink():
        raise ValueError('Cancelled-job receipt must be directly inside the isolated bench')
    old = json.loads((root/cancelled_file).read_text(encoding='utf-8'))['job']
    client = bench['clients']['codex']
    if APIClient(home, client['credential'], bench['port'])('air_get_job', {'job': old}).get('status') != 'CANCELLED':
        raise ValueError('Previous job must be cancelled')
    if output.exists(): raise ValueError('Choose a new receipt directory')
    protect_directory(output)
    config = tomllib.loads((Path(client['workspace'])/'.codex/config.toml').read_text(encoding='utf-8'))['mcp_servers']['air']
    server = {'command': config['command'], 'args': config['args']}
    arguments = {'idempotency_key': 'native-resume-'+uuid.uuid4().hex, 'operation': 'plan', 'arguments': bench['planning_arguments']}
    step = {'tool': 'air_submit_job', 'arguments': arguments}
    submitted = invoke('codex', output, server, [step, step], timeout=240)
    write_private(output/'submit.json', {k: v for k, v in submitted.items() if k != 'calls'})
    if submitted['status'] != 'CALLS_COMPLETED': raise RuntimeError(submitted['status'])
    job = submitted['calls'][0]['result']['job']
    # A subprocess with a real __main__ is required by Windows multiprocessing.
    worker_codes = []
    for _ in range(6):
        worker = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'worker-once'],
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        worker_codes.append(worker.returncode)
        if worker.returncode: raise RuntimeError('Isolated worker failed; inspect private bench')
        if not json.loads(worker.stdout).get('processed'): break
    read = invoke('codex', output, server, [{'tool': 'air_get_job', 'arguments': {'job': old}},
                                          {'tool': 'air_get_job', 'arguments': {'job': job}}], timeout=180)
    observed = read['calls']
    checks = {'native_submit': submitted['status'] == 'CALLS_COMPLETED',
              'distinct_job': job != old,
              'idempotent_native_resubmit': submitted['calls'][1]['result'].get('job') == job and submitted['calls'][1]['result'].get('created') is False,
              'native_final_reads': read['status'] == 'CALLS_COMPLETED',
              'old_remains_cancelled': len(observed) == 2 and observed[0]['result'].get('status') == 'CANCELLED',
              'new_calculation_succeeded': len(observed) == 2 and observed[1]['result'].get('status') == 'SUCCEEDED'}
    report = {'format': 'air.native-codex-job-resume/1', 'status': 'PASS_SCOPED' if all(checks.values()) else 'INCOMPLETE',
              'checks': checks, 'submit_transcript_sha256': submitted['transcript_sha256'],
              'read_transcript_sha256': read['transcript_sha256'], 'worker_exit_codes': worker_codes,
              'worker_actor': 'operator', 'p07_received': False}
    write_private(output/'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cancelled-file', required=True)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output.resolve(), args.cancelled_file)
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS_SCOPED' else 2)
