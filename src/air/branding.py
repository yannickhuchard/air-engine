"""Portable presentation identities. Imported prose is data, never instructions."""
import re
import math
import xml.etree.ElementTree as ET
from copy import deepcopy
from air.core import record
from air.foundation import InvalidModel, check_schema
from air.expr import artifact_digest
from air.atelier import product, render_json, collate, no_secret
from air.parsing import parse
from air.projections import SNAPSHOT
from air.artifacts import LOOKUP, download

ENGINE = 'air.branding/1'
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 120}
COLOR = {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$'}
ROLES = ('header', 'header_text', 'background', 'surface', 'text', 'muted', 'link', 'accent')
INPUT = record({
    'name': TEXT, 'tagline': TEXT,
    'colors': record({role: COLOR for role in ROLES}, []),
    'fonts': record({'body': TEXT, 'display': TEXT}, []),
    'logo_svg': {'type': 'string', 'minLength': 1, 'maxLength': 16384},
    'design_md': {'type': 'string', 'minLength': 1, 'maxLength': 65536},
    'design_mapping': record({role: TEXT for role in (*ROLES, 'body', 'display')}, []),
}, [])
SOURCE = {'oneOf': [INPUT, LOOKUP]}
SELECTION = record({'default': SOURCE, 'dossiers': {'type': 'array', 'maxItems': 16,
    'items': record({'baseline': SNAPSHOT, 'profile': SOURCE}, ['baseline', 'profile'])}}, [])
REQUEST = record({'profile': SOURCE, 'directory': {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{0,62}$'},
                  'content': {'enum': ['FULL', 'DIGESTS']}}, ['profile'])
DEFAULT = {'name': 'AIR', 'tagline': 'Projet d’architecture',
    'colors': dict(zip(ROLES, ('#153f4a', '#ffffff', '#f4f7f8', '#ffffff', '#17333c', '#536b74', '#17687c', '#6ed5c2'))),
    'fonts': {'body': 'Segoe UI', 'display': 'Bahnschrift'}}
HEADINGS = {'Brand & Style': 'Overview', 'Layout & Spacing': 'Layout', 'Elevation': 'Elevation & Depth'}


def contrast(a, b):
    def light(color):
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * w for c, w in zip(channels, (.2126, .7152, .0722)))
    x, y = sorted((light(a), light(b)))
    return (y + .05) / (x + .05)


def logo(value):
    """Small inert SVG subset: shapes and text, no references, CSS or active content."""
    if '<!' in value or '<?' in value: raise InvalidModel('Logo SVG declarations/entities are forbidden')
    try: root = ET.fromstring(value)
    except ET.ParseError as exc: raise InvalidModel('Logo SVG is malformed') from exc
    tags = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'title', 'desc'}
    attrs = {'viewBox', 'width', 'height', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 'd', 'points', 'x1', 'x2', 'y1', 'y2',
             'fill', 'stroke', 'stroke-width', 'stroke-linejoin', 'stroke-linecap', 'fill-rule', 'opacity', 'transform',
             'font-family', 'font-size', 'font-weight', 'text-anchor'}
    if root.tag != '{http://www.w3.org/2000/svg}svg': raise InvalidModel('Logo needs an SVG namespace')
    for node in root.iter():
        if node.tag not in {'{http://www.w3.org/2000/svg}' + t for t in tags}:
            raise InvalidModel('Unsupported or active logo SVG element')
        for key, val in node.attrib.items():
            if key not in attrs or not re.fullmatch(r'[A-Za-z0-9#., ()%+\-]*', val):
                raise InvalidModel('Unsupported or active logo SVG attribute')
            if key in ('fill', 'stroke') and not re.fullmatch(r'#[0-9A-Fa-f]{3,8}|none|currentColor|[a-zA-Z]+', val):
                raise InvalidModel('SVG paint must be a literal color')
    if not root.get('viewBox'): raise InvalidModel('Logo needs a viewBox for responsive sizing')
    try: box = [float(v) for v in re.split(r'[ ,]+', root.get('viewBox').strip())]
    except ValueError as exc: raise InvalidModel('SVG viewBox must contain four finite numbers') from exc
    if len(box) != 4 or not all(math.isfinite(v) for v in box) or box[2] <= 0 or box[3] <= 0:
        raise InvalidModel('SVG viewBox must have a positive finite width and height')
    return value.rstrip() + '\n'


