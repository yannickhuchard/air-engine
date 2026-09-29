"""Draft contributions and design decisions, without business authority effects."""
import json

PROFILE = 'air.collaboration/0.13'
NAMES = ['Contribution', 'Decision']


def bodies(record, text, uri, ref, nonempty):
    choice = {'oneOf': [text, ref]}
    texts = {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True}
    return {
        'air.Contribution': record({'author': uri, 'target': nonempty,
            'kind': {'enum': ['QUESTION', 'PROPOSAL', 'CRITIQUE', 'REVIEW', 'RESOLUTION']}, 'message': text,
            'resolution': ref}, ['author', 'target', 'kind', 'message']),
        'air.Decision': record({'question': text, 'alternatives': {'type': 'array', 'items': choice, 'minItems': 1, 'maxItems': 256, 'uniqueItems': True},
            'selection': choice, 'rationale': text, 'basis': nonempty, 'authority': uri,
            'consequences': texts, 'revisit_conditions': texts}),
    }


def slots(obj, data_types):
    body, kind = obj['body'], obj['meta']['type']
    if kind == 'air.Contribution':
        for ref in body['target']: yield 'body/target', ref, data_types
        if 'resolution' in body: yield 'body/resolution', body['resolution'], ['air.ChangeSet', 'air.Decision']
    elif kind == 'air.Decision':
        for ref in body['basis']: yield 'body/basis', ref, data_types
        for item in body['alternatives']:
            if isinstance(item, dict): yield 'body/alternatives', item, data_types
        if isinstance(body['selection'], dict): yield 'body/selection', body['selection'], data_types


def local_issues(obj):
    if obj['meta']['type'] == 'air.Decision' and obj['body']['selection'] not in obj['body']['alternatives']:
        yield 'AIR_DECISION_SELECTION', 'Selection must identify an exact declared alternative'


def canonicalize(obj):
    kind, body = obj['meta']['type'], obj['body']
    if kind == 'air.Contribution': body['target'].sort(key=lambda ref: (ref['id'], ref['revision']))
    if kind == 'air.Decision':
        body['basis'].sort(key=lambda ref: (ref['id'], ref['revision']))
        body['alternatives'].sort(key=lambda choice: json.dumps(choice, sort_keys=True, ensure_ascii=False))
