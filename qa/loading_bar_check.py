"""Exercise loading-bar placement and events in desktop and mobile viewports."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page()
    page.route('https://foodloop.test/**', lambda route: route.fulfill(body='''
        <html><body style="margin:0"><div class="page-loading" role="progressbar" aria-label="Loading page" aria-hidden="true"></div>
        <header style="height:72px;position:sticky;top:0;z-index:100">FoodLoop</header>
        <a id="next" href="/next">Next page</a><a id="hash" href="#content">Section</a>
        <form><button>Submit</button></form><main id="content" style="height:2000px"></main></body></html>
    ''', content_type='text/html'))
    page.goto('https://foodloop.test/')
    page.add_style_tag(path=str(root / 'static/page-loading.css'))
    page.add_script_tag(path=str(root / 'static/page-loading.js'))
    for width in (375, 768, 1440):
        page.set_viewport_size({'width': width, 'height': 900})
        page.evaluate("window.dispatchEvent(new Event('pageshow'))")
        assert not page.locator('.page-loading').evaluate("el => el.classList.contains('is-active')")
        page.evaluate('''() => {
            window.addEventListener('click', e => e.preventDefault(), {once:true});
            document.querySelector('#next').click();
        }''')
        bar = page.locator('.page-loading')
        assert bar.evaluate("el => el.classList.contains('is-active')")
        rect = bar.bounding_box()
        assert rect['y'] == 0 and rect['x'] == 0 and rect['width'] == width
        assert page.evaluate("document.elementFromPoint(10,1).tagName") == 'HEADER'
        page.evaluate("scrollTo(0,500)")
        assert bar.bounding_box()['y'] == 0
        page.evaluate("window.dispatchEvent(new Event('pageshow'))")
        page.locator('#hash').click()
        assert not bar.evaluate("el => el.classList.contains('is-active')")
        page.evaluate("document.querySelector('form').dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true}))")
        assert bar.evaluate("el => el.classList.contains('is-active')")
        page.evaluate("window.dispatchEvent(new Event('pageshow')); scrollTo(0,0)")
        print(f'{width}px: fixed top position, scroll, navigation, forms, anchors and history reset OK')
    page.emulate_media(reduced_motion='reduce')
    page.evaluate("document.querySelector('form').dispatchEvent(new SubmitEvent('submit',{bubbles:true}))")
    assert page.locator('.page-loading').evaluate("el => getComputedStyle(el,'::before').animationName") == 'none'
    print('Reduced-motion mode OK')
    browser.close()
