"""Exact architecture dossier: declared structure, structural checks, and nothing executed or contacted."""
from collections import defaultdict
from air import artifacts
from air.access import ScopedStore
from air.architecture_schema import messaging
from air.core import digest, record
from air.data_validation import parse_external, structured_issues, STRUCTURED, DataInputError
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.packages import reference
from air.projections import SNAPSHOT, snapshot

ENGINE = 'air.architecture-dossier/0.31'
CHECKS = 'air.architecture-checks/0.31'
REQUEST = record({'baseline': SNAPSHOT, 'detail': {'enum': ['FULL', 'SUMMARY']}}, ['baseline'])
NOT_CHECKED = [
    'Bounded-context membership of a block, contract and data authority is a naming convention, not a declared link',
    'A command changing only the aggregates of its own context: no declared function-to-entity write',
    'Context-map relationship kinds (customer/supplier, conformist, anti-corruption layer, shared kernel)',
    'Behaviour, authorisation, performance and the truth of any declaration',
]
# Each check belongs to one family, named after the design principle it makes structural.
FAMILIES = {
    'EXCLUSIVITY': {'principle': 'MECE — mutually exclusive: one exposer per function, one owner per aggregate, one provider per contract',
                    'codes': ['AIR_ARCH_FUNCTION_EXPOSED_TWICE', 'AIR_ARCH_OPERATION_NAME_REUSED', 'AIR_ARCH_ENTITY_OWNED_TWICE', 'AIR_ARCH_CONTRACT_PROVIDED_TWICE']},
    'EXHAUSTIVENESS': {'principle': 'MECE — collectively exhaustive: every MUST requirement satisfied, every function realised and exposed, every required contract provided',
                       'codes': ['AIR_ARCH_REQUIREMENT_UNSATISFIED', 'AIR_ARCH_FUNCTION_UNREALISED', 'AIR_ARCH_REQUIRED_CONTRACT_UNPROVIDED',
                                 'AIR_ARCH_ENTITY_UNOWNED', 'AIR_ARCH_CONTRACT_UNPROVIDED', 'AIR_ARCH_FUNCTION_NOT_EXPOSED']},
    'CONTEXT_COHERENCE': {'principle': 'DDD — a block stays within one data authority (bounded context) and an event is published by the owner of its aggregate',
                          'codes': ['AIR_ARCH_BLOCK_SPANS_CONTEXTS', 'AIR_ARCH_EVENT_PUBLISHER']},
    'COMPILABILITY': {'principle': 'Declared schemas stay inside the compilation subset so that a standard description can be produced',
                      'codes': ['AIR_ARCH_SCHEMA_OUTSIDE_SUBSET']},
    'DECLARATION': {'principle': 'What a reviewer or an agent needs declared: the roles allowed per operation, a channel for every event',
                    'codes': ['AIR_ARCH_OPERATION_ROLES_UNDECLARED', 'AIR_ARCH_EVENT_WITHOUT_CHANNEL', 'AIR_ARCH_EVENT_UNCONSUMED']},
    'SCOPE': {'principle': 'Checks apply to the objects the baseline owns', 'codes': ['AIR_ARCH_NOTHING_OWNED']},
}
FAMILY_OF = {code: family for family, value in FAMILIES.items() for code in value['codes']}


def _schema_report(store, principal, policy, index, refs, cache):
    """Validate the declared schema artifacts of a binding against the compilation subset, before any compilation.

    One artifact is read once per inspection, however many mappings reference it.
    """
    checked, issues = [], []
    for ref in sorted({key(r): r for r in refs}.values(), key=lambda r: (r['id'], r['revision'])):
        schema_obj = index.get(key(ref))
        if not schema_obj or schema_obj['meta']['type'] != 'air.DataSchema': continue
        descriptor = schema_obj['body']['artifact']
        cache_key = (descriptor['locator'], descriptor['digest']['value'])
        if cache_key not in cache:
            cache[cache_key] = _read_schema(store, principal, policy, descriptor)
        status, rows, truncated = cache[cache_key]
        entry = {'schema': {**exact(schema_obj), 'digest': digest(schema_obj)}, 'name': schema_obj['meta']['name'], 'status': status}
        if status in ('IN_SUBSET', 'OUTSIDE_SUBSET'): entry.update(issues=rows, issues_truncated=truncated)
        checked.append(entry)
        if status != 'IN_SUBSET': issues.append(entry)
    return checked, issues


