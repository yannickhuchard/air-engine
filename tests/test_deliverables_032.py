"""Tranche 32: the implementation team's deliverables, compiled from pinned baselines and citing their sources."""
import json
import pytest
from air import deliverables
from air.foundation import exact
from test_architecture import find
from test_delivery_032 import POLICY, delivery, frozen, obj  # noqa: F401  (fixture re-export)


def pack(example, members):
    scope = find(members, 'Scope');actor = find(members, 'Actor')
    contract = find(members, 'SemanticContract');blocks = [o for o in members if o['meta']['type'] == 'air.ArchitectureBlock']
    authority = obj(example, 'AuthorityScope', 'authority', {'principal': 'urn:person:sponsor', 'scope': exact(scope),
        'allowed_decisions': ['Approve the build'], 'limits': ['Budget ceiling'], 'delegations': [], 'separation_rules': ['Independent review']})
    competency = [{'binding': 'air.skill-requirement/0.21', 'competency': 'Delivery', 'minimum_level': 'Senior', 'assessment_method': 'Interview'}]
    lead = obj(example, 'Role', 'delivery-lead', {'responsibilities': ['Own the plan'], 'required_competencies': competency, 'authority': exact(authority)})
    dev = obj(example, 'Role', 'developer', {'responsibilities': ['Build units'], 'required_competencies': competency, 'authority': exact(authority)})
    sre = obj(example, 'Role', 'sre', {'responsibilities': ['Run production'], 'required_competencies': competency, 'authority': exact(authority)})
    programme = obj(example, 'OrganizationUnit', 'programme', {'mandate': 'Deliver the platform', 'roles': [exact(lead)]})
    squad = obj(example, 'OrganizationUnit', 'squad', {'mandate': 'Build claims', 'parent': exact(programme), 'roles': [exact(dev)]})
    run = obj(example, 'OrganizationUnit', 'run', {'mandate': 'Operate the platform', 'roles': [exact(sre)]})
    raci = [obj(example, 'RaciAssignment', 'raci-' + name, {'activity': activity, 'phase': phase, 'role': exact(role), 'responsibility': letter})
            for name, activity, phase, role, letter in (('a', 'Approve release', 'DELIVERY', lead, 'A'), ('b', 'Approve release', 'DELIVERY', dev, 'R'),
                                                        ('c', 'Handle incident', 'OPERATIONS', sre, 'A'))]
    environments = {stage: obj(example, 'Environment', stage.lower(), {'stage': stage, 'purpose': stage + ' purpose', 'hosting': 'EU cloud'})
                    for stage in ('BUILD_TEST', 'RELEASE', 'PRODUCTION')}
    prod = environments['PRODUCTION']
    dmz = obj(example, 'NetworkZone', 'dmz', {'environment': exact(prod), 'trust_level': 'DMZ', 'purpose': 'Edge'})
    restricted = obj(example, 'NetworkZone', 'restricted', {'environment': exact(prod), 'trust_level': 'RESTRICTED', 'purpose': 'Claims data'})
    tech = obj(example, 'Technology', 'postgres', {'category': 'DATABASE', 'version': '17', 'license': 'PostgreSQL', 'status': 'ADOPT'})
    gateway = obj(example, 'RuntimeComponent', 'gateway', {'kind': 'GATEWAY', 'environment': exact(prod), 'zone': exact(dmz), 'responsibility': 'Edge',
                                                           'realizes': [exact(blocks[1])]})
    database = obj(example, 'RuntimeComponent', 'database', {'kind': 'DATABASE', 'environment': exact(prod), 'zone': exact(restricted),
                                                             'responsibility': 'Claims store', 'realizes': [exact(blocks[0])], 'technologies': [exact(tech)]})
    link = obj(example, 'Connection', 'gateway-db', {'source': exact(gateway), 'target': exact(database), 'protocol': 'TLS', 'port': 5432,
                                                     'encrypted': True, 'authentication': 'mTLS', 'purpose': 'Persist claims'})
    table = obj(example, 'PhysicalTable', 'claim-table', {'store': exact(database), 'name': 'claim', 'columns': [
        {'name': 'id', 'type': 'uuid', 'nullable': False, 'primary_key': True}, {'name': 'amount', 'type': 'numeric(12,2)', 'nullable': False, 'primary_key': False}]})
    capex = obj(example, 'CostItem', 'build', {'nature': 'CAPEX', 'category': 'LABOUR', 'amount': {'value': '120000', 'currency': 'EUR'}, 'recurrence': 'ONCE',
                                               'start': '2027-01', 'basis': '200 person days', 'confidence': 'MEDIUM'})
    opex = obj(example, 'CostItem', 'hosting', {'nature': 'OPEX', 'category': 'INFRASTRUCTURE', 'amount': {'value': '1000', 'currency': 'EUR'},
                                                'recurrence': 'MONTHLY', 'start': '2027-07', 'end': '2028-06', 'basis': 'Cloud quote', 'confidence': 'HIGH'})
    milestone = obj(example, 'Milestone', 'go-live', {'target_date': '2027-07-01', 'exit_criteria': ['Ready-to-build gate MET']})
    stream = obj(example, 'ValueStream', 'claim-to-payment', {'trigger': 'A member claims', 'value': 'The member is paid', 'stakeholder': exact(actor),
        'stages': [{'id': 'claim', 'name': 'Claim'}, {'id': 'pay', 'name': 'Pay', 'lead_time': '48 h'}]})
    journey = obj(example, 'CustomerJourney', 'submit-claim', {'persona': exact(actor), 'goal': 'Be reimbursed', 'steps': [
        {'id': 'open', 'name': 'Open the app', 'channel': 'MOBILE', 'touchpoint': 'Home screen'},
        {'id': 'send', 'name': 'Send the claim', 'channel': 'MOBILE', 'touchpoint': 'Claim form', 'operation': {'contract': exact(contract), 'name': 'Submit'},
         'pain_points': ['Photo upload fails']}]})
    principle = obj(example, 'ArchitecturePrinciple', 'api-first', {'statement': 'Every capability is an API', 'rationale': 'Reuse', 'implications': ['Contracts first']})
    portal = obj(example, 'RuntimeComponent', 'portal', {'kind': 'USER_INTERFACE', 'environment': exact(prod), 'zone': exact(dmz), 'responsibility': 'Member portal'})
    navigation = obj(example, 'NavigationMap', 'portal-navigation', {'application': exact(portal), 'personas': [exact(actor)], 'entry_screens': ['home'],
        'screens': [{'id': 'home', 'name': 'Home', 'kind': 'PAGE', 'purpose': 'Start a claim'},
                    {'id': 'claim-form', 'name': 'Claim form', 'kind': 'WIZARD_STEP', 'purpose': 'Enter the claim', 'roles': [exact(dev)],
                     'operations': [{'contract': exact(contract), 'name': 'Submit'}]}],
        'transitions': [{'id': 'start', 'source': 'home', 'target': 'claim-form', 'trigger': 'New claim'}]})
    nodes = obj(example, 'Device', 'node-pool', {'kind': 'NODE_POOL', 'environment': exact(prod), 'zone': exact(dmz), 'location': 'EU region, two zones',
        'quantity': 3, 'owner': 'SRE', 'provider': 'Cloud', 'status': 'PLANNED', 'hosts': [exact(gateway), exact(portal)],
        'specification': {'cpu_cores': 8, 'memory_gib': 32, 'operating_system': 'Linux'}})
    return [authority, lead, dev, sre, programme, squad, run, *raci, *environments.values(), dmz, restricted, tech, gateway, database, link, table,
            capex, opex, milestone, stream, journey, principle, portal, navigation, nodes]


