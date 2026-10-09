"""Guided agent path: find the current state, prepare a change safely, and know what to do next.

Every service here is read-only for the registry. Validation and rebase work on drafts that are not stored;
the deposit and the freeze stay explicit calls, so a human sees the complete change before it is recorded.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from air import artifacts
from air.access import Forbidden, NotFound, ScopedStore
from air.core import (CONSTRUCTION_PROFILE, DATA_TYPES, PROFILE_TYPES, TYPES, URI, digest, infer_profile, record,
                      reference_slots, schema, validate)
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import InvalidModel, TooLarge, check_schema, exact, key, validate_graph
from air.packages import reference as manifest_reference
from air.projections import SNAPSHOT

ENGINE = 'air.agent-path/0.31'
DIGEST = {'type': 'string', 'pattern': '^sha256:[a-f0-9]{64}$'}
POINTER = record({'id': URI, 'revision': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647}, 'digest': DIGEST}, ['id'])
DRAFTS = {'type': 'array', 'items': {'type': 'object'}, 'minItems': 1, 'maxItems': 1000}
REVISIONS_REQUEST = record({'id': URI})
PROFILE_CHOICE = {'enum': sorted(PROFILE_TYPES)}
VALIDATE_REQUEST = record({'objects': DRAFTS, 'base': SNAPSHOT, 'profile': PROFILE_CHOICE,
                           'prepared_change': {'type': 'string', 'pattern': '^urn:air:prepared-change:[a-f0-9]{64}$'}}, [])
REBASE_REQUEST = record({'base': SNAPSHOT, 'objects': {**DRAFTS, 'minItems': 0}, 'realign_borrowed': {'type': 'boolean'}, 'profile': PROFILE_CHOICE,
                         'include_bundle': {'type': 'boolean'}}, ['base'])
BROWSE_REQUEST = record({
    'baseline': POINTER, 'types': {'type': 'array', 'items': {'enum': DATA_TYPES}, 'maxItems': 64, 'uniqueItems': True},
    'ids': {'type': 'array', 'items': URI, 'maxItems': 200, 'uniqueItems': True},
    'namespace': {'type': 'string', 'pattern': '^[a-z][a-z0-9_.-]{0,127}$'}, 'owned_only': {'type': 'boolean'},
    'text': {'type': 'string', 'minLength': 1, 'maxLength': 128}, 'fields': {'enum': ['OUTLINE', 'FULL']},
    'offset': {'type': 'integer', 'minimum': 0, 'maximum': 100000}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
    'schemas': {'type': 'boolean'}}, ['baseline'])
TYPE_REQUEST = record({'type': {'enum': DATA_TYPES}})
PREPARED = {'type': 'string', 'pattern': '^urn:air:prepared-change:[a-f0-9]{64}$'}
DEPOSIT_REQUEST = record({'prepared_change': PREPARED})
FREEZE_REQUEST = record({'prepared_change': PREPARED, 'name': {'type': 'string', 'minLength': 1, 'maxLength': 500},
                         'description': {'type': 'string', 'minLength': 1, 'maxLength': 10000}}, ['prepared_change'])
EXPRESSION_LANGUAGE = {
    'language': 'AIR-Expr 0.1',
    'expression': {'required_inputs': [{'name': '<input>', 'type': '<Boolean | Integer | Decimal | Text | Collection[...]>'}],
                   'result_type': 'Boolean', 'ast': '<node>'},
    'nodes': {'literal': {'literal': {'type': 'Integer', 'value': 30}}, 'reference': {'ref': '<input name>'},
              'operator': {'op': '<operator>', 'args': ['<node>', '<node>']},
              'quantifier': {'op': 'every | some', 'over': '<collection node>', 'predicate': '<Boolean node over $item>'}},
    'operators': {'not': 1, 'length': 1, 'and': 2, 'or': 2, 'eq': 2, 'ne': 2, 'lt': 2, 'lte': 2, 'gt': 2, 'gte': 2, 'in': 2,
                  'add': 2, 'sub': 2, 'mul': 2, 'div': 2},
    'notes': ['Every operator takes exactly its arity: "a and b and c" nests as and(a, and(b, c)).',
              'lte and gte exist: 30 >= days is gte(30, days) or lte(days, 30).']}
INTENTS = ['ORIENT', 'CHANGE', 'REVIEW', 'IMPACT', 'DELIVER']
GUIDE_REQUEST = record({'baseline': POINTER, 'intent': {'enum': INTENTS}}, ['baseline'])
OUTPUT_MAX = 400000
SCHEMA_INLINE_MAX = 65536

# Plain explanations of the diagnostics an architect meets most, with the change that removes them.
EXPLAIN = {
    'AIR_CONTRACT_EFFECTS': ('An operation changes state in a way its contract does not promise.',
                             'Copy the listed function effects into the contract state_effects.'),
    'AIR_CONTRACT_ERRORS': ('An operation can fail in a way its contract does not declare.',
                            'Add the listed failure modes to the contract error_contract.'),
    'AIR_FUNCTION_CONTRACT': ('A function is not exposed by any contract of the baseline.',
                              'Expose it as an operation of a contract. An internal function, such as an event consumer, cannot be declared internal yet: the diagnostic stays and is reported as such.'),
    'AIR_FUNCTION_REALIZATION': ('No construction unit realises this function or its contract.',
                                 'Add the function or contract to a ConstructionUnit realizes list.'),
    'AIR_REQUIRED_REALIZATION': ('A mandatory requirement has no complete chain requirement, function, contract, unit.',
                                 'Satisfy it with a function that is exposed by a contract and realised by a unit.'),
    'AIR_UNIT_JUSTIFICATION': ('A construction unit is justified by a requirement that none of its functions satisfies.',
                               'Point the justification at a requirement its functions satisfy, or add the function.'),
    'AIR_UNIT_OPERATIONS': ('A construction unit realises a contract without realising all of its operations.',
                            'List every operation function of the contract in the unit.'),
    'AIR_UNIT_ACCEPTANCE': ('A construction unit omits an acceptance criterion of a requirement it realises.',
                            'Add the criterion to the unit acceptance.'),
    'AIR_REQUIREMENT_VERIFICATION': ('An acceptance criterion has no verification case on the realisation chain.',
                                     'Add a VerificationCase targeting the function or contract.'),
    'AIR_ACCEPTANCE_CASES': ('An acceptance criterion has no verification case.', 'Add at least one VerificationCase.'),
    'AIR_ACCEPTANCE_METHOD': ('A criterion and its verification case use different methods.', 'Align the verification methods.'),
    'AIR_ESTIMATE_TARGET': ('An estimate targets another revision of its unit.', 'Point the estimate at the exact unit revision.'),
    'AIR_REFERENCE_MISSING': ('An exact reference points to a revision that is not in the set.',
                              'Add that revision to the bundle or baseline, or rebase the referencing object.'),
    'AIR_REFERENCE_NOT_LATEST': ('An exact reference points to an older revision than the latest one available.',
                                 'Use air_rebase_drafts to move references to the new revision, or keep the pin on purpose.'),
}
# What an agent can do next after a refusal; the refusal itself stays authoritative.
HINTS = {
    'AIR_NOT_FOUND': 'The exact revision does not exist. Call air_list_revisions with the id to see existing revisions and the latest one.',
    'AIR_FORBIDDEN': 'Read or write access is missing for the listed references, or they do not exist in a readable namespace. Report it; do not work around it.',
    'AIR_REVISION_CONFLICT': 'That revision already exists with different content, or a digest differs. Call air_list_revisions and use latest+1, or re-read the object.',
    'AIR_INVALID_MODEL': 'Read the diagnostics: each names the object and field. Run air_validate_drafts before depositing and air_describe_type for the expected shape.',
    'AIR_INVALID': 'Read the diagnostics: each names the object and field. Run air_validate_drafts before depositing and air_describe_type for the expected shape.',
    'AIR_OUTPUT_TOO_LARGE': 'The request is valid but its answer exceeds a budget named in the message: narrow it (filters, limit, detail SUMMARY, content DIGESTS) or split it.',
    'AIR_POLICY_UNAVAILABLE': 'The access policy of the instance cannot be loaded; an administrator must fix it.',
    'AIR_STORAGE_UNAVAILABLE': 'The registry storage is unavailable; retry later and report it.',
    'AIR_UNREACHABLE': 'The AIR server does not answer: ask the human to start it for this home and check the port in .mcp.json or .codex/config.toml.',
}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


# ---------------------------------------------------------------- errors an agent can act on

STATUS_CODES = {404: 'AIR_NOT_FOUND', 403: 'AIR_FORBIDDEN', 409: 'AIR_REVISION_CONFLICT', 422: 'AIR_INVALID_MODEL', 503: 'AIR_STORAGE_UNAVAILABLE'}
DETAIL_FIELDS = ('id', 'revision', 'type', 'latest_revision', 'unavailable_references')
ERROR_MAX = 65536


def _error(code, status, message=None, report=None, detail=None):
    result = {'error': code, 'http_status': status}
    if isinstance(message, str): result['message'] = message[:500]
    for field in DETAIL_FIELDS:
        if isinstance(detail, dict) and field in detail: result[field] = detail[field]
    if isinstance(report, dict):
        rows = report.get('diagnostics') if isinstance(report.get('diagnostics'), list) else []
        result['diagnostics'] = rows[:50];result['diagnostics_total'] = len(rows)
        for field in ('unresolved_references', 'schemas'):
            if isinstance(report.get(field), list): result[field] = report[field][:50]
    result['hint'] = HINTS.get(code, 'Report the refusal and its cause to the architect.')
    while len(json.dumps(result, ensure_ascii=False)) > ERROR_MAX and result.get('diagnostics'):
        result['diagnostics'] = result['diagnostics'][:len(result['diagnostics']) // 2]
    return result


def relay_http_error(status, body):
    """The structured part of an AIR API refusal; anything that is not AIR's own coded detail is dropped."""
    detail = body.get('detail') if isinstance(body, dict) else None
    if isinstance(detail, dict) and isinstance(detail.get('code'), str) and detail['code'].startswith('AIR_') and len(detail['code']) <= 64:
        return _error(detail['code'], status, detail.get('message'), detail.get('report'), detail)
    return _error(STATUS_CODES.get(status, 'AIR_API_REJECTED'), status)


