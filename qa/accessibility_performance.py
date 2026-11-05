"""Local browser accessibility, cold/warm timing and PWA checks; no human usability claim."""
import json
import os
import statistics
from tempfile import TemporaryDirectory
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
profile_dir=TemporaryDirectory(prefix='foodloop-pwa-browser-')
with sync_playwright() as p:
    browser=p.chromium.launch_persistent_context(profile_dir.name,channel='msedge',headless=True,viewport={'width':1440,'height':1000})
    page=browser.new_page()
    results=[]
    for role in [None,'provider','recipient','admin']:
        if role:
            page.goto('http://127.0.0.1:8000/login/')
            page.locator('#id_username').fill(role)
            page.locator('#id_password').fill(os.environ.get('FOODLOOP_DEMO_PASSWORD','Try@2026'))
            page.get_by_role('button',name='Enter your workspace').click()
            page.wait_for_url('http://127.0.0.1:8000/')
        paths=['/login/'] if role is None else ['/', '/impact/', '/profile/', '/notifications/']
        if role=='provider': paths+=['/listings/new/','/listings/1/']
        if role=='admin': paths+=['/administration/']
        for path in paths:
            for width in [390,820,1440]:
                page.set_viewport_size({'width':width,'height':1000})
                response=page.goto('http://127.0.0.1:8000'+path,wait_until='networkidle')
                assert response.status==200,(role,path,response.status)
                page.evaluate('document.fonts.ready')
                page.add_script_tag(path=str(ROOT/'axe.min.js'))
                audit=page.evaluate("axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                violations=[{'id':v['id'],'impact':v['impact'],'description':v['description'],'nodes':[n['target'] for n in v['nodes']]} for v in audit['violations']]
                timing=page.evaluate('performance.getEntriesByType("navigation")[0].loadEventEnd')
                result={'role':role or 'anonymous','path':path,'width':width,'load_ms':round(timing,1),'violations':violations}
                results.append(result)
    page.goto('http://127.0.0.1:8000/login/')
    page.wait_for_function("'serviceWorker' in navigator")
    page.evaluate('navigator.serviceWorker.ready')
    cdp=page.context.new_cdp_session(page)
    manifest=cdp.send('Page.getAppManifest')
    assert not manifest.get('errors'),manifest
    install=cdp.send('Page.getInstallabilityErrors')
    (ROOT/'accessibility-performance-results.json').write_text(json.dumps({'pages':results,'pwa':install,'manifest_errors':manifest.get('errors',[])},indent=2),encoding='utf-8')
    failures=[r for r in results if r['violations']]
    assert not failures, sorted({(v['id'],str(v['nodes'])) for r in failures for v in r['violations']})
    assert not install.get('installabilityErrors'),install
    timings=[r['load_ms'] for r in results]
    print(f'PASS: {len(results)} local WCAG A/AA automated page checks; median load {statistics.median(timings):.0f} ms, maximum {max(timings):.0f} ms; PWA manifest/installability checks pass.')
    browser.close()
profile_dir.cleanup()
