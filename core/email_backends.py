"""HTTPS email delivery for hosts that block outbound SMTP."""
import requests
import base64
import time
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                if not settings.RESEND_API_KEY:
                    raise RuntimeError('RESEND_API_KEY is not configured.')
                payload = {'from': message.from_email, 'to': message.to, 'subject': message.subject, 'text': message.body}
                for alternative in getattr(message, 'alternatives', []):
                    if alternative[1] == 'text/html':
                        payload['html'] = alternative[0]
                if message.cc: payload['cc'] = message.cc
                if message.bcc: payload['bcc'] = message.bcc
                if message.reply_to: payload['reply_to'] = message.reply_to
                headers = {'Authorization': 'Bearer ' + settings.RESEND_API_KEY}
                message_id = message.extra_headers.get('Message-ID')
                if message_id:
                    headers['Idempotency-Key'] = message_id.strip('<>')
                response = requests.post('https://api.resend.com/emails', headers=headers, json=payload, timeout=(4, 10))
                if not response.ok:
                    raise RuntimeError(f'Email provider rejected the request (HTTP {response.status_code}).')
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise RuntimeError('HTTPS email delivery failed. Check the provider configuration.') from None
        return sent


class GmailAPIEmailBackend(BaseEmailBackend):
    """Send with the Gmail owner's OAuth consent, over HTTPS rather than SMTP."""

    def _access_token(self):
        if getattr(self, '_token_expires', 0) > time.monotonic():
            return self._token
        credentials = (settings.GMAIL_CLIENT_ID, settings.GMAIL_CLIENT_SECRET, settings.GMAIL_REFRESH_TOKEN)
        if not all(credentials):
            raise RuntimeError('Gmail authorization is not configured.')
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': credentials[0], 'client_secret': credentials[1],
            'refresh_token': credentials[2], 'grant_type': 'refresh_token'}, timeout=(4, 10))
        response.raise_for_status()
        token = response.json()
        self._token = token['access_token']
        self._token_expires = time.monotonic() + max(0, int(token.get('expires_in', 3600)) - 60)
        return self._token

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                mime = message.message()
                # Django omits Bcc from its MIME output for SMTP. Gmail's API
                # derives envelope recipients from headers, including Bcc.
                if message.bcc:
                    mime['Bcc'] = ', '.join(message.bcc)
                raw = base64.urlsafe_b64encode(mime.as_bytes(linesep='\r\n')).decode('ascii')
                response = requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                    headers={'Authorization': 'Bearer ' + self._access_token()},
                    json={'raw': raw}, timeout=(4, 10))
                if response.status_code == 401:
                    self._token_expires = 0
                    response = requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                        headers={'Authorization': 'Bearer ' + self._access_token()},
                        json={'raw': raw}, timeout=(4, 10))
                response.raise_for_status()
                if not response.json().get('id'):
                    raise RuntimeError('Gmail did not accept the message.')
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise RuntimeError('Gmail HTTPS delivery failed. Reconnect the sender or check Gmail API access.') from None
        return sent
