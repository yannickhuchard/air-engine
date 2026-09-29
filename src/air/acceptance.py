"""First-order acceptance scenarios walked on the design: navigation, guards, contracts and coverage, before any build.

A walk proves that the designed screens, transitions and operations let each persona reach each goal. It does not
prove that the built system behaves: the same scenarios become the acceptance and regression tests of the build.
"""
from collections import defaultdict
from datetime import datetime, timezone
from air.core import record
from air.expr import Budget, artifact_digest, evaluate
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT

ENGINE = 'air.acceptance-walk/0.33'
WALK_REQUEST = record({'baseline': SNAPSHOT, 'owned_only': {'type': 'boolean'}}, ['baseline'])
QUIET_KINDS = ('REPORT', 'NOTIFICATION', 'EXTERNAL_LINK', 'DIALOG')


def _guard(guard, context):
    names = {i['name'] for i in guard.get('required_inputs', [])}
    missing = sorted(names - set(context))
    if missing: return 'UNDECIDED', 'context lacks ' + ', '.join(missing)
    result = evaluate({'expression': guard, 'inputs': {n: context[n] for n in names}}, budget=Budget())
    if result['execution'] != 'EXECUTED': return 'UNDECIDED', str(result.get('result'))
    return ('TRUE', '') if result['result'] == 'SATISFIED' else ('FALSE', 'guard is false for the scenario context')


def walk_scenario(scenario, index):
    """Play one scenario on its navigation map; returns verdict, per-step findings and what it covered."""
    body = scenario['body'];nav = index.get(key(body['navigation']))
    findings, steps, covered_screens, covered_moves, operations = [], [], set(), set(), set()
    if not nav or nav['meta']['type'] != 'air.NavigationMap':
        return {'verdict': 'FAIL', 'findings': [{'step': None, 'issue': 'The navigation map is not in the baseline'}], 'steps': [],
                'covered_screens': [], 'covered_transitions': [], 'operations': []}
    screens = {s['id']: s for s in nav['body']['screens']};moves = nav['body']['transitions']
    personas = {p['id'] for p in nav['body'].get('personas', [])}
    if personas and body['persona']['id'] not in personas:
        findings.append({'step': None, 'severity': 'FAIL', 'issue': 'The persona is not a declared user of ' + nav['meta']['name']})
    context = body.get('context', {});previous = None
    for i, step in enumerate(body['steps']):
        row = {'step': step['id'], 'screen': step['screen'], 'status': 'OK'}
        screen = screens.get(step['screen'])
        if screen is None:
            row.update(status='FAIL', issue='Screen ' + step['screen'] + ' does not exist');findings.append({'step': step['id'], 'severity': 'FAIL', 'issue': row['issue']})
            steps.append(row);previous = None;continue
        covered_screens.add(step['screen'])
        if i == 0 and step['screen'] not in nav['body']['entry_screens']:
            row.update(status='FAIL', issue='The scenario starts on ' + step['screen'] + ', which is not an entry screen')
        elif previous is not None and previous != step['screen']:
            candidates = [m for m in moves if m['source'] == previous and m['target'] == step['screen'] and (not step.get('via') or m['id'] == step['via'])]
            if not candidates:
                row.update(status='FAIL', issue='No transition leads from ' + previous + ' to ' + step['screen'] + (' via ' + step['via'] if step.get('via') else ''))
            else:
                decided = [(m, _guard(m['guard'], context) if 'guard' in m else ('TRUE', '')) for m in candidates]
                usable = [m for m, (state, _) in decided if state == 'TRUE']
                if usable: covered_moves.add(usable[0]['id']);row['transition'] = usable[0]['id']
                elif any(state == 'UNDECIDED' for _, (state, _) in decided):
                    row.update(status='UNDECIDED', issue='; '.join(why for _, (state, why) in decided if state == 'UNDECIDED'))
                else:
                    row.update(status='FAIL', issue='The guard of every transition to ' + step['screen'] + ' is false for this scenario')
        if 'operation' in step:
            op = step['operation'];contract = index.get(key(op['contract']))
            offered = {(o['contract']['id'], o['name']) for o in screen.get('operations', [])}
            if (op['contract']['id'], op['name']) not in offered:
                row.update(status='FAIL', issue='Screen ' + step['screen'] + ' does not call ' + op['name'])
            elif contract and op['name'] not in {o['name'] for o in contract['body']['operations']}:
                row.update(status='FAIL', issue=op['name'] + ' is not an operation of ' + contract['meta']['name'])
            else:
                operations.add((op['contract']['id'], op['name']))
        if row['status'] != 'OK': findings.append({'step': step['id'], 'severity': row['status'], 'issue': row['issue']})
        steps.append(row);previous = step['screen']
    verdict = 'FAIL' if any(f.get('severity') == 'FAIL' for f in findings) else 'INCONCLUSIVE' if findings else 'PASS'
    return {'verdict': verdict, 'findings': findings, 'steps': steps, 'covered_screens': sorted(covered_screens),
            'covered_transitions': sorted(covered_moves), 'operations': sorted(operations)}


