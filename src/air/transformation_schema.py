"""Declared sourcing and design-work governance, never external execution."""
from datetime import date
from collections import defaultdict

NAMES = ['SourcingStrategy', 'TransformationProgramme', 'ArchitectureProject', 'ArchitectureTask']
TERMINAL = ('COMPLETED', 'CANCELLED')
TASK_TERMINAL = ('DONE', 'CANCELLED')


def bodies(record, text, uri, ref, refs, nonempty, instant, day):
    optional = lambda fields, required: record(fields, required)
    project_status = {'enum': ['PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED']}
    return {
        'air.SourcingStrategy': optional({'scope': ref, 'decision': ref, 'strategy': {'enum': ['RFI_THEN_RFP', 'RFP_DIRECT', 'RFI_ONLY', 'NO_CONSULTATION']},
            'purpose': text, 'owner': uri, 'milestone': ref, 'criteria': {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
            'architecture_links': nonempty, 'status': {'enum': ['DRAFT', 'READY_TO_LAUNCH', 'LAUNCHED', 'EVALUATING', 'SELECTED', 'CANCELLED']},
            'evidence': refs, 'selected_supplier': ref}, ['scope', 'decision', 'strategy', 'purpose', 'owner', 'milestone', 'criteria', 'architecture_links', 'status', 'evidence']),
        'air.TransformationProgramme': optional({'purpose': text, 'scope': ref, 'owner': uri, 'parent': ref, 'projects': refs,
            'start': day, 'end': day, 'status': project_status, 'closure_decision': ref, 'closed_at': instant},
            ['purpose', 'scope', 'owner', 'projects', 'start', 'end', 'status']),
        'air.ArchitectureProject': optional({'code': {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{0,31}$'},
            'scope_kind': {'const': 'ARCHITECTURE_DESIGN'}, 'purpose': text, 'scope': ref, 'owner': uri,
            'tasks': refs, 'depends_on': {'type': 'array', 'maxItems': 128, 'items': record({'project': ref, 'kind': {'enum': ['REFERENCE', 'FINISH_TO_START']}})},
            'status': project_status, 'closure_decision': ref, 'closed_at': instant},
            ['code', 'scope_kind', 'purpose', 'scope', 'owner', 'tasks', 'depends_on', 'status']),
        'air.ArchitectureTask': optional({'project': ref, 'purpose': text, 'owner': uri,
            'kind': {'enum': ['RESEARCH', 'MODELLING', 'VERIFICATION', 'REVIEW', 'DECISION', 'DOCUMENTATION']},
            'status': {'enum': ['TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'CANCELLED']}, 'depends_on': refs,
            'deliverables': refs, 'evidence': refs, 'due': day, 'closed_at': instant},
            ['project', 'purpose', 'owner', 'kind', 'status', 'depends_on', 'deliverables', 'evidence']),
    }


def slots(obj, data_types):
    kind, b = obj['meta']['type'], obj['body']
    fields = {
        'air.SourcingStrategy': {'scope': ['air.Scope'], 'decision': ['air.Decision'], 'milestone': ['air.Milestone'], 'selected_supplier': ['air.Stakeholder']},
        'air.TransformationProgramme': {'scope': ['air.Scope'], 'parent': ['air.TransformationProgramme'], 'closure_decision': ['air.Decision']},
        'air.ArchitectureProject': {'scope': ['air.Scope'], 'closure_decision': ['air.Decision']},
        'air.ArchitectureTask': {'project': ['air.ArchitectureProject']},
    }
    for field, targets in fields.get(kind, {}).items():
        if field in b: yield 'body/' + field, b[field], targets
    arrays = {
        'air.SourcingStrategy': {'architecture_links': data_types, 'evidence': ['air.Source', 'air.Decision']},
        'air.TransformationProgramme': {'projects': ['air.ArchitectureProject']},
        'air.ArchitectureProject': {'tasks': ['air.ArchitectureTask']},
        'air.ArchitectureTask': {'depends_on': ['air.ArchitectureTask'], 'deliverables': data_types, 'evidence': ['air.Source', 'air.Decision']},
    }
    for field, targets in arrays.get(kind, {}).items():
        for i, reference in enumerate(b[field]): yield 'body/' + field + '/' + str(i), reference, targets
    if kind == 'air.ArchitectureProject':
        for i, d in enumerate(b['depends_on']): yield 'body/depends_on/' + str(i) + '/project', d['project'], ['air.ArchitectureProject']


def local_issues(obj):
    kind, b = obj['meta']['type'], obj['body']
    if kind in ('air.ArchitectureProject', 'air.TransformationProgramme'):
        closing = b['status'] in TERMINAL
        if closing != ('closure_decision' in b and 'closed_at' in b) or not closing and ('closure_decision' in b or 'closed_at' in b):
            yield 'AIR_WORK_CLOSURE', 'A terminal project/programme declares its exact closure decision and date; active work has neither'
    if kind == 'air.ArchitectureTask':
        closing = b['status'] in TASK_TERMINAL
        if closing and (not b['evidence'] or 'closed_at' not in b): yield 'AIR_TASK_CLOSURE', 'Terminal design work has evidence and a declared closure date'
        if not closing and 'closed_at' in b: yield 'AIR_TASK_CLOSURE', 'An active task has no closure date'
    if kind == 'air.SourcingStrategy':
        if b['status'] in ('LAUNCHED', 'EVALUATING', 'SELECTED') and not b['evidence']: yield 'AIR_SOURCING_EVIDENCE', 'A declared launched consultation has exact evidence'
        if (b['status'] == 'SELECTED') != ('selected_supplier' in b): yield 'AIR_SOURCING_SELECTION', 'A selected supplier is declared exactly at SELECTED'
        if b['strategy'] == 'NO_CONSULTATION' and b['status'] in ('LAUNCHED', 'EVALUATING', 'SELECTED'): yield 'AIR_SOURCING_STRATEGY', 'NO_CONSULTATION cannot claim a launched or evaluated consultation'
    if kind == 'air.TransformationProgramme':
        try:
            if date.fromisoformat(b['start']) > date.fromisoformat(b['end']): yield 'AIR_PROGRAMME_PERIOD', 'Programme start precedes its end'
        except ValueError: yield 'AIR_PROGRAMME_PERIOD', 'Programme dates exist in the calendar'


def graph_issues(objects, by_ref):
    key = lambda r: (r['id'], r['revision'])
    own = lambda o: key({'id': o['meta']['id'], 'revision': o['meta']['revision']})
    tasks_by_project, programmes_by_parent = defaultdict(list), defaultdict(list)
    for o in objects:
        if o['meta']['type'] == 'air.ArchitectureTask': tasks_by_project[key(o['body']['project'])].append(o)
        elif o['meta']['type'] == 'air.TransformationProgramme' and o['body'].get('parent'):
            programmes_by_parent[key(o['body']['parent'])].append(o)
    for o in objects:
        b, kind, location = o['body'], o['meta']['type'], o['meta']['id']
        if kind == 'air.ArchitectureProject':
            listed = {key(r) for r in b['tasks']}
            actual = tasks_by_project[own(o)]
            if {own(t) for t in actual} != listed: yield 'AIR_PROJECT_TASK_MEMBERSHIP', location, 'Every task of this exact project is listed, with no foreign task'
            if b['status'] in TERMINAL and any(t['body']['status'] not in TASK_TERMINAL for t in actual): yield 'AIR_PROJECT_ACTIVE_TASK', location, 'A closed project has no active design task'
            if b['status'] in ('ACTIVE', 'COMPLETED'):
                for d in b['depends_on']:
                    target = by_ref.get(key(d['project']))
                    if d['kind'] == 'FINISH_TO_START' and target and target['body'].get('status') != 'COMPLETED':
                        yield 'AIR_PROJECT_DEPENDENCY', location, 'An active or completed project has completed its finish-to-start prerequisite projects'
        elif kind == 'air.ArchitectureTask' and b['status'] == 'DONE':
            for r in b['depends_on']:
                d = by_ref.get(key(r))
                if d and d['body'].get('status') != 'DONE': yield 'AIR_TASK_DEPENDENCY', location, 'A completed task has completed its prerequisite tasks'
        elif kind == 'air.TransformationProgramme' and b['status'] in TERMINAL:
            children = [by_ref[key(r)] for r in b['projects'] if key(r) in by_ref]
            children += programmes_by_parent[own(o)]
            if any(c['body']['status'] not in TERMINAL for c in children): yield 'AIR_PROGRAMME_ACTIVE_WORK', location, 'A closed programme has no active child project or programme'
        elif kind == 'air.SourcingStrategy':
            decision = by_ref.get(key(b['decision']))
            if decision and key(b['scope']) not in {key(r) for r in decision['body'].get('basis', [])}:
                yield 'AIR_SOURCING_DECISION_SCOPE', location, 'The sourcing decision cites the exact scope as part of its basis'
    # Cycles would prevent a finish-to-start task/project chain or programme hierarchy.
    for kind, field in [('air.ArchitectureTask', 'depends_on'), ('air.ArchitectureProject', 'depends_on'), ('air.TransformationProgramme', 'parent')]:
        edges = {}
        for o in objects:
            if o['meta']['type'] != kind: continue
            b = o['body']
            refs = ([b[field]] if field in b else []) if field == 'parent' else [d['project'] for d in b[field] if d['kind'] == 'FINISH_TO_START'] if kind == 'air.ArchitectureProject' else b[field]
            edges[own(o)] = {key(r) for r in refs}
        done = set()
        for start in sorted(edges):
            visiting = set(); stack = [(start, False)]
            while stack:
                current, leaving = stack.pop()
                if leaving: visiting.discard(current); done.add(current); continue
                if current in done: continue
                if current in visiting:
                    yield 'AIR_WORK_DEPENDENCY_CYCLE', start[0], kind + ' has a dependency cycle'; break
                visiting.add(current); stack.append((current, True))
                stack.extend((n, False) for n in sorted(edges.get(current, ()), reverse=True) if n not in done)


def canonicalize(obj):
    kind, b = obj['meta']['type'], obj['body']
    fields = {'air.SourcingStrategy': ['architecture_links', 'evidence'], 'air.TransformationProgramme': ['projects'],
        'air.ArchitectureProject': ['tasks'], 'air.ArchitectureTask': ['depends_on', 'deliverables', 'evidence']}
    for field in fields.get(kind, []): b[field].sort(key=lambda r: (r['id'], r['revision']))
    if kind == 'air.ArchitectureProject': b['depends_on'].sort(key=lambda d: (d['project']['id'], d['project']['revision'], d['kind']))
