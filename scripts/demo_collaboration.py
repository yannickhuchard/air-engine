"""Three fictitious dossiers: observation, contribution, decision and exact treatment."""
import json
from demo_runtime import rehearse, ROOT
from air.report_views import collaboration_html

if __name__ == '__main__':
    report = rehearse(with_collaboration=True)
    output = ROOT / 'tmp/demo-asteria/collaboration.json';output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    output.with_suffix('.html').write_text(collaboration_html(report), encoding='utf-8', newline='\n')
    print(json.dumps({'status': report['status'], 'version': report['version'], 'report': str(output)}))
