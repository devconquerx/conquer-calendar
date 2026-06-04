from django.db import migrations, models

TODOS = [
    '{{nombre_invitado}}', '{{email_invitado}}',
    '{{nombre_host}}', '{{email_host}}',
    '{{nombre_evento}}',
    '{{fecha_hora}}', '{{fecha_hora_utc}}', '{{timezone}}',
    '{{duracion}}',
    '{{google_meet_url}}', '{{google_event_url}}',
    '{{link_cancelar}}',
]


def set_defaults(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    PlantillaCorreo.objects.filter(campos_visibles=[]).update(campos_visibles=TODOS)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0013_plantillacorreo_color_encabezado'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacorreo',
            name='campos_visibles',
            field=models.JSONField(blank=True, default=list, verbose_name='Campos visibles en el correo'),
        ),
        migrations.RunPython(set_defaults, migrations.RunPython.noop),
    ]
