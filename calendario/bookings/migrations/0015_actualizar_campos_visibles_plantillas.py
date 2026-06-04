from django.db import migrations

CAMPOS_HOST = [
    '{{nombre_evento}}',
    '{{nombre_invitado}}', '{{email_invitado}}', '{{telefono_invitado}}',
    '{{fecha_hora_host}}', '{{timezone_host}}', '{{fecha_hora_utc}}',
    '{{duracion}}',
    '{{google_event_url}}', '{{google_meet_url}}', '{{link_reserva}}', '{{link_cancelar}}',
]

CAMPOS_INVITADO = [
    '{{nombre_evento}}',
    '{{nombre_host}}', '{{email_host}}',
    '{{fecha_hora_invitado}}', '{{timezone}}', '{{fecha_hora_utc}}',
    '{{duracion}}',
    '{{google_event_url}}', '{{google_meet_url}}', '{{link_cancelar}}',
]

CAMPOS_RECORDATORIO = [
    '{{nombre_evento}}',
    '{{nombre_host}}', '{{email_host}}',
    '{{fecha_hora_invitado}}', '{{timezone}}', '{{fecha_hora_utc}}',
    '{{duracion}}',
    '{{google_event_url}}', '{{google_meet_url}}', '{{link_cancelar}}',
]


def actualizar(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    PlantillaCorreo.objects.filter(nombre='Confirmación — Host').update(campos_visibles=CAMPOS_HOST)
    PlantillaCorreo.objects.filter(nombre='Confirmación — Invitado').update(campos_visibles=CAMPOS_INVITADO)
    PlantillaCorreo.objects.filter(nombre='Recordatorio de reserva').update(campos_visibles=CAMPOS_RECORDATORIO)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0014_plantillacorreo_campos_visibles'),
    ]

    operations = [
        migrations.RunPython(actualizar, migrations.RunPython.noop),
    ]
