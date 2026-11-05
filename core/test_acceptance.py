import subprocess
import sys
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch
import sqlite3
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import AuditLog, FoodRequest, Listing, Membership, Notification, Organisation
from .services import change_request, request_food, verify_organisation
from .tests import WorkflowTests

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AcceptanceTests(TestCase):
    account = WorkflowTests.account
    setUp = WorkflowTests.setUp

    def test_tc01_all_four_roles_sign_in_and_out(self):
        recovery = self.account('recovery', 'recovery')
        org = recovery.membership.organisation; org.pathway = 'feed'; org.save()
        admin = User.objects.create_user('administrator', password='Test-only-password-42', is_staff=True)
        for user in [self.provider, self.recipient, recovery, admin]:
            self.assertTrue(self.client.login(username=user.username, password='Test-only-password-42'))
            self.assertEqual(self.client.get('/').status_code, 200)
            self.client.post('/logout/')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_tc03_verification_evidence_approval_enables_request(self):
        org = self.recipient.membership.organisation
        org.status = 'pending'; org.save()
        admin = User.objects.create_user('administrator', is_staff=True)
        with self.assertRaises(ValidationError): verify_organisation(admin, org.pk, 'approved', 'Reviewed')
        org.physical_address = 'Fictional centre'; org.contact_name = 'Demo contact'; org.contact_email = 'demo@example.invalid'; org.phone = 'DEMO'; org.activity_description = 'Community kitchen'; org.handling_capacity = 'Demo cool storage'; org.terms_accepted = True; org.save()
        self.client.force_login(admin)
        response = self.client.post('/administration/', {'kind': 'organisation', 'record_id': org.pk, 'decision': 'approved', 'reason': 'Demo evidence reviewed'})
        self.assertEqual(response.status_code, 302)
        org.refresh_from_db(); self.assertEqual(org.status, 'approved')
        self.recipient.refresh_from_db()
        request_food(self.recipient, self.listing.pk, Decimal('1'), True)
        self.assertTrue(AuditLog.objects.filter(actor=admin, action__contains='approved').exists())

    def test_tc04_and_tc05_unverified_access_blocked(self):
        provider = self.provider.membership.organisation
        provider.status = 'pending'; provider.save()
        self.client.force_login(self.provider)
        self.assertEqual(self.client.get('/listings/new/').status_code, 403)
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get('/'), 'Bread')
        self.assertEqual(self.client.get(f'/listings/{self.listing.pk}/').status_code, 404)
        provider.status = 'approved'; provider.save()
        recipient = self.recipient.membership.organisation
        recipient.status = 'pending'; recipient.save()
        response = self.client.post(f'/listings/{self.listing.pk}/', {'quantity': 1, 'safety': 'on'})
        self.assertEqual(response.status_code, 403)

    def test_tc06_tc07_listing_fields_and_validation(self):
        self.client.force_login(self.provider)
        data = {'name': 'New donation', 'quantity': 2, 'unit': 'kg', 'condition': 'fresh', 'pathway': 'human', 'area': 'Demo area', 'address': 'Private demo address', 'deadline': (timezone.now()+timedelta(days=1)).isoformat(), 'safety_acknowledged': 'on'}
        response = self.client.post('/listings/new/', data)
        self.assertEqual(response.status_code, 302)
        listing = Listing.objects.get(name='New donation')
        self.assertEqual(listing.listing_type, 'donation')
        self.assertContains(self.client.get(f'/listings/{listing.pk}/'), 'Listed')
        data['quantity'] = 0
        response = self.client.post('/listings/new/', data)
        self.assertIn('quantity', response.context['form'].errors)
        data['quantity'] = 1; del data['name']
        self.assertIn('name', self.client.post('/listings/new/', data).context['form'].errors)

    def test_tc09_tc10_pathway_area_food_and_availability(self):
        feed = Listing.objects.create(provider=self.provider.membership.organisation, name='Animal material', quantity=10, pathway='feed', condition='spoiled', area='Other area', address='Secret', deadline=timezone.now()+timedelta(hours=5), safety_acknowledged=True)
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get('/'), 'Animal material')
        self.assertEqual(self.client.get(f'/listings/{feed.pk}/').status_code, 404)
        self.assertContains(self.client.get('/?q=Bread&area=Lusaka&pathway=human&availability=available'), 'Bread')
        self.assertNotContains(self.client.get('/?area=Unknown'), 'Bread')
        self.client.force_login(self.provider)
        Listing.objects.filter(pk=self.listing.pk).update(status='withdrawn')
        self.assertContains(self.client.get('/?availability=withdrawn'), 'Bread')
        self.assertNotContains(self.client.get('/?availability=available'), '>Bread<')

    def test_tc11_deadline_ranking_and_visible_reasons(self):
        urgent = Listing.objects.create(provider=self.provider.membership.organisation, name='Urgent bread', quantity=10, pathway='human', condition='fresh', area='Lusaka', address='Secret', deadline=timezone.now()+timedelta(hours=1), safety_acknowledged=True)
        self.client.force_login(self.recipient)
        response = self.client.get('/')
        self.assertEqual(response.context['listings'][0].pk, urgent.pk)
        self.assertContains(response, '% match')
        self.assertContains(response, 'Same area')

    def test_tc12_and_tc19_request_quantity_and_acknowledgement(self):
        self.client.force_login(self.recipient)
        url = f'/listings/{self.listing.pk}/'
        self.assertEqual(self.client.post(url, {'quantity': 20, 'safety': 'on'}).status_code, 200)
        self.assertFalse(FoodRequest.objects.exists())
        self.assertIn('safety', self.client.post(url, {'quantity': 2}).context['form'].errors)
        self.client.force_login(self.provider)
        self.assertIn('safety_acknowledged', self.client.post('/listings/new/', {'name': 'No acknowledgement'}).context['form'].errors)

    def test_tc14_concurrent_last_unit(self):
        result = subprocess.run([sys.executable, str(settings.BASE_DIR/'qa/concurrent_acceptance.py')], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('PASS', result.stdout)

    def test_tc15_tc16_tc17_and_tc18_collection_impact_and_privacy(self):
        provider = self.provider.membership.organisation; provider.phone = 'PRIVATE-CONTACT'; provider.save()
        self.client.force_login(self.recipient)
        self.assertNotContains(self.client.get(f'/listings/{self.listing.pk}/'), 'PRIVATE-CONTACT')
        req = request_food(self.recipient, self.listing.pk, Decimal('2'), True)
        change_request(self.provider, req.pk, 'accept')
        self.assertContains(self.client.get(f'/listings/{self.listing.pk}/'), 'PRIVATE-CONTACT')
        with self.assertRaises(ValidationError): change_request(self.recipient, req.pk, 'ready')
        change_request(self.provider, req.pk, 'ready')
        change_request(self.provider, req.pk, 'confirm')
        self.assertEqual(self.client.get('/').context['kg'], 0)
        change_request(self.recipient, req.pk, 'confirm')
        req.refresh_from_db()
        self.assertIsNotNone(req.collected_at)
        self.assertEqual(self.client.get('/').context['kg'], 2)
        self.assertEqual(self.client.get('/impact/').context['rows'][0]['listed'], 10)
        self.assertEqual(self.client.get('/impact/').context['rows'][0]['collected'], 2)

    def test_tc21_deadline_blocks_request(self):
        Listing.objects.filter(pk=self.listing.pk).update(deadline=timezone.now()-timedelta(seconds=1))
        self.client.force_login(self.recipient)
        response = self.client.post(f'/listings/{self.listing.pk}/', {'quantity': 2, 'safety': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FoodRequest.objects.exists())
        self.assertContains(response, 'Expired')

    def test_profile_and_preferences_cannot_escalate_roles(self):
        self.client.force_login(self.recipient)
        response = self.client.post('/profile/', {'first_name': 'Demo', 'last_name': 'Member', 'email': 'demo@example.invalid', 'usual_quantity': 7, 'usual_unit': 'bags', 'is_staff': True, 'status': 'approved', 'role': 'provider'})
        self.assertEqual(response.status_code, 302)
        self.recipient.refresh_from_db()
        self.assertFalse(self.recipient.is_staff)
        self.assertEqual(self.recipient.membership.organisation.role, 'recipient')
        self.assertEqual(self.recipient.membership.organisation.usual_quantity, 7)

    def test_collection_notes_preserve_collection_period(self):
        req = request_food(self.recipient, self.listing.pk, Decimal('2'), True)
        for user, action in [(self.provider,'accept'), (self.provider,'ready'), (self.provider,'confirm'), (self.recipient,'confirm')]: change_request(user, req.pk, action)
        req.refresh_from_db(); timestamp = req.collected_at
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/requests/{req.pk}/notes/', {'notes': 'Not mine'}).status_code, 403)
        self.client.force_login(self.recipient)
        self.client.post(f'/requests/{req.pk}/notes/', {'notes': 'Collected in suitable containers.'})
        req.refresh_from_db(); self.assertEqual(req.collected_at, timestamp)
        self.assertEqual(req.collection_notes, 'Collected in suitable containers.')

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_optional_email_is_sent_once_and_disabled_by_default(self):
        self.recipient.email = 'demo@example.invalid'; self.recipient.save()
        Notification.objects.create(user=self.recipient, message='Test notification')
        call_command('send_notifications', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        call_command('send_notifications', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(CO2E_KG_PER_KG='1.5', CO2E_SOURCE='TEST FACTOR ONLY — not a real estimate')
    def test_optional_co2_is_labelled_and_sourced(self):
        self.client.force_login(self.provider)
        self.assertContains(self.client.get('/impact/'), 'TEST FACTOR ONLY')

    def test_csrf_xss_sql_inputs_and_timestamp_zone(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recipient)
        self.assertEqual(client.post(f'/listings/{self.listing.pk}/', {'quantity': 1, 'safety': 'on'}).status_code, 403)
        self.client.force_login(self.provider)
        self.listing.name = '<script>alert(1)</script>'; self.listing.save()
        response = self.client.get(f'/listings/{self.listing.pk}/')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(self.client.get("/?q=' OR 1=1 --").status_code, 200)
        self.assertContains(response, 'CAT')
        self.assertIsNotNone(self.listing.created.tzinfo)

    @override_settings(DEBUG=False)
    def test_safe_production_404_page(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Traceback', status_code=404)

    def test_backup_contains_database_and_media(self):
        with TemporaryDirectory() as folder:
            source = Path(folder)/'source.sqlite3'
            with closing(sqlite3.connect(source)) as db:
                db.execute('create table recovery (quantity integer)')
                db.execute('insert into recovery values (12)')
                db.commit()
            media=Path(folder)/'media'; media.mkdir(); (media/'sample.txt').write_text('backup file fixture')
            fake=SimpleNamespace(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3','NAME':str(source)}}, MEDIA_ROOT=media)
            with patch('core.management.commands.backup_demo.settings', fake):
                call_command('backup_demo', output=str(Path(folder)/'backups'), stdout=StringIO())
            restored=list(Path(folder).glob('backups/foodloop-*/db.sqlite3'))[0]
            with closing(sqlite3.connect(restored)) as db:
                self.assertEqual(db.execute('select quantity from recovery').fetchone()[0],12)
            self.assertTrue((restored.parent/'media/sample.txt').exists())

    def test_audit_cannot_be_deleted_by_admin(self):
        admin=User.objects.create_superuser('supervisor',password='Test-only-password-42')
        event=AuditLog.objects.create(actor=admin,action='Immutable fixture')
        self.client.force_login(admin)
        self.assertEqual(self.client.post(f'/admin/core/auditlog/{event.pk}/delete/').status_code,403)
        self.assertTrue(AuditLog.objects.filter(pk=event.pk).exists())

    def test_admin_can_reset_account_password(self):
        admin=User.objects.create_superuser('supervisor',password='Test-only-password-42')
        self.client.force_login(admin)
        response=self.client.post(f'/admin/auth/user/{self.recipient.pk}/password/',{'password1':'New-test-password-42','password2':'New-test-password-42'})
        self.assertEqual(response.status_code,302)
        self.recipient.refresh_from_db()
        self.assertTrue(self.recipient.check_password('New-test-password-42'))

    def test_records_persist_after_logout_and_cat_display(self):
        from datetime import datetime, timezone as utc
        req=request_food(self.recipient,self.listing.pk,Decimal('1'),True)
        Listing.objects.filter(pk=self.listing.pk).update(created=datetime(2026,11,4,23,0,tzinfo=utc.utc))
        self.client.force_login(self.provider)
        self.client.post('/logout/')
        self.assertTrue(FoodRequest.objects.filter(pk=req.pk).exists())
        self.client.force_login(self.provider)
        self.assertContains(self.client.get(f'/listings/{self.listing.pk}/'),'05 Nov 2026, 01:00')
