import os
from email.utils import parseaddr
import secrets
from urllib.parse import parse_qs, unquote, urlparse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env.local', override=False, interpolate=False)
load_dotenv(BASE_DIR / '.env', override=False, interpolate=False)
secret_file = BASE_DIR / 'local-secret.txt'
RENDER = os.environ.get('RENDER') == 'true'
DEBUG = os.environ.get('DJANGO_DEBUG', '0' if os.environ.get('VERCEL') == '1' or RENDER else '1') == '1'
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
if os.environ.get('VERCEL') == '1':
    ALLOWED_HOSTS.append('.vercel.app')
    if os.environ.get('VERCEL_URL'):
        ALLOWED_HOSTS.append(os.environ['VERCEL_URL'].split(':', 1)[0])
WSGI_APPLICATION = 'config.wsgi.application'
if RENDER and os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    ALLOWED_HOSTS.append(os.environ['RENDER_EXTERNAL_HOSTNAME'])
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
if os.environ.get('DATABASE_URL'):
    database_url = urlparse(os.environ['DATABASE_URL'])
    if database_url.scheme not in ('postgres', 'postgresql'):
        raise RuntimeError('DATABASE_URL must be a PostgreSQL connection string.')
    database_options = parse_qs(database_url.query)
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(database_url.path.lstrip('/')),
        'USER': unquote(database_url.username or ''),
        'PASSWORD': unquote(database_url.password or ''),
        'HOST': database_url.hostname or '',
        'PORT': str(database_url.port or 5432),
        'CONN_MAX_AGE': 0 if os.environ.get('VERCEL') == '1' else 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': database_options.get('sslmode', ['require'])[0]},
    }}
elif os.environ.get('POSTGRES_DB'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ['POSTGRES_DB'], 'USER': os.environ.get('POSTGRES_USER', ''), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''), 'HOST': os.environ.get('POSTGRES_HOST', 'localhost'), 'PORT': os.environ.get('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60, 'OPTIONS': {'sslmode': os.environ.get('POSTGRES_SSLMODE', 'require')}}}
elif os.environ.get('VERCEL') == '1':
    raise RuntimeError('Set DATABASE_URL to a persistent PostgreSQL database before deploying FoodLoop to Vercel.')
if RENDER and DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise RuntimeError('Set DATABASE_URL to a persistent PostgreSQL database before deploying FoodLoop to Render.')
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}]
TIME_ZONE = 'Africa/Lusaka'
USE_TZ = True
LANGUAGE_CODE = 'en-gb'
STATIC_URL = 'static/'
WHITENOISE_MIMETYPES = {'.webmanifest': 'application/manifest+json'}
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'media')))
MEDIA_URL = '/media/'
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG else 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
OBJECT_STORAGE_BUCKET = os.environ.get('OBJECT_STORAGE_BUCKET', '')
PRIVATE_UPLOADS_BUCKET = os.environ.get('PRIVATE_UPLOADS_BUCKET', '')
if OBJECT_STORAGE_BUCKET:
    AWS_STORAGE_BUCKET_NAME = OBJECT_STORAGE_BUCKET
    AWS_S3_REGION_NAME = os.environ.get('OBJECT_STORAGE_REGION', 'auto')
    AWS_S3_ENDPOINT_URL = os.environ.get('OBJECT_STORAGE_ENDPOINT_URL') or None
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    if AWS_S3_ENDPOINT_URL:
        AWS_S3_ADDRESSING_STYLE = 'path'
    STORAGES['default'] = {'BACKEND': 'storages.backends.s3.S3Storage', 'OPTIONS': {
        'bucket_name': OBJECT_STORAGE_BUCKET,
        'default_acl': 'private',
        'querystring_auth': True,
        'file_overwrite': False,
    }}
if os.environ.get('VERCEL') == '1' and (not OBJECT_STORAGE_BUCKET or not PRIVATE_UPLOADS_BUCKET):
    raise RuntimeError('Set OBJECT_STORAGE_BUCKET and PRIVATE_UPLOADS_BUCKET to persistent buckets before deploying FoodLoop to Vercel.')
