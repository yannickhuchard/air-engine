"""Exercise three Asteria contributions, divergent shared identity and historical replay."""
import json
from demo_packages import ROOT, rehearse
from air.report_views import reconciliation_html

if __name__ == '__main__':
    result = rehearse(with_context=True)
    output = ROOT / 'tmp/demo-asteria/contexts.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    labels = {'urn:asteria:package:d01': 'SAV omnicanal', 'urn:asteria:package:d02': 'Atelier connecté', 'urn:asteria:package:d03': 'Cycle de vie des identités', 'urn:asteria:scope:identity': 'Identité et habilitations partagées'}
    output.with_suffix('.html').write_text(reconciliation_html(result['contexts']['divergent'], result['contexts']['divergent_analysis'], labels), encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'report': str(output), 'shared_divergences': len(result['contexts']['divergent_analysis']['divergences'])}))
