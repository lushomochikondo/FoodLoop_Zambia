"""Exercise the light-only trial using actual rendered workspace pages."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from datetime import timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
with TemporaryDirectory(prefix='foodloop-light-', ignore_cleanup_errors=True) as directory:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
    os.environ['FOODLOOP_SQLITE_PATH'] = str(Path(directory) / 'light.sqlite3')
    import django
    django.setup()
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.db import connections
    from django.test import Client
    from django.utils import timezone
    from core.models import Organisation, Membership, Listing
    call_command('migrate', verbosity=0)
    pages = {}
    for role in ('provider', 'recipient', 'admin'):
        user = User.objects.create_user('light-' + role, is_staff=role == 'admin')
        if role != 'admin':
            org = Organisation.objects.create(name=role.title(), role=role, status='approved', area='Lusaka')
            Membership.objects.create(user=user, organisation=org)
            if role == 'provider':
                listing = Listing.objects.create(provider=org, name='Fresh bread', quantity=50, unit='kg', pathway='human',
                    condition='fresh', area='Lusaka', deadline=timezone.now()+timedelta(days=3), safety_acknowledged=True)
        client = Client()
        client.force_login(user)
        paths = ['/', '/dashboard/', '/profile/', '/notifications/', f'/listings/{listing.pk}/']
        paths += ['/listings/new/'] if role == 'provider' else ['/administration/', '/administration/system/'] if role == 'admin' else []
        for path in paths:
            response = client.get(path, HTTP_HOST='localhost')
            assert response.status_code == 200, (role, path, response.status_code)
            pages[role, path] = response.content.decode()
    connections.close_all()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        for role in ('provider', 'recipient', 'admin'):
            context = browser.new_context(color_scheme='dark')
            context.add_init_script("localStorage.setItem('foodloop-theme','dark'); Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({})}})")
            def handle(route):
                path = urlparse(route.request.url).path
                if path.startswith('/static/'):
                    asset = ROOT / 'static' / path.removeprefix('/static/')
                    route.fulfill(path=str(asset)) if asset.is_file() else route.fulfill(status=404, body='')
                elif path == '/listings/stock/':
                    route.fulfill(json={'listings': [{'id': listing.pk, 'available': True,
                        'remaining': '50', 'reserved': '0', 'collected': '0',
                        'status': 'Available', 'status_key': 'available'}]})
                else:
                    route.fulfill(body=pages.get((role, path), ''), content_type='text/html')
            context.route('https://foodloop.test/**', handle)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for path in [path for key, path in pages if key == role]:
                for width in (320, 390, 1440):
                    page.set_viewport_size({'width': width, 'height': 950})
                    page.goto('https://foodloop.test' + path)
                    assert page.evaluate('document.documentElement.dataset.theme') == 'light'
                    assert page.evaluate('getComputedStyle(document.documentElement).colorScheme') == 'light'
                    assert page.locator('#theme-toggle').count() == 0
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (role, path, width)
                    if path == '/':
                        assert page.locator('[data-listing-card]').count() == 1
                        assert 'hero-save-planet' in page.locator('.exchange-intro').evaluate('el=>getComputedStyle(el).backgroundImage')
                    for field in page.locator('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, select').all():
                        if field.is_visible():
                            channels = field.evaluate('el=>getComputedStyle(el).backgroundColor').split('(')[1].split(')')[0].split(',')
                            assert all(float(value.strip()) > 180 for value in channels[:3]), (role, path, channels)
                print(f'{role} {path}: light theme, no toggle, light inputs and mobile/desktop layout PASS', flush=True)
            page.emulate_media(color_scheme='light')
            page.emulate_media(color_scheme='dark')
            page.evaluate("dispatchEvent(new StorageEvent('storage',{key:'foodloop-theme',newValue:'dark'}))")
            page.reload()
            assert page.evaluate('document.documentElement.dataset.theme') == 'light'
            assert page.evaluate("localStorage.getItem('foodloop-theme')") == 'dark'
            page.screenshot(path=str(ROOT / f'qa/light-trial-{role}.png'), full_page=True)
            assert not errors, errors
            print(role + ': OS changes, saved dark preference and reload cannot enable dark mode PASS', flush=True)
            context.close()
        browser.close()
