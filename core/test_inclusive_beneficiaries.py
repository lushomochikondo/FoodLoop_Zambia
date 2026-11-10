from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_signup
from .models import BeneficiaryApplication, Listing, Organisation, Membership, FoodRequest
from .services import verify_organisation, request_food


@override_settings(EMAIL_NOTIFICATIONS_ENABLED=False, WEB_PUSH_ENABLED=False)
class InclusiveBeneficiaryTests(TestCase):
    def test_eligibility_includes_all_recovery_categories(self):
        page=self.client.get('/beneficiary/eligibility/')
        for text in ('Livestock farmer / animal feed', 'Composting / organic recovery', 'Tertiary institution', 'Orphans and vulnerable children programme'):
            self.assertContains(page,text)

    def test_recovery_categories_can_register_submit_and_be_approved(self):
        admin=User.objects.create_user('inclusive-admin',is_staff=True)
        for programme,pathway in [('livestock_farmer','feed'),('composting_operator','compost')]:
            with self.subTest(programme=programme):
                self.client.logout()
                self.client.post('/beneficiary/eligibility/',{'programme_type':programme,'accepted':'on'})
                data=test_signup.SignupTests().data(username=programme,email=programme+'@example.invalid',organisation_name=programme)
                response=self.client.post('/signup/?type=recipient',data)
                self.assertRedirects(response,'/beneficiary/application/')
                org=Organisation.objects.get(name=programme)
                self.assertEqual((org.role,org.pathway,org.status),('recipient',pathway,'draft'))
                page=self.client.get('/beneficiary/application/')
                self.assertNotContains(page,'id_people_served')
                self.assertNotContains(page,'id_health_clearance')
                response=self.client.post('/beneficiary/application/',{'action':'submit','legal_form':'community','programme_type':programme,'storage_description':'Describe animals and feed handling or compost site and process.','beneficiary_records':'on','no_resale_agreement':'on','inspection_consent':'on','information_accuracy':'on'})
                self.assertRedirects(response,'/beneficiary/application/')
                org.refresh_from_db();self.assertEqual(org.status,'pending')
                verify_organisation(admin,org.pk,'approved','Recovery handling details reviewed.')
                org.refresh_from_db();self.assertEqual(org.status,'approved')

    def test_every_beneficiary_can_browse_all_pathways_but_request_only_approved_use(self):
        donor=Organisation.objects.create(name='Donor',role='provider',status='approved',area='Lusaka')
        listings={p:Listing.objects.create(provider=donor,name='Visible '+p,quantity=10,pathway=p,condition='fresh' if p=='human' else 'spoiled',deadline=timezone.now()+timedelta(days=1),address='PRIVATE-ENTRANCE',area='Lusaka',safety_acknowledged=True) for p in ('human','feed','compost')}
        for pathway in ('human','feed','compost'):
            user=User.objects.create_user('viewer-'+pathway)
            org=Organisation.objects.create(name=pathway,role='recipient',pathway=pathway,status='approved',area='Lusaka')
            Membership.objects.create(user=user,organisation=org)
            self.client.force_login(user)
            page=self.client.get('/')
            self.assertEqual(len(page.context['listings']),3)
            self.assertEqual(page.context['listings'][0].pathway,pathway)
            for p,listing in listings.items():
                self.assertContains(page,listing.name)
                detail=self.client.get(f'/listings/{listing.pk}/')
                self.assertEqual(detail.status_code,200)
                self.assertNotContains(detail,'PRIVATE-ENTRANCE')
                if p==pathway:
                    self.assertContains(detail,'Request collection')
                else:
                    self.assertNotContains(detail,'Request collection')
                    self.assertContains(detail,'Browse this listing')
                    with self.assertRaises(PermissionDenied):request_food(user,listing.pk,Decimal('1'),True)
            req=request_food(user,listings[pathway].pk,Decimal('1'),True)
            self.assertEqual(req.recipient_id,org.pk)
        self.assertEqual(FoodRequest.objects.count(),3)

    def test_human_application_cannot_switch_to_recovery_without_matching_category(self):
        user=User.objects.create_user('human-applicant')
        org=Organisation.objects.create(name='Human group',role='recipient',pathway='human',status='draft',area='Lusaka')
        Membership.objects.create(user=user,organisation=org)
        BeneficiaryApplication.objects.create(organisation=org,programme_type='community_kitchen')
        self.client.force_login(user)
        response=self.client.post('/beneficiary/application/',{'action':'save','programme_type':'livestock_farmer'})
        self.assertEqual(response.status_code,200)
        self.assertIn('programme_type',response.context['form'].errors)
        org.refresh_from_db();self.assertEqual(org.pathway,'human')
