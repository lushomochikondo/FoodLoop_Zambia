"""Isolated local settings: python manage.py test --settings=config.test_settings."""
import tempfile
from pathlib import Path
from .settings import *

# Override deployed resources before Django loads models or storage instances.
_TEST_FILES = tempfile.TemporaryDirectory(prefix='foodloop-tests-')
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('FOODLOOP_SQLITE_PATH', str(Path(_TEST_FILES.name) / 'db.sqlite3')),
    'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'},
}}
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
MEDIA_ROOT = Path(_TEST_FILES.name) / 'media'
PRIVATE_UPLOADS_BUCKET = ''
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
