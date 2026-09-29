"""Generate three offline Workbenches from authenticated CLI/HTTP/MCP contexts."""
import json
from demo_runtime import rehearse, ROOT

if __name__ == '__main__':
    report = rehearse(with_collaboration=True, with_workbench=True)
    output = ROOT / 'tmp/demo-asteria/workbench.json';output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'version': report['version'], 'report': str(output)}))
