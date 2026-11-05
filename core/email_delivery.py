"""Claim queued emails briefly in the database; perform SMTP outside transactions."""
import uuid
from datetime import timedelta
from email.utils import parseaddr
from urllib.parse import urlparse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import connection, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from .models import EmailPreferences, Notification

def build_notification_email(note):
    base = settings.PUBLIC_APP_URL.rstrip('/')
    valid_base = urlparse(base).scheme == 'https' or (settings.DEBUG and urlparse(base).scheme == 'http')
    url = base + (f'/listings/{note.listing_id}/' if note.listing_id else '/notifications/') if valid_base else ''
    context = {'name': note.user.first_name or note.user.username, 'message': note.message, 'url': url, 'preferences_url': base+'/profile/' if valid_base else '', 'created': timezone.localtime(note.created)}
    subject = 'FoodLoop: ' + (' '.join(note.listing.name.split())[:90] if note.listing_id else 'Your account update')
    domain = parseaddr(settings.DEFAULT_FROM_EMAIL)[1].split('@')[-1] or 'foodloop.local'
    message = EmailMultiAlternatives(subject, render_to_string('emails/notification.txt', context), settings.DEFAULT_FROM_EMAIL, [note.user.email], headers={'Message-ID': f'<foodloop-{note.pk}-{int(note.created.timestamp())}@{domain}>'})
    message.attach_alternative(render_to_string('emails/notification.html', context), 'text/html')
    return message

def claim_next():
    now = timezone.now()
    with transaction.atomic():
        query = Notification.objects.filter(email_sent_at__isnull=True, email_skipped_at__isnull=True).filter(Q(email_next_retry_at__isnull=True)|Q(email_next_retry_at__lte=now)).filter(Q(email_claim_expires_at__isnull=True)|Q(email_claim_expires_at__lte=now)).order_by('created','pk')
        query = query.select_for_update(skip_locked=True) if connection.features.has_select_for_update_skip_locked else query.select_for_update()
        note = query.first()
        if note is None: return None
        reason = ''
        if note.created < now-timedelta(hours=24): reason = 'Notification older than 24 hours.'
        elif not note.user.is_active: reason = 'Account inactive.'
        elif EmailPreferences.objects.filter(user=note.user, enabled=False).exists(): reason = 'User turned email updates off.'
        else:
            try: validate_email(note.user.email)
            except ValidationError: reason = 'No valid email address on the account.'
        if reason:
            note.email_skipped_at = now
            note.email_last_error = reason
            note.save(update_fields=['email_skipped_at','email_last_error'])
            return 'skipped'
        note.email_claim_token = uuid.uuid4().hex
        note.email_claim_expires_at = now+timedelta(minutes=2)
        note.email_attempts += 1
        note.email_last_attempt_at = now
        note.save(update_fields=['email_claim_token','email_claim_expires_at','email_attempts','email_last_attempt_at'])
        return note

def deliver_pending(limit=200):
    result = {'sent':0,'failed':0,'skipped':0,'disabled':not settings.EMAIL_NOTIFICATIONS_ENABLED}
    if result['disabled']: return result
    for _ in range(limit):
        note = claim_next()
        if note is None: break
        if note == 'skipped': result['skipped'] += 1; continue
        try:
            delivered = build_notification_email(note).send(fail_silently=False)
            if delivered != 1: raise RuntimeError('Mail backend did not accept the message.')
        except Exception:
            values = {'email_claim_token':'','email_claim_expires_at':None,'email_last_error':'Email delivery failed. Check the sender connection.','email_next_retry_at':timezone.now()+timedelta(minutes=min(2**note.email_attempts,60))}
            if note.email_attempts >= 5:
                values['email_skipped_at'] = timezone.now()
                values['email_last_error'] = 'Email delivery stopped after five failed attempts.'
            Notification.objects.filter(pk=note.pk,email_claim_token=note.email_claim_token).update(**values)
            result['failed'] += 1
        else:
            Notification.objects.filter(pk=note.pk,email_claim_token=note.email_claim_token).update(email_sent_at=timezone.now(),email_claim_token='',email_claim_expires_at=None,email_next_retry_at=None,email_last_error='')
            result['sent'] += 1
    return result
