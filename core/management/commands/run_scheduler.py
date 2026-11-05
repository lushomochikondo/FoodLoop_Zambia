import time
from django.core.management import call_command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Run background deadline/email jobs every five minutes; stop with Ctrl+C.'
    def add_arguments(self,parser):
        parser.add_argument('--interval',type=int,default=300)
    def handle(self,*args,**options):
        try:
            while True:
                call_command('run_jobs', stdout=self.stdout, stderr=self.stderr)
                time.sleep(max(10,options['interval']))
        except KeyboardInterrupt:
            self.stdout.write('FoodLoop scheduler stopped.')
