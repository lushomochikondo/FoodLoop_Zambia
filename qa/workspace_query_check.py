"""Measure complete rendered workspace queries in an isolated database."""
import os
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
with TemporaryDirectory(prefix='foodloop-query-') as directory:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
    os.environ['FOODLOOP_SQLITE_PATH'] = str(Path(directory) / 'queries.sqlite3')
    import django
    django.setup()
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.db import connection, connections
    from django.test import Client
    from django.test.utils import CaptureQueriesContext
    from django.utils import timezone
    from core.models import Listing, Membership, Organisation
    call_command('migrate', verbosity=0)
    org = Organisation.objects.create(name='Query donor', role='provider', status='approved', area='Lusaka')
    user = User.objects.create(username='query-donor')
    Membership.objects.create(user=user, organisation=org)
    for index in range(5):
        Listing.objects.create(provider=org, name=f'Food {index}', quantity=50,
            unit='kg', pathway='human', condition='fresh', area='Lusaka',
            deadline=timezone.now() + timedelta(days=3), safety_acknowledged=True)
    client = Client()
    client.force_login(user)
    client.get('/', HTTP_HOST='localhost')  # Warm process-local platform settings.
    for path in ('/', '/dashboard/', '/requests/', '/impact/'):
        with CaptureQueriesContext(connection) as queries:
            response = client.get(path, HTTP_HOST='localhost')
        assert response.status_code == 200, (path, response.status_code)
        print(f'{path}: {len(queries)} database queries', flush=True)
    connections.close_all()
