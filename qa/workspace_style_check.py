"""Run the current light-only workspace browser checks."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('light_theme_check.py')), run_name='__main__')
