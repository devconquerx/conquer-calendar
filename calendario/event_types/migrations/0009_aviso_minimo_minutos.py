from django.db import migrations, models


def horas_a_minutos(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.all().update(
        aviso_minimo_minutos=models.F('aviso_minimo_minutos') * 60
    )


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0008_eventtype_unico_por_invitado'),
    ]

    operations = [
        migrations.RenameField(
            model_name='eventtype',
            old_name='aviso_minimo_horas',
            new_name='aviso_minimo_minutos',
        ),
        migrations.AlterField(
            model_name='eventtype',
            name='aviso_minimo_minutos',
            field=models.PositiveSmallIntegerField(
                default=0,
                choices=[
                    (0,   'Sin aviso mínimo'),
                    (15,  '15 minutos'),
                    (30,  '30 minutos'),
                    (45,  '45 minutos'),
                    (60,  '1 hora'),
                    (120, '2 horas'),
                    (180, '3 horas'),
                ],
            ),
        ),
        migrations.RunPython(horas_a_minutos, migrations.RunPython.noop),
    ]
