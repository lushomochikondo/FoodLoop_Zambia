from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from .models import BeneficiaryApplication, Membership, Organisation, Notification
from . import test_signup


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BeneficiaryReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('reviewer', password='Test-password-42')
        self.user = User.objects.create_user('beneficiary', password='Test-password-42')
        self.org = Organisation.objects.create(name='Draft Community Kitchen', role='recipient', status='draft', area='Lusaka')
        Membership.objects.create(user=self.user, organisation=self.org)
        BeneficiaryApplication.objects.create(organisation=self.org)

    def test_admin_can_see_draft_registration_separately(self):
        self.client.force_login(self.admin)
        response = self.client.get('/administration/')
        self.assertContains(response, 'Draft Community Kitchen')
        self.assertContains(response, 'Beneficiary registrations not yet submitted')
        self.assertNotIn(self.org, response.context['organisations'])
        self.assertIn(self.org, response.context['beneficiary_drafts'])

    def test_beneficiary_can_resume_application_from_menu(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/beneficiary/application/'), 'My beneficiary application')
        self.assertEqual(self.client.get('/administration/').status_code, 403)

    def test_registration_notifies_admin_and_remains_draft(self):
        self.client.post('/beneficiary/eligibility/', {'programme_type':'community_kitchen', 'accepted':'on'})
        data = test_signup.SignupTests().data(username='newbeneficiary')
        response = self.client.post('/signup/?type=recipient', data)
        self.assertRedirects(response, '/beneficiary/application/')
        org = Organisation.objects.get(name=data['organisation_name'])
        self.assertEqual(org.status, 'draft')
        self.assertTrue(Notification.objects.filter(user=self.admin, message__contains='not yet submitted').exists())

    def test_draft_cannot_be_approved(self):
        self.client.force_login(self.admin)
        self.client.post('/administration/', {'kind':'organisation','record_id':self.org.pk,'decision':'approved','reason':'Reviewed by administrator'})
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'draft')

    def test_submitted_assessment_reaches_review_queue(self):
        self.client.force_login(self.user)
        response = self.client.post('/beneficiary/application/', {
            'action':'submit', 'legal_form':'community', 'programme_type':'community_kitchen',
            'people_served':'35', 'feeding_days_per_week':'3', 'health_clearance':'not_required',
            'health_clearance_note':'Partner venue', 'food_handler_evidence':'yes',
            'storage_description':'Covered containers and cool storage', 'beneficiary_records':'on',
            'no_resale_agreement':'on', 'nondiscrimination_agreement':'on',
            'inspection_consent':'on', 'information_accuracy':'on',
        })
        self.assertRedirects(response, '/beneficiary/application/')
        self.org.refresh_from_db()
        self.assertEqual(self.org.status, 'pending')
        self.assertTrue(Notification.objects.filter(user=self.admin, message__contains='awaiting review').exists())
        self.client.force_login(self.admin)
        response = self.client.get('/administration/')
        self.assertIn(self.org, response.context['organisations'])
        self.assertNotIn(self.org, response.context['beneficiary_drafts'])