if RENDER and (not OBJECT_STORAGE_BUCKET or not PRIVATE_UPLOADS_BUCKET):
    raise RuntimeError('Set OBJECT_STORAGE_BUCKET and PRIVATE_UPLOADS_BUCKET before deploying FoodLoop to Render.')
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
MATCH_WEIGHTS = {'location': int(os.environ.get('MATCH_WEIGHT_LOCATION', '30')), 'urgency': int(os.environ.get('MATCH_WEIGHT_URGENCY', '30')), 'quantity': int(os.environ.get('MATCH_WEIGHT_QUANTITY', '20')), 'condition': int(os.environ.get('MATCH_WEIGHT_CONDITION', '20'))}
NEARBY_AREAS = {'Lusaka Central': ['Longacres', 'Rhodes Park'], 'Longacres': ['Lusaka Central', 'Rhodes Park'], 'Rhodes Park': ['Lusaka Central', 'Longacres']}
TEMPLATES[0]['OPTIONS']['context_processors'].extend(['core.context_processors.workspace', 'core.context_processors.push'])
CO2E_KG_PER_KG = os.environ.get('CO2E_KG_PER_KG', '')
CO2E_SOURCE = os.environ.get('CO2E_SOURCE', '')
REOFFER_GROUP_SIZE = int(os.environ.get('REOFFER_GROUP_SIZE', '5'))
REOFFER_HALF_TIME_FRACTION = os.environ.get('REOFFER_HALF_TIME_FRACTION', '0.5')
HANDOVER_CODE_ATTEMPTS = int(os.environ.get('HANDOVER_CODE_ATTEMPTS', '5'))
LITRE_TO_KG_FACTOR = os.environ.get('LITRE_TO_KG_FACTOR', '1')
WEIGHT_SANITY_LIMIT_KG = os.environ.get('WEIGHT_SANITY_LIMIT_KG', '100000')
IMPACT_VALUE_PER_KG_HUMAN = os.environ.get('IMPACT_VALUE_PER_KG_HUMAN', '')
IMPACT_VALUE_PER_KG_FEED = os.environ.get('IMPACT_VALUE_PER_KG_FEED', '')
IMPACT_VALUE_PER_KG_COMPOST = os.environ.get('IMPACT_VALUE_PER_KG_COMPOST', '')
EMAIL_NOTIFICATIONS_ENABLED = os.environ.get('EMAIL_NOTIFICATIONS_ENABLED', '0') == '1'
WEB_PUSH_PUBLIC_KEY = os.environ.get('WEB_PUSH_PUBLIC_KEY', '')
WEB_PUSH_PRIVATE_KEY = os.environ.get('WEB_PUSH_PRIVATE_KEY', '')
WEB_PUSH_SUBJECT = os.environ.get('WEB_PUSH_SUBJECT', '')
WEB_PUSH_ENABLED = bool(WEB_PUSH_PUBLIC_KEY and WEB_PUSH_PRIVATE_KEY)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
GMAIL_CLIENT_ID = os.environ.get('GMAIL_CLIENT_ID', '')
GMAIL_CLIENT_SECRET = os.environ.get('GMAIL_CLIENT_SECRET', '')
GMAIL_REFRESH_TOKEN = os.environ.get('GMAIL_REFRESH_TOKEN', '')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = 15
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'foodloop@example.invalid')
if not WEB_PUSH_SUBJECT:
    WEB_PUSH_SUBJECT = 'mailto:' + (parseaddr(DEFAULT_FROM_EMAIL)[1] or 'admin@foodloop.example')
PUBLIC_APP_URL = os.environ.get('PUBLIC_APP_URL', os.environ.get('RENDER_EXTERNAL_URL', '')).rstrip('/')
if not DEBUG:
    if not os.environ.get('DJANGO_SECRET_KEY'):
        raise RuntimeError('Set DJANGO_SECRET_KEY before running with DEBUG disabled.')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]
    if RENDER and os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
        CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['RENDER_EXTERNAL_HOSTNAME'])
    if os.environ.get('VERCEL') == '1':
        CSRF_TRUSTED_ORIGINS.append('https://*.vercel.app')
        if os.environ.get('VERCEL_URL'):
            CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['VERCEL_URL'].split(':', 1)[0])
        if os.environ.get('VERCEL_PROJECT_PRODUCTION_URL'):
            CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['VERCEL_PROJECT_PRODUCTION_URL'].split(':', 1)[0])
    if os.environ.get('DJANGO_TRUST_PROXY') == '1' or os.environ.get('VERCEL') == '1':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Public, best-effort pilot router; replace with a dedicated service before scaling.
ROUTING_BASE_URL = os.environ.get('ROUTING_BASE_URL', 'https://routing.openstreetmap.de')
