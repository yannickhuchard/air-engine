"""Reauthorize and close the three-dossier resource rehearsal over real HTTP."""
import json
from pathlib import Path
from demo_admission import rehearse

if __name__ == '__main__':
    result = rehearse(with_lifecycle=True)
    output = Path(__file__).resolve().parents[1] / 'tmp/demo-asteria/lifecycle.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    from air.report_views import lifecycle_html
    output.with_suffix('.html').write_text(lifecycle_html(result), encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'version': result['version'], 'lifecycle': result['lifecycle']['status'], 'report': str(output)}))
