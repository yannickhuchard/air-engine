"""Portable Agent Skills shipped with AIR, exported for every agent that reads the open SKILL.md format.

`.agents/skills/` is read by Codex, Cursor, Antigravity, OpenCode, Gemini CLI and others; `.claude/skills/` by Claude
Code; ChatGPT and Claude.ai take one zip per skill. The skills are data: exporting them writes files, nothing else.
"""
from pathlib import Path
import io
import re
import zipfile
import yaml

ROOT = Path(__file__).parent / 'skills'
LAYOUTS = {'agents': '.agents/skills', 'claude': '.claude/skills', 'chatgpt': ''}
NAME = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
STAMP = (2026, 1, 1, 0, 0, 0)


def check(name, text):
    """Rules of the Agent Skills standard that an export must keep."""
    if not text.startswith('---\n'): raise ValueError(name + ': SKILL.md starts with a YAML frontmatter')
    head = yaml.safe_load(text.split('---\n', 2)[1])
    if head.get('name') != name or not NAME.match(name) or len(name) > 64:
        raise ValueError(name + ': the frontmatter name matches the directory, in lowercase words joined by hyphens, at most 64 characters')
    if not 1 <= len(head.get('description') or '') <= 1024: raise ValueError(name + ': the description holds 1 to 1024 characters')
    if text.count('\n') > 500: raise ValueError(name + ': SKILL.md stays under 500 lines; move details to references/')
    return head


def bundled():
    """Every shipped skill: name, frontmatter and its files as (relative path, text), in a stable order."""
    skills = []
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / 'SKILL.md').is_file()):
        files = [(f.relative_to(folder).as_posix(), f.read_text(encoding='utf-8')) for f in sorted(folder.rglob('*.md'))]
        head = check(folder.name, dict(files)['SKILL.md'])
        skills.append({'name': folder.name, 'description': head['description'], 'files': files})
    return skills


def files_for(layout, names=None):
    """Repository files for a layout: [(path, text)]."""
    base = LAYOUTS[layout]
    return [(base + '/' + s['name'] + '/' + rel, text) for s in bundled() if not names or s['name'] in names for rel, text in s['files']]


def archive(skill):
    """A deterministic zip with the skill folder at its root, as ChatGPT and Claude.ai expect it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, text in skill['files']:
            info = zipfile.ZipInfo(skill['name'] + '/' + rel, STAMP);info.external_attr = 0o644 << 16;info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode('utf-8'))
    return buffer.getvalue()


def export(target, layout, apply=False, names=None):
    """Plan, then write if asked: CREATE, UPDATE or UNCHANGED for each file. Files outside the skills are never touched."""
    target = Path(target)
    if layout == 'chatgpt':
        outputs = [(s['name'] + '.zip', archive(s)) for s in bundled() if not names or s['name'] in names]
    else:
        outputs = [(path, text.encode('utf-8')) for path, text in files_for(layout, names)]
    plan = []
    for path, content in outputs:
        file = target / path
        action = 'CREATE' if not file.exists() else 'UNCHANGED' if file.read_bytes() == content else 'UPDATE'
        if apply and action != 'UNCHANGED':
            file.parent.mkdir(parents=True, exist_ok=True);file.write_bytes(content)
        plan.append({'path': path, 'action': action, 'bytes': len(content)})
    return {'engine': 'air.skills/0.33', 'layout': layout, 'target': str(target.resolve()), 'applied': bool(apply),
            'skills': [s['name'] for s in bundled() if not names or s['name'] in names], 'plan': plan}
