import base64
from datetime import timedelta
from decimal import Decimal
from email import message_from_bytes
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .email_backends import GmailAPIEmailBackend
from .models import FoodRequest, Listing, Membership, Notification, Organisation, PushDelivery, PushSubscription, ScheduledJobState


@override_settings(GMAIL_CLIENT_ID='test-client', GMAIL_CLIENT_SECRET='private-secret', GMAIL_REFRESH_TOKEN='private-refresh')
class GmailAPITests(TestCase):
    @patch('core.email_backends.requests.post')
    def test_refresh_token_reused_and_multipart_and_bcc_sent(self, post):
        post.side_effect = [Mock(status_code=200, json=lambda: {'access_token': 'private-access', 'expires_in': 3600}),
                            Mock(status_code=200, json=lambda: {'id': 'message-1'}),
                            Mock(status_code=200, json=lambda: {'id': 'message-2'})]
        note = mail.EmailMultiAlternatives('Approved', 'Approved text', 'owner@gmail.com', ['recipient@example.invalid'], bcc=['private@example.invalid'])
        note.attach_alternative('<p>Approved</p>', 'text/html')
        backend = GmailAPIEmailBackend()
        self.assertEqual(backend.send_messages([note, note]), 2)
        self.assertEqual(post.call_count, 3)
        token_call, send_call, _ = post.call_args_list
        self.assertEqual(token_call.args[0], 'https://oauth2.googleapis.com/token')
        mime = message_from_bytes(base64.urlsafe_b64decode(send_call.kwargs['json']['raw']))
        self.assertEqual(mime['Bcc'], 'private@example.invalid')
        self.assertTrue(mime.is_multipart())
        self.assertIn('text/html', [part.get_content_type() for part in mime.walk()])

    @patch('core.email_backends.requests.post')
    def test_expired_access_refreshes_once(self, post):
        post.side_effect = [Mock(json=lambda: {'access_token': 'first'}), Mock(status_code=401),
                            Mock(json=lambda: {'access_token': 'second'}), Mock(status_code=200, json=lambda: {'id': 'ok'})]
        message = mail.EmailMessage('Account', 'Approved', 'owner@gmail.com', ['person@example.invalid'])
        self.assertEqual(GmailAPIEmailBackend().send_messages([message]), 1)
        self.assertEqual(post.call_args_list[-1].kwargs['headers']['Authorization'], 'Bearer second')

    @patch('core.email_backends.requests.post', side_effect=RuntimeError('private-secret private-refresh'))
    def test_provider_errors_do_not_leak_credentials(self, post):
        message = mail.EmailMessage('Account', 'Approved', 'owner@gmail.com', ['person@example.invalid'])
        with self.assertRaisesRegex(RuntimeError, '^Gmail HTTPS delivery failed') as caught:
            GmailAPIEmailBackend().send_messages([message])
        self.assertNotIn('private-secret', str(caught.exception))
        self.assertEqual(GmailAPIEmailBackend(fail_silently=True).send_messages([message]), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkspaceTotalsTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name='Donor', role='provider', status='approved', area='Lusaka')
        self.recipient = Organisation.objects.create(name='Kitchen', role='recipient', status='approved', area='Lusaka')
        self.user = User.objects.create(username='totals-donor')
        Membership.objects.create(user=self.user, organisation=self.org)
        self.human = Listing.objects.create(provider=self.org, name='Bread', quantity=20, pathway='human', unit='kg',
            condition='fresh', area='Lusaka', deadline=timezone.now()+timedelta(days=3), safety_acknowledged=True)
        self.feed = Listing.objects.create(provider=self.org, name='Feed', quantity=30, pathway='feed', unit='bags',
            condition='fresh', area='Lusaka', deadline=timezone.now()+timedelta(days=3), safety_acknowledged=True)
        FoodRequest.objects.create(listing=self.human, recipient=self.recipient, status='collected', quantity=4,
                                   confirmed_quantity=3, confirmed_weight_kg=3, collected_at=timezone.now())
        FoodRequest.objects.create(listing=self.feed, recipient=self.recipient, status='collected', quantity=2,
                                   confirmed_quantity=1, confirmed_weight_kg=10, collected_at=timezone.now())
        for status in ['pending', 'accepted', 'ready']:
            FoodRequest.objects.create(listing=self.human, recipient=self.recipient, status=status, quantity=1)
        self.client.force_login(self.user)

    def test_dashboard_preserves_weight_and_status_totals(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['kg'], Decimal('13'))
        self.assertEqual(response.context['meals'], 7)
        self.assertEqual(response.context['collection_count'], 2)
        self.assertEqual(response.context['active_count'], 3)
        for status in ['pending', 'accepted', 'ready']:
            self.assertEqual(response.context[f'{status}_count'], 1)
        self.assertEqual([row['kg'] for row in response.context['pathway_totals']], [3, 10, 0])

    def test_impact_preserves_units_filters_and_reduces_queries(self):
        # Warm cached platform settings before counting complete page queries.
        self.client.get('/impact/')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/impact/')
        self.assertEqual(response.context['kg'], 13)
        self.assertLess(len(queries), 25)
        rows = {row['unit']: row for row in response.context['rows']}
        self.assertEqual(rows['Kilograms']['listed'], 20)
        self.assertEqual(rows['Kilograms']['collected'], 3)
        self.assertEqual(rows['Bags']['listed'], 30)
        self.assertEqual(rows['Bags']['collected'], 1)
        filtered = self.client.get('/impact/?pathway=feed')
        self.assertEqual(filtered.context['kg'], 10)
        self.assertEqual(filtered.context['meals'], 0)

    def test_system_status_is_admin_only_and_does_not_expose_credentials(self):
        self.assertEqual(self.client.get('/administration/system/').status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        with override_settings(GMAIL_CLIENT_SECRET='never-display-this', GMAIL_REFRESH_TOKEN='private-token'):
            response = self.client.get('/administration/system/')
        self.assertContains(response, 'System status.')
        self.assertNotContains(response, 'never-display-this')
        self.assertNotContains(response, 'private-token')


class RetryJobTests(TestCase):
    @patch('core.management.commands.run_scheduler.time.sleep', side_effect=[None, KeyboardInterrupt])
    @patch('core.management.commands.run_scheduler.call_command', side_effect=[RuntimeError('temporary'), None])
    def test_scheduler_survives_a_failed_cycle(self, command, sleep):
        with self.assertLogs('core.management.commands.run_scheduler', level='ERROR'):
            call_command('run_scheduler', stdout=StringIO())
        self.assertEqual(command.call_count, 2)

    @patch('core.management.commands.run_jobs.Command.run_cycle')
    def test_job_lease_prevents_overlap_and_recovers_after_expiry(self, cycle):
        state = ScheduledJobState.objects.create(name='notifications-and-deadlines', claim_token='busy',
                                                claim_expires_at=timezone.now()+timedelta(minutes=1))
        call_command('run_jobs', stdout=StringIO())
        cycle.assert_not_called()
        state.claim_expires_at = timezone.now()-timedelta(seconds=1)
        state.save()
        call_command('run_jobs', stdout=StringIO())
        cycle.assert_called_once()
        state.refresh_from_db()
        self.assertIsNotNone(state.last_completed_at)
        self.assertEqual(state.claim_token, '')

    @patch('core.management.commands.run_jobs.Command.run_cycle', side_effect=RuntimeError('provider-secret'))
    def test_failed_job_records_safe_error_and_releases_lease(self, cycle):
        with self.assertRaises(RuntimeError):
            call_command('run_jobs', stdout=StringIO())
        state = ScheduledJobState.objects.get()
        self.assertNotIn('provider-secret', state.last_error)
        self.assertIsNone(state.claim_expires_at)

    @override_settings(WEB_PUSH_ENABLED=True, WEB_PUSH_PRIVATE_KEY='private-key', WEB_PUSH_SUBJECT='https://foodloop.example')
    @patch('pywebpush.webpush')
    def test_push_claim_prevents_overlap_and_expired_claim_retries(self, webpush):
        from .push_delivery import deliver_push
        user = User.objects.create(username='push-test')
        sub = PushSubscription.objects.create(user=user, endpoint='https://example.invalid/push', p256dh='key', auth='auth')
        note = Notification.objects.create(user=user, message='Approved')
        delivery = PushDelivery.objects.create(subscription=sub, notification=note, claim_token='busy',
                                               claim_expires_at=timezone.now()+timedelta(minutes=1))
        self.assertEqual(deliver_push()['sent'], 0)
        webpush.assert_not_called()
        delivery.claim_expires_at = timezone.now()-timedelta(seconds=1)
        delivery.save()
        self.assertEqual(deliver_push()['sent'], 1)
        self.assertEqual(deliver_push()['sent'], 0)
        webpush.assert_called_once()


class SupervisorTests(TestCase):
    @patch('scripts.supervise.signal.signal')
    @patch('scripts.supervise.subprocess.Popen')
    def test_scheduler_failure_stops_web_process(self, start, signal):
        from scripts.supervise import supervise
        web, scheduler = Mock(), Mock()
        web.poll.return_value = None
        scheduler.poll.return_value = 7
        start.side_effect = [web, scheduler]
        self.assertEqual(supervise([['web'], ['scheduler']]), 7)
        web.terminate.assert_called_once()
        web.wait.assert_called_once()

    @patch('scripts.supervise.signal.signal')
    @patch('scripts.supervise.subprocess.Popen')
    def test_shutdown_signal_stops_both_children(self, start, signal_handler):
        from scripts.supervise import supervise
        web, scheduler = Mock(), Mock()
        web.poll.return_value = scheduler.poll.return_value = None
        start.side_effect = [web, scheduler]
        def trigger_shutdown(*args):
            handler = signal_handler.call_args_list[0].args[1]
            handler(15, None)
        with patch('scripts.supervise.time.sleep', side_effect=trigger_shutdown):
            self.assertEqual(supervise([['web'], ['scheduler']]), 0)
        web.terminate.assert_called_once()
        scheduler.terminate.assert_called_once()
