"""Visual, accessibility and content checks for cards and account entry pages."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
with TemporaryDirectory(prefix='foodloop-marketplace-', ignore_cleanup_errors=True) as directory:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
    os.environ['FOODLOOP_SQLITE_PATH'] = str(Path(directory) / 'qa.sqlite3')
    import django
    django.setup()
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.db import connections
    from django.test import Client
    from django.utils import timezone
    from core.models import Listing, Membership, Organisation
    call_command('migrate', verbosity=0)
    users, listings, pages = {}, [], {}
    for role in ('provider', 'recipient', 'admin'):
        user = User.objects.create_user('marketplace-' + role, is_staff=role == 'admin')
        if role != 'admin':
            org = Organisation.objects.create(name='Sunrise Market' if role == 'provider' else 'Community Kitchen',
                role=role, status='approved', area='Lusaka')
            Membership.objects.create(user=user, organisation=org)
            if role == 'provider':
                for name, pathway, photo in [('Fresh bread rolls for community kitchens', 'human', 'qa-bread.jpg'),
                                              ('Vegetable trimmings for livestock projects', 'feed', ''),
                                              ('Organic material for composting', 'compost', '')]:
                    listings.append(Listing.objects.create(provider=org, name=name, pathway=pathway,
                        condition='spoiled' if pathway == 'compost' else 'fresh', photo=photo,
                        quantity=50, unit='kg', area='Lusaka', deadline=timezone.now()+timedelta(hours=4), safety_acknowledged=True))
                for position in range(4):
                    listings[0].extra_photos.create(image=f'qa-extra-{position}.jpg', position=position)
        users[role] = user
        client = Client(); client.force_login(user)
        for path in ['/', '/notifications/', f'/listings/{listings[0].pk}/'] + (['/listings/new/', f'/listings/{listings[0].pk}/edit/'] if role == 'provider' else []):
            response = client.get(path, HTTP_HOST='localhost')
            assert response.status_code == 200
            pages[role, path] = response.content.decode()
    public = Client()
    session = public.session
    session['beneficiary_eligibility'] = {'version': 'zambia-beneficiary-v1', 'programme_type': 'community_kitchen', 'accepted_at': timezone.now().isoformat()}
    session.save()
    for path in ('/login/', '/signup/', '/signup/?type=provider', '/signup/?type=recipient', '/beneficiary/eligibility/'):
        response = public.get(path, HTTP_HOST='localhost')
        assert response.status_code == 200, (path, response.status_code)
        pages['public', path] = response.content.decode()
    connections.close_all()
    from playwright.sync_api import sync_playwright
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        for role in ('public', 'provider', 'recipient', 'admin'):
            context = browser.new_context(color_scheme='dark')
            context.add_init_script("Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({})}})")
            def handle(route):
                parsed = urlparse(route.request.url)
                path = parsed.path
                if path.startswith('/static/'):
                    asset = ROOT / 'static' / path.removeprefix('/static/')
                    route.fulfill(path=str(asset)) if asset.is_file() else route.fulfill(status=404, body='')
                elif path.endswith('/photo/') or '/photos/' in path:
                    route.fulfill(path=str(ROOT / 'static/images/foodloop-fresh-food.jpg'))
                elif path == '/listings/stock/':
                    route.fulfill(json={'listings': [{'id': item.pk, 'available': True, 'remaining': '50',
                        'reserved': '0', 'collected': '0', 'status': 'Available', 'status_key': 'available'} for item in listings]})
                else:
                    key = path + ('?' + parsed.query if parsed.query else '')
                    route.fulfill(body=pages.get((role, key), ''), content_type='text/html')
            context.route('https://foodloop.test/**', handle)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for key_role, path in pages:
                if key_role != role:
                    continue
                for width in (320, 390, 820, 1440):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.goto('https://foodloop.test' + path)
                    page.evaluate('document.fonts.ready')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), (role, path, width)
                    assert page.evaluate('document.documentElement.dataset.theme') == 'light'
                    assert page.locator('body').evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgb(246, 243, 235)'
                    assert page.locator('#push-test').count() == 0
                    if path == '/':
                        assert page.locator('.marketplace-card').count() == 3
                        assert page.locator('.match-reasons,.free-label,.card-bottom').count() == 0
                        for card in page.locator('.marketplace-card').all():
                            assert card.locator('.photo-pathway').count() == 1
                            assert card.locator('[data-stock-remaining]').inner_text() == '50'
                            assert 'View listing' in card.inner_text()
                            assert card.locator('h3').evaluate("el=>getComputedStyle(el).webkitLineClamp") == '2'
                            assert card.locator('.card-action').evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
                        assert page.locator('.marketplace-card.is-urgent').count() == 0
                        assert page.locator('.card-deadline.is-urgent').count() == 3
                    if path == '/login/':
                        assert page.locator('.login-panel').evaluate('el=>getComputedStyle(el).borderTopWidth') == '1px'
                    if path.startswith('/signup/'):
                        assert page.locator('.signup-heading').evaluate('el=>getComputedStyle(el).backgroundImage') == 'none'
                        assert page.locator('.signup-heading').evaluate("el=>getComputedStyle(el,'::after').content") == 'none'
                    if path == f'/listings/{listings[0].pk}/':
                        assert page.locator('[data-gallery-src]').count() == 5
                        page.get_by_role('button', name='Show photo 3', exact=True).click()
                        assert page.locator('[data-gallery-position]').inner_text() == 'Photo 3 of 5'
                        page.get_by_role('button', name='Show photo 3', exact=True).press('ArrowRight')
                        assert page.locator('[data-gallery-position]').inner_text() == 'Photo 4 of 5'
                    if path == '/listings/new/':
                        data = (ROOT / 'static/images/foodloop-fresh-food.jpg').read_bytes()
                        page.locator('#id_photo').set_input_files([{'name': f'photo-{i}.jpg', 'mimeType': 'image/jpeg', 'buffer': data} for i in range(5)])
                        assert page.locator('.new-photo-item').count() == 5
                        page.locator('[name=cover_photo][value=new-3]').check()
                        page.get_by_role('button', name='Remove selected photo 2', exact=True).click()
                        assert page.locator('.new-photo-item').count() == 4
                        assert page.locator('[name=cover_photo]:checked').input_value() == 'new-2'
                    if path.endswith('/edit/'):
                        assert page.locator('[data-saved-photo]').count() == 5
                        page.locator('#id_photo').set_input_files(str(ROOT / 'static/images/foodloop-fresh-food.jpg'))
                        assert page.locator('#id_photo').evaluate('el=>el.validationMessage')
                        page.locator('[data-remove-photo]').last.check()
                        assert page.locator('#id_photo').evaluate('el=>el.validationMessage') == ''
                        assert page.locator('.new-photo-item').count() == 1
                    if width in (390, 1440):
                        page.add_script_tag(path=str(ROOT / 'qa/axe.min.js'))
                        audit = page.evaluate("axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                        violations = [{'id': item['id'], 'nodes': [node['target'] for node in item['nodes']],
                                       'details': [node.get('failureSummary', '') for node in item['nodes']]} for item in audit['violations']]
                        if violations:
                            failures.append({'role': role, 'path': path, 'width': width, 'violations': violations})
                        name = path.strip('/').replace('/', '-').replace('?', '-').replace('=', '-') or 'cards'
                        page.screenshot(path=str(ROOT / f'qa/marketplace-{role}-{name}-{width}.png'), full_page=True)
                print(f'{role} {path}: visual structure, controls and 320/390/820/1440px layout PASS', flush=True)
            assert not errors, errors
            context.close()
        browser.close()
    (ROOT / 'qa/marketplace-auth-results.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
    assert not failures, json.dumps(failures, indent=2)
    print('PASS: card hierarchy, real/absent photos, category colors, auth pages and WCAG A/AA automated samples.')
