"""Browser checks against an isolated local Django server; no hosted data used."""
import os
import sys
import json
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with TemporaryDirectory(prefix='foodloop-map-browser-') as temp:
    os.environ['FOODLOOP_SQLITE_PATH'] = str(Path(temp) / 'browser.sqlite3')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from django.test import Client
    from django.utils import timezone
    from core.models import Organisation, Membership, Listing, FoodRequest
    from playwright.sync_api import sync_playwright
    call_command('migrate', verbosity=0)
    def account(name, role):
        user = User.objects.create_user(name)
        org = Organisation.objects.create(name=name, role=role, status='approved', pathway='human', area='Lusaka')
        Membership.objects.create(user=user, organisation=org)
        return user, org
    donor, donor_org = account('Map demo donor', 'provider')
    recipient, recipient_org = account('Map demo recipient', 'recipient')
    listing = Listing.objects.create(provider=donor_org, name='Map test vegetables', quantity=10, pathway='human', condition='fresh', area='Lusaka', address='Private entrance', deadline=timezone.now()+timedelta(hours=4), safety_acknowledged=True, pickup_latitude='-15.416789', pickup_longitude='28.283456', access_surface='gravel', access_condition='rough', access_notes='Final 600 m is muddy after rain.', access_reported_at=timezone.now())
    log = subprocess.DEVNULL
    server = subprocess.Popen([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8011', '--noreload', '--settings=config.test_settings'], cwd=ROOT, stdout=log, stderr=log)
    try:
        import requests
        base = 'http://127.0.0.1:8011'
        for attempt in range(40):
            try:
                if requests.get(base+'/login/', timeout=1).status_code == 200: break
            except requests.RequestException: pass
            time.sleep(.25)
        else: raise RuntimeError('Local test server did not start')
        cookies = {}
        for user in (donor, recipient):
            client = Client(); client.force_login(user)
            cookies[user.pk] = client.cookies['sessionid'].value
        from django.db import connections
        connections.close_all()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            errors = []
            context = browser.new_context(permissions=['geolocation'], geolocation={'latitude':-15.4,'longitude':28.27})
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            tile_responses = []
            page.on('response', lambda response: tile_responses.append(response.status) if 'tile.openstreetmap.org/' in response.url else None)
            def login(user):
                context.clear_cookies()
                context.add_cookies([{'name':'sessionid','value':cookies[user.pk],'url':base}])
            login(donor)
            for width in (390, 1440):
                page.set_viewport_size({'width':width,'height':900})
                page.goto(base+'/listings/new/')
                page.locator('[data-open-pickup-map]').click()
                assert page.locator('[data-pickup-town] option').count() == 12
                page.locator('[data-pickup-town]').select_option('-10.2117,31.1808')
                assert page.locator('#id_pickup_latitude').input_value() == ''
                page.locator('[data-zambia-overview]').click()
                assert page.locator('[data-pickup-town]').input_value() == ''
                page.locator('#id_access_surface').select_option('gravel')
                page.locator('#id_access_condition').select_option('rough')
                page.locator('#id_access_notes').fill('Final 600 m is muddy after rain.')
                page.locator('[data-pin-lat]').fill('-15.416789')
                page.locator('[data-pin-lon]').fill('28.283456')
                page.locator('[data-apply-pin]').click()
                assert page.locator('#id_pickup_latitude').input_value() == '-15.416789'
                page.locator('[data-clear-pickup]').click()
                assert page.locator('#id_pickup_latitude').input_value() == ''
                page.locator('[data-pickup-map]').click(position={'x':100,'y':100})
                assert page.locator('#id_pickup_latitude').input_value()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Editor overflow at {width}'
                page.screenshot(path=str(ROOT/f'qa/pickup-map-{width}.png'), full_page=True)
                print(f'{width}px donor road report and nationwide picker: coordinates, clear, map click, layout PASS', flush=True)
            # Publish from the actual editor using a pickup point in northern Zambia.
            page.locator('#id_name').fill('Kasama browser test food')
            page.locator('#id_quantity').fill('10')
            page.locator('#id_unit').select_option('kg')
            page.locator('#id_pathway').select_option('human')
            page.locator('#id_condition').select_option('fresh')
            page.locator('#id_area').fill('Kasama')
            page.locator('#id_address').fill('Private Kasama entrance')
            page.locator('[data-pin-lat]').fill('-10.2117')
            page.locator('[data-pin-lon]').fill('31.1808')
            page.locator('[data-apply-pin]').click()
            page.locator('#id_safety_acknowledged').check()
            page.locator('.editor-actions button').click()
            page.wait_for_url('**/listings/*/')
            assert 'Kasama browser test food' in page.content()
            assert 'Donor reported' in page.content()
            assert 'Final 600 m is muddy after rain.' in page.content()
            assert json.loads(page.locator('#route-destination').text_content())['latitude'] == -10.2117
            print('Kasama listing: browser publish, northern pickup pin and road report persisted PASS', flush=True)
            login(recipient)
            for width in (390, 1440):
                page.set_viewport_size({'width':width,'height':900})
                page.goto(base+f'/listings/{listing.pk}/')
                assert 'Final 600 m is muddy after rain.' not in page.content()
                config = json.loads(page.locator('#route-destination').text_content())
                assert config['exact'] is False and config['latitude'] == -15.42
                page.locator('[data-open-route]').click()
                page.locator('[data-route-zambia]').click()
                assert 'Showing all Zambia' in page.locator('[data-route-status]').text_content()
                page.locator('[data-origin-gps]').click()
                page.wait_for_function("document.querySelector('[data-origin-lat]').value !== ''")
                assert page.locator('[data-origin-lat]').input_value() == '-15.400000'
                page.locator('[data-origin-lat]').fill('')
                page.locator('[data-calculate-route]').click()
                assert 'valid starting point' in page.locator('[data-route-status]').text_content()
                page.locator('[data-origin-lat]').fill('-15.4')
                page.locator('[data-origin-lon]').fill('28.27')
                payload = {'routes':[{'distance':2500,'duration':400,'geometry':{'type':'LineString','coordinates':[[28.27,-15.4],[28.28,-15.42]]},'steps':[{'name':'Test road','distance':2500,'type':'depart','modifier':''}]}], 'deadline':listing.deadline.isoformat()}
                page.route('**/route/', lambda route: route.fulfill(json=payload))
                page.locator('[data-calculate-route]').click()
                page.locator('.route-choice').wait_for()
                assert '2.5 km' in page.locator('.route-choice').text_content()
                assert 'destination=-15.42%2C28.28' in page.locator('[data-google-route]').get_attribute('href')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Route overflow at {width}'
                page.wait_for_timeout(1500)
                assert page.locator('.leaflet-overlay-pane path').count() > 0
                assert page.locator('.leaflet-overlay-pane svg').bounding_box()['width'] > 200, 'Map overlay shrunk by icon styles'
                page.screenshot(path=str(ROOT/f'qa/collection-route-{width}.png'), full_page=True)
                page.unroute('**/route/')
                page.route('**/route/', lambda route: route.fulfill(status=503,json={'error':'Route estimates are temporarily unavailable.'}))
                page.locator('[data-calculate-route]').click()
                page.wait_for_function("document.querySelector('[data-route-status]').textContent.includes('temporarily unavailable')")
                page.unroute('**/route/')
                print(f'{width}px recipient: private preview, GPS, validation, route display, navigation link, provider failure, layout PASS', flush=True)
            from concurrent.futures import ThreadPoolExecutor
            def accept():
                FoodRequest.objects.create(listing_id=listing.pk, recipient_id=recipient_org.pk, quantity=1, status='accepted')
                connections.close_all()
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(accept).result()
            page.reload()
            assert json.loads(page.locator('#route-destination').text_content())['exact'] is True
            assert 'Private entrance' in page.content()
            assert 'Final 600 m is muddy after rain.' in page.content()
            assert 'Donor reported' in page.content()
            print('Accepted recipient: exact pickup pin and private address PASS', flush=True)
            assert not errors, errors
            print('Browser JavaScript errors: 0', flush=True)
            print('Live map tiles: HTTP statuses', sorted(set(tile_responses)), flush=True)
            assert 200 in tile_responses, 'No live map tiles loaded'
            browser.close()
    finally:
        server.terminate(); server.wait(timeout=15); connections.close_all()
