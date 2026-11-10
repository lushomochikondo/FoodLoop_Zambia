from .test_support import transition_request
from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import AuditLog,FlagReport,Listing,FoodRequest
from .services import change_request,delete_listing,request_food,review_flag
from .tests import WorkflowTests

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ListingManagementTests(TestCase):
    account=WorkflowTests.account
    setUp=WorkflowTests.setUp

    def test_delete_unused_listing_and_photo_after_commit(self):
        with TemporaryDirectory() as folder,override_settings(MEDIA_ROOT=folder):
            self.listing.photo.save('fixture.jpg',ContentFile(b'delete-file-fixture'))
            photo=self.listing.photo.name;storage=self.listing.photo.storage
            self.client.force_login(self.provider)
            self.assertEqual(self.client.get(f'/listings/{self.listing.pk}/delete/').status_code,200)
            self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
            self.assertRedirects(self.client.post(f'/listings/{self.listing.pk}/delete/',{}),f'/listings/{self.listing.pk}/delete/')
            self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
            with self.captureOnCommitCallbacks(execute=True):
                response=self.client.post(f'/listings/{self.listing.pk}/delete/',{'confirm':'yes'})
            self.assertEqual(response.status_code,302)
            self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())
            self.assertFalse(storage.exists(photo))
            self.assertTrue(AuditLog.objects.filter(action__contains='deleted by donor').exists())

    def test_withdrawn_listing_can_be_deleted(self):
        self.listing.status='withdrawn';self.listing.save()
        delete_listing(self.provider,self.listing.pk)
        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_only_owning_provider_can_delete(self):
        for user in [self.recipient,self.other,self.account('anotherprovider','provider')]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(f'/listings/{self.listing.pk}/delete/',{'confirm':'yes'}).status_code,403)
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_delete_cancels_pending_and_accepted_requests_and_releases_quantity(self):
        first=request_food(self.recipient,self.listing.pk,Decimal('4'),True)
        second=request_food(self.other,self.listing.pk,Decimal('3'),True)
        change_request(self.provider,first.pk,'accept')
        self.assertTrue(delete_listing(self.provider,self.listing.pk))
        self.listing.refresh_from_db();first.refresh_from_db();second.refresh_from_db()
        self.assertEqual(self.listing.status,'deleted')
        self.assertIsNotNone(self.listing.deleted_at)
        self.assertEqual(self.listing.allocated,0)
        self.assertEqual(first.status,'cancelled');self.assertEqual(second.status,'cancelled')
        self.client.force_login(self.provider)
        self.assertNotIn(self.listing.pk,[item.pk for item in self.client.get('/').context['listings']])

    def test_completed_collection_impact_and_history_survive_deletion(self):
        req=request_food(self.recipient,self.listing.pk,Decimal('4'),True)
        for user,action in [(self.provider,'accept'),(self.provider,'ready'),(self.provider,'confirm'),(self.recipient,'confirm')]:transition_request(user,req,action)
        delete_listing(self.provider,self.listing.pk)
        req.refresh_from_db();self.assertEqual(req.status,'collected')
        self.client.force_login(self.provider)
        self.assertEqual(self.client.get('/impact/').context['kg'],4)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/listings/{self.listing.pk}/').status_code,404)
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(f'/listings/{self.listing.pk}/').status_code,200)

    def test_provider_can_accept_from_listing_detail_and_recipient_sees_decision(self):
        self.client.force_login(self.recipient)
        response=self.client.post(f'/listings/{self.listing.pk}/',{'quantity':4,'safety':'on'})
        self.assertEqual(response.status_code,302)
        req=FoodRequest.objects.get()
        self.client.force_login(self.provider)
        page=self.client.get(f'/listings/{self.listing.pk}/')
        self.assertContains(page,f'/requests/{req.pk}/accept/')
        response=self.client.post(f'/requests/{req.pk}/accept/',{'return_to_listing':'1'})
        self.assertRedirects(response,f'/listings/{self.listing.pk}/')
        req.refresh_from_db();self.listing.refresh_from_db()
        self.assertEqual(req.status,'accepted');self.assertEqual(self.listing.allocated,4)
        self.client.force_login(self.recipient)
        page=self.client.get(f'/listings/{self.listing.pk}/')
        self.assertContains(page,'Accepted')
        self.assertContains(page,'SECRET-PICKUP-ADDRESS')

    def test_existing_moderation_report_survives_and_can_be_reviewed_after_deletion(self):
        from django.contrib.auth.models import User
        flag=FlagReport.objects.create(listing=self.listing,reporter=self.recipient,reason='Review this donation')
        self.assertTrue(delete_listing(self.provider,self.listing.pk))
        admin=User.objects.create_user('reviewer',is_staff=True)
        review_flag(admin,flag.pk,'removed','Report reviewed after provider deletion.')
        flag.refresh_from_db();self.listing.refresh_from_db()
        self.assertEqual(flag.status,'removed')
        self.assertEqual(self.listing.status,'deleted')
