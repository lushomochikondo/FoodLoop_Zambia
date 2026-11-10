from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0022_alter_listing_provider_alter_organisation_role')]
    operations = [migrations.AddField(model_name='listing', name='share_pickup_pin', field=models.BooleanField(default=False, help_text='Allow eligible organisations to see the exact pickup pin before requesting. The written address and phone remain private until acceptance.'))]
