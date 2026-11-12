from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Listing, ListingPhoto, Membership, Organisation


def uploaded_photo(name='food.png', size=(12, 10)):
    output = BytesIO()
    image = Image.new('RGB', size, '#be6d38')
    image.save(output, format='PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ListingGalleryTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        org = Organisation.objects.create(name='Gallery donor', role='provider', status='approved', area='Lusaka')
        self.donor = User.objects.create_user('gallery-donor')
        Membership.objects.create(user=self.donor, organisation=org)
        org = Organisation.objects.create(name='Gallery kitchen', role='recipient', status='approved', area='Lusaka')
        self.recipient = User.objects.create_user('gallery-recipient')
        Membership.objects.create(user=self.recipient, organisation=org)
        self.client.force_login(self.donor)

    def data(self, **values):
        data = {'name': 'Gallery bread', 'quantity': 50, 'unit': 'kg', 'pathway': 'human', 'condition': 'fresh',
                'area': 'Lusaka', 'address': 'Private entrance', 'deadline': (timezone.now()+timedelta(days=3)).isoformat(),
                'safety_acknowledged': 'on'}
        data.update(values)
        return data

    def create_gallery(self, count=5):
        response = self.client.post('/listings/new/', self.data(photos=[uploaded_photo(f'food-{i}.png') for i in range(count)]))
        self.assertEqual(response.status_code, 302)
        return Listing.objects.get(name='Gallery bread')

    def test_five_photos_create_one_cover_and_four_private_gallery_images(self):
        listing = self.create_gallery()
        self.assertTrue(listing.photo)
        self.assertEqual(listing.extra_photos.count(), 4)
        with listing.photo.open('rb') as file:
            image = Image.open(file)
            self.assertEqual(image.format, 'JPEG')
            self.assertFalse(image.getexif())
        home = self.client.get('/')
        self.assertContains(home, f'/listings/{listing.pk}/photo/')
        self.assertNotContains(home, f'/listings/{listing.pk}/photos/')
        detail = self.client.get(f'/listings/{listing.pk}/')
        self.assertContains(detail, 'data-gallery-src=', count=5)
        self.assertContains(detail, 'Photo 1 of 5')
        self.client.force_login(self.recipient)
        image = self.client.get(f'/listings/{listing.pk}/photos/{listing.extra_photos.first().pk}/')
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Cache-Control'], 'private, no-store')
        image.close()

    def test_six_photos_rejected_without_partial_listing(self):
        response = self.client.post('/listings/new/', self.data(photos=[uploaded_photo(f'p{i}.png') for i in range(6)]))
        self.assertContains(response, 'up to five photos')
        self.assertEqual(Listing.objects.count(), 0)
        self.assertEqual(ListingPhoto.objects.count(), 0)

    def test_invalid_or_oversized_photo_rejects_whole_upload(self):
        invalid = SimpleUploadedFile('fake.jpg', b'not an image', content_type='image/jpeg')
        response = self.client.post('/listings/new/', self.data(photos=[uploaded_photo(), invalid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Listing.objects.count(), 0)
        image = uploaded_photo()
        oversized = SimpleUploadedFile('large.png', image.read() + b'x' * (4*1024*1024), content_type='image/png')
        response = self.client.post('/listings/new/', self.data(photos=[oversized]))
        self.assertContains(response, 'smaller than 4 MB')
        self.assertEqual(Listing.objects.count(), 0)

    def test_edit_cannot_exceed_five_and_can_replace_after_removal(self):
        listing = self.create_gallery()
        old_cover = listing.photo.name
        response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(photos=[uploaded_photo('new.png')], cover_photo='cover'))
        self.assertContains(response, 'up to five photos')
        listing.refresh_from_db()
        self.assertEqual(listing.photo.name, old_cover)
        removed = listing.extra_photos.last()
        old_path = removed.image.name
        storage = removed.image.storage
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(
                photos=[uploaded_photo('new.png', (22, 10))], remove_photos=[f'extra-{removed.pk}'], cover_photo='new-0'))
        self.assertEqual(response.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.extra_photos.count(), 4)
        self.assertFalse(storage.exists(old_path))
        self.assertTrue(listing.extra_photos.filter(image=old_cover).exists())
        with listing.photo.open('rb') as file:
            self.assertEqual(Image.open(file).size, (22, 10))

    def test_cover_can_switch_to_existing_photo_without_deleting_files(self):
        listing = self.create_gallery()
        old_cover = listing.photo.name
        extra = listing.extra_photos.first()
        selected = extra.image.name
        response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(cover_photo=f'extra-{extra.pk}'))
        self.assertEqual(response.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.photo.name, selected)
        self.assertTrue(listing.extra_photos.filter(image=old_cover).exists())
        self.assertTrue(listing.photo.storage.exists(old_cover))

    def test_legacy_single_photo_and_edit_without_photo_changes(self):
        response = self.client.post('/listings/new/', self.data(photo=uploaded_photo()))
        self.assertEqual(response.status_code, 302)
        listing = Listing.objects.get()
        cover = listing.photo.name
        response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(name='Updated bread'))
        self.assertEqual(response.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.photo.name, cover)
        self.assertEqual(listing.extra_photos.count(), 0)

    def test_gallery_access_and_tampering_follow_listing_permissions(self):
        listing = self.create_gallery()
        extra = listing.extra_photos.first()
        response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(cover_photo='extra-9999999'))
        self.assertContains(response, 'Choose a cover photo from this listing')
        self.client.logout()
        self.assertEqual(self.client.get(f'/listings/{listing.pk}/photos/{extra.pk}/').status_code, 302)
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(f'/listings/999999/photos/{extra.pk}/').status_code, 404)
        self.assertEqual(self.client.post(f'/listings/{listing.pk}/edit/', self.data()).status_code, 403)

    def test_remove_all_photos_and_hard_delete_cleanup(self):
        listing = self.create_gallery()
        names = [listing.photo.name] + list(listing.extra_photos.values_list('image', flat=True))
        storage = listing.photo.storage
        tokens = ['cover'] + [f'extra-{item.pk}' for item in listing.extra_photos.all()]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/listings/{listing.pk}/edit/', self.data(remove_photos=tokens, cover_photo='cover'))
        self.assertEqual(response.status_code, 302)
        listing.refresh_from_db()
        self.assertFalse(listing.photo)
        self.assertEqual(listing.extra_photos.count(), 0)
        self.assertTrue(all(not storage.exists(name) for name in names))
        listing.delete()
        listing = self.create_gallery()
        names = [listing.photo.name] + list(listing.extra_photos.values_list('image', flat=True))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/listings/{listing.pk}/delete/', {'confirm': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ListingPhoto.objects.count(), 0)
        self.assertTrue(all(not storage.exists(name) for name in names))
