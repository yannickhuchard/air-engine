"""Run pytest with temporary files on the project drive and UTF-8 diagnostics."""
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    scratch = Path(os.environ.get('AIR_WORK_ROOT', ROOT / 'tmp')).resolve() / 'test-runtime'
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(scratch)
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', *sys.argv[1:]], cwd=ROOT))
