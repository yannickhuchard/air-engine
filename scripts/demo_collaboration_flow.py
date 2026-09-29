"""Extend a runtime dossier with explicitly authored draft treatment decisions."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from air.core import COLLABORATION_PROFILE
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL

TREATMENTS = {
    'D01': ('Conserver la demande en attente et réessayer la confirmation ERP avec un identifiant idempotent.', 'Rejeter immédiatement la demande.', 'Réexaminer après rétablissement de l’ERP ou évolution du délai de traitement.'),
    'D02': ('Suspendre la recommandation et exiger une mesure fraîche avant inspection.', 'Utiliser la mesure ancienne sans réserve.', 'Réexaminer après restauration de la collecte ou modification du seuil de fraîcheur.'),
    'D03': ('Suspendre la révocation automatique et soumettre la contradiction aux responsables RH et IAM.', 'Révoquer à partir d’une seule source.', 'Réexaminer après résolution documentée du conflit entre RH et IAM.'),
}


def treatment(case, baseline, call, workspace, home, port, with_workbench=False, with_business=False):
    observer, architect = 'observer-' + case['id'], 'architect-' + case['id']
    observation_identity = call('/v1/identity', None, observer)['identity']
    decision_identity = call('/v1/identity', None, architect)['identity']
    assert observation_identity != decision_identity
    def meta(kind, suffix, author):
        value = deepcopy(case['observation']['meta'])
        value.update(id='urn:asteria:collaboration:' + case['id'].lower() + ':' + suffix, type='air.' + kind, name=suffix + ' — ' + case['title'])
        value['provenance']['recorded_by'] = author
        value['provenance']['method'] = 'Explicit fictitious team contribution in the AIR demonstration'
        return value
    contribution = {'meta': meta('Contribution', 'question', observation_identity),
        'body': {'author': observation_identity, 'target': [exact(case['observation']), case['drift']['body']['expected']],
            'kind': 'QUESTION', 'message': 'Quel traitement proposer pour cet écart observé, sans perdre sa trace ni autoriser implicitement une action ?'}}
    question = call('/v1/collaboration/submissions', {'idempotency_key': 'question-' + case['id'], 'object': contribution}, observer)
    chosen, rejected, revisit = TREATMENTS[case['id']]
    decision = {'meta': meta('Decision', 'decision', decision_identity), 'body': {
        'question': 'Quel traitement de conception retenir pour ' + case['title'] + ' ?', 'alternatives': [chosen, rejected], 'selection': chosen,
        'rationale': 'Conserver la traçabilité et demander la vérification nécessaire avant toute action métier.',
        'basis': [exact(case['observation']), case['drift']['body']['expected']], 'authority': decision_identity,
        'consequences': ['Travail de conception à instruire et faire revoir ; aucune activation externe dans cette recette.'], 'revisit_conditions': [revisit]}}
    forged = deepcopy(decision);forged['body']['authority'] = observation_identity
    call('/v1/collaboration/submissions', {'idempotency_key': 'forged-' + case['id'], 'object': forged}, architect, (403,))
    submitted = call('/v1/collaboration/submissions', {'idempotency_key': 'decision-' + case['id'], 'object': decision}, architect)
    replay = call('/v1/collaboration/submissions', {'idempotency_key': 'decision-' + case['id'], 'object': decision}, architect)
    assert not replay['created'] and replay['submission'] == submitted['submission']
    resolution = deepcopy(contribution);resolution['meta']['revision'] = 2
    resolution['body'].update(kind='RESOLUTION', resolution=exact(decision), message='Proposition documentée dans la décision liée ; efficacité métier non vérifiée.')
    resolved = call('/v1/collaboration/submissions', {'idempotency_key': 'resolution-' + case['id'], 'object': resolution}, observer)
    drift = deepcopy(case['drift']);drift['meta']['revision'] = 2;drift['body']['treatment'] = exact(decision)
    incident = deepcopy(case['incident']);incident['meta']['revision'] = 2;incident['body']['learning'] = [exact(drift)]
    call('/v1/draft-bundles', [drift, incident], architect)
    request = deepcopy(case['baseline_request']);request['profile'] = COLLABORATION_PROFILE
    request['meta'].update(id='urn:asteria:collaboration-baseline:' + case['id'].lower(), name='Décision de traitement — ' + case['title'])
    replaced = {drift['meta']['id']: exact(drift), incident['meta']['id']: exact(incident)}
    request['members'] = [replaced.get(r['id'], r) for r in request['members']] + [exact(resolution), exact(decision)]
    request['parent_baselines'] = [exact(baseline['baseline'])]
    snapshot = call('/v1/baselines', request, architect)
    assert len(snapshot['baseline']['body']['members']) == 30 and snapshot['validation']['valid']
    read_request = {'submission': submitted['submission']}
    received = call('/v1/collaboration/read', read_request, observer)
    assert received['business_mandate_granted'] is False
    if case['id'] == 'D03':
        session = Session(APIClient(home, observer + '.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'collaboration-demo', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        result = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_collaboration_read', 'arguments': read_request}})['result']
        assert not result['isError'] and result['structuredContent'] == received
        request_file = workspace / 'collaboration-read.json';request_file.write_text(json.dumps(read_request), encoding='utf-8')
        command = [sys.executable, '-m', 'air', '--home', str(home)]
        cli = subprocess.run(command + ['collaboration-read', str(request_file), '--credential', observer + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert cli.returncode == 0 and json.loads(cli.stdout) == received
        cli = subprocess.run(command + ['whoami', '--credential', observer + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert cli.returncode == 0 and json.loads(cli.stdout)['identity'] == observation_identity
    business = None
    if with_business:
        from demo_business_flow import extend
        snapshot, business = extend(case, snapshot, call, workspace, home, port)
    workbench = None
    if with_workbench:
        request = {'baseline': {**exact(snapshot['baseline']), 'digest': snapshot['digest']}}
        rendered = call('/v1/workbench', request, observer)
        assert not rendered['credentials_embedded'] and not rendered['register_modified']
        folder = Path(__file__).resolve().parents[1] / ('tmp/demo-asteria/business-workbench' if with_business else 'tmp/demo-asteria/workbench');folder.mkdir(parents=True, exist_ok=True)
        output = folder / (case['id'] + '.html');output.write_text(rendered['content'], encoding='utf-8', newline='\n')
        workbench = {k: v for k, v in rendered.items() if k != 'content'};workbench['path'] = str(output)
        if case['id'] == 'D03':
            result = session.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'air_compile_workbench', 'arguments': request}})['result']
            assert not result['isError'] and result['structuredContent'] == rendered
            request_file = workspace / 'workbench-request.json';request_file.write_text(json.dumps(request), encoding='utf-8')
            cli_output = workspace / 'cli-workbench.html'
            cli = subprocess.run(command + ['workbench', str(request_file), '--output', str(cli_output), '--credential', observer + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert cli.returncode == 0 and cli_output.read_text(encoding='utf-8') == rendered['content']
            call('/v1/workbench', request, 'observer-D01', (403,))
    return {'case': case['id'], 'title': case['title'], 'selected_treatment': chosen, 'question': question, 'decision': submitted,
        'resolution': resolved, 'receipt': received, 'authorship_forgery_refused': True, 'baseline': {**exact(snapshot['baseline']), 'digest': snapshot['digest']},
        'prior_drift': exact(case['drift']), 'revised_drift': exact(drift), 'independent_subjects': True, 'workbench': workbench, 'business': business}
