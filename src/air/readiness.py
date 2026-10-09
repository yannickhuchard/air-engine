"""Ready to build is a result: explicit criteria, and simulations that say how much they prove.

The simulator is deterministic (seeded) and model-based: it proves what the declared model implies, and says whether
that model is calibrated on measurements or only declared. The gate never grants anything; it reports.
"""
from collections import Counter, defaultdict
import json
import math
import random
import re
from air import artifacts
from air.access import ScopedStore, Forbidden
from air.core import digest, record
from air.expr import Budget, artifact_digest, bounded, evaluate, ExprError
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot

SIMULATION_ENGINE = 'air.scenario-simulation/0.32'
SYNCHRONIZED_ENGINE = 'air.scenario-simulation/0.35'
GATE_ENGINE = 'air.readiness-gate/0.32'
SIMULATE_REQUEST = record({'baseline': SNAPSHOT, 'scenario': SNAPSHOT})
RECORD_REQUEST = record({'baseline': SNAPSHOT, 'scenario': SNAPSHOT, 'run_id': {'type': 'string', 'format': 'uri', 'maxLength': 512},
                         'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128}})
GATE_REQUEST = {'oneOf': [record({'baseline': SNAPSHOT}),
                          record({'prepared_change': {'type': 'string', 'pattern': '^urn:air:prepared-change:[a-f0-9]{64}$'}})]}
Z95 = 1.6448536269514722
SIMULATION_LIMITS = [
    'Model-based: the result is what the declared workflow, guards and duration model imply, not a measurement of a running system',
    'Guards are evaluated on the declared class contexts; an unguarded flow is always taken and reported',
    'A class without start_step enters every start step at once; name the start step of alternative triggers',
    'A step reached by several paths starts at its earliest arrival (OR-join); parallel branches are not synchronised',
    'A step is numerically calibrated only when every cited duration statistic agrees within 20 %; this does not authenticate the observations or establish their freshness or representativeness',
    'Latency percentiles describe only runs reaching both measurement endpoints; a known excluded path is outside that measured population',
    'An undecidable guard or a missing step duration makes the overall verdict inconclusive; the conditional verdict remains available for diagnosis',
]


def _members(store, principal, policy, snapshot_ref):
    exported = snapshot(ScopedStore(store, principal, policy), snapshot_ref)
    # Dependency locks and validation receipts repeat the authorized members.
    # The evaluator consumes the exact baseline and model objects; charge its
    # unchanged 1 MiB input budget to those, not the transport envelope.
    try: bounded({'baseline': exported['baseline'], 'objects': exported['objects']})
    except ExprError as exc: raise InvalidModel('Baseline exceeds the simulation budget') from exc
    return exported, {key(exact(o)): o for o in exported['objects']}


def _sample(rng, d):
    kind = d['kind']
    if kind == 'FIXED': return float(d['value'])
    u = rng.random()
    if kind == 'UNIFORM': return d['min'] + (d['max'] - d['min']) * u
    if kind == 'TRIANGULAR':
        a, c, b = d['min'], d['mode'], d['max']
        if b == a: return float(a)
        f = (c - a) / (b - a)
        return a + math.sqrt(u * (b - a) * (c - a)) if u < f else b - math.sqrt((1 - u) * (b - a) * (b - c))
    # LOGNORMAL from median and p95, with a Box-Muller normal draw: stable across Python versions for a given seed
    mu = math.log(d['median']);sigma = (math.log(d['p95']) - mu) / Z95
    z = math.sqrt(-2.0 * math.log(max(u, 1e-300))) * math.cos(2 * math.pi * rng.random())
    return math.exp(mu + sigma * z)


TOLERANCE = 0.20
STATISTIC = re.compile(r'(?<![a-z0-9])(p50|p90|p95|p99|median)(?![a-z0-9])', re.IGNORECASE)


def _model_quantile(d, q):
    """The declared model's own quantile, to compare with what was measured."""
    kind = d['kind']
    if kind == 'FIXED': return float(d['value'])
    if kind == 'UNIFORM': return d['min'] + (d['max'] - d['min']) * q
    if kind == 'TRIANGULAR':
        a, c, b = d['min'], d['mode'], d['max']
        if b == a: return float(a)
        f = (c - a) / (b - a)
        return a + math.sqrt(q * (b - a) * (c - a)) if q < f else b - math.sqrt((1 - q) * (b - a) * (b - c))
    mu = math.log(d['median']);sigma = (math.log(d['p95']) - mu) / Z95
    z = {0.5: 0.0, 0.9: 1.2815515655446004, 0.95: Z95, 0.99: 2.3263478740408408}[q]
    return math.exp(mu + sigma * z)


def _observed_ms(observation):
    """(quantile, milliseconds) of a numeric duration observation, or None when it cannot calibrate a step."""
    body = observation['body'];signal = body['metric_or_signal'];value = body['value_or_artifact']
    label = signal if isinstance(signal, str) else observation['meta']['name']
    quantiles = {'p50': 0.5, 'median': 0.5, 'p90': 0.9, 'p95': 0.95, 'p99': 0.99}
    matched = {quantiles[m.lower()] for m in STATISTIC.findall(label + ' ' + observation['meta']['name'])}
    if len(matched) != 1 or not isinstance(value, dict) or value.get('state', 'KNOWN') != 'KNOWN' or 'value' not in value: return None
    factors = {'Quantity[ms]': 1, 'Quantity[s]': 1000}
    factor = factors.get(value.get('type'))
    if factor is None or isinstance(value['value'], bool): return None
    try: number = float(str(value['value']))
    except (ValueError, OverflowError): return None
    number *= factor
    if not math.isfinite(number) or number < 0: return None
    return next(iter(matched)), number


def calibration(durations, index):
    """Per step: observations that can calibrate it, the model's value at the same quantile, and whether they agree."""
    result = {}
    for step, entry in sorted(durations.items()):
        rows = []
        for ref in entry.get('calibrated_from', []):
            observation = index.get(key(ref))
            if not observation or observation['meta']['type'] != 'air.RuntimeObservation':
                rows.append({'observation': {'id': ref['id'], 'revision': ref['revision']}, 'status': 'ABSENT_FROM_BASELINE'});continue
            observed = _observed_ms(observation)
            if observed is None:
                rows.append({'observation': exact(observation), 'status': 'NOT_A_DURATION_STATISTIC'});continue
            q, ms = observed;modelled = _model_quantile(entry['distribution'], q)
            deviation = abs(modelled - ms) / ms if ms else (0.0 if modelled == 0 else None)
            # An undefined or unrepresentable relative error must remain JSON-safe and cannot agree.
            if deviation is not None and not math.isfinite(deviation): deviation = None
            rows.append({'observation': exact(observation), 'quantile': q, 'observed_ms': round(ms, 1), 'modelled_ms': round(modelled, 1),
                         'deviation': round(deviation, 3) if deviation is not None else None,
                         'status': 'AGREES' if deviation is not None and deviation <= TOLERANCE else 'DISAGREES'})
        result[step] = {'observations': rows, 'calibrated': bool(rows) and all(r['status'] == 'AGREES' for r in rows)}
    return result


def _percentile(sorted_values, p, rounded=True):
    if not sorted_values: return None
    rank = max(0, math.ceil(p / 100 * len(sorted_values)) - 1)
    return round(sorted_values[rank], 1) if rounded else sorted_values[rank]


def simulate_scenario(store, principal, policy, request):
    check_schema(request, SIMULATE_REQUEST)
    exported, index = _members(store, principal, policy, request['baseline'])
    scenario = index.get(key(request['scenario']))
    if not scenario or scenario['meta']['type'] != 'air.SimulationScenario': raise InvalidModel('Scenario must be an exact member of the baseline')
    if digest(scenario) != request['scenario']['digest']:
        from air.storage import Conflict
        raise Conflict('Scenario digest differs')
    body = scenario['body']
    workflow = index.get(key(body['workflow']));model = index.get(key(body['performance_model']))
    if not workflow or workflow['meta']['type'] != 'air.Workflow' or not model or model['meta']['type'] != 'air.PerformanceModel':
        raise InvalidModel('The scenario workflow and performance model must be exact members of the baseline')
    steps = {s['id'] for s in workflow['body']['steps']}
    durations = {s['step']: s for s in model['body']['steps']}
    outgoing = defaultdict(list)
    for flow in workflow['body']['flows']: outgoing[flow['source']].append(flow)
    joins = {s['id']: s.get('join', 'ANY') for s in workflow['body']['steps']}
    synchronized = any(s['binding'] == 'air.workflow-step/0.35' for s in workflow['body']['steps'])
    from air.expr import engine_for, UNITS_ENGINE
    expression_engines = sorted({engine_for(f['guard']) for f in workflow['body']['flows'] if 'guard' in f})
    incoming = defaultdict(set)
    for flow in workflow['body']['flows']: incoming[flow['target']].add(flow['id'])
    if any(joins[s] == 'ALL' and incoming[s] for s in workflow['body']['start_steps']):
        raise InvalidModel('An ALL join with incoming flows cannot also be a start step')
    if any('start_step' in c and joins[c['start_step']] == 'ALL' and incoming[c['start_step']]
           for c in body['classes']):
        raise InvalidModel('A scenario cannot bypass an ALL join with incoming flows')
    unguarded = sorted(f['id'] for f in workflow['body']['flows'] if 'guard' not in f)
    # a guard depends only on the class context: evaluate it once per class
    decisions, undecided = {}, Counter()
    for cls in body['classes']:
        for flow in workflow['body']['flows']:
            if 'guard' not in flow: decisions[(cls['name'], flow['id'])] = True;continue
            names = {i['name'] for i in flow['guard'].get('required_inputs', [])}
            inputs = {n: v for n, v in cls['context'].items() if n in names}
            result = evaluate({'expression': flow['guard'], 'inputs': inputs}, budget=Budget())
            taken = result['execution'] == 'EXECUTED' and result['result'] == 'SATISFIED'
            if result['execution'] != 'EXECUTED' or result['result'] not in ('SATISFIED', 'VIOLATED'):
                undecided[(cls['name'], flow['id'], result['result'])] += 1
            decisions[(cls['name'], flow['id'])] = taken
    rng = random.Random(body['seed'])
    weights = [c['weight'] for c in body['classes']];total_weight = sum(weights)
    latencies, per_class, not_reached = [], defaultdict(Counter), Counter()
    blocked_joins = Counter()
    for _ in range(body['runs']):
        pick = rng.random() * total_weight;acc = 0
        for cls in body['classes']:
            acc += cls['weight']
            if pick < acc: break
        start, finish, order = {}, {}, []
        # alternative triggers: a class that names its start step enters the workflow only there
        frontier = [(0.0, s, '') for s in ([cls['start_step']] if 'start_step' in cls else sorted(workflow['body']['start_steps']))]
        arrivals = defaultdict(dict)
        while frontier:
            frontier.sort();begin, step, via = frontier.pop(0)
            if step in finish: continue
            if joins[step] == 'ALL' and incoming[step]:
                arrivals[step][via] = begin
                if not incoming[step] <= arrivals[step].keys(): continue
                begin = max(arrivals[step][f] for f in incoming[step])
            spent = _sample(rng, durations[step]['distribution']) if step in durations else 0.0
            start[step], finish[step] = begin, begin + spent;order.append(step)
            for flow in sorted(outgoing.get(step, []), key=lambda f: f['id']):
                if decisions[(cls['name'], flow['id'])] and flow['target'] not in finish:
                    frontier.append((finish[step], flow['target'], flow['id']))
        for step in arrivals:
            if step not in finish: blocked_joins[(cls['name'], step)] += 1
        per_class[cls['name']][' > '.join(order)] += 1
        measure = body['measure']
        if measure['from_step'] in start and measure['to_step'] in finish:
            latencies.append(finish[measure['to_step']] - start[measure['from_step']])
        else:
            not_reached[cls['name']] += 1
    latencies.sort()
    target = body['target'];observed = _percentile(latencies, target['percentile'], rounded=False)
    verdict = 'INCONCLUSIVE' if observed is None else 'PASS' if observed <= target['max_ms'] else 'FAIL'
    checked = calibration(durations, index)
    calibrated_steps = sorted(s for s, c in checked.items() if c['calibrated'])
    unmodelled = sorted(steps - set(durations))
    conditional_verdict = verdict
    inconclusive_reasons = (['UNDECIDED_GUARDS'] if undecided else []) + (['UNMODELLED_STEPS'] if unmodelled else [])
    if observed is None: inconclusive_reasons.append('NO_MEASURED_RUNS')
    if blocked_joins: inconclusive_reasons.append('BLOCKED_SYNCHRONIZATIONS')
    if inconclusive_reasons: verdict = 'INCONCLUSIVE'
    used = sorted(set(durations) & steps)
    qualification = 'CALIBRATED' if used and set(used) <= set(calibrated_steps) and not unmodelled else 'DECLARED'
    report = {'engine': SIMULATION_ENGINE, 'regime': 'MODEL_BASED_SIMULATION', 'baseline': request['baseline'], 'scenario': request['scenario'],
        'workflow': {**exact(workflow), 'digest': digest(workflow)}, 'performance_model': {**exact(model), 'digest': digest(model)},
        'runs': body['runs'], 'seed': body['seed'], 'measure': body['measure'], 'target': target,
        'latency_ms': {'measured_runs': len(latencies), 'p50': _percentile(latencies, 50), 'p90': _percentile(latencies, 90),
                       'p95': _percentile(latencies, 95), 'p99': _percentile(latencies, 99),
                       'max': round(latencies[-1], 1) if latencies else None,
                       'mean': round(sum(latencies) / len(latencies), 1) if latencies else None},
        'observed_at_target_percentile': observed, 'verdict': verdict, 'conditional_verdict': conditional_verdict,
        'inconclusive_reasons': inconclusive_reasons,
        'population': {'requested_runs': body['runs'], 'measured_runs': len(latencies),
                       'excluded_runs': sum(not_reached.values()), 'scope': 'RUNS_REACHING_BOTH_ENDPOINTS'},
        'classes': [{'name': c['name'], 'weight': c['weight'], 'runs': sum(per_class[c['name']].values()),
                     'measure_not_reached': not_reached[c['name']], 'paths': dict(per_class[c['name']].most_common(10))} for c in body['classes']],
        'model_qualification': qualification, 'proof_level': 'CALIBRATED_SIMULATION' if qualification == 'CALIBRATED' else 'DECLARED_MODEL_SIMULATION',
        'calibrated_steps': calibrated_steps, 'calibration': checked, 'calibration_tolerance': TOLERANCE,
        'unmodelled_steps': unmodelled, 'unguarded_flows': unguarded,
        'undecided_guards': [{'class': c, 'flow': f, 'result': r, 'count': n} for (c, f, r), n in sorted(undecided.items())],
        'verification_case': body.get('verification_case'), 'limits': SIMULATION_LIMITS,
        'external_effects': False, 'authorization_granted': False}
    if synchronized:
        report['engine'] = SYNCHRONIZED_ENGINE
        report['synchronizations'] = {'semantics': 'ALL_STATIC_INCOMING_FLOWS_OR_ANY_FIRST_ARRIVAL',
            'blocked': [{'class': c, 'step': s, 'runs': n} for (c, s), n in sorted(blocked_joins.items())]}
        report['limits'] = [s for s in SIMULATION_LIMITS if 'OR-join' not in s] + [
            'ALL joins require every declared incoming flow; an untaken branch blocks the join',
            'Each step executes at most once per run; repeated loop iterations and mutable business state are not modelled']
    if UNITS_ENGINE in expression_engines:
        report['engine'] = SYNCHRONIZED_ENGINE
        report['expression_engines'] = expression_engines
    report['report_digest'] = artifact_digest(report)
    return report


def record_simulation(store, principal, policy, settings, request):
    """Run the scenario, keep its report as an artifact, and return the VerificationRun draft that cites it.

    Nothing enters the registry model: the run is a draft the architect deposits after reading it.
    """
    check_schema(request, RECORD_REQUEST)
    report = simulate_scenario(store, principal, policy, {'baseline': request['baseline'], 'scenario': request['scenario']})
    index = _members(store, principal, policy, request['baseline'])[1]
    scenario = index[key(request['scenario'])]
    case_ref = scenario['body'].get('verification_case')
    if not case_ref: raise InvalidModel('The scenario names no verification case to record a run for')
    namespace = scenario['meta']['namespace']
    raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    stored = artifacts.put(store, principal, policy, settings, {'idempotency_key': request['idempotency_key'], 'namespace': namespace,
                                                               'media_type': 'application/json'}, raw)
    from air.collaboration import identity_context, identity_uri
    from air.agent import now
    executor = identity_uri(identity_context(principal, settings)) if settings else 'urn:air:identity:unknown'
    stamp = now()
    meta = {**{k: v for k, v in scenario['meta'].items() if k not in ('id', 'type', 'revision', 'name', 'description')},
            'id': request['run_id'], 'type': 'air.VerificationRun', 'revision': 1,
            'name': 'Simulation run of ' + scenario['meta']['name'], 'recorded_at': stamp, 'validity': {'start': stamp, 'end': None},
            'description': 'Seeded model-based simulation; verdict ' + report['verdict'] + ' at p' + str(report['target']['percentile'])
                           + ' = ' + str(report['observed_at_target_percentile']) + ' ms against ' + str(report['target']['max_ms']) + ' ms'}
    meta['provenance'] = {**scenario['meta']['provenance'], 'recorded_by': executor, 'method': 'air_record_simulation ' + report['engine']}
    run = {'meta': meta, 'body': {'case': {'id': case_ref['id'], 'revision': case_ref['revision']}, 'method': 'SIMULATION',
        'result': {'PASS': 'PASS', 'FAIL': 'FAIL'}.get(report['verdict'], 'INCONCLUSIVE'), 'proof_level': report['proof_level'],
        'executed_at': stamp, 'executor': executor, 'summary': meta['description'], 'report': stored['artifact_reference'],
        'scenario': {'id': scenario['meta']['id'], 'revision': scenario['meta']['revision']}}}
    return {'engine': report['engine'], 'report': report, 'report_artifact': stored['artifact_reference'], 'verification_run': run,
            'registry_written': False, 'artifact_stored': True,
            'next_steps': ['Show the verdict and its limits; after approval add verification_run to a change (air_rebase_drafts) and deposit it']}


def _behind_latest(store, objects, home):
    """Borrowed objects that their owner has revised since: consistent as pinned, but a realignment to plan (air_guide IMPACT)."""
    borrowed = [o for o in objects if o['meta']['namespace'] != home]
    heads = store.latest_revisions([o['meta']['id'] for o in borrowed])
    behind = [o for o in borrowed if heads.get(o['meta']['id'], 0) > o['meta']['revision']]
    return {'count': len(behind), 'namespaces': sorted({o['meta']['namespace'] for o in behind}),
            'sample': [{'id': o['meta']['id'], 'pinned_revision': o['meta']['revision'], 'latest_revision': heads[o['meta']['id']]} for o in behind[:10]]}


def _input_kernels(store, principal, policy, objects, home):
    """Controls and quality requirements received as inputs: those of each borrowed namespace whose latest baseline pinning
    the borrowed revisions builds nothing (a shared kernel). They apply to this project even if it cites none of them."""
    borrowed = defaultdict(dict)
    for o in objects:
        if o['meta']['namespace'] != home: borrowed[o['meta']['namespace']][o['meta']['id']] = o['meta']['revision']
    inputs = []
    for namespace, pins in sorted(borrowed.items()):
        if not policy.allows(principal, 'read', namespace): continue
        best = None
        for baseline_id in store.identities_of(namespace, 'air.Baseline'):
            rows, _ = store.revisions(baseline_id, 20)
            for row in rows:
                members = {m['id']: m['revision'] for m in store.get(baseline_id, row['revision'])['object']['body']['members']}
                if all(members.get(i) == r for i, r in pins.items()) and (best is None or row['revision'] > best['revision']):
                    best = {'id': baseline_id, 'revision': row['revision']}
        if best is None: continue
        kernel = ScopedStore(store, principal, policy).export_baseline(best)['objects']
        if any(o['meta']['namespace'] == namespace and o['meta']['type'] in ('air.ArchitectureBlock', 'air.Requirement') for o in kernel): continue
        inputs += [o for o in kernel if o['meta']['namespace'] == namespace and o['meta']['type'] in ('air.Control', 'air.QualityRequirement')]
    return inputs


def _owner_coverage(store, principal, policy, objects, home, theirs):
    """A borrowed object is proven complete where it is owned: in a readable baseline of its own project that pins the
    same revision of every object borrowed from that project. Diagnostics raised here only because the owner's units,
    estimates or cases were not borrowed are then covered; those the owner's baseline also raises stay open."""
    from air.agent import _construction
    namespace_of = {o['meta']['id']: o['meta']['namespace'] for o in objects}
    borrowed = defaultdict(dict)
    for o in objects:
        if o['meta']['namespace'] != home: borrowed[o['meta']['namespace']][o['meta']['id']] = o['meta']['revision']
    owners, failing = {}, {}
    for namespace, pins in sorted(borrowed.items()):
        if not policy.allows(principal, 'read', namespace):
            owners[namespace] = {'status': 'UNREADABLE'};continue
        best = None
        for baseline_id in store.identities_of(namespace, 'air.Baseline'):
            rows, _ = store.revisions(baseline_id, 20)
            for row in rows:
                members = {m['id']: m['revision'] for m in store.get(baseline_id, row['revision'])['object']['body']['members']}
                if all(members.get(i) == r for i, r in pins.items()) and (best is None or row['revision'] > best['revision']):
                    best = {'id': baseline_id, 'revision': row['revision'], 'digest': row['digest']}
        if best is None:
            owners[namespace] = {'status': 'NO_OWNER_BASELINE_PINS_THESE_REVISIONS'};continue
        exported = ScopedStore(store, principal, policy).export_baseline({'id': best['id'], 'revision': best['revision']})
        result = _construction(exported['objects'], exported['baseline']['body']['profiles'][0])
        if result is None:
            owners[namespace] = {'status': 'OWNER_BASELINE_WITHOUT_CONSTRUCTION', 'baseline': best};continue
        failing[namespace] = {str(r.get('path', '')).split('#')[0] for r in result['diagnostics']}
        owners[namespace] = {'status': 'OWNER_BASELINE_FOUND', 'baseline': best, 'objects_with_owner_diagnostics': len(failing[namespace])}
    uncovered = []
    for row in theirs:
        object_id = str(row.get('path', '')).split('#')[0];namespace = namespace_of.get(object_id, '?')
        if namespace not in failing: uncovered.append({**row, 'owner_status': owners.get(namespace, {}).get('status', 'UNKNOWN')})
        elif object_id in failing[namespace]: uncovered.append({**row, 'owner_status': 'INCOMPLETE_IN_OWNER_BASELINE'})
    return owners, uncovered


def _candidate(store, principal, policy, prepared_id):
    """The baseline a prepared change would freeze, assembled in memory: nothing is written."""
    from air.agent import _prepared
    from air.foundation import validate_graph
    payload = _prepared(store, principal, prepared_id, policy)
    bundle = {key(exact(o)): o for o in payload['objects']};request = payload['baseline_request']
    guarded = ScopedStore(store, principal, policy)
    objects = [bundle.get(key(ref)) or guarded.get(ref['id'], ref['revision'])['object'] for ref in request['members']]
    validation = validate_graph(objects, request['profile'])
    baseline = {'meta': request['meta'], 'body': {'profiles': [request['profile']], 'members': request['members'],
                                                  'parent_baselines': request['parent_baselines']}}
    exported = {'objects': objects, 'baseline': baseline, 'validation': validation, 'digest': None}
    return exported, {key(exact(o)): o for o in objects}


def assess_readiness(store, principal, policy, request):
    """Criteria that make "ready to build" a result, each with its evidence and what would close it.

    With a prepared change, the gate judges the baseline that change would freeze, before anything is deposited."""
    check_schema(request, GATE_REQUEST)
    from air.architecture import inspect_objects
    from air.agent import _construction, _owner
    if 'prepared_change' in request:
        exported, index = _candidate(store, principal, policy, request['prepared_change'])
    else:
        exported, index = _members(store, principal, policy, request['baseline'])
    objects = exported['objects'];baseline = exported['baseline'];home = baseline['meta']['namespace']
    profile = baseline['body']['profiles'][0]
    owned = lambda o: o['meta']['namespace'] == home
    of = lambda kind: [o for o in objects if o['meta']['type'] == kind]
    namespaces = {o['meta']['id']: o['meta']['namespace'] for o in objects}
    criteria = []

    # A project that owns no block and no requirement builds nothing (a shared kernel, a strategy repository):
    # construction, planning and runtime do not apply to it; everything else does.
    buildable = any(owned(o) and o['meta']['type'] in ('air.ArchitectureBlock', 'air.Requirement') for o in objects)
    BUILD_ONLY = ('CONSTRUCTION_CHAIN', 'PLANNING', 'RUNTIME', 'COMPLIANCE')

    def criterion(code, title, met, detail, fix, owner=None):
        if not buildable and code in BUILD_ONLY:
            criteria.append({'code': code, 'title': title, 'status': 'NOT_APPLICABLE', 'detail': {'reason': 'This project owns no architecture block and no requirement'},
                             'to_close': None});return
        criteria.append({'code': code, 'title': title, 'status': 'MET' if met else 'NOT_MET', 'detail': detail, 'to_close': None if met else fix,
                         **({'owner': owner} if owner else {})})

    criterion('REFERENCE_CLOSURE', 'Every exact reference resolves inside the baseline', exported['validation']['valid'],
              {'diagnostics': len(exported['validation']['diagnostics'])}, 'Correct or add the referenced revisions')
    checks = inspect_objects(store, principal, policy, objects, home, 'SUMMARY')['checks']
    criterion('STRUCTURE', 'No structural violation (MECE exclusivity and exhaustiveness, DDD context coherence)',
              checks['result'] == 'NO_STRUCTURAL_VIOLATION', {'result': checks['result'], 'violations': checks['violations'][:20]},
              'Resolve each violation named by air_inspect_architecture')
    construction = _construction(objects, profile)
    if construction is None:
        criterion('CONSTRUCTION_CHAIN', 'Requirement, function, contract, unit and verification chain is complete', False,
                  {'reason': 'The baseline profile carries no construction types'}, 'Freeze under a profile that includes construction')
    else:
        rows = [{**r, 'owner': _owner(r, namespaces, home)} for r in construction['diagnostics']]
        mine = [r for r in rows if r['owner'] != 'OTHER_PROJECT'];theirs = [r for r in rows if r['owner'] == 'OTHER_PROJECT']
        criterion('CONSTRUCTION_CHAIN', 'Requirement, function, contract, unit and verification chain is complete for this project', not mine,
                  {'diagnostics': len(mine), 'by_code': dict(Counter(r['code'] for r in mine))},
                  'Close each diagnostic; air_guide explains each code and its fix')
        owners, open_theirs = _owner_coverage(store, principal, policy, objects, home, theirs)
        criterion('EXTERNAL_DEPENDENCIES', 'Borrowed objects are complete in a baseline of their owning project that pins the same revisions',
                  not open_theirs,
                  {'diagnostics': len(open_theirs), 'raised_here': len(theirs), 'by_code': dict(Counter(r['code'] for r in open_theirs)),
                   'namespaces': sorted({namespaces.get(str(r.get('path', '')).split('#')[0], '?') for r in open_theirs}), 'owners': owners,
                   'behind_latest': _behind_latest(store, objects, home),
                   'open_sample': [{k: r[k] for k in ('code', 'path', 'owner_status') if k in r} for r in open_theirs[:20]]},
                  'The owning projects close these diagnostics in their own baseline, then this project realigns (air_rebase_drafts realign_borrowed)')
    unknowns = [u for u in exported['validation'].get('open_unknowns', []) if u['blocking_policy'] == 'BLOCK']
    contested = [exact(o) for o in of('air.Assertion') if o['body']['epistemic_status'] == 'CONTESTED']
    criterion('KNOWLEDGE', 'No blocking unknown and no contested assertion', not unknowns and not contested,
              {'blocking_unknowns': unknowns[:20], 'contested_assertions': contested[:20]}, 'Resolve or explicitly downgrade them')
    decisions = of('air.Decision')
    accepted = {key(r) for d in decisions for r in d['body'].get('basis', [])}
    gaps = [g for g in of('air.ArchitectureGap') if owned(g)]
    open_gaps = [{'id': g['meta']['id'], 'revision': g['meta']['revision'], 'name': g['meta']['name']} for g in gaps if key(exact(g)) not in accepted]
    # A decision is a draft until a human approves it: a gap it accepts counts only once an authenticated review
    # covers this exact revision, which carries the decision.
    # Reuse the authority service, never infer acceptance from the mere existence of a receipt.
    from air.reviews import read_review
    from air.proofs import QUALIFIED, DESIGN_QUALIFIED
    reviews, rejected = [], []
    assessments = []
    unreadable_review = False
    for receipt in store.reviews_of(baseline['meta']['id'], home):
        if receipt['revision'] != baseline['meta']['revision'] or receipt['digest'] != exported['digest']: continue
        try:
            review = read_review(store, principal, policy, receipt['receipt'])
        except (Forbidden, InvalidModel):
            # Do not expose private evidence, or ignore a potentially effective rejection.
            unreadable_review = True
            continue
        if review['effective']:
            (reviews if review['outcome'] == 'ACCEPTED' else rejected).append(receipt)
            if review['outcome'] == 'ACCEPTED':
                assessments.extend({**q, 'receipt': receipt['receipt']} for q in review['proof_qualifications'])
    review_accepted = bool(reviews) and not rejected and not unreadable_review
    if not review_accepted: assessments = []
    by_decision = [{'id': g['meta']['id'], 'revision': g['meta']['revision'], 'name': g['meta']['name'],
                    'decisions': sorted(d['meta']['id'] for d in decisions if key(exact(g)) in {key(r) for r in d['body'].get('basis', [])})}
                   for g in gaps if key(exact(g)) in accepted]
    pending = by_decision if not review_accepted else []
    criterion('GAPS', 'Every declared gap is closed, or accepted by a decision that a human review of this revision approved', not open_gaps and not pending,
              {'declared': len(gaps), 'open': open_gaps, 'accepted_by_decision': by_decision, 'accepted_pending_review': pending},
              'Remove the gap once its output exists, or record a Decision whose basis cites it and have this revision reviewed' if open_gaps else
              'A human reviewer approves the decisions that accept these gaps by reviewing this exact revision (air review)', None if open_gaps else 'human')
    runs = defaultdict(list)
    for run in of('air.VerificationRun'): runs[key(run['body']['case'])].append(run)
    statuses = []
    for case in [c for c in of('air.VerificationCase') if owned(c)]:
        history = sorted(runs.get(key(exact(case)), []), key=lambda r: r['body']['executed_at'])
        last = history[-1]['body'] if history else None
        qualified = [q for q in assessments if key(q['case']) == key(exact(case)) and q['status'] in QUALIFIED]
        selected = {key(q['run']) for q in qualified}
        if len(selected) == 1:
            # A client-supplied future execution date cannot supersede an explicit qualified selection.
            last = index[next(iter(selected))]['body']
        state = 'NOT_RUN' if last is None else 'FAILED' if last['result'] == 'FAIL' else 'INCONCLUSIVE' if last['result'] == 'INCONCLUSIVE' \
            else 'PASS_ON_DECLARED_MODEL' if last['proof_level'] == 'DECLARED_MODEL_SIMULATION' else 'PASS_UNVERIFIED'
        if len(selected) == 1: state = qualified[0]['status']
        elif len(selected) > 1: state = 'CONFLICTING_QUALIFICATIONS'
        statuses.append({'case': exact(case), 'name': case['meta']['name'], 'method': case['body']['method'], 'status': state,
                         **({'proof_level': last['proof_level'], 'executed_at': last['executed_at'],
                             'qualification': state if qualified else 'DECLARED_RECORD_ONLY'} if last else {}),
                         'runtime_execution_attested': state == 'VERIFIED_EXTERNAL_TEST',
                         'qualification_receipts': sorted({q['receipt'] for q in qualified})[:10],
                         **({'selected_run': qualified[0]['run'], 'qualification_scope': qualified[0]['scope']} if len(selected) == 1 else {})})
    counts = Counter(s['status'] for s in statuses)
    # Before construction only design-time cases can run; a TEST case is the acceptance of the build and must be planned:
    # referenced by an acceptance criterion of a construction unit of this project.
    design = [s for s in statuses if s['method'] != 'TEST'];tests = [s for s in statuses if s['method'] == 'TEST']
    planned = {key(c) for u in of('air.ConstructionUnit') if owned(u) for r in u['body']['acceptance'] if key(r) in index
               for c in index[key(r)]['body'].get('cases', [])}
    # a shared kernel plans no unit: its test cases are planned by the projects that implement them
    unplanned = [s for s in tests if key(s['case']) not in planned and s['status'] != 'VERIFIED_EXTERNAL_TEST'] if buildable else []
    failed_tests = [s['case'] for s in tests if s['status'] in ('FAILED', 'CONFLICTING_QUALIFICATIONS')]
    open_design = [s for s in design if s['status'] not in QUALIFIED]
    criterion('VERIFICATION', 'Every design-time case has an effective explicit design qualification, and every runtime test is planned as construction-unit acceptance',
              bool(statuses) and not open_design and not unplanned and not failed_tests,
              {'cases': len(statuses), 'by_status': dict(counts), 'design_cases': len(design), 'design_cases_open': [
                  {k: s[k] for k in ('name', 'method', 'status') if k in s} for s in open_design][:50],
               'build_acceptance_tests': len(tests), 'failed_or_conflicting_runtime_tests': failed_tests,
               'tests_not_planned_in_a_unit': [s['name'] for s in unplanned][:50], 'cases_detail': statuses[:100]},
              'Attach an exact report to each design run and obtain an independent baseline review with explicit proof_assessments; a simulation must also reproduce with numerical calibration; plan runtime tests in construction-unit acceptance')
    units = [u for u in of('air.ConstructionUnit') if owned(u)]
    estimated = {key(e['body']['target']) for e in of('air.Estimate')}
    unestimated = [exact(u) for u in units if key(exact(u)) not in estimated]
    costs = [c for c in of('air.CostItem') if owned(c)];milestones = [m for m in of('air.Milestone') if owned(m)]
    criterion('PLANNING', 'Every construction unit is estimated, and costs and milestones are declared',
              bool(units) and not unestimated and bool(costs) and bool(milestones),
              {'units': len(units), 'unestimated': unestimated[:20], 'cost_items': len(costs), 'milestones': len(milestones)},
              'Add an Estimate per unit, CostItems (CAPEX and OPEX) and Milestones')
    production = [r for r in of('air.RuntimeComponent') if owned(r) and index.get(key(r['body']['environment']), {}).get('body', {}).get('stage') == 'PRODUCTION']
    realised = {key(ref) for r in production for ref in r['body'].get('realizes', [])}
    unrealised = [{'id': b['meta']['id'], 'name': b['meta']['name']} for b in of('air.ArchitectureBlock') if owned(b) and key(exact(b)) not in realised]
    criterion('RUNTIME', 'Every architecture block of this project has a production runtime component',
              bool(production) and not unrealised, {'production_components': len(production), 'blocks_without_runtime': unrealised[:30]},
              'Declare Environment, NetworkZone and RuntimeComponent objects for production')
    zones = {key(exact(z)): z for z in of('air.NetworkZone')};components = {key(exact(r)): r for r in of('air.RuntimeComponent')}
    rank = {'PUBLIC': 0, 'DMZ': 1, 'INTERNAL': 2, 'RESTRICTED': 3, 'MANAGEMENT': 3}
    exposures = []
    for connection in [c for c in of('air.Connection') if owned(c)]:
        source = components.get(key(connection['body']['source']));target = components.get(key(connection['body']['target']))
        if not source or not target: continue
        from_zone = zones.get(key(source['body']['zone']));to_zone = zones.get(key(target['body']['zone']))
        if not from_zone or not to_zone: continue
        crossing = from_zone['body']['trust_level'] != to_zone['body']['trust_level']
        if crossing and not connection['body']['encrypted']:
            exposures.append({'connection': exact(connection), 'issue': 'Unencrypted crossing between trust zones'})
        if rank[from_zone['body']['trust_level']] == 0 and rank[to_zone['body']['trust_level']] >= 3:
            exposures.append({'connection': exact(connection), 'issue': 'Public zone reaches a restricted zone directly'})
    criterion('SECURITY_ZONES', 'No unencrypted crossing between trust zones and no direct public-to-restricted path', not exposures,
              {'issues': exposures[:30]}, 'Encrypt the crossing or route it through a gateway in the DMZ')
    inputs = _input_kernels(store, principal, policy, objects, home) if buildable else []
    # Owned subjects, subjects the project itself cites, and inputs of shared kernels. A control that is only in the closure of
    # another project's borrowed objects is that project's obligation, not this one's.
    from air.agent import _walk_refs
    cited = set()
    for o in objects:
        if owned(o) and o['meta']['type'] != 'air.ComplianceMapping':
            _walk_refs(o['body'], lambda ref, path: cited.add(ref['id']))
    subjects = {o['meta']['id']: o for o in [o for o in objects if o['meta']['type'] in ('air.Control', 'air.QualityRequirement')
                                             and (owned(o) or o['meta']['id'] in cited)] + inputs}
    mapped = {m['body']['subject']['id'] for m in of('air.ComplianceMapping') if owned(m)}
    unmapped = [{'id': s['meta']['id'], 'name': s['meta']['name'], 'type': s['meta']['type'], 'namespace': s['meta']['namespace']}
                for i, s in sorted(subjects.items()) if i not in mapped]
    if buildable and not subjects:
        criteria.append({'code': 'COMPLIANCE', 'title': 'Every control and quality requirement is implemented by named construction blocks',
                         'status': 'NOT_APPLICABLE', 'detail': {'reason': 'No control or quality requirement applies to this project'}, 'to_close': None})
    else:
        criterion('COMPLIANCE', 'Every control and quality requirement, received or owned, is implemented by named construction blocks or declared not applicable by a decision',
                  not unmapped, {'subjects': len(subjects), 'received_as_input': len(inputs), 'mapped': len(subjects) - len(unmapped), 'unmapped': unmapped[:50]},
                  'Add a ComplianceMapping per control and quality requirement: the blocks that implement it and the cases that verify it')
    criterion('INDEPENDENT_REVIEW', 'An effective independent acceptance covers this exact revision, with no effective rejection', review_accepted,
              {'receipts': reviews[:10], 'rejections': rejected[:10], 'review_unavailable': unreadable_review},
              'An independent reviewer accepts this exact baseline under the current policy; effective rejections must be resolved explicitly', 'human')
    blocking = [c['code'] for c in criteria if c['status'] == 'NOT_MET']
    target = request['baseline'] if 'baseline' in request else {'prepared_change': request['prepared_change'], 'would_freeze': {
        'id': baseline['meta']['id'], 'revision': baseline['meta']['revision']}, 'candidate': True}
    report = {'engine': GATE_ENGINE, 'baseline': target, 'namespace': home, 'profile': profile,
              'result': 'READY_TO_BUILD' if not blocking else 'NOT_READY', 'blocking': blocking, 'criteria': criteria,
              'proof': {'verified_cases': counts.get('VERIFIED_EXTERNAL_TEST', 0), 'cases': len(statuses), 'design_cases': len(design),
                        'build_acceptance_tests': len(tests), 'declared_model_passes': counts.get('PASS_ON_DECLARED_MODEL', 0),
                        'unverified_passes': counts.get('PASS_UNVERIFIED', 0), 'qualification_available': True,
                        'qualified_design_cases': sum(counts.get(level, 0) for level in DESIGN_QUALIFIED),
                        'runtime_execution_attested': counts.get('VERIFIED_EXTERNAL_TEST', 0) > 0},
              'authorization_granted': False, 'contract_signed': False,
              'limits': ['Ready to build means these criteria hold for this exact revision; it is not a warranty of behaviour',
                         'Human review, signature and admission remain separate authenticated acts',
                         'VerificationRun fields alone are declarations; explicit effective independent assessments can qualify design evidence',
                         'Design review and reproduced numerical simulation do not attest runtime execution or automatically qualify measurement provenance/freshness']}
    report['report_digest'] = artifact_digest(report)
    return report
