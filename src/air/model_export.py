"""Lossless exports of the declared model, not an inferred database design."""
import base64
from air import artifacts
from air.core import digest, schema

ENGINE = 'air.model-export/1'


def export_model(store, principal, policy, exports):
    retained, descriptors = {}, {}
    retained_size = 0
    for exported in exports:
        for obj in exported['objects']:
            if obj['meta']['type'] == 'air.DataSchema':
                a = obj['body']['artifact']
                ref = {'id': a['locator'], 'digest': 'sha256:' + a['digest']['value']}
                identity = (ref['id'], ref['digest'])
                if identity not in retained:
                    manifest = artifacts.describe(store, principal, policy, {'artifact': ref})
                    if manifest['size'] != a['size'] or manifest['media_type'] != a['media_type']:
                        from air.foundation import InvalidModel
                        raise InvalidModel('DataSchema artifact descriptor differs from retained manifest')
                    retained_size += manifest['size']
                    if retained_size > 8 * 1024 * 1024:
                        from air.foundation import TooLarge
                        raise TooLarge('Retained schema artifacts exceed 8 MiB; export fewer baselines')
                    manifest, raw = artifacts.download(store, principal, policy, {'artifact': ref})
                    retained[identity] = {'artifact': ref, 'manifest': manifest,
                                         'encoding': 'base64', 'content': base64.b64encode(raw).decode('ascii')}
                descriptors[obj['meta']['type']] = schema(obj['meta']['type'])
            else:
                descriptors[obj['meta']['type']] = schema(obj['meta']['type'])
    snapshots = []
    for e in exports:
        objects = sorted(e['objects'], key=lambda o: (o['meta']['id'], o['meta']['revision']))
        snapshots.append({'baseline': e['baseline'], 'digest': e['digest'], 'objects': objects,
                          'object_digests': [{'id': o['meta']['id'], 'revision': o['meta']['revision'], 'digest': digest(o)} for o in objects],
                          'dependency_lock': e['dependency_lock']})
    return {'engine': ENGINE, 'scope': 'EXACT_DECLARED_BASELINES', 'snapshots': snapshots,
            'metamodel': descriptors, 'schema_artifacts': [retained[k] for k in sorted(retained)],
            'limitations': ['Only declared objects are exported; missing design information is not inferred.',
                            'External source documents are references, not fetched or embedded.',
                            'DataSchema bytes are retained and authorized; no network schema resolution.',
                            'No SQL DDL, schema migration, runtime behavior or compliance certification is generated.'],
            'registry_written': False, 'authorization_granted': False}
