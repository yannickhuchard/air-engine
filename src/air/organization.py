"""Inspect declared organizational responsibilities in an exact authorized snapshot."""
from air.access import ScopedStore
from air.core import record, digest
from air.expr import artifact_digest, bounded, ExprError
from air.foundation import check_schema, exact, key, InvalidModel
from air.projections import SNAPSHOT, snapshot

REQUEST = record({'baseline': SNAPSHOT})
ENGINE = 'air.organization-dossier/0.21'


def inspect_organization(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    try: bounded(exported)
    except ExprError as exc: raise InvalidModel('Organization context exceeds its budget') from exc
    groups = {'air.OrganizationUnit': 'units', 'air.Role': 'roles', 'air.Actor': 'actors',
              'air.Domain': 'domains', 'air.AuthorityScope': 'authorities'}
    report = {'engine': ENGINE, 'baseline': request['baseline'], **{v: [] for v in groups.values()},
              'declarations_only': True, 'authorization_granted': False, 'policy_updated': False,
              'competencies_verified': False, 'delegations_executed': False,
              'limitations': ['Declared responsibilities and limits are not server permissions or admission mandates',
                             'No competency qualification or textual limit evaluation is performed'],
              'request_digest': artifact_digest(request)}
    for obj in sorted(exported['objects'], key=lambda o: key(exact(o))):
        group = groups.get(obj['meta']['type'])
        if group:
            report[group].append({'reference': {**exact(obj), 'digest': digest(obj)}, 'name': obj['meta']['name'],
                                 'namespace': obj['meta']['namespace'], 'validity': obj['meta']['validity'],
                                 'lifecycle': obj['meta']['lifecycle'], 'declared': obj['body']})
    report['report_digest'] = artifact_digest(report)
    try: bounded(report)
    except ExprError as exc: raise InvalidModel('Organization report exceeds its budget') from exc
    return report
