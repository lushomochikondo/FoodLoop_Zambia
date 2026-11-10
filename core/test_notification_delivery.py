from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from .models import Notification, PushSubscription, PushDelivery
from .email_backends import ResendEmailBackend


class NotificationDeliveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('alerts-user', email='alerts@example.invalid', is_staff=True)
        self.client.force_login(self.user)

    @override_settings(WEB_PUSH_ENABLED=True, WEB_PUSH_PUBLIC_KEY='test-public-key')
    def test_notification_page_exposes_phone_controls(self):
        response = self.client.get('/notifications/')
        self.assertContains(response, 'Enable phone notifications')
        self.assertContains(response, 'Send test phone alert')
        self.assertContains(response, 'test-public-key')

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', WEB_PUSH_ENABLED=False)
    def test_new_notification_delivers_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            note = Notification.objects.create(user=self.user, message='Your organisation is approved.')
            self.assertEqual(len(mail.outbox), 0)
        note.refresh_from_db()
        self.assertIsNotNone(note.email_sent_at)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(WEB_PUSH_ENABLED=True, EMAIL_NOTIFICATIONS_ENABLED=False)
    @patch('core.push_delivery.deliver_push')
    def test_phone_test_is_scoped_and_throttled(self, deliver):
        self.assertEqual(self.client.post('/notifications/push/test/').status_code, 409)
        PushSubscription.objects.create(user=self.user, endpoint='https://example.invalid/push/demo', p256dh='test-key', auth='test-auth')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post('/notifications/push/test/').status_code, 200)
        note = Notification.objects.get(user=self.user)
        deliver.assert_called_once_with(notification_ids=[note.pk])
        self.assertEqual(self.client.post('/notifications/push/test/').status_code, 429)

    @override_settings(WEB_PUSH_ENABLED=True, WEB_PUSH_PRIVATE_KEY='test-key', WEB_PUSH_SUBJECT='mailto:demo@example.invalid', EMAIL_NOTIFICATIONS_ENABLED=False)
    @patch('pywebpush.webpush')
    def test_push_targets_new_notification_and_deduplicates(self, webpush):
        from .push_delivery import deliver_push
        PushSubscription.objects.create(user=self.user, endpoint='https://example.invalid/push/demo', p256dh='test-key', auth='test-auth')
        old = Notification.objects.create(user=self.user, message='Older notification')
        new = Notification.objects.create(user=self.user, message='New approval')
        self.assertEqual(deliver_push(notification_ids=[new.pk])['sent'], 1)
        self.assertEqual(deliver_push(notification_ids=[new.pk])['sent'], 0)
        self.assertFalse(PushDelivery.objects.filter(notification=old).exists())
        self.assertEqual(webpush.call_count, 1)

    @override_settings(RESEND_API_KEY='test-secret')
    @patch('core.email_backends.requests.post')
    def test_https_email_payload_and_private_errors(self, post):
        from django.core.mail import EmailMultiAlternatives
        message = EmailMultiAlternatives('Approval', 'Approved', 'demo@example.invalid', ['recipient@example.invalid'], headers={'Message-ID':'<foodloop-demo@example.invalid>'})
        message.attach_alternative('<p>Approved</p>', 'text/html')
        post.return_value = Mock(ok=True)
        self.assertEqual(ResendEmailBackend().send_messages([message]), 1)
        self.assertEqual(post.call_args.kwargs['json']['html'], '<p>Approved</p>')
        self.assertEqual(post.call_args.kwargs['headers']['Idempotency-Key'], 'foodloop-demo@example.invalid')
        post.side_effect = RuntimeError('test-secret')
        with self.assertRaisesRegex(RuntimeError, '^HTTPS email delivery failed') as error:
            ResendEmailBackend().send_messages([message])
        self.assertNotIn('test-secret', str(error.exception))
