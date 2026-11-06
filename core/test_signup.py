from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from .models import AuditLog, BeneficiaryApplication, Membership, Notification, Organisation

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SignupTests(TestCase):
    def data(self, **updates):
        data={'username':'newmember','email':'member@example.invalid','password1':'New-account-password-42','password2':'New-account-password-42','organisation_name':'New Demo Kitchen','account_type':'recipient','contact_name':'Demo Member','phone':'DEMO CONTACT','area':'Lusaka Central','physical_address':'Fictional demo address','registration_reference':'','activity_description':'Community meals','handling_capacity':'Cold storage and safe containers','terms_accepted':'on'}
        data.update(updates)
        return data

    def test_signup_is_discoverable_from_login(self):
        response=self.client.get('/login/')
        self.assertContains(response,'Create an account')
        self.assertContains(response,'/signup/')
        self.assertEqual(self.client.get('/signup/').status_code,200)

    def test_recipient_signup_creates_pending_organisation_and_session(self):
        admin=User.objects.create_user('supervisor',is_staff=True)
        response=self.client.post('/signup/',self.data())
        self.assertRedirects(response,'/')
        user=User.objects.get(username='newmember')
        self.assertTrue(user.check_password('New-account-password-42'))
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        org=user.membership.organisation
        self.assertEqual(org.status,'pending'); self.assertEqual(org.role,'recipient'); self.assertEqual(org.pathway,'human')
        self.assertEqual(org.contact_email,'member@example.invalid')
        self.assertTrue(org.terms_accepted)
        self.assertTrue(AuditLog.objects.filter(actor=user).exists())
        self.assertTrue(Notification.objects.filter(user=admin).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']),user.pk)
        self.assertEqual(self.client.get('/listings/new/').status_code,403)

    def test_beneficiary_application_can_be_saved_and_submitted_for_review(self):
        response=self.client.post('/signup/?type=recipient',self.data())
        self.assertRedirects(response,'/beneficiary/application/')
        org=Organisation.objects.get(name='New Demo Kitchen')
        self.assertEqual(org.status,'draft')
        application=BeneficiaryApplication.objects.get(organisation=org)
        self.assertIsNone(application.submitted_at)
        self.assertEqual(self.client.get('/beneficiary/application/').status_code,200)
        response=self.client.post('/beneficiary/application/',{
            'action':'submit','legal_form':'community','programme_type':'community_kitchen',
            'people_served':'35','feeding_days_per_week':'3','years_operating':'1.5',
            'health_clearance':'not_required','health_clearance_note':'We use a partner venue.',
            'food_handler_evidence':'yes','food_handler_note':'','storage_description':'Covered containers and cool storage.',
            'governance_description':'Community committee','community_references':'Ward office contact available.',
            'beneficiary_records':'on','no_resale_agreement':'on','nondiscrimination_agreement':'on',
            'inspection_consent':'on','information_accuracy':'on','has_food_transport':'on',
            'has_performance_indicators':'on','has_financial_records':'on','staff_or_volunteers':'4',
            'additional_context':'',
        })
        self.assertRedirects(response,'/beneficiary/application/')
        org.refresh_from_db(); application.refresh_from_db()
        self.assertEqual(org.status,'pending')
        self.assertIsNotNone(application.submitted_at)

    def test_role_and_approval_escalation_inputs_are_ignored(self):
        self.client.post('/signup/',self.data(is_staff='on',is_superuser='on',status='approved',role='administrator',pathway='feed'))
        user=User.objects.get(username='newmember')
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertEqual(user.membership.organisation.status,'pending')
        self.assertEqual(user.membership.organisation.pathway,'human')
        self.client.logout()
        response=self.client.post('/signup/',self.data(username='badrole',organisation_name='Bad role',account_type='admin'))
        self.assertIn('account_type',response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='badrole').exists())

    def test_provider_and_both_recovery_pathways(self):
        for kind,role,pathway in [('provider','provider','human'),('feed','recovery','feed'),('compost','recovery','compost')]:
            self.client.post('/signup/',self.data(username=f'new{kind}',email=f'{kind}@example.invalid',organisation_name=f'New {kind}',account_type=kind,authorised_representative='on'))
            org=User.objects.get(username=f'new{kind}').membership.organisation
            self.assertEqual((org.role,org.pathway,org.status),(role,pathway,'pending'))
            self.client.logout()

    def test_password_terms_and_conditional_evidence_validation(self):
        cases=[({'password2':'different'},'password2'),({'terms_accepted':''},'terms_accepted'),({'handling_capacity':''},'handling_capacity'),({'account_type':'provider'},'authorised_representative')]
        for updates,field in cases:
            response=self.client.post('/signup/',self.data(**updates))
            self.assertIn(field,response.context['form'].errors)
            self.assertFalse(User.objects.filter(username='newmember').exists())
        self.assertFalse(Organisation.objects.exists())

    def test_duplicates_and_atomic_rollback(self):
        User.objects.create_user('NEWMember')
        response=self.client.post('/signup/',self.data())
        self.assertIn('username',response.context['form'].errors)
        self.assertFalse(Organisation.objects.exists())
        Organisation.objects.create(name='New Demo Kitchen',role='recipient',area='Lusaka')
        response=self.client.post('/signup/',self.data(username='another'))
        self.assertIn('organisation_name',response.context['form'].errors)
        with patch('core.views.Membership.objects.create',side_effect=RuntimeError('Rollback fixture')):
            with self.assertRaises(RuntimeError):
                self.client.post('/signup/',self.data(username='rollback',organisation_name='Rollback organisation'))
        self.assertFalse(User.objects.filter(username='rollback').exists())
        self.assertFalse(Organisation.objects.filter(name='Rollback organisation').exists())

    def test_csrf_is_required(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/signup/',self.data()).status_code,403)
