"""Produce a sourced design through Codex for a native ChatGPT resumption."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from air.config import protect_directory, write_private
from air.core import FOUNDATION_PROFILE, digest
from air.foundation import exact, resolved
from air.mcp import APIClient
from air.storage import Store
from p07_session_bench import bench_home, state
from qualify_native_clients import invoke


def run(root, output):
    bench = state(root); home, settings = bench_home(root, bench)
    if output.exists(): raise ValueError('Choose a new receipt directory')
    protect_directory(output)
    client = bench['clients']['codex']
    store = Store(settings.database_url)
    try:
        scope = store.get('urn:air:example:scope:claims', 1)['object']
        source = {k: bench['fixtures']['source'][k] for k in ('id', 'revision')}
        label = uuid.uuid4().hex
        meta = deepcopy(scope['meta']); meta.update(id='urn:p07:pair:base:'+label, type='air.Baseline')
        base = store.create_baseline({'meta': meta, 'profile': FOUNDATION_PROFILE,
            'members': [exact(scope), source], 'parent_baselines': []}, 'synthetic-fixture')['baseline']
        author = APIClient(home, client['credential'], bench['port'])('air_whoami', {})['identity']
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        variant = deepcopy(scope)
        variant['meta'].update(revision=2, recorded_at=stamp, description='Synthetic Claims design adds notification planning; implementation is a later phase.')
        variant['meta']['provenance'].update(recorded_by=author, source_refs=[source], method='Native Codex recipe; synthetic company source cited')
        change_meta = deepcopy(variant['meta']); change_meta.update(id='urn:p07:pair:change:'+label, type='air.ChangeSet', revision=1)
        change = {'meta': change_meta, 'body': {'base': exact(base),
            'operations': [{'op': 'REPLACE', 'before': resolved(scope), 'after': resolved(variant)}],
            'rationale': 'Source-backed synthetic variant for cross-client resumption, without approval or execution.',
            'expected_revisions': base['body']['members'], 'approvals': []}}
        invalid = deepcopy(scope); invalid['body']['includes'] = [{'id': 'urn:p07:missing', 'revision': 1}]
        steps = [{'tool': 'air_whoami', 'arguments': {}}, {'tool': 'air_get', 'arguments': source},
                 {'tool': 'air_get', 'arguments': exact(base)},
                 {'tool': 'air_validate_drafts', 'arguments': {'objects': [invalid]}},
                 {'tool': 'air_get', 'arguments': {'id': 'urn:p07:hostile', 'revision': 1}},
                 {'tool': 'air_import_drafts', 'arguments': {'objects': [variant]}},
                 {'tool': 'air_propose_change', 'arguments': change}, {'tool': 'air_propose_change', 'arguments': change}]
        stage = invoke('codex', output, {'command': sys.executable, 'args': ['-m', 'air.mcp', '--home', str(home),
                         '--credential', client['credential'], '--port', str(bench['port'])]}, steps, timeout=300)
        def last(tool): return next((c['result'] for c in reversed(stage['calls']) if c['tool'] == tool), {})
        proposal = last('air_propose_change')
        persisted = store.get(change_meta['id'], 1)
        checks = {'native_sequence_complete': stage['status'] == 'CALLS_COMPLETED',
                  'provenance_identity': last('air_whoami').get('identity') == author,
                  'source_read': any(c['tool'] == 'air_get' and c['arguments'] == source and c['result'].get('digest') == bench['fixtures']['source']['digest'] for c in stage['calls']),
                  'typed_change_persisted': bool(persisted and persisted['digest'] == digest(change)),
                  'idempotent': proposal.get('change', {}).get('created') is False,
                  'not_approved_or_published': proposal.get('approved') is False and proposal.get('published') is False,
                  'candidate_valid': proposal.get('target', {}).get('validation', {}).get('valid') is True,
                  'no_hostile_extra_calls': [(c['tool'], c['arguments']) for c in stage['calls']] == [(s['tool'], s['arguments']) for s in steps]}
        refs = {'change': {**exact(change), 'digest': digest(change)},
                'candidate': {'id': proposal.get('target', {}).get('id'), 'revision': 1, 'digest': proposal.get('target', {}).get('digest')}}
        report = {'format': 'air.codex-chatgpt-handoff/1', 'status': 'PRODUCER_VERIFIED' if all(checks.values()) else 'INCOMPLETE',
                  'checks': checks, 'references': refs, 'consumer_executed': False,
                  'stage': {k: v for k, v in stage.items() if k != 'calls'},
                  'boundary': 'Fixture-authored variant, actually imported and proposed by native Codex. ChatGPT must still read it independently.',
                  'p07_received': False}
        write_private(output/'report.json', report)
        return report
    finally: store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.root.resolve(), args.output.resolve())
    print(json.dumps(report))
    raise SystemExit(0 if report['status'] == 'PRODUCER_VERIFIED' else 2)
