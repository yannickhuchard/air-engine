"""Atomic, authenticated capture of derived views and their exact artifacts."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
from importlib import metadata, resources
import json
import platform
from sqlalchemy import select
from air import __version__, artifacts
from air.access import AccessPolicy, ScopedStore, Forbidden
from air.audience import compile_view, ENGINE
from air.collaboration import identity_context, identity_uri
from air.core import META, REF, TEXT, URI, canonical, digest, record, validate
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.jobs import check_identity
from air.packages import RECORD_REF, lock_registry, reference
from air.parsing import parse
from air.projections import SNAPSHOT
from air.reviews import record_key
from air.storage import Conflict, identities, revisions, service_records, now

FORMAT = 'air.view-capture/0.20'
REQUEST = record({'id': URI, 'revision': REF['properties']['revision'], 'name': TEXT,
    'baseline': SNAPSHOT, 'viewpoint': SNAPSHOT, 'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128}})
LOOKUP = record({'view': SNAPSHOT})
PAYLOAD = record({'format': {'const': FORMAT}, 'request': REQUEST, 'view': SNAPSHOT,
    'output': RECORD_REF, 'source_mapping': RECORD_REF, 'identity_context': artifacts.CONTEXT,
    'identity': URI, 'policy_digest': artifacts.CHECKSUM})
KEY_PAYLOAD = record({'format': {'const': 'air.view-capture-key/0.20'}, 'capture': RECORD_REF})
MAPPING_ITEM = record({'object': SNAPSHOT, 'selector': {'type': 'string', 'pattern': '^#[a-z][a-z0-9-]{1,127}$'}})
MAP = record({'format': {'const': 'air.view-mapping/0.20'}, 'engine': {'const': ENGINE},
    'baseline': SNAPSHOT, 'viewpoint': SNAPSHOT, 'content_digest': artifacts.CHECKSUM,
    'source_mapping': {'type': 'array', 'items': MAPPING_ITEM, 'maxItems': 1000},
    'context_mapping': {'type': 'array', 'items': MAPPING_ITEM, 'maxItems': 322},
    'objects_selected': {'type': 'integer', 'minimum': 0, 'maximum': 1000},
    'objects_excluded': {'type': 'integer', 'minimum': 0, 'maximum': 1000},
    'field_redaction': {'const': False}, 'authorization_granted': {'const': False}})


def _toolchain():
    components = [{'name': 'air/' + file.name, 'digest': 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest()}
        for file in resources.files('air').iterdir() if file.name.endswith('.py') and file.is_file()]
    components.sort(key=lambda item: item['name'])
    return {'binding': 'air.toolchain/0.20', 'engine': ENGINE, 'air_version': __version__, 'python_version': platform.python_version(),
        'source_observation': 'MODULE_STARTUP', 'components': components,
        'dependencies': [{'name': name, 'version': metadata.version(name)} for name in ('jsonschema', 'rfc8785')],
        'source_digest': artifact_digest(components)}


TOOLCHAIN = _toolchain()


def capture_id(view): return record_key('view-capture', view['id'], str(view['revision']))
def request_id(identity, namespace, key): return record_key('view-capture-key', identity, namespace + ':' + key)


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids = set();self.csp = False
    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in ('script', 'iframe', 'object', 'embed', 'base', 'form', 'img', 'link'):
            raise InvalidModel('Captured view contains active or external content')
        if any(name.startswith('on') or name in ('src', 'srcdoc', 'action', 'formaction') for name, _ in attributes):
            raise InvalidModel('Captured view contains active attributes')
        if 'href' in attrs and not (attrs['href'] or '').startswith('#'):
            raise InvalidModel('Captured view contains an external link')
        if 'id' in attrs:
            if attrs['id'] in self.ids or len(self.ids) >= 4096: raise InvalidModel('Captured view has ambiguous or excessive anchors')
            self.ids.add(attrs['id'])
        if tag == 'meta' and 'http-equiv' in attrs:
            if attrs['http-equiv'].lower() != 'content-security-policy': raise InvalidModel('Captured view contains an active meta directive')
            value = attrs.get('content', '')
            self.csp = all(part in value for part in ("default-src 'none'", "connect-src 'none'", "form-action 'none'", "base-uri 'none'"))


def _verified(store, conn, entry):
    if entry is None or entry['kind'] != 'view_capture': raise InvalidModel('View capture is unavailable')
    payload = entry['payload'];check_schema(payload, PAYLOAD)
    request = payload['request'];view = store._required(conn, payload['view'], 'air.View')
    if not validate(view)['valid']: raise InvalidModel('Captured View schema is invalid')
    baseline = store._export(conn, request['baseline']);objects = {key(exact(o)): o for o in baseline['objects']}
    viewpoint = objects.get(key(request['viewpoint']))
    if not viewpoint or viewpoint['meta']['type'] != 'air.Viewpoint' or digest(viewpoint) != request['viewpoint']['digest']:
        raise InvalidModel('Captured viewpoint differs from its source baseline')
    context = payload['identity_context'];identity = identity_uri(context);meta, body = view['meta'], view['body']
    if (entry['id'] != capture_id(payload['view']) or entry['scope'] != meta['namespace'] or meta['namespace'] != viewpoint['meta']['namespace']
        or entry['actor'] != context['subject'] or payload['identity'] != identity or meta['owner'] != identity
        or meta['provenance']['recorded_by'] != identity or meta['provenance']['method'] != 'Deterministic audience view capture'
        or meta['provenance']['source_refs'] != viewpoint['meta']['provenance']['source_refs']
        or meta['id'] != request['id'] or meta['revision'] != request['revision'] or meta['name'] != request['name']
        or body['baseline'] != exact(baseline['baseline']) or body['viewpoint'] != exact(viewpoint)):
        raise InvalidModel('View capture identity, request or source binding differs')
    if context['mode'] == 'local' and context['issuer'] is not None or context['mode'] == 'oidc' and context['issuer'] is None:
        raise InvalidModel('View authentication context differs')
    index = store._get_record(conn, request_id(identity, entry['scope'], request['idempotency_key']))
    if index is None or index['kind'] != 'view_capture_key' or index['scope'] != entry['scope'] or index['actor'] != entry['actor']:
        raise InvalidModel('View capture idempotency index is missing')
    check_schema(index['payload'], KEY_PAYLOAD)
    if index['payload']['capture'] != reference(entry): raise InvalidModel('View capture idempotency index differs')
    contents = {};descriptors = {}
    for field in ('output', 'source_mapping'):
        manifest = store._get_record(conn, payload[field]['id'])
        if manifest is None or manifest['kind'] != 'artifact_manifest' or reference(manifest) != payload[field]:
            raise InvalidModel('View artifact manifest differs')
        check_schema(manifest['payload'], artifacts.PAYLOAD)
        if (manifest['scope'] != entry['scope'] or manifest['actor'] != entry['actor']
            or manifest['payload']['identity'] != identity or manifest['payload']['policy_digest'] != payload['policy_digest']):
            raise InvalidModel('View artifact provenance differs')
        descriptor = artifacts._result(manifest)
        if descriptor['artifact_reference'] != body[field]: raise InvalidModel('View artifact reference differs')
        content = artifacts._load_blob(conn, descriptor['content_digest'].split(':')[1])
        if len(content) != descriptor['size']: raise InvalidModel('View artifact size differs')
        guard = artifacts._context_guard(store, conn, manifest)
        expected = {'format': 'air.artifact-context/0.20', 'artifact': payload[field], 'baseline': request['baseline'], 'view': payload['view']}
        if guard is None or guard['payload'] != expected: raise InvalidModel('View artifact lacks its exact source access context')
        contents[field] = content;descriptors[field] = descriptor
    if len(contents['output']) > 4 * 1024 * 1024: raise InvalidModel('Captured HTML exceeds 4 MiB')
    mapping = parse(contents['source_mapping']);check_schema(mapping, MAP)
    if mapping['baseline'] != request['baseline'] or mapping['viewpoint'] != request['viewpoint'] or mapping['content_digest'] != descriptors['output']['content_digest']:
        raise InvalidModel('View mapping source or output differs')
    selected_types = set(viewpoint['body']['selection']['types']);selected_refs = {key(r) for r in viewpoint['body']['selection']['objects']}
    selected = [o for k, o in objects.items() if k in selected_refs or o['meta']['type'] in selected_types]
    expected = sorted([{**exact(o), 'digest': digest(o)} for o in selected], key=key)
    if sorted([m['object'] for m in mapping['source_mapping']], key=key) != expected or mapping['objects_selected'] != len(selected) or mapping['objects_excluded'] != len(objects) - len(selected):
        raise InvalidModel('View mapping selection differs')
    expected_context = [request['viewpoint'], request['viewpoint']] + [{**r, 'digest': digest(objects[key(r)])} for field in ('audience', 'concerns') for r in viewpoint['body'][field]]
    if sorted([m['object'] for m in mapping['context_mapping']], key=key) != sorted(expected_context, key=key):
        raise InvalidModel('View context mapping differs')
    parser = _Anchors()
    try: parser.feed(contents['output'].decode('utf-8'));parser.close()
    except (UnicodeError, ValueError) as exc: raise InvalidModel('Captured HTML cannot be verified') from exc
    if not parser.csp or any(m['selector'][1:] not in parser.ids for m in mapping['source_mapping'] + mapping['context_mapping']):
        raise InvalidModel('Captured view mappings or content policy are missing')
    return {'view': {'object': view, 'digest': digest(view)}, 'capture': reference(entry), **descriptors,
        'historical_capture': True, 'regenerated': False, 'authorization_granted': False}


def read(store, principal, policy, request):
    check_schema(request, LOOKUP)
    row = ScopedStore(store, principal, policy).get(request['view']['id'], request['view']['revision'])
    if row is None or row['object']['meta']['type'] != 'air.View': raise Forbidden('Captured View is unavailable')
    if row['digest'] != request['view']['digest']: raise Conflict('Requested View digest differs')
    with store.engine.connect() as conn:
        return _verified(store, conn, store._get_record(conn, capture_id(request['view'])))


def capture(store, principal, policy, settings, request):
    check_schema(request, REQUEST)
    # Read the exact context even on replay; historical artifacts grant no permanent access.
    guarded = ScopedStore(store, principal, policy)
    source = guarded.export_baseline(request['baseline'])
    if source['digest'] != request['baseline']['digest']: raise Conflict('Source baseline digest differs')
    viewpoint = next((o for o in source['objects'] if key(exact(o)) == key(request['viewpoint'])), None)
    if viewpoint is None or viewpoint['meta']['type'] != 'air.Viewpoint' or digest(viewpoint) != request['viewpoint']['digest']:
        raise InvalidModel('Viewpoint is absent from the exact source baseline')
    namespace = viewpoint['meta']['namespace'];policy.require(principal, 'write', namespace)
    context = identity_context(principal, settings);identity = identity_uri(context)
    identifier = capture_id(request);index_id = request_id(identity, namespace, request['idempotency_key'])
    def existing(conn):
        index = store._get_record(conn, index_id)
        if index is None:
            if store._get_record(conn, identifier): raise Conflict('View identity/revision is already captured')
            return None
        check_schema(index['payload'], KEY_PAYLOAD)
        entry = store._get_record(conn, index['payload']['capture']['id'])
        if entry is None or entry['payload']['request'] != request or entry['payload']['identity'] != identity:
            raise Conflict('View idempotency key was reused for a different capture')
        return _verified(store, conn, entry)
    # Check historical receipt before using the current generator.
    with store.engine.connect() as conn: prior = existing(conn)
    rendered = None if prior else compile_view(store, principal, policy, {k: request[k] for k in ('baseline', 'viewpoint')})
    if rendered:
        mapping = {'format': 'air.view-mapping/0.20', **{k: rendered[k] for k in MAP['properties'] if k != 'format'}}
        check_schema(mapping, MAP)
        html = rendered['content'].encode('utf-8');map_bytes = json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        if len(map_bytes) > 1024 * 1024: raise InvalidModel('View mapping exceeds 1 MiB')
        suffix = hashlib.sha256(identifier.encode()).hexdigest()
        prepared = {field: artifacts._prepare(principal, policy, settings, {'namespace': namespace, 'media_type': media,
            'idempotency_key': prefix + suffix}, content) for field, media, prefix, content in
            [('output', 'text/html', 'view-html-', html), ('source_mapping', 'application/json', 'view-map-', map_bytes)]}
    with store.write() as conn:
        lock_registry(conn);check_identity(store, conn, principal, settings)
        current = AccessPolicy.load(settings.home)
        if current.digest != policy.digest: raise Forbidden('Access policy changed during View capture')
        current.require(principal, 'write', namespace)
        prior = existing(conn)
        if prior: return {**prior, 'created': False}
        deposited = {field: artifacts._put_locked(store, conn, principal, policy, settings, prepared[field], content, context_required=True)
            for field, content in [('output', html), ('source_mapping', map_bytes)]}
        at = now()
        obj = {'meta': {'id': request['id'], 'revision': request['revision'], 'type': 'air.View', 'name': request['name'],
            'description': 'Captured deterministic projection of an exact source baseline.', 'namespace': namespace, 'owner': identity,
            'classification': {'level': 'INTERNAL'}, 'lifecycle': 'DRAFT', 'recorded_at': at, 'validity': {'start': at, 'end': None},
            'provenance': {'recorded_by': identity, 'method': 'Deterministic audience view capture', 'source_refs': deepcopy(viewpoint['meta']['provenance']['source_refs'])}},
            'body': {'baseline': exact(source['baseline']), 'viewpoint': exact(viewpoint), 'generator': deepcopy(TOOLCHAIN),
                'output': deposited['output']['artifact_reference'], 'source_mapping': deposited['source_mapping']['artifact_reference']}}
        if not validate(obj)['valid']: raise InvalidModel('Generated View is invalid')
        stored = store._put(conn, obj, principal['subject']);pin = {**exact(obj), 'digest': stored['digest']}
        for field in ('output', 'source_mapping'):
            artifact = deposited[field]['artifact']
            store._record_once(conn, artifacts.context_guard_id(artifact['id']), 'artifact_context', namespace, principal['subject'],
                {'format': 'air.artifact-context/0.20', 'artifact': artifact, 'baseline': request['baseline'], 'view': pin})
        entry = store._record_once(conn, identifier, 'view_capture', namespace, principal['subject'],
            {'format': FORMAT, 'request': request, 'view': pin, 'output': deposited['output']['artifact'],
                'source_mapping': deposited['source_mapping']['artifact'], 'identity_context': context, 'identity': identity, 'policy_digest': policy.digest})['record']
        store._record_once(conn, index_id, 'view_capture_key', namespace, principal['subject'], {'format': 'air.view-capture-key/0.20', 'capture': reference(entry)})
        return {**_verified(store, conn, entry), 'created': True}


def verify_views(store, conn):
    seen = set();indexes = set()
    for row in conn.execute(select(service_records).where(service_records.c.kind == 'view_capture')).mappings():
        entry = store._get_record(conn, row['id']);result = _verified(store, conn, entry);pin = exact(result['view']['object'])
        if key(pin) in seen: raise InvalidModel('View has multiple capture receipts')
        seen.add(key(pin));p = entry['payload']
        indexes.add(request_id(p['identity'], entry['scope'], p['request']['idempotency_key']))
    views = set(conn.execute(select(revisions.c.id, revisions.c.revision).join(identities, identities.c.id == revisions.c.id).where(identities.c.type == 'air.View')).all())
    existing_indexes = set(conn.execute(select(service_records.c.id).where(service_records.c.kind == 'view_capture_key')).scalars())
    if views != seen or existing_indexes != indexes: raise InvalidModel('View capture or idempotency index is orphaned')