def _read_schema(store, principal, policy, descriptor):
    manifest = store.get_record(descriptor['locator'])
    if not manifest or manifest['kind'] != 'artifact_manifest': return 'ARTIFACT_UNAVAILABLE', [], False
    lookup = {'artifact': reference(manifest)}
    try:
        meta = artifacts.describe(store, principal, policy, lookup)
        raw = artifacts.download(store, principal, policy, lookup)[1]
        parsed = parse_external(raw)
    except (InvalidModel, DataInputError, ValueError):
        return 'ARTIFACT_UNREADABLE', [], False
    if meta['artifact_reference'] != descriptor: return 'DESCRIPTOR_DIFFERS', [], False
    rows, truncated = structured_issues(parsed)
    return ('OUTSIDE_SUBSET' if rows else 'IN_SUBSET'), rows, truncated


def inspect_objects(store, principal, policy, objects, home, detail='FULL'):
    """The structural report over any exact object set: a stored baseline or a candidate of drafts."""
    objects = sorted(objects, key=lambda o: key(exact(o)));index = {key(exact(o)): o for o in objects}
    owned = lambda obj: obj['meta']['namespace'] == home
    names = {'air.ArchitectureBlock': 'blocks', 'air.Port': 'ports', 'air.TechnicalBinding': 'bindings', 'air.DataFlow': 'flows',
             'air.RequiredOutput': 'required_outputs', 'air.ArchitectureGap': 'gaps'}
    report = {'engine': ENGINE, 'namespace': home, 'detail': detail, **{name: [] for name in names.values()},
        'endpoints_contacted': False, 'security_verified': False, 'transformations_executed': False, 'behavioral_compatibility_verified': False,
        'outputs_constructed': False, 'authorization_granted': False, 'model_updated': False}
    violations, observations, cache = [], [], {}

    def note(rows, code, message, **detail_fields): rows.append({'code': code, 'family': FAMILY_OF[code], 'message': message, **detail_fields})

    for obj in objects:
        kind = obj['meta']['type']
        if kind not in names: continue
        item = {'reference': {**exact(obj), 'digest': digest(obj)}, 'name': obj['meta']['name'], 'lifecycle': obj['meta']['lifecycle'],
                'namespace': obj['meta']['namespace'], 'owned': owned(obj)}
        if detail == 'FULL': item['declaration'] = obj['body']
        if kind == 'air.TechnicalBinding':
            body = obj['body'];contract = index.get(key(body['contract']))
            if messaging(body):
                declared = {key(e['event']) for e in body['channel_mapping']}
                carried = {key(exact(o)) for o in objects if o['meta']['type'] == 'air.Event'
                           and 'delivery_contract' in o['body'] and contract is not None and key(o['body']['delivery_contract']) == key(exact(contract))}
                item['transport'] = 'MESSAGING'
                item['channel_coverage'] = {'channels': sorted({e['channel'] for e in body['channel_mapping']}),
                    'events_mapped': sorted(i for i, _ in declared), 'events_without_channel': sorted(i for i, _ in carried - declared),
                    'complete': not (carried - declared)}
                schema_refs = [e['message_schema'] for e in body['channel_mapping']]
            else:
                declared_ops = {op['name'] for op in contract['body']['operations']} if contract and contract['meta']['type'] == 'air.SemanticContract' else set()
                mapped = {m['operation'] for m in body['schema_mapping']}
                item['transport'] = 'HTTP'
                item['operation_coverage'] = {'mapped': sorted(mapped), 'unmapped': sorted(declared_ops - mapped), 'complete': mapped == declared_ops}
                declared_errors = {f['code'] for f in contract['body']['error_contract']} if contract and contract['meta']['type'] == 'air.SemanticContract' else set()
                mapped_errors = {f['code'] for m in body['schema_mapping'] for f in m.get('errors', [])}
                item['error_coverage'] = {'mapped': sorted(mapped_errors), 'unmapped': sorted(declared_errors - mapped_errors), 'complete': declared_errors == mapped_errors}
                item['mapping_bindings'] = sorted({m['binding'] for m in body['schema_mapping']})
                item['operation_authorization'] = [{'operation': m['operation'], 'roles': m.get('authorization_roles', []),
                                                    'declared': 'authorization_roles' in m} for m in sorted(body['schema_mapping'], key=lambda m: m['operation'])]
                schema_refs = [m[field] for m in body['schema_mapping'] for field in ('request_schema', 'response_schema') if field in m]
                schema_refs += [f['response_schema'] for m in body['schema_mapping'] for f in m.get('errors', [])]
            checked, issues = _schema_report(store, principal, policy, index, schema_refs, cache)
            item['schemas_checked'] = checked if detail == 'FULL' else len(checked)
            item['schema_artifacts_validated'] = bool(checked) and not issues
            item['schema_subset'] = STRUCTURED
            if issues:
                note(violations, 'AIR_ARCH_SCHEMA_OUTSIDE_SUBSET', 'Declared schemas are outside ' + STRUCTURED + '; no description can be compiled',
                     binding=item['reference'], schemas=[{'schema': e['schema'], 'name': e['name'], 'status': e['status']} for e in issues])
        if kind == 'air.ArchitectureBlock':
            item['ports'] = [exact(p) for p in objects if p['meta']['type'] == 'air.Port' and key(p['body']['block']) == key(exact(obj))]
            if detail == 'SUMMARY':
                item['responsibilities'] = obj['body']['responsibilities']
        if kind == 'air.ArchitectureGap' and detail == 'SUMMARY':
            item.update(missing_element_kind=obj['body']['missing_element_kind'], impact=obj['body']['impact'],
                        resolution_owner=obj['body']['resolution_owner'])
        report[names[kind]].append(item)

    # structural exclusivity and exhaustiveness over the objects this baseline owns
    contracts = [o for o in objects if o['meta']['type'] == 'air.SemanticContract']
    blocks = [o for o in objects if o['meta']['type'] == 'air.ArchitectureBlock']
    exposure, operation_names, providers, realizers, owners = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for contract in contracts:
        for op in contract['body']['operations']:
            exposure[key(op['function'])].append({'contract': exact(contract), 'operation': op['name']})
            operation_names[op['name']].append(exact(contract))
    for block in blocks:
        for ref in block['body']['provided_contracts']: providers[key(ref)].append(exact(block))
        for ref in block['body']['functions']: realizers[key(ref)].append(exact(block))
        for ref in block['body']['owned_state']: owners[key(ref)].append(exact(block))
    for function_key, where in sorted(exposure.items()):
        if len(where) > 1 and function_key in index and owned(index[function_key]):
            note(violations, 'AIR_ARCH_FUNCTION_EXPOSED_TWICE', 'A function is exposed by more than one contract',
                 function={'id': function_key[0], 'revision': function_key[1]}, exposed_by=where)
    for name, where in sorted(operation_names.items()):
        if len({(c['id'], c['revision']) for c in where}) > 1 and any(owned(index[key(c)]) for c in where if key(c) in index):
            note(violations, 'AIR_ARCH_OPERATION_NAME_REUSED', 'An operation name is declared by more than one contract', operation=name, contracts=where)
    for entity in [o for o in objects if o['meta']['type'] == 'air.DataEntity' and owned(o)]:
        holders = owners[key(exact(entity))]
        if len(holders) > 1:
            note(violations, 'AIR_ARCH_ENTITY_OWNED_TWICE', 'An aggregate is owned by more than one block', entity=exact(entity), blocks=holders)
        elif not holders:
            note(observations, 'AIR_ARCH_ENTITY_UNOWNED', 'An aggregate is owned by no block of this baseline', entity=exact(entity))
    for contract in [o for o in contracts if owned(o)]:
        holders = providers[key(exact(contract))]
        if len(holders) > 1:
            note(violations, 'AIR_ARCH_CONTRACT_PROVIDED_TWICE', 'A contract is provided by more than one block', contract=exact(contract), blocks=holders)
        elif not holders:
            note(observations, 'AIR_ARCH_CONTRACT_UNPROVIDED', 'A contract of this baseline is provided by no block', contract=exact(contract))
    satisfied = defaultdict(list)
    for function in [o for o in objects if o['meta']['type'] == 'air.Function']:
        for ref in function['body']['satisfies']: satisfied[key(ref)].append(exact(function))
        if owned(function) and not realizers[key(exact(function))]:
            note(violations, 'AIR_ARCH_FUNCTION_UNREALISED', 'A function of this baseline belongs to no block', function=exact(function))
        if owned(function) and not exposure[key(exact(function))]:
            note(observations, 'AIR_ARCH_FUNCTION_NOT_EXPOSED', 'A function is realised by a block without being exposed by a contract', function=exact(function))
    for requirement in [o for o in objects if o['meta']['type'] == 'air.Requirement' and owned(o)]:
        if requirement['body']['kind'] == 'FUNCTIONAL' and requirement['body']['priority'] == 'MUST' and not satisfied[key(exact(requirement))]:
            note(violations, 'AIR_ARCH_REQUIREMENT_UNSATISFIED', 'A mandatory functional requirement is satisfied by no function', requirement=exact(requirement))
    dependencies = []
    for block in blocks:
        for ref in block['body']['required_contracts']:
            holders = providers[key(ref)]
            target = index.get(key(ref))
            entry = {'block': exact(block), 'contract': {'id': ref['id'], 'revision': ref['revision']},
                     'namespace': target['meta']['namespace'] if target else None, 'provided_in_baseline': bool(holders)}
            dependencies.append(entry)
            if not holders and target is not None and owned(target) and owned(block):
                note(violations, 'AIR_ARCH_REQUIRED_CONTRACT_UNPROVIDED', 'A required contract of this baseline is provided by no block', **entry)
        authorities = {index[key(e)]['body']['ownership']['id'] for e in block['body']['owned_state'] if key(e) in index}
        if len(authorities) > 1 and owned(block):
            note(violations, 'AIR_ARCH_BLOCK_SPANS_CONTEXTS', 'A block owns aggregates of more than one data authority', block=exact(block), authorities=sorted(authorities))
    for event in [o for o in objects if o['meta']['type'] == 'air.Event' and owned(o)]:
        payload = index.get(key(event['body']['payload_schema']))
        publishers = {(b['id'], b['revision']) for b in providers.get(key(event['body']['delivery_contract']), [])} if 'delivery_contract' in event['body'] else set()
        entity_owners = {(b['id'], b['revision']) for ref in (payload['body']['represents'] if payload else []) for b in owners[key(ref)]}
        if publishers and entity_owners and not publishers & entity_owners:
            note(violations, 'AIR_ARCH_EVENT_PUBLISHER', 'An event is delivered by a contract whose block does not own the aggregate its payload represents',
                 event=exact(event), publishers=[{'id': i, 'revision': r} for i, r in sorted(publishers)], owners=[{'id': i, 'revision': r} for i, r in sorted(entity_owners)])
    for binding in [o for o in objects if o['meta']['type'] == 'air.TechnicalBinding' and owned(o) and not messaging(o['body'])]:
        missing = sorted(m['operation'] for m in binding['body']['schema_mapping'] if not m.get('authorization_roles'))
        if missing:
            note(observations, 'AIR_ARCH_OPERATION_ROLES_UNDECLARED', 'Operations declare no authorization roles (air.http-json-mapping/0.30 authorization_roles)',
                 binding=exact(binding), operations=missing)
    channelled = {key(e['event']) for o in objects if o['meta']['type'] == 'air.TechnicalBinding' and messaging(o['body']) for e in o['body']['channel_mapping']}
    silent = sorted((exact(o) for o in objects if o['meta']['type'] == 'air.Event' and owned(o) and key(exact(o)) not in channelled), key=key)
    if silent:
        note(observations, 'AIR_ARCH_EVENT_WITHOUT_CHANNEL', 'Events of this baseline are carried by no message channel', events=silent)
    # Published but subscribed by nobody in the baseline: either a consumer is missing, or the consumer lives outside the dossier.
    actions = defaultdict(set)
    for o in objects:
        if o['meta']['type'] == 'air.TechnicalBinding' and messaging(o['body']):
            for e in o['body']['channel_mapping']: actions[key(e['event'])].add(e['action'])
    unconsumed = sorted((exact(o) for o in objects if o['meta']['type'] == 'air.Event' and owned(o)
                         and 'PUBLISH' in actions.get(key(exact(o)), set()) and 'SUBSCRIBE' not in actions.get(key(exact(o)), set())), key=key)
    if unconsumed:
        note(observations, 'AIR_ARCH_EVENT_UNCONSUMED', 'Events are published but no binding of the baseline subscribes to them: '
             'declare the consumer, or record that it lives outside this dossier', events=unconsumed)
    referenced = defaultdict(int)
    for obj in objects:
        if not owned(obj): referenced[obj['meta']['namespace']] += 1
    owned_count = sum(1 for o in objects if owned(o))
    if not owned_count:
        note(observations, 'AIR_ARCH_NOTHING_OWNED', 'The baseline namespace owns none of its members, so no structural check applied; '
             'inspect the baseline of the project that owns them', namespace=home, namespaces_present=sorted(referenced))
    report['scope'] = {'owned_objects': owned_count,
                       'referenced_objects': [{'namespace': ns, 'objects': count} for ns, count in sorted(referenced.items())]}
    report['dependencies'] = sorted(dependencies, key=lambda d: (d['block']['id'], d['contract']['id']))
    families = {name: {'principle': value['principle'], 'violations': sum(1 for v in violations if v['family'] == name),
                       'observations': sum(1 for o in observations if o['family'] == name)}
                for name, value in FAMILIES.items() if name != 'SCOPE'}
    result = 'NOTHING_OWNED' if not owned_count else 'VIOLATIONS_FOUND' if violations else 'NO_STRUCTURAL_VIOLATION'
    report['checks'] = {'binding': CHECKS, 'result': result, 'families': families, 'violations': violations, 'observations': observations,
                        'not_checked': NOT_CHECKED}
    return report


def inspect_architecture(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Architecture context exceeds its budget') from exc
    report = inspect_objects(store, principal, policy, exported['objects'], exported['baseline']['meta']['namespace'], request.get('detail', 'FULL'))
    report = {'engine': ENGINE, 'baseline': request['baseline'], **report}
    report['request_digest'] = artifact_digest(request);report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Architecture report exceeds its budget') from exc
    return report