def error_from_exception(exc):
    from air.storage import Conflict
    from air.quotas import QuotaExceeded
    if isinstance(exc, QuotaExceeded): return _error('AIR_QUOTA_EXCEEDED', 429, str(exc))
    if isinstance(exc, NotFound): return _error('AIR_NOT_FOUND', 404, str(exc), None, exc.detail)
    if isinstance(exc, Forbidden): return _error('AIR_FORBIDDEN', 403, str(exc), None, {'unavailable_references': exc.unavailable})
    if isinstance(exc, Conflict): return _error('AIR_REVISION_CONFLICT', 409, str(exc))
    from air.foundation import TooLarge
    return _error('AIR_OUTPUT_TOO_LARGE' if isinstance(exc, TooLarge) else 'AIR_INVALID_MODEL', 422, str(exc), getattr(exc, 'report', None))


def _bounded(report, label):
    try: bounded(report)
    except ExprError as exc: raise TooLarge(label + ' exceeds its budget; narrow the request') from exc
    return report


# ---------------------------------------------------------------- revisions

def list_revisions(store, principal, policy, request):
    check_schema(request, REVISIONS_REQUEST)
    head = store.head(request['id'])
    if head is None:
        raise NotFound('No object has this identifier', {'id': request['id']})
    policy.require(principal, 'read', head['namespace'])
    rows, total = store.revisions(request['id'])
    items = [{'revision': r['revision'], 'digest': r['digest'], 'stored_at': r['stored_at']} for r in rows]
    if head['type'] == 'air.Baseline':
        reviews = store.reviews_of(request['id'], head['namespace'])
        for item in items[:20]:
            obj = store.get(request['id'], item['revision'])['object']
            item.update(name=obj['meta']['name'], description=obj['meta']['description'][:500], recorded_at=obj['meta']['recorded_at'], members=len(obj['body']['members']),
                        profile=obj['body']['profiles'][0], parent_baselines=obj['body']['parent_baselines'],
                        recorded_by=obj['meta']['provenance']['recorded_by'], method=obj['meta']['provenance']['method'][:300],
                        reviews=[r for r in reviews if r['revision'] == item['revision'] and r['digest'] == item['digest']])
    return {'engine': ENGINE, 'id': request['id'], 'type': head['type'], 'namespace': head['namespace'], 'count': total,
            'latest': items[0] if items else None, 'revisions': items, 'truncated': total > len(items),
            'use': 'Pass {id, revision, digest} of the latest item wherever an exact baseline snapshot is required.',
            'review_note': 'reviews lists authenticated review receipts of each baseline revision (revoked ones marked); a review grants no admission, which stays a separate human act.'}


def resolve_pointer(store, principal, policy, pointer):
    """{id, revision?, digest?} to an exact snapshot; the latest readable revision when none is given."""
    if 'revision' in pointer:
        row = store.get(pointer['id'], pointer['revision'])
        if row is None: raise ScopedStore(store, principal, policy).missing(pointer['id'], pointer['revision'])
    else:
        head = store.head(pointer['id'])
        if head is None: raise NotFound('No object has this identifier', {'id': pointer['id']})
        policy.require(principal, 'read', head['namespace'])
        row = store.get(pointer['id'], head['latest_revision'])
    if row['object']['meta']['type'] != 'air.Baseline':
        raise InvalidModel('The pointer names a ' + row['object']['meta']['type'] + ', not a baseline')
    snapshot = {'id': pointer['id'], 'revision': row['object']['meta']['revision'], 'digest': row['digest']}
    if pointer.get('digest') and pointer['digest'] != snapshot['digest']:
        from air.storage import Conflict
        raise Conflict('Baseline digest differs from the pointer')
    exported = ScopedStore(store, principal, policy).export_baseline(snapshot)
    head = store.head(pointer['id'])
    return snapshot, exported, head['latest_revision']


# ---------------------------------------------------------------- drafts

def _walk_refs(value, visit, path=''):
    """Every {id, revision[, type, digest]} mapping in a JSON tree, including expression literals."""
    if isinstance(value, dict):
        if isinstance(value.get('id'), str) and isinstance(value.get('revision'), int) and set(value) <= {'id', 'revision', 'type', 'digest', 'direction'}:
            visit(value, path)
        for field, item in value.items():
            _walk_refs(item, visit, path + '/' + field)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_refs(item, visit, path + '/' + str(index))


def _storage_status(store, policy, principal, obj, heads):
    meta = obj['meta'];head = heads.get(meta['id'])
    status = {'id': meta['id'], 'revision': meta['revision'], 'type': meta['type'], 'namespace': meta['namespace'],
              'writable': policy.allows(principal, 'write', meta['namespace'])}
    if head is None:
        status['storage'] = 'NEW_IDENTITY'
    elif head['namespace'] != meta['namespace'] or head['type'] != meta['type']:
        status.update(storage='IDENTITY_CONFLICT', stored_namespace=head['namespace'], stored_type=head['type'])
    else:
        stored = store.get(meta['id'], meta['revision'])
        if stored is not None:
            status['storage'] = 'UNCHANGED' if stored['digest'] == digest(obj) else 'REVISION_CONFLICT'
        elif meta['revision'] <= head['latest_revision']:
            status['storage'] = 'REVISION_NOT_AFTER_LATEST'
        else:
            status['storage'] = 'NEW_REVISION'
        status['latest_stored_revision'] = head['latest_revision']
    return status


def _diag_key(row):
    return (row.get('code'), row.get('path'), row.get('operation'), json.dumps(row.get('missing'), sort_keys=True))


def _construction(objects, profile):
    from air.construction import validate_construction
    if not set(PROFILE_TYPES[CONSTRUCTION_PROFILE]) <= set(PROFILE_TYPES.get(profile, [])): return None
    return validate_construction(objects, profile)


def _compare(before, after):
    old = {_diag_key(r): r for r in (before or [])};new = {_diag_key(r): r for r in (after or [])}
    return [new[k] for k in sorted(new.keys() - old.keys(), key=str)], [old[k] for k in sorted(old.keys() - new.keys(), key=str)]


def _owner(row, namespaces, home):
    """THIS_PROJECT when the diagnostic concerns an object of the baseline namespace, OTHER_PROJECT otherwise."""
    refs = []
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('id'), str) and 'revision' in value: refs.append(value['id'])
            else:
                for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit({k: v for k, v in row.items() if k not in ('missing_state_effects', 'missing_failure_modes')})
    head = str(row.get('path', '')).split('#')[0].split('/')[0]
    if head: refs.insert(0, head)
    for ref in refs:
        if ref in namespaces: return 'THIS_PROJECT' if namespaces[ref] == home else 'OTHER_PROJECT'
    return 'UNKNOWN'


