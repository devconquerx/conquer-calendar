from django.db import migrations


def backfill_pool(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventTypeXHost = apps.get_model('event_types', 'EventTypeXHost')
    for et in EventType.objects.all():
        EventTypeXHost.objects.get_or_create(
            event_type=et, host_id=et.host_id,
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('event_types', '0003_eventtypexhost_and_more')]
    operations = [migrations.RunPython(backfill_pool, reverse_noop)]
