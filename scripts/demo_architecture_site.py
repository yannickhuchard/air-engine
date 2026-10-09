"""Build a fresh, entirely fictional Asteria project site with three dossiers.

The added designs are declarations, not proof of working business applications.
The original nine business tests and original blocked gates remain unchanged.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid
from air import artifacts
from air.access import AccessPolicy
from air.atelier import apply_files, plan_files, previous_generation
from air.config import Settings, protect_directory
from air.core import DELIVERY_PROFILE, digest
from air.deliverables import compile_deliverables
from air.foundation import exact
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures/enterprise/asteria'
DATA = {
    'D01': ('Demande SAV', 'Adresse de correspondance', 'Recevoir une demande SAV et préparer son traitement, sans décision automatique de garantie.',
            ['Saisir la demande', 'Conserver la proposition', 'Préparer le suivi ERP']),
    'D02': ('Observation machine', 'Proposition d’inspection', 'Préparer une inspection à partir d’une observation qualifiée, sans commander une machine.',
            ['Recevoir l’observation', 'Contrôler sa fraîcheur', 'Proposer une inspection']),
    'D03': ('Demande de changement d’accès', 'Période de validité', 'Préparer un changement de droits sous responsabilité du sponsor, sans activation automatique.',
            ['Recevoir la demande RH', 'Examiner le sponsor', 'Proposer le changement IAM']),
}


def read(path): return json.loads((FIXTURES / path).read_text(encoding='utf-8'))


def extend(case, members, store, user, policy, settings):
    own = [o for o in members if o['meta']['namespace'] != 'asteria.shared']
    find = lambda kind: next(o for o in own if o['meta']['type'] == 'air.' + kind)
    scope, actor, original, contract = (find(k) for k in ('Scope', 'Actor', 'Function', 'SemanticContract'))
    prototype = deepcopy(scope['meta']);code = case['id'];entity_name, related_name, purpose, stages = DATA[code]
    added = []
    def obj(kind, suffix, name, body):
        meta = {**deepcopy(prototype), 'id': 'urn:asteria:site:' + code.lower() + ':' + suffix, 'type': 'air.' + kind,
                'name': name, 'description': 'Design fictif déclaré pour ' + case['title'] + '. ' + name}
        result = {'meta': meta, 'body': body};added.append(result);return result
    authority = obj('AuthorityScope', 'authority', 'Responsabilité de conception', {'principal': prototype['owner'], 'scope': exact(scope),
                    'allowed_decisions': ['Proposer le design'], 'limits': ['Aucune autorité d’exécution métier'], 'delegations': [], 'separation_rules': ['Revue avant réalisation']})
    domain = obj('Domain', 'domain', case['title'], {'purpose': purpose, 'scope': exact(scope), 'authority': exact(authority)})
    concept = obj('Concept', 'concept', entity_name, {'definition': purpose, 'domain': exact(domain), 'semantic_relations': [], 'steward': prototype['owner']})
    related = obj('Concept', 'related', related_name, {'definition': 'Information liée à ' + entity_name + ', avec identité et responsable explicites.', 'domain': exact(domain), 'semantic_relations': [], 'steward': prototype['owner']})
    obj('ConceptRelation', 'relation', 'Relation métier déclarée', {'subject': exact(concept), 'object': exact(related), 'predicate': 'REFERS_TO', 'cardinality': '0..1'})
    data_authority = obj('DataAuthority', 'data-authority', 'Équipe responsable des données', {'data_scope': exact(scope), 'operations': ['Préparer une proposition'],
        'responsible': prototype['owner'], 'writer_policy': 'Écriture sous mandat du système à développer', 'coordination_policy': 'Revue des changements et traçabilité'})
    field = lambda name: {'binding': 'air.field/0.23', 'name': name}
    attributes = [{'binding': 'air.attribute/0.23', 'name': name, 'value_type': kind, 'required': required, 'description': description}
        for name, kind, required, description in [('id', 'Text', True, 'Identité stable de la proposition'), ('occurred_at', 'Instant', True, 'Date de l’information métier'),
                                                 ('status', 'Text', True, 'État déclaré de traitement'), ('related_id', 'Text', False, 'Référence facultative vers ' + related_name)]]
    entity = obj('DataEntity', 'entity', entity_name, {'concept': exact(concept), 'attributes': attributes, 'identity': [field('id')], 'ownership': exact(data_authority), 'constraints': []})
    secondary = obj('DataEntity', 'secondary-entity', related_name, {'concept': exact(related), 'attributes': [
        {'binding': 'air.attribute/0.23', 'name': 'id', 'value_type': 'Text', 'required': True, 'description': 'Identité de ' + related_name},
        {'binding': 'air.attribute/0.23', 'name': 'value', 'value_type': 'Text', 'required': True, 'description': 'Valeur déclarée à préciser avant réalisation'}],
        'identity': [field('id')], 'ownership': exact(data_authority), 'constraints': []})
    raw = json.dumps({'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'additionalProperties': False,
        'properties': {'id': {'type': 'string'}, 'occurred_at': {'type': 'string', 'format': 'date-time'}, 'status': {'type': 'string'}, 'related_id': {'type': 'string'}},
        'required': ['id', 'occurred_at', 'status']}, ensure_ascii=False).encode('utf-8')
    artifact = artifacts.put(store, user, policy, settings, {'namespace': prototype['namespace'], 'idempotency_key': code.lower() + '-schema', 'media_type': 'application/json'}, raw)
    obj('DataSchema', 'schema', 'Schéma de proposition', {'format': 'JSON Schema', 'dialect_version': '2020-12', 'artifact': artifact['artifact_reference'],
        'represents': [exact(entity)], 'compatibility_policy': 'Revue explicite des changements'})
    env = obj('Environment', 'prod', 'Production prévue', {'stage': 'PRODUCTION', 'purpose': 'Exploitation future après réalisation', 'hosting': 'Infrastructure entreprise à préciser'})
    zone = obj('NetworkZone', 'zone', 'Zone interne', {'environment': exact(env), 'trust_level': 'INTERNAL', 'purpose': 'Services du dossier'})
    tech = obj('Technology', 'database-tech', 'PostgreSQL - choix de design', {'category': 'DATABASE', 'version': 'à décider', 'license': 'PostgreSQL', 'status': 'ASSESS'})
    block = obj('ArchitectureBlock', 'block', 'Service de propositions', {'kind': 'MODULE', 'responsibilities': [purpose], 'functions': [exact(original)],
        'provided_contracts': [exact(contract)], 'required_contracts': [], 'owned_state': [exact(entity)]})
    service = obj('RuntimeComponent', 'service', 'Service métier prévu', {'kind': 'SERVICE', 'environment': exact(env), 'zone': exact(zone), 'responsibility': purpose, 'realizes': [exact(block)]})
    db = obj('RuntimeComponent', 'database', 'Stockage des propositions', {'kind': 'DATABASE', 'environment': exact(env), 'zone': exact(zone),
        'responsibility': 'Conserver les propositions et leur identité', 'stores': [exact(entity), exact(secondary)], 'technologies': [exact(tech)]})
    obj('Connection', 'db-link', 'Connexion au stockage', {'source': exact(service), 'target': exact(db), 'protocol': 'TLS', 'port': 5432,
        'encrypted': True, 'authentication': 'Identité de service à spécifier', 'purpose': 'Conserver les propositions'})
    secondary_table = obj('PhysicalTable', 'secondary-table', 'Données liées', {'store': exact(db), 'implements': exact(secondary), 'name': 'related_information',
        'columns': [{'name': 'id', 'type': 'uuid', 'nullable': False, 'primary_key': True}, {'name': 'value', 'type': 'text', 'nullable': False, 'primary_key': False}]})
    obj('PhysicalTable', 'table', 'Propositions', {'store': exact(db), 'implements': exact(entity), 'name': 'proposal', 'columns': [
        {'name': 'id', 'type': 'uuid', 'nullable': False, 'primary_key': True}, {'name': 'occurred_at', 'type': 'timestamp with time zone', 'nullable': False, 'primary_key': False},
        {'name': 'status', 'type': 'text', 'nullable': False, 'primary_key': False}, {'name': 'related_id', 'type': 'uuid', 'nullable': True, 'primary_key': False,
        'references': {'table': exact(secondary_table), 'column': 'id'}}], 'indexes': ['Index sur occurred_at à spécifier selon volumétrie']})
    functions = []
    for i, stage in enumerate(stages):
        body = deepcopy(original['body']);body.update(inputs=[], outputs=[], postconditions=[stage + ' : résultat de conception à vérifier'], effects=[], exceptions=[])
        functions.append(obj('Function', 'step-function-' + str(i), stage, body))
    obj('Workflow', 'workflow', 'Parcours de proposition', {'steps': [{'binding': 'air.workflow-step/0.22', 'id': 's' + str(i), 'name': stage,
        'function': exact(functions[i]), 'participants': [exact(actor)]} for i, stage in enumerate(stages)],
        'flows': [{'binding': 'air.workflow-flow/0.22', 'id': 'f' + str(i), 'source': 's' + str(i), 'target': 's' + str(i+1), 'condition': 'Information recevable - garde non formalisée'} for i in range(2)],
        'start_steps': ['s0'], 'termination_policy': 'Fin à la proposition, pas à l’exécution métier', 'compensations': []})
    journey = obj('CustomerJourney', 'journey', 'Parcours utilisateur', {'persona': exact(actor), 'goal': purpose, 'steps': [
        {'id': 'submit', 'name': stages[0], 'channel': 'WEB' if code == 'D01' else 'BACK_OFFICE', 'touchpoint': 'Interface de proposition',
         'operation': {'contract': exact(contract), 'name': contract['body']['operations'][0]['name']}, 'pain_points': ['Information incomplète ou accès insuffisant']}]})
    ui = obj('RuntimeComponent', 'ui', 'Interface de proposition', {'kind': 'USER_INTERFACE', 'environment': exact(env), 'zone': exact(zone), 'responsibility': 'Préparer et suivre la proposition'})
    obj('NavigationMap', 'navigation', 'Navigation de la proposition', {'application': exact(ui), 'personas': [exact(actor)], 'entry_screens': ['home'], 'screens': [
        {'id': 'home', 'name': 'Vue d’ensemble', 'kind': 'PAGE', 'purpose': 'Comprendre les propositions'},
        {'id': 'form', 'name': 'Préparer la proposition', 'kind': 'PAGE', 'purpose': purpose, 'operations': [{'contract': exact(contract), 'name': contract['body']['operations'][0]['name']}]},
        {'id': 'receipt', 'name': 'Reçu de proposition', 'kind': 'PAGE', 'purpose': 'Suivre sans confondre dépôt et approbation'}],
        'transitions': [{'id': 'open', 'source': 'home', 'target': 'form', 'trigger': 'Nouvelle proposition'}, {'id': 'send', 'source': 'form', 'target': 'receipt', 'trigger': 'Déposer la proposition'}]})
    obj('ValueStream', 'value', 'De l’information à la proposition', {'trigger': stages[0], 'value': purpose, 'stakeholder': exact(actor),
        'stages': [{'id': 'v' + str(i), 'name': stage, 'functions': [exact(functions[i])]} for i, stage in enumerate(stages)]})
    obj('Decision', 'decision', 'Séparer proposition et exécution', {'question': 'AIR doit-il exécuter le changement métier ?',
        'alternatives': ['Produire un plan et une proposition', 'Déclencher directement le système métier'], 'selection': 'Produire un plan et une proposition',
        'rationale': 'Les équipes de réalisation et les responsables habilités gardent la maîtrise de l’implémentation et de l’exécution.', 'basis': [exact(scope)], 'authority': prototype['owner'],
        'consequences': ['Le design ne vaut pas exécution du système conçu.', 'Les équipes doivent implémenter et tester les contrats avant utilisation métier.'],
        'revisit_conditions': ['Une décision habilitée change explicitement le périmètre.']})
    metric = obj('Metric', 'metric', 'Propositions traçables', {'definition': 'Part des propositions reliées à une source et un responsable', 'unit': '1', 'aggregation': 'Ratio déclaré',
        'population': 'Propositions de ce dossier', 'collection_method': 'Contrôle prévu du système à réaliser'})
    goal = obj('Goal', 'goal', 'Traçabilité des propositions', {'outcome': purpose, 'measures': [exact(metric)], 'targets': [
        {'id': 'traceability', 'metric': exact(metric), 'operator': 'EQ', 'value': {'type': 'Decimal', 'value': '1'}, 'unit': '1', 'context': exact(scope)}]})
    obj('Intent', 'intent', 'Intention de transformation', {'desired_change': purpose, 'sponsor': prototype['owner'], 'scope': exact(scope), 'goals': [exact(goal)]})
    return members + added


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output', type=Path, default=ROOT / 'tmp/architecture-site-20261002')
    parser.add_argument('--branding-fixtures', action='store_true', help='Use the three fictional enterprise, consultant and studio identities')
    parser.add_argument('--transformation-fixtures', action='store_true', help='Exercise three linked fictional design projects, one completed, one active and one planned')
    parser.add_argument('--experience-fixtures', action='store_true', help='Three full fictional journey maps with explicit emotion hypotheses and one unknown score')
    args = parser.parse_args()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Unset AIR_DATABASE_URL for the isolated SQLite demo')
    root = args.output.resolve();root.mkdir(parents=True, exist_ok=True)
    home = root / ('registry-' + uuid.uuid4().hex);protect_directory(home)
    settings = Settings(home, 'sqlite:///' + (home / 'air.db').as_posix(), instance_id='site-demo')
    store = Store(settings.database_url);store.migrate();policy = AccessPolicy()
    token = store.create_token('site-demo-author', 'admin');user = store.authenticate(token['access_token'], True)
    user['authorization']['instance_id'] = settings.instance_id
    pins = []
    try:
        previous_members = []; previous_projects = []
        for position, case in enumerate(read('manifest.json')['dossiers']):
            members = extend(case, read(case['construction']), store, user, policy, settings)
            if args.experience_fixtures:
                journey = next(o for o in members if o['meta']['id'].endswith(':journey') and o['meta']['type']=='air.CustomerJourney')
                prototype = deepcopy(journey['body']['steps'][0]); namespace = journey['meta']['namespace']
                runtime = [o for o in members if o['meta']['type']=='air.RuntimeComponent' and o['meta']['namespace']==namespace]
                journey['body'].update(view_state='TO_BE', scenario='Hypothèse fictive de conception, sans recherche utilisateur reçue')
                journey['body']['steps'] = [{**deepcopy(prototype), 'id': 'experience-'+str(i), 'name': stage,
                    'phase': ['Préparer','Examiner','Conclure'][i], 'action': stage,
                    'thoughts': ['Hypothèse à discuter : comprendre le résultat de '+stage.lower()],
                    'frontstage': ['Présenter la proposition et son statut à l’utilisateur'],
                    'backstage': ['Contrôler les données et les droits avant de conserver la proposition'],
                    'support_processes': ['Journaliser la provenance sans activer le système métier'],
                    'systems': [exact(o) for o in runtime], 'opportunities': ['Rendre visible le responsable et la prochaine étape'],
                    'outcome': stage+' : proposition documentée',
                    'emotion': {'status':'UNKNOWN'} if position==1 and i==1 else {'status':'HYPOTHESIS','score':[2,3,4][i],
                        'label':['Incertitude','Attention','Confiance à confirmer'][i], 'rationale':'Proposition de démonstration, pas un entretien ou une mesure'}}
                    for i,stage in enumerate(DATA[case['id']][3])]
            if args.transformation_fixtures:
                own_scope = next(o for o in members if o['meta']['type'] == 'air.Scope' and o['meta']['namespace'] != 'asteria.shared')
                source = next(o for o in members if o['meta']['type'] == 'air.Source')
                proto = deepcopy(own_scope['meta']); root_id = 'urn:asteria:design-work:' + case['id'].lower()
                def declared(kind, suffix, body):
                    return {'meta': {**deepcopy(proto), 'id': root_id + ':' + suffix, 'type': 'air.' + kind,
                        'name': case['title'] + ' : ' + suffix, 'description': 'Déclaration fictive de démonstration, sans réception humaine réelle.'}, 'body': body}
                project_ref = {'id': root_id + ':project', 'revision': 1}
                task = declared('ArchitectureTask', 'task', {'project': project_ref, 'purpose': 'Préparer et relire les plans de ' + case['title'],
                    'owner': proto['owner'], 'kind': 'DOCUMENTATION', 'status': ['DONE', 'BLOCKED', 'TODO'][position], 'depends_on': [],
                    'deliverables': [exact(own_scope)], 'evidence': [exact(source)] if position == 0 else [],
                    **({'closed_at': '2026-10-07T00:00:00Z'} if position == 0 else {})})
                closure = declared('Decision', 'closure', {'question': 'Quelle clôture de conception démontrer ?', 'alternatives': ['Clôture déclarée fictive', 'Conception active'],
                    'selection': 'Clôture déclarée fictive', 'rationale': 'Exercer la règle sans inventer de réception humaine.', 'basis': [exact(own_scope), exact(source)],
                    'authority': proto['owner'], 'consequences': ['Aucun service métier exécuté ; le statut reste une déclaration fictive.'], 'revisit_conditions': ['Nouvelle tâche réelle']})
                p = declared('ArchitectureProject', 'project', {'code': case['id'].lower(), 'scope_kind': 'ARCHITECTURE_DESIGN',
                    'purpose': case['title'], 'scope': exact(own_scope), 'owner': proto['owner'], 'tasks': [exact(task)],
                    'depends_on': [{'project': exact(previous_projects[-1]), 'kind': 'FINISH_TO_START'}] if previous_projects else [],
                    'status': ['COMPLETED', 'ACTIVE', 'PLANNED'][position],
                    **({'closure_decision': exact(closure), 'closed_at': '2026-10-07T00:00:00Z'} if position == 0 else {})})
                pool = {o['meta']['id']: o for o in previous_members + members + [task, p] + ([closure] if position == 0 else [])}
                previous_projects.append(p)
                if position == 2:
                    programme = declared('TransformationProgramme', 'programme', {'purpose': 'Coordonner SAV, atelier et identités au sein d’Asteria',
                        'scope': exact(own_scope), 'owner': proto['owner'], 'projects': [exact(x) for x in previous_projects],
                        'start': '2026-10-01', 'end': '2028-12-31', 'status': 'ACTIVE'})
                    pool[programme['meta']['id']] = programme
                members = list(pool.values()); previous_members = members
            store.put_bundle(members, 'fictional-design')
            meta = deepcopy(read(case['construction_baseline_request'])['meta'])
            meta.update(id='urn:asteria:site-baseline:' + case['id'].lower(), name=case['title'])
            base = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, 'fictional-design')
            pins.append({**exact(base['baseline']), 'digest': base['digest']})
        request = {'title': 'Asteria Industrie - dossiers de transformation', 'baselines': pins}
        if args.transformation_fixtures: request['max_total_bytes'] = 33554432
        if args.branding_fixtures:
            request['branding'] = {'dossiers': [
                {'baseline': pin, 'profile': json.loads((ROOT / 'fixtures/branding' / (name + '.json')).read_text(encoding='utf-8'))['profile']}
                for pin, name in zip(pins, ('enterprise', 'consultant', 'studio'))]}
        result = compile_deliverables(store, user, policy, request)
        if args.transformation_fixtures:
            graph = json.loads(next(f['content'] for f in result['files'] if f['path'] == 'livrables/site/transformation.json'))
            assert graph['totals'] == {'programmes': 1, 'projects': 3, 'tasks': 3, 'active_tasks': 2, 'done_tasks': 1, 'cancelled_tasks': 0}
            assert not graph['gaps'] and not graph['completion_attested'] and graph['declared_work_status'] == 'ACTIVE'
            assert sum(e['relation'] == 'DEPENDS_ON_FINISH_TO_START' for e in graph['edges']) == 2
        assert result['file_set_digest'] == compile_deliverables(store, user, policy, {**request, 'content': 'DIGESTS'})['file_set_digest']
        workspace = root / 'project';workspace.mkdir(exist_ok=True)
        previous = previous_generation(workspace, result['files'])
        plan = plan_files(workspace, result['files'], previous);assert not any(x['action'] == 'CONFLICT' for x in plan)
        apply_files(workspace, result['files'], plan)
        assert all(x['action'] == 'UNCHANGED' for x in plan_files(workspace, result['files'], previous_generation(workspace, result['files'])))
        report = {'status': 'PASS_SCOPED', 'scope': 'Declared designs and static site; no business execution', 'sqlite': True,
                  'site': result['website'], 'entrypoint': str(workspace / result['website']['entrypoint']), 'files': len(result['files']),
                  'total_size': result['total_size'], 'file_set_digest': result['file_set_digest'], 'gates': result['gates'],
                  'deterministic': True, 'regeneration_unchanged': True, 'business_execution_performed': False, 'business_tests_executed': 0,
                  'original_business_tests_not_executed': 9}
        (root / 'site-demo.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': report['status'], 'dossiers': 3, 'diagrams': result['website']['diagrams'], 'entrypoint': report['entrypoint']}))
    finally: store.engine.dispose()


if __name__ == '__main__': main()