def _delta(store, principal, policy, before_objects, after_objects, home, profile):
    from air.architecture import inspect_objects
    namespaces = {o['meta']['id']: o['meta']['namespace'] for o in list(before_objects) + list(after_objects)}
    before_arch = inspect_objects(store, principal, policy, before_objects, home, 'SUMMARY')['checks']
    after_arch = inspect_objects(store, principal, policy, after_objects, home, 'SUMMARY')['checks']
    introduced, resolved = _compare(before_arch['violations'] + before_arch['observations'], after_arch['violations'] + after_arch['observations'])
    tag = lambda rows: [{**r, 'owner': _owner(r, namespaces, home)} for r in rows[:50]]
    delta = {'architecture': {'result': after_arch['result'], 'families': after_arch['families'], 'introduced': tag(introduced), 'resolved': resolved[:50]}}
    before_c, after_c = _construction(before_objects, profile), _construction(after_objects, profile)
    if before_c is not None and after_c is not None:
        introduced_c, resolved_c = _compare(before_c['diagnostics'], after_c['diagnostics'])
        rows = tag([_explained(d) for d in introduced_c])
        delta['construction'] = {'diagnostics_before': len(before_c['diagnostics']), 'diagnostics_after': len(after_c['diagnostics']),
                                 'introduced': rows, 'resolved': resolved_c[:50],
                                 'introduced_by_owner': dict(Counter(r['owner'] for r in rows))}
    return delta


def _target_profile(exported, requested):
    current = exported['baseline']['body']['profiles'][0]
    if not requested or requested == current: return current
    if not set(PROFILE_TYPES[current]) <= set(PROFILE_TYPES[requested]):
        raise InvalidModel('Profile ' + requested + ' does not contain every type of ' + current)
    return requested


def _candidate(store, principal, policy, base_snapshot, objects):
    """Base members with drafts applied: same identity replaced, new identity added."""
    exported = ScopedStore(store, principal, policy).export_baseline(base_snapshot)
    if exported['digest'] != base_snapshot['digest']:
        from air.storage import Conflict
        raise Conflict('Base baseline digest differs')
    members = {o['meta']['id']: o for o in exported['objects']}
    for obj in objects: members[obj['meta']['id']] = obj
    return exported, list(members.values())


def _stale_dependents(members, drafts):
    """Members that still point at an older revision of an identity the drafts replace."""
    replaced = {o['meta']['id']: o['meta']['revision'] for o in drafts}
    stale = []
    for obj in members:
        if obj['meta']['id'] in replaced: continue
        hits = []
        _walk_refs(obj['body'], lambda ref, path: hits.append({'path': 'body' + path, 'target': {'id': ref['id'], 'revision': ref['revision']},
                                                             'now': replaced[ref['id']]})
                   if ref['id'] in replaced and ref['revision'] < replaced[ref['id']] else None)
        _walk_refs(obj['meta']['provenance'], lambda ref, path: hits.append({'path': 'meta/provenance' + path, 'target': {'id': ref['id'], 'revision': ref['revision']},
                                                                          'now': replaced[ref['id']]})
                   if ref['id'] in replaced and ref['revision'] < replaced[ref['id']] else None)
        if hits: stale.append({'object': {**exact(obj), 'type': obj['meta']['type']}, 'references': hits})
    return stale


def validate_drafts(store, principal, policy, request):
    """A dry run of the deposit and of the next baseline: nothing is stored."""
    check_schema(request, VALIDATE_REQUEST)
    prepared_id = request.get('prepared_change')
    if prepared_id:
        payload = _prepared(store, principal, prepared_id, policy)
        request = {'objects': payload['objects'], 'base': payload['base']}
    if not request.get('objects'):
        raise InvalidModel('Give objects, or the prepared_change returned by air_rebase_drafts')
    objects = request['objects']
    schema_report = validate(objects)
    report = {'engine': ENGINE, 'registry_written': False, 'objects': len(objects), 'schema_valid': schema_report['valid'],
              'diagnostics': schema_report['diagnostics'][:200], 'diagnostics_truncated': len(schema_report['diagnostics']) > 200}
    if not schema_report['valid']:
        report.update(deposit_ready=False, freeze_ready=False, next_steps=[
            _step('Fix the schema diagnostics; each names its object and field', 'air_describe_type', {'type': '<the type named in the diagnostic>'})])
        return _bounded(report, 'Draft validation')
    ids = {o['meta']['id'] for o in objects}
    heads = {i: store.head(i) for i in ids}
    report['storage'] = [_storage_status(store, policy, principal, o, heads) for o in sorted(objects, key=lambda o: key(exact(o)))]
    in_bundle = {key(exact(o)): o for o in objects}
    latest_in_bundle = defaultdict(int)
    for o in objects: latest_in_bundle[o['meta']['id']] = max(latest_in_bundle[o['meta']['id']], o['meta']['revision'])
    references, missing, not_latest, unreadable = [], [], [], []
    target_ids = set()
    for obj in objects:
        for field, ref, _ in reference_slots(obj): target_ids.add(ref['id'])
    stored_latest = store.latest_revisions(target_ids)
    for obj in objects:
        for field, ref, types in reference_slots(obj):
            where = {'from': {**exact(obj), 'type': obj['meta']['type']}, 'field': field, 'target': {'id': ref['id'], 'revision': ref['revision']}}
            target = in_bundle.get(key(ref))
            if target is not None:
                resolution = 'IN_BUNDLE';target_type = target['meta']['type']
            else:
                row = store.get(ref['id'], ref['revision'])
                if row is None:
                    missing.append({**where, 'code': 'AIR_REFERENCE_MISSING', 'message': 'Exact target is neither in the bundle nor stored'});continue
                target_type = row['object']['meta']['type']
                if not policy.allows(principal, 'read', row['object']['meta']['namespace']):
                    unreadable.append(where);continue
                resolution = 'STORED'
            if target_type not in types:
                missing.append({**where, 'code': 'AIR_REFERENCE_TYPE', 'message': 'Expected ' + ', '.join(types)})
            newest = max(latest_in_bundle.get(ref['id'], 0), stored_latest.get(ref['id'], 0))
            if newest > ref['revision']:
                not_latest.append({**where, 'code': 'AIR_REFERENCE_NOT_LATEST', 'latest_revision': newest})
            references.append(resolution)
    report['references'] = {'total': len(references), 'in_bundle': references.count('IN_BUNDLE'), 'stored': references.count('STORED'),
                            'problems': missing[:200], 'unreadable': unreadable[:50], 'not_latest': not_latest[:200]}
    blocked = [s for s in report['storage'] if s['storage'] in ('IDENTITY_CONFLICT', 'REVISION_CONFLICT', 'REVISION_NOT_AFTER_LATEST')]
    forbidden = sorted({s['namespace'] for s in report['storage'] if not s['writable'] and s['storage'] != 'UNCHANGED'})
    report['borrowed_repins'] = sum(1 for s in report['storage'] if not s['writable'] and s['storage'] == 'UNCHANGED')
    stamp = now()
    report['future_timestamps'] = [{'id': o['meta']['id'], 'revision': o['meta']['revision'], 'recorded_at': o['meta']['recorded_at']}
                                   for o in objects if o['meta']['recorded_at'] > stamp][:50]
    report['forbidden_namespaces'] = forbidden
    report['deposit_ready'] = not blocked and not forbidden and not missing and not unreadable
    steps = []
    if blocked: steps.append(_step('Give each conflicting object the next free revision (latest_stored_revision + 1)', 'air_list_revisions', {'id': blocked[0]['id']}))
    if forbidden: steps.append(_step('These namespaces are not writable for you: move the objects to your namespace or hand them to their owner', None, {}))
    if missing: steps.append(_step('Add the missing targets to the bundle or correct the references', 'air_describe_type', {'type': missing[0]['from']['type']}))
    if 'base' in request:
        exported, members = _candidate(store, principal, policy, request['base'], objects)
        profile = _target_profile(exported, request.get('profile'))
        stale = _stale_dependents(members, objects)
        graph = validate_graph(members, profile)
        home = exported['baseline']['meta']['namespace']
        candidate = {'base': request['base'], 'profile': profile, 'members': len(members),
                     'stale_dependents': len(stale), 'stale_dependents_sample': stale[:20],
                     'reference_closure_valid': graph['valid'] if not stale else False,
                     'closure_diagnostics': [d for d in graph['diagnostics'] if d['code'] != 'AIR_REFERENCE_MISSING' or not stale][:50]}
        if stale:
            reason = 'Stale dependents still point at replaced revisions; compare after air_rebase_drafts'
            candidate['architecture'] = {'status': 'NOT_COMPARABLE_UNTIL_REBASE', 'reason': reason}
            candidate['construction'] = {'status': 'NOT_COMPARABLE_UNTIL_REBASE', 'reason': reason}
        else:
            candidate.update(_delta(store, principal, policy, exported['objects'], members, home, profile))
        report['candidate'] = candidate
        report['freeze_ready'] = report['deposit_ready'] and not stale and graph['valid']
        if stale:
            steps.append(_step(str(len(stale)) + ' existing objects still point at older revisions: produce their new revisions automatically',
                               'air_rebase_drafts', {'base': request['base'], 'objects': '<the same objects>'}))
        elif report['deposit_ready'] and prepared_id:
            steps.append(_step('Show the change to the architect; after explicit approval deposit it by reference', 'air_deposit_prepared', {'prepared_change': prepared_id}))
            steps.append(_step('Then freeze the next revision, naming this change', 'air_freeze_prepared',
                               {'prepared_change': prepared_id, 'name': '<name>', 'description': '<what this change does>'}))
        elif report['deposit_ready']:
            steps.append(_step('Prepare the complete change, then deposit and freeze it by reference', 'air_rebase_drafts',
                               {'base': request['base'], 'objects': '<the same objects>'}))
    else:
        report['freeze_ready'] = False
        if report['deposit_ready']:
            steps.append(_step('Validate against the current baseline to see the effect on the whole dossier', 'air_validate_drafts',
                               {'objects': '<the same objects>', 'base': '<latest baseline snapshot from air_list_revisions>'}))
    if prepared_id: report['prepared_change'] = prepared_id
    report['next_steps'] = steps
    return _bounded(report, 'Draft validation')


