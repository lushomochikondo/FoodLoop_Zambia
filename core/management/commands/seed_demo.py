import secrets
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Listing, Membership, Organisation

class Command(BaseCommand):
    help = 'Create fictional sample accounts and listings. Existing passwords are preserved.'
    def handle(self, *args, **options):
        password = secrets.token_urlsafe(12)
        accounts = [('provider', 'Sunrise Bakery', 'provider', 'human'), ('recipient', 'Hope Community Kitchen', 'recipient', 'human'), ('school', 'Bright Future School Feeding Programme', 'recipient', 'human'), ('farm', 'Mwana Livestock Farm', 'recovery', 'feed'), ('compost', 'EcoSoil Composting Co-op', 'recovery', 'compost')]
        for username, name, role, pathway in accounts:
            org, _ = Organisation.objects.get_or_create(name=name, defaults={'role': role, 'pathway': pathway, 'status': 'approved', 'area': 'Lusaka Central', 'phone': 'Fictional sample contact'})
            sample_evidence = {'contact_name': 'Fictional sample representative', 'contact_email': f'{username}@example.invalid', 'physical_address': 'Fictional sample address, Lusaka Central', 'registration_reference': 'sample — not a real registration', 'activity_description': 'Fictional food recovery partner for the controlled prototype.', 'handling_capacity': 'prototype storage and handling capacity; not a real-world assessment.', 'verification_reason': 'Fictional organisation approved for the controlled sample.'}
            for field, value in sample_evidence.items():
                if not getattr(org, field): setattr(org, field, value)
            org.save()
            user, created = User.objects.get_or_create(username=username)
            if created: user.set_password(password); user.save()
            Membership.objects.get_or_create(user=user, defaults={'organisation': org})
            if role == 'provider':
                for title, qty, route, condition in [('Fresh bread', 25, 'human', 'fresh'), ('Overripe produce', 40, 'feed', 'spoiled'), ('Vegetable trimmings', 30, 'compost', 'spoiled')]:
                    Listing.objects.get_or_create(provider=org, name=title, defaults={'quantity': qty, 'unit': 'kg', 'pathway': route, 'condition': condition, 'area': org.area, 'address': 'sample PRIVATE ADDRESS — 12 Example Road', 'deadline': timezone.now() + timedelta(days=2), 'safety_acknowledged': True, 'notes': 'Fictional prototype listing. Bring suitable collection containers.'})
        admin, created = User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True})
        if created: admin.set_password(password); admin.save()
        Organisation.objects.get_or_create(name='Pending Community Kitchen', defaults={'role': 'recipient', 'area': 'Lusaka Central'})
        self.stdout.write('Accounts: provider, recipient, school, farm, compost, admin')
        self.stdout.write('Password for newly created accounts: ' + password)
        self.stdout.write('Existing accounts and their passwords are preserved.')