def walk(objects, home=None, owned_only=True):
    """Walk every scenario, then measure what the scenarios leave unexercised in each navigation map."""
    index = {key(exact(o)): o for o in objects}
    owned = lambda o: home is None or o['meta']['namespace'] == home or not owned_only
    scenarios = [o for o in objects if o['meta']['type'] == 'air.AcceptanceScenario' and owned(o)]
    results, by_map = [], defaultdict(lambda: {'screens': set(), 'transitions': set(), 'operations': set(), 'scenarios': 0})
    for s in sorted(scenarios, key=lambda o: o['meta']['id']):
        r = walk_scenario(s, index)
        results.append({'scenario': exact(s), 'name': s['meta']['name'], 'suites': s['body']['suites'], 'priority': s['body']['priority'], **r})
        m = by_map[s['body']['navigation']['id']];m['scenarios'] += 1
        m['screens'] |= set(r['covered_screens']);m['transitions'] |= set(r['covered_transitions']);m['operations'] |= {tuple(x) for x in r['operations']}
    coverage = []
    for nav in [o for o in objects if o['meta']['type'] == 'air.NavigationMap' and owned(o)]:
        m = by_map.get(nav['meta']['id'], {'screens': set(), 'transitions': set(), 'operations': set(), 'scenarios': 0})
        screens = nav['body']['screens'];moves = nav['body']['transitions']
        outgoing = {mv['source'] for mv in moves}
        called = {(o['contract']['id'], o['name']) for s in screens for o in s.get('operations', [])}
        coverage.append({'navigation': exact(nav), 'name': nav['meta']['name'], 'scenarios': m['scenarios'],
            'screens': len(screens), 'screens_covered': len(m['screens'] & {s['id'] for s in screens}),
            'screens_uncovered': sorted({s['id'] for s in screens} - m['screens']),
            'transitions': len(moves), 'transitions_covered': len(m['transitions'] & {mv['id'] for mv in moves}),
            'transitions_uncovered': sorted({mv['id'] for mv in moves} - m['transitions']),
            'operations': len(called), 'operations_uncovered': sorted(n for _, n in called - m['operations']),
            'dead_ends': sorted(s['id'] for s in screens if s['id'] not in outgoing and s['kind'] not in QUIET_KINDS)})
    journeys = []
    exercised = set().union(*[set(tuple(x) for x in r['operations']) for r in results]) if results else set()
    for j in [o for o in objects if o['meta']['type'] == 'air.CustomerJourney' and owned(o)]:
        ops = [(s['operation']['contract']['id'], s['operation']['name']) for s in j['body']['steps'] if 'operation' in s]
        journeys.append({'journey': exact(j), 'name': j['meta']['name'], 'operations': len(ops),
                         'operations_exercised': sum(1 for o in ops if o in exercised), 'not_exercised': sorted(n for c, n in ops if (c, n) not in exercised)})
    regression = [{'scenario': r['scenario'], 'name': r['name'], 'priority': r['priority'], 'design_verdict': r['verdict']}
                  for r in results if 'REGRESSION' in r['suites']]
    return {'scenarios': results, 'coverage': coverage, 'journeys': journeys, 'regression_suite': regression,
            'summary': {'scenarios': len(results), 'pass': sum(r['verdict'] == 'PASS' for r in results),
                        'fail': sum(r['verdict'] == 'FAIL' for r in results), 'inconclusive': sum(r['verdict'] == 'INCONCLUSIVE' for r in results)}}


def walk_baseline(store, principal, policy, request):
    check_schema(request, WALK_REQUEST)
    from air.readiness import _members
    exported, index = _members(store, principal, policy, request['baseline'])
    home = exported['baseline']['meta']['namespace']
    report = walk(exported['objects'], home, request.get('owned_only', True))
    from air.collaboration import identity_context, identity_uri
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    runs = []
    for r in report['scenarios']:
        scenario = index[key(r['scenario'])]
        case = scenario['body'].get('design_case')
        if not case: continue
        meta = {k: v for k, v in scenario['meta'].items() if k in ('namespace', 'owner', 'classification', 'lifecycle', 'provenance')}
        meta['provenance'] = {**meta['provenance'], 'method': ENGINE + ' walk of the scenario on the exact baseline'}
        runs.append({'meta': {**meta, 'id': scenario['meta']['id'].replace(':scenario:', ':run:') + ':walk', 'type': 'air.VerificationRun', 'revision': 1,
                              'name': 'Design walk of ' + scenario['meta']['name'], 'recorded_at': stamp, 'validity': {'start': stamp, 'end': None},
                              'description': 'Deterministic walk of the scenario on the navigation graph and contracts: ' + r['verdict']},
                     'body': {'case': case, 'method': 'ANALYSIS', 'result': {'PASS': 'PASS', 'FAIL': 'FAIL'}.get(r['verdict'], 'INCONCLUSIVE'),
                              'proof_level': 'ANALYSIS', 'executed_at': stamp, 'executor': 'urn:air:engine:' + ENGINE,
                              'summary': r['verdict'] + ': ' + ('; '.join(f['issue'] for f in r['findings'][:5]) or 'every step reachable, every operation offered')}})
    result = {'engine': ENGINE, 'baseline': request['baseline'], 'namespace': home, **report, 'verification_runs': runs,
              'registry_written': False,
              'limits': ['A design walk checks screens, transitions, guards and operations of the model; it does not execute the built system',
                         'The same scenarios are the first acceptance and regression tests of the build; their TEST cases run after construction',
                         'Guards are decided on the scenario context; an absent input leaves the step UNDECIDED']}
    result['report_digest'] = artifact_digest(result)
    return result