def _explained(row):
    text = EXPLAIN.get(row.get('code'))
    return {**row, 'explanation': text[0], 'fix_hint': text[1]} if text else row


def _step(what, tool, arguments, note=None):
    step = {'step': what, 'tool': tool, 'arguments': arguments}
    if note: step['note'] = note
    return step


def rebase_drafts(store, principal, policy, settings, request):
    """Complete a change: every member that points at a replaced identity gets a new revision with advanced references."""
    check_schema(request, REBASE_REQUEST)
    objects = deepcopy(request.get('objects', []))
    if not objects and not request.get('realign_borrowed'):
        raise InvalidModel('Give drafts, or realign_borrowed: true to follow the latest revisions of borrowed objects')
    if objects:
        checked = validate(objects)
        if not checked['valid']:
            raise InvalidModel('Drafts are not valid; run air_validate_drafts first', checked)
    exported, members = _candidate(store, principal, policy, request['base'], objects)
    home = exported['baseline']['meta']['namespace']
    repins, skipped = [], []
    if request.get('realign_borrowed'):
        current = {o['meta']['id']: o for o in members}
        latest = store.latest_revisions([i for i, o in current.items() if o['meta']['namespace'] != home])
        pending = [(i, r) for i, r in latest.items() if r > current[i]['meta']['revision'] and i not in {o['meta']['id'] for o in objects}]
        steps = 0
        while pending and steps < 4000:
            object_id, revision = pending.pop();steps += 1
            row = store.get(object_id, revision)
            if row is None or not policy.allows(principal, 'read', row['object']['meta']['namespace']):
                skipped.append({'id': object_id, 'revision': revision});continue
            obj = row['object']
            if obj['meta']['namespace'] == home: continue  # own objects are rebased, never pulled
            held = current.get(object_id)
            if held is not None and held['meta']['revision'] >= revision: continue
            current[object_id] = obj;repins.append({'id': object_id, 'revision': revision, 'from_revision': held['meta']['revision'] if held else None,
                                                   'type': obj['meta']['type'], 'namespace': obj['meta']['namespace']})
            for _, ref, _ in reference_slots(obj):
                target = current.get(ref['id'])
                if target is None or target['meta']['revision'] < ref['revision']: pending.append((ref['id'], ref['revision']))
        objects += [current[r['id']] for r in repins]
        exported, members = _candidate(store, principal, policy, request['base'], objects)
    from air.collaboration import identity_context, identity_uri
    author = identity_uri(identity_context(principal, settings)) if settings else None
    stamp = now()
    drafts = {o['meta']['id']: o for o in objects}
    base_members = {o['meta']['id']: o for o in exported['objects']}
    replaced = {i: o['meta']['revision'] for i, o in drafts.items()}
    heads = store.latest_revisions([o['meta']['id'] for o in members])
    rebased, adjusted, conflicts = [], [], []

    def advance(obj):
        paths = []
        def visit(ref, path):
            if ref['id'] in replaced and ref['revision'] < replaced[ref['id']]:
                ref['revision'] = replaced[ref['id']];ref.pop('digest', None);paths.append(path)
        _walk_refs(obj['body'], lambda r, p: visit(r, 'body' + p))
        _walk_refs(obj['meta']['provenance'], lambda r, p: visit(r, 'meta/provenance' + p))
        return paths

    changed = True
    while changed:
        changed = False
        for object_id, obj in sorted(drafts.items()):
            candidate = deepcopy(obj)
            paths = advance(candidate)
            if paths and obj['meta']['namespace'] != home:
                if object_id not in {c['id'] for c in conflicts}:
                    conflicts.append({'id': object_id, 'revision': obj['meta']['revision'], 'namespace': obj['meta']['namespace'], 'references_behind': paths})
                continue
            if paths:
                held = store.get(object_id, obj['meta']['revision']) if heads.get(object_id, 0) >= obj['meta']['revision'] else None
                if held is not None and digest(held['object']) != digest(candidate):
                    # A previously deposited draft can be outside the base
                    # (e.g. an interrupted creation). Advancing its references
                    # must not overwrite that immutable stored revision.
                    previous_revision = obj['meta']['revision']
                    candidate['meta']['revision'] = max(heads.get(object_id, 0), previous_revision) + 1
                    candidate['meta']['recorded_at'] = stamp
                    if author: candidate['meta']['provenance']['recorded_by'] = author
                    replaced[object_id] = candidate['meta']['revision']
                    changed = True
                    rebased.append({'id': object_id, 'type': obj['meta']['type'], 'from_revision': previous_revision,
                                    'to_revision': candidate['meta']['revision'], 'references_advanced': paths})
                drafts[object_id] = candidate
                obj = candidate
            if paths and object_id not in {r['id'] for r in rebased}:
                adjusted.append({'id': object_id, 'revision': obj['meta']['revision'], 'references_advanced': paths})
        for object_id, obj in sorted(base_members.items()):
            if object_id in drafts: continue
            candidate = deepcopy(obj);paths = advance(candidate)
            if not paths: continue
            if obj['meta']['namespace'] != home:
                # Another project's revision is never re-revised from here: its owner must publish the aligned revision.
                if object_id not in {c['id'] for c in conflicts}:
                    conflicts.append({'id': object_id, 'revision': obj['meta']['revision'], 'namespace': obj['meta']['namespace'], 'references_behind': paths})
                continue
            candidate['meta']['revision'] = max(heads.get(object_id, 0), obj['meta']['revision']) + 1
            candidate['meta']['recorded_at'] = stamp
            if author: candidate['meta']['provenance']['recorded_by'] = author
            drafts[object_id] = candidate;replaced[object_id] = candidate['meta']['revision'];changed = True
            rebased.append({'id': object_id, 'type': obj['meta']['type'], 'from_revision': obj['meta']['revision'],
                            'to_revision': candidate['meta']['revision'], 'references_advanced': paths})
    # A first reference to another project's object pulls that exact revision and its closure: it is borrowed as it
    # stands in the registry, never revised from here. A different revision already held is left to realign_borrowed.
    added, present = [], {**base_members, **drafts}
    queue = [ref for o in present.values() for _, ref, _ in reference_slots(o)]
    while queue and len(added) < 4000:
        ref = queue.pop()
        if ref['id'] in present: continue
        row = store.get(ref['id'], ref['revision'])
        if row is None: continue
        obj = row['object']
        if obj['meta']['namespace'] == home: continue
        if not policy.allows(principal, 'read', obj['meta']['namespace']):
            skipped.append({'id': ref['id'], 'revision': ref['revision']});continue
        present[ref['id']] = obj;drafts[ref['id']] = obj;objects.append(obj)
        added.append({'id': ref['id'], 'revision': ref['revision'], 'type': obj['meta']['type'], 'namespace': obj['meta']['namespace']})
        queue += [r for _, r, _ in reference_slots(obj)]
    # A reference the walk could not reach (for instance one built from an expression) is reported, never guessed.
    unreachable = []
    for obj in drafts.values():
        for field, ref, _ in reference_slots(obj):
            if ref['id'] in replaced and ref['revision'] < replaced[ref['id']]:
                unreachable.append({'object': exact(obj), 'field': field, 'target': {'id': ref['id'], 'revision': ref['revision']}})
    bundle = sorted(drafts.values(), key=lambda o: key(exact(o)))
    candidate_members = {**base_members, **drafts}
    profile = _target_profile(exported, request.get('profile'))
    graph = validate_graph(list(candidate_members.values()), profile)
    base_meta = exported['baseline']['meta']
    meta = deepcopy(base_meta)
    meta['revision'] = max(store.head(base_meta['id'])['latest_revision'], base_meta['revision']) + 1
    meta['recorded_at'] = stamp;meta['validity'] = {'start': stamp, 'end': None}
    if author: meta['provenance']['recorded_by'] = author
    sources = {key(ref): {'id': ref['id'], 'revision': ref['revision']} for o in request.get('objects', []) for ref in o['meta']['provenance']['source_refs']
               if candidate_members.get(ref['id']) is not None and candidate_members[ref['id']]['meta']['revision'] == ref['revision']
               and candidate_members[ref['id']]['meta']['type'] == 'air.Source'}
    if sources:
        meta['provenance']['source_refs'] = sorted(sources.values(), key=key)
    else:
        for ref in meta['provenance']['source_refs']:
            if ref['id'] in replaced: ref['revision'] = replaced[ref['id']]
    own_changes = [o for o in request.get('objects', []) if o['meta']['namespace'] == home]
    borrowed = [o for o in objects if o['meta']['namespace'] != home]
    meta['provenance']['method'] = ('Baseline prepared by air_rebase_drafts: ' + str(len(own_changes)) + ' content changes, '
                                    + str(len(rebased)) + ' reference-only revisions, ' + str(len(borrowed)) + ' borrowed revisions re-pinned')
    baseline_request = {'meta': meta, 'profile': profile, 'members': sorted((exact(o) for o in candidate_members.values()), key=key),
                        'parent_baselines': [exact(exported['baseline'])]}
    size = len(json.dumps(bundle, ensure_ascii=False))
    prepared = None
    if policy.allows(principal, 'write', base_meta['namespace']) and graph['valid'] and not unreachable and not conflicts:
        def timeless(value):
            value = deepcopy(value)
            for obj in value['objects'] + [value['baseline_request']]:
                obj['meta'].pop('recorded_at', None);obj['meta'].pop('validity', None)
            return value
        payload = {'base': request['base'], 'objects': bundle, 'baseline_request': baseline_request}
        identifier = 'urn:air:prepared-change:' + artifact_digest({'actor': principal['subject'], **timeless(payload)}).split(':')[1]
        existing = store.get_record(identifier)
        if existing is not None and existing['kind'] == 'prepared_change' and existing['actor'] == principal['subject']:
            # Preparing the same change twice returns the first preparation, timestamps included.
            payload = existing['payload'];bundle = payload['objects'];baseline_request = payload['baseline_request']
        else:
            store.record_once(identifier, 'prepared_change', base_meta['namespace'], principal['subject'], payload)
        prepared = {'id': identifier, 'objects': len(bundle), 'baseline_revision': meta['revision'],
                    'use': 'air_deposit_prepared then air_freeze_prepared with this id: nothing is resent, nothing is stored in the registry before them'}
    report = {'engine': ENGINE, 'registry_written': False, 'prepared_change': prepared, 'base': request['base'],
              'fields_to_review': ['baseline_request.meta.name', 'baseline_request.meta.description'],
              'drafts_given': len(request.get('objects', [])), 'rebased': rebased, 'drafts_adjusted': adjusted, 'unreachable_references': unreachable,
              'bundle': {'objects': len(bundle), 'bytes': size, 'content_changes': len(own_changes), 'reference_only_revisions': len(rebased),
                         'borrowed_repins': len(borrowed)},
              'borrowed_realigned': repins, 'borrowed_added': added, 'borrowed_not_readable': skipped,
              'borrowed_conflicts': conflicts,
              'candidate': {'members': len(candidate_members), 'valid': graph['valid'] and not unreachable and not conflicts,
                            'diagnostics': [_explained(d) for d in graph['diagnostics'][:50]],
                            **(_delta(store, principal, policy, exported['objects'], list(candidate_members.values()), home, profile) if graph['valid'] else {})},
              'objects': bundle, 'baseline_request': baseline_request,
              'next_steps': [
                  _step('Show the architect the content changes and the list of reference-only revisions', None, {}),
                  *([_step('After approval, deposit the prepared bundle by reference', 'air_deposit_prepared', {'prepared_change': prepared['id']}),
                     _step('Then freeze the next baseline revision, naming this change', 'air_freeze_prepared',
                           {'prepared_change': prepared['id'], 'name': '<name of the new revision>', 'description': '<what this change does>'})] if prepared else
                    [_step('After approval, deposit the complete bundle in one call', 'air_import_drafts', {'objects': '<objects of this result>'}),
                     _step('Then freeze the next baseline revision after reviewing its name and description', 'air_freeze_baseline', '<baseline_request of this result>')]),
                  _step('Then verify the new baseline', 'air_guide', {'baseline': {'id': base_meta['id']}, 'intent': 'REVIEW'})]}
    if not request.get('include_bundle', prepared is None):
        # The prepared change holds the bundle; the answer lists it instead of repeating every body.
        roles = {r['id']: 'REFERENCE_ONLY' for r in rebased}
        report['objects'] = [{'id': o['meta']['id'], 'revision': o['meta']['revision'], 'type': o['meta']['type'],
                              'role': 'BORROWED_REPIN' if o['meta']['namespace'] != home else roles.get(o['meta']['id'], 'CONTENT')} for o in bundle]
        report['bundle_included'] = False
    else:
        report['bundle_included'] = True
    if len(json.dumps(report, ensure_ascii=False)) > OUTPUT_MAX:
        raise TooLarge('Rebased bundle exceeds ' + str(OUTPUT_MAX) + ' bytes; split the change')
    return _bounded(report, 'Rebase')


