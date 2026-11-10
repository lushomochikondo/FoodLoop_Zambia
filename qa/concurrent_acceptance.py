"""Exercise the actual service against an isolated, file-backed SQLite database."""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
with TemporaryDirectory(prefix='foodloop-concurrency-') as directory:
    if '--postgres' not in sys.argv:
        os.environ.pop('POSTGRES_DB', None)
    os.environ['FOODLOOP_SQLITE_PATH'] = str(Path(directory) / 'race.sqlite3')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings' if '--postgres' in sys.argv else 'config.test_settings'
    import django
    django.setup()
    from django.contrib.auth.models import User
    from django.core.exceptions import ValidationError
    from django.core.management import call_command
    from django.db import connections, close_old_connections
    from django.utils import timezone
    from core.models import Listing, Membership, Organisation
    from core.services import request_food, change_request
    if '--postgres' not in sys.argv:
        assert connections['default'].settings_dict['ENGINE'] == 'django.db.backends.sqlite3'
        assert Path(connections['default'].settings_dict['NAME']).resolve() == (Path(directory) / 'race.sqlite3').resolve()
    call_command('migrate', verbosity=0)
    provider = Organisation.objects.create(name='Race provider', role='provider', status='approved', area='Lusaka')
    owner = User.objects.create(username='race-owner')
    Membership.objects.create(user=owner, organisation=provider)
    listing = Listing.objects.create(provider=provider, name='Last kilogram', quantity=1, unit='kg', pathway='human', condition='fresh', area='Lusaka', address='Test only', deadline=timezone.now()+timedelta(hours=4), safety_acknowledged=True)
    requests = []
    for i in range(2):
        org = Organisation.objects.create(name=f'Race recipient {i}', role='recipient', status='approved', area='Lusaka')
        user = User.objects.create(username=f'race-recipient-{i}')
        Membership.objects.create(user=user, organisation=org)
        requests.append(request_food(user, listing.pk, Decimal('1'), True))
    barrier = Barrier(2)
    def accept(pk):
        close_old_connections()
        user = User.objects.get(pk=owner.pk)
        barrier.wait(timeout=10)
        try:
            change_request(user, pk, 'accept')
            return 'accepted'
        except ValidationError:
            return 'blocked'
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(accept, [r.pk for r in requests]))
    listing.refresh_from_db()
    assert sorted(outcomes) == ['accepted', 'blocked'], outcomes
    assert listing.allocated == 1
    assert listing.requests.filter(status='accepted').count() == 1
    connections.close_all()
    print('Database engine:',connections['default'].settings_dict['ENGINE'])
    print('PASS: concurrent acceptances for the last kilogram produced one acceptance and one validation rejection; no over-allocation.')