def design(text):
    if len(text.encode('utf-8')) > 65536: raise InvalidModel('DESIGN.md exceeds 64 KiB')
    lines = text.splitlines(); front = {}; start = 0
    if lines and lines[0] == '---':
        try: end = lines.index('---', 1)
        except ValueError as exc: raise InvalidModel('DESIGN.md frontmatter is not closed') from exc
        try: front = parse('\n'.join(lines[1:end]).encode('utf-8'), 'yaml')
        except ValueError as exc: raise InvalidModel('Invalid DESIGN.md frontmatter: ' + str(exc)) from exc
        if not isinstance(front, dict): raise InvalidModel('DESIGN.md frontmatter must be a mapping')
        start = end + 1
    seen = set(); fenced = False
    for line in lines[start:]:
        if line.startswith('```') or line.startswith('~~~'): fenced = not fenced
        if line.startswith('## ') and not fenced:
            heading = line[3:].strip(); heading = HEADINGS.get(heading, heading)
            if heading in seen: raise InvalidModel('Duplicate DESIGN.md section: ' + heading)
            seen.add(heading)
    for key in ('colors', 'typography'):
        if key in front and not isinstance(front[key], dict): raise InvalidModel('DESIGN.md ' + key + ' must be a mapping')
    return front


def resolve(front, path):
    trail = set()
    for _ in range(32):
        path = path.strip('{}')
        if path in trail: raise InvalidModel('DESIGN.md token reference cycle')
        trail.add(path); value = front
        for part in path.split('.'):
            if not isinstance(value, dict) or part not in value: raise InvalidModel('Unknown DESIGN.md token: ' + path)
            value = value[part]
        if isinstance(value, str) and re.fullmatch(r'\{[^{}]+\}', value): path = value; continue
        return value
    raise InvalidModel('DESIGN.md reference chain exceeds 32')


def normalize(source):
    check_schema(source, INPUT)
    brand = deepcopy(DEFAULT); warnings = []; applied = {}; front = {}
    if 'design_mapping' in source and 'design_md' not in source: raise InvalidModel('Token mapping requires DESIGN.md')
    if 'design_md' in source:
        front = design(source['design_md'])
        if isinstance(front.get('name'), str): brand['name'] = front['name']
        if front.get('version') != 'alpha': warnings.append('DESIGN_VERSION_NOT_ALPHA_OR_ABSENT')
        colors = front.get('colors', {}); typography = front.get('typography', {})
        mapping = {}
        for role in ROLES:
            if role in colors: mapping[role] = 'colors.' + role
        if 'primary' in colors:
            mapping.setdefault('header', 'colors.primary'); mapping.setdefault('link', 'colors.primary')
        for role in ('body', 'display'):
            if role in typography: mapping[role] = 'typography.' + role
        mapping.update(source.get('design_mapping', {}))
        for role, path in mapping.items():
            value = resolve(front, path)
            if role in ROLES:
                if isinstance(value, str) and re.fullmatch('#[0-9A-Fa-f]{3}', value): value = '#' + ''.join(c*2 for c in value[1:])
                check_schema(value, COLOR); brand['colors'][role] = value.lower()
            else:
                if isinstance(value, dict): value = value.get('fontFamily')
                check_schema(value, TEXT); brand['fonts'][role] = value
            applied[role] = path
        if 'header' in mapping and 'header_text' not in mapping:
            brand['colors']['header_text'] = max(('#ffffff', '#000000'), key=lambda c: contrast(c, brand['colors']['header']))
        warnings.append('DESIGN_RETAINED_UNMAPPED_TOKENS_AND_PROSE_NOT_APPLIED')
    from air.editorial import prose
    for key in ('name', 'tagline'):
        brand[key] = prose(source.get(key, brand[key])); check_schema(brand[key], TEXT)
    if brand['tagline'].casefold() in ('atlas d’architecture', "atlas d'architecture"):
        brand['tagline'] = 'Projet d’architecture'
    for key in ('colors', 'fonts'): brand[key].update(source.get(key, {}))
    brand['colors'] = {key: value.lower() for key, value in brand['colors'].items()}
    for value in brand['fonts'].values():
        if not re.fullmatch(r'[\w][\w -]{0,119}', value, re.UNICODE): raise InvalidModel('Font must be one family name; remote URLs and CSS are forbidden')
    pairs = [('header_text', 'header'), ('text', 'background'), ('text', 'surface'), ('muted', 'surface'), ('link', 'surface'), ('text', 'accent')]
    for fg, bg in pairs:
        if contrast(brand['colors'][fg], brand['colors'][bg]) < 4.5:
            raise InvalidModel('Branding contrast below 4.5:1: ' + fg + '/' + bg)
    # The ontology diagrams and source cards retain their light reading surfaces.
    for role in ('text', 'muted', 'link'):
        if contrast(brand['colors'][role], '#ffffff') < 4.5:
            raise InvalidModel('Branding text must remain readable on AIR light diagram/source surfaces: ' + role)
    if 'logo_svg' in source: brand['logo_svg'] = logo(source['logo_svg'])
    else:
        brand['logo_svg'] = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="18" fill="' + brand['colors']['header'] + '"/><path d="M20 78L50 20L80 78M33 54H67" fill="none" stroke="' + brand['colors']['header_text'] + '" stroke-width="7"/></svg>\n'
    no_secret([{'path': 'branding/source.json', 'content': render_json(source)}])
    return {'engine': ENGINE, 'profile': brand, 'profile_digest': artifact_digest(brand),
            'source': deepcopy(source), 'source_digest': artifact_digest(source), 'warnings': warnings,
            'design_applied_tokens': applied, 'logo_delivery': 'CUSTOM_SVG' if 'logo_svg' in source else 'AIR_FALLBACK', 'fonts_delivery': 'SYSTEM_FAMILY_WITH_LOCAL_FALLBACK',
            'registry_written': False, 'architecture_changed': False}


