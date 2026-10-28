"""Build the AIR skills plugin without copying a checkout, runtime or credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
# Explicit inventory: untracked notes, credentials and future files are never swept in.
TEXT_FILES = (
    '.codex-plugin/plugin.json', '.claude-plugin/plugin.json', 'plugin.json', 'README.md', 'LICENSE', 'NOTICE',
    'skills/air-local-setup/SKILL.md',
    'skills/air-local-setup/references/connection.md',
    'skills/air-local-design/SKILL.md',
    'skills/air-local-design/references/portable-session.md',
    'skills/air-local-design/assets/session.template.json',
    'skills/README.md',
)
BINARY_FILES = ('assets/logo.png',)
FILES = TEXT_FILES + BINARY_FILES
CLI_TEXT_FILES = tuple(name for name in TEXT_FILES if name != '.claude-plugin/plugin.json') + (
    'skills/air-local-design/scripts/air_cli.py',
    'skills/air-local-design/references/engine-workflows.md',
)


def build(source: Path, output: Path, variant: str = 'project', package_name: str | None = None) -> dict:
    source = source.resolve()
    if variant not in ('project', 'cli'):
        raise ValueError('Unknown plugin variant')
    text_files = CLI_TEXT_FILES if variant == 'cli' else TEXT_FILES
    files = text_files + BINARY_FILES
    payloads = {}
    for name in files:
        path = source / name
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError('Plugin source must not contain redirected files')
        # Only text is normalized: PNG bytes must survive packaging unchanged.
        payloads[name] = (path.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')
                          if name in text_files else path.read_bytes())
        if name in BINARY_FILES and (not payloads[name].startswith(b'\x89PNG\r\n\x1a\n')
                                    or len(payloads[name]) > 5 * 1024 * 1024):
            raise ValueError('Plugin branding requires a PNG up to 5 MiB')
    portable = json.loads(payloads['plugin.json'])
    compat = json.loads(payloads['.codex-plugin/plugin.json'])
    manifests = [portable, compat]
    if variant == 'project':
        manifests.append(json.loads(payloads['.claude-plugin/plugin.json']))
    for key in ('name', 'version', 'description', 'author', 'homepage', 'repository', 'keywords', 'license'):
        if any(portable[key] != manifest[key] for manifest in manifests):
            raise ValueError('Plugin manifests disagree: ' + key)
    if portable['name'] != 'air-local' or not re.fullmatch(r'\d+\.\d+\.\d+', portable['version']):
        raise ValueError('Unexpected plugin identity or version')
    if portable['author']['name'] != 'Yannick Huchard' or compat['interface']['developerName'] != 'Yannick Huchard':
        raise ValueError('Official developer metadata is inconsistent')
    if portable['license'] != 'Apache-2.0' or b'END OF TERMS AND CONDITIONS' not in payloads['LICENSE']:
        raise ValueError('Plugin license assignment or license text is missing')
    for field in ('logo', 'composerIcon'):
        if compat['interface'].get(field) != './assets/logo.png':
            raise ValueError('Plugin branding must reference its packaged logo')
    # This distribution is deliberately project-bound, not a global MCP connection.
    if any(k in manifest for manifest in manifests for k in ('mcpServers', 'apps')):
        raise ValueError('AIR Local must use the project connection')
    if variant == 'cli':
        overlay = portable.get('extensions', {}).get('com.openai', {})
        if overlay.get('requires_local_executor') is not True or compat.get('requires_local_executor') is not True:
            raise ValueError('CLI variant requires boolean requires_local_executor=true in both formats')
        if any(k in overlay for k in ('mcpServers', 'apps')) or any(
            p.name in ('mcp.json', '.mcp.json', '.app.json') for p in source.rglob('*')
        ):
            raise ValueError('CLI variant cannot contain MCP configuration')
        if overlay.get('interface') != compat['interface']:
            raise ValueError('CLI listing metadata must agree across package formats')
        for field, limit in (('displayName', 30), ('shortDescription', 30), ('longDescription', 4000)):
            value = compat['interface'].get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError('Public listing field invalid: ' + field)
    if package_name is not None:
        if variant != 'cli' or not re.fullmatch(r'app-[a-zA-Z0-9_-]{1,60}', package_name):
            raise ValueError('Unexpected portal package identity')
        for name in ('plugin.json', '.codex-plugin/plugin.json'):
            manifest = json.loads(payloads[name])
            manifest['name'] = package_name
            payloads[name] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output = output.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError('Write artifacts outside the plugin source')
    output.mkdir(parents=True, exist_ok=True)
    suffix = ('-openai' if package_name else '-cli') if variant == 'cli' else ''
    archive = output / f"air-local-{portable['version']}{suffix}.zip"
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for name, content in sorted(payloads.items()):
            info = zipfile.ZipInfo('air-local/' + name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    report = {'schema': 'air.plugin-package/1', 'name': package_name or portable['name'],
              'version': portable['version'], 'developer': portable['author']['name'], 'license': portable['license'],
              'archive': archive.name, 'sha256': digest,
              'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())}}
    (output / 'plugin-package.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


def build_marketplace(report, output):
    """Wrap the exact built CLI ZIP in a reproducible local marketplace."""
    archive = output / report['archive']
    if archive.name != report['archive'] or hashlib.sha256(archive.read_bytes()).hexdigest() != report['sha256']:
        raise ValueError('CLI archive does not match its build receipt')
    catalogue = {'name': 'air-cli-direct', 'interface': {'displayName': 'AIR CLI - Distribution directe'},
        'plugins': [{'name': 'air-local', 'source': {'source': 'local', 'path': './air-local'},
                     'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]}
    files = {'AIR-plugins/.agents/plugins/marketplace.json': (json.dumps(catalogue, ensure_ascii=False, indent=2) + '\n').encode(),
        'AIR-plugins/INSTALLATION.txt': ('AIR Skills-only CLI ' + report['version'] + '\n'
            'Ouvrir AIR-plugins comme projet local dans ChatGPT desktop, puis Plugins et ajouter cette marketplace locale.\n'
            'Installer séparément le moteur AIR autorisé. Un chat local avec exécuteur est requis.\n'
            'Les tests locaux du paquet ne qualifient ni le client natif ni la publication dans un annuaire.\n').encode('utf-8')}
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            if not name.startswith('air-local/') or '..' in name.split('/') or '\\' in name:
                raise ValueError('Unsafe plugin archive member')
            files['AIR-plugins/' + name] = source.read(name)
    destination = output / ('air-local-' + report['version'] + '-marketplace.zip')
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    return {'archive': destination.name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'source_plugin_sha256': report['sha256'], 'native_installation_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist' / 'plugin')
    parser.add_argument('--variant', choices=('project', 'cli'), default='project')
    parser.add_argument('--portal-name', help='Existing portal-assigned package name; CLI copy only')
    parser.add_argument('--direct-marketplace', action='store_true', help='Also wrap the canonical CLI ZIP for local installation')
    args = parser.parse_args()
    source = ROOT / 'plugins' / ('air-local-cli' if args.variant == 'cli' else 'air-local')
    if args.direct_marketplace and (args.variant != 'cli' or args.portal_name):
        parser.error('Direct marketplace requires the canonical CLI variant')
    report = build(source, args.output_dir, args.variant, args.portal_name)
    if args.direct_marketplace:
        report['direct_marketplace'] = build_marketplace(report, args.output_dir)
        (args.output_dir / 'direct-marketplace.json').write_text(json.dumps(report['direct_marketplace'], indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
