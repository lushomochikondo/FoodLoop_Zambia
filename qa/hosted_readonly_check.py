"""Production smoke checks using demo logins; never submit business actions."""
import json
import os
import re
from pathlib import Path

import requests

BASE = 'https://foodloop-zambia.onrender.com'
results = []


def check(session, path, expected=200):
    response = session.get(BASE + path, timeout=60)
    assert response.status_code == expected, (path, response.status_code)
    if expected == 200:
        assert '/login/' not in response.url or path == '/login/', path
    results.append({'path': path, 'status': response.status_code,
                    'elapsed_ms': round(response.elapsed.total_seconds() * 1000)})
    return response


public = requests.Session()
for path in ('/', '/login/', '/signup/', '/faq/', '/contact/',
             '/service-worker.js', '/static/manifest.webmanifest'):
    check(public, path)
assert public.get(BASE.replace('https:', 'http:') + '/login/',
                  allow_redirects=False, timeout=60).status_code in (301, 302, 307, 308)

for username in ('demo_donor', 'demo_beneficiary'):
    session = requests.Session()
    login = check(session, '/login/')
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login.text).group(1)
    response = session.post(BASE + '/login/', data={
        'username': username, 'password': os.environ.get('FOODLOOP_QA_PASSWORD', 'Try@2026'),
        'csrfmiddlewaretoken': token, 'next': '/dashboard/'},
        headers={'Referer': BASE + '/login/'}, timeout=60)
    assert response.status_code == 200 and '/login/' not in response.url, username
    for path in ('/', '/dashboard/', '/requests/', '/profile/', '/notifications/', '/impact/'):
        response = check(session, path)
        assert response.headers.get('Strict-Transport-Security'), path
        if path == '/notifications/':
            assert 'id="push-enable"' in response.text, 'Production push controls absent'
    stock = check(session, '/listings/stock/?ids=3,4,5').json()['listings']
    assert len(stock) == 3, (username, stock)
    assert all(float(item['remaining']) >= 0 for item in stock)
    for item in stock:
        check(session, '/listings/' + str(item['id']) + '/')
    check(session, '/administration/', 403)
    check(session, '/listings/new/', 200 if username == 'demo_donor' else 403)
    print(username + ': login, pages, stock API, listing details, push controls and permissions PASS', flush=True)

Path(__file__).with_name('hosted-readonly-results.json').write_text(
    json.dumps(results, indent=2), encoding='utf-8')
print(f'PASS: {len(results)} live HTTP checks; no listings, requests or account details changed.')
