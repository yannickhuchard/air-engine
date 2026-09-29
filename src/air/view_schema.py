"""Managed derived View products, outside the source baseline member profiles."""
from air.expr import artifact_digest
PROFILE = 'air.view/0.20'
CHECKSUM = {'type': 'string', 'pattern': '^sha256:[a-f0-9]{64}$'}


def bodies(record, text, uri, ref):
    component = record({'name': {'type': 'string', 'pattern': '^air/[a-z_]+[.]py$'}, 'digest': CHECKSUM})
    dependency = record({'name': {'type': 'string', 'minLength': 1, 'maxLength': 128}, 'version': {'type': 'string', 'minLength': 1, 'maxLength': 128}})
    toolchain = record({'binding': {'const': 'air.toolchain/0.20'}, 'engine': {'const': 'air.audience/0.19'},
        'air_version': text, 'python_version': text, 'source_observation': {'const': 'MODULE_STARTUP'},
        'components': {'type': 'array', 'items': component, 'minItems': 1, 'maxItems': 128},
        'dependencies': {'type': 'array', 'items': dependency, 'minItems': 1, 'maxItems': 32}, 'source_digest': CHECKSUM})
    def artifact(media_type):
        return record({'locator': uri, 'media_type': {'const': media_type}, 'size': {'type': 'integer', 'minimum': 1, 'maximum': 16777216},
            'digest': record({'algorithm': {'const': 'sha256'}, 'value': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}}),
            'access_policy': text, 'retention_policy': text})
    return {'air.View': record({'viewpoint': ref, 'baseline': ref, 'generator': toolchain,
        'output': artifact('text/html'), 'source_mapping': artifact('application/json')})}


def slots(obj):
    if obj['meta']['type'] != 'air.View': return
    yield 'body/viewpoint', obj['body']['viewpoint'], ['air.Viewpoint']
    yield 'body/baseline', obj['body']['baseline'], ['air.Baseline']


def local_issues(obj):
    if obj['meta']['type'] != 'air.View': return
    generator = obj['body']['generator']
    for field in ('components', 'dependencies'):
        if len({item['name'] for item in generator[field]}) != len(generator[field]):
            yield 'AIR_VIEW_TOOLCHAIN', 'Toolchain component and dependency names must be unique'
    components = sorted(generator['components'], key=lambda item: item['name'])
    if generator['source_digest'] != artifact_digest(components):
        yield 'AIR_VIEW_TOOLCHAIN', 'Toolchain source digest differs from its components'


def canonicalize(obj):
    if obj['meta']['type'] != 'air.View': return
    for field in ('components', 'dependencies'): obj['body']['generator'][field].sort(key=lambda item: item['name'])
