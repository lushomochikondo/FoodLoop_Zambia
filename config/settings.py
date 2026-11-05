import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False, interpolate=False)
secret_file = BASE_DIR / 'local-secret.txt'
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Set DJANGO_SECRET_KEY before running with DEBUG disabled.')
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(64))
    SECRET_KEY = secret_file.read_text().strip()
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
if os.environ.get('DJANGO_ALLOWED_HOSTS'):
    ALLOWED_HOSTS = [host.strip() for host in os.environ['DJANGO_ALLOWED_HOSTS'].split(',') if host.strip()]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
if DEBUG:
    TEMPLATES[0]['APP_DIRS'] = False
    TEMPLATES[0]['OPTIONS']['loaders'] = ['django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3', 'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}}
if os.environ.get('FOODLOOP_SQLITE_PATH'):
    DATABASES['default']['NAME'] = os.environ['FOODLOOP_SQLITE_PATH']
if os.environ.get('POSTGRES_DB'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ['POSTGRES_DB'], 'USER': os.environ.get('POSTGRES_USER', ''), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''), 'HOST': os.environ.get('POSTGRES_HOST', 'localhost'), 'PORT': os.environ.get('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60, 'OPTIONS': {'sslmode': os.environ.get('POSTGRES_SSLMODE', 'require')}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}]
TIME_ZONE = 'Africa/Lusaka'
USE_TZ = True
LANGUAGE_CODE = 'en-gb'
STATIC_URL = 'static/'
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'media')))
MEDIA_URL = '/media/'
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG else 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
REQUEST_EXPIRY_HOURS = int(os.environ.get('REQUEST_EXPIRY_HOURS', '24'))
MEAL_WEIGHT_KG = os.environ.get('MEAL_WEIGHT_KG', '0.4')
MATCH_WEIGHTS = {'location': 30, 'urgency': 30, 'quantity': 20, 'condition': 20}
NEARBY_AREAS = {'Lusaka Central': ['Longacres', 'Rhodes Park'], 'Longacres': ['Lusaka Central', 'Rhodes Park'], 'Rhodes Park': ['Lusaka Central', 'Longacres']}
TEMPLATES[0]['OPTIONS']['context_processors'].append('core.context_processors.workspace')
CO2E_KG_PER_KG = os.environ.get('CO2E_KG_PER_KG', '')
CO2E_SOURCE = os.environ.get('CO2E_SOURCE', '')
EMAIL_NOTIFICATIONS_ENABLED = os.environ.get('EMAIL_NOTIFICATIONS_ENABLED', '0') == '1'
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = 15
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'foodloop@example.invalid')
PUBLIC_APP_URL = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
if not DEBUG:
    if not os.environ.get('DJANGO_SECRET_KEY'):
        raise RuntimeError('Set DJANGO_SECRET_KEY before running with DEBUG disabled.')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]
    if os.environ.get('DJANGO_TRUST_PROXY') == '1':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
