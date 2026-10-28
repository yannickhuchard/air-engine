"""Persistent, bounded design orchestration. The caller's model supplies the reasoning."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from sqlalchemy import select
from air import agent, readiness
from air.access import ScopedStore, Forbidden
from air.builder_handoff import commit_guard
from air.core import DATA_TYPES, URI, TEXT, INSTANT, record, validate, digest, reference_slots, BUILD_PROFILE, DELIVERY_PROFILE
from air.expr import artifact_digest
from air.foundation import check_schema, exact, key, InvalidModel
from air.packages import reference
from air.projections import SNAPSHOT, snapshot
from air.storage import Conflict, service_records, revisions

ENGINE = 'air.architecture-completion/1'
REF = record({'id': URI, 'digest': SNAPSHOT['properties']['digest']})
KEY = {'type': 'string', 'minLength': 1, 'maxLength': 128}
TYPES = sorted(set(DATA_TYPES) - {'air.Baseline', 'air.ChangeSet', 'air.View'})
CREATE = record({'idempotency_key': KEY, 'baseline': SNAPSHOT, 'scope': SNAPSHOT,
    'objectives': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 32, 'uniqueItems': True},
    'purpose': TEXT})
READ = record({'run': REF, 'prepared_change': agent.PREPARED}, ['run'])
COMMAND = {'run': REF, 'checkpoint': REF, 'idempotency_key': KEY}
GRANT = record({'executors': {'type': 'array', 'items': {**TEXT, 'maxLength': 256}, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True},
    'allowed_types': {'type': 'array', 'items': {'enum': TYPES}, 'minItems': 1, 'maxItems': len(TYPES), 'uniqueItems': True},
    'max_cycles': {'type': 'integer', 'minimum': 1, 'maximum': 200},
    'max_objects': {'type': 'integer', 'minimum': 1, 'maximum': 10000},
    'max_no_progress': {'type': 'integer', 'minimum': 1, 'maximum': 10}, 'expires_at': INSTANT,
    'approved_prepared': {'type': 'array', 'items': agent.PREPARED, 'maxItems': 64, 'uniqueItems': True}},
    ['executors', 'allowed_types', 'max_cycles', 'max_objects', 'max_no_progress', 'expires_at'])
AUTHORIZE = record({**COMMAND, 'mandate': GRANT, 'rationale': TEXT})
QUESTION = record({'id': KEY, 'kind': {'enum': ['BUSINESS_DECISION', 'CONFLICT', 'QUALIFICATION', 'UNSUPPORTED_ASSUMPTION']},
    'question': TEXT, 'references': {'type': 'array', 'items': SNAPSHOT, 'minItems': 1, 'maxItems': 16, 'uniqueItems': True}})
ADVANCE = record({**COMMAND, 'action': {'enum': ['CHECKPOINT', 'ESCALATE', 'RESOLVE', 'RESUME', 'ADOPT_BASELINE']},
    'summary': TEXT, 'question': QUESTION, 'question_id': KEY, 'answer': TEXT, 'baseline': SNAPSHOT,
    'prepared_change': agent.PREPARED},
    [*COMMAND, 'action', 'summary'])
APPLY = record({**COMMAND, 'prepared_change': agent.PREPARED, 'name': TEXT, 'description': TEXT})
STOP = record({**COMMAND, 'state': {'enum': ['PAUSED', 'CANCELLED']}, 'rationale': TEXT})
MATERIAL = {'air.StakeholderParticipation', 'air.ScopeGate', 'air.OperationalEvidence', 'air.Decision', 'air.Evidence', 'air.VerificationRun', 'air.AuthorityScope',
    'air.Risk', 'air.ComplianceMapping', 'air.RuntimeObservation', 'air.FinancialPlan',
    'air.SourcingStrategy', 'air.Waiver'}

# Existing commitments cannot be weakened under a broad technical-type mandate.
# Reference revision churn is ignored here; changing the referenced identity is not.
PROTECTED_FIELDS = {
    'air.Function': ('inputs', 'outputs', 'preconditions', 'postconditions', 'effects', 'exceptions', 'atomic', 'satisfies'),
    'air.FailureMode': ('trigger', 'effect', 'detection', 'response', 'recovery_condition'),
    'air.DataLifecycleSpecification': ('table', 'owner', 'unique_keys', 'indexes', 'retention', 'migration', 'rollback'),
    'air.DossierContext': ('profiles', 'exclusions', 'assurance_plan'),
    'air.Constraint': ('mode', 'condition', 'scope', 'exception_policy', 'verification'),
    'air.Control': ('objective', 'mechanism', 'scope', 'owner', 'verification', 'evidence_requirements'),
    'air.Policy': ('intent', 'issuer', 'applicability', 'constraints', 'review_policy'),
    'air.Obligation': ('source_text', 'interpretation', 'applicability_decision', 'controls', 'review_due'),
    'air.Requirement': ('statement', 'kind', 'priority', 'applicability', 'acceptance'),
    'air.QualityRequirement': ('statement', 'category', 'priority', 'target', 'scope', 'verification_method'),
    'air.AcceptanceCriterion': ('condition', 'verification_method', 'acceptance_authority', 'cases'),
    'air.VerificationCase': ('target', 'method', 'inputs', 'oracle', 'acceptance', 'independence_basis'),
    'air.SemanticContract': ('operations', 'participants', 'authorization', 'compatibility_policy', 'state_effects', 'error_contract', 'quality'),
    'air.InterfaceSpecification': ('binding', 'operations', 'compatibility'),
}


def now(): return datetime.now(timezone.utc)
def pin(obj): return {**exact(obj), 'digest': digest(obj)}
def identifier(kind, value): return 'urn:air:' + kind + ':' + hashlib.sha256(value.encode()).hexdigest()
def event_prefix(run): return 'urn:air:completion-event:' + run['id'].rsplit(':', 1)[-1] + ':'


def _intent(obj):
    normalized = deepcopy(obj)
    for _, ref, _ in reference_slots(normalized): ref['revision'] = 0; ref.pop('digest', None)
    return {'type': obj['meta']['type'], 'body': normalized['body']}


def _material(kind, body, previous):
    if previous:
        old = previous['body']
        current = body
        if 'meta' in previous:
            # Normalize only typed AIR reference slots. API schemas and examples
            # may also contain id/revision/digest keys, which are business data.
            try:
                old = _intent(previous)['body']
                current = _intent({**previous, 'body': body})['body']
            except (KeyError, TypeError, ValueError):
                return True
        if any(old.get(field) != current.get(field) for field in PROTECTED_FIELDS.get(kind, ())):
            return True
    if kind in MATERIAL:
        # Mapping a planned control to its design blocks is technical work.
        if kind == 'air.ComplianceMapping' and body.get('status') == 'PLANNED' and (
            previous is None or previous['body'].get('status') == 'PLANNED'): return False
        return True
    if kind == 'air.Assertion':
        return body.get('epistemic_status') in ('ESTABLISHED', 'REFUTED') or (
            previous is not None and previous['body'].get('epistemic_status') != body.get('epistemic_status'))
    if kind == 'air.Unknown':
        return body.get('state') == 'RESOLVED' or (previous is not None and any(
            body.get(field) != previous['body'].get(field) for field in ('state', 'blocking_policy')))
    return kind in ('air.ArchitectureProject', 'air.TransformationProgramme') and body.get('status') in ('COMPLETED', 'CANCELLED')


def _record_progress(data, criteria):
    """A changed digest is not improvement. Count only non-regressing gate closure."""
    current = {c['code']: c['status'] for c in criteria}
    previous = data.get('last_readiness_progress')
    improved = previous is None or (set(previous) <= set(current) and
        all(current.get(k) == 'MET' for k, v in previous.items() if v == 'MET') and
        any(current.get(k) == 'MET' for k, v in previous.items() if v == 'NOT_MET'))
    data['no_progress'] = 0 if improved else data['no_progress'] + 1
    if improved: data['last_readiness_progress'] = current
    data['last_evaluation'] = artifact_digest(criteria)


def _root(store, principal, policy, ref):
    row = store.get_record(ref['id'])
    if row is None or row['kind'] != 'completion_run': raise InvalidModel('Completion run unavailable')
    policy.require(principal, 'read', row['scope'])
    if reference(row) != ref: raise Conflict('Completion run digest differs')
    return row


def _latest(store, conn, run):
    row_id = conn.execute(select(service_records.c.id).where(service_records.c.id.startswith(event_prefix(run))).order_by(service_records.c.id.desc()).limit(1)).scalar_one()
    row = store._get_record(conn, row_id)
    if row['kind'] not in ('completion_event', 'completion_stop'): raise InvalidModel('Completion checkpoint kind differs')
    return row


def _load(store, principal, policy, ref):
    root = _root(store, principal, policy, ref)
    with store.engine.connect() as conn: event = _latest(store, conn, ref)
    return root, event


def _context(store, principal, policy, baseline, declaration=None):
    exported = snapshot(ScopedStore(store, principal, policy), baseline)
    if declaration:
        origin = snapshot(ScopedStore(store, principal, policy), declaration['baseline'])
        if exported['baseline']['body']['profiles'] != origin['baseline']['body']['profiles']:
            raise InvalidModel('The completion scope cannot silently change profile')
        old = {o['meta']['id']: o for o in origin['objects']}; current = {o['meta']['id']: o for o in exported['objects']}
        for ref in [declaration['scope'], *declaration['objectives']]:
            previous = old.get(ref['id']); obj = current.get(ref['id'])
            if not previous or not obj or _intent(previous) != _intent(obj):
                raise InvalidModel('Agreed scope or objective changed; authorize a new completion scope')
    return exported


def _evaluation(store, principal, policy, baseline):
    gate = readiness.assess_readiness(store, principal, policy, {'baseline': baseline})
    from air.acceptance import walk_baseline
    walk = walk_baseline(store, principal, policy, {'baseline': baseline})
    from air.interface_contracts import inspect_members
    exported = snapshot(ScopedStore(store, principal, policy), baseline)
    interfaces = inspect_members(store, principal, policy, exported)
    tasks = []
    for criterion in gate['criteria']:
        if criterion['status'] != 'NOT_MET': continue
        human = criterion.get('owner') == 'human'
        detail = criterion.get('detail', {})
        if criterion['code'] == 'VERIFICATION' and detail.get('design_cases_open'):
            human = not detail.get('tests_not_planned_in_a_unit') and not detail.get('failed_or_conflicting_runtime_tests')
            for case in detail['design_cases_open']:
                if case['status'] in ('NOT_RUN', 'FAILED', 'INCONCLUSIVE'):
                    tasks.append({'id': 'DESIGN_EVIDENCE:' + case['name'], 'kind': 'DESIGN',
                        'title': 'Prepare or reproduce design evidence for ' + case['name'], 'next_step': 'air_browse_baseline', 'priority': 25})
        tasks.append({'id': criterion['code'], 'kind': 'QUALIFICATION' if human else 'DESIGN',
            'title': criterion['title'], 'next_step': criterion['to_close'], 'priority': 90 if human else 20,
            'source': {'engine': gate['engine'], 'report_digest': gate['report_digest']}})
    if any(s['verdict'] != 'PASS' for s in walk.get('scenarios', [])):
        tasks.append({'id': 'SCENARIO_WALK', 'kind': 'DESIGN', 'title': 'Resolve failing or inconclusive acceptance paths',
            'next_step': 'air_walk_scenarios', 'priority': 15})
    if any(i['result'] != 'PASS_DESIGN_EXAMPLES' for i in interfaces):
        tasks.append({'id': 'INTERFACE_EXAMPLES', 'kind': 'DESIGN', 'title': 'Resolve blocked interface examples',
            'next_step': 'air_compile_interface_suite', 'priority': 15})
    fingerprint = artifact_digest(gate['criteria'])
    return {'readiness': gate, 'tasks': sorted(tasks, key=lambda t: (t['priority'], t['id'])),
        'scenario_summary': walk.get('summary', {}), 'interfaces': interfaces, 'progress_fingerprint': fingerprint}


def _computed_simulation(store, principal, policy, obj, baseline):
    """Only a reproduced engine result can bypass the explicit-change proof guard."""
    if obj['body'].get('method') != 'SIMULATION' or 'report' not in obj['body']: return False
    from air import artifacts
    import json
    from air.parsing import pairs
    descriptor = obj['body']['report']
    manifest = store.get_record(descriptor['locator'])
    if not manifest or manifest['kind'] != 'artifact_manifest': return False
    lookup = {'artifact': reference(manifest)}
    metadata = artifacts.describe(store, principal, policy, lookup)
    if metadata['artifact_reference'] != descriptor or metadata['size'] > artifacts.JSON_MAX_SIZE: return False
    # Engine reports contain measured/modelled floating-point results; model-input
    # parsing deliberately rejects those and is not the report codec.
    try: saved = json.loads(artifacts.download(store, principal, policy, lookup)[1].decode('utf-8'), object_pairs_hook=pairs)
    except (ValueError, InvalidModel, RecursionError): return False
    if not isinstance(saved, dict) or saved.get('baseline') != baseline: return False
    scenario = saved.get('scenario')
    if not scenario or not obj['body'].get('scenario') or key(scenario) != key(obj['body']['scenario']): return False
    source = snapshot(ScopedStore(store, principal, policy), baseline)
    scenario_obj = next((o for o in source['objects'] if key(exact(o)) == key(scenario)), None)
    if not scenario_obj or scenario_obj['body'].get('verification_case') != obj['body']['case']: return False
    reproduced = readiness.simulate_scenario(store, principal, policy, {'baseline': baseline, 'scenario': scenario})
    return (artifact_digest(saved) == artifact_digest(reproduced) and
        obj['body']['result'] == {'PASS': 'PASS', 'FAIL': 'FAIL'}.get(reproduced['verdict'], 'INCONCLUSIVE') and
        obj['body']['proof_level'] == reproduced['proof_level'])


def _blocked_questions(store, principal, policy, root, data, payload):
    objects = snapshot(ScopedStore(store, principal, policy), data['baseline'])['objects']
    old = {o['meta']['id']: o for o in objects}
    changed = {o['meta']['id'] for o in payload['objects'] if o['meta']['id'] not in old or digest(old[o['meta']['id']]) != digest(o)}
    index = {**old, **{o['meta']['id']: o for o in payload['objects']}}
    def closure(ids):
        pending = list(ids); seen = set()
        while pending:
            identity = pending.pop()
            if identity in seen: continue
            seen.add(identity)
            if len(seen) > 4096: raise InvalidModel('Completion question dependency closure exceeds 4096 objects')
            if identity in index: pending.extend(ref['id'] for _, ref, _ in reference_slots(index[identity]))
        return seen
    dependencies = closure(changed)
    return [q['id'] for q in data['questions'] if q['state'] == 'OPEN' and (
        root['payload']['request']['scope']['id'] in {r['id'] for r in q['references']} or
        dependencies & {r['id'] for r in q['references']} or closure(r['id'] for r in q['references']) & changed)]


def _mandate(root, data, principal, policy):
    grant = data.get('grant')
    if not grant: return 'AWAITING_AUTHORIZATION'
    if grant['policy_digest'] != policy.digest: return 'AUTHORIZATION_CHANGED'
    if datetime.fromisoformat(grant['mandate']['expires_at']) <= now(): return 'AUTHORIZATION_EXPIRED'
    if not policy.allows({'subject': grant['actor'], 'role': grant['role']}, 'authorize_design', root['scope']): return 'AUTHORIZATION_REVOKED'
    if principal['subject'] not in grant['mandate']['executors']: return 'EXECUTOR_NOT_AUTHORIZED'
    if not policy.allows(principal, 'write', root['scope']): return 'WRITE_NOT_AUTHORIZED'
    if data['cycles'] >= grant['mandate']['max_cycles'] or data['objects_written'] >= grant['mandate']['max_objects']: return 'BUDGET_EXHAUSTED'
    if data['no_progress'] >= grant['mandate']['max_no_progress']: return 'NEEDS_REPLAN'
    return 'ACTIVE'


def _current_head(store, conn, baseline):
    latest = conn.execute(select(revisions.c.revision).where(revisions.c.id == baseline['id']).order_by(revisions.c.revision.desc()).limit(1)).scalar_one()
    if latest != baseline['revision']: raise Conflict('Baseline moved; read the run and explicitly adopt the new baseline')


def _event(store, conn, run, root, principal, data, operation, request, kind='completion_event'):
    if data['sequence'] > 1024: raise InvalidModel('Completion history exceeds 1024 checkpoints; create a successor run')
    row = store._record_once(conn, event_prefix(run) + str(data['sequence']).zfill(4), kind,
        root['scope'], principal['subject'], {'run': run, 'operation': operation, 'data': data})['record']
    reply = {'engine': ENGINE, 'run': run, 'checkpoint': reference(row), 'sequence': data['sequence'], 'baseline': data['baseline'],
        'operation': operation, 'authorization_granted': False, 'business_runtime_executed': False}
    command_id = identifier('completion-command', run['id'] + '\0' + principal['subject'] + '\0' + request['idempotency_key'])
    store._record_once(conn, command_id, 'completion_stop' if kind == 'completion_stop' else 'completion_command', root['scope'], principal['subject'],
        {'request': request, 'reply': reply})
    return reply


def _begin(store, conn, principal, policy, settings, request, action='write'):
    commit_guard(store, conn, principal, policy, settings)
    root = _root(store, principal, policy, request['run']); policy.require(principal, action, root['scope'])
    command_id = identifier('completion-command', request['run']['id'] + '\0' + principal['subject'] + '\0' + request['idempotency_key'])
    retry = store._get_record(conn, command_id)
    if retry:
        if retry['payload']['request'] != request: raise Conflict('Completion idempotency key reused for different content')
        return root, None, retry['payload']['reply']
    event = _latest(store, conn, request['run'])
    if reference(event) != request['checkpoint']: raise Conflict('Completion checkpoint moved; resume before retrying')
    if event['payload']['data']['lifecycle'] == 'CANCELLED': raise Conflict('Completion run was cancelled')
    return root, deepcopy(event['payload']['data']), None


def _retry(store, principal, policy, request, action='write'):
    root = _root(store, principal, policy, request['run']); policy.require(principal, action, root['scope'])
    prior = store.get_record(identifier('completion-command', request['run']['id'] + '\0' + principal['subject'] + '\0' + request['idempotency_key']))
    if prior:
        if prior['payload']['request'] != request: raise Conflict('Completion idempotency key reused for different content')
        return prior['payload']['reply']


def create(store, principal, policy, request, settings=None):
    check_schema(request, CREATE)
    exported = _context(store, principal, policy, request['baseline']); home = exported['baseline']['meta']['namespace']
    policy.require(principal, 'write', home)
    if exported['baseline']['body']['profiles'][0] not in (DELIVERY_PROFILE, BUILD_PROFILE):
        raise InvalidModel('Completion requires a delivery or build-design profile')
    index = {key(exact(o)): o for o in exported['objects']}
    for ref, kinds in [(request['scope'], ('air.Scope',)), *((o, ('air.Goal', 'air.Requirement')) for o in request['objectives'])]:
        obj = index.get(key(ref))
        if not obj or pin(obj) != ref or obj['meta']['type'] not in kinds or obj['meta']['namespace'] != home:
            raise InvalidModel('Scope and objectives must be exact owned baseline members')
    identifier_ = identifier('completion', principal['subject'] + '\0' + request['idempotency_key'])
    with store.write() as conn:
        commit_guard(store, conn, principal, policy, settings)
        result = store._record_once(conn, identifier_, 'completion_run', home, principal['subject'], {'request': request})
        run = reference(result['record'])
        if result['created']:
            _current_head(store, conn, request['baseline'])
            data = {'sequence': 0, 'baseline': request['baseline'], 'lifecycle': 'ACTIVE', 'cycles': 0,
                'objects_written': 0, 'no_progress': 0, 'grant': None, 'questions': [], 'pending_change': None,
                'last_evaluation': None, 'summary': request['purpose']}
            store._record_once(conn, event_prefix(run) + '0000', 'completion_event', home, principal['subject'],
                {'run': run, 'operation': 'CREATE', 'data': data})
    return {'engine': ENGINE, 'run': run, 'created': result['created'], 'resume_with': 'air_read_completion_run', 'authorization_granted': False}


def read(store, principal, policy, request):
    check_schema(request, READ)
    root, event = _load(store, principal, policy, request['run']); data = event['payload']['data']
    _context(store, principal, policy, data['baseline'], root['payload']['request'])
    evaluation = _evaluation(store, principal, policy, data['baseline'])
    latest = store.head(data['baseline']['id'])['latest_revision']
    execution = data['lifecycle'] if data['lifecycle'] != 'ACTIVE' else _mandate(root, data, principal, policy)
    if latest != data['baseline']['revision'] and execution not in ('CANCELLED', 'PAUSED'): execution = 'BASELINE_MOVED'
    questions = [q for q in data['questions'] if q['state'] == 'OPEN']
    tasks = evaluation['tasks']
    scope_blocked = any(root['payload']['request']['scope']['id'] in {r['id'] for r in q['references']} for q in questions)
    ready = latest == data['baseline']['revision'] and evaluation['readiness']['result'] == 'READY_TO_BUILD' and not tasks and not questions
    outcome = 'READY_TO_BUILD' if ready else 'BLOCKED_ON_DECISION' if scope_blocked else 'REQUIRES_MORE_DESIGN' if any(t['kind'] == 'DESIGN' for t in tasks) else 'BLOCKED_ON_DECISION'
    action = {'tool': 'air_guide', 'arguments': {'baseline': data['baseline'], 'intent': 'CHANGE'}}
    if ready: action = {'tool': 'air_compile_deliverables', 'arguments': {'baselines': [data['baseline']], 'title': root['payload']['request']['purpose'], 'content': 'DIGESTS'}}
    elif execution != 'ACTIVE': action = {'required': execution, 'resume_tool': 'air_read_completion_run'}
    elif questions and (scope_blocked or not any(t['kind'] == 'DESIGN' for t in tasks)): action = {'required': 'AUTHORIZED_DECISION', 'questions': questions}
    elif not any(t['kind'] == 'DESIGN' for t in tasks): action = {'required': 'QUALIFICATION', 'tasks': tasks}
    elif data.get('pending_change'): action = {'tool': 'air_read_completion_run',
        'arguments': {'run': request['run'], 'prepared_change': data['pending_change']}}
    report = {'engine': ENGINE, 'run': request['run'], 'checkpoint': reference(event), 'baseline': data['baseline'],
        'declaration': root['payload']['request'], 'execution_state': execution, 'outcome': outcome,
        'sequence': data['sequence'], 'cycles': data['cycles'], 'objects_written': data['objects_written'],
        'no_progress': data['no_progress'], 'questions': data['questions'], 'evaluation': evaluation,
        'mandate': data['grant'], 'summary': data['summary'], 'pending_change': data.get('pending_change'), 'next_action': action,
        'registry_written': False, 'authorization_granted': False, 'business_runtime_executed': False,
        'model_kept_running': False, 'independent_review_inferred': False}
    if 'prepared_change' in request:
        proposed = store.get_record(request['prepared_change'])
        if proposed and proposed['kind'] == 'prepared_change' and proposed['actor'] != principal['subject']:
            policy.require(principal, 'authorize_design', root['scope'])
            if proposed['scope'] != root['scope'] or proposed['payload']['base'] != data['baseline']:
                raise InvalidModel('Proposal is outside this completion scope')
            for obj in proposed['payload']['objects']:
                policy.require(principal, 'read', obj['meta']['namespace'])
                for _, ref, _ in reference_slots(obj):
                    if store.head(ref['id']): ScopedStore(store, principal, policy).get(ref['id'], ref['revision'])
            report['proposal_preview'] = {'prepared_change': request['prepared_change'], 'actor': proposed['actor'],
                'payload_digest': artifact_digest(proposed['payload']), 'objects': proposed['payload']['objects'],
                'qualification_inferred': False}
            from air.completeness import context_budget
            context_budget(report, 1048576)
            return {**report, 'report_digest': artifact_digest(report)}
        payload, candidate, issues = _candidate(store, principal, policy, root, data, request['prepared_change'])
        report['candidate'] = {'prepared_change': request['prepared_change'], 'readiness': candidate,
            'automatic_apply_eligible': execution == 'ACTIVE' and not issues and not _blocked_questions(store, principal, policy, root, data, payload), 'material_changes': issues,
            'blocking_questions': _blocked_questions(store, principal, policy, root, data, payload),
            'objects': len(payload['objects'])}
    from air.completeness import context_budget
    context_budget(report, 1048576)
    return {**report, 'report_digest': artifact_digest(report)}


def authorize(store, principal, policy, request, settings=None):
    check_schema(request, AUTHORIZE)
    retry = _retry(store, principal, policy, request, 'authorize_design')
    if retry: return retry
    expiry = datetime.fromisoformat(request['mandate']['expires_at'])
    if not now() < expiry <= now() + timedelta(days=31): raise InvalidModel('Design mandate expiry must be within 31 days')
    with store.write() as conn:
        root, data, retry = _begin(store, conn, principal, policy, settings, request, 'authorize_design')
        if retry: return retry
        for identifier_ in request['mandate'].get('approved_prepared', []):
            proposal = store._get_record(conn, identifier_)
            if not proposal or proposal['kind'] != 'prepared_change' or proposal['scope'] != root['scope'] or proposal['payload']['base'] != data['baseline']:
                raise InvalidModel('Explicit approvals must name exact prepared changes for this baseline')
            if proposal['actor'] not in request['mandate']['executors']: raise InvalidModel('Approved proposal author is outside the executor mandate')
            for obj in proposal['payload']['objects']: policy.require(principal, 'read', obj['meta']['namespace'])
        data['grant'] = {'actor': principal['subject'], 'role': principal['role'], 'policy_digest': policy.digest,
            'mandate': request['mandate'], 'rationale': request['rationale'], 'human_identity_attested': False}
        data['no_progress'] = 0; data['sequence'] += 1
        return _event(store, conn, request['run'], root, principal, data, 'AUTHORIZE', request)


def _executor(root, data, principal):
    allowed = [root['actor']] + (data['grant']['mandate']['executors'] if data.get('grant') else [])
    if principal['subject'] not in allowed: raise Forbidden('Subject cannot advance this completion run')


def advance(store, principal, policy, request, settings=None):
    check_schema(request, ADVANCE)
    retry = _retry(store, principal, policy, request)
    if retry: return retry
    root, old = _load(store, principal, policy, request['run']); current = old['payload']['data']
    target = request.get('baseline', current['baseline'])
    if request['action'] == 'ADOPT_BASELINE':
        if 'baseline' not in request or target['id'] != current['baseline']['id'] or target['revision'] <= current['baseline']['revision']:
            raise InvalidModel('Adoption requires a newer revision of the same baseline')
        _context(store, principal, policy, target, root['payload']['request'])
    elif 'baseline' in request: raise InvalidModel('Only ADOPT_BASELINE accepts a new baseline')
    if 'prepared_change' in request:
        if request['action'] != 'CHECKPOINT': raise InvalidModel('Only CHECKPOINT accepts a pending prepared change')
        if agent._prepared(store, principal, request['prepared_change'], policy)['base'] != current['baseline']:
            raise Conflict('Pending proposal targets another baseline')
    evaluation = _evaluation(store, principal, policy, target)
    with store.write() as conn:
        root, data, retry = _begin(store, conn, principal, policy, settings, request)
        if retry: return retry
        if request['action'] == 'RESOLVE': policy.require(principal, 'authorize_design', root['scope'])
        else: _executor(root, data, principal)
        if request['action'] == 'ESCALATE':
            q = request.get('question')
            if not q: raise InvalidModel('Escalation requires a question and exact references')
            _export = snapshot(ScopedStore(store, principal, policy), data['baseline'])
            members = {key(exact(o)): pin(o) for o in _export['objects']}
            if any(members.get(key(ref)) != ref for ref in q['references']): raise InvalidModel('Question references must belong to the current baseline')
            if any(x['id'] == q['id'] for x in data['questions']): raise Conflict('Question already exists')
            if len(data['questions']) >= 64: raise InvalidModel('At most 64 questions per run')
            data['questions'].append({**q, 'state': 'OPEN', 'raised_by': principal['subject'], 'baseline': data['baseline']})
        elif request['action'] == 'RESOLVE':
            question = next((q for q in data['questions'] if q['id'] == request.get('question_id')), None)
            if not question or question['state'] != 'OPEN' or not request.get('answer'): raise InvalidModel('Resolve an open question with an explicit answer')
            question.update(state='ANSWERED', answer=request['answer'], answered_by=principal['subject'], policy_digest=policy.digest)
        elif request['action'] == 'RESUME': data['lifecycle'] = 'ACTIVE'
        elif request['action'] == 'ADOPT_BASELINE':
            _current_head(store, conn, target); data['baseline'] = target; data['pending_change'] = None
        if 'prepared_change' in request: data['pending_change'] = request['prepared_change']
        _record_progress(data, evaluation['readiness']['criteria'])
        data['summary'] = request['summary']; data['sequence'] += 1
        return _event(store, conn, request['run'], root, principal, data, request['action'], request)


def _candidate(store, principal, policy, root, data, prepared):
    payload = agent._prepared(store, principal, prepared, policy)
    if payload['base'] != data['baseline']: raise Conflict('Prepared change targets another completion checkpoint baseline')
    declaration = root['payload']['request']; baseline = _context(store, principal, policy, data['baseline'], declaration)
    if payload['baseline_request']['profile'] != baseline['baseline']['body']['profiles'][0]: raise InvalidModel('Completion cannot silently change profile')
    old = {o['meta']['id']: o for o in baseline['objects']}; issues = []
    unchanged_inputs = all(o['meta']['type'] == 'air.VerificationRun' or
        (o['meta']['id'] in old and _intent(o) == _intent(old[o['meta']['id']])) for o in payload['objects'])
    grant = data.get('grant'); mandate = grant['mandate'] if grant else {}
    approved = prepared in mandate.get('approved_prepared', [])
    for obj in payload['objects']:
        previous = old.get(obj['meta']['id'])
        if previous and digest(previous) == digest(obj): continue
        if obj['meta']['namespace'] != root['scope']: raise Forbidden('Completion cannot change another project')
        if obj['meta']['type'] not in mandate.get('allowed_types', []): issues.append({'object': exact(obj), 'reason': 'TYPE_OUTSIDE_MANDATE'})
        kind = obj['meta']['type']; body = obj['body']
        material = _material(kind, body, previous)
        if kind == 'air.VerificationRun' and unchanged_inputs:
            try: reproduced = _computed_simulation(store, principal, policy, obj, data['baseline'])
            except Forbidden: raise
            except (ValueError, KeyError, TypeError): reproduced = False
            if reproduced: material = False
        if previous and any(obj['meta'].get(f) != previous['meta'].get(f) for f in ('classification', 'owner')):
            material = True
        if obj['meta']['id'] in {declaration['scope']['id'], *(r['id'] for r in declaration['objectives'])}:
            if previous is None or _intent(previous) != _intent(obj):
                raise InvalidModel('Agreed scope or objective content changed; start a new explicitly scoped run')
        if material and not approved: issues.append({'object': exact(obj), 'reason': 'EXPLICIT_CHANGE_APPROVAL_REQUIRED'})
    if not validate(payload['objects'])['valid']: raise InvalidModel('Prepared completion drafts are invalid')
    validation = agent.validate_drafts(store, principal, policy, {'prepared_change': prepared})
    introduced = validation.get('candidate', {}).get('architecture', {}).get('introduced', [])
    if introduced: issues.append({'reason': 'INTRODUCED_ARCHITECTURE_VIOLATIONS', 'diagnostics': introduced})
    return payload, readiness.assess_readiness(store, principal, policy, {'prepared_change': prepared}), issues


def apply(store, principal, policy, request, settings=None):
    check_schema(request, APPLY)
    root, old = _load(store, principal, policy, request['run']); before = old['payload']['data']
    # Idempotent retry is resolved before inspecting the old prepared base.
    command_id = identifier('completion-command', request['run']['id'] + '\0' + principal['subject'] + '\0' + request['idempotency_key'])
    prior = store.get_record(command_id)
    if prior:
        policy.require(principal, 'write', root['scope'])
        if prior['payload']['request'] != request: raise Conflict('Completion idempotency key reused')
        return prior['payload']['reply']
    current_evaluation = _evaluation(store, principal, policy, before['baseline'])
    if current_evaluation['readiness']['result'] == 'READY_TO_BUILD' and not current_evaluation['tasks']:
        raise Conflict('Architecture is already ready in this scope; create a new run for additional design')
    payload, candidate, issues = _candidate(store, principal, policy, root, before, request['prepared_change'])
    if issues: raise InvalidModel('Prepared change requires authorization', {'material_changes': issues})
    if before['lifecycle'] != 'ACTIVE' or _mandate(root, before, principal, policy) != 'ACTIVE': raise Forbidden('An active bounded design mandate is required')
    if _blocked_questions(store, principal, policy, root, before, payload): raise Conflict('Resolve the decisions that affect this change before applying it')
    with store.write() as conn:
        root, data, retry = _begin(store, conn, principal, policy, settings, request)
        if retry: return retry
        _executor(root, data, principal)
        if _mandate(root, data, principal, policy) != 'ACTIVE': raise Forbidden('Design mandate is no longer active')
        _current_head(store, conn, data['baseline'])
        if data['objects_written'] + len(payload['objects']) > data['grant']['mandate']['max_objects']: raise InvalidModel('Completion object budget exhausted')
        for obj in payload['objects']:
            policy.require(principal, 'write', obj['meta']['namespace'])
            store._put(conn, obj, principal['subject'])
        baseline_request = deepcopy(payload['baseline_request']); baseline_request['meta'].update(name=request['name'], description=request['description'])
        frozen = store._baseline(conn, baseline_request, principal['subject'])
        data['baseline'] = pin(frozen['baseline']); data['pending_change'] = None
        data['cycles'] += 1; data['objects_written'] += len(payload['objects'])
        _record_progress(data, candidate['criteria'])
        data['sequence'] += 1; data['summary'] = request['description']
        return _event(store, conn, request['run'], root, principal, data, 'APPLY', request)


def stop(store, principal, policy, request, settings=None):
    check_schema(request, STOP)
    with store.write() as conn:
        root, data, retry = _begin(store, conn, principal, policy, settings, request)
        if retry: return retry
        if not policy.allows(principal, 'authorize_design', root['scope']): _executor(root, data, principal)
        data['lifecycle'] = request['state']; data['sequence'] += 1; data['summary'] = request['rationale']
        return _event(store, conn, request['run'], root, principal, data, 'STOP', request, 'completion_stop')


def for_site(store, principal, policy, baseline):
    exported = snapshot(ScopedStore(store, principal, policy), baseline)
    home = exported['baseline']['meta']['namespace']
    with store.engine.connect() as conn:
        ids = conn.execute(select(service_records.c.id).where(service_records.c.kind == 'completion_run', service_records.c.scope == home).order_by(service_records.c.id).limit(33)).scalars().all()
    truncated = len(ids) > 32
    runs = []
    for identifier_ in ids[:32]:
        row = store.get_record(identifier_)
        if row['payload']['request']['baseline']['id'] != baseline['id']: continue
        ref = reference(row); state = read(store, principal, policy, {'run': ref})
        import json
        runs.append({'run': ref, 'checkpoint': state['checkpoint'], 'baseline': state['baseline'],
            'purpose': state['declaration']['purpose'], 'execution_state': state['execution_state'], 'outcome': state['outcome'],
            'sequence': state['sequence'], 'cycles': state['cycles'], 'tasks': state['evaluation']['tasks'], 'questions': state['questions'],
            'matches_export': state['baseline'] == baseline,
            'resume_prompt': 'Use AIR to resume this architecture completion run. Call air_read_completion_run with ' + json.dumps({'run': ref}) + '. Read the current checkpoint, mandate and next tasks. Continue authorized design; escalate only consequential decisions or required qualification. Never invent evidence or approval.'})
    return {'engine': ENGINE, 'baseline': baseline, 'runs': runs, 'coverage': 'BOUNDED' if truncated else 'COMPLETE',
        'limit': 32, 'live_state': False, 'authorization_granted': False}
