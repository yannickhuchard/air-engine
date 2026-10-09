"""Three fictitious knowledge dossiers, exact baselines, decisions and recovery."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from air import __version__
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.config import Settings, protect_directory, write_private
from air.core import KNOWLEDGE_PROFILE, digest
from air.foundation import exact
from air.knowledge import inspect_knowledge
from air.mcp import APIClient, PROTOCOL, Session
from air.storage import Store
from install import start, stop

ROOT = Path(__file__).resolve().parents[1]


def rehearse():
    source = json.loads((ROOT / 'tmp/demo-asteria/business.json').read_text(encoding='utf-8'))
    source_home = Path(source['workbench_home']).resolve()
    assert source_home.is_relative_to((ROOT / 'tmp').resolve()) and source_home.parent.name.startswith('air-runtime-')
    workspace = ROOT / 'tmp' / ('air-runtime-knowledge-' + uuid.uuid4().hex)
    protect_directory(workspace)
    snapshot(source_home, workspace / 'source-backup')
    home = workspace / 'home';restore(workspace / 'source-backup', home)
    store = Store(Settings.load(home).database_url)
    try:
        for case in source['treatments']:
            for role in ('architect', 'observer'):
                name = role + '-' + case['case']
                write_private(home / (name + '.json'), store.create_token(name, 'editor'))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    output = ROOT / 'tmp/demo-asteria/knowledge-workbench';output.mkdir(parents=True, exist_ok=True)
    results = []
    pairs = {
        'D01': ('La confirmation de la demande SAV est enregistrée dans le dossier CRM.', 'La confirmation de cette même demande SAV est absente du dossier ERP.'),
        'D02': ('Le relevé de référence de l’atelier a moins de cinq minutes.', 'Ce même relevé de référence de l’atelier a neuf minutes.'),
        'D03': ('Le collaborateur fictif possède un statut actif dans RH.', 'Ce collaborateur possède un statut inactif dans IAM pour la même période.'),
    }
    start(sys.executable, home, port)
    try:
        for case in source['treatments']:
            code = case['case'];architect = APIClient(home, 'architect-' + code + '.json', port);observer = APIClient(home, 'observer-' + code + '.json', port)
            def call(client, name, request):
                result = client(name, request)
                if 'error' in result: raise RuntimeError('AIR knowledge demo rejected ' + name + ': ' + str(result.get('http_status')))
                return result
            original = call(architect, 'air_export_baseline', case['baseline'])
            goal = next(o for o in original['objects'] if o['meta']['type'] == 'air.Goal')
            scope = goal['body']['targets'][0]['context']
            identity = call(architect, 'air_whoami', {})['identity']
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            prefix = 'urn:asteria:knowledge:' + code.lower() + ':'
            def obj(kind, suffix, body):
                meta = deepcopy(goal['meta']);meta.update(id=prefix + suffix, type='air.' + kind, revision=1,
                    name=kind + ' - ' + code + ' - ' + suffix, recorded_at=now, validity={'start': now, 'end': None}, owner=identity,
                    description='Déclaration entièrement fictive pour la recette du dossier de connaissance.')
                meta['provenance'] = {'recorded_by': identity, 'method': 'Authored fictitious declarations; not an independent observation', 'source_refs': [{'id': prefix + 'source', 'revision': 1}]}
                return {'meta': meta, 'body': body}
            content = json.dumps({'classification': 'FICTIONAL_DEMONSTRATION', 'statements': pairs[code], 'live_measurement': False}, ensure_ascii=False, indent=2).encode('utf-8')
            document = workspace / (code + '-fictitious-statements.json');document.write_bytes(content)
            document_source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': document.as_uri(), 'source_revision': 'sha256:' + hashlib.sha256(content).hexdigest(), 'captured_at': now, 'access_policy': 'Dossier team only', 'retention_policy': 'Retain with fictitious demonstration'})
            document_source['meta']['provenance']['source_refs'] = []
            assertions = [obj('Assertion', 'statement-' + str(i), {'statement': text, 'subject_scope': scope, 'epistemic_status': 'SUPPORTED', 'evidence': [{'id': prefix + 'evidence-' + str(i), 'revision': 1}]}) for i, text in enumerate(pairs[code])]
            evidence = [obj('Evidence', 'evidence-' + str(i), {'source': exact(document_source), 'selector': '/statements/' + str(i), 'evidence_kind': 'DOCUMENT_EXCERPT', 'supports_or_refutes': [{**exact(assertion), 'direction': 'SUPPORTS'}], 'limitations': ['Déclaration fictive rédigée pour la recette ; aucune mesure externe ni vérification indépendante.']}) for i, assertion in enumerate(assertions)]
            conclusion = obj('Assertion', 'candidate-conclusion', {'statement': 'Les informations disponibles permettent de reconstruire un état unique fiable.', 'subject_scope': scope, 'epistemic_status': 'UNASSESSED', 'evidence': []})
            inference = obj('Inference', 'inference', {'conclusion': exact(conclusion), 'premises': [exact(a) for a in assertions], 'derivation': 'Conclusion candidate soumise à examen des deux déclarations et de leur contexte ; aucune preuve automatique.', 'limitations': ['Les déclarations sont fictives, non établies et peuvent décrire des systèmes en désaccord.']})
            conflict = obj('Conflict', 'conflict', {'statements': [exact(a) for a in assertions], 'overlap_scope': scope, 'reason': 'Désaccord déclaré à instruire sur une même opération, un même périmètre et une période commune.'})
            additions = [document_source, *assertions, *evidence, conclusion, inference, conflict]
            call(architect, 'air_import_drafts', {'objects': additions})
            meta = deepcopy(original['baseline']['meta']);meta.update(id='urn:asteria:knowledge-baseline:' + code.lower(), revision=1, recorded_at=now, name='Connaissance et conflits - ' + case['title'])
            opened = call(architect, 'air_freeze_baseline', {'meta': meta, 'profile': KNOWLEDGE_PROFILE, 'members': [exact(o) for o in original['objects'] + additions], 'parent_baselines': [exact(original['baseline'])]})
            assert len(opened['baseline']['body']['members']) == 47
            open_pin = {**exact(opened['baseline']), 'digest': opened['digest']}
            open_request = {'baseline': open_pin, 'as_of': now}
            open_report = call(observer, 'air_inspect_knowledge', open_request)
            assert open_report['conflicts'][0]['resolution_state'] == 'OPEN_DECLARATION'
            decision = obj('Decision', 'decision', {'question': 'Quelle instruction mener pour le désaccord ' + code + ' ?', 'alternatives': ['Relever des données complémentaires', 'Conserver l’incertitude'], 'selection': 'Relever des données complémentaires', 'rationale': 'Une décision d’instruction ne démontre pas encore le nouvel état.', 'basis': [exact(a) for a in assertions] + [exact(inference)], 'authority': identity, 'consequences': ['Le conflit reste non vérifié dans l’attente de nouvelles preuves.'], 'revisit_conditions': ['Réception d’une preuve indépendante et revue par les équipes concernées.']})
            submission = call(architect, 'air_collaboration_submit', {'idempotency_key': 'knowledge-' + uuid.uuid4().hex, 'object': decision})
            updated = deepcopy(conflict);updated['meta']['revision'] = 2;updated['body']['resolution'] = exact(decision)
            call(architect, 'air_import_drafts', {'objects': [updated]})
            final_objects = original['objects'] + [o for o in additions if o is not conflict] + [updated, decision]
            meta = deepcopy(meta);meta['revision'] = 2
            final = call(architect, 'air_freeze_baseline', {'meta': meta, 'profile': KNOWLEDGE_PROFILE, 'members': [exact(o) for o in final_objects], 'parent_baselines': [exact(opened['baseline'])]})
            final_pin = {**exact(final['baseline']), 'digest': final['digest']}
            request = {'baseline': final_pin, 'as_of': now}
            report = call(observer, 'air_inspect_knowledge', request)
            assert len(final['baseline']['body']['members']) == 48
            assert report['conflicts'][0]['resolution_state'] == 'DECISION_RECORDED_UNVERIFIED'
            assert not report['conflicts'][0]['new_state_verified'] and not report['inferences'][0]['conclusion_promoted']
            assert call(observer, 'air_inspect_knowledge', open_request) == open_report
            request_file = workspace / (code + '-request.json');request_file.write_text(json.dumps(request), encoding='utf-8')
            cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'knowledge-inspect', str(request_file), '--credential', 'observer-' + code + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert cli.returncode == 0 and json.loads(cli.stdout) == report
            session = Session(observer);session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'knowledge-demo', 'version': '1'}}});session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            assert session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_inspect_knowledge', 'arguments': request}})['result']['structuredContent'] == report
            workbench = call(observer, 'air_compile_workbench', {'baseline': final_pin})
            html = output / (code + '.html');html.write_text(workbench.pop('content'), encoding='utf-8', newline='\n');workbench['path'] = str(html)
            results.append({'case': code, 'title': case['title'], 'baseline': final_pin, 'workbench': workbench, 'business': case['business'],
                'knowledge': {'conflict': {**exact(updated), 'digest': digest(updated)}, 'request': request, 'report': report, 'open_request': open_request, 'open_report': open_report, 'decision_submission': submission}})
        denied = APIClient(home, 'observer-D01.json', port)('air_inspect_knowledge', results[2]['knowledge']['request'])
        assert denied['http_status'] == 403
    finally: stop(home)
    snapshot(home, workspace / 'backup');restore(workspace / 'backup', workspace / 'restored')
    settings = Settings.load(workspace / 'restored');store = Store(settings.database_url)
    try:
        for result in results:
            principal = {'subject': 'observer-' + result['case'], 'role': 'editor'}
            for request_key, report_key in [('request', 'report'), ('open_request', 'open_report')]:
                assert inspect_knowledge(store, principal, AccessPolicy.load(settings.home), result['knowledge'][request_key]) == result['knowledge'][report_key]
    finally: store.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': KNOWLEDGE_PROFILE, 'treatments': results, 'workbench_home': str(home),
        'cross_dossier_refused': True, 'cli_mcp_replay_identical': True, 'restored_knowledge_reports_identical': True,
        'prior_baselines_preserved': True, 'fictitious_authored_documents': True, 'inference_executed': False, 'conclusions_promoted': False,
        'conflict_resolution_verified': False, 'live_instance_modified': False, 'external_action_executed': False}


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'): stream.reconfigure(encoding='utf-8')
    result = rehearse();output = ROOT / 'tmp/demo-asteria/knowledge.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'dossiers': len(result['treatments']), 'report': str(output)}))