def css(result):
    p = result['profile']; c = p['colors']; f = p['fonts']
    return ':root{' + ';'.join('--' + k + ':' + c[v] for k, v in {'header': 'header', 'header-text': 'header_text', 'ink': 'text', 'muted': 'muted', 'paper': 'surface', 'ground': 'background', 'accent': 'accent', 'link': 'link'}.items()) + '}\n' + \
        'body{background:' + c['background'] + ';font-family:"' + f['body'] + '",system-ui,sans-serif}h1,h2,h3,.reading-route strong{font-family:"' + f['display'] + '",system-ui,sans-serif}a{color:' + c['link'] + '}\n' + \
        '.workspace-header,.workspace-header a,.workspace-header .brand small,.workspace-header .project-name,.story-controls,.story-chapters a[aria-current]{color:' + c['header_text'] + '}\n' + \
        '.brand{min-width:0;max-width:100%;flex-shrink:1}.brand img{object-fit:contain;flex-shrink:0}.brand span{min-width:0;max-width:20rem;overflow-wrap:anywhere;font-family:"' + f['display'] + '",system-ui,sans-serif}.brand small{display:block;font-family:"' + f['body'] + '",system-ui,sans-serif}\n' + \
        'aside,.app-menu>div{background:' + c['surface'] + '}.workspace-nav a:hover{background:' + c['background'] + '}.workspace-nav a[aria-current]{background:' + c['header'] + ';color:' + c['header_text'] + '}\n'


def files(result, prefix='branding/'):
    out = [product(prefix + 'brand.json', 'application/json', render_json(result), 'GENERATED', 131072),
           product(prefix + 'brand.css', 'text/css', css(result), 'GENERATED')]
    if 'logo_svg' in result['profile']: out.append(product(prefix + 'logo.svg', 'image/svg+xml', result['profile']['logo_svg'], 'GENERATED'))
    if 'design_md' in result['source']: out.append(product(prefix + 'DESIGN.md', 'text/markdown', result['source']['design_md'], 'GENERATED', 65536))
    return out


def compile_branding(store, principal, policy, request):
    check_schema(request, REQUEST)
    result = load_profile(store, principal, policy, request['profile']); products = files(result, request.get('directory', 'branding') + '/')
    # Generation ownership receipts make CLI updates protect local edits.
    products.append(product(request.get('directory', 'branding') + '/manifest.json', 'application/json',
        render_json({'engine': ENGINE, 'files': [{'path': f['path'], 'content_digest': f['content_digest']} for f in products]}), 'GENERATED'))
    ordered, total, checksum = collate(products, 262144)
    if request.get('content') == 'DIGESTS': ordered = [{k: v for k, v in f.items() if k != 'content'} for f in ordered]
    return {**result, 'files': ordered, 'total_size': total, 'file_set_digest': checksum}


def load_profile(store, principal, policy, source):
    if 'artifact' not in source: return normalize(source)
    manifest, raw = download(store, principal, policy, source)
    if len(raw) > 98304: raise InvalidModel('Branding artifact exceeds 96 KiB')
    try: document = parse(raw)
    except ValueError as exc: raise InvalidModel('Branding artifact must be strict JSON') from exc
    if not isinstance(document, dict) or set(document) != {'profile'}: raise InvalidModel('Branding artifact must contain exactly profile')
    result = normalize(document['profile'])
    return {**result, 'source_artifact': {**source, 'content_digest': manifest['content_digest']}}


def selection(request, baselines, store=None, principal=None, policy=None):
    value = request.get('branding', {}); check_schema(value, SELECTION)
    default = load_profile(store, principal, policy, value.get('default', {})); dossiers = {}
    valid = {artifact_digest(pin) for pin in baselines}
    for item in value.get('dossiers', []):
        key = artifact_digest(item['baseline'])
        if key not in valid: raise InvalidModel('Branding dossier must pin a requested baseline exactly')
        if key in dossiers: raise InvalidModel('Duplicate branding dossier baseline')
        dossiers[key] = load_profile(store, principal, policy, item['profile'])
    return default, dossiers
