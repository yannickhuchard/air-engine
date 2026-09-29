"""Figures derived from the delivery model: effort with and without AI, roadmap comparison, compliance coverage.

Every figure is computed from declared objects; the basis and confidence of each estimate travel with it.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from air.foundation import InvalidModel


def single_currency(currencies):
    """No exchange-rate model is implemented: refuse mixed monetary aggregates."""
    found = sorted({c for c in currencies if c is not None})
    if len(found) > 1:
        raise InvalidModel('Mixed currencies require an explicit conversion: ' + ', '.join(found))
    return found[0] if found else None


def dec(value):
    return Decimal(str(value))


def money(value):
    return value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def estimates(objects, by_id):
    """Per construction unit: effort without AI, with AI where it applies, delta, durations and agentic subscription cost."""
    rows = []
    for e in sorted((o for o in objects if o['meta']['type'] == 'air.DeliveryEstimate'), key=lambda o: o['meta']['id']):
        b = e['body'];team = b['team'];days = team.get('days_per_month', 20)
        without = sum(dec(a['effort_pd']) for a in b['activities'])
        with_ai = sum(dec(a['ai_effort_pd']) if a['ai_applicable'] else dec(a['effort_pd']) for a in b['activities'])
        plan = by_id.get(b['plan']['id']) if 'plan' in b else None
        months_without = without / team['workers'] / days;months_with = with_ai / team['workers'] / days
        price = dec(plan['body']['price']['value']) if plan else Decimal(0)
        subscription = money(price * team['ai_seats'] * months_with) if plan else Decimal(0)
        unit = by_id.get(b['unit']['id'])
        rows.append({'estimate': e, 'unit': unit['meta']['name'] if unit else b['unit']['id'], 'unit_id': b['unit']['id'],
                     'without_ai_pd': without, 'with_ai_pd': with_ai, 'delta_pd': without - with_ai,
                     'delta_ratio': (without - with_ai) / without if without else Decimal(0),
                     'months_without_ai': months_without, 'months_with_ai': months_with, 'workers': team['workers'], 'ai_seats': team['ai_seats'],
                     'plan': plan, 'subscription': subscription, 'currency': plan['body']['price']['currency'] if plan else None,
                     'activities': b['activities'], 'confidence': b['confidence'], 'basis': b['basis']})
    return rows


def _months(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return dec(max((b - a).days, 1)) / Decimal('30.4375')


def roadmaps(objects, by_id, estimate_rows):
    """Compare roadmaps: calendar, critical path, effort, labour cost, agentic subscription cost."""
    effort = {r['unit_id']: r for r in estimate_rows}
    unit_estimate = {o['body']['target']['id']: dec(o['body']['value_or_distribution']['value']) for o in objects
                     if o['meta']['type'] == 'air.Estimate' and o['body']['value_or_distribution'].get('unit') == 'person_day'}
    result = []
    for r in sorted((o for o in objects if o['meta']['type'] == 'air.Roadmap'), key=lambda o: o['meta']['id']):
        b = r['body'];phases = b['phases']
        start = min(p['start'] for p in phases);end = max(p['end'] for p in phases)
        by_phase = {p['id']: p for p in phases};memo = {}
        def chain(pid):
            if pid not in memo:
                p = by_phase[pid];deps = [d for d in p.get('depends_on', []) if d in by_phase]
                best = max((chain(d) for d in deps), key=lambda c: c[0], default=(Decimal(0), []))
                memo[pid] = (best[0] + _months(p['start'], p['end']), best[1] + [pid])
            return memo[pid]
        critical = max((chain(p['id']) for p in phases), key=lambda c: c[0])
        units = {u['id'] for p in phases for u in p.get('units', [])}
        total_effort = Decimal(0);missing = []
        for u in sorted(units):
            if u in effort: total_effort += effort[u]['with_ai_pd'] if b['uses_ai'] else effort[u]['without_ai_pd']
            elif u in unit_estimate: total_effort += unit_estimate[u]
            else: missing.append(u)
        rate = dec(b['day_rate']['value']) if 'day_rate' in b else None
        plan = by_id.get(b['plan']['id']) if 'plan' in b else None
        seat_months = sum(dec(p['team_size']) * _months(p['start'], p['end']) for p in phases)
        currency = single_currency([b['day_rate']['currency'] if 'day_rate' in b else None,
                                    plan['body']['price']['currency'] if plan and b['uses_ai'] else None])
        subscription = money(dec(plan['body']['price']['value']) * seat_months) if (plan and b['uses_ai']) else Decimal(0)
        external = []
        for p in phases:
            for dependency in p.get('external_depends_on', []):
                other = by_id.get(dependency['roadmap']['id'])
                target = next((x for x in other['body']['phases'] if x['id'] == dependency['phase']), None) if other else None
                kind_ = dependency.get('kind', 'FINISH_TO_START')
                satisfied = None if target is None else {'FINISH_TO_START': p['start'] >= target['end'], 'START_TO_START': p['start'] >= target['start'],
                                                         'FINISH_TO_FINISH': p['end'] >= target['end']}[kind_]
                external.append({'phase': p['id'], 'phase_name': p['name'], 'roadmap_id': dependency['roadmap']['id'],
                                 'roadmap_name': other['meta']['name'] if other else dependency['roadmap']['id'],
                                 'namespace': other['meta']['namespace'] if other else None, 'target_phase': dependency['phase'],
                                 'target_name': target['name'] if target else None, 'target_start': target['start'] if target else None,
                                 'target_end': target['end'] if target else None, 'kind': kind_, 'satisfied': satisfied})
        result.append({'roadmap': r, 'external': external, 'namespace': r['meta']['namespace'], 'name': r['meta']['name'], 'strategy': b['strategy'], 'uses_ai': b['uses_ai'], 'status': b['status'],
                       'start': start, 'end': end, 'months': _months(start, end), 'critical_path': critical[1], 'critical_months': critical[0],
                       'effort_pd': total_effort, 'units_without_estimate': missing, 'labour_cost': money(total_effort * rate) if rate is not None else None,
                       'currency': currency,
                       'subscription': subscription, 'peak_team': max(p['team_size'] for p in phases), 'phases': phases, 'rationale': b['rationale']})
    for row in result:
        row['total_cost'] = row['labour_cost'] + row['subscription'] if row['labour_cost'] is not None else None
    for row in result:
        # the reference of a project is its roadmap without AI, when it has one: deltas are read against it
        reference = next((x for x in result if x['namespace'] == row['namespace'] and not x['uses_ai']), None)
        if reference and reference is not row and row['total_cost'] is not None and reference['total_cost'] is not None:
            single_currency([row['currency'], reference['currency']])
        row['reference'] = reference['name'] if reference and reference is not row else None
        row['delta_months'] = row['months'] - reference['months'] if reference and reference is not row else None
        row['delta_cost'] = row['total_cost'] - reference['total_cost'] if reference and reference is not row and row['total_cost'] is not None and reference['total_cost'] is not None else None
    return sorted(result, key=lambda x: (x['namespace'], x['uses_ai'], x['months']))


def programme(rows):
    """The programme is the chosen roadmap of each project and the dependencies between them.

    Each cross-project dependency is checked on dates and on choice: waiting for a roadmap that its project did not
    recommend or select is an inconsistency. The driving path runs back from the latest phase through the predecessor
    that ends last, across projects.
    """
    chosen = chosen_by_project(rows)
    ids = {r['roadmap']['meta']['id']: r for r in chosen.values()}
    dependencies, issues = [], []
    for r in chosen.values():
        for e in r['external']:
            row = {**e, 'from_namespace': r['namespace'], 'from_roadmap': r['name'], 'target_chosen': e['roadmap_id'] in ids}
            dependencies.append(row)
            if e['satisfied'] is None: issues.append({'code': 'PHASE_UNKNOWN', **row})
            elif not e['satisfied']: issues.append({'code': 'DATES', **row})
            if not row['target_chosen']: issues.append({'code': 'NOT_THE_CHOSEN_ROADMAP', **row})
    node = {(r['namespace'], p['id']): (r, p) for r in chosen.values() for p in r['phases']}
    def predecessors(key_):
        r, p = node[key_]
        local = [(r['namespace'], d) for d in p.get('depends_on', []) if (r['namespace'], d) in node]
        remote = [(ids[e['roadmap_id']]['namespace'], e['target_phase']) for e in r['external'] if e['phase'] == p['id'] and e['roadmap_id'] in ids
                  and (ids[e['roadmap_id']]['namespace'], e['target_phase']) in node]
        return local + remote
    path = []
    if node:
        current = max(node, key=lambda k: (node[k][1]['end'], node[k][1]['start']))
        seen = set()
        while current and current not in seen:
            seen.add(current);path.append(current)
            before = predecessors(current)
            current = max(before, key=lambda k: node[k][1]['end']) if before else None
    path.reverse()
    return {'chosen': chosen, 'dependencies': dependencies, 'issues': issues,
            'critical_path': [{'namespace': ns, 'phase': pid, 'name': node[(ns, pid)][1]['name'], 'start': node[(ns, pid)][1]['start'],
                               'end': node[(ns, pid)][1]['end']} for ns, pid in path],
            'end': max((r['end'] for r in chosen.values()), default=None)}


def chosen_by_project(rows):
    """One roadmap per project: the selected one, else the recommended one, else none (the choice is still open)."""
    chosen = {}
    for status in ('SELECTED', 'RECOMMENDED'):
        for r in rows:
            if r['status'] == status: chosen.setdefault(r['namespace'], r)
    return chosen


# A business block or a construction unit carries a requirement as behaviour; a component, a device, a connection or
# a zone carries it as infrastructure. Both are legitimate; the second needs a named accountable role.
BUSINESS = {'air.ArchitectureBlock', 'air.ConstructionUnit'}


def compliance(objects, by_id, inputs=()):
    """Controls and quality requirements against the construction blocks that implement them.

    `inputs` are controls and requirements received from a shared kernel; they must be mapped even when no project
    object references them yet.
    """
    subjects = {o['meta']['id']: o for o in list(objects) + list(inputs) if o['meta']['type'] in ('air.Control', 'air.QualityRequirement')}
    mappings = defaultdict(list)
    for m in (o for o in objects if o['meta']['type'] == 'air.ComplianceMapping'):
        mappings[m['body']['subject']['id']].append(m)
    rows = []
    for sid, s in sorted(subjects.items(), key=lambda kv: (kv[1]['meta']['type'], kv[1]['meta']['name'])):
        ms = mappings.get(sid, [])
        implementers = sorted({(by_id[r['id']]['meta']['type'][4:], by_id[r['id']]['meta']['name']) if r['id'] in by_id else ('?', r['id'])
                               for m in ms for r in m['body'].get('implemented_by', [])})
        statuses = sorted({m['body']['status'] for m in ms})
        per_project = {}
        for m in ms: per_project.setdefault(m['meta']['namespace'], set()).add(m['body']['status'])
        by_project = {ns: '+'.join(sorted(v)) for ns, v in sorted(per_project.items())}
        implemented_in = sorted({m['meta']['namespace'] for m in ms if m['body'].get('implemented_by')})
        kinds = lambda mappings: {by_id[r['id']]['meta']['type'] if r['id'] in by_id else '?' for m in mappings for r in m['body'].get('implemented_by', [])}
        scope = lambda found: ('BOTH' if found & BUSINESS and found - BUSINESS else 'BUSINESS' if found & BUSINESS else 'TECHNICAL' if found else 'NONE')
        ownership = {ns: {'scope': scope(kinds([m for m in ms if m['meta']['namespace'] == ns])),
                          'accountable': sorted({by_id[m['body']['accountable']['id']]['meta']['name'] if m['body']['accountable']['id'] in by_id else m['body']['accountable']['id']
                                                 for m in ms if m['meta']['namespace'] == ns and 'accountable' in m['body']})}
                     for ns in sorted({m['meta']['namespace'] for m in ms}) if by_project.get(ns) != 'NOT_APPLICABLE'}
        rows.append({'subject': s, 'kind': s['meta']['type'][4:], 'name': s['meta']['name'], 'namespace': s['meta']['namespace'],
                     'by_project': by_project, 'implemented_in': implemented_in, 'ownership': ownership,
                     'scope': scope(kinds(ms)),
                     # a project that declares a requirement not applicable names who implements it; the programme view confirms it
                     'delegated': {ns: implemented_in or sorted({m['body']['delegated_to'] for m in ms if m['meta']['namespace'] == ns and 'delegated_to' in m['body']})
                                   for ns, st in by_project.items() if st == 'NOT_APPLICABLE'},
                     'delegation_confirmed': bool(implemented_in),
                     'mappings': ms, 'implementers': implementers, 'status': statuses[0] if len(statuses) == 1 else ('+'.join(statuses) if statuses else 'UNMAPPED'),
                     'verification': sorted({by_id[v['id']]['meta']['name'] if v['id'] in by_id else v['id'] for m in ms for v in m['body'].get('verification', [])})})
    return rows
