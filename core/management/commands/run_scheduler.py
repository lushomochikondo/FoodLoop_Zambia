import time
import logging
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run background deadline/email jobs every five minutes; stop with Ctrl+C.'
    def add_arguments(self,parser):
        parser.add_argument('--interval',type=int,default=300)
    def handle(self,*args,**options):
        try:
            while True:
                close_old_connections()
                try:
                    call_command('run_jobs', stdout=self.stdout, stderr=self.stderr)
                except Exception:
                    # No exception text: provider responses may contain credentials.
                    logger.error('Scheduled jobs failed; retrying on the next interval.')
                finally:
                    close_old_connections()
                time.sleep(max(10,options['interval']))
        except KeyboardInterrupt:
            self.stdout.write('FoodLoop scheduler stopped.')
