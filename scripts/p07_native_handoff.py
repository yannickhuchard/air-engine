"""Have Codex persist a synthetic design for a fresh Claude session to resume.

Uses only the isolated attended-session bench. This is a native invocation test,
not a claim of automatic project discovery or complete P07 reception.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib
import uuid
from datetime import datetime, timezone

from air.config import protect_directory, write_private
from air.collaboration import identity_context, identity_uri
from air.core import digest
from air.foundation import exact, resolved
from air.storage import Store
from p07_session_bench import bench_home, state
from qualify_native_clients import invoke

ROOT = Path(__file__).resolve().parents[1]


def run(root, output):
    root = root.resolve()
    bench = state(root)
    _, settings = bench_home(root, bench)
    if output.exists():
        raise ValueError('Choose a new evidence directory')
    protect_directory(output)
    cfg = tomllib.loads((Path(bench['clients']['codex']['workspace']) / '.codex/config.toml').read_text(encoding='utf-8'))['mcp_servers']['air']
    store = Store(settings.database_url)
    try:
        previous = store.get('urn:p07:session:change:claims-notification', 1)
        # Resolve the candidate from the persisted proposal record, using the same deterministic identifier.
        baseline = store.get('urn:air:baseline:proposal:' + previous['digest'].split(':', 1)[1], 1)['object']
        scope = store.get('urn:air:example:scope:claims', 2)['object']
        label = uuid.uuid4().hex
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        author = identity_uri(identity_context({'subject': bench['clients']['codex']['subject']}, settings))
        variant = deepcopy(scope)
        variant['meta'].update(revision=store.latest_revisions([scope['meta']['id']])[scope['meta']['id']]+1, recorded_at=stamp)
        variant['meta']['description'] = 'P07 Codex handoff: notification design reviewed for implementation planning, no execution or approval.'
        meta = deepcopy(previous['object']['meta'])
        meta.update(id='urn:p07:codex:handoff:change:'+label, revision=1, recorded_at=stamp,
                    description='Synthetic proposal deposited through Codex native MCP tools for Claude resumption.')
        for m in (meta, variant['meta']):
            m['provenance'].update(recorded_by=author, method='Native Codex MCP handoff fixture; no human approval')
            m['validity'] = {'start': stamp, 'end': None}
        change = {'meta': meta, 'body': {'base': exact(baseline),
                  'operations': [{'op': 'REPLACE', 'before': resolved(scope), 'after': resolved(variant)}],
                  'rationale': 'Synthetic Codex-authored design for independent client resumption.',
                  'expected_revisions': baseline['body']['members'], 'approvals': []}}
        steps = [{'tool': 'air_whoami', 'arguments': {}},
                 {'tool': 'air_get', 'arguments': exact(scope)},
                 {'tool': 'air_import_drafts', 'arguments': {'objects': [variant]}},
                 {'tool': 'air_propose_change', 'arguments': change},
                 {'tool': 'air_propose_change', 'arguments': change}]
        stage = invoke('codex', output, {'command': cfg['command'], 'args': cfg['args']}, steps, timeout=240)
        def result(name):
            return next((c['result'] for c in reversed(stage['calls']) if c['tool'] == name), {})
        proposed = result('air_propose_change')
        persisted = store.get(meta['id'], 1)
        checks = {'native_calls_completed': stage['status'] == 'CALLS_COMPLETED',
                  'codex_identity': result('air_whoami').get('subject') == bench['clients']['codex']['subject'],
                  'declared_provenance_matches_identity': result('air_whoami').get('identity') == author,
                  'base_digest_read': result('air_get').get('digest') == digest(scope),
                  'change_persisted': bool(persisted and persisted['digest'] == digest(change)),
                  'not_approved': proposed.get('approved') is False and proposed.get('published') is False,
                  'idempotent': proposed.get('change', {}).get('created') is False,
                  'closed_candidate': proposed.get('target', {}).get('validation', {}).get('valid') is True}
        target = proposed.get('target', {})
        report = {'format': 'air.native-handoff/1', 'direction': 'codex -> claude-code',
                  'status': 'PRODUCER_VERIFIED' if all(checks.values()) else 'INCOMPLETE',
                  'checks': checks, 'consumer_executed': False,
                  'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'mcp_sha256': hashlib.sha256((ROOT/'src/air/mcp.py').read_bytes()).hexdigest(),
                  'stage': {k: v for k, v in stage.items() if k != 'calls'},
                  'references': {'change': {**exact(change), 'digest': digest(change)},
                                 'candidate': {'id': target.get('id'), 'revision': 1, 'digest': target.get('digest')}},
                  'automatic_project_discovery_tested': False, 'p07_received': False}
        write_private(output/'report.json', report)
        return {'status': report['status'], 'checks': checks, 'references': report['references']}
    finally:
        store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PRODUCER_VERIFIED' else 2)
