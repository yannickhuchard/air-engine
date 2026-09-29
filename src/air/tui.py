"""The AIR activity spinner: what a long command is going to do, what it is doing now, and how it ended.

It writes only to an interactive stderr, so stdout keeps the machine-readable JSON for scripts and agents. It stays
silent when stderr is not a terminal, under CI, with AIR_NO_SPINNER or --quiet, and for commands that finish before
it would appear. Colours follow NO_COLOR; a terminal without ANSI support gets a single updating line.
"""
import locale
import math
import os
import sys
import threading
import time

DELAY = 0.35          # a command that ends before this never shows the spinner
FRAME = 0.08
NOTE_EVERY = 3.2      # seconds between two explanations of the current step
WAVE = '⠀⡀⣀⣄⣤⣦⣶⣷⣿'  # airflow: a crest of braille dots travelling left to right
WAVE_ASCII = ' .:-=+*#'
TEAL = (23, 29, 30, 36, 37, 43, 37, 36, 30, 29)

# command -> (title fr, title en, server step fr, server step en, explanations fr, explanations en)
SPECS = {
    'deliverables': ('Compiler le dossier de livrables', 'Compile the deliverables pack',
                     'AIR compile 37 documents et le deck de direction', 'AIR compiles 37 documents and the executive deck',
                     ['lecture des baselines épinglées et de leurs emprunts', 'calcul de la porte prêt à construire de chaque baseline',
                      'diagrammes Mermaid : graphe, séquences, états, infrastructure, gantt', 'matrice de conformité, estimation IA, feuilles de route',
                      'deck bilingue : titres d’action calculés depuis le modèle'],
                     ['reading the pinned baselines and what they borrow', 'computing the ready-to-build gate of each baseline',
                      'Mermaid diagrams: graph, sequences, states, infrastructure, gantt', 'compliance matrix, AI estimate, roadmaps',
                      'bilingual deck: action titles computed from the model']),
    'presentation': ('Compiler la présentation de direction', 'Compile the executive presentation',
                     'AIR construit le deck en français et en anglais', 'AIR builds the deck in French and English',
                     ['synthèse et décision demandée', 'porte prêt à construire par projet', 'scénarios, conformité, estimation avec et sans IA',
                      'feuilles de route et chemin critique du programme', 'CAPEX, OPEX, risques et décisions'],
                     ['summary and decision asked', 'ready-to-build gate per project', 'scenarios, compliance, estimate with and without AI',
                      'roadmaps and programme critical path', 'CAPEX, OPEX, risks and decisions']),
    'readiness': ('Évaluer la porte prêt à construire', 'Assess the ready-to-build gate',
                  'AIR juge douze critères sur la révision exacte', 'AIR judges twelve criteria on the exact revision',
                  ['fermeture des références et contrôles MECE et DDD', 'chaîne exigence, fonction, contrat, unité, cas',
                   'cas de conception exécutés et tests planifiés', 'conformité reçue du socle et correspondances', 'revues humaines de cette révision'],
                  ['reference closure and MECE and DDD checks', 'requirement, function, contract, unit, case chain',
                   'design cases run and tests planned', 'compliance received from the kernel and mappings', 'human reviews of this revision']),
    'scenarios-walk': ('Rejouer les scénarios d’acceptation', 'Walk the acceptance scenarios',
                       'AIR parcourt chaque scénario sur sa carte de navigation', 'AIR walks each scenario on its navigation map',
                       ['écran d’entrée, transitions et gardes', 'opérations offertes par l’écran et présentes dans le contrat',
                        'couverture des écrans, transitions et impasses', 'socle de non-régression'],
                       ['entry screen, transitions and guards', 'operations offered by the screen and present in the contract',
                        'coverage of screens, transitions and dead ends', 'foundation regression suite']),
    'scenario-simulate': ('Simuler un scénario de performance', 'Simulate a performance scenario',
                          'AIR tire les exécutions avec une graine fixe', 'AIR draws the runs with a fixed seed',
                          ['durées par étape selon le modèle de performance', 'chemins pris selon les gardes de chaque classe', 'percentiles et verdict face à la cible'],
                          ['step durations from the performance model', 'paths taken by the guards of each class', 'percentiles and verdict against the target']),
    'guide': ('S’orienter dans le dossier', 'Orient in the dossier', 'AIR résume l’état du dossier', 'AIR sums up the dossier',
              ['dernière révision et emprunts en retard', 'porte prêt à construire', 'scénarios, conformité, estimation, feuilles de route', 'prochains appels exacts'],
              ['latest revision and borrowed objects behind', 'ready-to-build gate', 'scenarios, compliance, estimate, roadmaps', 'next exact calls']),
    'drafts-validate': ('Valider les brouillons à blanc', 'Dry-run the drafts', 'AIR valide sans rien écrire', 'AIR validates without writing',
                        ['schémas de chaque type', 'références exactes et dernières révisions', 'fermeture de la baseline candidate', 'contrôles d’architecture introduits'],
                        ['schema of each type', 'exact references and latest revisions', 'closure of the candidate baseline', 'architecture checks introduced']),
    'drafts-rebase': ('Préparer le changement', 'Prepare the change', 'AIR fait avancer les références dépendantes', 'AIR advances the dependent references',
                      ['révisions de référence des objets qui dépendent des brouillons', 'emprunts ajoutés ou réalignés', 'baseline candidate et son verdict'],
                      ['reference revisions of the objects depending on the drafts', 'borrowed objects added or realigned', 'candidate baseline and its verdict']),
    'prepared-deposit': ('Déposer le changement préparé', 'Deposit the prepared change', 'AIR enregistre les révisions préparées', 'AIR records the prepared revisions',
                         ['écriture des révisions dans le registre'], ['writing the revisions into the registry']),
    'prepared-freeze': ('Figer la révision suivante', 'Freeze the next revision', 'AIR fige la baseline et la valide', 'AIR freezes and validates the baseline',
                        ['fermeture des références', 'validation du profil'], ['reference closure', 'profile validation']),
    'ide-setup': ('Configurer l’agent du référentiel', 'Set up the repository agent', 'AIR produit la configuration de l’agent', 'AIR produces the agent configuration',
                  ['serveur MCP et permissions', 'skill du référentiel et parcours guidés', 'skills portables air-architecte et air-presentation'],
                  ['MCP server and permissions', 'repository skill and guided journeys', 'portable skills air-architecte and air-presentation']),
    'workspace-init': ('Créer le référentiel', 'Create the repository', 'AIR produit les domaines et leurs dossiers', 'AIR produces the domains and their dossiers',
                       ['un dossier par domaine', 'conventions et instructions'], ['one dossier per domain', 'conventions and instructions']),
    'portfolio-index': ('Indexer le portefeuille', 'Index the portfolio', 'AIR lit les baselines épinglées de chaque projet', 'AIR reads the pinned baseline of each project',
                        ['état et porte de chaque projet', 'emprunts entre projets'], ['state and gate of each project', 'borrowing between projects']),
    'openapi-compile': ('Compiler la description OpenAPI', 'Compile the OpenAPI description', 'AIR traduit le contrat et sa liaison HTTP', 'AIR translates the contract and its HTTP binding',
                        ['chemins, paramètres, corps et erreurs'], ['paths, parameters, bodies and errors']),
    'bootstrap': ('Initialiser l’instance AIR', 'Initialise the AIR instance', 'Création de la base, des identités et de la politique', 'Creating the database, identities and policy',
                  ['schéma SQL et migrations', 'identifiants protégés', 'politique d’accès'], ['SQL schema and migrations', 'protected credentials', 'access policy']),
    'backup': ('Sauvegarder l’instance', 'Back up the instance', 'Copie cohérente du registre', 'Consistent copy of the registry', ['base et fichiers d’artefacts'], ['database and artefact files']),
    'restore': ('Restaurer l’instance', 'Restore the instance', 'Restauration du registre', 'Restoring the registry', ['base et fichiers d’artefacts'], ['database and artefact files']),
    'registry-export': ('Exporter le registre', 'Export the registry', 'Export des objets et des baselines', 'Exporting objects and baselines', ['objets, révisions, baselines'], ['objects, revisions, baselines']),
    'registry-import': ('Importer le registre', 'Import the registry', 'Import des objets et des baselines', 'Importing objects and baselines', ['objets, révisions, baselines'], ['objects, revisions, baselines']),
}
WORDS = {'fr': {'read': 'Lire la requête', 'write': 'Écrire le résultat', 'files': 'Comparer et écrire les fichiers', 'call': 'AIR traite la requête',
                'done': 'terminé en', 'failed': 'échec après', 'decimal': ','},
         'en': {'read': 'Read the request', 'write': 'Write the result', 'files': 'Compare and write the files', 'call': 'AIR processes the request',
                'done': 'done in', 'failed': 'failed after', 'decimal': '.'}}
