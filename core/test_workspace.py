from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import DropOffLocation,FoodRequest,NewsArticle
from .services import request_food
from .tests import WorkflowTests

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkspaceTests(TestCase):
    account=WorkflowTests.account
    setUp=WorkflowTests.setUp

    def test_home_is_listing_exchange_and_dashboard_is_separate(self):
        self.client.force_login(self.provider)
        home=self.client.get('/')
        self.assertTemplateUsed(home,'exchange.html')
        self.assertNotContains(home,'analytics-stats')
        self.assertContains(home,'id="menu-toggle"')
        self.assertContains(home,'#i-menu')
        self.assertNotContains(home,'icons/3d/')
        dashboard=self.client.get('/dashboard/')
        self.assertTemplateUsed(dashboard,'dashboard.html')
        self.assertContains(dashboard,'analytics-stats')
        self.assertEqual(len(dashboard.context['daily_collections']),7)
        self.assertTrue(all(day['quantity']==0 for day in dashboard.context['daily_collections']))

    def test_collection_actions_stay_on_collection_page(self):
        req=request_food(self.recipient,self.listing.pk,Decimal('2'),True)
        self.client.force_login(self.provider)
        page=self.client.get('/requests/?status=pending')
        self.assertContains(page,f'/requests/{req.pk}/accept/')
        response=self.client.post(f'/requests/{req.pk}/accept/',{'return_to_collections':'1'})
        self.assertRedirects(response,'/requests/')
        req.refresh_from_db();self.assertEqual(req.status,'accepted')
        self.assertNotContains(self.client.get('/requests/?status=pending'),'>Bread<')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/requests/'),'>Bread<')

    def test_footer_links_and_company_pages_are_public(self):
        for url in ['/company/who-we-are/','/company/our-story/','/company/our-teams/','/company/partners/','/faq/','/news/','/drop-off-locations/']:
            page=self.client.get(url)
            self.assertEqual(page.status_code,200,url)
            self.assertContains(page,'Beaver Technologies Limited.')
            self.assertNotContains(page,'Social Link')
        self.assertEqual(self.client.get('/company/unknown/').status_code,404)

    def test_public_dropoffs_do_not_expose_private_pickup_addresses(self):
        DropOffLocation.objects.create(name='Private review location',area='Lusaka',address='UNPUBLISHED-DROPOFF',published=False)
        DropOffLocation.objects.create(name='Public collection centre',area='Lusaka',address='CONFIRMED-PUBLIC-DROPOFF',published=True)
        page=self.client.get('/drop-off-locations/')
        self.assertContains(page,'CONFIRMED-PUBLIC-DROPOFF')
        self.assertNotContains(page,'UNPUBLISHED-DROPOFF')
        self.assertNotContains(page,'SECRET-PICKUP-ADDRESS')

    def test_only_published_current_news_is_public(self):
        for title,slug,published,time in [('Current update','current',True,timezone.now()-timedelta(days=1)),('Draft update','draft',False,timezone.now()),('Future update','future',True,timezone.now()+timedelta(days=1))]:
            NewsArticle.objects.create(title=title,slug=slug,summary='Platform information',body='Article text',published=published,published_at=time)
        page=self.client.get('/news/')
        self.assertContains(page,'Current update')
        self.assertNotContains(page,'Draft update')
        self.assertNotContains(page,'Future update')
        self.assertEqual(self.client.get('/news/current/').status_code,200)
        self.assertEqual(self.client.get('/news/draft/').status_code,404)
        self.assertEqual(self.client.get('/news/future/').status_code,404)

    def test_heatmap_uses_completed_scoped_collections_and_local_dates(self):
        from .services import change_request
        req=request_food(self.recipient,self.listing.pk,Decimal('2'),True)
        for actor,action in [(self.provider,'accept'),(self.provider,'ready'),(self.provider,'confirm'),(self.recipient,'confirm')]:
            change_request(actor,req.pk,action)
        self.client.force_login(self.provider)
        response=self.client.get('/dashboard/')
        self.assertEqual(response.context['heatmap_total'],1)
        self.assertEqual(response.context['heatmap_active_days'],1)
        self.assertEqual(response.context['heatmap_peak'],1)
        self.assertTrue(response.context['has_recovery'])
        cells=[cell for week in response.context['heatmap_weeks'] for cell in week['days']]
        self.assertEqual(len(cells),84)
        self.assertEqual(sum(cell['count'] for cell in cells),1)
        self.assertEqual(next(cell for cell in cells if cell['count'])['date'],timezone.localdate())
        self.client.force_login(self.other)
        other=self.client.get('/dashboard/')
        self.assertEqual(other.context['heatmap_total'],0)
        self.assertFalse(other.context['has_recovery'])