@pytest.fixture
def compiled(store, example, delivery):
    members, user, baseline, extra = delivery
    added = pack(example, members);store.put_bundle(added, 'fixture')
    pinned = frozen(store, example, members + added, 'urn:delivery:pack')
    request = {'title': 'Claims platform', 'baselines': [pinned], 'implementation_root': 'urn:delivery:programme', 'operations_root': 'urn:delivery:run'}
    return deliverables.compile_deliverables(store, user, POLICY, request), request, user


def test_every_deliverable_is_compiled_with_its_sources(compiled):
    report, request, user = compiled
    files = {f['path']: f for f in report['files']}
    assert 'livrables/site/index.html' in files and 'livrables/architecture-model.json' in files
    assert 'livrables/README.md' in files and 'livrables/00-presentation-direction.html' in files and 'livrables/manifest.json' in files
    for name, _ in deliverables.CATALOGUE:
        content = files['livrables/' + name + '.md']['content']
        assert content.startswith('# ') and '## Sources' in content, name
    assert not report['registry_written'] and not report['authorization_granted']
    assert json.loads(files['livrables/manifest.json']['content'])['gates'][0]['result'] == 'NOT_READY'
    readme = files['livrables/README.md']['content']
    assert 'NOT_READY' in readme and 'INDEPENDENT_REVIEW' in readme and 'signature' in readme


