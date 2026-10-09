"""Public catalogue fingerprints and bounded, offline client comparisons.

No registry, credential or client configuration is read or changed. A supplied
snapshot is an observation supplied by its author, not a successful tool call.
"""
from copy import deepcopy
from air import __version__
from air.expr import artifact_digest
from air.foundation import check_schema

ENGINE = 'air.client-contract/1'
PROFILES = ('all', 'contribute', 'read', 'guided')


def catalogue(profile='all'):
    from air.mcp import published_schema, published_tools
    return [{'name': name, 'inputSchema': published_schema(tool[1])}
            for name, tool in sorted(published_tools(profile).items())]


def contract():
    return {'engine': ENGINE, 'engine_version': __version__,
            'scope': 'SUPPORTED_CATALOGUES_NOT_AUTHORIZED_SESSION',
            'uri_policy': 'LEXICAL_SCHEME_IN_PUBLIC_SCHEMA_FULL_URI_ON_SERVER',
            'profiles': {p: {'tools': len(catalogue(p)),
                             'catalogue_digest': artifact_digest(catalogue(p))}
                         for p in PROFILES},
            'required_for_site': ['air_whoami', 'air_capabilities', 'air_list_revisions',
                                 'air_browse_baseline', 'air_compile_deliverables'],
            'required_for_branding': ['air_compile_branding'],
            'recovery': ['Compare the actual client tools/list with its authorized profile.',
                         'Refresh tool discovery in the client when the catalogue differs.',
                         'Retry the exact URN and pin; never substitute an identifier.',
                         'A matching catalogue does not prove successful authentication or reads.']}


def compare(snapshot, profile='guided'):
    """Compare the *observed* catalogue, without inferring session authority."""
    if profile not in PROFILES: raise ValueError('Unknown client catalogue profile')
    check_schema(snapshot, {'type': 'object', 'additionalProperties': False,
        'required': ['tools'], 'properties': {
            'tools': {'type': 'array', 'maxItems': 200, 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['name', 'inputSchema'], 'properties': {
                    'name': {'type': 'string', 'maxLength': 100},
                    'inputSchema': {'type': 'object'}}}},
            'expected_baseline': {'type': 'object'},
            'observed_baseline': {'type': 'object'}}})
    expected = catalogue(profile)
    actual = sorted(deepcopy(snapshot['tools']), key=lambda t: t['name'])
    names = [t['name'] for t in actual]
    if len(names) != len(set(names)): raise ValueError('Duplicate client tool names')
    by_name = {t['name']: t for t in actual}
    missing = [t['name'] for t in expected if t['name'] not in by_name]
    different = [t['name'] for t in expected if t['name'] in by_name
                 and t['inputSchema'] != by_name[t['name']]['inputSchema']]
    extra = sorted(set(names) - {t['name'] for t in expected})
    context = 'NOT_CHECKED'
    if 'expected_baseline' in snapshot:
        from air.core import REF, record
        pin_schema = record({**REF['properties'], 'digest': {'type': 'string', 'pattern': '^sha256:[a-f0-9]{64}$'}})
        check_schema(snapshot['expected_baseline'], pin_schema)
        if 'observed_baseline' not in snapshot: context = 'OBSERVATION_MISSING'
        else:
            check_schema(snapshot['observed_baseline'], pin_schema)
            context = 'MATCH' if snapshot['expected_baseline'] == snapshot['observed_baseline'] else 'MISMATCH'
    elif 'observed_baseline' in snapshot:
        raise ValueError('An observed baseline requires an expected exact baseline')
    return {'engine': ENGINE, 'engine_version': __version__, 'profile': profile,
            'catalogue_result': 'MATCH' if not (missing or different or extra) else 'MISMATCH',
            'expected_catalogue_digest': artifact_digest(expected),
            'observed_catalogue_digest': artifact_digest(actual),
            'missing_tools': missing, 'different_schemas': different, 'extra_tools': extra,
            'baseline_context': context, 'observation_basis': 'USER_SUPPLIED_SNAPSHOT',
            'client_reads_verified': False, 'configuration_changed': False}
