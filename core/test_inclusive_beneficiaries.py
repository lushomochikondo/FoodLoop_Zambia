from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_signup
from .models import BeneficiaryApplication, Listing, Organisation, Membership, FoodRequest
from .services import verify_organisation, request_food, change_request


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

    def test_every_approved_beneficiary_can_request_every_pathway(self):
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
                self.assertContains(detail,'Request collection')
                self.assertContains(detail,'purpose shown on the listing')
                req=request_food(user,listing.pk,Decimal('1'),True)
                self.assertEqual(req.recipient_id,org.pk)
        self.assertEqual(FoodRequest.objects.count(),9)

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

    def test_cross_pathway_collection_completes_and_suspension_still_blocks_requests(self):
        from .test_support import transition_request
        donor_user=User.objects.create_user('multi-project-donor')
        donor=Organisation.objects.create(name='Multi-project donor',role='provider',status='approved',area='Lusaka')
        Membership.objects.create(user=donor_user,organisation=donor)
        user=User.objects.create_user('multi-project-beneficiary')
        org=Organisation.objects.create(name='School with agriculture project',role='recipient',pathway='human',status='approved',area='Lusaka')
        Membership.objects.create(user=user,organisation=org)
        listing=Listing.objects.create(provider=donor,name='Composting project material',quantity=20,pathway='compost',condition='spoiled',deadline=timezone.now()+timedelta(days=1),address='Private entrance',area='Lusaka',safety_acknowledged=True)
        req=request_food(user,listing.pk,Decimal('2'),True)
        for actor,action in [(donor_user,'accept'),(donor_user,'ready'),(donor_user,'confirm'),(user,'confirm')]:
            transition_request(actor,req,action)
        req.refresh_from_db();self.assertEqual(req.status,'collected')
        org.status='suspended';org.save()
        user.refresh_from_db()
        with self.assertRaises(PermissionDenied):request_food(user,listing.pk,Decimal('1'),True)

    def test_requests_need_acknowledgement_and_spoiled_food_cannot_be_requested_as_human_food(self):
        donor=Organisation.objects.create(name='Food donor',role='provider',status='approved',area='Lusaka')
        user=User.objects.create_user('open-requests-beneficiary')
        org=Organisation.objects.create(name='Agriculture project',role='recipient',pathway='compost',status='approved',area='Lusaka')
        Membership.objects.create(user=user,organisation=org)
        listing=Listing.objects.create(provider=donor,name='Misclassified spoiled food',quantity=10,pathway='human',condition='spoiled',deadline=timezone.now()+timedelta(days=1),address='Private entrance',area='Lusaka',safety_acknowledged=True)
        with self.assertRaises(PermissionDenied):request_food(user,listing.pk,Decimal('1'),True)
        listing.pathway='compost';listing.save()
        with self.assertRaises(ValidationError):request_food(user,listing.pk,Decimal('1'),False)

    def test_admin_can_manage_beneficiaries_with_livestock_or_compost_primary_interest(self):
        from .admin import OrganisationAdminForm
        for pathway in ('feed','compost'):
            form=OrganisationAdminForm(data={'name':'Programme '+pathway,'role':'recipient','pathway':pathway,'area':'Lusaka','status':'draft','usual_quantity':'10','usual_unit':'kg'})
            self.assertTrue(form.is_valid(),form.errors)
