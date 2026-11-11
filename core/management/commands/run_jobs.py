from django.core.management import call_command
from django.core.management.base import BaseCommand
import uuid
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.models import ScheduledJobState

class Command(BaseCommand):
    help = 'Run deadline processing and opt-in queued notification emails once.'
    def handle(self,*args,**options):
        # Old/new Render instances briefly overlap during deployment. Keep one
        # job runner across processes, including authenticated HTTP invocations.
        token = uuid.uuid4().hex
        with transaction.atomic():
            state, _ = ScheduledJobState.objects.get_or_create(name='notifications-and-deadlines')
            state = ScheduledJobState.objects.select_for_update().get(pk=state.pk)
            now = timezone.now()
            if state.claim_expires_at and state.claim_expires_at > now:
                self.stdout.write('Scheduled jobs are already running.')
                return
            state.claim_token = token
            state.claim_expires_at = now + timedelta(minutes=30)
            state.last_started_at = now
            state.save(update_fields=['claim_token', 'claim_expires_at', 'last_started_at'])
        try:
            self.run_cycle()
        except Exception:
            ScheduledJobState.objects.filter(pk=state.pk, claim_token=token).update(
                claim_token='', claim_expires_at=None, last_error='Scheduled jobs failed; check service logs.')
            raise
        else:
            ScheduledJobState.objects.filter(pk=state.pk, claim_token=token).update(
                claim_token='', claim_expires_at=None, last_completed_at=timezone.now(), last_error='')

    def run_cycle(self):
        call_command('process_deadlines', stdout=self.stdout)
        call_command('send_notifications', stdout=self.stdout, stderr=self.stderr)
        from core.push_delivery import deliver_push
        result=deliver_push()
        if result['sent'] or result['failed']:
            self.stdout.write(f"Phone notifications: {result['sent']} sent, {result['failed']} failed.")
