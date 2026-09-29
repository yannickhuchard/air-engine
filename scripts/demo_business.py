"""Three Asteria business chains with explicit goals, metric observations and Workbenches."""
import json
from demo_runtime import rehearse, ROOT

if __name__ == '__main__':
    report = rehearse(with_collaboration=True, with_workbench=True, with_business=True)
    output = ROOT / 'tmp/demo-asteria/business.json';output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'version': report['version'], 'report': str(output)}))
