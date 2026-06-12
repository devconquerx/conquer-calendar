from django.db import migrations


def ajustar_incremento(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(duracion_minutos__gt=30).update(incremento_inicio_minutos=60)
    EventType.objects.filter(duracion_minutos__lte=30).update(incremento_inicio_minutos=30)


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0012_set_incremento_inicio_default_30'),
    ]

    operations = [
        migrations.RunPython(ajustar_incremento, migrations.RunPython.noop),
    ]
