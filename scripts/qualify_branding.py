"""Continue three real AIR-plugin artifact receipts through authenticated CLI/site generation.

The connected-plugin calls are performed separately; this script does not impersonate
ChatGPT. It rejects missing/unequal receipts and keeps direct-tool refresh pending.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from air.branding import normalize
from air.storage import Store
from p07_chatgpt_bench import checked

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bench', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    bench, home, settings = checked(args.bench.resolve())
    receipts = json.loads(args.receipts.read_text(encoding='utf-8'))
    assert [r['test'] for r in receipts] == ['enterprise', 'consultant', 'studio']
    assert all(r['transport'] == 'CONNECTED_AIR_PLUGIN_IN_CODEX' and r['read_equal'] and not r['read_isError'] for r in receipts)
    def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    def cli(command, request, workspace, *options):
        filename = output / (workspace.name + '-' + command + '-request.json'); write(filename, request)
        result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), command, str(filename),
            '--port', str(bench['port']), '--credential', bench['credential'], '--workspace', str(workspace), *options],
            capture_output=True, encoding='utf-8', timeout=120)
        if result.returncode: raise RuntimeError('CLI failed: ' + result.stderr[:1000] + result.stdout[:1000])
        return json.loads(result.stdout)
    store = Store(settings.database_url)
    try:
        pins = []
        for suffix in ('sav', 'atelier', 'identites'):
            base = store.export_baseline({'id': 'urn:asteria:construction-baseline:' + suffix, 'revision': 1})
            pins.append({'id': base['baseline']['meta']['id'], 'revision': 1, 'digest': base['digest']})
        checks = []
        for receipt, pin in zip(receipts, pins):
            name = receipt['test']; workspace = output / name
            profile = json.loads((ROOT / 'fixtures/branding' / (name + '.json')).read_text(encoding='utf-8'))['profile']
            expected = normalize(profile)
            configured = cli('branding-configure', {'profile': {'artifact': receipt['import']['artifact']}}, workspace, '--apply')
            assert configured['profile_digest'] == expected['profile_digest']
            assert configured['source_artifact']['content_digest'] == receipt['read']['content_digest']
            wire = '\n'.join(json.dumps(message) for message in [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'branding-local-reception', 'version': '1'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_compile_branding', 'arguments': {'profile': {'artifact': receipt['import']['artifact']}}}},
            ]) + '\n'
            mcp = subprocess.run([sys.executable, '-m', 'air.mcp', '--home', str(home), '--port', str(bench['port']), '--credential', bench['credential']],
                                 input=wire, capture_output=True, encoding='utf-8', timeout=120)
            assert mcp.returncode == 0
            reply = next(json.loads(line) for line in mcp.stdout.splitlines() if json.loads(line).get('id') == 2)
            assert not reply['result']['isError']
            assert reply['result']['structuredContent']['file_set_digest'] == configured['file_set_digest']
            repeated = cli('branding-configure', {'profile': {'artifact': receipt['import']['artifact']}}, workspace, '--apply')
            assert repeated['written'] == []
            pack = cli('deliverables', {'title': 'Recette ' + name, 'baselines': [pin]}, workspace,
                       '--apply')  # Reuses the configured local branding automatically.
            dossier = pack['website']['dossiers'][0]
            assert dossier['branding']['profile_digest'] == expected['profile_digest']
            page = (workspace / 'livrables/site' / dossier['path']).read_text(encoding='utf-8')
            assert expected['profile']['name'] in page
            checks.append({'test': name, 'baseline': pin, 'profile_digest': expected['profile_digest'],
                'plugin_artifact_roundtrip': 'PASS', 'authenticated_cli_artifact_compile': 'PASS',
                'local_mcp_stdio_compile_and_cli_parity': 'PASS',
                'cli_idempotence': 'PASS', 'dossier_identity': 'PASS', 'warnings': expected['warnings'],
                'source_artifact': receipt['import']['artifact'], 'website': pack['website'],
                'entrypoint': str(workspace / pack['website']['entrypoint'])})
        combined = output / 'portfolio'
        selection = {'default': {'name': 'Morgan Conseil'}, 'dossiers': [
            {'baseline': pin, 'profile': {'artifact': r['import']['artifact']}} for pin, r in zip(pins, receipts)]}
        pack = cli('deliverables', {'title': 'Trois identités de dossier', 'baselines': pins, 'branding': selection}, combined, '--apply')
        for dossier, check in zip(pack['website']['dossiers'], checks):
            assert dossier['branding']['profile_digest'] == check['profile_digest']
        write(output / 'site-demo.json', {'entrypoint': str(combined / pack['website']['entrypoint']), 'site': pack['website']})
        report = {'status': 'PASS_SCOPED', 'plugin_calls': 'ACTUAL_CONNECTED_AIR_PLUGIN_IN_CODEX',
                  'tests': checks, 'same_portfolio_separate_identities': True,
                  'direct_branding_tool_in_cached_connector': 'PENDING_CATALOGUE_REFRESH',
                  'native_chatgpt_ui_qualification': 'NOT_EXECUTED', 'business_execution': False}
        write(output / 'report.json', report)
        print(json.dumps({'status': report['status'], 'profiles': 3, 'entrypoint': str(combined / pack['website']['entrypoint'])}))
    finally: store.engine.dispose()


if __name__ == '__main__': main()
