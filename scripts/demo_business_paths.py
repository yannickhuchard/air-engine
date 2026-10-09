"""Receive declared path queries on three isolated fictional Asteria dossiers.

Adds two explicitly fictional designs requested by the user, not business
execution or retroactive results for the nine original acceptance tests.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from air import artifacts, business_paths
from air.access import AccessPolicy
from air.api import create_app
from air.atelier import apply_files, plan_files, previous_generation
from air.config import Settings, protect_directory
from air.core import DELIVERY_PROFILE
from air.deliverables import compile_deliverables
from air.foundation import exact
from air.mcp import PROTOCOL
from air.storage import Store
from demo_architecture_site import extend, read

ROOT = Path(__file__).resolve().parents[1]
TITLES = {'D01': ('Mise à jour de l’adresse de correspondance', ['Recevoir la nouvelle adresse', 'Vérifier le mandat et la cohérence', 'Préparer la confirmation ERP']),
          'D02': ('Proposition proactive d’opportunité au réseau de partenaire', ['Qualifier l’observation machine', 'Préparer une opportunité d’intervention', 'Soumettre la proposition au partenaire'])}


def augment(code, members, store, user, policy, settings):
    if code not in TITLES: return members
    name, stages = TITLES[code]
    own = [o for o in members if o['meta']['namespace'] != 'asteria.shared']
    find = lambda kind: next(o for o in own if o['meta']['type'] == 'air.' + kind)
    prototype = find('Scope')['meta'];function, actor, contract = (find(k) for k in ['Function', 'Actor', 'SemanticContract'])
    added = []
    def obj(kind, suffix, title, body):
        o = {'meta': {**deepcopy(prototype), 'id': 'urn:asteria:paths:' + code.lower() + ':' + suffix, 'type': 'air.' + kind,
                      'name': title, 'description': 'Complément fictif de conception. ' + title}, 'body': body}
        added.append(o);return o
    criterion = obj('AcceptanceCriterion', 'criterion', 'Contrôle de traçabilité du parcours prévu',
                    {'condition': 'Chaque étape possède une fonction et ses liens de conception explicites', 'verification_method': 'ANALYSIS',
                     'acceptance_authority': prototype['owner'], 'cases': []})
    requirement = obj('Requirement', 'requirement', name, {'statement': name + ' sous mandat, avant réalisation des systèmes',
        'kind': 'FUNCTIONAL', 'priority': 'MUST', 'applicability': 'Design fictif à revoir avant implémentation', 'acceptance': [exact(criterion)],
        'source': [exact(next(o for o in members if o['meta']['type'] == 'air.Source'))]})
    functions = []
    for i, stage in enumerate(stages):
        body = deepcopy(function['body']);body.update(inputs=[], outputs=[], preconditions=['Mandat et qualité des données à vérifier'],
            postconditions=[stage + ' prévu dans le design'], effects=[], exceptions=[], satisfies=[exact(requirement)])
        functions.append(obj('Function', 'function-' + str(i), stage, body))
    contract_body = deepcopy(contract['body']);contract_body.update(operations=[{'name': 'Prepare' + str(i), 'function': exact(f)} for i, f in enumerate(functions)],
        state_effects=[], error_contract=[], authorization='Mandat explicite à vérifier par les systèmes à réaliser')
    contract = obj('SemanticContract', 'contract', 'Contrat de préparation du parcours', contract_body)
    domain = find('Domain');authority = find('DataAuthority')
    concept = obj('Concept', 'concept', 'Proposition d’adresse' if code == 'D01' else 'Opportunité d’intervention partenaire',
        {'definition': name + ' : proposition traçable, pas exécution ou vente garantie', 'domain': exact(domain), 'semantic_relations': [], 'steward': prototype['owner']})
    entity = obj('DataEntity', 'entity', concept['meta']['name'], {'concept': exact(concept), 'attributes': [
        {'binding': 'air.attribute/0.23', 'name': 'id', 'value_type': 'Text', 'required': True, 'description': 'Identité de la proposition'},
        {'binding': 'air.attribute/0.23', 'name': 'occurred_at', 'value_type': 'Instant', 'required': True, 'description': 'Date métier de la proposition'},
        {'binding': 'air.attribute/0.23', 'name': 'status', 'value_type': 'Text', 'required': True, 'description': 'État de préparation déclaré'}],
        'identity': [{'binding': 'air.field/0.23', 'name': 'id'}], 'ownership': exact(authority), 'constraints': []})
    raw = json.dumps({'type': 'object', 'additionalProperties': False, 'properties': {'id': {'type': 'string'},
        'occurred_at': {'type': 'string', 'format': 'date-time'}, 'status': {'type': 'string'}}, 'required': ['id', 'occurred_at', 'status']}).encode()
    art = artifacts.put(store, user, policy, settings, {'namespace': prototype['namespace'], 'idempotency_key': 'path-schema-' + code, 'media_type': 'application/json'}, raw)
    schema = obj('DataSchema', 'schema', 'Schéma de la proposition', {'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': art['artifact_reference'],
        'represents': [exact(entity)], 'compatibility_policy': 'Revue avant évolution'})
    block = obj('ArchitectureBlock', 'core', 'Préparation des correspondances' if code == 'D01' else 'Préparation des opportunités',
        {'kind': 'MODULE', 'responsibilities': [name], 'functions': [exact(f) for f in functions[:2]], 'provided_contracts': [exact(contract)],
         'required_contracts': [], 'owned_state': [exact(entity)]})
    boundary = obj('ArchitectureBlock', 'adapter', 'Adaptateur ERP prévu' if code == 'D01' else 'Passerelle partenaire prévue',
        {'kind': 'ADAPTER', 'responsibilities': [stages[-1]], 'functions': [exact(functions[-1])], 'provided_contracts': [],
         'required_contracts': [exact(contract)], 'owned_state': []})
    obj('DataFlow', 'flow', 'Transmettre la proposition prévue', {'source': exact(block), 'destination': exact(boundary), 'schema': exact(schema),
        'purpose': stages[-1], 'transformations': [], 'controls': []})
    verification = obj('VerificationCase', 'auth-case', 'Inspection du mandat prévue', {'target': exact(contract), 'method': 'INSPECTION',
        'inputs': [], 'oracle': 'L’identité et son mandat sont liés à la proposition', 'acceptance': 'Inspection à effectuer après conception détaillée',
        'independence_basis': 'Revue habilitée à prévoir, non effectuée'})
    control = obj('Control', 'auth-control', 'Vérification du mandat prévue', {'objective': 'Préparer une proposition uniquement sous mandat',
        'mechanism': 'Authentification et contrôle d’autorisation à détailler avant réalisation', 'scope': exact(find('Scope')), 'owner': prototype['owner'],
        'verification': [exact(verification)], 'evidence_requirements': ['Revue du design et essais à produire']})
    obj('TechnicalBinding', 'binding', 'Binding HTTP prévu', {'contract': exact(contract), 'protocol': 'HTTP', 'protocol_version': '1.1',
        'schema_mapping': [{'binding': 'air.http-json-mapping/0.30', 'operation': 'Prepare' + str(i), 'method': 'POST', 'path': '/proposals/' + str(i),
            'request_schema': exact(schema), 'request_required': True, 'response_schema': exact(schema), 'response_status': '202'} for i in range(3)],
        'security_binding': [exact(control)]})
    obj('Workflow', 'workflow', name, {'steps': [{'binding': 'air.workflow-step/0.22', 'id': 's' + str(i), 'name': stage,
        'function': exact(functions[i]), 'participants': [exact(actor)]} for i, stage in enumerate(stages)],
        'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'f' + str(i), 'source': 's' + str(i), 'target': 's' + str(i + 1),
            'condition': 'Qualité et mandat confirmés - condition à formaliser'} for i in range(2)],
        'start_steps': ['s0'], 'termination_policy': 'Fin à la préparation ; aucune application externe exécutée', 'compensations': []})
    return members + added


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output', type=Path, default=ROOT / 'tmp/business-paths-20261002')
    args = parser.parse_args()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated SQLite demo')
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=True)
    home = output / ('registry-' + uuid.uuid4().hex);protect_directory(home)
    settings = Settings(home, 'sqlite:///' + (home / 'air.db').as_posix(), instance_id='paths-demo')
    store = Store(settings.database_url);store.migrate();policy = AccessPolicy()
    token = store.create_token('paths-demo-author', 'admin');user = store.authenticate(token['access_token'], True)
    user['authorization']['instance_id'] = settings.instance_id
    pins, queries = [], []
    try:
        for case in read('manifest.json')['dossiers']:
            members = extend(case, read(case['construction']), store, user, policy, settings)
            members = augment(case['id'], members, store, user, policy, settings)
            store.put_bundle(members, 'fictional-design')
            meta = deepcopy(read(case['construction_baseline_request'])['meta']);meta.update(id='urn:asteria:paths-baseline:' + case['id'].lower(), name=case['title'])
            base = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fictional-design')
            pin = {**exact(base['baseline']), 'digest': base['digest']};pins.append(pin)
            root = next(o for o in members if o['meta']['id'] == 'urn:asteria:paths:' + case['id'].lower() + ':workflow') if case['id'] in TITLES else next(o for o in members if o['meta']['type'] == 'air.Workflow')
            queries.append({'case': case['id'], 'request': {'baselines': [pin], 'start': {'baseline': pin, 'object': exact(root)}}})
        counts = store.counts();results = []
        with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
            headers = {'Authorization': 'Bearer ' + token['access_token']}
            for query in queries:
                request = query['request'];expected = business_paths.query_paths(store, user, policy, request)
                response = client.post('/v1/business-paths/query', json=request, headers=headers)
                assert response.status_code == 200 and response.json() == expected
                mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_query_business_paths', 'arguments': request}},
                    headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL}).json()['result']
                assert not mcp['isError'] and mcp['structuredContent'] == expected
                assert expected == business_paths.query_paths(store, user, policy, request)
                result = expected['result'];assert not result['causality_verified'] and not result['business_execution_performed']
                (output / (query['case'] + '-path.json')).write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                results.append({'case': query['case'], 'name': result['root']['name'], 'status': result['status'], 'nodes': len(result['context_graph']['nodes']),
                                'workflows': len(result['workflows']), 'data_flows': len(result['data_flows']), 'gaps': [g['code'] for g in result['gaps']], 'report_digest': expected['report_digest']})
            assert client.post('/v1/business-paths/query', json=queries[0]['request']).status_code == 401
        assert counts == store.counts()
        for query in queries[:2]:
            specific = 'adresse correspondance' if query['case'] == 'D01' else 'proactive opportunité partenaire'
            found = business_paths.query_paths(store, user, policy, {'baselines': pins, 'query': specific})
            assert found['status'] in ['AMBIGUOUS', 'PARTIAL_DECLARATIONS', 'RESOLVED_DECLARATIONS'] and found.get('candidate_count', 0) > 0
        pack = compile_deliverables(store, user, policy, {'title': 'Asteria - comprendre les parcours de transformation', 'baselines': pins})
        workspace = output / 'project';workspace.mkdir(exist_ok=True)
        plan = plan_files(workspace, pack['files'], previous_generation(workspace, pack['files']));assert not any(x['action'] == 'CONFLICT' for x in plan)
        apply_files(workspace, pack['files'], plan)
        assert all(x['action'] == 'UNCHANGED' for x in plan_files(workspace, pack['files'], previous_generation(workspace, pack['files'])))
        report = {'status': 'PASS_SCOPED', 'scope': 'Declared path queries and static pages, not business execution', 'results': results,
                  'site': pack['website'], 'entrypoint': str(workspace / pack['website']['entrypoint']), 'file_set_digest': pack['file_set_digest'],
                  'gates': pack['gates'], 'sqlite': True, 'http_mcp_parity': True, 'deterministic': True, 'registry_unchanged_by_queries': True,
                  'business_tests_executed': 0, 'original_business_tests_not_executed': 9, 'ci_run': False}
        (output / 'site-demo.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': report['status'], 'results': results, 'entrypoint': report['entrypoint']}, ensure_ascii=False))
    finally: store.engine.dispose()


if __name__ == '__main__': main()
