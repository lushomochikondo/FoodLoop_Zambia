from django.core.management.base import BaseCommand
from core.services import expire_requests

class Command(BaseCommand):
    help = 'Expire pending requests, record no-shows, release reservations, and notify providers of approaching deadlines.'
    def handle(self, *args, **options):
        self.stdout.write(f'Updated {expire_requests()} overdue requests.')
