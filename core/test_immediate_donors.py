from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_signup
from .models import Organisation, Listing, Membership


@override_settings(EMAIL_NOTIFICATIONS_ENABLED=False, WEB_PUSH_ENABLED=False)
class ImmediateDonorTests(TestCase):
    def test_new_donor_can_publish_and_beneficiary_sees_food_immediately(self):
        data = test_signup.SignupTests().data(account_type='provider', authorised_representative='on')
        response = self.client.post('/signup/?type=provider', data)
        self.assertRedirects(response, '/listings/new/')
        donor = User.objects.get(username='newmember')
        org = donor.membership.organisation
        self.assertEqual(org.status, 'approved')
        self.assertIsNone(org.last_verified_at)
        response = self.client.post('/listings/new/', {'name':'Immediate food', 'quantity':'20', 'unit':'kg', 'pathway':'human', 'condition':'fresh', 'area':'Lusaka', 'address':'Collection entrance', 'deadline':(timezone.now()+timedelta(days=2)).isoformat(), 'safety_acknowledged':'on'})
        listing = Listing.objects.get(name='Immediate food')
        self.assertRedirects(response, f'/listings/{listing.pk}/')
        beneficiary = User.objects.create_user('beneficiary')
        recipient = Organisation.objects.create(name='Kitchen',role='recipient',pathway='human',status='approved',area='Lusaka')
        Membership.objects.create(user=beneficiary,organisation=recipient)
        self.client.force_login(beneficiary)
        self.assertContains(self.client.get('/'), 'Immediate food')
        self.assertContains(self.client.get(f'/listings/{listing.pk}/'), 'Request collection')
        listing.pathway='compost';listing.condition='spoiled';listing.save()
        self.assertContains(self.client.get('/'), 'Immediate food')
        self.assertEqual(self.client.get(f'/listings/{listing.pk}/').status_code,200)
        self.assertEqual(self.client.post(f'/listings/{listing.pk}/', {'quantity':'1','safety':'on'}).status_code,302)

    def test_policy_migration_activates_pending_donors_only(self):
        donors = {status:Organisation.objects.create(name=status,role='provider',status=status,area='Lusaka') for status in ('pending','approved','suspended','rejected','needs_info')}
        recipient = Organisation.objects.create(name='Pending recipient',role='recipient',status='pending',area='Lusaka')
        recovery = Organisation.objects.create(name='Pending recovery',role='recovery',pathway='compost',status='pending',area='Lusaka')
        migrate = import_module('core.migrations.0025_enable_pending_donor_posting').enable_pending_donors
        migrate(apps, SimpleNamespace(connection=connection))
        for status, org in donors.items():
            org.refresh_from_db()
            self.assertEqual(org.status, 'approved' if status=='pending' else status)
        for org in (recipient,recovery):
            org.refresh_from_db();self.assertEqual(org.status,'pending')
        user=User.objects.create_user('blocked-donor')
        Membership.objects.create(user=user,organisation=donors['suspended'])
        self.client.force_login(user)
        self.assertEqual(self.client.get('/listings/new/').status_code,403)

    def test_signup_explains_immediate_posting(self):
        response=self.client.get('/signup/?type=provider')
        self.assertContains(response, 'Donors can publish immediately after registration.')
        self.assertNotContains(response, 'Listing and collection access is enabled only after approval.')
