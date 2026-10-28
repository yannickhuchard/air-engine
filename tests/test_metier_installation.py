from pathlib import Path


def test_fresh_signed_proof_rehearsal_installs_its_optional_adapter(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from demo_metier import installation_command
    base = ['python', 'install.py']
    assert installation_command(base, True, True) == base + ['--extras', 'proofs', '--start']
    assert installation_command(base, True, False) == base + ['--start']
    assert installation_command(base, False, True) == base + ['--start', '--skip-install']
    assert base == ['python', 'install.py']