def test_the_pack_answers_who_decides_what_it_costs_and_where_it_runs(compiled):
    report, request, user = compiled
    text = {f['path'].split('/')[-1][:-3]: f['content'] for f in report['files']}
    organisation = text['06-organisation-realisation-raci']
    assert '| Approve release | delivery-lead |' in organisation and 'flowchart TD' in organisation
    assert '| Handle incident | sre |' in text['07-organisation-exploitation']
    finance = text['17-plan-financier']
    assert '| 2027 | EUR | 120 000 | 6 000 | 126 000 |' in finance and '| 2028 | EUR | 0 | 6 000 | 6 000 |' in finance
    security = text['22-securite-zones']
    assert 'DMZ · dmz' in security and '🔒 mTLS' in security
    assert 'erDiagram' in text['20-modele-physique'] and 'uuid id PK' in text['20-modele-physique']
    assert '```mermaid' in text['04-processus-metier'] and '(score ≥ 50)' in text['04-processus-metier']
    assert 'gantt' in text['27-planning-jalons'] and 'Photo upload fails' in text['03-parcours-clients']
    assert 'Aucun composant déclaré pour BUILD_TEST' in text['08-architectures-systeme']
    assert '| postgres | DATABASE | 17 |' in text['26-registre-technologies']


def test_the_pack_is_deterministic_and_can_be_checked_by_digest(store, compiled):
    report, request, user = compiled
    again = deliverables.compile_deliverables(store, user, POLICY, {**request, 'content': 'DIGESTS'})
    assert again['file_set_digest'] == report['file_set_digest'] and all('content' not in f for f in again['files'])


def test_a_regenerated_pack_replaces_its_own_files_and_keeps_hand_edits(tmp_path, compiled):
    from air.atelier import apply_files, plan_files, previous_generation
    report, request, user = compiled
    files = report['files']
    apply_files(tmp_path, files, plan_files(tmp_path, files, previous_generation(tmp_path, files)))
    edited = tmp_path / 'livrables' / '16-risques.md'
    edited.write_text(edited.read_text(encoding='utf-8') + '\nNote manuelle\n', encoding='utf-8')
    changed = [dict(f) for f in files]
    for f in changed:
        if f['path'].endswith(('05-roles.md', '16-risques.md')):
            f['content'] = f['content'] + '\n'
            import hashlib
            f['content_digest'] = 'sha256:' + hashlib.sha256(f['content'].encode('utf-8')).hexdigest();f['size'] = len(f['content'].encode('utf-8'))
    actions = {s['path']: s['action'] for s in plan_files(tmp_path, changed, previous_generation(tmp_path, changed))}
    assert actions['livrables/16-risques.md'] == 'CONFLICT', 'a hand edit is never overwritten silently'
    assert actions['livrables/05-roles.md'] != 'CONFLICT', 'a file this generation wrote is refreshed'


def test_events_navigation_and_devices_are_delivered(compiled):
    report, request, user = compiled
    text = {f['path'].split('/')[-1][:-3]: f['content'] for f in report['files']}
    navigation = text['30-navigation-interfaces']
    assert 'Claim form' in navigation and '"New claim"' in navigation and 'Submit' in navigation
    devices = text['31-equipements-machines']
    assert 'node-pool × 3 · NODE_POOL' in devices and '8 vCPU, 32 Gio RAM, Linux' in devices and '- database' in devices, 'an unplaced component is named'
    assert '## Événements sans canal' in text['29-evenements']


def test_navigation_and_devices_are_checked(example, delivery):
    from air.core import DELIVERY_PROFILE, validate
    from air.foundation import validate_graph
    members, user, baseline, extra = delivery
    added = pack(example, members)
    navigation = next(o for o in added if o['meta']['type'] == 'air.NavigationMap')
    lost = json.loads(json.dumps(navigation));lost['body']['screens'].append({'id': 'orphan', 'name': 'Orphan', 'kind': 'DIALOG', 'purpose': 'Nobody comes here'})
    assert 'AIR_NAVIGATION_UNREACHABLE' in {d['code'] for d in validate([lost])['diagnostics']}
    wrong = json.loads(json.dumps(navigation));wrong['body']['screens'][1]['operations'][0]['name'] = 'Teleport'
    graph = validate_graph(members + [o for o in added if o is not navigation] + [wrong], DELIVERY_PROFILE)['diagnostics']
    assert any(d['code'] == 'AIR_NAVIGATION_OPERATION' and 'Teleport' in d['message'] for d in graph)
