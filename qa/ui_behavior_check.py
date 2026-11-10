from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
state={'id':1,'available':True,'remaining':'10','reserved':'0','collected':'0','status':'Available','status_key':'available'}
styles=''.join(f'<link rel="stylesheet" href="/static/{name}">' for name in ('responsive.css','workspace.css','premium.css'))
header='<header class="masthead"><div class="masthead-inner"><a class="brand" href="/">FoodLoop</a><button>Menu</button></div></header>'
card='<div data-stock-feed data-stock-endpoint="/listings/stock/" data-stock-donor="0"><p data-stock-message role="status" hidden></p><span class="heading-count">1</span><div class="cards"><a data-listing-card data-listing-id="1"><span data-stock-remaining>10</span><span data-stock-status>Available</span></a></div></div>'
detail='<div data-stock-detail data-listing-id="1" data-stock-endpoint="/listings/stock/"><span data-stock-remaining>10</span><span data-stock-reserved>0</span><span data-stock-collected>0</span></div><p data-stock-message hidden></p><span data-stock-status>Available</span><section class="request-panel"><form><input id="id_quantity" type="number" max="10"><button type="button">Request collection</button></form></section>'
footer='<footer class="site-footer"><div class="footer-column"><button id="install-app" type="button">Install app</button><p id="install-status" hidden></p></div></footer>'
scripts=''.join(f'<script src="/static/{name}"></script>' for name in ('landing-nav.js','stock-updates.js','pwa.js'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({})}})")
    def handle(route):
        path=urlparse(route.request.url).path
        if path.startswith('/static/'):
            asset=ROOT/'static'/path.removeprefix('/static/')
            if asset.is_file():route.fulfill(path=str(asset))
            else:route.fulfill(status=404,body='')
        elif path=='/listings/stock/':route.fulfill(json={'listings':[dict(state)]})
        else:route.fulfill(body='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'+styles+'</head><body class="app">'+header+'<main style="min-height:3000px">'+(detail if path=='/detail/' else card)+'</main>'+footer+scripts+'</body></html>',content_type='text/html')
    page.route('https://foodloop.test/**',handle)
    for width in (390,1440):
        page.set_viewport_size({'width':width,'height':900})
        page.goto('https://foodloop.test/')
        offset=page.locator('main').evaluate('el=>el.offsetTop')
        page.evaluate('scrollTo(0,500)')
        page.wait_for_function("document.querySelector('.masthead').classList.contains('is-hidden')")
        page.evaluate('scrollTo(0,400)')
        page.wait_for_function("document.querySelector('.masthead').classList.contains('is-revealed')")
        page.wait_for_function("Math.abs(document.querySelector('.masthead').getBoundingClientRect().y)<1")
        assert page.locator('main').evaluate('el=>el.offsetTop')==offset
        page.evaluate('scrollTo(0,0)')
        page.wait_for_function("!document.querySelector('.masthead').classList.contains('is-hidden')")
        page.locator('#install-app').click()
        assert 'Chrome or Edge' in page.locator('#install-status').text_content()
        page.evaluate("window.promptCalls=0;const e=new Event('beforeinstallprompt',{cancelable:true});e.prompt=async()=>{window.promptCalls++};e.userChoice=Promise.resolve({outcome:'accepted'});window.dispatchEvent(e)")
        page.locator('#install-app').click()
        page.wait_for_function("document.querySelector('#install-status').textContent.includes('Installation requested')")
        assert page.evaluate('window.promptCalls')==1
        page.evaluate("window.dispatchEvent(new Event('appinstalled'))")
        assert page.locator('#install-app').is_disabled()
        print(f'{width}px: header hides/reveals without layout jumps; install fallback, native prompt and installed state PASS',flush=True)
    state.update(available=False,remaining='0',reserved='10',collected='0',status='Fully reserved',status_key='allocated')
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_function("document.querySelectorAll('[data-listing-card]').length===0")
    state.update(available=True,remaining='10',reserved='0',collected='0',status='Available',status_key='available')
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_function("document.querySelectorAll('[data-listing-card]').length===1")
    page.goto('https://foodloop.test/detail/')
    state.update(available=False,remaining='0',reserved='0',collected='10',status='Exhausted',status_key='exhausted')
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_function("document.querySelector('[data-stock-status]').textContent==='Exhausted'")
    assert page.locator('.request-panel button').is_disabled()
    assert page.locator('[data-stock-collected]').text_content()=='10'
    assert 'exhausted' in page.locator('[data-stock-message]').text_content()
    print('Live stock UI: reserved stock leaves feed, cancellations restore card, exhaustion disables requests and updates collected total PASS',flush=True)
    assert not errors,errors
    browser.close()