# ---------------------------------------------------------------- reading

def _summary_of(obj):
    meta = obj['meta']
    return {'id': meta['id'], 'revision': meta['revision'], 'type': meta['type'], 'namespace': meta['namespace'],
            'name': meta['name'], 'description': meta['description'][:300], 'digest': digest(obj)}


def _inline_schema(store, principal, policy, obj):
    descriptor = obj['body']['artifact']
    try:
        manifest = store.get_record(descriptor['locator'])
        if not manifest or manifest['kind'] != 'artifact_manifest': return {'status': 'ARTIFACT_UNAVAILABLE'}
        result, data = artifacts.download(store, principal, policy, {'artifact': manifest_reference(manifest)})
    except (InvalidModel, Forbidden, ValueError):
        return {'status': 'ARTIFACT_UNREADABLE'}
    if result['artifact_reference'] != descriptor: return {'status': 'DESCRIPTOR_DIFFERS'}
    if len(data) > SCHEMA_INLINE_MAX: return {'status': 'TOO_LARGE_TO_INLINE', 'size': len(data), 'read_with': 'air_read_artifact'}
    try: return {'status': 'INLINED', 'content': json.loads(data.decode('utf-8'))}
    except ValueError: return {'status': 'NOT_JSON'}


def browse_baseline(store, principal, policy, request):
    check_schema(request, BROWSE_REQUEST)
    snapshot, exported, latest = resolve_pointer(store, principal, policy, request['baseline'])
    baseline = exported['baseline'];home = baseline['meta']['namespace']
    objects = sorted(exported['objects'], key=lambda o: (o['meta']['type'], o['meta']['id']))
    counts = defaultdict(lambda: {'owned': 0, 'referenced': 0})
    for obj in objects: counts[obj['meta']['type']]['owned' if obj['meta']['namespace'] == home else 'referenced'] += 1
    selected = objects
    if request.get('types'): selected = [o for o in selected if o['meta']['type'] in request['types']]
    if request.get('ids'): selected = [o for o in selected if o['meta']['id'] in set(request['ids'])]
    if request.get('namespace'): selected = [o for o in selected if o['meta']['namespace'] == request['namespace']]
    if request.get('owned_only'): selected = [o for o in selected if o['meta']['namespace'] == home]
    if request.get('text'):
        needle = request['text'].lower()
        selected = [o for o in selected if needle in (o['meta']['name'] + ' ' + o['meta']['description'] + ' ' + o['meta']['id']).lower()]
    offset, limit = request.get('offset', 0), request.get('limit', 50 if request.get('fields') == 'FULL' else 200)
    page = selected[offset:offset + limit]
    items = []
    for obj in page:
        item = _summary_of(obj) if request.get('fields', 'OUTLINE') == 'OUTLINE' else {**_summary_of(obj), 'object': obj}
        if request.get('schemas') and obj['meta']['type'] == 'air.DataSchema':
            item['schema'] = _inline_schema(store, principal, policy, obj)
        items.append(item)
    report = {'engine': ENGINE, 'baseline': {**snapshot, 'name': baseline['meta']['name'], 'namespace': home,
                                             'profile': baseline['body']['profiles'][0], 'recorded_at': baseline['meta']['recorded_at'],
                                             'parent_baselines': baseline['body']['parent_baselines'], 'members': len(objects),
                                             'latest_revision': latest, 'is_latest': snapshot['revision'] == latest},
              'counts_by_type': {k: v for k, v in sorted(counts.items())},
              'namespaces': dict(sorted(Counter(o['meta']['namespace'] for o in objects).items())),
              'matching': len(selected), 'offset': offset, 'limit': limit, 'items': items,
              'next_offset': offset + limit if offset + limit < len(selected) else None}
    if len(json.dumps(report, ensure_ascii=False)) > OUTPUT_MAX:
        raise TooLarge('Page exceeds ' + str(OUTPUT_MAX) + ' bytes; lower the limit or use fields OUTLINE')
    return _bounded(report, 'Browse')


