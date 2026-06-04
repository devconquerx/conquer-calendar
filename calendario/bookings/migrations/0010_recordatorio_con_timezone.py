from django.db import migrations

CUERPO = (
    'Hola {{nombre_invitado}},\n\n'
    'Te recordamos que tienes una reunión programada próximamente.\n\n'
    'Con: {{nombre_host}}\n'
    'Fecha y hora: {{fecha_hora}} ({{timezone}}) — {{fecha_hora_utc}}\n'
    'Duración: {{duracion}} minutos'
)


def actualizar(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    PlantillaCorreo.objects.filter(nombre='Recordatorio de reserva').update(cuerpo=CUERPO)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0009_actualizar_cuerpos_plantillas_ejemplo'),
    ]

    operations = [
        migrations.RunPython(actualizar, migrations.RunPython.noop),
    ]
