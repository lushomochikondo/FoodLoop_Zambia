from django.db import migrations
from django.db.models import F

def backfill(apps, schema_editor):
    Request = apps.get_model('core', 'FoodRequest')
    Request.objects.filter(status='collected', collected_at__isnull=True).update(collected_at=F('updated'))

class Migration(migrations.Migration):
    dependencies = [('core', '0006_foodrequest_collected_at_listing_listing_type_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
