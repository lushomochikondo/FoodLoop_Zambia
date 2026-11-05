from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from .email_delivery import build_notification_email, claim_next, deliver_pending
from .models import EmailPreferences, Notification

@override_settings(EMAIL_NOTIFICATIONS_ENABLED=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',PUBLIC_APP_URL='https://foodloop.example')
class EmailNotificationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create(username='recipient',first_name='Demo',email='recipient@example.invalid')
        self.note=Notification.objects.create(user=self.user,message='Your collection is ready. <script>not executable</script>')

    def test_multipart_private_recipient_links_and_deduplication(self):
        self.assertEqual(deliver_pending()['sent'],1)
        self.assertEqual(len(mail.outbox),1)
        message=mail.outbox[0]
        self.assertEqual(message.to,['recipient@example.invalid'])
        self.assertIn('https://foodloop.example/notifications/',message.body)
        self.assertIn('https://foodloop.example/profile/',message.body)
        html=message.alternatives[0].content
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>',html)
        self.note.refresh_from_db();self.assertIsNotNone(self.note.email_sent_at)
        self.assertEqual(deliver_pending()['sent'],0)
        self.assertEqual(len(mail.outbox),1)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_disabled_delivery_leaves_notification_available_in_app(self):
        self.assertTrue(deliver_pending()['disabled'])
        self.note.refresh_from_db()
        self.assertIsNone(self.note.email_sent_at)
        self.assertEqual(self.note.email_attempts,0)
        self.assertFalse(self.note.read)

    def test_user_opt_out_is_respected_at_delivery(self):
        EmailPreferences.objects.create(user=self.user,enabled=False)
        self.assertEqual(deliver_pending()['skipped'],1)
        self.note.refresh_from_db();self.assertIsNotNone(self.note.email_skipped_at)
        self.assertIsNone(self.note.email_sent_at)
        self.assertFalse(self.note.read)

    def test_failed_smtp_retries_without_leaking_credentials(self):
        with patch('core.email_delivery.EmailMultiAlternatives.send',side_effect=RuntimeError('FAKE-SMTP-SECRET')):
            self.assertEqual(deliver_pending()['failed'],1)
        self.note.refresh_from_db()
        self.assertEqual(self.note.email_attempts,1)
        self.assertNotIn('FAKE-SMTP-SECRET',self.note.email_last_error)
        self.assertIsNotNone(self.note.email_next_retry_at)
        self.assertEqual(deliver_pending()['sent'],0)
        Notification.objects.filter(pk=self.note.pk).update(email_next_retry_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(deliver_pending()['sent'],1)

    def test_claim_lease_prevents_second_worker_taking_same_email(self):
        note=claim_next()
        self.assertEqual(note.pk,self.note.pk)
        self.assertIsNone(claim_next())
        Notification.objects.filter(pk=self.note.pk).update(email_claim_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(claim_next().pk,self.note.pk)

    def test_bad_or_inactive_recipients_and_stale_notifications_are_skipped(self):
        self.user.email='';self.user.save()
        self.assertEqual(deliver_pending()['skipped'],1)
        self.user.email='recipient@example.invalid';self.user.save()
        stale=Notification.objects.create(user=self.user,message='Old update')
        Notification.objects.filter(pk=stale.pk).update(created=timezone.now()-timedelta(days=2))
        self.assertEqual(deliver_pending()['skipped'],1)
        self.user.is_active=False;self.user.save()
        Notification.objects.create(user=self.user,message='Inactive account')
        self.assertEqual(deliver_pending()['skipped'],1)

    def test_profile_preference_is_editable_only_for_current_user(self):
        self.client.force_login(self.user)
        self.user.is_staff=True;self.user.save() # Admin profile has no organisation requirement.
        self.client.post('/profile/',{'first_name':'Demo','last_name':'Member','email':'recipient@example.invalid'})
        self.assertFalse(EmailPreferences.objects.get(user=self.user).enabled)
        self.client.post('/profile/',{'first_name':'Demo','last_name':'Member','email':'recipient@example.invalid','email_notifications':'on'})
        self.assertTrue(EmailPreferences.objects.get(user=self.user).enabled)

    def test_no_public_url_produces_no_broken_localhost_link(self):
        with override_settings(PUBLIC_APP_URL=''):
            message=build_notification_email(self.note)
        self.assertNotIn('127.0.0.1',message.body)
        self.assertIn('Sign in to your FoodLoop',message.body)

    def test_older_server_notification_insert_uses_database_defaults(self):
        # During a rolling update an older worker omits newly added email columns.
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO core_notification (user_id,message,"read",created,listing_id,event_key) VALUES (%s,%s,%s,%s,%s,%s)',[self.user.pk,'Old worker compatibility fixture',False,timezone.now(),None,None])
        note=Notification.objects.get(message='Old worker compatibility fixture')
        self.assertEqual(note.email_attempts,0)
        self.assertEqual(note.email_claim_token,'')
        self.assertEqual(note.email_last_error,'')
