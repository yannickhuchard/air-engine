"""Project participation is a declaration, distinct from identity and authority."""
from datetime import date

NAMES = ['StakeholderParticipation']
STATES = ['INVOLVED', 'TO_INVOLVE', 'MISSING']
ACTIONS = ['NONE', 'ASSIGN', 'RECRUIT', 'PARTNER', 'ASSESS']


def bodies(record, text, uri, ref, nonempty, day):
    return {'air.StakeholderParticipation': record({
        'scope': ref, 'role': ref, 'stakeholder': ref, 'state': {'enum': STATES},
        'reason': text, 'responsibilities': {'type': 'array', 'items': text, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True},
        'architecture_links': nonempty, 'engagement_plan': text, 'coordination_owner': uri,
        'staffing_action': {'enum': ACTIONS}, 'needed_by': day},
        ['scope', 'role', 'state', 'reason', 'responsibilities', 'architecture_links', 'engagement_plan', 'coordination_owner', 'staffing_action'])}


def slots(obj, data_types):
    if obj['meta']['type'] != 'air.StakeholderParticipation': return
    b = obj['body']
    for field, kinds in [('scope', ['air.Scope']), ('role', ['air.Role']), ('stakeholder', ['air.Stakeholder', 'air.Actor', 'air.OrganizationUnit'])]:
        if field in b: yield 'body/' + field, b[field], kinds
    for i, r in enumerate(b['architecture_links']): yield 'body/architecture_links/' + str(i), r, data_types


def local_issues(obj):
    if obj['meta']['type'] != 'air.StakeholderParticipation': return
    b = obj['body']
    if (b['state'] == 'MISSING') == ('stakeholder' in b):
        yield 'AIR_STAKEHOLDER_ASSIGNMENT', 'INVOLVED and TO_INVOLVE name a stakeholder; MISSING declares a vacant role without an invented identity'
    if b['state'] == 'MISSING' and b['staffing_action'] == 'NONE':
        yield 'AIR_STAKEHOLDER_STAFFING', 'A missing stakeholder has a staffing action or an explicit ASSESS action'
    if b['state'] == 'INVOLVED' and b['staffing_action'] != 'NONE':
        yield 'AIR_STAKEHOLDER_STAFFING', 'An involved stakeholder is already assigned; staffing_action is NONE'
    if 'needed_by' in b:
        try: date.fromisoformat(b['needed_by'])
        except ValueError: yield 'AIR_STAKEHOLDER_DATE', 'The required participation date exists in the calendar'
    if any(r['id'] == obj['meta']['id'] for r in b['architecture_links']):
        yield 'AIR_STAKEHOLDER_SELF_LINK', 'Participation links to the architecture it supports, not to itself'
