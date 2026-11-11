"""Authorize a Desktop OAuth client locally; save tokens without printing them."""
import argparse
import base64
import hashlib
import hmac
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import set_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-file', type=Path, required=True)
    parser.add_argument('--sender', required=True, help='The Gmail address you will authorize.')
    args = parser.parse_args()
    client = json.loads(args.client_file.read_text(encoding='utf-8')).get('installed')
    if not client or not client.get('client_id') or not client.get('client_secret'):
        parser.error('Choose a downloaded Google Desktop OAuth client JSON file.')
    if '@' not in args.sender or any(c in args.sender for c in '\r\n'):
        parser.error('Choose a valid sender email address.')
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth codes must never appear in access logs.

        def do_GET(self):
            parsed = urlparse(self.path)
            values = parse_qs(parsed.query)
            valid = parsed.path == '/callback' and hmac.compare_digest(values.get('state', [''])[0], state)
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid authorization callback.')
                return
            result['code'] = values.get('code', [''])[0]
            result['denied'] = bool(values.get('error'))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(b'You can close this tab and return to the FoodLoop setup terminal.')

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/callback'
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': client['client_id'], 'redirect_uri': redirect,
            'response_type': 'code', 'scope': 'https://www.googleapis.com/auth/gmail.send',
            'access_type': 'offline', 'prompt': 'consent', 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256',
            'login_hint': args.sender})
        print('Open this Google authorization link in your browser (valid for 10 minutes):', flush=True)
        print(url, flush=True)
        deadline = time.monotonic() + 600
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result.get('code') or result.get('denied'):
        raise SystemExit('Gmail authorization was not completed. No credentials were saved.')
    try:
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': client['client_id'], 'client_secret': client['client_secret'],
            'code': result['code'], 'grant_type': 'authorization_code',
            'redirect_uri': redirect, 'code_verifier': verifier}, timeout=(4, 15))
        response.raise_for_status()
        token = response.json()['refresh_token']
    except Exception:
        raise SystemExit('Google did not issue offline authorization. Recheck the OAuth client and consent setup.') from None
    destination = Path(__file__).resolve().parent.parent / '.env.gmail-api'
    destination.touch(mode=0o600, exist_ok=True)
    for key, value in {
        'GMAIL_CLIENT_ID': client['client_id'], 'GMAIL_CLIENT_SECRET': client['client_secret'],
        'GMAIL_REFRESH_TOKEN': token, 'DEFAULT_FROM_EMAIL': args.sender,
        'EMAIL_BACKEND': 'core.email_backends.GmailAPIEmailBackend',
        'EMAIL_NOTIFICATIONS_ENABLED': '1',
    }.items():
        set_key(str(destination), key, value)
    print('Gmail authorization saved to .env.gmail-api (ignored by Git). No email was sent.')
    print('The Gmail sender must match the Google account you authorized. Keep this file private.')


if __name__ == '__main__':
    main()
