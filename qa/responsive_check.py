"""Run against the local demo server with Playwright and installed Microsoft Edge."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
WIDTHS = [320, 375, 390, 480, 600, 768, 820, 1024, 1280, 1440, 1920]

def inspect(page, name, width):
    page.evaluate('document.fonts.ready')
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(100)
    result = page.evaluate('''() => {
      const root = document.documentElement;
      const visible = [...document.querySelectorAll('body *')].filter(el => {
        const r = el.getBoundingClientRect();
        return el.checkVisibility() && r.width && r.height && getComputedStyle(el).visibility !== 'hidden' && !el.closest('.svg-defs');
      });
      const overflow = visible.filter(el => {
        const r = el.getBoundingClientRect();
        return r.right > innerWidth + 1 || r.left < -1;
      }).map(el => ({tag:el.tagName, class:el.className.baseVal ?? el.className, text:el.textContent.trim().slice(0,60)}));
      const families = [...new Set(visible.filter(el => el.textContent.trim() && !['svg','path','use'].includes(el.tagName)).map(el => getComputedStyle(el).fontFamily))];
      return {viewport:innerWidth, document:root.scrollWidth, overflow, families, fontLoaded:document.fonts.check('16px Inter')};
    }''')
    result.update(page=name, width=width)
    assert result['document'] <= width, json.dumps(result)
    assert not result['overflow'], json.dumps(result)
    assert result['fontLoaded'], 'Inter did not load'
    assert all('Inter' in family for family in result['families']), json.dumps(result)
    return result

with sync_playwright() as p:
    engine = os.environ.get('FOODLOOP_BROWSER', 'edge')
    browser = p.chromium.launch(channel='msedge', headless=True) if engine == 'edge' else getattr(p, engine).launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    results = []
    page.goto('http://127.0.0.1:8000/login/')
    for width in WIDTHS:
        page.set_viewport_size({'width': width, 'height': 1000})
        results.append(inspect(page, 'login', width))
        if width in [390, 820, 1440]: page.screenshot(path=str(ROOT/f'{engine}-login-{width}.png'), full_page=True)
    page.get_by_label('Username', exact=True).fill('provider')
    page.get_by_label('Password', exact=True).fill('Try@2026')
    page.get_by_role('button', name='Enter your workspace').click()
    page.wait_for_url('http://127.0.0.1:8000/')
    for path, name in [('/', 'dashboard'), ('/listings/new/', 'upload'), ('/listings/1/', 'detail'), ('/notifications/', 'notifications'), ('/impact/', 'impact'), ('/profile/', 'profile'), ('/about/terms/', 'terms'), ('/about/privacy/', 'privacy')]:
        page.goto('http://127.0.0.1:8000'+path)
        for width in WIDTHS:
            page.set_viewport_size({'width': width, 'height': 1000})
            results.append(inspect(page, name, width))
            if name == 'dashboard' and width < 1024:
                page.locator('.mobile-menu summary').click()
                results.append(inspect(page, 'menu-open', width))
                page.get_by_role('navigation', name='Mobile navigation').get_by_text('Food listings', exact=True).click()
                assert not page.locator('.mobile-menu').evaluate('(el) => el.open')
            page.evaluate('window.scrollTo(0, 0)')
            page.wait_for_timeout(150)
            if width in [390, 820, 1440]: page.screenshot(path=str(ROOT/f'{engine}-{name}-{width}.png'), full_page=True)
    page.goto('http://127.0.0.1:8000/login/')
    page.locator('#id_username').fill('admin')
    page.locator('#id_password').fill('Try@2026')
    page.get_by_role('button', name='Enter your workspace').click()
    page.wait_for_url('http://127.0.0.1:8000/')
    page.goto('http://127.0.0.1:8000/administration/')
    for width in WIDTHS:
        page.set_viewport_size({'width': width, 'height': 1000})
        results.append(inspect(page, 'administration', width))
        if width < 1024:
            page.locator('.mobile-menu summary').click()
            results.append(inspect(page, 'admin-menu-open', width))
            page.keyboard.press('Escape')
            assert not page.locator('.mobile-menu').evaluate('(el) => el.open')
    assert not errors, errors
    (ROOT/f'responsive-{engine}-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'PASS: {len(results)} {engine} layout checks; no horizontal overflow; Inter loaded throughout; mobile menu works.')
    browser.close()
