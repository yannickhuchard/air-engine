"""Bounded, immutable static PWA generation. No registry or business execution."""
from importlib import resources
import hashlib
import json
from air.expr import artifact_digest
from air.atelier import render_json
from air.editorial import prose

ENGINE = 'air.architecture-pwa/1'


def add_identity(add, title, brand=None):
    profile = brand['profile'] if brand else None
    # Text SVG keeps the delivery protocol and Python-only installation intact.
    for size in (192, 512):
        icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#153f4a"/><path d="M136 354L256 148L376 354M196 252H316" fill="none" stroke="#fff" stroke-width="28" stroke-linejoin="round"/><path d="M136 354H376" stroke="#6ed5c2" stroke-width="20"/><g fill="#6ed5c2"><circle cx="256" cy="148" r="22"/><circle cx="136" cy="354" r="22"/><circle cx="376" cy="354" r="22"/></g></svg>\n'
        if profile:
            icon = profile.get('logo_svg', icon.replace('#153f4a', profile['colors']['header']).replace('#6ed5c2', profile['colors']['accent']))
        add(f'assets/icon-{size}.svg', 'image/svg+xml', icon)
    add('manifest.webmanifest', 'application/manifest+json', render_json({
        'id': './', 'name': prose(title) + ' - ' + (profile['name'] if profile else 'AIR'), 'short_name': (profile['name'][:24] if profile else 'AIR'), 'lang': 'fr',
        'description': 'Dossiers de solution, diagrammes, décisions et sources d’architecture.',
        'start_url': 'index.html', 'scope': './', 'display': 'standalone',
        'background_color': profile['colors']['background'] if profile else '#f4f7f8', 'theme_color': profile['colors']['header'] if profile else '#153f4a',
        'icons': [{'src': f'assets/icon-{size}.svg', 'type': 'image/svg+xml',
                   'sizes': f'{size}x{size}', 'purpose': 'any'} for size in (192, 512)]}))


def compile_worker(files, directory, add):
    entries = [{'path': f['path'][len(directory) + 1:], 'digest': f['content_digest'],
                'media_type': f['media_type']} for f in files]
    template = resources.files('air').joinpath('assets/architecture-worker.js').read_text(encoding='utf-8')
    template_digest = 'sha256:' + hashlib.sha256(template.encode('utf-8')).hexdigest()
    # A worker-only change must not install into/delete an active cache with
    # the same resource version. Include the worker's source in its generation.
    version = artifact_digest({'engine': ENGINE, 'resources': entries, 'worker_template_digest': template_digest})
    add('sw.js', 'text/javascript', template.replace('__AIR_RESOURCE_LIST__', json.dumps(entries, ensure_ascii=True))
        .replace('__AIR_VERSION__', json.dumps(version)))
    return {'engine': ENGINE, 'manifest': 'manifest.webmanifest', 'worker': 'sw.js',
            'worker_digest': files[-1]['content_digest'],
            'worker_template_digest': template_digest,
            'version': version, 'resources': entries, 'resource_count': len(entries), 'cache_policy': 'EXPLICIT_OPT_IN_VERIFIED_SNAPSHOT',
            'scope': './', 'external_exports_cached': False, 'requires': 'HTTPS_OR_LOOPBACK',
            'query_alias': {'page': 'cooperate.html', 'allowed_keys': ['topic', 'audience'], 'other_queries_cached': False},
            'os_installation_verified': False}