def _skeleton(definition, depth=0):
    if depth > 12: return None
    if 'const' in definition: return definition['const']
    if 'enum' in definition: return definition['enum'][0]
    for combinator in ('oneOf', 'anyOf'):
        if combinator in definition: return _skeleton(definition[combinator][0], depth + 1)
    kind = definition.get('type')
    if isinstance(kind, list): kind = kind[0]
    if kind == 'object' or 'properties' in definition:
        return {name: _skeleton(sub, depth + 1) for name, sub in definition.get('properties', {}).items()
                if name in definition.get('required', [])}
    if kind == 'array':
        return [_skeleton(definition['items'], depth + 1)] if definition.get('minItems', 0) > 0 and isinstance(definition.get('items'), dict) else []
    if kind == 'integer': return max(definition.get('minimum', 1), 1)
    if kind == 'number': return definition.get('minimum', 0)
    if kind == 'boolean': return False
    if kind == 'string':
        if definition.get('format') == 'uri': return 'urn:example:replace-me'
        if definition.get('format') == 'date-time' or definition.get('pattern') == 'Z$': return '2026-01-01T00:00:00Z'
        return '<text>'
    return None


def _reference_fields(definition, path='', found=None, depth=0):
    found = [] if found is None else found
    if depth > 14 or not isinstance(definition, dict): return found
    props = definition.get('properties', {})
    if set(props) >= {'id', 'revision'} and set(props) <= {'id', 'revision', 'type', 'digest', 'direction'}:
        found.append(path or '/');return found
    for name, sub in props.items(): _reference_fields(sub, path + '/' + name, found, depth + 1)
    if isinstance(definition.get('items'), dict): _reference_fields(definition['items'], path + '/[]', found, depth + 1)
    for combinator in ('oneOf', 'anyOf'):
        for sub in definition.get(combinator, []): _reference_fields(sub, path, found, depth + 1)
    return sorted(set(found))


def describe_type(store, principal, policy, request):
    check_schema(request, TYPE_REQUEST)
    kind = request['type'];definition = schema(kind)
    profile = next(p for p, types in sorted(PROFILE_TYPES.items(), key=lambda item: len(item[1])) if kind in types)
    return {'engine': ENGINE, 'type': kind, 'first_profile': profile, 'json_schema': definition,
            'skeleton': _skeleton(definition), 'reference_fields': _reference_fields(definition['properties']['body'], 'body'),
            **({'expression_language': EXPRESSION_LANGUAGE} if '"ast"' in json.dumps(definition) else {}),
            'notes': ['The skeleton only fills required fields with placeholders; replace every placeholder.',
                      'meta.revision starts at 1 for a new identity; a change stores latest+1 (air_list_revisions).',
                      'Every reference is exact {id, revision}; air_validate_drafts checks them before any deposit.']}


# ---------------------------------------------------------------- guide

def _grouped(diagnostics, limit=12):
    groups = defaultdict(list)
    for row in diagnostics: groups[row['code']].append(row)
    result = []
    for code, rows in sorted(groups.items(), key=lambda item: -len(item[1]))[:limit]:
        text = EXPLAIN.get(code, (rows[0].get('message', ''), 'See the diagnostics for the object and field concerned.'))
        shown = rows if len(rows) <= 25 else rows[:3]
        result.append({'code': code, 'count': len(rows), 'explanation': text[0], 'fix_hint': text[1], 'complete_list': len(rows) <= 25,
                       'items': [{k: r[k] for k in ('path', 'operation', 'object', 'missing_state_effects', 'missing_failure_modes') if k in r} for r in shown]})
    return result


def _gap_status(gap, criterion):
    detail = (criterion or {}).get('detail', {})
    if any(o['id'] == gap['reference']['id'] for o in detail.get('open', [])): return {'status': 'OPEN'}
    for g in detail.get('accepted_by_decision', []):
        if g['id'] == gap['reference']['id']:
            pending = any(p['id'] == g['id'] for p in detail.get('accepted_pending_review', []))
            return {'status': 'ACCEPTED_PENDING_HUMAN_REVIEW' if pending else 'ACCEPTED_BY_REVIEWED_DECISION', 'decisions': g['decisions']}
    return {'status': 'UNKNOWN'}


