from django.db import migrations


CUERPOS = {
    'Confirmación — Host': (
        'Hola {{nombre_host}},\n\n'
        'Tienes una nueva reserva confirmada.\n\n'
        'Invitado: {{nombre_invitado}} ({{email_invitado}})\n'
        'Fecha y hora: {{fecha_hora}}\n'
        'Duración: {{duracion}} minutos'
    ),
    'Confirmación — Invitado': (
        'Hola {{nombre_invitado}},\n\n'
        'Tu reserva ha sido confirmada correctamente.\n\n'
        'Con: {{nombre_host}}\n'
        'Fecha y hora: {{fecha_hora}}\n'
        'Duración: {{duracion}} minutos'
    ),
    'Recordatorio de reserva': (
        'Hola {{nombre_invitado}},\n\n'
        'Te recordamos que tienes una reunión programada próximamente.\n\n'
        'Con: {{nombre_host}}\n'
        'Fecha y hora: {{fecha_hora}}\n'
        'Duración: {{duracion}} minutos'
    ),
}


def actualizar_cuerpos(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    for nombre, cuerpo in CUERPOS.items():
        PlantillaCorreo.objects.filter(nombre=nombre).update(cuerpo=cuerpo)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0008_plantillas_ejemplo'),
    ]

    operations = [
        migrations.RunPython(actualizar_cuerpos, migrations.RunPython.noop),
    ]
