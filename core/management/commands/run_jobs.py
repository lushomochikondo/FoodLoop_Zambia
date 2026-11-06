from django.core.management import call_command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Run deadline processing and opt-in queued notification emails once.'
    def handle(self,*args,**options):
        call_command('process_deadlines', stdout=self.stdout)
        call_command('send_notifications', stdout=self.stdout, stderr=self.stderr)
        from core.push_delivery import deliver_push
        result=deliver_push()
        if result['sent'] or result['failed']:
            self.stdout.write(f"Phone notifications: {result['sent']} sent, {result['failed']} failed.")
