"""HTTPS email delivery for hosts that block outbound SMTP."""
import requests
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
