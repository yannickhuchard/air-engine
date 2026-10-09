"""Generate a synthetic read-only Workbench containing hostile-looking model text."""
import json
import os
from pathlib import Path
import uuid
from air.access import AccessPolicy
from air.config import Settings
from air.foundation import exact
from air.storage import Store
from air.workbench import compile_workbench
from demo_runtime import cases_for, ROOT

if __name__ == '__main__':
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('This fixture is isolated')
    workspace = ROOT / 'tmp' / ('workbench-hostile-' + uuid.uuid4().hex);workspace.mkdir(parents=True)
    settings = Settings(workspace, 'sqlite:///' + (workspace / 'test.db').as_posix(), instance_id='hostile-fixture')
    store = Store(settings.database_url);store.migrate()
    try:
        case = cases_for(store)[0]
        case['source']['meta']['name'] = '</title><script>window.airInjected=true</script><img src="https://example.invalid/leak" onerror="window.airInjected=true">'
        case['source']['body']['locator'] = 'javascript:window.airInjected=true'
        store.put_bundle([case['source'], case['observation'], case['drift'], case['incident']], 'fixture')
        baseline = store.create_baseline(case['baseline_request'], 'fixture')
        request = {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}}
        result = compile_workbench(store, {'subject': 'reader', 'role': 'reader'}, AccessPolicy(), settings, request)
        output = ROOT / 'tmp/demo-asteria/workbench/hostile.html';output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result['content'], encoding='utf-8', newline='\n')
        print(json.dumps({'status': 'PREPARED', 'path': str(output), 'digest': result['content_digest']}))
    finally: store.engine.dispose()
