"""Local authenticated reception on a disposable three-dossier Asteria demo only.

Creates and revokes test credentials in the demo registry. No credential bytes
are printed or copied into the report. TestClient is a development dependency.
"""
import argparse
import json
import os
from pathlib import Path
from fastapi.testclient import TestClient
from air.api import create_app
from air.config import Settings, write_private
from air.storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', type=Path)
    args = parser.parse_args()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated reception')
    run = args.demo.resolve().parent
    workspace_tmp = Path(__file__).resolve().parents[1] / 'tmp'
    if not run.is_relative_to(workspace_tmp.resolve()): raise ValueError('Reception must use a workspace tmp demo')
    demo = json.loads(args.demo.read_text(encoding='utf-8'))
    root = Path(demo['entrypoint']).resolve()
    if not root.is_relative_to(run): raise ValueError('Demo entrypoint is outside its run')
    root = root.parent
    homes = list(run.glob('registry-*'))
    if len(homes) != 1 or homes[0].is_symlink(): raise ValueError('Use a fresh isolated demo with one owned registry')
    home = homes[0].resolve()
    if not home.is_relative_to(run): raise ValueError('Registry is outside its isolated run')
    dossiers = demo['site']['dossiers']
    if len(dossiers) != 3 or any(not d['namespace'].startswith('asteria.') for d in dossiers):
        raise ValueError('This receipt qualifies only the three fictional Asteria dossiers')
    settings = Settings(home, 'sqlite:///' + (home / 'air.db').as_posix(), instance_id='site-demo')
    store = Store(settings.database_url);store.check_version()
    policy_file = home / 'access-policy.json'
    if policy_file.exists(): raise ValueError('Reception never replaces an existing access policy')
    tokens, checks, refused = [], [], 0
    static_count, download_count, policy_created = 0, 0, False
    before = store.counts()
    try:
        subjects = {}
        for d in dossiers:
            token = store.create_token('capsule-reception:' + d['namespace'], 'reader')
            tokens.append(token)
            subjects[token['subject']] = {'read': [d['namespace'], 'asteria.shared']}
        write_private(policy_file, {'version': 'ux04-isolated-reception/1', 'subjects': subjects})
        policy_created = True
        with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
            for d, token in zip(dossiers, tokens):
                headers = {'Authorization': 'Bearer ' + token['access_token']}
                identity = client.get('/v1/identity', headers=headers).json()['identity']
                folder = (root / d['path']).parent.resolve()
                if not folder.is_relative_to(root): raise ValueError('Dossier is outside the generated site')
                candidates = sorted(folder.glob('question-*.json'))
                assert len(candidates) == 37
                static_count += len(candidates)
                downloads = sorted((run / 'browser').glob('*-' + d['namespace'] + '.json'))
                download_count += len(downloads)
                candidates += downloads
                for file in candidates:
                    request = json.loads(file.read_text(encoding='utf-8'))
                    response = client.post('/v1/agent/questions/resume', json=request, headers=headers)
                    if response.status_code != 200: raise AssertionError('Question reception failed: ' + file.name)
                    result = response.json();receipt = result['receipt']
                    assert receipt['identity'] == identity and receipt['role'] == 'reader'
                    assert receipt['baseline'] == d['baseline'] and not receipt['signed']
                    resumed = client.post('/v1/agent/questions/resume', json={**request, 'previous_receipt': receipt}, headers=headers)
                    assert resumed.status_code == 200 and resumed.json() == result
                    checks.append({'namespace': d['namespace'], 'file': file.name,
                                   'capsule_digest': request['capsule']['capsule_digest'], 'receipt_digest': receipt['receipt_digest']})
                for other in dossiers:
                    if other['namespace'] == d['namespace']: continue
                    request = json.loads(((root / other['path']).parent / 'question-23.json').read_text(encoding='utf-8'))
                    assert client.post('/v1/agent/questions/resume', json=request, headers=headers).status_code == 403
                    refused += 1
        assert store.counts() == before
    finally:
        # TestClient closes its store; this separate handle owns the fixture cleanup.
        for token in tokens:
            store.revoke_token(token['token_id'])
            assert store.authenticate(token['access_token']) is None
        if policy_created and policy_file.exists(): policy_file.unlink()
        store.engine.dispose()
    result = {'status': 'PASS_SCOPED', 'authenticated_api': True, 'reader_identities': len(tokens),
              'static_capsules': static_count, 'browser_downloads': download_count,
              'same_context_resumptions': len(checks), 'cross_namespace_reads_refused': refused,
              'architecture_revisions_written': False, 'test_credentials_revoked': True,
              'native_assistant_exercised': False, 'checks': checks}
    (run / 'capsule-registry-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}))


if __name__ == '__main__': main()