WRITES_FILES = ('workspace-init', 'ide-setup', 'portfolio-init', 'portfolio-index', 'deliverables')
WRITES_OUTPUT = ('presentation', 'openapi-compile', 'view', 'workbench', 'audience-view', 'artifact-download')
LOCAL = ('bootstrap', 'backup', 'restore', 'registry-export', 'registry-import')


def language():
    wanted = os.environ.get('AIR_LANG') or os.environ.get('LC_ALL') or os.environ.get('LANG') or (locale.getlocale()[0] or '')
    return 'en' if wanted.lower().startswith('en') else 'fr'


def enabled(quiet=False, stream=None):
    stream = stream or sys.stderr
    if quiet or os.environ.get('AIR_NO_SPINNER') or os.environ.get('CI') or os.environ.get('TERM') == 'dumb': return False
    return bool(getattr(stream, 'isatty', lambda: False)())


def _ansi_ready(stream):
    """True when the terminal understands cursor movement; on Windows, ask the console to."""
    if os.name != 'nt': return True
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-12)
        mode = ctypes.c_uint32()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)): return bool(os.environ.get('WT_SESSION') or os.environ.get('TERM'))
        return bool(kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


class Activity:
    """A checklist of steps with a live spinner on the current one."""

    def __init__(self, title, steps, notes=(), stream=None, lang='fr', show=True):
        self.stream = stream or sys.stderr;self.lang = lang;self.show = show
        self.title = title;self.steps = [{'label': s, 'state': 'todo', 'start': None, 'end': None} for s in steps]
        self.notes = {i: list(n) for i, n in notes} if notes else {}
        self.current = -1;self.began = time.monotonic();self.lines = 0;self.visible = False
        self.lock = threading.Lock();self.stop = threading.Event();self.thread = None
        encoding = (getattr(self.stream, 'encoding', '') or '').lower()
        self.unicode = 'utf' in encoding
        self.color = self.unicode and not os.environ.get('NO_COLOR')
        self.multiline = show and _ansi_ready(self.stream)
        self.color = self.color and self.multiline

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        if self.show and self.thread is None:
            self.thread = threading.Thread(target=self._loop, name='air-spinner', daemon=True);self.thread.start()
        return self

    def enter(self, index):
        """Mark every earlier step done and make `index` the current one."""
        with self.lock:
            now = time.monotonic()
            for i, step in enumerate(self.steps):
                if i < index and step['state'] != 'done':
                    step['state'] = 'done';step['start'] = step['start'] or now;step['end'] = now
            if 0 <= index < len(self.steps) and self.steps[index]['state'] == 'todo':
                self.steps[index].update(state='run', start=now)
            self.current = index

    def finish(self, summary=None):
        self._close(True, summary)

    def fail(self, message=None):
        self._close(False, message)

    # ---------------------------------------------------------------- rendering
    def _loop(self):
        if self.stop.wait(DELAY): return
        tick = 0
        while not self.stop.is_set():
            with self.lock: self._draw(tick)
            tick += 1
            self.stop.wait(FRAME)

    def _paint(self, text, colour):
        return '\x1b[38;5;%dm%s\x1b[0m' % (colour, text) if self.color else text

    def _bold(self, text):
        return '\x1b[1m%s\x1b[0m' % text if self.color else text

    def _dim(self, text):
        return '\x1b[2m%s\x1b[0m' % text if self.color else text

    def _wave(self, tick):
        levels = WAVE if self.unicode else WAVE_ASCII
        out = []
        for j in range(6):
            height = (math.sin(tick * 0.45 - j * 0.9) + 1) / 2
            out.append(self._paint(levels[int(round(height * (len(levels) - 1)))], TEAL[(tick + j) % len(TEAL)]))
        return ''.join(out)

    def _seconds(self, value):
        return ('%.1f s' % value).replace('.', WORDS[self.lang]['decimal'])

    def _draw(self, tick):
        now = time.monotonic();glyph = ('✔', '○', '↳') if self.unicode else ('+', '.', '>')
        head = self._wave(tick) + ' ' + self._bold(self._paint('AIR', 36)) + '  ' + self.title + '  ' + self._dim(self._seconds(now - self.began))
        if not self.multiline:
            step = self.steps[self.current]['label'] if 0 <= self.current < len(self.steps) else ''
            line = '\r' + head + (' · ' + step if step else '')
            self.stream.write(line[:max(40, _width() - 1)] + '\x1b[K' if self.color else line[:max(40, _width() - 1)])
            self.stream.flush();self.visible = True
            return
        rows = [head]
        for i, step in enumerate(self.steps):
            if step['state'] == 'done':
                rows.append('  ' + self._paint(glyph[0], 36) + ' ' + step['label'] + '  ' + self._dim(self._seconds(step['end'] - step['start'])))
            elif step['state'] == 'run':
                spin = self._wave(tick)[:1] if not self.unicode else self._paint('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'[tick % 10], 37)
                rows.append('  ' + spin + ' ' + self._bold(step['label']) + '  ' + self._dim(self._seconds(now - step['start'])))
                notes = self.notes.get(i)
                if notes:
                    rows.append('    ' + self._dim(glyph[2] + ' ' + notes[int((now - step['start']) / NOTE_EVERY) % len(notes)]))
            else:
                rows.append('  ' + self._dim(glyph[1] + ' ' + step['label']))
        out = ('\x1b[%dF' % self.lines if self.lines else '') + ''.join('\x1b[2K' + r + '\n' for r in rows)
        if self.lines > len(rows): out += ''.join('\x1b[2K\n' for _ in range(self.lines - len(rows))) + '\x1b[%dF' % (self.lines - len(rows))
        self.stream.write(out);self.stream.flush()
        self.lines = len(rows);self.visible = True

    def _close(self, ok, message):
        if self.thread is None:
            return
        self.stop.set();self.thread.join(timeout=1);self.thread = None
        with self.lock:
            if not self.visible: return
            if self.multiline:
                self.stream.write(('\x1b[%dF' % self.lines if self.lines else '') + ''.join('\x1b[2K\n' for _ in range(self.lines))
                                  + ('\x1b[%dF' % self.lines if self.lines else ''))
            else:
                self.stream.write('\r' + ' ' * max(40, _width() - 1) + '\r')
            words = WORDS[self.lang];elapsed = self._seconds(time.monotonic() - self.began)
            mark = self._paint('✔' if self.unicode else '+', 36) if ok else self._paint('✖' if self.unicode else 'x', 160)
            text = mark + ' ' + self._bold(self._paint('AIR', 36)) + '  ' + self.title + '  ' + self._dim((words['done'] if ok else words['failed']) + ' ' + elapsed)
            if message: text += '\n   ' + message
            self.stream.write(text + '\n');self.stream.flush()


def _width():
    try: return os.get_terminal_size(2).columns
    except OSError: return 100


def _visible_len(text):
    import re
    return len(re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text))


