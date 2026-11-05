from django.db import migrations
from django.db.models import F

def backfill(apps, schema_editor):
    Request = apps.get_model('core', 'FoodRequest')
    Request.objects.filter(status='collected', confirmed_quantity__isnull=True).update(confirmed_quantity=F('quantity'))

class Migration(migrations.Migration):
    dependencies = [('core', '0003_foodrequest_collection_notes_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
