from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import Listing, Membership, Organisation, FoodRequest
from .services import request_food, change_request
from io import BytesIO
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from .forms import ListingForm

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkflowTests(TestCase):
    def setUp(self):
        self.provider = self.account('provider', 'provider')
        self.recipient = self.account('recipient', 'recipient')
        self.other = self.account('other', 'recipient')
        self.listing = Listing.objects.create(provider=self.provider.membership.organisation, name='Bread', quantity=10, unit='kg', pathway='human', condition='fresh', area='Lusaka', address='SECRET-PICKUP-ADDRESS', deadline=timezone.now()+timedelta(hours=8), safety_acknowledged=True)
    def account(self, name, role):
        org = Organisation.objects.create(name=name, role=role, area='Lusaka', status='approved')
        user = User.objects.create_user(name, password='Test-only-password-42')
        Membership.objects.create(user=user, organisation=org)
        return user
    def test_dual_confirmation_and_reservation(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('8'), True)
        self.listing.refresh_from_db(); self.assertEqual(self.listing.remaining, 10)
        change_request(self.provider, req.pk, 'accept')
        self.listing.refresh_from_db(); self.assertEqual(self.listing.remaining, 2)
        change_request(self.provider, req.pk, 'ready')
        change_request(self.provider, req.pk, 'confirm')
        req.refresh_from_db(); self.assertEqual(req.status, 'ready')
        change_request(self.recipient, req.pk, 'confirm')
        req.refresh_from_db(); self.assertEqual(req.status, 'collected')
        with self.assertRaises(ValidationError): change_request(self.recipient, req.pk, 'cancel')
    def test_overallocation_and_release(self):
        first = request_food(self.recipient, self.listing.pk, Decimal('8'), True)
        second = request_food(self.other, self.listing.pk, Decimal('8'), True)
        change_request(self.provider, first.pk, 'accept')
        with self.assertRaises(ValidationError): change_request(self.provider, second.pk, 'accept')
        change_request(self.recipient, first.pk, 'cancel')
        change_request(self.provider, second.pk, 'accept')
        self.listing.refresh_from_db(); self.assertEqual(self.listing.allocated, 8)
    def test_address_privacy(self):
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get(f'/listings/{self.listing.pk}/'), 'SECRET-PICKUP-ADDRESS')
        req = request_food(self.recipient, self.listing.pk, Decimal('3'), True)
        change_request(self.provider, req.pk, 'accept')
        self.assertContains(self.client.get(f'/listings/{self.listing.pk}/'), 'SECRET-PICKUP-ADDRESS')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(f'/listings/{self.listing.pk}/'), 'SECRET-PICKUP-ADDRESS')
    def test_eligibility_and_safety(self):
        with self.assertRaises(ValidationError): request_food(self.recipient, self.listing.pk, Decimal('1'), False)
        org = self.recipient.membership.organisation; org.status = 'suspended'; org.save()
        self.recipient.refresh_from_db()
        with self.assertRaises(PermissionDenied): request_food(self.recipient, self.listing.pk, Decimal('1'), True)
    def test_server_permissions(self):
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get('/listings/new/').status_code, 403)
        self.assertEqual(self.client.get('/').status_code, 200)
        req = request_food(self.recipient, self.listing.pk, Decimal('1'), True)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/requests/{req.pk}/accept/').status_code, 403)
    def test_deadline_and_human_suitability(self):
        self.listing.deadline = timezone.now()-timedelta(seconds=1); self.listing.save()
        with self.assertRaises(ValidationError): request_food(self.recipient, self.listing.pk, Decimal('1'), True)
        self.listing.condition = 'spoiled'
        with self.assertRaises(ValidationError): self.listing.full_clean()

    def test_photo_upload_and_display(self):
        image = BytesIO()
        source = Image.new('RGB', (2000, 1000), 'green')
        exif = Image.Exif()
        exif[270] = 'Private camera metadata'
        source.save(image, format='JPEG', exif=exif)
        upload = SimpleUploadedFile('bread.jpg', image.getvalue(), content_type='image/jpeg')
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.client.force_login(self.provider)
            response = self.client.post('/listings/new/', {'name': 'Photo bread', 'quantity': '5', 'unit': 'kg', 'pathway': 'human', 'condition': 'fresh', 'area': 'Lusaka', 'address': 'Private address', 'deadline': (timezone.now()+timedelta(days=1)).isoformat(), 'safety_acknowledged': 'on', 'photo': upload})
            self.assertEqual(response.status_code, 302)
            listing = Listing.objects.get(name='Photo bread')
            self.assertTrue(listing.photo.storage.exists(listing.photo.name))
            with Image.open(listing.photo.path) as processed:
                self.assertEqual(processed.size, (1600, 800))
                self.assertFalse(processed.getexif())
            self.assertContains(self.client.get('/'), f'/listings/{listing.pk}/photo/')
            photo_response = self.client.get(f'/listings/{listing.pk}/photo/')
            self.assertEqual(photo_response.status_code, 200)
            self.assertEqual(photo_response.headers['Content-Type'], 'image/jpeg')
            self.assertEqual(photo_response.headers['Cache-Control'], 'private, no-store')
            self.assertTrue(b''.join(photo_response.streaming_content).startswith(b'\xff\xd8'))
            self.client.force_login(self.recipient)
            self.assertContains(self.client.get(f'/listings/{listing.pk}/'), f'/listings/{listing.pk}/photo/')
            self.assertNotContains(self.client.get(f'/listings/{listing.pk}/'), 'Private address')
            self.client.logout()
            self.assertEqual(self.client.get(f'/listings/{listing.pk}/photo/').status_code, 302)
            self.assertEqual(self.client.get(listing.photo.url).status_code, 404)

    def test_invalid_photo_rejected(self):
        upload = SimpleUploadedFile('not-a-photo.jpg', b'<html>not an image</html>', content_type='image/jpeg')
        form = ListingForm(data={}, files={'photo': upload})
        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

    def test_pathway_filter_preserves_eligibility(self):
        Listing.objects.create(provider=self.provider.membership.organisation, name='Animal only', quantity=10, unit='kg', pathway='feed', condition='spoiled', area='Lusaka', address='Secret', deadline=timezone.now()+timedelta(hours=8), safety_acknowledged=True)
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get('/?pathway=feed'), 'Animal only')
        self.assertContains(self.client.get('/?q=Bread'), 'Bread')
