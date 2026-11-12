"""Check mobile push setup controls with browser push APIs simulated."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
with TemporaryDirectory(prefix='foodloop-push-browser-') as temp:
    os.environ['DJANGO_SETTINGS_MODULE']='config.test_settings'
    os.environ['FOODLOOP_SQLITE_PATH']=str(Path(temp)/'browser.sqlite3')
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from django.test import Client, override_settings
    from django.db import connections
    call_command('migrate',verbosity=0)
    user=User.objects.create_user('mobile-notification-demo',is_staff=True)
    client=Client();client.force_login(user)
    with override_settings(WEB_PUSH_ENABLED=True,WEB_PUSH_PUBLIC_KEY='B'+('A'*86)):
        html=client.get('/notifications/', HTTP_HOST='localhost').content.decode()
    connections.close_all()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script('''
          let subscription=null;
          const manager={getSubscription:async()=>subscription,subscribe:async()=>{
            subscription={toJSON:()=>({endpoint:'https://push.example.invalid/demo',keys:{p256dh:'key',auth:'auth'}}),unsubscribe:async()=>{subscription=null;return true;}};
            return subscription;
          }};
          Object.defineProperty(window,'PushManager',{value:function(){}});
          Object.defineProperty(window,'Notification',{value:Object.assign(function(){},{requestPermission:async()=>'granted'})});
          Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({pushManager:manager}),ready:Promise.resolve({pushManager:manager})}});
        ''')
        def handle(route):
            path=urlparse(route.request.url).path
            if path.startswith('/notifications/push/'):
                requests.append(path);route.fulfill(json={'queued':True,'saved':True,'removed':True})
            elif path=='/notifications/':route.fulfill(body=html,content_type='text/html')
            elif path.startswith('/static/'):
                file=ROOT/'static'/path.removeprefix('/static/')
                if file.is_file():route.fulfill(path=str(file))
                else:route.fulfill(status=404,body='')
            else:route.fulfill(body='')
        page.route('https://foodloop.test/**',handle)
        page.goto('https://foodloop.test/notifications/')
        page.locator('#push-enable').click()
        page.wait_for_function("document.querySelector('#push-status').textContent.includes('enabled')")
        assert page.locator('#push-test').count() == 0
        assert '/notifications/push/subscribe/' in requests and '/notifications/push/test/' not in requests
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(ROOT/'qa/phone-notification-controls.png'),full_page=True)
        page.locator('#push-enable').click()
        page.wait_for_function("document.querySelector('#push-status').textContent.includes('turned off')")
        assert '/notifications/push/unsubscribe/' in requests
        assert not errors,errors
        browser.close()
        print('390px phone alerts: enable, subscribe and disable work without a test-alert button; layout PASS; browser APIs simulated.')
