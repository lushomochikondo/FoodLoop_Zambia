"""Check production settings and actual WhiteNoise responses without publishing."""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_SECRET_KEY'] = secrets.token_urlsafe(64)
os.environ['DJANGO_ALLOWED_HOSTS'] = 'testserver'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = 'https://testserver'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.core.management import call_command
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import Client

call_command('collectstatic', interactive=False, verbosity=0)
call_command('check', deploy=True)
client = Client()
response = client.get('/login/', secure=True)
assert response.status_code == 200, response.status_code
assert response.cookies['csrftoken']['secure']
assert response.headers['Strict-Transport-Security'].startswith('max-age=31536000')
for name in ['responsive.css', 'fonts/Inter.ttf', 'images/market.jpg', 'navigation.js', 'upload.js']:
    url = staticfiles_storage.url(name)
    asset = client.get(url, secure=True)
    assert asset.status_code == 200, (name, url, asset.status_code)
    asset.close()
assert client.get('/login/').status_code == 301
print('PASS: production sign-in page, HTTPS redirect, HSTS, hashed stylesheet, bundled font, photo and scripts.')
