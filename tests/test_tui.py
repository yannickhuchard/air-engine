"""The AIR activity display: informative on a terminal, invisible everywhere else."""
import io
import re
import time
import pytest
from air import tui
from air.cli import main


class Terminal(io.StringIO):
    def __init__(self, encoding='utf-8'):
        super().__init__();self._encoding = encoding

    @property
    def encoding(self): return self._encoding

    def isatty(self): return True


def plain(text): return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)


@pytest.fixture(autouse=True)
def interactive(monkeypatch):
    for name in ('CI', 'AIR_NO_SPINNER', 'NO_COLOR', 'TERM'): monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('AIR_LANG', 'fr')
    monkeypatch.setattr(tui, '_ansi_ready', lambda stream: True)


def test_it_says_what_will_be_done_what_is_running_and_how_it_ended():
    stream = Terminal()
    activity = tui.for_command('deliverables', stream=stream)
    activity.enter(1);time.sleep(tui.DELAY + 0.3);activity.enter(2);time.sleep(0.2)
    activity.finish(tui.summary('deliverables', {'written': ['a', 'b'], 'workspace_directory': 'docs'}))
    text = plain(stream.getvalue())
    assert 'Compiler le dossier de livrables' in text and 'AIR compile 37 documents' in text and 'Comparer et écrire les fichiers' in text
    assert '↳ lecture des baselines épinglées' in text, 'the current step explains what AIR does'
    assert text.rstrip().endswith('2 fichiers écrits dans docs') and 'terminé en' in text


def test_it_stays_silent_when_nobody_watches(monkeypatch):
    assert isinstance(tui.for_command('deliverables', stream=io.StringIO()), tui.Silent), 'not a terminal'
    assert isinstance(tui.for_command('deliverables', quiet=True, stream=Terminal()), tui.Silent)
    monkeypatch.setenv('CI', 'true')
    assert isinstance(tui.for_command('deliverables', stream=Terminal()), tui.Silent)
    monkeypatch.delenv('CI');monkeypatch.setenv('AIR_NO_SPINNER', '1')
    assert isinstance(tui.for_command('deliverables', stream=Terminal()), tui.Silent)


def test_a_fast_command_shows_nothing():
    stream = Terminal()
    activity = tui.for_command('readiness', stream=stream)
    activity.enter(1);activity.finish('READY_TO_BUILD')
    assert stream.getvalue() == ''


def test_a_terminal_without_unicode_gets_ascii_and_a_failure_is_said():
    stream = Terminal('cp1252')
    activity = tui.for_command('presentation', stream=stream)
    activity.enter(1);time.sleep(tui.DELAY + 0.2);activity.fail('HTTP 422')
    text = plain(stream.getvalue())
    assert 'x AIR' in text and 'échec après' in text and 'HTTP 422' in text
    assert not any(ord(c) > 0x2000 for c in text.replace('’', "'")), 'no braille or check marks on a legacy code page'


def test_the_cli_keeps_stdout_for_json_and_accepts_quiet(capsys):
    assert main(['--quiet', 'capabilities']) == 0
    out, err = capsys.readouterr()
    assert out.lstrip().startswith('{') and err == ''


def test_summaries_say_what_was_produced():
    assert tui.summary('readiness', {'result': 'NOT_READY', 'blocking': ['GAPS']}, 'fr') == 'NOT_READY · GAPS'
    assert tui.summary('scenarios-walk', {'summary': {'scenarios': 2, 'pass': 1, 'fail': 1, 'inconclusive': 0}}, 'en') == '2 scenarios: 1 PASS, 1 FAIL, 0 inconclusive'
    assert tui.summary('prepared-freeze', {'baseline': {'revision': 7}}, 'fr') == 'baseline figée à la révision 7'
    assert tui.summary('unknown', {}, 'fr') is None
