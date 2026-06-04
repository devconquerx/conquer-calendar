from django.db import migrations

CUERPOS = {
    'Confirmación — Host': (
        'Hola {{nombre_host}},\n\n'
        'Tienes una nueva reserva confirmada con {{nombre_invitado}}.'
    ),
    'Confirmación — Invitado': (
        'Hola {{nombre_invitado}},\n\n'
        'Tu reserva ha sido confirmada correctamente.'
    ),
    'Recordatorio de reserva': (
        'Hola {{nombre_invitado}},\n\n'
        'Te recordamos que tienes una reunión programada próximamente.'
    ),
}


def actualizar(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    for nombre, cuerpo in CUERPOS.items():
        PlantillaCorreo.objects.filter(nombre=nombre).update(cuerpo=cuerpo)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0011_recordatorio_formato_fecha'),
    ]

    operations = [
        migrations.RunPython(actualizar, migrations.RunPython.noop),
    ]
