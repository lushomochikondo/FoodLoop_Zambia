from django.core.management.base import BaseCommand
from core.email_delivery import deliver_pending

class Command(BaseCommand):
    help = 'Deliver opt-in notification emails with retries, short queue claims and private recipient settings.'
    def handle(self,*args,**options):
        result = deliver_pending()
        if result['disabled']:
            self.stdout.write('Email delivery is disabled; in-app notifications remain available.')
        else:
            self.stdout.write(f"Emails: {result['sent']} sent, {result['failed']} failed, {result['skipped']} skipped.")
