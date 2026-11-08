"""Apply migrations before serving the single-instance Render testing service."""
import runpy
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(root / 'manage.py'), 'check', '--deploy'], check=True)
subprocess.run([sys.executable, str(root / 'manage.py'), 'migrate', '--noinput'], check=True)
runpy.run_path(str(root / 'scripts' / 'serve.py'), run_name='__main__')