class Silent:
    """The same interface, doing nothing: pipes, CI, agents and --quiet."""
    def start(self): return self
    def enter(self, index): pass
    def finish(self, summary=None): pass
    def fail(self, message=None): pass


def for_command(command, quiet=False, stream=None):
    """The activity of a CLI command: its steps, the explanation of what AIR does, and whether to show it at all."""
    stream = stream or sys.stderr
    if not enabled(quiet, stream): return Silent()
    lang = language();w = WORDS[lang]
    spec = SPECS.get(command)
    fr = lang == 'fr'
    if spec:
        title = spec[0] if fr else spec[1];server = spec[2] if fr else spec[3];notes = spec[4] if fr else spec[5]
    else:
        title = 'air ' + command;server = w['call'];notes = []
    if command in LOCAL:
        steps, where = [server], 0
    else:
        steps = [w['read'], server] + ([w['files']] if command in WRITES_FILES else [w['write']] if command in WRITES_OUTPUT else [])
        where = 1
    return Activity(title, steps, [(where, notes)] if notes else (), stream, lang).start()


def summary(command, result, lang=None):
    """One line that says what the command produced, from its JSON result."""
    lang = lang or language();fr = lang == 'fr'
    try:
        if command == 'deliverables':
            written = result.get('written')
            return ('%d fichiers écrits dans %s' if fr else '%d files written to %s') % (len(written), result['workspace_directory']) if written else \
                   ('%d fichiers planifiés, rien écrit (--apply pour écrire)' if fr else '%d files planned, nothing written (--apply to write)') % len(result.get('plan', []))
        if command in ('ide-setup', 'workspace-init', 'portfolio-init', 'portfolio-index'):
            return ('%d fichiers, %d écrits' if fr else '%d files, %d written') % (len(result.get('plan', [])), len(result.get('written') or []))
        if command == 'presentation':
            return ('%d diapositives en français et en anglais : %s' if fr else '%d slides in French and English: %s') % (result['slides'], result['output'])
        if command == 'readiness':
            return result['result'] + ((' · ' + ', '.join(result['blocking'])) if result.get('blocking') else '')
        if command == 'scenarios-walk':
            s = result['summary'];return ('%d scénarios : %d PASS, %d FAIL, %d non concluants' if fr else '%d scenarios: %d PASS, %d FAIL, %d inconclusive') % (s['scenarios'], s['pass'], s['fail'], s['inconclusive'])
        if command == 'scenario-simulate':
            return result['verdict'] + ' · ' + result.get('proof_level', '')
        if command == 'drafts-rebase':
            p = result.get('prepared_change') or {}
            return ('changement préparé : %d objets, révision %d à venir' if fr else 'prepared change: %d objects, revision %d to come') % (p.get('objects', 0), p.get('baseline_revision', 0))
        if command == 'drafts-validate':
            ready = ('oui' if fr else 'yes') if result.get('deposit_ready') else ('non' if fr else 'no')
            return ('%d objets, prêt à déposer : %s' if fr else '%d objects, ready to deposit: %s') % (result.get('objects', 0), ready)
        if command == 'prepared-freeze':
            b = result['baseline'];return ('baseline figée à la révision %d' if fr else 'baseline frozen at revision %d') % b['revision']
        if command == 'guide':
            r = result.get('readiness') or {};return (r.get('result') or '') + ' · r%d' % result['baseline']['revision']
    except (KeyError, TypeError, ValueError):
        return None
    return None


def demo():
    """python -m air.tui: see the activity display without an AIR server (a simulated deliverables compilation)."""
    activity = for_command('deliverables')
    if isinstance(activity, Silent):
        print('stderr is not an interactive terminal (or AIR_NO_SPINNER, CI, --quiet): nothing to show.', file=sys.stderr)
        return 1
    activity.enter(0);time.sleep(0.8);activity.enter(1);time.sleep(9);activity.enter(2);time.sleep(1.2)
    activity.finish(summary('deliverables', {'written': ['file'] * 38, 'workspace_directory': 'docs'}))
    return 0


if __name__ == '__main__':
    sys.exit(demo())
