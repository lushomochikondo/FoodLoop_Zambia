"""Create a source-only archive without local credentials, records or uploads."""
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
output_dir = root / 'dist'
output_dir.mkdir(exist_ok=True)
archive = output_dir / f'foodloop-source-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip'
directories = ['config', 'core', 'templates', 'static', 'docs', 'scripts']
files = ['manage.py', 'requirements.txt', 'requirements-production.txt', 'README.md', '.gitignore', '.dockerignore', '.env.example', 'Dockerfile']
with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
    for name in directories:
        for path in sorted((root/name).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                bundle.write(path, path.relative_to(root))
    for name in files:
        bundle.write(root/name, name)
with ZipFile(archive) as bundle:
    names = bundle.namelist()
    assert not any(name.endswith(('.sqlite3', 'local-secret.txt')) or name.startswith(('media/', '.venv/', 'backups/')) for name in names)
print(f'Source archive created and checked: {archive}')