def _delivery(objects, home, gate):
    """What an architect asks before a committee, computed once so that an agent does not rebuild it from raw objects."""
    types = {o['meta']['type'] for o in objects if o['meta']['namespace'] == home}
    wanted = {'air.AcceptanceScenario', 'air.ComplianceMapping', 'air.DeliveryEstimate', 'air.Roadmap'}
    if not types & wanted: return None
    from air.acceptance import walk
    from air.delivery_calc import chosen_by_project, compliance, estimates, roadmaps
    by_id = {o['meta']['id']: o for o in objects}
    owned = [o for o in objects if o['meta']['namespace'] == home]
    result = {'deliverables': ['32-scenarios-acceptation', '33-tests-non-regression', '34-matrice-conformite', '35-exigences-non-fonctionnelles',
                               '36-estimation-ia', '37-feuilles-de-route']}
    if 'air.AcceptanceScenario' in types:
        w = walk(objects, home, owned_only=True)
        result['scenarios'] = {**w['summary'], 'not_passing': [{'name': r['name'], 'verdict': r['verdict'], 'issues': [f['issue'] for f in r['findings'][:3]]}
                                                               for r in w['scenarios'] if r['verdict'] != 'PASS'][:10],
                               'coverage': [{'navigation': c['name'], 'screens': '%d/%d' % (c['screens_covered'], c['screens']),
                                             'transitions': '%d/%d' % (c['transitions_covered'], c['transitions']), 'operations_uncovered': c['operations_uncovered'][:10],
                                             'dead_ends': c['dead_ends']} for c in w['coverage']],
                               'journey_operations_not_exercised': {j['name']: j['not_exercised'] for j in w['journeys'] if j['not_exercised']},
                               'regression_suite': len(w['regression_suite'])}
    criterion = next((c for c in (gate or {}).get('criteria', []) if c['code'] == 'COMPLIANCE'), None)
    rows = [r for r in compliance(objects, by_id) if home in r['by_project'] or r['namespace'] == home]
    result['compliance'] = {'status': criterion['status'] if criterion else None,
                            **({k: criterion['detail'][k] for k in ('subjects', 'received_as_input', 'mapped') if k in criterion['detail']} if criterion else {}),
                            'unmapped': [u['name'] for u in (criterion or {}).get('detail', {}).get('unmapped', [])][:20],
                            'not_applicable_here': [{'name': r['name'], 'delegated_to': r['delegated'].get(home, []),
                                                     'confirmed_in_this_baseline': r['delegation_confirmed']} for r in rows if home in r['delegated']],
                            'infrastructure_only': [{'name': r['name'], 'accountable': r['ownership'][home]['accountable']} for r in rows
                                                    if r['ownership'].get(home, {}).get('scope') == 'TECHNICAL'],
                            'meaning': 'A requirement not applicable here must be implemented by the project it is delegated to; pin both baselines together to confirm it. '
                                       'A requirement carried by infrastructure only needs a named accountable role'}
    est = [r for r in estimates(owned, by_id)]
    if est:
        without = sum(r['without_ai_pd'] for r in est);with_ai = sum(r['with_ai_pd'] for r in est)
        result['estimate'] = {'without_ai_pd': str(without), 'with_ai_pd': str(with_ai), 'saved_pd': str(without - with_ai),
                              'saved_ratio': str(round((without - with_ai) / without, 3)) if without else None,
                              'confidence': sorted({r['confidence'] for r in est}), 'units': len(est)}
    maps = roadmaps(objects, by_id, estimates(objects, by_id))
    mine = [r for r in maps if r['namespace'] == home]
    if mine:
        pick = chosen_by_project(mine).get(home)
        result['roadmaps'] = {'compared': [{'name': r['name'], 'status': r['status'], 'uses_ai': r['uses_ai'], 'end': r['end'], 'months': str(round(r['months'], 1)),
                                            'total_cost': str(r['total_cost']) if r['total_cost'] is not None else None,
                                            'delta_months': str(round(r['delta_months'], 1)) if r['delta_months'] is not None else None,
                                            'subscription': str(r['subscription']),
                                            'external_dependencies': [{'phase': e['phase'], 'waits_for': (e['namespace'] or '?') + ' / ' + e['roadmap_name'] + ' / ' + e['target_phase'],
                                                                       'kind': e['kind'], 'dates_hold': e['satisfied']} for e in r['external']]} for r in mine],
                              'recommended': pick['name'] if pick else None}
    return result


def guide(store, principal, policy, request):
    """Where the dossier stands and the next exact calls for the architect's intent."""
    check_schema(request, GUIDE_REQUEST)
    intent = request.get('intent', 'ORIENT')
    snapshot, exported, latest = resolve_pointer(store, principal, policy, request['baseline'])
    baseline = exported['baseline'];home = baseline['meta']['namespace'];objects = exported['objects']
    profile = baseline['body']['profiles'][0]
    owned = [o for o in objects if o['meta']['namespace'] == home];borrowed = [o for o in objects if o['meta']['namespace'] != home]
    from air.architecture import inspect_objects
    arch = inspect_objects(store, principal, policy, objects, home, 'SUMMARY')
    construction = _construction(objects, profile)
    heads = store.latest_revisions([o['meta']['id'] for o in borrowed])
    stale = [{'id': o['meta']['id'], 'type': o['meta']['type'], 'namespace': o['meta']['namespace'], 'pinned_revision': o['meta']['revision'],
              'latest_revision': heads[o['meta']['id']]} for o in borrowed if heads.get(o['meta']['id'], 0) > o['meta']['revision']]
    parents = baseline['body']['parent_baselines']
    aligned = {}
    for namespace in sorted({o['meta']['namespace'] for o in borrowed}):
        pins = {o['meta']['id']: o['meta']['revision'] for o in borrowed if o['meta']['namespace'] == namespace}
        matches = []
        if policy.allows(principal, 'read', namespace):
            for baseline_id in store.identities_of(namespace, 'air.Baseline'):
                rows, _ = store.revisions(baseline_id, 20)
                for row in rows:
                    members = {m['id']: m['revision'] for m in store.get(baseline_id, row['revision'])['object']['body']['members']}
                    if all(members.get(i) == r for i, r in pins.items()): matches.append({'id': baseline_id, 'revision': row['revision'], 'digest': row['digest']})
        aligned[namespace] = {'objects': len(pins), 'matching_baselines': matches[:10], 'status': 'ALIGNED' if matches else 'NO_SINGLE_BASELINE_MATCHES'}
    bindings = [b for b in arch['bindings'] if b['owned']]
    machines = [exact(o) for o in owned if o['meta']['type'] == 'air.StateMachine']
    # The ready-to-build verdict travels with the guide, so that a client whose tool list is older still reads it right.
    from air.readiness import assess_readiness
    try:
        gate = assess_readiness(store, principal, policy, {'baseline': snapshot})
    except (InvalidModel, Forbidden, NotFound):
        gate = None
    gap_criterion = next((c for c in gate['criteria'] if c['code'] == 'GAPS'), None) if gate else None
    state = {
        'baseline': {**snapshot, 'name': baseline['meta']['name'], 'namespace': home, 'profile': profile,
                     'recorded_at': baseline['meta']['recorded_at'], 'latest_revision': latest, 'is_latest': snapshot['revision'] == latest,
                     'parent_baselines': parents},
        'content': {'owned': dict(sorted(Counter(o['meta']['type'] for o in owned).items())), 'borrowed': dict(sorted(Counter(o['meta']['namespace'] for o in borrowed).items()))},
        'health': {
            'reference_closure': 'VALID' if exported['validation']['valid'] else 'INVALID',
            'architecture_checks': {'result': arch['checks']['result'], 'families': arch['checks']['families'],
                                    'violations': arch['checks']['violations'][:10]},
            'construction': None if construction is None else {'structurally_complete': construction['valid'],
                                                                'diagnostics': len(construction['diagnostics']), 'by_code': _grouped(construction['diagnostics']),
                                                                'meaning': 'Structural completeness of the construction chain only; whether the dossier is ready to build is readiness.result'},
            'declared_gaps': [{'id': g['reference']['id'], 'revision': g['reference']['revision'], 'name': g['name'], 'impact': g.get('impact'),
                               'resolution_owner': g.get('resolution_owner'), **_gap_status(g, gap_criterion)} for g in arch['gaps'] if g['owned']],
            'open_unknowns': exported['validation'].get('open_unknowns', []),
            'borrowed_objects_behind_latest': {'count': len(stale), 'sample': stale[:25]},
            'borrowed_alignment': aligned},
        'readiness': None if gate is None else {'result': gate['result'], 'blocking': gate['blocking'], 'proof': gate['proof'],
            'criteria': [{'code': c['code'], 'status': c['status'], **({'to_close': c['to_close']} if c['to_close'] else {}),
                          **({'owner': c['owner']} if c.get('owner') else {})} for c in gate['criteria']],
            'verification': next(({k: v for k, v in c['detail'].items() if k in ('design_cases', 'design_cases_open', 'build_acceptance_tests', 'tests_not_planned_in_a_unit')}
                                  for c in gate['criteria'] if c['code'] == 'VERIFICATION'), None),
            'meaning': 'READY_TO_BUILD only when no criterion is NOT_MET; tests run after construction, design-time cases before'},
    }
    delivery = _delivery(objects, home, gate)
    if delivery: state['delivery'] = delivery
    s = snapshot;steps = []
    if snapshot['revision'] != latest:
        steps.append(_step('This is not the latest revision (' + str(latest) + '): switch to it unless you review history on purpose',
                           'air_guide', {'baseline': {'id': s['id']}, 'intent': intent}))
    if intent == 'ORIENT':
        steps += [_step('Ready to build? Twelve criteria, each with what closes it (already summarised in readiness)', 'air_assess_readiness', {'baseline': s})]
        if delivery and delivery.get('scenarios'):
            steps.append(_step('Walk the acceptance scenarios on the navigation (already summarised in delivery.scenarios)', 'air_walk_scenarios', {'baseline': s}))
        steps += [
                  _step('Outline the dossier content by type', 'air_browse_baseline', {'baseline': s, 'owned_only': True}),
                  _step('Read the structure without full bodies', 'air_inspect_architecture', {'baseline': s, 'detail': 'SUMMARY'})]
        steps += [_step('Read the API of ' + b['name'], 'air_compile_openapi', {'baseline': s, 'binding': b['reference'],
                                                                                'info': {'title': b['name'], 'version': str(s['revision'])}})
                  for b in bindings if b.get('transport') == 'HTTP'][:6]
    elif intent == 'CHANGE':
        steps += [_step('Find the objects to change and read them in full', 'air_browse_baseline', {'baseline': s, 'text': '<keyword>', 'fields': 'FULL', 'limit': 20}),
                  _step('Get the exact shape of any new object type', 'air_describe_type', {'type': '<air.Type>'}),
                  _step('Write only the objects whose content changes, each at latest+1 or revision 1 when new', None, {}),
                  _step('Dry-run the change against this baseline', 'air_validate_drafts', {'objects': '<drafts>', 'base': s}),
                  _step('Produce the reference-only revisions and the next baseline request', 'air_rebase_drafts', {'base': s, 'objects': '<drafts>'}),
                  _step('Show the architect the change; after explicit approval deposit it by reference', 'air_deposit_prepared', {'prepared_change': '<prepared_change.id from air_rebase_drafts>'}),
                  _step('Freeze the next revision, naming this change', 'air_freeze_prepared', {'prepared_change': '<prepared_change.id>', 'name': '<name>', 'description': '<what this change does>'}),
                  _step('Verify what changed and produce the deliverables', 'air_guide', {'baseline': {'id': s['id']}, 'intent': 'REVIEW'})]
    elif intent == 'REVIEW':
        if parents:
            parent_row = store.get(parents[0]['id'], parents[0]['revision'])
            parent = {'id': parents[0]['id'], 'revision': parents[0]['revision'], 'digest': parent_row['digest']}
            steps.append(_step('List what changed since the previous revision (content changes first)', 'air_diff', {'before': parent, 'after': s}))
            try:
                previous = ScopedStore(store, principal, policy).export_baseline(parent)
                before_arch = inspect_objects(store, principal, policy, previous['objects'], previous['baseline']['meta']['namespace'], 'SUMMARY')['checks']
                introduced_a, resolved_a = _compare(before_arch['violations'] + before_arch['observations'], arch['checks']['violations'] + arch['checks']['observations'])
                before_c = _construction(previous['objects'], previous['baseline']['body']['profiles'][0])
                delta = {'parent': parent, 'architecture': {'introduced': introduced_a[:20], 'resolved': resolved_a[:20]}}
                if construction is not None and before_c is not None:
                    introduced_c, resolved_c = _compare(before_c['diagnostics'], construction['diagnostics'])
                    delta['construction'] = {'before': len(before_c['diagnostics']), 'after': len(construction['diagnostics']),
                                             'introduced': [_explained(d) for d in introduced_c[:20]], 'resolved': resolved_c[:20]}
                state['health']['since_parent'] = delta
            except (Forbidden, NotFound):
                state['health']['since_parent'] = {'parent': parent, 'status': 'PARENT_UNREADABLE'}
        steps += [_step('Structural checks by family (MECE exclusivity, exhaustiveness, DDD context coherence)', 'air_inspect_architecture', {'baseline': s, 'detail': 'SUMMARY'}),
                  _step('Construction traceability, with each blocker explained', 'air_validate_construction', {'baseline': s})]
        steps += [_step('Replay the lifecycle rules that the change touches', 'air_replay_state_machine',
                        {'baseline': s, 'machine': '<snapshot of ' + m['id'] + ' r' + str(m['revision']) + '>', 'stimuli': '<scenario>'}) for m in machines[:4]]
        steps.append(_step('Read a schema file directly from the dossier', 'air_browse_baseline', {'baseline': s, 'types': ['air.DataSchema'], 'schemas': True, 'text': '<name>'}))
    elif intent == 'IMPACT':
        if stale:
            steps.append(_step('Trace which of your objects depend on the borrowed objects that moved', 'air_impact',
                               {'baselines': [s], 'targets': [{'id': x['id'], 'revision': x['pinned_revision']} for x in stale[:50]]}))
            steps.append(_step('Prepare the realignment: borrowed objects at their latest readable revision with their closure, and your objects re-pinned',
                               'air_rebase_drafts', {'base': s, 'realign_borrowed': True},
                               'Add your own content drafts in objects when the change also needs them'))
        else:
            steps.append(_step('Borrowed objects are at their latest revision; trace a planned change instead', 'air_impact', {'baselines': [s], 'targets': '<objects that will change>'}))
    elif intent == 'DELIVER':
        steps.append(_step('Read declared programmes, architecture projects and remaining design tasks at this pin; add authorized sibling pins for the global transformation',
                           'air_query_transformation', {'baselines': [s], 'limit': 50}))
        steps.append(_step('Read the current Management Summary before the detailed dossier; regenerate it after each frozen change',
                           'air_compile_deliverables', {'title': baseline['meta']['name'], 'baselines': [s], 'only': ['00-management-summary']}))
        steps += [_step('OpenAPI description of ' + b['name'], 'air_compile_openapi', {'baseline': s, 'binding': b['reference'],
                                                                                      'info': {'title': b['name'], 'version': str(s['revision'])}})
                  for b in bindings if b.get('transport') == 'HTTP'][:12]
        steps.append(_step('Deliverables pack (37 documents with diagrams): list them with their digests, then read the ones you need; 32 to 37 hold scenarios, regression, compliance, NFRs, AI estimate and roadmaps',
                           'air_compile_deliverables', {'title': baseline['meta']['name'], 'baselines': [s], 'content': 'DIGESTS'}))
        steps.append(_step('Read one deliverable in full', 'air_compile_deliverables', {'title': baseline['meta']['name'], 'baselines': [s], 'only': ['<e.g. 34-matrice-conformite>']}))
        steps.append(_step('Executive presentation outline (action titles and sources); pin sibling and kernel baselines together for a programme', 'air_compile_presentation',
                           {'title': baseline['meta']['name'], 'baselines': [s], 'audience': 'STEERING'}))
    report = {'engine': ENGINE, 'intent': intent, 'registry_written': False, **state, 'next_steps': steps,
              'limits': ['Checks are structural; behaviour, security and business truth are not verified.',
                         'Commitments (admission, activation, closure, publication) stay human and authenticated.']}
    report['report_digest'] = artifact_digest(report)
    return _bounded(report, 'Guide')


