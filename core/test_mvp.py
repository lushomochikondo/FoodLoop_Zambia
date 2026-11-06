from .test_support import transition_request
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from .tests import WorkflowTests
from .models import AuditLog, FlagReport, FoodRequest, Listing, Notification, Organisation, RequestEvent
from .matching import rank_listing
from .services import change_request, close_listing, expire_requests, request_food, review_flag, verify_organisation

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MVPTests(TestCase):
    account = WorkflowTests.account
    setUp = WorkflowTests.setUp

    def listing_data(self):
        return {'name': 'Updated bread', 'quantity': '12', 'unit': 'kg', 'pathway': 'human', 'condition': 'fresh', 'area': 'Lusaka', 'address': 'Private updated address', 'deadline': (timezone.now()+timedelta(days=1)).isoformat(), 'safety_acknowledged': 'on'}

    def test_edit_notifies_pending_requesters(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        self.client.force_login(self.provider)
        response = self.client.post(f'/listings/{self.listing.pk}/edit/', self.listing_data())
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db(); req.refresh_from_db()
        self.assertEqual(self.listing.name, 'Updated bread')
        self.assertEqual(req.status, 'cancelled')
        self.assertTrue(Notification.objects.filter(user=self.recipient).exists())

    def test_edit_blocks_accepted_and_other_organisations(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        change_request(self.provider, req.pk, 'accept')
        self.client.force_login(self.provider)
        self.client.post(f'/listings/{self.listing.pk}/edit/', self.listing_data())
        self.listing.refresh_from_db(); self.assertEqual(self.listing.name, 'Bread')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/listings/{self.listing.pk}/edit/', self.listing_data()).status_code, 403)

    def test_withdraw_releases_allocations_and_cancels_pending(self):
        first = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        second = request_food(self.other, self.listing.pk, Decimal('3'), True)
        change_request(self.provider, first.pk, 'accept')
        close_listing(self.provider, self.listing.pk, 'withdrawn', 'No longer available')
        self.listing.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(self.listing.allocated, 0)
        self.assertEqual(first.status, 'cancelled'); self.assertEqual(second.status, 'cancelled')
        self.assertFalse(self.listing.available)
        with self.assertRaises(ValidationError): request_food(self.recipient, self.listing.pk, Decimal('1'), True)

    def test_expiry_and_no_show_are_idempotent(self):
        first = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        second = request_food(self.other, self.listing.pk, Decimal('3'), True)
        change_request(self.provider, first.pk, 'accept')
        change_request(self.provider, first.pk, 'ready')
        Listing.objects.filter(pk=self.listing.pk).update(deadline=timezone.now()-timedelta(seconds=1))
        self.assertEqual(expire_requests(), 2)
        first.refresh_from_db(); second.refresh_from_db(); self.listing.refresh_from_db()
        self.assertEqual(first.status, 'no_show'); self.assertEqual(second.status, 'expired')
        self.assertEqual(self.listing.allocated, 0)
        count = Notification.objects.count()
        self.assertEqual(expire_requests(), 0)
        self.assertEqual(count, Notification.objects.count())

    def test_stale_pending_expires_before_future_listing_deadline(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        FoodRequest.objects.filter(pk=req.pk).update(created=timezone.now()-timedelta(hours=25))
        self.assertEqual(expire_requests(), 1)
        req.refresh_from_db(); self.assertEqual(req.status, 'expired')

    def test_matching_scores_urgency_and_explains_fit(self):
        org = self.recipient.membership.organisation
        org.area = 'Lusaka'; org.usual_quantity = 10
        first = rank_listing(self.listing, org)
        self.listing.deadline = timezone.now()+timedelta(hours=1)
        urgent = rank_listing(self.listing, org)
        self.assertGreater(urgent[0], first[0])
        self.assertIn('Same area', urgent[1]); self.assertIn('Quantity fits', urgent[1])
        self.listing.pathway = 'feed'; self.listing.condition = 'spoiled'
        self.assertIsNone(rank_listing(self.listing, org))

    def test_notifications_are_private_and_post_only_for_read_state(self):
        note = Notification.objects.create(user=self.recipient, message='Private recipient notification')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/notifications/'), 'Private recipient notification')
        self.client.post('/notifications/', {'notification_id': note.pk})
        note.refresh_from_db(); self.assertFalse(note.read)
        self.client.force_login(self.recipient)
        self.assertContains(self.client.get('/notifications/'), 'Private recipient notification')
        note.refresh_from_db(); self.assertFalse(note.read)
        self.client.post('/notifications/', {'notification_id': note.pk})
        note.refresh_from_db(); self.assertTrue(note.read)

    def test_admin_review_removes_and_audits_listing(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        change_request(self.provider, req.pk, 'accept')
        self.client.force_login(self.recipient)
        self.client.post(f'/listings/{self.listing.pk}/report/', {'reason': 'Food appears to be misdescribed.'})
        flag = FlagReport.objects.get()
        admin = User.objects.create_user('admin', is_staff=True)
        with self.assertRaises(PermissionDenied): review_flag(self.recipient, flag.pk, 'removed', 'Unsafe description')
        review_flag(admin, flag.pk, 'removed', 'Unsafe description')
        flag.refresh_from_db(); req.refresh_from_db(); self.listing.refresh_from_db()
        self.assertEqual(flag.status, 'removed'); self.assertEqual(req.status, 'cancelled')
        self.assertEqual(self.listing.status, 'removed'); self.assertEqual(self.listing.allocated, 0)
        self.assertTrue(AuditLog.objects.filter(actor=admin, action__contains='removed').exists())

    def test_verification_requires_admin_and_reason(self):
        org = self.recipient.membership.organisation
        with self.assertRaises(PermissionDenied): verify_organisation(self.other, org.pk, 'suspended', 'Review required')
        admin = User.objects.create_user('admin', is_staff=True)
        with self.assertRaises(ValidationError): verify_organisation(admin, org.pk, 'suspended', '')
        verify_organisation(admin, org.pk, 'suspended', 'Review required')
        self.recipient.refresh_from_db()
        with self.assertRaises(PermissionDenied): request_food(self.recipient, self.listing.pk, Decimal('1'), True)

    def test_dual_confirmation_timestamps_events_and_impact(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        change_request(self.provider, req.pk, 'accept')
        req.refresh_from_db(); self.assertIsNotNone(req.decision_time)
        change_request(self.provider, req.pk, 'ready')
        transition_request(self.provider, req, 'confirm')
        self.client.force_login(self.recipient)
        self.assertContains(self.client.get('/impact/'), '0.0')
        transition_request(self.recipient, req, 'confirm')
        req.refresh_from_db(); self.assertEqual(req.confirmed_quantity, 4)
        self.assertEqual(req.events.count(), 5)
        self.assertTrue(all(e.created for e in req.events.all()))
        response = self.client.get('/impact/')
        self.assertEqual(response.context['kg'], 4)
        self.assertEqual(response.context['meals'], 10)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/impact/').context['kg'], 0)

    def test_moderation_and_export_permissions(self):
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get('/administration/').status_code, 403)
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        for user, action in [(self.provider, 'accept'), (self.provider, 'ready'), (self.provider, 'confirm'), (self.recipient, 'confirm')]: transition_request(user, req, action)
        self.listing.name = '=FORMULA'; self.listing.save()
        export = self.client.get('/impact/?format=csv')
        self.assertIn("'=FORMULA", export.content.decode())
        self.client.force_login(self.other)
        self.assertNotIn('FORMULA', self.client.get('/impact/?format=csv').content.decode())

    def test_admin_can_cancel_but_cannot_accept(self):
        admin = User.objects.create_user('admin', is_staff=True)
        req = request_food(self.recipient, self.listing.pk, Decimal('4'), True)
        with self.assertRaises(PermissionDenied): change_request(admin, req.pk, 'accept')
        change_request(admin, req.pk, 'cancel')
        req.refresh_from_db(); self.assertEqual(req.status, 'cancelled')

    def test_new_pages_render_for_correct_roles(self):
        admin = User.objects.create_user('admin', is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/administration/').status_code, 200)
        self.assertEqual(self.client.get('/impact/').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)
