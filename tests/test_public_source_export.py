import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

spec = importlib.util.spec_from_file_location('public_export', Path(__file__).parents[1] / 'scripts/export_public_source.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_export_pins_committed_bytes_and_excludes_unselected_private_files(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    git('init', '-q')
    (repo / 'public.txt').write_bytes(b'public\n')
    (repo / 'private.txt').write_bytes(b'not published\n')
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
    data = subprocess.check_output(['git', '-C', str(repo), 'show', 'HEAD:public.txt'])
    plan = {'schema':'air.public-source-selection/1', 'commit':git('rev-parse', 'HEAD'),
            'files':{'public.txt':hashlib.sha256(data).hexdigest()}}
    path = tmp_path / 'plan.json';path.write_text(json.dumps(plan))
    (repo / 'public.txt').write_text('unreviewed working changes')
    output = tmp_path / 'export'
    assert module.export(path, output, repo)['files'] == 1
    assert [p.name for p in output.iterdir()] == ['public.txt']
    assert (output / 'public.txt').read_bytes() == data
    with pytest.raises(ValueError, match='new directory'): module.export(path, output, repo)
    plan['files']['public.txt'] = '0' * 64;path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='digest mismatch'): module.export(path, tmp_path / 'bad', repo)
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', '.git/config', '.GIT/config', '.air/key', 'a/../b', 'x\\y', 'NUL.txt', 'a./b', 'a\nb'])
def test_unsafe_public_paths(name):
    with pytest.raises(ValueError): module.safe_path(name)
