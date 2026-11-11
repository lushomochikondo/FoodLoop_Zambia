"""Apply migrations before serving the single-instance Render testing service."""
import runpy
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(root / 'manage.py'), 'check', '--deploy'], check=True)
subprocess.run([sys.executable, str(root / 'manage.py'), 'migrate', '--noinput'], check=True)
if os.environ.get('ENABLE_BACKGROUND_JOBS', '1') == '1':
    from supervise import supervise
    sys.exit(supervise([
        [sys.executable, '-u', str(root / 'scripts' / 'serve.py')],
        [sys.executable, '-u', str(root / 'manage.py'), 'run_scheduler'],
    ]))
else:
    runpy.run_path(str(root / 'scripts' / 'serve.py'), run_name='__main__')
