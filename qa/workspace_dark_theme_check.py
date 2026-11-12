"""Render real workspace pages and verify both themes in desktop/mobile browsers."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
with TemporaryDirectory(prefix='foodloop-style-',ignore_cleanup_errors=True) as directory:
    os.environ['DJANGO_SETTINGS_MODULE']='config.test_settings'
    os.environ['FOODLOOP_SQLITE_PATH']=str(Path(directory)/'style.sqlite3')
    import django
    django.setup()
    from django.test import Client
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.utils import timezone
    from django.db import connections
    from core.models import Organisation,Membership,Listing
    call_command('migrate',verbosity=0)
    users={}
    for role,name in [('provider','Sunrise Food Market'),('recipient','Hope Community Kitchen'),('admin','FoodLoop Administration')]:
        user=User.objects.create_user('style-'+role,first_name='Lushomo',is_staff=role=='admin')
        if role!='admin':
            org=Organisation.objects.create(name=name,role=role,status='approved',pathway='human',area='Lusaka')
            Membership.objects.create(user=user,organisation=org)
            if role=='provider':donor=org
        users[role]=user
    listings=[]
    for title,area,pathway,quantity,photo in [('Fresh bread for community kitchens','Lusaka','human',50,''),('Seasonal vegetables and leafy greens','Kasama','human',32.5,'style-demo.jpg'),('Organic material for agriculture projects','Mongu','compost',98,'')]:
        listings.append(Listing.objects.create(provider=donor,name=title,area=area,quantity=quantity,pathway=pathway,condition='spoiled' if pathway=='compost' else 'fresh',deadline=timezone.now()+timedelta(days=1),address='Fictional demonstration entrance',photo=photo,safety_acknowledged=True))
    pages={}
    for role,user in users.items():
        client=Client();client.force_login(user)
        for path in ['/', '/dashboard/', f'/listings/{listings[0].pk}/', '/profile/', '/notifications/'] + (['/listings/new/'] if role=='provider' else ['/administration/'] if role=='admin' else []):
            response=client.get(path,HTTP_HOST='localhost')
            assert response.status_code==200,(role,path,response.status_code)
            pages[role,path]=response.content.decode()
    connections.close_all()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        for role in users:
            context=browser.new_context(color_scheme='light')
            def handle(route):
                path=urlparse(route.request.url).path
                if path.startswith('/static/'):
                    asset=ROOT/'static'/path.removeprefix('/static/')
                    if asset.is_file():route.fulfill(path=str(asset))
                    else:route.fulfill(status=404,body='')
                elif path.endswith('/photo/'):
                    route.fulfill(path=str(ROOT/'static/images/foodloop-fresh-food.jpg'))
                elif path=='/listings/stock/':
                    route.fulfill(json={'listings':[{'id':item.pk,'available':True,'remaining':str(item.quantity),'reserved':'0','collected':'0','status':'Available','status_key':'available'} for item in listings]})
                else:route.fulfill(body=pages.get((role,path),''),content_type='text/html')
            context.route('https://foodloop.test/**',handle)
            page=context.new_page()
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script("Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({})}})")
            for width in (390,1440):
                page.set_viewport_size({'width':width,'height':1000})
                page.goto('https://foodloop.test/')
                for theme in ('light','dark'):
                    if page.evaluate('document.documentElement.dataset.theme')!=theme:page.locator('#theme-toggle').click()
                    assert page.locator('#theme-toggle').get_attribute('aria-pressed')==str(theme=='dark').lower()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(role,width,theme)
                    assert 'hero-save-planet' in page.locator('.exchange-intro').evaluate('el=>getComputedStyle(el).backgroundImage')
                    assert page.locator('[data-listing-card]').count()==3
                    assert page.locator('.photo-placeholder-label').first.evaluate('el=>getComputedStyle(el).color')=='rgb(238, 240, 217)'
                    if theme=='dark':
                        assert page.locator('select').first.evaluate('el=>getComputedStyle(el).backgroundColor')=='rgb(22, 30, 35)'
                    if role=='provider' and width==390 and theme=='dark':
                        devtools=context.new_cdp_session(page)
                        devtools.send('DOM.enable');devtools.send('CSS.enable')
                        root=devtools.send('DOM.getDocument')['root']['nodeId']
                        node=devtools.send('DOM.querySelector',{'nodeId':root,'selector':'#food-search'})['nodeId']
                        devtools.send('CSS.forcePseudoState',{'nodeId':node,'forcedPseudoClasses':['autofill']})
                        assert page.locator('#food-search').evaluate("el=>getComputedStyle(el).getPropertyValue('-webkit-text-fill-color')")=='rgb(239, 243, 244)'
                        assert 'rgb(22, 30, 35)' in page.locator('#food-search').evaluate('el=>getComputedStyle(el).boxShadow')
                        devtools.send('CSS.forcePseudoState',{'nodeId':node,'forcedPseudoClasses':[]})
                        devtools.detach()
                        print('Browser autofill state: light text and dark inset background PASS',flush=True)
                    assert page.locator('#theme-toggle').bounding_box()['x']<page.locator('.masthead-notifications').bounding_box()['x']
                    page.screenshot(path=str(ROOT/f'qa/workspace-{role}-{theme}-{width}.png'),full_page=True)
                    if role=='recipient':page.locator('[data-listing-card]').first.screenshot(path=str(ROOT/f'qa/listing-card-{theme}-{width}.png'))
                    page.evaluate('scrollTo(0,0)')
                    print(f'{role}, {width}px, {theme}: theme toggle, hero photograph, three cards and no horizontal overflow PASS',flush=True)
                page.reload()
                assert page.evaluate('document.documentElement.dataset.theme')=='dark'
            for path in ['/dashboard/', f'/listings/{listings[0].pk}/', '/profile/', '/notifications/'] + (['/listings/new/'] if role=='provider' else ['/administration/'] if role=='admin' else []):
                page.goto('https://foodloop.test'+path)
                assert page.evaluate('document.documentElement.dataset.theme')=='dark'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if page.locator('input[type=file]').count():
                    assert page.locator('input[type=file]').first.evaluate('el=>getComputedStyle(el).backgroundColor')=='rgb(22, 30, 35)'
                white_panels=page.evaluate(r"""() => [...document.querySelectorAll('main section, main article, main .empty-state, main .request-panel, main .pickup-location-capture')].filter(el=>{const r=el.getBoundingClientRect(),c=getComputedStyle(el).backgroundColor.match(/[\d.]+/g);return r.width*r.height>8000&&c&&Number(c[0])>225&&Number(c[1])>225&&Number(c[2])>225&&(c.length<4||Number(c[3])>.8)}).map(el=>el.className)""")
                assert not white_panels,(role,path,white_panels)
                text_input=page.locator('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file])').first
                if text_input.count() and text_input.is_enabled() and not text_input.get_attribute('readonly'):
                    kind=text_input.get_attribute('type') or 'text'
                    if kind in ('text','email','number','search'):
                        text_input.fill('12' if kind=='number' else 'reader@example.invalid' if kind=='email' else 'Readable input text')
                        assert text_input.evaluate("el=>getComputedStyle(el).color")== 'rgb(239, 243, 244)'
                        assert text_input.evaluate("el=>getComputedStyle(el).getPropertyValue('-webkit-text-fill-color')")== 'rgb(239, 243, 244)'
                        assert text_input.evaluate("el=>getComputedStyle(el).caretColor")== 'rgb(239, 243, 244)'
                page.screenshot(path=str(ROOT / ('qa/workspace-'+role+'-dark-'+path.strip('/').replace('/','-')+'.png')),full_page=True)
            page.goto('https://foodloop.test/')
            page.set_viewport_size({'width':320,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(role,'320px')
            assert page.locator('#theme-toggle').is_visible()
            assert not errors,errors
            print(role+': theme persists on reload, dashboard and details; 320px header and JavaScript errors PASS',flush=True)
            context.close()
        context=browser.new_context(color_scheme='dark')
        context.route('https://foodloop.test/**',handle)
        page=context.new_page();page.goto('https://foodloop.test/')
        assert page.evaluate('document.documentElement.dataset.theme')=='dark'
        page.locator('#theme-toggle').click()
        page.emulate_media(color_scheme='dark')
        assert page.evaluate('document.documentElement.dataset.theme')=='light'
        other=context.new_page();other.goto('https://foodloop.test/')
        assert other.evaluate('document.documentElement.dataset.theme')=='light'
        page.locator('#theme-toggle').focus();page.keyboard.press('Space')
        other.wait_for_function("document.documentElement.dataset.theme==='dark'")
        print('System preference, explicit override, keyboard toggle and cross-tab synchronization PASS',flush=True)
        context.close();browser.close()
