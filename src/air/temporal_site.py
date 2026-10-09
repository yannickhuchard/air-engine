"""Offline comparisons of explicitly pinned designs and their declared dates.

No registry receipt time is available here. A filtered design is never rebuilt
or promoted to a closed baseline, and planned dates do not prove execution.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from air.core import digest, record, TEXT
from air.expr import artifact_digest
from air.foundation import InvalidModel, TooLarge, exact
from air.projections import SNAPSHOT, changes, reference_neutral

ENGINE = 'air.temporal-site/1'
COMPARISON = record({'title': {**TEXT, 'maxLength': 200}, 'before': SNAPSHOT, 'after': SNAPSHOT})
LABELS = {'UNCHANGED': 'Identique', 'ADDED': 'Ajouté', 'REMOVED': 'Retiré',
          'CONTENT': 'Contenu modifié', 'REFERENCE_ONLY': 'Références révisées',
          'REVISION_ONLY': 'Révision ou date auteur', 'METADATA_ONLY': 'Métadonnées modifiées',
          'MULTIPLE_REVISIONS': 'Plusieurs révisions : comparaison groupée'}


def pin(exported): return {**exact(exported['baseline']), 'digest': exported['digest']}
def identity(ref): return ref['id'], ref['revision'], ref['digest']
def instant(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def object_info(obj):
    meta = obj['meta'];period = meta['validity']
    return {'reference': {**exact(obj), 'digest': digest(obj)}, 'type': meta['type'],
            'name': meta['name'], 'description': meta['description'], 'lifecycle': meta['lifecycle'],
            'validity': period, 'valid_start': instant(period['start']),
            'valid_end': instant(period['end']) if period['end'] is not None else None,
            'author_recorded_at': meta['recorded_at']}


def compare(before, after, title):
    groups = []
    maps = []
    for snapshot in (before, after):
        grouped = defaultdict(list)
        for obj in snapshot['objects']: grouped[obj['meta']['id']].append(obj)
        maps.append(grouped)
    old, new = maps
    for key in sorted(old.keys() | new.keys()):
        a, b = (sorted(m.get(key, []), key=lambda o: o['meta']['revision']) for m in maps)
        fields = []
        if len(a) > 1 or len(b) > 1:
            status = 'UNCHANGED' if [digest(o) for o in a] == [digest(o) for o in b] else 'MULTIPLE_REVISIONS'
        elif not a: status = 'ADDED'
        elif not b: status = 'REMOVED'
        elif a[0] == b[0]: status = 'UNCHANGED'
        else:
            fields = changes(a[0], b[0])
            neutral = reference_neutral(a[0]) == reference_neutral(b[0])
            status = ('REVISION_ONLY' if a[0]['body'] == b[0]['body'] else 'REFERENCE_ONLY') if neutral else \
                     'METADATA_ONLY' if a[0]['body'] == b[0]['body'] else 'CONTENT'
        groups.append({'id': key, 'status': status, 'before': [object_info(o) for o in a],
                       'after': [object_info(o) for o in b], 'fields': fields})
    result = {'title': title, 'before': pin(before), 'after': pin(after), 'objects': groups,
              'summary': {kind: sum(g['status'] == kind for g in groups) for kind in LABELS},
              'same_namespace': before['baseline']['meta']['namespace'] == after['baseline']['meta']['namespace'],
              'semantic_compatibility': 'NOT_EXECUTED', 'execution_performed': False}
    result['comparison_digest'] = artifact_digest(result)
    return result


def project(exports, comparisons):
    """Consume only already authorized snapshots; never discover hidden history."""
    by_pin = {identity(pin(e)): e for e in exports}
    for c in comparisons:
        if identity(c['before']) not in by_pin or identity(c['after']) not in by_pin:
            raise InvalidModel('Site comparison endpoints must be among the exact requested baselines')
    snapshots = []
    for e in exports:
        if len(e['objects']) > 1000: raise TooLarge('Temporal site supports at most 1000 objects per baseline')
        objects = [object_info(o) for o in sorted(e['objects'], key=lambda o: (o['meta']['id'], o['meta']['revision']))]
        instants = sorted({v for o in objects for v in (o['valid_start'], o['valid_end']) if v is not None})
        plans, gaps = [], []
        for obj in e['objects']:
            if obj['meta']['type'] == 'air.Milestone':
                entries = [{'name': obj['meta']['name'], 'start': obj['body']['target_date'], 'end': None,
                            'criteria': obj['body']['exit_criteria'], 'selector': '/body/target_date'}]
            elif obj['meta']['type'] == 'air.Roadmap':
                entries = [{'name': p['name'], 'start': p['start'], 'end': p['end'], 'criteria': p.get('exit_criteria', []),
                            'selector': '/body/phases/' + str(i), 'declared': p} for i, p in enumerate(obj['body']['phases'])]
            else: continue
            for entry in entries:
                valid_dates = True
                try:
                    start = date.fromisoformat(entry['start']);end = date.fromisoformat(entry['end']) if entry['end'] else start
                    if end < start: raise ValueError('Reversed planned interval')
                except ValueError:
                    valid_dates = False
                    gaps.append({'code': 'INVALID_PLANNED_DATE', 'source': object_info(obj)['reference'], 'selector': entry['selector']})
                plans.append({**entry, 'source': object_info(obj)['reference'], 'planned_only': True, 'dates_valid': valid_dates})
        snapshots.append({'baseline': pin(e), 'name': e['baseline']['meta']['name'],
                          'namespace': e['baseline']['meta']['namespace'], 'objects': objects,
                          'validity_boundaries': instants, 'plans': sorted(plans, key=lambda p: (p['start'], p['name'])), 'gaps': gaps})
    result = {'engine': ENGINE, 'snapshots': snapshots,
              'comparisons': [compare(by_pin[identity(c['before'])], by_pin[identity(c['after'])], c['title']) for c in comparisons],
              'change_labels': LABELS, 'validity_policy': 'DECLARED_HALF_OPEN_INTERVAL',
              'registry_knowledge_history_available': False, 'author_recorded_at_is_registry_receipt': False,
              'filtered_view_is_closed_baseline': False, 'semantic_compatibility': 'NOT_EXECUTED',
              'business_execution_performed': False, 'registry_written': False, 'authorization_granted': False}
    result['report_digest'] = artifact_digest(result)
    return result
