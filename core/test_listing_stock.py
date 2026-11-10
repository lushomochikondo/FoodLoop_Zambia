from decimal import Decimal
from django.test import TestCase, override_settings
from . import tests as workflow
from .models import Listing, FoodRequest
from .services import request_food, change_request
from .test_support import transition_request


@override_settings(EMAIL_NOTIFICATIONS_ENABLED=False, WEB_PUSH_ENABLED=False)
class ListingStockTests(TestCase):
    account=workflow.WorkflowTests.account
    setUp=workflow.WorkflowTests.setUp

    def assert_stock(self, available, reserved, collected):
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.remaining,Decimal(available))
        self.assertEqual(self.listing.reserved_quantity,Decimal(reserved))
        self.assertEqual(self.listing.collected_quantity,Decimal(collected))
        self.client.force_login(self.recipient)
        response=self.client.get('/listings/stock/',{'ids':str(self.listing.pk)})
        self.assertEqual(response.status_code,200)
        stock=response.json()['listings'][0]
        self.assertEqual(Decimal(stock['remaining']),Decimal(available))
        self.assertEqual(Decimal(stock['reserved']),Decimal(reserved))
        self.assertEqual(Decimal(stock['collected']),Decimal(collected))
        self.assertNotIn('address',stock)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def collect(self, request):
        for actor,action in [(self.provider,'ready'),(self.provider,'confirm'),(self.recipient,'confirm')]:
            transition_request(actor,request,action)

    def test_requests_reserve_on_acceptance_and_collections_are_not_deducted_twice(self):
        first=request_food(self.recipient,self.listing.pk,Decimal('4'),True)
        self.assert_stock('10','0','0')
        change_request(self.provider,first.pk,'accept')
        self.assert_stock('6','4','0')
        self.collect(first)
        self.assert_stock('6','0','4')
        second=request_food(self.recipient,self.listing.pk,Decimal('6'),True)
        change_request(self.provider,second.pk,'accept')
        self.assert_stock('0','6','4')
        self.assertEqual(self.listing.display_status,'Fully reserved')
        self.assertNotContains(self.client.get('/'),'>Bread<')
        change_request(self.recipient,second.pk,'cancel')
        self.assert_stock('6','0','4')
        self.assertContains(self.client.get('/'),'>Bread<')
        third=request_food(self.recipient,self.listing.pk,Decimal('6'),True)
        change_request(self.provider,third.pk,'accept')
        self.collect(third)
        self.assert_stock('0','0','10')
        self.assertEqual(self.listing.display_status,'Exhausted')
        self.assertEqual(self.listing.status_key,'exhausted')
        self.assertNotContains(self.client.get('/'),'>Bread<')
        response=self.client.get(f'/listings/{self.listing.pk}/')
        self.assertContains(response,'Exhausted')
        self.assertNotContains(response,'id="id_quantity"')
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
        self.assertEqual(FoodRequest.objects.filter(listing=self.listing,status='collected').count(),2)
        self.assertEqual(self.listing.quantity,Decimal('10'))

    def test_stock_endpoint_validates_ids_and_respects_donor_visibility(self):
        self.client.force_login(self.recipient)
        for ids in ('bad','-1','9999999999999999999999999999999',','.join(map(str,range(1,302)))):
            self.assertEqual(self.client.get('/listings/stock/',{'ids':ids}).status_code,400)
        other_donor=self.account('stock-other-donor','provider')
        self.client.force_login(other_donor)
        self.assertEqual(self.client.get('/listings/stock/',{'ids':self.listing.pk}).json()['listings'],[])
        self.client.logout()
        self.assertEqual(self.client.get('/listings/stock/',{'ids':self.listing.pk}).status_code,302)
