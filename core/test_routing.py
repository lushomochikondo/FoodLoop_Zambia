import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, Mock
import requests
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from .models import Organisation, Membership, Listing, FoodRequest
from .routing import destination_for


class CollectionRouteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.donor = Organisation.objects.create(name='Donor', role='provider', status='approved')
        self.org = Organisation.objects.create(name='Recipient', role='recipient', status='approved', pathway='human')
        self.user = User.objects.create_user('route-user')
        Membership.objects.create(user=self.user, organisation=self.org)
        self.listing = Listing.objects.create(provider=self.donor, name='Food', quantity=10, pathway='human', condition='fresh', deadline=timezone.now()+timedelta(hours=4), pickup_latitude=Decimal('-15.416789'), pickup_longitude=Decimal('28.283456'))
        self.client.force_login(self.user)
        self.url = f'/listings/{self.listing.pk}/route/'

    def post(self, data):
        return self.client.post(self.url, json.dumps(data), content_type='application/json')

    def test_pin_privacy_and_acceptance(self):
        destination = destination_for(self.listing, self.user, self.org)
        self.assertFalse(destination['exact'])
        self.assertEqual(destination['latitude'], -15.42)
        req = FoodRequest.objects.create(listing=self.listing, recipient=self.org, quantity=1)
        self.assertFalse(destination_for(self.listing, self.user, self.org)['exact'])
        req.status = 'accepted'
        req.save()
        self.assertTrue(destination_for(self.listing, self.user, self.org)['exact'])
        req.status = 'cancelled'
        req.save()
        self.assertFalse(destination_for(self.listing, self.user, self.org)['exact'])
        self.listing.share_pickup_pin = True
        self.assertTrue(destination_for(self.listing, self.user, self.org)['exact'])

    def test_malformed_requests(self):
        for data in [None, [], 'text', {}, {'latitude':'NaN','longitude':28}, {'latitude':91,'longitude':28}, {'latitude':-15,'longitude':28,'mode':'plane'}]:
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)

    @patch('core.routing.requests.get')
    def test_routes_use_approximate_pin_and_sort(self, get):
        get.return_value = Mock(json=lambda: {'code':'Ok','routes':[{'distance':200,'duration':40,'geometry':{'type':'LineString','coordinates':[]}}, {'distance':100,'duration':60,'geometry':{'type':'LineString','coordinates':[]}}]})
        response = self.post({'latitude':-15,'longitude':28})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['routes'][0]['distance'], 100)
        self.assertIn('28.280000,-15.420000', get.call_args.args[0])
        self.assertNotIn('28.283456', get.call_args.args[0])
        self.assertEqual(self.post({'latitude':-15,'longitude':28}).status_code, 429)

    @patch('core.routing.requests.get', side_effect=requests.Timeout)
    def test_provider_failure(self, get):
        self.assertEqual(self.post({'latitude':-15,'longitude':28}).status_code, 503)

    @patch('core.routing.requests.get')
    def test_access_and_missing_pin(self, get):
        self.org.status = 'pending'
        self.org.save()
        self.assertEqual(self.post({'latitude':-15,'longitude':28}).status_code, 403)
        self.org.status = 'approved'
        self.org.pathway = 'feed'
        self.org.save()
        self.assertEqual(self.post({'latitude':-15,'longitude':28}).status_code, 404)
        self.org.pathway = 'human'
        self.org.save()
        self.listing.pickup_latitude = self.listing.pickup_longitude = None
        self.listing.save()
        self.assertEqual(self.post({'latitude':-15,'longitude':28}).status_code, 409)
        get.assert_not_called()

    def test_detail_and_editor_render(self):
        response = self.client.get(f'/listings/{self.listing.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open route planner')
        self.assertNotContains(response, '-15.416789')
