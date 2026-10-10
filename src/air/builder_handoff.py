"""Versioned design handoffs and authenticated role receipts, without launch authority."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import select
from air.access import ScopedStore, Forbidden
from air.atelier import product
from air.core import TEXT, INSTANT, record, digest
from air.expr import artifact_digest
from air.foundation import InvalidModel, TooLarge, check_schema, key
from air.projections import SNAPSHOT, snapshot
from air.reviews import record_key
from air.packages import RECORD_REF, identifier, lock_registry, reference
from air.storage import Conflict, service_records
from air import site_handoff

ENGINE = 'air.builder-handoff/1'
ID = {'type': 'string', 'format': 'uri', 'minLength': 1, 'maxLength': 512}
KEY = {'type': 'string', 'minLength': 1, 'maxLength': 128}
COMPILE = record({'package_id': ID, 'version': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647},
    'baseline': SNAPSHOT, 'units': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
    'title': {**TEXT, 'maxLength': 256}, 'content': {'enum': ['FULL', 'DIGESTS']}}, ['package_id', 'version', 'baseline', 'units'])
CREATE = deepcopy(COMPILE); CREATE['properties']['idempotency_key'] = KEY
CREATE['required'].append('idempotency_key'); CREATE['properties'].pop('content')
READ = record({'package': RECORD_REF, 'baseline': SNAPSHOT})
ASSESS = record({'baseline': SNAPSHOT})
RECEIVE = record({'idempotency_key': KEY, 'package': RECORD_REF, 'role': SNAPSHOT,
    'outcome': {'enum': ['ACCEPTED', 'CHANGES_REQUESTED']}, 'rationale': TEXT,
    'questions': {'type': 'array', 'items': TEXT, 'maxItems': 64, 'uniqueItems': True}, 'expires_at': INSTANT})
REVOKE = record({'receipt': RECORD_REF, 'rationale': TEXT})
LIMITS = ['Acceptance of this design scope for build planning only',
    'No independent review, test execution, financial commitment, runtime delivery or deployment authority',
    'Static export reflects receipt state at generation time; refresh after changes',
    'Closed model included; retained external artifacts remain in the authorized AIR registry']


def pin(obj):
    return {**{f: obj['meta'][f] for f in ('id', 'revision')}, 'digest': digest(obj)}


def load(store, principal, policy, baseline):
    exported = snapshot(ScopedStore(store, principal, policy), baseline)
    if len(exported['objects']) > 1000: raise TooLarge('Builder handoff supports at most 1000 baseline objects')
    if len(json.dumps(exported, ensure_ascii=False).encode('utf-8')) > 32 * 1024 * 1024:
        raise TooLarge('Builder snapshot exceeds 32 MiB')
    return exported


def compile_package(store, principal, policy, request):
    check_schema(request, COMPILE)
    exported = load(store, principal, policy, request['baseline'])
    namespace = exported['baseline']['meta']['namespace']
    index = {key(o['meta']): o for o in exported['objects']}
    if len({r['id'] for r in request['units']}) != len(request['units']):
        raise InvalidModel('Select one exact revision per construction unit')
    for ref in request['units']:
        obj = index.get(key(ref))
        if not obj or obj['meta']['type'] != 'air.ConstructionUnit' or pin(obj) != ref or obj['meta']['namespace'] != namespace:
            raise InvalidModel('Units must be exact owned ConstructionUnit members of this baseline')
    projection = site_handoff.project(exported, {'result': 'NOT_ASSESSED'})
    packets = [p for p in projection['packets'] if p['target'] in request['units']]
    responsibilities, gaps = [], []
    for packet in packets:
        unit = index[key(packet['target'])]
        # These checks concern transmission, not execution of the planned cases.
        for code in ('CONSTRUCTION_UNIT', 'ACCEPTANCE', 'CRITERION_CASES', 'VERIFICATION', 'UNRESOLVED_REFERENCE'):
            for gap in packet['gaps']:
                if gap['code'] == code: gaps.append({'unit': packet['target'], **gap})
        if not unit['body']['realizes']:
            gaps.append({'unit': packet['target'], 'code': 'REALIZATION', 'label': 'Aucun objet à réaliser'})
        if not unit['body']['acceptance']:
            gaps.append({'unit': packet['target'], 'code': 'UNIT_ACCEPTANCE', 'label': 'Critères propres à cette unité non déclarés'})
        for duty in ('R', 'A'):
            assignments = [o for o in exported['objects'] if o['meta']['type'] == 'air.RaciAssignment'
                and o['body'].get('subject') == {'id': packet['target']['id'], 'revision': packet['target']['revision']}
                and o['body']['phase'] == 'DELIVERY' and o['body']['responsibility'] == duty]
            if not assignments:
                gaps.append({'unit': packet['target'], 'code': 'DELIVERY_' + duty, 'label': 'Responsabilité ' + duty + ' sur cette unité non déclarée'})
            for assignment in assignments:
                role = index[key(assignment['body']['role'])]
                teams = [o for o in exported['objects'] if o['meta']['type'] == 'air.OrganizationUnit' and
                    assignment['body']['role'] in o['body'].get('roles', [])]
                if len(teams) != 1:
                    gaps.append({'unit': packet['target'], 'code': 'ROLE_TEAM', 'label': 'Le rôle doit appartenir à une équipe explicite unique', 'role': pin(role)})
                else:
                    responsibilities.append({'unit': packet['target'], 'role': pin(role), 'team': pin(teams[0]),
                        'duty': duty, 'assignment': pin(assignment), 'role_name': role['meta']['name'], 'team_name': teams[0]['meta']['name']})
    # Embed only contract suites associated with the selected units or their blocks.
    from air.interface_contracts import compile_suite
    contract_keys = {key(r) for p in packets for r in p['sections']['contracts']
        if index[key(r)]['meta']['type'] == 'air.SemanticContract'}
    function_keys = {key(r) for p in packets for r in p['sections']['design']
        if index[key(r)]['meta']['type'] == 'air.Function'}
    architecture_context = [o for o in exported['objects'] if o['meta']['type'] == 'air.ArchitectureBlock'
        and any(key(ref) in function_keys for ref in o['body']['functions'])]
    contract_keys.update(key(ref) for o in architecture_context for field in ('provided_contracts', 'required_contracts')
        for ref in o['body'][field])
    contract_keys.update(key(o['meta']) for o in exported['objects'] if o['meta']['type'] == 'air.SemanticContract'
        and any(key(op['function']) in function_keys for op in o['body']['operations']))
    suites = []
    for obj in exported['objects']:
        if obj['meta']['type'] == 'air.InterfaceSpecification' and key(obj['body']['contract']) in contract_keys:
            suite = compile_suite(store, principal, policy, {'baseline': request['baseline'], 'specification': pin(obj)})
            if suite['result'] != 'PASS_DESIGN_EXAMPLES':
                gaps.append({'code': 'INTERFACE_EXAMPLES', 'label': 'Exemples de contrat non vérifiés', 'specification': pin(obj)})
            suites.append(suite)
    for contract_key in sorted(contract_keys):
        if not any(key(s['contract']) == contract_key for s in (index[key(v['specification'])]['body'] for v in suites)):
            gaps.append({'code': 'INTERFACE_SPECIFICATION', 'label': 'Spécification de construction du contrat absente', 'contract': pin(index[contract_key])})
    manifest = {'engine': ENGINE, 'package_id': request['package_id'], 'version': request['version'],
        'title': request.get('title', 'Paquet de construction'),
        'baseline': request['baseline'], 'namespace': namespace, 'units': sorted(request['units'], key=key),
        'packets': packets, 'contracts': [pin(index[k]) for k in sorted(contract_keys)],
        'architecture_context': [pin(o) for o in architecture_context],
        'responsibilities': sorted(responsibilities, key=lambda r: (key(r['unit']), r['duty'], key(r['role']))),
        'global_context': [pin(o) for o in exported['objects'] if o['meta']['type'] in
            ('air.Risk', 'air.Unknown', 'air.Assertion', 'air.Decision', 'air.Control')],
        'gaps': gaps, 'state': 'DRAFT_WITH_GAPS' if gaps else 'AWAITING_RECEIPTS',
        'authorization_granted': False, 'limits': LIMITS}
    manifest['manifest_digest'] = artifact_digest(manifest)
    payloads = [('handoff-manifest.json', 'application/json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'),
        ('architecture-snapshot.json', 'application/json', json.dumps(exported, ensure_ascii=False, indent=2) + '\n'),
        ('README.md', 'text/markdown', '# Paquet de construction\n\n'
            'Lire handoff-manifest.json : périmètre exact, responsabilités, sections et questions.\n'
            'architecture-snapshot.json conserve le modèle fermé et ses références originales.\n'
            'Les suites contracts/ contiennent les exemples et leurs vérificateurs.\n'
            'Les critères et cas sont des plans : leur présence ne signifie pas qu’ils ont été exécutés.\n'
            'Les risques et décisions globaux sont du contexte, sans affectation implicite à cette unité.\n'
            'Les artefacts originaux conservés dans AIR ne sont pas copiés automatiquement.\n'
            'La réception se fait avec une identité mandatée via handoff-receive, jamais dans ce fichier.\n')]
    for suite in suites:
        folder = artifact_digest(suite['specification']).split(':')[1][:16]
        payloads.extend(('contracts/' + folder + '/' + f['path'], f['media_type'], f['content']) for f in suite['files'])
    files = [product(path, media, data, 'GENERATED', 32 * 1024 * 1024) for path, media, data in payloads]
    if sum(f['size'] for f in files) > 48 * 1024 * 1024: raise TooLarge('Builder package exceeds 48 MiB')
    if request.get('content') == 'DIGESTS':
        for f in files: f.pop('content')
    return {'engine': ENGINE, 'manifest': manifest, 'files': files, 'registry_written': False, 'authorization_granted': False}


def commit_guard(store, conn, principal, policy, settings):
    lock_registry(conn)
    if settings is not None:
        from air.jobs import check_identity
        from air.access import AccessPolicy
        check_identity(store, conn, principal, settings)
        if AccessPolicy.load(settings.home).digest != policy.digest: raise Forbidden('Handoff policy changed before commit')


def create_package(store, principal, policy, request, settings=None):
    check_schema(request, CREATE)
    normalized = deepcopy(request); normalized['units'].sort(key=key)
    report = compile_package(store, principal, policy, {k: v for k, v in normalized.items() if k != 'idempotency_key'})
    manifest = report['manifest']; scope = manifest['namespace']
    policy.require(principal, 'write', scope)
    package_id = identifier('builder-package', request['package_id'], request['version'])
    retry_id = record_key('builder-command', principal['subject'], request['idempotency_key'])
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        retry = store._get_record(conn, retry_id)
        if retry and retry['payload']['request'] != normalized: raise Conflict('Handoff idempotency key was reused')
        prior = store._get_record(conn, package_id)
        if prior and prior['payload']['manifest'] != manifest: raise Conflict('Handoff version already has another immutable scope')
        result = store._record_once(conn, package_id, 'builder_package', scope, principal['subject'], {'manifest': manifest})
        store._record_once(conn, retry_id, 'builder_command', scope, principal['subject'], {'request': normalized, 'package': reference(result['record'])})
    return {'package': reference(result['record']), 'created': result['created'], 'manifest': manifest, 'authorization_granted': False}


def required(store, principal, policy, ref, kind):
    row = store.get_record(ref['id'])
    if not row or row['kind'] != kind: raise InvalidModel('Handoff record unavailable')
    policy.require(principal, 'read', row['scope'])
    if reference(row) != ref: raise Conflict('Handoff record digest differs')
    return row


def role_mandate(principal, policy, namespace, role):
    policy.require(principal, 'receive', namespace)
    if not policy.document or role not in policy.document['subjects'].get(principal['subject'], {}).get('builder_roles', []):
        raise Forbidden('Authenticated subject has no mandate for this exact builder role')


def receive(store, principal, policy, request, settings=None):
    check_schema(request, RECEIVE)
    package = required(store, principal, policy, request['package'], 'builder_package')
    manifest = package['payload']['manifest']
    load(store, principal, policy, manifest['baseline'])
    if request['role'] not in [r['role'] for r in manifest['responsibilities']]:
        raise InvalidModel('Receipt role is not a responsibility of this package')
    role_mandate(principal, policy, package['scope'], request['role'])
    if request['outcome'] == 'ACCEPTED' and (request['questions'] or manifest['gaps']):
        raise InvalidModel('Acceptance requires no open questions and no blocking handoff gaps')
    if request['outcome'] == 'CHANGES_REQUESTED' and not request['questions']:
        raise InvalidModel('Changes requested must identify at least one question')
    receipt_id = record_key('builder-receipt', principal['subject'], request['idempotency_key'])
    payload = {'request': deepcopy(request), 'policy_digest': policy.digest, 'actor_role': principal['role'], 'authorization_granted': False}
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        if store._get_record(conn, receipt_id) is None:
            expiry = datetime.fromisoformat(request['expires_at']); now = datetime.now(timezone.utc)
            if not now < expiry <= now + timedelta(days=366): raise InvalidModel('Receipt expires in the next 366 days')
        result = store._record_once(conn, receipt_id, 'builder_receipt', package['scope'], principal['subject'], payload)
    return {'receipt': reference(result['record']), 'created': result['created'], 'authorization_granted': False}


def receipt_state(store, policy, row):
    payload = row['payload']; request = payload['request']; reasons = []
    if store.get_record(identifier('builder-revoked', row['id'])): reasons.append('REVOKED')
    if datetime.fromisoformat(request['expires_at']) <= datetime.now(timezone.utc): reasons.append('EXPIRED')
    if payload['policy_digest'] != policy.digest: reasons.append('POLICY_CHANGED')
    try: role_mandate({'subject': row['actor'], 'role': payload['actor_role']}, policy, row['scope'], request['role'])
    except Forbidden: reasons.append('MANDATE_MISSING')
    return {'receipt': reference(row), 'actor': row['actor'], 'role': request['role'], 'outcome': request['outcome'],
        'rationale': request['rationale'], 'questions': request['questions'], 'recorded_at': row['created_at'],
        'effective': not reasons, 'ineffective_reasons': reasons}


def rows(store, kind, scope):
    with store.engine.connect() as conn:
        ids = conn.execute(select(service_records.c.id).where(service_records.c.kind == kind,
            service_records.c.scope == scope).order_by(service_records.c.id).limit(2001)).scalars().all()
    if len(ids) > 2000: raise TooLarge('Handoff record catalogue exceeds 2000 entries; no partial acceptance is reported')
    return [store.get_record(i) for i in ids]


def read_package(store, principal, policy, request):
    check_schema(request, READ)
    row = required(store, principal, policy, request['package'], 'builder_package')
    manifest = row['payload']['manifest']
    load(store, principal, policy, manifest['baseline']); load(store, principal, policy, request['baseline'])
    current = manifest['baseline'] == request['baseline']
    receipts = [receipt_state(store, policy, r) for r in rows(store, 'builder_receipt', row['scope'])
        if r['payload']['request']['package'] == request['package']]
    role_states = []
    for role in sorted({key(r['role']): r['role'] for r in manifest['responsibilities']}.values(), key=key):
        history = [r for r in receipts if r['role'] == role]
        # Same-microsecond decisions may disagree. Never infer acceptance from ordering or a convenient PASS.
        effective = [r for r in history if r['effective']]
        state = 'MISSING' if not effective else 'CHANGES_REQUESTED' if any(r['outcome'] == 'CHANGES_REQUESTED' for r in effective) else 'ACCEPTED'
        role_states.append({'role': role, 'state': state, 'receipts': history})
    state = 'BASELINE_CHANGED' if not current else 'DRAFT_WITH_GAPS' if manifest['gaps'] else 'CHANGES_REQUESTED' if any(r['state'] == 'CHANGES_REQUESTED' for r in role_states) else 'RECEIVED_FOR_BUILD_PLANNING' if role_states and all(r['state'] == 'ACCEPTED' for r in role_states) else 'AWAITING_RECEIPTS'
    return {'engine': ENGINE, 'package': request['package'], 'manifest': manifest, 'requested_baseline': request['baseline'],
        'state': state, 'roles': role_states, 'authorization_granted': False, 'limits': LIMITS}


def revoke(store, principal, policy, request, settings=None):
    check_schema(request, REVOKE)
    row = required(store, principal, policy, request['receipt'], 'builder_receipt')
    role_mandate(principal, policy, row['scope'], row['payload']['request']['role'])
    if row['actor'] != principal['subject']: raise Forbidden('Only the receiver may withdraw this receipt')
    load(store, principal, policy, required(store, principal, policy, row['payload']['request']['package'], 'builder_package')['payload']['manifest']['baseline'])
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        result = store._record_once(conn, identifier('builder-revoked', row['id']), 'builder_revocation', row['scope'], principal['subject'], request)
    return {'revocation': reference(result['record']), 'created': result['created'], 'authorization_granted': False}


def assess(store, principal, policy, request):
    check_schema(request, ASSESS)
    exported = load(store, principal, policy, request['baseline'])
    scope = exported['baseline']['meta']['namespace']
    packages = [read_package(store, principal, policy, {'package': reference(row), 'baseline': request['baseline']})
        for row in rows(store, 'builder_package', scope) if row['payload']['manifest']['baseline'] == request['baseline']]
    latest = {}
    for package in packages:
        manifest = package['manifest']
        latest[manifest['package_id']] = max(latest.get(manifest['package_id'], 0), manifest['version'])
    for package in packages:
        package['superseded'] = package['manifest']['version'] < latest[package['manifest']['package_id']]
    current = [p for p in packages if not p['superseded']]
    selected = {key(unit) for p in current for unit in p['manifest']['units']}
    missing = [pin(o) for o in exported['objects'] if o['meta']['type'] == 'air.ConstructionUnit' and
        o['meta']['namespace'] == scope and key(o['meta']) not in selected]
    return {'engine': ENGINE, 'baseline': request['baseline'], 'packages': packages, 'units_without_package': missing,
        'state': 'NO_PACKAGES' if not current else 'RECEIVED_FOR_BUILD_PLANNING' if not missing and all(p['state'] == 'RECEIVED_FOR_BUILD_PLANNING' for p in current) else 'INCOMPLETE',
        'authorization_granted': False, 'limits': LIMITS}
