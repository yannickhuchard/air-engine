"""Extend the three dossier baselines with draft business purpose and metric targets."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from air.core import BUSINESS_PROFILE, digest
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL

LABELS = {
    'D01': ('Fiabiliser le traitement des demandes SAV', 'Disponibilité de la confirmation ERP pour l’opération observée', 'Traiter une demande de service après-vente', 'Service après-vente des équipements industriels', 'Comment conserver une demande lorsque la confirmation ERP est indisponible ?'),
    'D02': ('Fonder les recommandations d’inspection sur des mesures récentes', 'Âge de la mesure utilisée dans la recommandation observée', 'Préparer une inspection de maintenance', 'Maintenance préventive de l’atelier connecté', 'Quelle fraîcheur de mesure exige la préparation d’une inspection ?'),
    'D03': ('Maîtriser les changements d’accès des collaborateurs', 'Cohérence du statut RH/IAM pour l’opération observée', 'Instruire un changement d’accès', 'Gestion des accès des collaborateurs', 'Comment traiter une contradiction RH/IAM avant une révocation ?'),
}


def extend(case, baseline, call, workspace, home, port):
    observer, architect = 'observer-' + case['id'], 'architect-' + case['id']
    bridge = APIClient(home, observer + '.json', port)
    owner = call('/v1/identity', None, architect)['identity']
    purpose, metric_name, ability, offer, question = LABELS[case['id']]
    scope = case['observation']['body']['instance_or_scope']
    members = baseline['baseline']['body']['members']
    def first(kind): return {k: next(r for r in members if r['type'] == 'air.' + kind)[k] for k in ('id', 'revision')}
    contract = bridge('air_get', first('SemanticContract'))['object']
    def obj(kind, suffix, name, body):
        meta = deepcopy(case['observation']['meta']);meta.update(id='urn:asteria:business:' + case['id'].lower() + ':' + suffix,
            type='air.' + kind, name=name, owner=owner)
        meta['provenance']['recorded_by'] = owner;meta['provenance']['method'] = 'Explicit fictitious business model for AIR reception'
        return {'meta': meta, 'body': body}
    unit = 'second' if case['id'] == 'D02' else '1'
    metric = obj('Metric', 'metric', metric_name, {'definition': metric_name, 'unit': unit, 'aggregation': 'Valeur de l’échantillon explicitement fourni ; aucune agrégation de population calculée',
        'population': 'Une opération fictive du dossier ' + case['id'], 'window': 'PT300S', 'collection_method': 'Échantillon synthétique avec Source et fenêtre exactes'})
    threshold = {'type': 'Quantity[second]', 'value': '300'} if unit == 'second' else {'type': 'Boolean', 'value': True}
    goal = obj('Goal', 'goal', 'Objectif - ' + case['title'], {'outcome': purpose, 'measures': [exact(metric)],
        'targets': [{'id': 'sample-target', 'metric': exact(metric), 'operator': 'LTE' if unit == 'second' else 'EQ', 'value': threshold, 'unit': unit, 'context': scope}],
        'horizon': {'start': '2026-09-19T00:00:00Z', 'end': '2026-09-20T00:00:00Z'}})
    intent = obj('Intent', 'intent', 'Intention - ' + case['title'], {'desired_change': purpose, 'sponsor': owner, 'scope': scope, 'goals': [exact(goal)]})
    concern = obj('Concern', 'concern', 'Préoccupation - ' + case['title'], {'question': question, 'scope': scope, 'addressed_by': []})
    stakeholder = obj('Stakeholder', 'stakeholder', 'Responsable - ' + case['title'], {'identity_or_group': owner, 'concerns': [exact(concern)], 'participation_role': 'Responsable déclaré du dossier fictif ; pas de mandat métier implicite'})
    functions = {(r['function']['id'], r['function']['revision']): r['function'] for r in contract['body']['operations']}
    capability = obj('Capability', 'capability', 'Capacité - ' + case['title'], {'ability': ability, 'outcomes': [exact(goal)], 'required_functions': list(functions.values()), 'context': scope, 'maturity_evidence': []})
    service = obj('BusinessService', 'service', 'Service - ' + case['title'], {'beneficiaries': [first('Actor')], 'value_proposition': purpose, 'capabilities': [exact(capability)], 'service_commitments': [exact(contract)]})
    product = obj('Product', 'product', 'Offre - ' + case['title'], {'offer': offer, 'market_scope': scope, 'services': [exact(service)], 'lifecycle_owner': owner})
    objects = [metric, goal, intent, concern, stakeholder, capability, service, product]
    call('/v1/draft-bundles', objects, architect)
    observation = deepcopy(case['observation']);observation['meta'].update(id='urn:asteria:business:' + case['id'].lower() + ':metric-observation', name='Mesure de la cible - ' + case['title'])
    observation['meta']['provenance']['method'] = 'Explicit metric binding of the same fictitious sample; not independent additional evidence'
    observation['body']['metric_or_signal'] = exact(metric)
    ingestion = call('/v1/runtime/observations', {'idempotency_key': 'metric-' + case['id'], 'source': {**exact(case['source']), 'digest': digest(case['source'])}, 'observations': [observation]}, observer)
    request = {'goal': {**exact(goal), 'digest': digest(goal)}, 'as_of': case['comparison']['as_of'], 'window': case['comparison']['window'], 'max_age_seconds': 120,
        'bindings': [{'target': 'sample-target', 'observation': {**exact(observation), 'digest': digest(observation)}}]}
    assessed = call('/v1/goals/assess', request, observer)
    assert assessed['result'] == ('CONFLICTING' if case['id'] == 'D03' else 'VIOLATED') and not assessed['goal_outcome_verified']
    assert assessed == call('/v1/goals/assess', request, observer)
    stale = deepcopy(request);stale['max_age_seconds'] = 30
    stale_report = call('/v1/goals/assess', stale, observer);assert stale_report['result'] == 'UNKNOWN'
    meta = deepcopy(baseline['baseline']['meta']);meta.update(id='urn:asteria:business-baseline:' + case['id'].lower(), name='Objectifs et services - ' + case['title'])
    final = call('/v1/baselines', {'meta': meta, 'profile': BUSINESS_PROFILE,
        'members': [{k: r[k] for k in ('id', 'revision')} for r in members] + [exact(o) for o in objects + [observation]], 'parent_baselines': [exact(baseline['baseline'])]}, architect)
    assert final['validation']['valid'] and len(final['baseline']['body']['members']) == 39
    if case['id'] == 'D03':
        call('/v1/goals/assess', request, 'observer-D01', (403,))
        session = Session(bridge)
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'business-demo', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        result = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_assess_goal_targets', 'arguments': request}})['result']
        assert not result['isError'] and result['structuredContent'] == assessed
        filename = workspace / 'goal-assess.json';filename.write_text(json.dumps(request), encoding='utf-8')
        cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'goal-assess', str(filename), '--credential', observer + '.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert cli.returncode == 0 and json.loads(cli.stdout) == assessed
    return final, {'goal': request['goal'], 'request': request, 'assessment': assessed, 'stale_assessment': stale_report,
        'ingestion': ingestion, 'collaboration_baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}}
