from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from .forms import ListingForm
from .models import FoodRequest
from . import test_routing


class PickupAccessTests(TestCase):
    setUp = test_routing.CollectionRouteTests.setUp
    def data(self, **updates):
        data = {'name':'Vegetables', 'quantity':'10', 'unit':'kg', 'pathway':'human', 'condition':'fresh', 'area':'Kasama', 'address':'Private entrance', 'deadline':(timezone.now()+timedelta(days=2)).isoformat(), 'safety_acknowledged':'on', 'pickup_latitude':'-10.211700', 'pickup_longitude':'31.180800', 'access_surface':'gravel', 'access_condition':'rough', 'access_notes':'Final 600 m is muddy after rain.'}
        data.update(updates)
        return data

    def test_donor_report_saved_and_timestamp_tracks_report_changes(self):
        form = ListingForm(data=self.data(), instance=self.listing)
        self.assertTrue(form.is_valid(), form.errors)
        listing = form.save()
        self.assertIsNotNone(listing.access_reported_at)
        original = listing.access_reported_at
        form = ListingForm(data=self.data(name='Renamed vegetables'), instance=listing)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().access_reported_at, original)
        form = ListingForm(data=self.data(access_notes='Road repaired yesterday.'), instance=listing)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertGreaterEqual(form.save().access_reported_at, original)
        form = ListingForm(data=self.data(access_surface='', access_condition='', access_notes=''), instance=listing)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().access_reported_at)

    def test_report_privacy_and_escaping(self):
        self.listing.access_surface = 'asphalt'
        self.listing.access_condition = 'rough'
        self.listing.access_notes = '<script>alert(1)</script> Private access landmark'
        self.listing.access_reported_at = timezone.now()
        self.listing.share_pickup_pin = True
        self.listing.save()
        url = f'/listings/{self.listing.pk}/'
        self.assertNotContains(self.client.get(url), 'Private access landmark')
        FoodRequest.objects.create(listing=self.listing, recipient=self.org, quantity=1, status='accepted')
        response = self.client.get(url)
        self.assertContains(response, 'Tarred / asphalt / bituminous')
        self.assertContains(response, 'Rough')
        self.assertContains(response, 'Donor reported')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_invalid_surface_is_rejected(self):
        form = ListingForm(data=self.data(access_surface='invented'), instance=self.listing)
        self.assertFalse(form.is_valid())
        self.assertIn('access_surface', form.errors)

    def test_editor_has_country_controls(self):
        from django.contrib.auth.models import User
        from .models import Membership
        user = User.objects.create_user('country-donor')
        Membership.objects.create(user=user, organisation=self.donor)
        self.client.force_login(user)
        response = self.client.get('/listings/new/')
        for text in ['Show all Zambia', 'Kasama', 'Mongu', 'Livingstone', 'Road access near pickup']:
            self.assertContains(response, text)
