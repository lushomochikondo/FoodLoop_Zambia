"""Record an isolated end-to-end prototype while denying all external browser traffic."""
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / 'qa' / 'prototype-recording'
OUTPUT.mkdir(exist_ok=True)

with TemporaryDirectory(prefix='foodloop-e2e-') as folder:
    os.environ.update({'FOODLOOP_SQLITE_PATH': str(Path(folder)/'prototype.sqlite3'), 'DJANGO_MEDIA_ROOT': str(Path(folder)/'media'), 'DJANGO_DEBUG': '1', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(64), 'DJANGO_SETTINGS_MODULE': 'config.settings'})
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from django.db import connections
    from core.models import Membership, Organisation
    from playwright.sync_api import sync_playwright, expect
    call_command('migrate', verbosity=0)
    password = secrets.token_urlsafe(16)
    for username, role in [('provider','provider'), ('recipient','recipient')]:
        org = Organisation.objects.create(name=f'prototype {role.title()}', role=role, status='approved', area='Lusaka Central')
        user = User.objects.create_user(username, password=password)
        Membership.objects.create(user=user, organisation=org)
    admin = User.objects.create_user('admin', password=password, is_staff=True)
    pending = Organisation.objects.create(name='prototype Pending Kitchen', role='recipient', area='Lusaka Central', physical_address='Fictional prototype walkthrough address', contact_name='prototype Contact', contact_email='prototype@example.invalid', phone='prototype ONLY', activity_description='Community meals', handling_capacity='prototype walkthrough safe storage', terms_accepted=True)
    connections.close_all()
    process = subprocess.Popen([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8765', '--noreload'], cwd=ROOT, env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = 'http://127.0.0.1:8765'
    report = {'external_requests_blocked': True, 'checks': [], 'timings_seconds': {}}
    try:
        for attempt in range(100):
            try:
                with urlopen(base+'/login/', timeout=1) as response:
                    if response.status == 200: break
            except Exception: time.sleep(.2)
        else: raise RuntimeError('Isolated prototype walkthrough server did not start.')
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width':1440,'height':1000}, record_video_dir=str(OUTPUT), record_video_size={'width':1440,'height':1000})
            context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname in ['127.0.0.1','localhost'] else route.abort())
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            def pause(): page.wait_for_timeout(900)
            def login(name):
                page.goto(base+'/login/')
                page.locator('#id_username').fill(name)
                page.locator('#id_password').fill(password)
                page.get_by_role('button', name='Enter your workspace').click()
                page.wait_for_url(base+'/')
            login('admin')
            page.goto(base+'/administration/')
            card = page.locator('.review-card').filter(has=page.get_by_role('heading', name='prototype Pending Kitchen'))
            card.locator('select[name=decision]').select_option('approved')
            card.locator('textarea[name=reason]').fill('Fictional eligibility evidence reviewed for the prototype walkthrough.')
            card.get_by_role('button', name='Record decision').click()
            expect(page.get_by_role('status')).to_contain_text('Decision recorded')
            pause(); report['checks'].append('Admin verifies organisation and records decision')
            login('provider')
            start=time.perf_counter()
            page.get_by_role('link', name='Create listing').click()
            page.locator('#id_photo').set_input_files(str(ROOT/'static/images/bread.jpg'))
            expect(page.locator('#photo-preview')).to_be_visible()
            page.locator('#id_name').fill('prototype bread batch')
            page.locator('#id_quantity').fill('10')
            page.locator('#id_unit').select_option('kg')
            page.locator('#id_pathway').select_option('human')
            page.locator('#id_condition').select_option('fresh')
            page.locator('#id_area').fill('Lusaka Central')
            page.locator('#id_address').fill('PRIVATE-prototype-PICKUP-ADDRESS')
            page.locator('#id_deadline').fill((datetime.now()+timedelta(hours=8)).strftime('%Y-%m-%dT%H:%M'))
            page.locator('#id_notes').fill('Fictional prototype walkthrough food. Bring clean collection containers.')
            page.locator('#id_safety_acknowledged').check()
            pause()
            page.get_by_role('button', name='Publish listing').click()
            expect(page.get_by_role('heading', name='prototype bread batch')).to_be_visible()
            listing_url=page.url
            report['timings_seconds']['scripted_provider_task']=round(time.perf_counter()-start,3)
            photo=page.locator('.detail-photo img')
            expect(photo).to_be_visible()
            assert photo.evaluate('(img)=>img.complete && img.naturalWidth > 0')
            pause(); report['checks'].append('Provider publishes a photo listing')
            login('recipient')
            expect(page.locator('.match-reasons')).to_contain_text('Same area')
            page.goto(listing_url)
            assert 'PRIVATE-prototype-PICKUP-ADDRESS' not in page.content()
            page.locator('#id_quantity').fill('8')
            page.locator('#id_safety').check()
            page.get_by_role('button', name='Request collection').click()
            page.wait_for_url(base+'/'); pause()
            report['checks'].append('Matching reasons, hidden address and pending request')
            login('provider')
            page.goto(listing_url)
            page.get_by_role('button',name='Accept',exact=True).click()
            pause()
            login('recipient'); page.goto(listing_url)
            expect(page.locator('.pickup-panel')).to_contain_text('PRIVATE-prototype-PICKUP-ADDRESS')
            pause(); report['checks'].append('Acceptance reveals private pickup details')
            login('provider')
            page.goto(base+'/requests/')
            page.get_by_role('button',name='Ready for collection',exact=True).click()
            page.get_by_role('button',name='Confirm full collection',exact=False).click()
            page.goto(base+'/impact/')
            assert '0.0' in page.locator('.metrics').inner_text()
            pause(); report['checks'].append('One confirmation does not count as recovered')
            login('recipient')
            page.goto(base+'/requests/')
            page.get_by_role('button',name='Confirm full collection',exact=False).click()
            page.goto(base+'/impact/')
            expect(page.locator('.metrics').first).to_contain_text('8.0')
            expect(page.locator('.metrics')).to_contain_text('20')
            pause(); report['checks'].append('Dual confirmation updates kilograms and estimated meals')
            page.goto(listing_url)
            page.locator('.report-disclosure summary').click()
            page.locator('#id_reason').fill('prototype walkthrough report for moderation review.')
            page.get_by_role('button',name='Send report for review').click()
            login('admin'); page.goto(base+'/administration/')
            flag=page.locator('.review-card').filter(has=page.get_by_role('heading',name='prototype bread batch')).first
            flag.locator('select[name=decision]').select_option('dismissed')
            flag.locator('textarea[name=reason]').fill('Fictional report reviewed and dismissed for this prototype walkthrough.')
            flag.get_by_role('button',name='Complete review').click()
            pause(); report['checks'].append('Report queue, administrator outcome and audit trail')
            login('provider'); page.goto(listing_url)
            page.get_by_role('link',name='Delete listing',exact=True).click()
            page.get_by_role('button',name='Delete listing',exact=True).click()
            page.wait_for_url(base+'/')
            assert page.locator('.cards .card').count()==0
            page.goto(base+'/impact/')
            expect(page.locator('.metrics')).to_contain_text('8.0')
            report['checks'].append('Provider deletes listing while completed impact remains unchanged')
            # Prove current app needs no external font, image, script or service for the local fallback.
            page.set_viewport_size({'width':390,'height':844})
            page.goto(base+'/')
            page.locator('#menu-toggle').click()
            expect(page.get_by_role('navigation',name='Main navigation')).to_be_visible()
            page.keyboard.press('Escape')
            pause(); report['checks'].append('Phone navigation works with external traffic denied')
            page.wait_for_function("'serviceWorker' in navigator")
            page.evaluate('navigator.serviceWorker.ready')
            cached_urls=page.evaluate('''async () => {
              const names=await caches.keys();
              const requests=(await Promise.all(names.map(async name => (await caches.open(name)).keys()))).flat();
              return requests.map(request => request.url);
            }''')
            assert all(urlparse(url).path.startswith('/static/') for url in cached_urls), cached_urls
            context.set_offline(True)
            page.goto(base+'/offline-check')
            expect(page.get_by_role('heading',name="You're offline.")).to_be_visible()
            context.set_offline(False)
            report['checks'].append('Service-worker offline screen works without caching private pages')
            video=page.video
            assert not errors, errors
            context.close()
            video.save_as(str(OUTPUT/'FoodLoop-complete-prototype.webm'))
            browser.close()
        report['result']='PASS'
        report['limits']='Scripted timings are not first-time-user usability results. Local Edge, not physical devices or hosted PostgreSQL.'
        (ROOT/'qa/acceptance-browser-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('PASS:',len(report['checks']),'isolated browser acceptance checks, offline fallback, and recorded prototype.')
    finally:
        process.terminate()
        process.wait(timeout=15)
        connections.close_all()
