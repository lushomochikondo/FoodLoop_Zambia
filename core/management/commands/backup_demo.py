import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

class Command(BaseCommand):
    help = 'Create a consistent SQLite backup plus uploaded media. Source records are not changed.'
    def add_arguments(self, parser):
        parser.add_argument('--output', default='backups')
    def handle(self, *args, **options):
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Use pg_dump for PostgreSQL backups; see docs/DEPLOYMENT.md.')
        root = Path(options['output']).resolve()
        if root == Path(settings.MEDIA_ROOT).resolve() or Path(settings.MEDIA_ROOT).resolve() in root.parents:
            raise CommandError('Choose a backup destination outside the media directory.')
        target = root / timezone.now().strftime('foodloop-%Y%m%d-%H%M%S-%f')
        target.mkdir(parents=True, exist_ok=False)
        with closing(sqlite3.connect(settings.DATABASES['default']['NAME'])) as source:
            with closing(sqlite3.connect(target / 'db.sqlite3')) as dest:
                source.backup(dest)
        media = Path(settings.MEDIA_ROOT)
        if media.exists(): shutil.copytree(media, target / 'media')
        self.stdout.write(f'Backup created: {target}')
