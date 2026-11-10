from django.db import migrations


def enable_pending_donors(apps, schema_editor):
    Organisation = apps.get_model('core', 'Organisation')
    AuditLog = apps.get_model('core', 'AuditLog')
    alias = schema_editor.connection.alias
    for org in Organisation.objects.using(alias).filter(role='provider', status='pending').iterator():
        org.status = 'approved'
        org.verification_reason = 'Donor posting enabled under immediate-publishing policy; administrator approval is not required.'
        org.save(using=alias, update_fields=['status', 'verification_reason'])
        AuditLog.objects.using(alias).create(action=f'Organisation {org.pk}: pending donor posting enabled under immediate-publishing policy.')


class Migration(migrations.Migration):
    dependencies = [('core', '0024_listing_access_condition_listing_access_notes_and_more')]
    operations = [migrations.RunPython(enable_pending_donors, migrations.RunPython.noop)]
