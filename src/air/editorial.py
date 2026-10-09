"""Presentation rules, without rewriting source models, identifiers or code."""
from html import unescape
from html.parser import HTMLParser
import re

RULE = ('Ne pas utiliser le tiret cadratin U+2014 dans les textes produits ou présentés. '
        'Employer une ponctuation simple. Conserver les sources originales, les identifiants, '
        'le code et les empreintes ; normaliser leur prose uniquement pour la présentation.')


def prose(value):
    return str(value).replace('\u2014', '-')


def markdown(value):
    """Normalize narrative text; literal fenced and inline code stays exact."""
    out, fence = [], None
    for line in value.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None: fence = marker[1][0]
            elif marker[1][0] == fence: fence = None
            out.append(line)
        elif fence: out.append(line)
        else:
            parts = re.split(r'(`+[^`]*`+)', line)
            out.append(''.join(part if i % 2 else prose(part) for i, part in enumerate(parts)))
    return ''.join(out)


class _Presentation(HTMLParser):
    """Patch text offsets only: markup, attributes and embedded JSON remain intact."""
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0] + [m.end() for m in re.finditer('\n', source)]
        self.protected = []
        self.edits = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'pre', 'code', 'textarea'):
            self.protected.append(tag)

    def handle_endtag(self, tag):
        if tag in self.protected:
            self.protected = self.protected[:self.protected.index(tag)]

    def replace(self, original, replacement):
        if self.protected or original == replacement: return
        line, column = self.getpos()
        offset = self.lines[line - 1] + column
        self.edits.append((offset, offset + len(original), replacement))

    def handle_data(self, data):
        self.replace(data, prose(data))

    def handle_entityref(self, name):
        raw = '&' + name + ';'
        if unescape(raw) == '\u2014': self.replace(raw, '-')

    def handle_charref(self, name):
        raw = '&#' + name + ';'
        if unescape(raw) == '\u2014': self.replace(raw, '-')


def html(value):
    parser = _Presentation(value)
    parser.feed(value)
    parser.close()
    for start, end, replacement in reversed(parser.edits):
        value = value[:start] + replacement + value[end:]
    return value
