"""Explicit coverage beyond document presence; no semantic truth or execution inferred."""
from collections import Counter, defaultdict
import hashlib
from air.core import digest
from air.foundation import key


def checks(exported, context):
    plan = context['body'].get('assurance_plan')
    if plan is None: return []
    objects = exported['objects']; by = {key(o['meta']): o for o in objects}
    home = exported['baseline']['meta']['namespace']; rows = []
    owned = [o for o in objects if o['meta']['namespace'] == home]
    functions_by_requirement = defaultdict(set); contracts_by_function = defaultdict(set); units_by_requirement = defaultdict(set)
    mappings_by_requirement = defaultdict(list); quality_by_requirement = defaultdict(list)
    for obj in objects:
        kind, body, identity = obj['meta']['type'], obj['body'], key(obj['meta'])
        if kind == 'air.Function':
            for r in body['satisfies']: functions_by_requirement[key(r)].add(identity)
        elif kind == 'air.SemanticContract':
            for op in body['operations']: contracts_by_function[key(op['function'])].add(identity)
        elif kind == 'air.ConstructionUnit':
            for r in body['justified_by']: units_by_requirement[key(r)].add(identity)
    for m in plan['requirements']: mappings_by_requirement[key(m['requirement'])].append(m)
    for m in plan['quality']: quality_by_requirement[key(m['requirement'])].append(m)
    def add(code, obj, refs, issues):
        suffix = hashlib.sha256(obj['meta']['id'].encode()).hexdigest()[:24]
        rows.append({'code': 'ASSURANCE.' + code + ':' + suffix, 'subject': obj,
                     'references': refs, 'issues': sorted(set(issues))})
    for requirement in [o for o in owned if o['meta']['type'] == 'air.Requirement' and o['body']['priority'] == 'MUST']:
        mappings = mappings_by_requirement[key(requirement['meta'])]
        issues = []; refs = [requirement]
        if len(mappings) != 1: issues.append('ONE_REQUIREMENT_COVERAGE_REQUIRED')
        else:
            mapping = mappings[0]
            goal = by.get(key(mapping['goal']))
            if not goal or not goal['body'].get('measures') or not goal['body'].get('targets') or any(
                    t['value'].get('state', 'KNOWN') != 'KNOWN' or 'value' not in t['value'] for t in goal['body']['targets']):
                issues.append('MEASURABLE_BUSINESS_OUTCOME_REQUIRED')
            functions = functions_by_requirement[key(requirement['meta'])]
            contracts = set().union(*(contracts_by_function[f] for f in functions))
            units = units_by_requirement[key(requirement['meta'])]
            targets = functions | contracts | units | {key(requirement['meta'])}
            cases = [by.get(key(mapping[f])) for f in ('happy', 'failure', 'recovery')]
            if len({key(mapping[f]) for f in ('happy', 'failure', 'recovery')}) != 3:
                issues.append('DISTINCT_HAPPY_FAILURE_RECOVERY_CASES_REQUIRED')
            if any(not c or c['meta']['type'] != 'air.VerificationCase' or key(c['body']['target']) not in targets for c in cases):
                issues.append('CASE_OUTSIDE_REQUIREMENT_CHAIN')
            refs += [o for o in [goal, *cases] if o]
        add('REQUIREMENT', requirement, refs, issues)
    for requirement in [o for o in owned if o['meta']['type'] == 'air.QualityRequirement' and o['body']['priority'] == 'MUST']:
        mappings = quality_by_requirement[key(requirement['meta'])]
        issues = []; refs = [requirement]
        target = requirement['body'].get('target')
        if not target or target['value'].get('state', 'KNOWN') != 'KNOWN' or 'value' not in target['value']:
            issues.append('MEASURABLE_QUALITY_TARGET_REQUIRED')
        if not requirement['body'].get('scope') or not requirement['body'].get('source'):
            issues.append('QUALITY_SCOPE_AND_BASIS_REQUIRED')
        if len(mappings) != 1: issues.append('ONE_QUALITY_VERIFICATION_REQUIRED')
        else:
            case = by.get(key(mappings[0]['case']))
            if not case or case['meta']['type'] != 'air.VerificationCase' or key(case['body']['target']) != key(requirement['meta']):
                issues.append('QUALITY_CASE_MUST_TARGET_REQUIREMENT')
            elif case['body']['method'] != ('TEST' if requirement['body']['verification_method'] == 'MONITORING' else requirement['body']['verification_method']):
                issues.append('QUALITY_VERIFICATION_METHOD_MISMATCH')
            else: refs.append(case)
        add('QUALITY', requirement, refs, issues)
    counts = Counter(m['kind'] for m in plan['lifecycle'])
    for kind in ('MIGRATION', 'ROLLBACK', 'RETIREMENT'):
        refs = [by.get(key(m['case'])) for m in plan['lifecycle'] if m['kind'] == kind]
        issues = [] if counts[kind] == 1 and all(r and r['meta']['type'] == 'air.VerificationCase' for r in refs) else ['ONE_LIFECYCLE_CASE_REQUIRED']
        if len({key(m['case']) for m in plan['lifecycle']}) != len(plan['lifecycle']):
            issues.append('DISTINCT_LIFECYCLE_CASES_REQUIRED')
        # Context is the subject, so lifecycle exclusions use the existing exact-review mechanism.
        add(kind, context, [r for r in refs if r], issues)
    return rows