# ---------------------------------------------------------------- the two writes, by reference

def _prepared(store, principal, identifier, policy):
    row = store.get_record(identifier)
    if row is None or row['kind'] != 'prepared_change':
        raise NotFound('No prepared change has this identifier', {'id': identifier})
    if row['actor'] != principal['subject']:
        raise Forbidden('A prepared change is used by the subject that prepared it', [{'id': identifier}])
    ScopedStore(store, principal, policy).check_read([row['payload']['base']])
    for obj in row['payload']['objects']:
        policy.require(principal, 'read', obj['meta']['namespace'])
    return row['payload']


def deposit_prepared(store, principal, policy, request):
    """Store the exact bundle air_rebase_drafts prepared; the server validates it again as any deposit."""
    check_schema(request, DEPOSIT_REQUEST)
    payload = _prepared(store, principal, request['prepared_change'], policy)
    receipt = ScopedStore(store, principal, policy).put_bundle(payload['objects'], principal['subject'])
    return {**receipt, 'engine': ENGINE, 'prepared_change': request['prepared_change'], 'objects': len(receipt['objects']),
            'created': sum(1 for r in receipt['objects'] if r['created']),
            'next_steps': [_step('Freeze the next baseline revision, naming this change', 'air_freeze_prepared',
                                 {'prepared_change': request['prepared_change'], 'name': '<name>', 'description': '<what this change does>'})]}


def freeze_prepared(store, principal, policy, request):
    check_schema(request, FREEZE_REQUEST)
    payload = _prepared(store, principal, request['prepared_change'], policy)
    baseline_request = deepcopy(payload['baseline_request'])
    for field in ('name', 'description'):
        if field in request: baseline_request['meta'][field] = request[field]
    result = ScopedStore(store, principal, policy).create_baseline(baseline_request, principal['subject'])
    snapshot = {**exact(result['baseline']), 'digest': result['digest']}
    return {'engine': ENGINE, 'prepared_change': request['prepared_change'], 'baseline': snapshot, 'created': result['created'],
            'validation': {'valid': result['validation']['valid'], 'diagnostics': result['validation']['diagnostics'][:50]},
            'published': False,
            'next_steps': [_step('Verify the new revision', 'air_guide', {'baseline': snapshot, 'intent': 'REVIEW'}),
                           _step('Produce the deliverables', 'air_guide', {'baseline': snapshot, 'intent': 'DELIVER'})]}
