"""Recompute bounded P07 follow-up checks from native transcripts, not client prose."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from air import __version__
from air.config import protect_directory
from air.native_evidence import calls
from air.storage import Store
from p07_session_bench import bench_home, inspect, state
from p07_session_evidence import fingerprint, tested_source

ROOT = Path(__file__).resolve().parents[1]


def sha(data): return hashlib.sha256(data).hexdigest()


def read_native(folder, client, report_name='report.json'):
    report = json.loads((folder/report_name).read_text(encoding='utf-8'))
    streams = list(folder.glob('*.jsonl'))
    if len(streams) != 1:
        raise ValueError('Exactly one native transcript is required')
    raw = streams[0].read_bytes()
    expected = report.get('transcript_sha256') or report['stage']['transcript_sha256']
    if sha(raw) != expected:
        raise ValueError('Native transcript hash mismatch')
    return report, calls(client, [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]), sha(raw)


def assemble(root, transcript, output):
    root = root.resolve(); bench = state(root); _, settings = bench_home(root, bench)
    if output.exists():
        raise ValueError('Choose a new evidence directory')
    private = root/'followup-transcript-snapshots'; protect_directory(private)
    raw = transcript.read_bytes()
    raw_hash = sha(raw)
    # Content-addressed private snapshot is preserved even when the live session grows.
    snapshot = private/(raw_hash+'.jsonl')
    if not snapshot.exists():
        snapshot.write_bytes(raw)
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    claude = calls('claude-code', rows)
    producer, codex, codex_hash = read_native(root/'codex-to-claude-final', 'codex')
    stale, stale_calls, stale_hash = read_native(root/'codex-stale-catalog', 'codex')
    discovery, discovery_calls, discovery_hash = read_native(root/'codex-project-discovery', 'codex')
    local_discovery, local_calls, local_hash = read_native(root/'codex-project-discovery-local-only', 'codex')
    def find(items, tool, object_id=None):
        return next((c['result'] for c in reversed(items) if c['tool'] == tool and
                     (object_id is None or c['arguments'].get('id') == object_id)), {})
    who_codex = find(codex, 'air_whoami'); who_claude = find(claude, 'air_whoami')
    proposal = find(codex, 'air_propose_change')
    change = producer['references']['change']; candidate = producer['references']['candidate']
    read_change = find(claude, 'air_get', change['id'])
    read_candidate = find(claude, 'air_export_baseline', candidate['id'])
    cross = {
        'producer_proposal_observed': proposal.get('change', {}).get('digest') == change['digest'],
        'distinct_identities': who_codex.get('subject') == bench['clients']['codex']['subject'] != who_claude.get('subject') == bench['subject'],
        'change_digest_identical': read_change.get('digest') == change['digest'],
        'candidate_digest_identical': read_candidate.get('digest') == candidate['digest'],
        'declared_provenance_matches_producer': bool(who_codex.get('identity')) and
            read_change.get('object', {}).get('meta', {}).get('provenance', {}).get('recorded_by') == who_codex.get('identity'),
        'no_approval_or_publication': proposal.get('approved') is False and proposal.get('published') is False,
    }
    outage_indices = [i for i, c in enumerate(claude) if c['result'].get('error') == 'AIR_UNREACHABLE']
    first = outage_indices[0] if outage_indices else len(claude)
    last = outage_indices[-1] if outage_indices else len(claude)
    before = find(claude[:first], 'air_get', 'urn:p07:codex:handoff:change')
    after = find(claude[last+1:], 'air_get', 'urn:p07:codex:handoff:change')
    network = {
        'get_and_identity_unreachable': {claude[i]['tool'] for i in outage_indices} == {'air_get', 'air_whoami'},
        'no_object_during_outage': bool(outage_indices) and all('object' not in claude[i]['result'] for i in outage_indices),
        'same_digest_after_recovery': bool(before.get('digest')) and before.get('digest') == after.get('digest'),
        'same_identity_after_recovery': find(claude[:first], 'air_whoami').get('subject') ==
            find(claude[last+1:], 'air_whoami').get('subject') == bench['subject'],
    }
    identities = [c['result'] for c in stale_calls if c['tool'] == 'air_whoami']
    store = Store(settings.database_url)
    try:
        counts = inspect(store, bench)['counts']
    finally:
        store.engine.dispose()
    denials = {
        'initial_mandate_observed': bool(identities and {'admit', 'activate'} <= set(identities[0].get('actions', []))),
        'admission_refused': find(stale_calls, 'air_admission_admit').get('http_status') == 403,
        'activation_refused': find(stale_calls, 'air_admission_activate').get('http_status') == 403,
        'mandate_absent_after_revocation': len(identities) == 2 and not {'admit', 'activate'}.intersection(identities[-1].get('actions', [])),
        'no_commitments': not any(counts.values()) and stale['before'] == stale['after'] == counts,
    }
    checks = {'claude_network_recovery': network, 'codex_to_claude_resume': cross, 'codex_stale_catalog_refusals': denials}
    source_files = [(str(p.relative_to(ROOT)).replace('\\', '/'), p.read_bytes()) for p in (ROOT/'src/air').rglob('*')
                    if p.suffix in ('.py', '.json') and '__pycache__' not in p.parts]
    source = fingerprint(source_files)
    normalized_source = fingerprint([(name, data.replace(b'\r\n', b'\n')) for name, data in source_files])
    if normalized_source != tested_source(producer['source_commit']):
        raise ValueError('Engine differs from the native producer tested revision')
    mcp_hash = sha((ROOT/'src/air/mcp.py').read_bytes())
    if producer['mcp_sha256'] != mcp_hash or stale['mcp_sha256'] != mcp_hash:
        raise ValueError('Native adapter hash mismatch')
    junit = (root/'junit-followup-final.xml').read_bytes()
    suites = list(ET.fromstring(junit).iter('testsuite'))
    test_counts = {key: sum(int(s.get(key, '0')) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    report = {'format': 'air.p07-native-followup/1', 'air_version': __version__, 'source_sha256': source,
              'committed_lf_source_sha256': normalized_source,
              'source_byte_scope': 'source_sha256 hashes actual tested working files; committed_lf_source_sha256 hashes the same contents with LF. Three pre-existing checkout files contain CRLF. No historical source fingerprint is rewritten.',
              'tested_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'checks': checks, 'results': {name: 'PASS_SCOPED' if all(values.values()) else 'INCOMPLETE' for name, values in checks.items()},
              'claude_client_version': sorted({r['version'] for r in rows if r.get('version')}),
              'codex_client_version': producer['stage']['client_version'],
              'claude_fresh_project_session': {'project_instructions_observed': 'Le registre AIR de Asteria fait foi' in raw.decode('utf-8'),
                  'native_tools_working': find(claude, 'air_capabilities').get('engine_version') == __version__,
                  'context': 'New Claude desktop Code session in the already trusted generated workspace; only exact object references supplied, no producer conversation.'},
              'native_transcript_sha256': {'claude': raw_hash, 'codex_producer': codex_hash, 'codex_stale_catalog': stale_hash, 'codex_project_discovery': discovery_hash,
                  'codex_local_only_discovery': local_hash},
              'codex_project_discovery': {'status': discovery['status'], 'local_air_calls': len(discovery_calls),
                  'observation': 'The native run used the remote codex_apps AIR connector (404), not the generated local air MCP. No local project discovery success is claimed.'},
              'codex_local_only_discovery': {'status': local_discovery['status'], 'local_air_calls': len(local_calls),
                  'checks': local_discovery['checks'], 'observation': 'Repeated with an explicit ban on the remote connector: no local AIR tool calls observed; the client reports absent local tools. Cause not established.'},
              'local_tests': {**test_counts, 'junit_sha256': sha(junit), 'ci': False},
              'references': producer['references'], 'private_root': 'tmp/p07-claude-session',
              'preserved_attempts': ['codex-to-claude: calls succeeded but copied provenance still declared Claude',
                  'codex-to-claude-corrected: native proposal rejected 422 because REPLACE changed identity; corrected without overwriting immutable revisions'],
              'recipes_sha256': {p.name: sha(p.read_bytes()) for p in (ROOT/'scripts').glob('p07_native_*.py')},
              'p07_received': False, 'production_ready': False, 'ci': 'NOT_RUN_BY_USER_DECISION',
              'remaining': ['Claude native admission/activation refusal cases', 'Complete same-source native client suites and transverse journeys',
                  'Codex automatic local project discovery and interactive cancellation', 'Working ChatGPT native connector',
                  'Independent human review', 'Exchange between two physical workstations']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    return {'results': report['results'], 'source_sha256': source, 'p07_received': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--claude-transcript', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = assemble(args.root, args.claude_transcript, args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(value == 'PASS_SCOPED' for value in result['results'].values()) else 2)
