"""Read-only automated production accessibility and layout sampling."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = 'https://foodloop-zambia.onrender.com'
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    for role in os.environ.get('FOODLOOP_QA_ROLES', 'anonymous,demo_donor,demo_beneficiary').split(','):
        context = browser.new_context()
        # Do not request public map tiles through automated browsing.
        context.route('**/*tile.openstreetmap.org/**', lambda route: route.abort())
        if os.environ.get('FOODLOOP_QA_LOCAL_CSS') == '1':
            import re
            context.route(re.compile(r'/static/workspace-polish[^/]*\.css(?:\?.*)?$'),
                          lambda route: route.fulfill(path=str(ROOT.parent / 'static/workspace-polish.css'),
                                                       content_type='text/css'))
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/login/', wait_until='domcontentloaded', timeout=60000)
        if role != 'anonymous':
            page.locator('#id_username').fill(role)
            page.locator('#id_password').fill(os.environ.get('FOODLOOP_QA_PASSWORD', 'Try@2026'))
            page.locator('form button[type="submit"], form button').first.click()
            page.wait_for_url(lambda url: '/login/' not in url, timeout=60000)
        paths = ['/login/'] if role == 'anonymous' else ['/dashboard/', '/notifications/', '/profile/']
        if role == 'demo_donor':
            paths.append('/listings/new/')
        if os.environ.get('FOODLOOP_QA_PATHS'):
            paths = os.environ['FOODLOOP_QA_PATHS'].split(',')
        for path in paths:
            response = page.goto(BASE + path, wait_until='domcontentloaded', timeout=60000)
            assert response.status == 200, (role, path, response.status)
            for theme in ('light', 'dark'):
                page.evaluate('(t)=>document.documentElement.dataset.theme=t', theme)
                for width in (390, 1440):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.evaluate('document.fonts.ready')
                    page.add_script_tag(path=str(ROOT / 'axe.min.js'))
                    audit = page.evaluate("axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                    violations = [{'id': v['id'], 'impact': v['impact'],
                                   'targets': [n['target'] for n in v['nodes']],
                                   'details': [n.get('failureSummary', '') for n in v['nodes']]}
                                  for v in audit['violations']]
                    overflow = page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                    results.append({'role': role, 'path': path, 'theme': theme,
                                    'width': width, 'overflow': overflow, 'violations': violations})
            print(f'{role} {path}: browser audit complete', flush=True)
        assert not errors, errors
        context.close()
    browser.close()
suffix = '-local-css' if os.environ.get('FOODLOOP_QA_LOCAL_CSS') == '1' else ''
if os.environ.get('FOODLOOP_QA_PATHS') or os.environ.get('FOODLOOP_QA_ROLES'):
    suffix += '-focused'
ROOT.joinpath('hosted-accessibility' + suffix + '-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
failures = [r for r in results if r['violations'] or r['overflow']]
print(json.dumps({'checks': len(results), 'failed_samples': len(failures),
                  'rule_ids': sorted({v['id'] for r in failures for v in r['violations']})}))
raise SystemExit(1 if failures else 0)
